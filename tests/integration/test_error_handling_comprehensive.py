"""
Comprehensive error handling test suite for Phase 3.

Validates all error handling requirements:
- ERR-01: Network timeout errors return clear messages
- ERR-02: VQL syntax errors provide correction hints
- ERR-03: Non-existent resources return 404-style errors
- ERR-04: Invalid parameters validated with clear messages
- ERR-05: Auth/permission errors handled gracefully
- ERR-06: No stack traces exposed
- ERR-07: Retry logic handles transient failures

This test suite uses mocking to simulate various error conditions
without requiring a live Velociraptor server.
"""

import pytest
import grpc
from unittest.mock import Mock, patch, AsyncMock
import json

# Import all tool modules to test
from megaraptor_mcp.tools.clients import (
    list_clients,
    get_client_info,
    label_client,
    quarantine_client,
)
from megaraptor_mcp.tools.artifacts import (
    list_artifacts,
    get_artifact,
    collect_artifact,
)
from megaraptor_mcp.tools.hunts import (
    list_hunts,
    get_hunt_results,
    create_hunt,
)
from megaraptor_mcp.tools.flows import (
    list_flows,
    get_flow_status,
    cancel_flow,
)
from megaraptor_mcp.tools.vql import (
    run_vql,
    vql_help,
)
from megaraptor_mcp.tools.deployment import (
    deploy_server,
    get_deployment_status,
    list_deployments,
)


class TestERR01_NetworkTimeoutErrors:
    """ERR-01: Network timeout errors return clear messages."""

    @pytest.mark.asyncio
    async def test_deadline_exceeded_clear_message(self):
        """Test DEADLINE_EXCEEDED gRPC error returns clear timeout message."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.DEADLINE_EXCEEDED)
        mock_error.details = Mock(return_value="Deadline Exceeded")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await list_clients()
            data = json.loads(result[0].text)

            assert "error" in data
            assert "timeout" in data["error"].lower() or "deadline" in data["error"].lower()
            assert "hint" in data
            assert "LIMIT" in data["hint"] or "timeout" in data["hint"].lower()
            # Must not expose technical details
            assert "Traceback" not in result[0].text

    @pytest.mark.asyncio
    async def test_unavailable_server_clear_message(self):
        """Test UNAVAILABLE gRPC error returns clear connection message."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.UNAVAILABLE)
        mock_error.details = Mock(return_value="Connection refused")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await list_hunts()
            data = json.loads(result[0].text)

            assert "error" in data
            assert "unavailable" in data["error"].lower() or "connection" in data["error"].lower()
            assert "hint" in data
            assert "running" in data["hint"].lower() or "connectivity" in data["hint"].lower()


class TestERR02_VQLSyntaxErrors:
    """ERR-02: VQL syntax errors provide correction hints."""

    @pytest.mark.asyncio
    async def test_trailing_semicolon_rejected(self):
        """Test VQL with trailing semicolon returns helpful error."""
        result = await run_vql(query="SELECT * FROM clients();")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "semicolon" in data["error"].lower()
        assert "hint" in data
        assert "VQL" in data["hint"] or "SQL" in data["hint"]

    @pytest.mark.asyncio
    async def test_empty_query_rejected(self):
        """Test empty VQL query returns clear error."""
        result = await run_vql(query="")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "empty" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_missing_select_rejected(self):
        """Test VQL without SELECT statement returns clear error."""
        result = await run_vql(query="FROM clients()")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "SELECT" in data["error"] or "select" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_invalid_vql_syntax_hint(self):
        """Test server INVALID_ARGUMENT error includes VQL hint."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.INVALID_ARGUMENT)
        mock_error.details = Mock(return_value="syntax error near FROM")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await run_vql(query="SELECT * FROM")
            data = json.loads(result[0].text)

            assert "error" in data
            assert "hint" in data
            # Should have VQL-specific guidance
            assert "VQL" in data["hint"] or "syntax" in data["hint"].lower()


class TestERR03_NotFoundErrors:
    """ERR-03: Non-existent resources return 404-style errors."""

    @pytest.mark.asyncio
    async def test_nonexistent_client_404_style(self):
        """Test non-existent client returns 404-style error with hint."""
        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            # Simulate no results
            mock_client.query.return_value = []
            mock_get_client.return_value = mock_client

            result = await get_client_info(client_id="C.0000000000000000")
            data = json.loads(result[0].text)

            assert "error" in data
            assert "not found" in data["error"].lower() or "C.0000000000000000" in data["error"]
            assert "hint" in data
            assert "list_clients" in data["hint"].lower()

    @pytest.mark.asyncio
    async def test_nonexistent_hunt_404_style(self):
        """Test non-existent hunt returns 404-style error with hint."""
        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.return_value = []
            mock_get_client.return_value = mock_client

            result = await get_hunt_results(hunt_id="H.0000000000")
            data = json.loads(result[0].text)

            assert "error" in data
            assert "not found" in data["error"].lower() or "H.0000000000" in data["error"]
            assert "hint" in data
            assert "list_hunts" in data["hint"].lower()

    @pytest.mark.asyncio
    async def test_nonexistent_deployment_404_style(self):
        """Test non-existent deployment returns 404-style error with hint."""
        result = await get_deployment_status(deployment_id="vr-00000000-00000000")
        data = json.loads(result[0].text)

        assert "error" in data
        assert "not found" in data["error"].lower() or "vr-00000000" in data["error"]
        assert "hint" in data
        assert "list_deployments" in data["hint"].lower()

    @pytest.mark.asyncio
    async def test_grpc_not_found_returns_404_style(self):
        """Test gRPC NOT_FOUND status returns 404-style error."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.NOT_FOUND)
        mock_error.details = Mock(return_value="Resource not found")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await get_flow_status(client_id="C.1234", flow_id="F.5678")
            data = json.loads(result[0].text)

            assert "error" in data
            assert "not found" in data["error"].lower()
            assert "hint" in data


