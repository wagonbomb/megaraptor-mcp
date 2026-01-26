"""
Integration tests for error handling in clients and artifacts tools.

Tests validate that invalid inputs, missing resources, and gRPC errors
return clear, user-friendly error messages without exposing stack traces.
"""

import pytest
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
import json


class TestClientsErrorHandling:
    """Test error handling for client management tools."""

    @pytest.mark.asyncio
    async def test_list_clients_negative_limit(self):
        """Test list_clients with negative limit returns validation error."""
        result = await list_clients(limit=-1)

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "limit" in data["error"].lower()
        assert "hint" in data
        # Ensure no stack traces
        assert "Traceback" not in result[0].text
        assert "File " not in result[0].text

    @pytest.mark.asyncio
    async def test_list_clients_excessive_limit(self):
        """Test list_clients with excessive limit returns validation error."""
        result = await list_clients(limit=999999)

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "limit" in data["error"].lower() or "10000" in data["error"]
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_list_clients_injection_protection(self):
        """Test list_clients rejects potentially unsafe search queries."""
        # Test semicolon
        result = await list_clients(search="test; DROP TABLE")
        data = json.loads(result[0].text)
        assert "error" in data
        assert "unsafe" in data["error"].lower() or "invalid" in data["error"].lower()

        # Test SQL comment
        result = await list_clients(search="test-- comment")
        data = json.loads(result[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_client_info_invalid_format(self):
        """Test get_client_info with invalid client_id format returns clear error."""
        result = await get_client_info(client_id="invalid-id")

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "C." in str(data)  # Error should mention correct format
        assert "hint" in data
        # Ensure no stack traces
        assert "Traceback" not in result[0].text

    @pytest.mark.asyncio
    async def test_get_client_info_empty_client_id(self):
        """Test get_client_info with empty client_id returns validation error."""
        result = await get_client_info(client_id="")

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "empty" in data["error"].lower() or "cannot be empty" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_get_client_info_nonexistent(self, enrolled_client_id):
        """Test get_client_info with non-existent client returns 404-style error."""
        # Use a valid format but non-existent client ID
        fake_id = "C.0000000000000000"
        result = await get_client_info(client_id=fake_id)

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        # Should return an error (either not found or connection error)
        # The key is that it's a clear error message, not a stack trace
        assert "hint" in data
        assert "Traceback" not in result[0].text

    @pytest.mark.asyncio
    async def test_label_client_invalid_operation(self, enrolled_client_id):
        """Test label_client with invalid operation returns clear error."""
        result = await label_client(
            client_id=enrolled_client_id,
            labels=["test"],
            operation="invalid"
        )

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "operation" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_quarantine_client_invalid_format(self):
        """Test quarantine_client with invalid client_id format."""
        result = await quarantine_client(client_id="invalid")

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "C." in str(data)
        assert "hint" in data


class TestArtifactsErrorHandling:
    """Test error handling for artifact tools."""

    @pytest.mark.asyncio
    async def test_list_artifacts_negative_limit(self):
        """Test list_artifacts with negative limit returns validation error."""
        result = await list_artifacts(limit=-1)

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "limit" in data["error"].lower()
        assert "hint" in data
        # Ensure no stack traces
        assert "Traceback" not in result[0].text

    @pytest.mark.asyncio
    async def test_list_artifacts_invalid_type(self):
        """Test list_artifacts with invalid artifact_type returns clear error."""
        result = await list_artifacts(artifact_type="INVALID")

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "CLIENT" in str(data) or "SERVER" in str(data)  # Should mention valid types
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_get_artifact_empty_name(self):
        """Test get_artifact with empty name returns validation error."""
        result = await get_artifact(artifact_name="")

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "empty" in data["error"].lower() or "cannot be empty" in data["error"].lower()
        assert "hint" in data
        assert "list_artifacts" in data["hint"].lower()

    @pytest.mark.asyncio
    async def test_get_artifact_nonexistent(self):
        """Test get_artifact with non-existent artifact returns 404-style error."""
        result = await get_artifact(artifact_name="Nonexistent.Artifact.Name")

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        # Should return a clear error (either not found or connection error)
        # The key is it's user-friendly, not a stack trace
        assert "hint" in data
        assert "Traceback" not in result[0].text

    @pytest.mark.asyncio
    async def test_collect_artifact_invalid_client_id(self):
        """Test collect_artifact with invalid client_id format returns clear error."""
        result = await collect_artifact(
            client_id="invalid",
            artifacts=["Linux.Sys.Pslist"]
        )

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "C." in str(data)
        assert "hint" in data
        # Ensure no stack traces
        assert "Traceback" not in result[0].text

    @pytest.mark.asyncio
    async def test_collect_artifact_empty_artifacts_list(self, enrolled_client_id):
        """Test collect_artifact with empty artifacts list returns validation error."""
        result = await collect_artifact(
            client_id=enrolled_client_id,
            artifacts=[]
        )

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "empty" in data["error"].lower() or "required" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_collect_artifact_invalid_timeout(self, enrolled_client_id):
        """Test collect_artifact with invalid timeout returns validation error."""
        result = await collect_artifact(
            client_id=enrolled_client_id,
            artifacts=["Linux.Sys.Pslist"],
            timeout=0
        )

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert "error" in data
        assert "timeout" in data["error"].lower()
        assert "hint" in data

    @pytest.mark.asyncio
    async def test_collect_artifact_nonexistent_client(self):
        """Test collect_artifact with non-existent client returns clear error."""
        # Use valid format but non-existent client
        fake_id = "C.0000000000000000"
        result = await collect_artifact(
            client_id=fake_id,
            artifacts=["Linux.Sys.Pslist"]
        )

        assert len(result) == 1
        data = json.loads(result[0].text)

        # Should either fail with validation or gRPC error - both should be clear
        assert "error" in data
        assert "hint" in data
        # Ensure no stack traces
        assert "Traceback" not in result[0].text


class TestErrorMessageFormat:
    """Test that error messages follow consistent format."""

    @pytest.mark.asyncio
    async def test_error_messages_have_required_fields(self):
        """Test that all error responses contain required fields."""
        # Test various error scenarios
        test_cases = [
            await list_clients(limit=-1),
            await get_client_info(client_id=""),
            await get_artifact(artifact_name=""),
            await list_artifacts(limit=999999),
        ]

        for result in test_cases:
            data = json.loads(result[0].text)
            assert "error" in data, "Error response must have 'error' field"
            assert isinstance(data["error"], str), "Error must be a string"
            assert len(data["error"]) > 0, "Error message cannot be empty"

            # Most errors should have hints
            if "error" in data:
                assert "hint" in data, "Error response should have 'hint' field"

    @pytest.mark.asyncio
    async def test_no_stack_traces_in_errors(self):
        """Test that error messages never expose Python stack traces."""
        # Test various error scenarios
        test_cases = [
            await list_clients(limit=-1),
            await get_client_info(client_id="invalid"),
            await collect_artifact(client_id="invalid", artifacts=["test"]),
        ]

        forbidden_patterns = [
            "Traceback",
            "File \"",
            "line ",
            ".py\",",
            "raise ",
            "Exception:",
        ]

        for result in test_cases:
            text = result[0].text
            for pattern in forbidden_patterns:
                assert pattern not in text, f"Error response contains stack trace pattern: {pattern}"
