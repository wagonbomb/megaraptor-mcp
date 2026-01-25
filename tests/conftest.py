"""Shared pytest fixtures for megaraptor-mcp tests.

This module provides fixtures for both unit tests (no external dependencies)
and integration tests (requires Docker infrastructure).
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Generator, Optional

import pytest

# Test configuration constants
FIXTURES_DIR = Path(__file__).parent / "fixtures"
COMPOSE_FILE = Path(__file__).parent / "docker-compose.test.yml"
SERVER_CONFIG = FIXTURES_DIR / "server.config.yaml"
CLIENT_CONFIG = FIXTURES_DIR / "client.config.yaml"
API_CLIENT_CONFIG = FIXTURES_DIR / "api_client.yaml"

# Timeouts and retries
DOCKER_STARTUP_TIMEOUT = 60  # seconds
HEALTH_CHECK_INTERVAL = 5  # seconds
HEALTH_CHECK_RETRIES = 12


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (no external dependencies)")
    config.addinivalue_line("markers", "integration: Requires Docker infrastructure")
    config.addinivalue_line("markers", "slow: Long-running tests")


def has_docker() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def has_velociraptor_configs() -> bool:
    """Check if Velociraptor configs exist."""
    return SERVER_CONFIG.exists() and CLIENT_CONFIG.exists()


def is_velociraptor_running() -> bool:
    """Check if Velociraptor test containers are running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=vr-test-server", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "Up" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# Skip decorators for conditional test execution
skip_no_docker = pytest.mark.skipif(
    not has_docker(),
    reason="Docker not available"
)

skip_no_configs = pytest.mark.skipif(
    not has_velociraptor_configs(),
    reason="Velociraptor configs not generated. Run: ./scripts/test-lab.sh generate-config"
)


@pytest.fixture(scope="session")
def docker_available() -> bool:
    """Check if Docker is available for tests."""
    return has_docker()


@pytest.fixture(scope="session")
def velociraptor_configs_exist() -> bool:
    """Check if Velociraptor configs exist."""
    return has_velociraptor_configs()


@pytest.fixture(scope="session")
def docker_compose_up(docker_available: bool, velociraptor_configs_exist: bool) -> Generator[bool, None, None]:
    """Start test infrastructure for integration tests.

    This fixture starts the Docker Compose stack if not already running,
    waits for health checks to pass, and tears down on completion.

    Yields:
        True if infrastructure is ready, False otherwise
    """
    if not docker_available:
        pytest.skip("Docker not available")
        return

    if not velociraptor_configs_exist:
        pytest.skip("Velociraptor configs not generated")
        return

    # Check if already running
    already_running = is_velociraptor_running()

    if not already_running:
        # Start containers
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.fail(f"Failed to start Docker Compose: {result.stderr}")

        # Wait for health check
        for i in range(HEALTH_CHECK_RETRIES):
            if is_velociraptor_running():
                break
            time.sleep(HEALTH_CHECK_INTERVAL)
        else:
            # Cleanup on failure
            subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
                capture_output=True,
            )
            pytest.fail("Velociraptor server failed to become healthy")

    yield True

    # Only tear down if we started it
    if not already_running:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down"],
            capture_output=True,
        )


@pytest.fixture(scope="session")
def velociraptor_api_config(docker_compose_up: bool) -> dict:
    """Provide Velociraptor API configuration for tests.

    Returns:
        Dictionary with API connection settings
    """
    if not docker_compose_up:
        pytest.skip("Velociraptor infrastructure not running")

    return {
        "api_url": "https://localhost:18001",
        "config_path": str(API_CLIENT_CONFIG),
        "server_config_path": str(SERVER_CONFIG),
    }


@pytest.fixture
def temp_deployment_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide an isolated directory for deployment artifacts.

    Yields:
        Path to a temporary deployment directory
    """
    deploy_dir = tmp_path / "deployments"
    deploy_dir.mkdir()
    yield deploy_dir
    # Cleanup handled automatically by tmp_path


@pytest.fixture
def temp_certs_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide an isolated directory for certificate storage.

    Yields:
        Path to a temporary certificates directory
    """
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    yield certs_dir


