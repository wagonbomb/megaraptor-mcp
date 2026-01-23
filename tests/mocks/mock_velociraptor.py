"""Mock Velociraptor server and client for unit testing.

These mocks simulate Velociraptor's gRPC API responses without
requiring a real server. Use for unit tests that need to verify
tool behavior without Docker infrastructure.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock


@dataclass
class MockClient:
    """Represents a mock Velociraptor client."""

    client_id: str
    hostname: str
    os_info: Dict[str, str] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_ip: str = "192.168.1.100"

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.first_seen_at:
            self.first_seen_at = now
        if not self.last_seen_at:
            self.last_seen_at = now
        if not self.os_info:
            self.os_info = {
                "system": "Linux",
                "release": "5.15.0",
                "machine": "x86_64",
            }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching Velociraptor API."""
        return {
            "client_id": self.client_id,
            "os_info": self.os_info,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "last_ip": self.last_ip,
            "labels": self.labels,
            "hostname": self.hostname,
        }


@dataclass
class MockArtifact:
    """Represents a mock Velociraptor artifact."""

    name: str
    description: str = ""
    author: str = "Test"
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching Velociraptor API."""
        return {
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "parameters": self.parameters,
            "sources": self.sources,
        }


@dataclass
class MockHunt:
    """Represents a mock Velociraptor hunt."""

    hunt_id: str
    description: str
    artifact_name: str
    state: str = "RUNNING"
    created_time: str = ""
    stats: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_time:
            self.created_time = datetime.now(timezone.utc).isoformat()
        if not self.stats:
            self.stats = {
                "total_clients_scheduled": 0,
                "total_clients_with_results": 0,
            }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching Velociraptor API."""
        return {
            "hunt_id": self.hunt_id,
            "hunt_description": self.description,
            "artifacts": [self.artifact_name],
            "state": self.state,
            "create_time": self.created_time,
            "stats": self.stats,
        }