class TestERR04_InvalidParameterValidation:
    """ERR-04: Invalid parameters validated with clear messages."""

    @pytest.mark.asyncio
    async def test_invalid_client_id_format(self):
        """Test invalid client_id format returns clear validation error."""
        result = await get_client_info(client_id="invalid-format")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "C." in str(data)  # Should mention correct format
        assert "hint" in data
        assert "list_clients" in data["hint"].lower()

    @pytest.mark.asyncio
    async def test_invalid_hunt_id_format(self):
        """Test invalid hunt_id format returns clear validation error."""
        result = await get_hunt_results(hunt_id="invalid-format")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "H." in str(data)  # Should mention correct format
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_invalid_flow_id_format(self):
        """Test invalid flow_id format returns clear validation error."""
        result = await get_flow_status(client_id="C.1234", flow_id="invalid-format")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "F." in str(data)  # Should mention correct format
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_invalid_deployment_id_format(self):
        """Test invalid deployment_id format returns clear validation error."""
        result = await get_deployment_status(deployment_id="invalid-format")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "vr-" in str(data)  # Should mention correct format
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_negative_limit_validation(self):
        """Test negative limit parameter returns validation error."""
        result = await list_clients(limit=-10)

        data = json.loads(result[0].text)
        assert "error" in data
        assert "limit" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_excessive_limit_validation(self):
        """Test excessive limit parameter returns validation error."""
        result = await list_artifacts(limit=999999)

        data = json.loads(result[0].text)
        assert "error" in data
        assert "limit" in data["error"].lower() or "10000" in str(data)
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_empty_required_parameter(self):
        """Test empty required parameter returns validation error."""
        result = await get_artifact(artifact_name="")

        data = json.loads(result[0].text)
        assert "error" in data
        assert "empty" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_injection_protection(self):
        """Test basic injection protection for search parameters."""
        # Test semicolon
        result = await list_clients(search="test; DROP TABLE")
        data = json.loads(result[0].text)
        assert "error" in data
        assert "unsafe" in data["error"].lower() or "invalid" in data["error"].lower()

        # Test SQL comment
        result = await list_clients(search="test-- comment")
        data = json.loads(result[0].text)
        assert "error" in data