@pytest.fixture
def temp_credentials_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide an isolated directory for credential storage.

    Yields:
        Path to a temporary credentials directory
    """
    creds_dir = tmp_path / "credentials"
    creds_dir.mkdir()
    yield creds_dir


@pytest.fixture
def clean_env(monkeypatch):
    """Provide a clean environment without Velociraptor config vars.

    Removes environment variables that might interfere with config tests.
    """
    env_vars = [
        "VELOCIRAPTOR_CONFIG_PATH",
        "VELOCIRAPTOR_API_URL",
        "VELOCIRAPTOR_CLIENT_CERT",
        "VELOCIRAPTOR_CLIENT_KEY",
        "VELOCIRAPTOR_CA_CERT",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_velociraptor_config(tmp_path: Path) -> dict:
    """Create a mock Velociraptor API config file.

    Returns:
        Dictionary with paths to the mock config
    """
    import yaml

    config_data = {
        "api_url": "https://velociraptor.test:8001",
        "ca_certificate": "-----BEGIN CERTIFICATE-----\nMOCK_CA_CERT\n-----END CERTIFICATE-----",
        "client_cert": "-----BEGIN CERTIFICATE-----\nMOCK_CLIENT_CERT\n-----END CERTIFICATE-----",
        "client_private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_PRIVATE_KEY\n-----END PRIVATE KEY-----",
    }

    config_file = tmp_path / "api_client.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return {
        "config_path": str(config_file),
        "config_data": config_data,
    }


@pytest.fixture(scope="module")
def velociraptor_client(docker_compose_up, velociraptor_api_config):
    """Create module-scoped Velociraptor client with lifecycle management.

    Reuses gRPC connection across all tests in a module to prevent
    connection exhaustion (gRPC channels should be long-lived).
    """
    if not docker_compose_up:
        pytest.skip("Docker infrastructure not available")

    from megaraptor_mcp.client import VelociraptorClient, reset_client
    from megaraptor_mcp.config import VelociraptorConfig

    config_path = velociraptor_api_config["config_path"]
    if not Path(config_path).exists():
        pytest.skip(f"API client config not found: {config_path}")

    config = VelociraptorConfig.from_config_file(config_path)
    client = VelociraptorClient(config)

    # Explicit connection
    client.connect()

    yield client

    # Explicit cleanup
    try:
        client.close()
    finally:
        reset_client()  # Reset global client state


@pytest.fixture(autouse=True)
def reset_global_client_state():
    """Reset global client before each test for isolation.

    Mitigates global _client instance to prevent state leakage.
    """
    from megaraptor_mcp.client import reset_client
    reset_client()
    yield
    reset_client()


# Autouse fixture for test isolation
@pytest.fixture(autouse=True)
def isolate_test_artifacts(tmp_path: Path, monkeypatch) -> Generator[None, None, None]:
    """Ensure tests don't affect the real system.

    Sets environment variables to redirect all storage to temp directories.
    """
    # Redirect XDG data home to temp directory
    test_data_home = tmp_path / "data"
    test_data_home.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(test_data_home))

    # On Windows, also set LOCALAPPDATA
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(test_data_home))

    yield

    # Cleanup is automatic with tmp_path


@pytest.fixture(autouse=True, scope="function")
def cleanup_velociraptor_state(request, velociraptor_client):
    """Clean up Velociraptor entities after each test.

    This autouse fixture runs after every integration test to remove:
    - Hunts with TEST- prefix in description
    - Labels with TEST- prefix from all clients

    Prevents state pollution between tests.
    """
    test_name = request.node.name

    yield  # Test runs here

    # After test: cleanup (only if client is available)
    if velociraptor_client is None:
        return

    try:
        from tests.integration.helpers.cleanup_helpers import (
            cleanup_test_hunts,
            cleanup_test_labels,
        )

        # Archive test hunts
        archived_hunts = cleanup_test_hunts(velociraptor_client, "TEST-")
        if archived_hunts:
            print(f"Cleanup [{test_name}]: Archived {len(archived_hunts)} hunt(s)")

        # Remove test labels
        cleaned_clients = cleanup_test_labels(velociraptor_client, "TEST-")
        if cleaned_clients:
            print(f"Cleanup [{test_name}]: Removed labels from {len(cleaned_clients)} client(s)")

    except ImportError:
        # Helpers not available yet (this is fine during plan execution)
        pass
    except Exception as e:
        # Log cleanup failure but don't fail test
        print(f"Cleanup warning for {test_name}: {e}")
