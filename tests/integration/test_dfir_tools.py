"""Integration tests for DFIR tools against real Velociraptor server.

These tests require the Docker test infrastructure to be running.
Start with: ./scripts/test-lab.sh up

The tests verify that the MCP tools correctly interact with a real
Velociraptor server and enrolled client.
"""

import pytest

# These tests require Docker infrastructure
pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestClientManagement:
    """Tests for client management via VQL."""

    def test_list_clients(self, velociraptor_client):
        """Test listing all enrolled clients using VQL."""
        result = velociraptor_client.query("SELECT * FROM clients() LIMIT 10")

        # Should return a list (may be empty if client hasn't enrolled yet)
        assert isinstance(result, list)

    def test_list_clients_with_limit(self, velociraptor_client):
        """Test listing clients with a limit."""
        result = velociraptor_client.query("SELECT * FROM clients() LIMIT 5")

        assert isinstance(result, list)
        assert len(result) <= 5

    def test_list_clients_with_search(self, velociraptor_client):
        """Test listing clients with search filter."""
        # Search for our test client container name pattern
        result = velociraptor_client.query(
            "SELECT * FROM clients() WHERE os_info.hostname =~ 'test' LIMIT 10"
        )

        assert isinstance(result, list)

    def test_get_client_info_query(self, velociraptor_client):
        """Test getting info for a specific client pattern."""
        # Query for any client - will return empty if none enrolled
        result = velociraptor_client.query(
            "SELECT * FROM clients() WHERE client_id =~ 'C\\.' LIMIT 1"
        )

        assert isinstance(result, list)


class TestArtifactOperations:
    """Tests for artifact operations via VQL."""

    def test_list_artifacts(self, velociraptor_client):
        """Test listing available artifacts."""
        result = velociraptor_client.query(
            "SELECT name, description FROM artifact_definitions() LIMIT 50"
        )

        assert isinstance(result, list)
        assert len(result) > 0  # Should have built-in artifacts

    def test_list_artifacts_with_search(self, velociraptor_client):
        """Test listing artifacts with search filter."""
        # Search for generic artifacts
        result = velociraptor_client.query(
            "SELECT name FROM artifact_definitions() WHERE name =~ 'Generic' LIMIT 20"
        )

        assert isinstance(result, list)
        # Should find some Generic.* artifacts
        if len(result) > 0:
            assert any("Generic" in str(a.get("name", "")) for a in result)

    def test_get_artifact(self, velociraptor_client):
        """Test getting artifact details."""
        # Get a common built-in artifact
        result = velociraptor_client.query(
            "SELECT * FROM artifact_definitions() WHERE name = 'Generic.Client.Info'"
        )

        assert isinstance(result, list)
        # Should find the artifact
        if len(result) > 0:
            assert result[0].get("name") == "Generic.Client.Info"

    def test_get_artifact_not_found(self, velociraptor_client):
        """Test getting non-existent artifact."""
        result = velociraptor_client.query(
            "SELECT * FROM artifact_definitions() WHERE name = 'NonExistent.Artifact.Name'"
        )

        # Should return empty list
        assert isinstance(result, list)
        assert len(result) == 0


class TestVQLOperations:
    """Tests for VQL query operations."""

    def test_run_simple_vql(self, velociraptor_client):
        """Test running a simple VQL query."""
        # Simple query that should work on any server
        result = velociraptor_client.query("SELECT * FROM info()")

        assert result is not None
        assert isinstance(result, list)

    def test_run_vql_with_syntax_error(self, velociraptor_client):
        """Test VQL with syntax error returns empty result.

        Note: Velociraptor returns an empty list for invalid VQL
        rather than raising an exception.
        """
        # Invalid VQL syntax returns empty result
        result = velociraptor_client.query("INVALID VQL SYNTAX HERE")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_run_vql_clients_query(self, velociraptor_client):
        """Test VQL query against clients table."""
        result = velociraptor_client.query(
            "SELECT client_id, os_info FROM clients() LIMIT 10"
        )

        assert result is not None
        assert isinstance(result, list)


class TestHuntOperations:
    """Tests for hunt operations via VQL.

    Note: These tests use VQL to query hunt information.
    Creating hunts via the API may require additional setup.
    """

    def test_list_hunts(self, velociraptor_client):
        """Test listing all hunts."""
        result = velociraptor_client.query(
            "SELECT hunt_id, hunt_description, state FROM hunts() LIMIT 20"
        )

        assert isinstance(result, list)


class TestFlowOperations:
    """Tests for flow operations via VQL."""

    def test_list_flows_query(self, velociraptor_client):
        """Test listing flows using VQL."""
        # Query for flows - will be empty if no flows exist
        result = velociraptor_client.query(
            "SELECT * FROM flows() LIMIT 10"
        )

        assert isinstance(result, list)


class TestServerHealth:
    """Tests for server health and connectivity."""

    def test_server_reachable(self, velociraptor_client):
        """Test that the Velociraptor server is reachable."""
        # Use info() VQL as a health check
        result = velociraptor_client.query("SELECT * FROM info()")

        assert result is not None
        assert isinstance(result, list)

    def test_multiple_sequential_queries(self, velociraptor_client):
        """Test running multiple VQL queries sequentially."""
        queries = [
            "SELECT * FROM info()",
            "SELECT * FROM clients() LIMIT 5",
            "SELECT name FROM artifact_definitions() LIMIT 5",
        ]

        results = []
        for q in queries:
            try:
                result = velociraptor_client.query(q)
                results.append(result)
            except Exception as e:
                results.append(e)

        # All queries should complete without error
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Query {i} failed: {result}"