@dataclass
class MockFlow:
    """Represents a mock Velociraptor flow."""

    flow_id: str
    client_id: str
    artifact_name: str
    state: str = "RUNNING"
    created_time: str = ""

    def __post_init__(self):
        if not self.created_time:
            self.created_time = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching Velociraptor API."""
        return {
            "session_id": self.flow_id,
            "client_id": self.client_id,
            "request": {
                "artifacts": [self.artifact_name],
            },
            "state": self.state,
            "create_time": self.created_time,
        }


class MockVelociraptorServer:
    """Mock Velociraptor server for testing.

    Simulates a Velociraptor server's gRPC API, storing state in memory.
    Use for unit tests that don't need real infrastructure.

    Example:
        server = MockVelociraptorServer()
        server.add_client(MockClient(
            client_id="C.1234567890abcdef",
            hostname="test-client-1",
        ))

        client = MockVelociraptorClient(server)
        result = await client.list_clients()
    """

    def __init__(self):
        """Initialize the mock server with empty state."""
        self.clients: Dict[str, MockClient] = {}
        self.artifacts: Dict[str, MockArtifact] = {}
        self.hunts: Dict[str, MockHunt] = {}
        self.flows: Dict[str, MockFlow] = {}
        self._hunt_counter = 0
        self._flow_counter = 0

        # Add some default artifacts
        self._add_default_artifacts()

    def _add_default_artifacts(self):
        """Add common artifacts for testing."""
        default_artifacts = [
            MockArtifact(
                name="Generic.Client.Info",
                description="Collect basic client information",
            ),
            MockArtifact(
                name="Generic.System.Info",
                description="Collect system information",
            ),
            MockArtifact(
                name="Windows.System.Processes",
                description="List running processes",
            ),
            MockArtifact(
                name="Linux.Sys.Users",
                description="List users on Linux systems",
            ),
        ]
        for artifact in default_artifacts:
            self.artifacts[artifact.name] = artifact

    def add_client(self, client: MockClient):
        """Add a client to the mock server."""
        self.clients[client.client_id] = client

    def add_artifact(self, artifact: MockArtifact):
        """Add an artifact to the mock server."""
        self.artifacts[artifact.name] = artifact

    def create_hunt(self, description: str, artifact_name: str) -> MockHunt:
        """Create a new hunt."""
        self._hunt_counter += 1
        hunt_id = f"H.{self._hunt_counter:08x}"
        hunt = MockHunt(
            hunt_id=hunt_id,
            description=description,
            artifact_name=artifact_name,
        )
        self.hunts[hunt_id] = hunt
        return hunt

    def create_flow(self, client_id: str, artifact_name: str) -> MockFlow:
        """Create a new flow."""
        self._flow_counter += 1
        flow_id = f"F.{self._flow_counter:08x}"
        flow = MockFlow(
            flow_id=flow_id,
            client_id=client_id,
            artifact_name=artifact_name,
        )
        self.flows[flow_id] = flow
        return flow

    def reset(self):
        """Reset all state."""
        self.clients.clear()
        self.hunts.clear()
        self.flows.clear()
        self._hunt_counter = 0
        self._flow_counter = 0


class MockVelociraptorClient:
    """Mock Velociraptor client for testing.

    Wraps a MockVelociraptorServer to provide the same interface as
    the real VelociraptorClient, but without network calls.
    """

    def __init__(self, server: Optional[MockVelociraptorServer] = None):
        """Initialize the mock client.

        Args:
            server: Mock server to use. Creates new one if not provided.
        """
        self.server = server or MockVelociraptorServer()

    async def list_clients(
        self,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List enrolled clients."""
        clients = list(self.server.clients.values())

        if search:
            search_lower = search.lower()
            clients = [
                c for c in clients
                if search_lower in c.client_id.lower()
                or search_lower in c.hostname.lower()
            ]

        return [c.to_dict() for c in clients[:limit]]

    async def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client information."""
        client = self.server.clients.get(client_id)
        return client.to_dict() if client else None

    async def label_client(
        self,
        client_id: str,
        labels: List[str],
        operation: str = "add",
    ) -> bool:
        """Add or remove client labels."""
        client = self.server.clients.get(client_id)
        if not client:
            return False

        if operation == "add":
            client.labels.extend(labels)
            client.labels = list(set(client.labels))  # Remove duplicates
        elif operation == "remove":
            client.labels = [l for l in client.labels if l not in labels]

        return True

    async def list_artifacts(
        self,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List available artifacts."""
        artifacts = list(self.server.artifacts.values())

        if search:
            search_lower = search.lower()
            artifacts = [
                a for a in artifacts
                if search_lower in a.name.lower()
                or search_lower in a.description.lower()
            ]

        return [a.to_dict() for a in artifacts]

    async def get_artifact(self, name: str) -> Optional[Dict[str, Any]]:
        """Get artifact details."""
        artifact = self.server.artifacts.get(name)
        return artifact.to_dict() if artifact else None

    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Collect an artifact from a client."""
        if client_id not in self.server.clients:
            raise ValueError(f"Client not found: {client_id}")

        if artifact_name not in self.server.artifacts:
            raise ValueError(f"Artifact not found: {artifact_name}")

        flow = self.server.create_flow(client_id, artifact_name)
        return flow.to_dict()

    async def list_hunts(self) -> List[Dict[str, Any]]:
        """List all hunts."""
        return [h.to_dict() for h in self.server.hunts.values()]

    async def create_hunt(
        self,
        description: str,
        artifact_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new hunt."""
        if artifact_name not in self.server.artifacts:
            raise ValueError(f"Artifact not found: {artifact_name}")

        hunt = self.server.create_hunt(description, artifact_name)
        return {"hunt_id": hunt.hunt_id}

    async def get_hunt_results(self, hunt_id: str) -> List[Dict[str, Any]]:
        """Get hunt results."""
        hunt = self.server.hunts.get(hunt_id)
        if not hunt:
            return []

        # Return mock results
        return [
            {"client_id": c.client_id, "collected": True}
            for c in self.server.clients.values()
        ]

    async def modify_hunt(
        self,
        hunt_id: str,
        state: Optional[str] = None,
    ) -> bool:
        """Modify hunt state."""
        hunt = self.server.hunts.get(hunt_id)
        if not hunt:
            return False

        if state:
            hunt.state = state

        return True

    async def list_flows(self, client_id: str) -> List[Dict[str, Any]]:
        """List flows for a client."""
        flows = [
            f for f in self.server.flows.values()
            if f.client_id == client_id
        ]
        return [f.to_dict() for f in flows]

    async def get_flow_results(
        self,
        client_id: str,
        flow_id: str,
    ) -> List[Dict[str, Any]]:
        """Get flow results."""
        flow = self.server.flows.get(flow_id)
        if not flow or flow.client_id != client_id:
            return []

        # Return mock results
        return [{"result": "mock data"}]

    async def get_flow_status(
        self,
        client_id: str,
        flow_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get flow status."""
        flow = self.server.flows.get(flow_id)
        if not flow or flow.client_id != client_id:
            return None

        return flow.to_dict()

    async def run_vql(self, query: str) -> List[Dict[str, Any]]:
        """Run a VQL query."""
        # Simple mock responses for common queries
        query_lower = query.lower()

        if "from info()" in query_lower:
            return [{"version": "0.7.0", "name": "MockVelociraptor"}]

        if "from clients()" in query_lower:
            return [c.to_dict() for c in self.server.clients.values()]

        if "from artifact_definitions()" in query_lower:
            return [a.to_dict() for a in self.server.artifacts.values()]

        # Default empty result for unknown queries
        return []


def create_mock_velociraptor_fixture():
    """Create pytest fixtures for mock Velociraptor.

    Example usage in conftest.py:
        from tests.mocks.mock_velociraptor import create_mock_velociraptor_fixture

        mock_server, mock_client = create_mock_velociraptor_fixture()

    Returns:
        Tuple of (server_fixture, client_fixture)
    """
    import pytest

    @pytest.fixture
    def mock_velociraptor_server():
        """Provide a fresh mock server for each test."""
        server = MockVelociraptorServer()

        # Add a default test client
        server.add_client(MockClient(
            client_id="C.1234567890abcdef",
            hostname="test-client-1",
        ))

        yield server
        server.reset()

    @pytest.fixture
    def mock_velociraptor_client(mock_velociraptor_server):
        """Provide a mock client connected to the mock server."""
        return MockVelociraptorClient(mock_velociraptor_server)

    return mock_velociraptor_server, mock_velociraptor_client
