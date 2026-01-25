"""Parametrized smoke tests for all 35 MCP tools.

Tests that each MCP tool can be invoked without raising exceptions.
Validates basic response structure and graceful error handling.

This validates SMOKE-01 (all tools callable) and SMOKE-05 (JSON Schema validation).
"""

import pytest

from tests.integration.helpers.mcp_helpers import invoke_mcp_tool, replace_placeholders
from tests.integration.schemas import get_tool_schema

# Map of all 35 MCP tools with minimal smoke test inputs
# Each entry: (tool_name, base_arguments, requires_client_id)
TOOL_SMOKE_INPUTS = [
    # Client tools (4)
    ("list_clients", {}, False),
    ("list_clients", {"search": "host:", "limit": 10}, False),
    ("get_client_info", {"client_id": "C.placeholder"}, True),
    ("label_client", {"client_id": "C.placeholder", "labels": ["TEST-smoke"], "operation": "add"}, True),
    ("quarantine_client", {"client_id": "C.placeholder", "quarantine": False}, True),

    # Artifact tools (3)
    ("list_artifacts", {}, False),
    ("list_artifacts", {"artifact_type": "CLIENT", "limit": 10}, False),
    ("get_artifact", {"artifact_name": "Windows.System.Pslist"}, False),
    ("collect_artifact", {"client_id": "C.placeholder", "artifacts": ["Generic.Client.Info"]}, True),

    # Hunt tools (4)
    ("list_hunts", {}, False),
    ("list_hunts", {"state": "PAUSED", "limit": 10}, False),
    ("create_hunt", {
        "artifacts": ["Generic.Client.Info"],
        "description": "TEST-smoke-hunt",
        "paused": True
    }, False),
    ("get_hunt_results", {"hunt_id": "H.0", "limit": 1}, False),
    ("modify_hunt", {"hunt_id": "H.0", "action": "pause"}, False),

    # Flow tools (4)
    ("list_flows", {"client_id": "C.placeholder", "limit": 10}, True),
    ("get_flow_status", {"client_id": "C.placeholder", "flow_id": "F.0"}, True),
    ("get_flow_results", {"client_id": "C.placeholder", "flow_id": "F.0", "limit": 1}, True),
    ("cancel_flow", {"client_id": "C.placeholder", "flow_id": "F.0"}, True),

    # VQL tools (2)
    ("run_vql", {"query": "SELECT 1 AS test"}, False),
    ("vql_help", {}, False),
    ("vql_help", {"topic": "syntax"}, False),

    # Deployment tools (18)
    # Server deployment (6)
    ("deploy_server", {
        "deployment_type": "docker",
        "profile": "rapid",
        "server_hostname": "smoke-test.local"
    }, False),
    ("deploy_server_docker", {"profile": "rapid"}, False),
    ("deploy_server_cloud", {"cloud_provider": "aws", "profile": "standard"}, False),
    ("get_deployment_status", {"deployment_id": "vr-test-nonexistent"}, False),
    ("destroy_deployment", {"deployment_id": "vr-test-nonexistent", "confirm": False}, False),
    ("list_deployments", {}, False),

    # Agent deployment (7)
    ("generate_agent_installer", {
        "deployment_id": "vr-test-nonexistent",
        "os_type": "windows"
    }, False),
    ("create_offline_collector", {
        "artifacts": ["Windows.System.Pslist"],
        "target_os": "windows"
    }, False),
    ("generate_gpo_package", {
        "deployment_id": "vr-test-nonexistent",
        "domain_controller": "DC01"
    }, False),
    ("generate_ansible_playbook", {
        "deployment_id": "vr-test-nonexistent",
        "include_windows": True
    }, False),
    ("deploy_agents_winrm", {
        "deployment_id": "vr-test-nonexistent",
        "targets": ["smoke-test.local"],
        "username": "admin",
        "password": "test"
    }, False),
    ("deploy_agents_ssh", {
        "deployment_id": "vr-test-nonexistent",
        "targets": ["smoke-test.local"],
        "username": "admin",
        "password": "test"
    }, False),
    ("check_agent_deployment", {"deployment_id": "vr-test-nonexistent"}, False),

    # Configuration & Security (5)
    ("generate_server_config", {"deployment_id": "vr-test-nonexistent"}, False),
    ("generate_api_credentials", {"deployment_id": "vr-test-nonexistent"}, False),
    ("rotate_certificates", {"deployment_id": "vr-test-nonexistent", "rotate_ca": False}, False),
    ("validate_deployment", {"deployment_id": "vr-test-nonexistent"}, False),
    ("export_deployment_docs", {"deployment_id": "vr-test-nonexistent"}, False),
]


