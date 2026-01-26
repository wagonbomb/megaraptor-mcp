"""
Velociraptor API client wrapper.

Provides a high-level interface to the Velociraptor gRPC API.
"""

import json
import grpc
import tempfile
import os
from typing import Any, AsyncIterator, Optional
from contextlib import contextmanager
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from .config import VelociraptorConfig, load_config
from .error_handling import is_retryable_grpc_error

# Import Velociraptor gRPC stubs
try:
    import pyvelociraptor
    from pyvelociraptor import api_pb2
    from pyvelociraptor import api_pb2_grpc
except ImportError:
    # Define minimal stubs if pyvelociraptor not installed
    api_pb2 = None
    api_pb2_grpc = None


class VelociraptorClient:
    """Client for interacting with Velociraptor server via gRPC API."""

    def __init__(self, config: Optional[VelociraptorConfig] = None):
        """Initialize the Velociraptor client.

        Args:
            config: Configuration for connecting to Velociraptor.
                   If not provided, will be loaded from environment.
        """
        self.config = config or load_config()
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[Any] = None

    @contextmanager
    def _temp_cert_files(self):
        """Create temporary files for certificates.

        Velociraptor's gRPC client expects file paths for certificates,
        so we need to write the PEM content to temp files.
        """
        temp_files = []
        try:
            # Write CA cert
            ca_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".pem", delete=False
            )
            ca_file.write(self.config.ca_cert)
            ca_file.close()
            temp_files.append(ca_file.name)

            # Write client cert
            cert_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".pem", delete=False
            )
            cert_file.write(self.config.client_cert)
            cert_file.close()
            temp_files.append(cert_file.name)

            # Write client key
            key_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".pem", delete=False
            )
            key_file.write(self.config.client_key)
            key_file.close()
            temp_files.append(key_file.name)

            yield ca_file.name, cert_file.name, key_file.name
        finally:
            # Clean up temp files
            for f in temp_files:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def _create_channel(self) -> grpc.Channel:
        """Create a gRPC channel with TLS credentials."""
        if api_pb2_grpc is None:
            raise ImportError(
                "pyvelociraptor is required. Install with: pip install pyvelociraptor"
            )

        with self._temp_cert_files() as (ca_path, cert_path, key_path):
            # Read certs for gRPC credentials
            with open(ca_path, "rb") as f:
                ca_cert = f.read()
            with open(cert_path, "rb") as f:
                client_cert = f.read()
            with open(key_path, "rb") as f:
                client_key = f.read()

            # Create SSL credentials
            credentials = grpc.ssl_channel_credentials(
                root_certificates=ca_cert,
                private_key=client_key,
                certificate_chain=client_cert,
            )

            # Parse the API URL to get host:port
            api_url = self.config.api_url
            if api_url.startswith("https://"):
                api_url = api_url[8:]
            elif api_url.startswith("http://"):
                api_url = api_url[7:]

            # Create the channel
            channel = grpc.secure_channel(api_url, credentials)

            return channel

    def connect(self) -> None:
        """Establish connection to the Velociraptor server."""
        if self._channel is None:
            self._channel = self._create_channel()
            self._stub = api_pb2_grpc.APIStub(self._channel)

    def close(self) -> None:
        """Close the connection to the Velociraptor server."""
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None

    @retry(
        retry=retry_if_exception(is_retryable_grpc_error),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def query(
        self,
        vql: str,
        env: Optional[dict[str, Any]] = None,
        org_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Execute a VQL query and return results.

        Automatic retry on transient failures (UNAVAILABLE, DEADLINE_EXCEEDED,
        RESOURCE_EXHAUSTED) with exponential backoff (1s, 2s, 4s up to 10s max).
        No retry on validation errors, authentication errors, or not found errors.

        Args:
            vql: The VQL query to execute
            env: Optional environment variables for the query
            org_id: Optional organization ID for multi-tenant setups
            timeout: Query timeout in seconds (default: 30.0)

        Returns:
            List of result rows as dictionaries
        """
        if self._stub is None:
            self.connect()

        # Build the request
        env_list = []
        if env:
            for key, value in env.items():
                env_list.append(
                    api_pb2.VQLEnv(key=key, value=json.dumps(value))
                )

        request = api_pb2.VQLCollectorArgs(
            Query=[api_pb2.VQLRequest(VQL=vql)],
            env=env_list,
            org_id=org_id or "",
        )

        # Execute the query and collect results
        results = []
        for response in self._stub.Query(request, timeout=timeout):
            if response.Response:
                # Parse JSON response
                try:
                    rows = json.loads(response.Response)
                    if isinstance(rows, list):
                        results.extend(rows)
                    else:
                        results.append(rows)
                except json.JSONDecodeError:
                    # Non-JSON response, skip
                    pass

        return results

    @retry(
        retry=retry_if_exception(is_retryable_grpc_error),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def query_stream(
        self,
        vql: str,
        env: Optional[dict[str, Any]] = None,
        org_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute a VQL query and stream results.

        Automatic retry on transient failures (UNAVAILABLE, DEADLINE_EXCEEDED,
        RESOURCE_EXHAUSTED) with exponential backoff (1s, 2s, 4s up to 10s max).
        No retry on validation errors, authentication errors, or not found errors.

        Args:
            vql: The VQL query to execute
            env: Optional environment variables for the query
            org_id: Optional organization ID for multi-tenant setups
            timeout: Query timeout in seconds (default: 30.0)

        Yields:
            Result rows as dictionaries
        """
        if self._stub is None:
            self.connect()

        # Build the request
        env_list = []
        if env:
            for key, value in env.items():
                env_list.append(
                    api_pb2.VQLEnv(key=key, value=json.dumps(value))
                )

        request = api_pb2.VQLCollectorArgs(
            Query=[api_pb2.VQLRequest(VQL=vql)],
            env=env_list,
            org_id=org_id or "",
        )

        # Execute the query and stream results
        for response in self._stub.Query(request, timeout=timeout):
            if response.Response:
                try:
                    rows = json.loads(response.Response)
                    if isinstance(rows, list):
                        for row in rows:
                            yield row
                    else:
                        yield rows
                except json.JSONDecodeError:
                    pass

    def __enter__(self) -> "VelociraptorClient":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# Global client instance
_client: Optional[VelociraptorClient] = None


def get_client() -> VelociraptorClient:
    """Get or create the global Velociraptor client instance."""
    global _client
    if _client is None:
        _client = VelociraptorClient()
        _client.connect()
    return _client


def reset_client() -> None:
    """Reset the global client instance."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