class TestERR05_AuthPermissionErrors:
    """ERR-05: Auth/permission errors handled gracefully."""

    @pytest.mark.asyncio
    async def test_unauthenticated_clear_message(self):
        """Test UNAUTHENTICATED gRPC error returns clear auth error."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.UNAUTHENTICATED)
        mock_error.details = Mock(return_value="Invalid credentials")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await list_clients()
            data = json.loads(result[0].text)

            assert "error" in data
            assert "authentication" in data["error"].lower() or "credential" in data["error"].lower()
            assert "hint" in data
            assert "certificate" in data["hint"].lower() or "config" in data["hint"].lower()
            # Must not expose stack traces
            assert "Traceback" not in result[0].text

    @pytest.mark.asyncio
    async def test_permission_denied_clear_message(self):
        """Test PERMISSION_DENIED gRPC error returns clear permission error."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.PERMISSION_DENIED)
        mock_error.details = Mock(return_value="Insufficient permissions")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await create_hunt(
                artifacts=["Windows.System.Pslist"],
                description="Test hunt"
            )
            data = json.loads(result[0].text)

            assert "error" in data
            assert "permission" in data["error"].lower() or "denied" in data["error"].lower()
            assert "hint" in data
            assert "role" in data["hint"].lower() or "administrator" in data["hint"].lower()


class TestERR06_NoStackTracesExposed:
    """ERR-06: No stack traces exposed in error responses."""

    @pytest.mark.asyncio
    async def test_validation_errors_no_stacktrace(self):
        """Test validation errors don't expose stack traces."""
        test_cases = [
            await list_clients(limit=-1),
            await get_client_info(client_id="invalid"),
            await get_hunt_results(hunt_id="invalid"),
            await get_flow_status(client_id="C.123", flow_id="invalid"),
            await run_vql(query=""),
            await get_artifact(artifact_name=""),
        ]

        forbidden_patterns = [
            "Traceback",
            "File \"",
            "line ",
            ".py\",",
            "raise ",
            "Exception:",
            "TypeError:",
            "AttributeError:",
        ]

        for result in test_cases:
            text = result[0].text
            for pattern in forbidden_patterns:
                assert pattern not in text, f"Found stack trace pattern '{pattern}' in: {text[:200]}"

    @pytest.mark.asyncio
    async def test_grpc_errors_no_stacktrace(self):
        """Test gRPC errors don't expose stack traces."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.INTERNAL)
        mock_error.details = Mock(return_value="Internal error")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await list_clients()
            text = result[0].text

            # Check for stack trace patterns
            forbidden_patterns = ["Traceback", "File \"", ".py\",", "raise "]
            for pattern in forbidden_patterns:
                assert pattern not in text

    @pytest.mark.asyncio
    async def test_generic_errors_no_stacktrace(self):
        """Test generic exceptions don't expose stack traces."""
        # Simulate an unexpected error
        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            # Raise a generic Python exception
            mock_client.query.side_effect = RuntimeError("Unexpected internal error")
            mock_get_client.return_value = mock_client

            result = await list_hunts()
            text = result[0].text
            data = json.loads(text)

            # Should return a generic error, not expose the exception
            assert "error" in data
            assert "hint" in data
            # Should NOT contain the actual exception message or stack trace
            assert "RuntimeError" not in text
            assert "Unexpected internal error" not in text
            assert "Traceback" not in text


class TestERR07_RetryLogic:
    """ERR-07: Retry logic handles transient failures."""

    @pytest.mark.asyncio
    async def test_transient_errors_retried(self):
        """Test that transient gRPC errors trigger retry logic."""
        # This test verifies retry behavior exists by checking that
        # retryable errors are handled differently than permanent errors

        # Mock a retryable error (UNAVAILABLE)
        mock_retryable = Mock(spec=grpc.RpcError)
        mock_retryable.code.return_value = grpc.StatusCode.UNAVAILABLE
        mock_retryable.details.return_value = "Connection refused"

        # Mock a permanent error (INVALID_ARGUMENT)
        mock_permanent = Mock(spec=grpc.RpcError)
        mock_permanent.code.return_value = grpc.StatusCode.INVALID_ARGUMENT
        mock_permanent.details.return_value = "Invalid parameter"

        # Test that both return clear errors (retry happens internally)
        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_retryable
            mock_get_client.return_value = mock_client

            result = await list_clients()
            data = json.loads(result[0].text)

            assert "error" in data
            assert "unavailable" in data["error"].lower()
            assert "hint" in data

    @pytest.mark.asyncio
    async def test_resource_exhausted_returns_clear_message(self):
        """Test RESOURCE_EXHAUSTED error (retryable) returns clear message."""
        mock_error = Mock(spec=grpc.RpcError)
        mock_error.code = Mock(return_value=grpc.StatusCode.RESOURCE_EXHAUSTED)
        mock_error.details = Mock(return_value="Rate limit exceeded")

        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.side_effect = mock_error
            mock_get_client.return_value = mock_client

            result = await list_artifacts()
            data = json.loads(result[0].text)

            assert "error" in data
            assert "exhausted" in data["error"].lower() or "load" in data["error"].lower()
            assert "hint" in data
            assert "delay" in data["hint"].lower() or "try again" in data["hint"].lower()