@pytest.mark.smoke
@pytest.mark.integration
@pytest.mark.parametrize("tool_name,arguments,requires_client", TOOL_SMOKE_INPUTS, ids=lambda x: x if isinstance(x, str) else "")
async def test_mcp_tool_smoke(tool_name, arguments, requires_client, enrolled_client_id):
    """Smoke test: verify MCP tool can be invoked and returns valid response.

    Tests:
    - Tool invocation does not raise exceptions
    - Response is valid JSON or error object
    - If error, it's graceful (has error field, not exception)
    - If success, response matches expected schema (if schema defined)
    """
    # Replace placeholder client IDs with real enrolled client
    if requires_client:
        arguments = replace_placeholders(arguments, enrolled_client_id)

    # Invoke the tool
    success, response = await invoke_mcp_tool(tool_name, arguments)

    # Tool should not raise exceptions - either success or graceful error
    assert success is not None, f"{tool_name} returned None success indicator"
    assert response is not None, f"{tool_name} returned None response"

    # If tool failed, verify it's a graceful error (not an exception)
    if not success:
        # Deployment tools often error on missing infrastructure - that's expected
        if "deployment" in tool_name or "deploy" in tool_name:
            # Graceful error expected for deployment tools in test environment
            assert isinstance(response, str), f"{tool_name} error should be string"
            return

        # Hunt/flow tools may fail on non-existent IDs - verify graceful handling
        if tool_name in ["get_hunt_results", "modify_hunt", "cancel_flow", "get_flow_status", "get_flow_results"]:
            assert isinstance(response, str), f"{tool_name} should handle missing IDs gracefully"
            return

        # Other tools should succeed in smoke test
        pytest.fail(f"{tool_name} failed: {response}")

    # Tool succeeded - validate response structure if schema exists
    schema = get_tool_schema(tool_name)
    if schema:
        import jsonschema

        # Response should be valid JSON matching schema
        try:
            jsonschema.validate(response, schema)
        except jsonschema.ValidationError as e:
            pytest.fail(f"{tool_name} response validation failed: {e.message}\nResponse: {response}")


@pytest.mark.smoke
@pytest.mark.integration
async def test_tool_count_completeness():
    """Meta-test: verify we're testing all 35 MCP tools."""
    # Extract unique tool names from TOOL_SMOKE_INPUTS
    tested_tools = set(entry[0] for entry in TOOL_SMOKE_INPUTS)

    # We should have test coverage for all 35 tools
    # (Some tools tested multiple times with different params, but 35 unique tools)
    expected_tools = {
        # Client (4)
        "list_clients", "get_client_info", "label_client", "quarantine_client",
        # Artifacts (3)
        "list_artifacts", "get_artifact", "collect_artifact",
        # Hunts (4)
        "create_hunt", "list_hunts", "get_hunt_results", "modify_hunt",
        # Flows (4)
        "list_flows", "get_flow_results", "get_flow_status", "cancel_flow",
        # VQL (2)
        "run_vql", "vql_help",
        # Deployment - Server (6)
        "deploy_server", "deploy_server_docker", "deploy_server_cloud",
        "get_deployment_status", "destroy_deployment", "list_deployments",
        # Deployment - Agent (7)
        "generate_agent_installer", "create_offline_collector", "generate_gpo_package",
        "generate_ansible_playbook", "deploy_agents_winrm", "deploy_agents_ssh",
        "check_agent_deployment",
        # Deployment - Config/Security (5)
        "generate_server_config", "generate_api_credentials", "rotate_certificates",
        "validate_deployment", "export_deployment_docs",
    }

    assert tested_tools == expected_tools, \
        f"Tool coverage mismatch.\nMissing: {expected_tools - tested_tools}\nExtra: {tested_tools - expected_tools}"

    assert len(expected_tools) == 35, f"Expected 35 tools, got {len(expected_tools)}"
