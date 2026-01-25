"""Server connectivity smoke tests.

Validates SMOKE-06: Server connectivity and authentication verified before test runs.

These tests verify basic infrastructure before running other smoke tests.
"""

import pytest
from pytest_check import check


@pytest.mark.smoke
@pytest.mark.integration
class TestServerConnectivity:
    """Test server connectivity and basic operations."""

    def test_server_connection(self, velociraptor_client):
        """Smoke test: Verify server is accessible and responds to VQL.

        This is the foundational smoke test - if this fails, all other
        smoke tests will fail.
        """
        # Execute simplest VQL query
        vql = "SELECT * FROM info()"

        try:
            result = velociraptor_client.query(vql)
        except Exception as e:
            pytest.fail(f"Server connection failed: {e}")

        # Validate result structure
        with check:
            assert result is not None, "info() returned None"
        with check:
            assert isinstance(result, list), f"Expected list, got {type(result)}"
        with check:
            assert len(result) > 0, "info() returned empty result"

        # Validate server info fields
        if result:
            info = result[0]
            with check:
                # info() returns fields like Architecture, BootTime, etc.
                # Just verify we got a dict with some fields
                assert isinstance(info, dict), f"Expected dict, got {type(info)}"
            with check:
                assert len(info) > 0, "Server info returned empty dict"

    def test_client_enrolled(self, velociraptor_client, enrolled_client_id):
        """Smoke test: Verify at least one client is enrolled.

        Tests require enrolled clients for artifact collection and flow testing.
        """
        with check:
            assert enrolled_client_id is not None, "No enrolled client ID"
        with check:
            assert enrolled_client_id.startswith("C."), \
                f"Invalid client ID format: {enrolled_client_id}"

        # Verify client exists in server
        vql = f"SELECT client_id FROM clients(client_id='{enrolled_client_id}')"
        result = velociraptor_client.query(vql)

        with check:
            assert len(result) > 0, f"Client {enrolled_client_id} not found on server"

    def test_vql_execution(self, velociraptor_client):
        """Smoke test: Verify VQL execution works with various query types."""
        test_queries = [
            ("info", "SELECT * FROM info()"),
            ("clients_list", "SELECT client_id FROM clients() LIMIT 5"),
            ("artifacts", "SELECT name FROM artifact_definitions() LIMIT 5"),
        ]

        for query_name, vql in test_queries:
            try:
                result = velociraptor_client.query(vql)
                with check:
                    assert result is not None, f"Query '{query_name}' returned None"
                with check:
                    assert isinstance(result, list), \
                        f"Query '{query_name}' returned {type(result)}, expected list"
            except Exception as e:
                pytest.fail(f"Query '{query_name}' failed: {e}")
