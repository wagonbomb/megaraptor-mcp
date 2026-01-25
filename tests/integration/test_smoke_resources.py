"""Resource URI smoke tests.

Validates SMOKE-07: Resource URIs return valid JSON data.

These tests verify MCP resource endpoints return properly formatted JSON
for browsing Velociraptor data.
"""

import json
import pytest
from pytest_check import check


# Resource handlers to test - covering all MCP resource endpoints
RESOURCE_URIS = [
    # Handler function, needs_client, path_parts, expected_type
    ("clients_list", "_handle_clients_resource", True, [], "client_list"),
    ("hunts_list", "_handle_hunts_resource", True, [], "hunt_list"),
    ("artifacts_list", "_handle_artifacts_resource", True, [], "artifact_list"),
    ("server_info", "_handle_server_info_resource", True, None, "server_info"),
    ("deployments_list", "_handle_deployments_resource", False, [], "deployment_list"),
]


@pytest.mark.smoke
@pytest.mark.integration
class TestResourceURIs:
    """Test MCP resource URI smoke tests."""

    @pytest.mark.parametrize("resource_name,handler_name,needs_client,path_parts,expected_type", RESOURCE_URIS)
    async def test_resource_handler_returns_json(self, velociraptor_client, resource_name, handler_name, needs_client, path_parts, expected_type):
        """Smoke test: Resource handlers return valid JSON.

        Validates SMOKE-07: All resource handlers should:
        1. Return valid JSON (parseable)
        2. Include a 'type' field matching the expected type
        3. Not raise exceptions
        """
        from megaraptor_mcp.resources import resources

        handler = getattr(resources, handler_name)

        try:
            if not needs_client:
                # Deployments handler doesn't take client
                result = await handler(path_parts)
            elif path_parts is None:
                # server_info doesn't take path_parts
                result = await handler(velociraptor_client)
            else:
                result = await handler(velociraptor_client, path_parts)
        except Exception as e:
            pytest.fail(f"Resource handler '{resource_name}' failed: {e}")

        # Validate JSON structure
        with check:
            assert result is not None, f"Resource '{resource_name}' returned None"

        # Parse JSON
        try:
            data = json.loads(result)
        except json.JSONDecodeError as e:
            pytest.fail(f"Resource '{resource_name}' returned invalid JSON: {e}")

        # Validate type field
        with check:
            assert "type" in data, f"Resource '{resource_name}' missing 'type' field"
        with check:
            assert data["type"] == expected_type, \
                f"Resource '{resource_name}' expected type '{expected_type}', got '{data.get('type')}'"

    async def test_clients_resource_structure(self, velociraptor_client):
        """Smoke test: Clients resource has expected structure."""
        from megaraptor_mcp.resources.resources import _handle_clients_resource

        result = await _handle_clients_resource(velociraptor_client, [])
        data = json.loads(result)

        with check:
            assert "count" in data, "Clients resource missing 'count' field"
        with check:
            assert "clients" in data, "Clients resource missing 'clients' field"
        with check:
            assert isinstance(data["clients"], list), \
                f"Clients field should be list, got {type(data['clients'])}"

    async def test_hunts_resource_structure(self, velociraptor_client):
        """Smoke test: Hunts resource has expected structure."""
        from megaraptor_mcp.resources.resources import _handle_hunts_resource

        result = await _handle_hunts_resource(velociraptor_client, [])
        data = json.loads(result)

        with check:
            assert "count" in data, "Hunts resource missing 'count' field"
        with check:
            assert "hunts" in data, "Hunts resource missing 'hunts' field"
        with check:
            assert isinstance(data["hunts"], list), \
                f"Hunts field should be list, got {type(data['hunts'])}"

    async def test_artifacts_resource_structure(self, velociraptor_client):
        """Smoke test: Artifacts resource has expected structure."""
        from megaraptor_mcp.resources.resources import _handle_artifacts_resource

        result = await _handle_artifacts_resource(velociraptor_client, [])
        data = json.loads(result)

        with check:
            assert "total_count" in data, "Artifacts resource missing 'total_count' field"
        with check:
            assert "categories" in data, "Artifacts resource missing 'categories' field"
        with check:
            assert isinstance(data["categories"], dict), \
                f"Categories field should be dict, got {type(data['categories'])}"

    async def test_server_info_resource_structure(self, velociraptor_client):
        """Smoke test: Server info resource has expected structure."""
        from megaraptor_mcp.resources.resources import _handle_server_info_resource

        result = await _handle_server_info_resource(velociraptor_client)
        data = json.loads(result)

        with check:
            assert "info" in data, "Server info resource missing 'info' field"
        with check:
            assert "version" in data, "Server info resource missing 'version' field"
        with check:
            assert isinstance(data["info"], dict), \
                f"Info field should be dict, got {type(data['info'])}"

    async def test_deployments_resource_structure(self):
        """Smoke test: Deployments resource has expected structure."""
        from megaraptor_mcp.resources.resources import _handle_deployments_resource

        result = await _handle_deployments_resource([])
        data = json.loads(result)

        with check:
            assert "count" in data, "Deployments resource missing 'count' field"
        with check:
            assert "deployments" in data, "Deployments resource missing 'deployments' field"
        with check:
            assert isinstance(data["deployments"], list), \
                f"Deployments field should be list, got {type(data['deployments'])}"

    async def test_specific_client_resource(self, velociraptor_client, enrolled_client_id):
        """Smoke test: Specific client resource works with valid client ID."""
        from megaraptor_mcp.resources.resources import _handle_clients_resource

        result = await _handle_clients_resource(velociraptor_client, [enrolled_client_id])
        data = json.loads(result)

        with check:
            assert "type" in data, "Client detail missing 'type' field"
        with check:
            assert data["type"] == "client_detail", \
                f"Expected type 'client_detail', got '{data.get('type')}'"
        with check:
            assert "client" in data, "Client detail missing 'client' field"

    async def test_nonexistent_client_resource(self, velociraptor_client):
        """Smoke test: Nonexistent client returns error JSON, not exception."""
        from megaraptor_mcp.resources.resources import _handle_clients_resource

        result = await _handle_clients_resource(velociraptor_client, ["C.0000000000000000"])
        data = json.loads(result)

        # Should contain error field for nonexistent client
        with check:
            assert "error" in data, "Expected error field for nonexistent client"

    async def test_resource_json_is_pretty_printed(self, velociraptor_client):
        """Smoke test: Resource JSON includes indentation for readability."""
        from megaraptor_mcp.resources.resources import _handle_server_info_resource

        result = await _handle_server_info_resource(velociraptor_client)

        # Pretty-printed JSON should have newlines and indentation
        with check:
            assert "\n" in result, "JSON should be pretty-printed with newlines"
        with check:
            assert "  " in result, "JSON should be indented"