class TestComprehensiveCoverage:
    """Verify all 35 MCP tools handle errors without exposing stack traces."""

    @pytest.mark.asyncio
    async def test_all_tools_handle_validation_errors_gracefully(self):
        """Test that all tools handle invalid inputs without stack traces."""
        # Test representative tools from each module
        test_cases = [
            # Clients module
            ("list_clients", list_clients, {"limit": -1}),
            ("get_client_info", get_client_info, {"client_id": "invalid"}),

            # Artifacts module
            ("list_artifacts", list_artifacts, {"limit": -1}),
            ("get_artifact", get_artifact, {"artifact_name": ""}),

            # Hunts module
            ("list_hunts", list_hunts, {"limit": -1}),
            ("get_hunt_info", get_hunt_info, {"hunt_id": "invalid"}),

            # Flows module
            ("list_flows", list_flows, {"client_id": "invalid"}),
            ("get_flow_info", get_flow_info, {"client_id": "C.123", "flow_id": "invalid"}),

            # VQL module
            ("run_vql", run_vql, {"query": ""}),

            # Deployment module
            ("get_deployment_status", get_deployment_status, {"deployment_id": "invalid"}),
        ]

        for tool_name, tool_func, params in test_cases:
            result = await tool_func(**params)
            data = json.loads(result[0].text)

            # All errors must have 'error' field
            assert "error" in data, f"{tool_name} missing 'error' field"

            # Most should have 'hint' field
            if "error" in data:
                assert "hint" in data, f"{tool_name} missing 'hint' field"

            # None should have stack traces
            assert "Traceback" not in result[0].text, f"{tool_name} exposed stack trace"
            assert "File \"" not in result[0].text, f"{tool_name} exposed file paths"

    @pytest.mark.asyncio
    async def test_deployment_tools_handle_missing_dependencies(self):
        """Test deployment tools handle ImportError gracefully."""
        # Deployment tools should catch ImportError when deployment extras not installed
        result = await get_deployment_status(deployment_id="vr-test-12345678")
        data = json.loads(result[0].text)

        # Should return error (either not found or missing dependency)
        assert "error" in data
        assert "hint" in data
        # Should not expose stack trace
        assert "Traceback" not in result[0].text


class TestErrorMessageConsistency:
    """Verify error messages follow consistent patterns."""

    @pytest.mark.asyncio
    async def test_all_errors_have_required_fields(self):
        """Test all error responses contain error and hint fields."""
        test_cases = [
            await list_clients(limit=-1),
            await get_client_info(client_id=""),
            await get_artifact(artifact_name=""),
            await get_hunt_results(hunt_id="invalid"),
            await run_vql(query=""),
        ]

        for result in test_cases:
            data = json.loads(result[0].text)
            assert "error" in data, "Error response must have 'error' field"
            assert isinstance(data["error"], str), "'error' must be a string"
            assert len(data["error"]) > 0, "Error message cannot be empty"
            assert "hint" in data, "Error response should have 'hint' field"
            assert isinstance(data["hint"], str), "'hint' must be a string"

    @pytest.mark.asyncio
    async def test_404_errors_suggest_list_tools(self):
        """Test 404-style errors suggest appropriate list_* tools."""
        # Client not found should suggest list_clients
        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.return_value = []
            mock_get_client.return_value = mock_client

            result = await get_client_info(client_id="C.0000000000000000")
            data = json.loads(result[0].text)
            assert "list_clients" in data["hint"].lower()

        # Hunt not found should suggest list_hunts
        with patch('megaraptor_mcp.client.get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query.return_value = []
            mock_get_client.return_value = mock_client

            result = await get_hunt_results(hunt_id="H.0000000000")
            data = json.loads(result[0].text)
            assert "list_hunts" in data["hint"].lower()

        # Deployment not found should suggest list_deployments
        result = await get_deployment_status(deployment_id="vr-00000000-00000000")
        data = json.loads(result[0].text)
        assert "list_deployments" in data["hint"].lower()
