"""VQL query execution smoke tests.

Validates SMOKE-04: VQL queries execute without syntax errors and return list results.

These tests verify basic VQL functionality across common query patterns.
"""

import pytest
from pytest_check import check


# VQL queries to test - covering common query patterns
SMOKE_VQL_QUERIES = [
    # Basic system info queries
    ("info", "SELECT * FROM info()"),
    ("server_version", "SELECT server_version() AS version FROM scope()"),

    # Client queries
    ("clients_list", "SELECT client_id, os_info FROM clients() LIMIT 5"),
    ("clients_count", "SELECT count() AS total FROM clients()"),

    # Artifact queries
    ("artifacts_list", "SELECT name, type FROM artifact_definitions() LIMIT 10"),
    ("artifacts_filter", "SELECT name FROM artifact_definitions() WHERE type = 'CLIENT' LIMIT 5"),

    # Hunt queries
    ("hunts_list", "SELECT hunt_id, state FROM hunts() LIMIT 5"),
    ("hunts_with_stats", "SELECT hunt_id, stats FROM hunts() LIMIT 3"),

    # Flow queries (may return empty if no flows)
    ("flows_list", "SELECT flow_id FROM flows() LIMIT 5"),

    # Scope queries
    ("scope_query", "SELECT * FROM scope()"),

    # VQL with WHERE clause
    ("filtered_clients", "SELECT client_id FROM clients() WHERE last_seen_at > now() - 86400 LIMIT 5"),

    # VQL with aggregation
    ("artifact_types", "SELECT type, count() AS count FROM artifact_definitions() GROUP BY type"),
]


@pytest.mark.smoke
@pytest.mark.integration
class TestVQLExecution:
    """Test VQL query execution smoke tests."""

    @pytest.mark.parametrize("query_name,vql", SMOKE_VQL_QUERIES)
    def test_vql_query_executes(self, velociraptor_client, query_name, vql):
        """Smoke test: VQL queries execute without syntax errors.

        Validates SMOKE-04: All VQL queries should:
        1. Execute without raising exceptions
        2. Return a list (even if empty)
        3. Not return None
        """
        try:
            result = velociraptor_client.query(vql)
        except Exception as e:
            pytest.fail(f"VQL query '{query_name}' failed to execute: {e}")

        # Validate result type
        with check:
            assert result is not None, f"Query '{query_name}' returned None"
        with check:
            assert isinstance(result, list), \
                f"Query '{query_name}' returned {type(result)}, expected list"

    def test_vql_with_client_id(self, velociraptor_client, enrolled_client_id):
        """Smoke test: VQL queries with client_id parameter work."""
        vql = f"SELECT client_id, os_info FROM clients(client_id='{enrolled_client_id}')"

        try:
            result = velociraptor_client.query(vql)
        except Exception as e:
            pytest.fail(f"Client-specific VQL query failed: {e}")

        with check:
            assert result is not None, "Client query returned None"
        with check:
            assert isinstance(result, list), f"Expected list, got {type(result)}"
        with check:
            # Should return at least the requested client
            assert len(result) > 0, f"Client {enrolled_client_id} not found"

    def test_vql_syntax_error_handling(self, velociraptor_client):
        """Smoke test: VQL syntax errors return empty result gracefully."""
        # Invalid VQL query (missing FROM)
        invalid_vql = "SELECT * WHERE client_id = 'C.1234'"

        # Velociraptor returns empty list for syntax errors, not exceptions
        try:
            result = velociraptor_client.query(invalid_vql)
            # If it doesn't raise, it should at least return a list
            with check:
                assert isinstance(result, list), f"Invalid VQL returned {type(result)}"
        except Exception:
            # Some syntax errors may raise exceptions - that's also acceptable
            pass

    def test_vql_returns_expected_fields(self, velociraptor_client):
        """Smoke test: VQL results contain expected field structure."""
        vql = "SELECT client_id FROM clients() LIMIT 1"
        result = velociraptor_client.query(vql)

        # Skip if no clients enrolled
        if len(result) == 0:
            pytest.skip("No clients enrolled")

        with check:
            assert isinstance(result[0], dict), f"Expected dict row, got {type(result[0])}"
        with check:
            assert "client_id" in result[0], "Missing expected field 'client_id'"

    def test_vql_limit_clause(self, velociraptor_client):
        """Smoke test: VQL LIMIT clause is respected."""
        vql = "SELECT name FROM artifact_definitions() LIMIT 3"
        result = velociraptor_client.query(vql)

        with check:
            assert len(result) <= 3, f"LIMIT 3 returned {len(result)} results"

    def test_vql_empty_result_is_list(self, velociraptor_client):
        """Smoke test: VQL queries with no matches return empty list, not None."""
        # Query for non-existent client
        vql = "SELECT * FROM clients(client_id='C.0000000000000000')"
        result = velociraptor_client.query(vql)

        with check:
            assert result is not None, "Empty result returned None instead of empty list"
        with check:
            assert isinstance(result, list), f"Empty result is {type(result)}, expected list"
        with check:
            assert len(result) == 0, f"Expected empty list, got {len(result)} items"
