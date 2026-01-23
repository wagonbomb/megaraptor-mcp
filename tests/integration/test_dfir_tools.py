"""Integration tests for DFIR tools against real Velociraptor server.

These tests require the Docker test infrastructure to be running.
Start with: ./scripts/test-lab.sh up

The tests verify that the MCP tools correctly interact with a real
Velociraptor server and enrolled client.
"""

import asyncio
import time
from pathlib import Path

import pytest

# These tests require Docker infrastructure
pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(scope="module")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def velociraptor_client(docker_compose_up, velociraptor_api_config):
    """Create a Velociraptor client for testing.

    This fixture creates a VelociraptorClient connected to the test server.
    """
    if not docker_compose_up:
        pytest.skip("Docker infrastructure not available")

    try:
        from megaraptor_mcp.client import VelociraptorClient
        from megaraptor_mcp.config import VelociraptorConfig

        # Load config from the API client file
        config_path = velociraptor_api_config["config_path"]

        if not Path(config_path).exists():
            pytest.skip(f"API client config not found: {config_path}")

        config = VelociraptorConfig.from_config_file(config_path)
        client = VelociraptorClient(config)
        return client

    except ImportError as e:
        pytest.skip(f"Required module not available: {e}")
    except Exception as e:
        pytest.skip(f"Failed to create Velociraptor client: {e}")


class TestClientManagement:
    """Tests for client management tools."""

    async def test_list_clients(self, velociraptor_client):
        """Test listing all enrolled clients."""
        result = await velociraptor_client.list_clients()

        # Should return a list (may be empty if client hasn't enrolled yet)
        assert isinstance(result, list)

    async def test_list_clients_with_limit(self, velociraptor_client):
        """Test listing clients with a limit."""
        result = await velociraptor_client.list_clients(limit=10)

        assert isinstance(result, list)
        assert len(result) <= 10

    async def test_list_clients_with_search(self, velociraptor_client):
        """Test listing clients with search filter."""
        # Search for our test client container name
        result = await velociraptor_client.list_clients(search="vr-test-client")

        assert isinstance(result, list)

    async def test_get_client_info_not_found(self, velociraptor_client):
        """Test getting info for non-existent client."""
        # Use a client ID that definitely doesn't exist
        result = await velociraptor_client.get_client_info("C.0000000000000000")

        # Should return None or empty for non-existent client
        assert result is None or result == {}


class TestArtifactOperations:
    """Tests for artifact operations."""

    async def test_list_artifacts(self, velociraptor_client):
        """Test listing available artifacts."""
        result = await velociraptor_client.list_artifacts()

        assert isinstance(result, list)
        assert len(result) > 0  # Should have built-in artifacts

    async def test_list_artifacts_with_search(self, velociraptor_client):
        """Test listing artifacts with search filter."""
        # Search for generic artifacts
        result = await velociraptor_client.list_artifacts(search="Generic")

        assert isinstance(result, list)
        # Should find some Generic.* artifacts
        if len(result) > 0:
            assert any("Generic" in str(a) for a in result)

    async def test_get_artifact(self, velociraptor_client):
        """Test getting artifact details."""
        # Get a common built-in artifact
        result = await velociraptor_client.get_artifact("Generic.Client.Info")

        assert result is not None
        # Should contain artifact definition

    async def test_get_artifact_not_found(self, velociraptor_client):
        """Test getting non-existent artifact."""
        result = await velociraptor_client.get_artifact("NonExistent.Artifact.Name")

        assert result is None or result == {}


class TestVQLOperations:
    """Tests for VQL query operations."""

    async def test_run_simple_vql(self, velociraptor_client):
        """Test running a simple VQL query."""
        # Simple query that should work on any server
        result = await velociraptor_client.run_vql("SELECT * FROM info()")

        assert result is not None
        assert isinstance(result, (list, dict))

    async def test_run_vql_with_syntax_error(self, velociraptor_client):
        """Test VQL with syntax error returns appropriate error."""
        # Invalid VQL syntax
        with pytest.raises(Exception):
            await velociraptor_client.run_vql("INVALID VQL SYNTAX HERE")

    async def test_run_vql_clients_query(self, velociraptor_client):
        """Test VQL query against clients table."""
        result = await velociraptor_client.run_vql(
            "SELECT client_id, os_info FROM clients() LIMIT 10"
        )

        assert result is not None
        assert isinstance(result, (list, dict))


class TestHuntOperations:
    """Tests for hunt operations."""

    @pytest.fixture
    def created_hunt_id(self, velociraptor_client, event_loop):
        """Create a hunt for testing and clean up after."""
        hunt_id = None

        async def create_hunt():
            nonlocal hunt_id
            result = await velociraptor_client.create_hunt(
                description="Test Hunt - Integration Test",
                artifact_name="Generic.Client.Info",
            )
            if result and "hunt_id" in result:
                hunt_id = result["hunt_id"]
            return hunt_id

        event_loop.run_until_complete(create_hunt())
        yield hunt_id

        # Cleanup: stop and archive the hunt
        if hunt_id:
            async def cleanup_hunt():
                try:
                    await velociraptor_client.modify_hunt(
                        hunt_id, state="ARCHIVED"
                    )
                except Exception:
                    pass  # Best effort cleanup

            event_loop.run_until_complete(cleanup_hunt())

    async def test_list_hunts(self, velociraptor_client):
        """Test listing all hunts."""
        result = await velociraptor_client.list_hunts()

        assert isinstance(result, list)

    async def test_create_hunt(self, velociraptor_client, created_hunt_id):
        """Test creating a new hunt."""
        assert created_hunt_id is not None
        assert created_hunt_id.startswith("H.")

    async def test_get_hunt_results(self, velociraptor_client, created_hunt_id):
        """Test getting hunt results."""
        if not created_hunt_id:
            pytest.skip("Hunt creation failed")

        # Give the hunt a moment to start
        await asyncio.sleep(2)

        result = await velociraptor_client.get_hunt_results(created_hunt_id)

        # May be empty if no clients matched, but should not error
        assert result is not None


class TestFlowOperations:
    """Tests for flow operations."""

    async def test_list_flows_no_client(self, velociraptor_client):
        """Test listing flows for non-existent client returns empty."""
        result = await velociraptor_client.list_flows("C.0000000000000000")

        assert isinstance(result, list)
        assert len(result) == 0

    async def test_get_flow_status_invalid(self, velociraptor_client):
        """Test getting status of invalid flow."""
        result = await velociraptor_client.get_flow_status(
            client_id="C.0000000000000000",
            flow_id="F.INVALID",
        )

        # Should return None or empty for invalid flow
        assert result is None or result == {}


class TestServerHealth:
    """Tests for server health and connectivity."""

    async def test_server_reachable(self, velociraptor_client):
        """Test that the Velociraptor server is reachable."""
        # Use info() VQL as a health check
        result = await velociraptor_client.run_vql("SELECT * FROM info()")

        assert result is not None

    async def test_multiple_concurrent_queries(self, velociraptor_client):
        """Test running multiple VQL queries concurrently."""
        queries = [
            "SELECT * FROM info()",
            "SELECT * FROM clients() LIMIT 5",
            "SELECT * FROM artifact_definitions() LIMIT 5",
        ]

        tasks = [velociraptor_client.run_vql(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All queries should complete without error
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Query {i} failed: {result}"
