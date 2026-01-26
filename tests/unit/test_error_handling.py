"""
Unit tests for error handling utilities.

Tests validators, gRPC error handlers, and VQL error hint extraction.
"""

import pytest
from unittest.mock import Mock
import grpc

from megaraptor_mcp.error_handling import (
    validate_client_id,
    validate_limit,
    validate_hunt_id,
    validate_flow_id,
    validate_vql_syntax_basics,
    is_retryable_grpc_error,
    map_grpc_error,
    extract_vql_error_hint,
)


# ==================== Validator Tests ====================


@pytest.mark.unit
def test_validate_client_id_valid():
    """Valid client ID passes validation."""
    result = validate_client_id("C.1234567890abcdef")
    assert result == "C.1234567890abcdef"


@pytest.mark.unit
def test_validate_client_id_empty():
    """Empty client ID raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_client_id("")
    assert "cannot be empty" in str(exc_info.value)
    assert "list_clients" in str(exc_info.value)


@pytest.mark.unit
def test_validate_client_id_invalid_format():
    """Client ID without 'C.' prefix raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_client_id("invalid-id")
    assert "Must start with 'C.'" in str(exc_info.value)
    assert "invalid-id" in str(exc_info.value)


@pytest.mark.unit
def test_validate_limit_valid():
    """Valid limit passes validation."""
    result = validate_limit(100)
    assert result == 100


@pytest.mark.unit
def test_validate_limit_negative():
    """Negative limit raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_limit(-1)
    assert "at least" in str(exc_info.value).lower()


@pytest.mark.unit
def test_validate_limit_too_large():
    """Limit exceeding max raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_limit(100001)
    assert "cannot exceed" in str(exc_info.value).lower()


@pytest.mark.unit
def test_validate_limit_custom_range():
    """Custom min/max range is enforced."""
    result = validate_limit(50, min_val=10, max_val=100)
    assert result == 50

    with pytest.raises(ValueError):
        validate_limit(5, min_val=10, max_val=100)

    with pytest.raises(ValueError):
        validate_limit(101, min_val=10, max_val=100)


@pytest.mark.unit
def test_validate_hunt_id_valid():
    """Valid hunt ID passes validation."""
    result = validate_hunt_id("H.1234567890")
    assert result == "H.1234567890"


@pytest.mark.unit
def test_validate_hunt_id_empty():
    """Empty hunt ID raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_hunt_id("")
    assert "cannot be empty" in str(exc_info.value)
    assert "list_hunts" in str(exc_info.value)


@pytest.mark.unit
def test_validate_hunt_id_invalid_format():
    """Hunt ID without 'H.' prefix raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_hunt_id("invalid")
    assert "Must start with 'H.'" in str(exc_info.value)


@pytest.mark.unit
def test_validate_flow_id_valid():
    """Valid flow ID passes validation."""
    result = validate_flow_id("F.1234567890")
    assert result == "F.1234567890"


@pytest.mark.unit
def test_validate_flow_id_empty():
    """Empty flow ID raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_flow_id("")
    assert "cannot be empty" in str(exc_info.value)
    assert "list_flows" in str(exc_info.value)


@pytest.mark.unit
def test_validate_flow_id_invalid_format():
    """Flow ID without 'F.' prefix raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_flow_id("invalid")
    assert "Must start with 'F.'" in str(exc_info.value)


@pytest.mark.unit
def test_validate_vql_syntax_empty():
    """Empty VQL query raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_vql_syntax_basics("")
    assert "cannot be empty" in str(exc_info.value)
    assert "vql_help" in str(exc_info.value)


@pytest.mark.unit
def test_validate_vql_syntax_whitespace_only():
    """Whitespace-only VQL query raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_vql_syntax_basics("   \n\t  ")
    assert "cannot be empty" in str(exc_info.value)


@pytest.mark.unit
def test_validate_vql_syntax_semicolon():
    """VQL query ending with semicolon raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_vql_syntax_basics("SELECT * FROM info();")
    assert "semicolon" in str(exc_info.value).lower()
    assert "VQL" in str(exc_info.value)


@pytest.mark.unit
def test_validate_vql_syntax_no_select():
    """VQL query without SELECT raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_vql_syntax_basics("FROM info()")
    assert "SELECT" in str(exc_info.value)
    assert "vql_help" in str(exc_info.value)


@pytest.mark.unit
def test_validate_vql_syntax_valid():
    """Valid VQL query passes validation."""
    result = validate_vql_syntax_basics("SELECT * FROM info()")
    assert result == "SELECT * FROM info()"


# ==================== gRPC Handler Tests ====================


def create_mock_grpc_error(status_code: grpc.StatusCode, details: str = "") -> Mock:
    """Create a mock gRPC error with specified status code."""
    mock_error = Mock(spec=grpc.RpcError)
    # Configure the mock to have code() and details() methods
    mock_error.code = Mock(return_value=status_code)
    mock_error.details = Mock(return_value=details)
    return mock_error


@pytest.mark.unit
def test_is_retryable_unavailable():
    """UNAVAILABLE status code is retryable."""
    error = create_mock_grpc_error(grpc.StatusCode.UNAVAILABLE)
    assert is_retryable_grpc_error(error) is True


@pytest.mark.unit
def test_is_retryable_deadline_exceeded():
    """DEADLINE_EXCEEDED status code is retryable."""
    error = create_mock_grpc_error(grpc.StatusCode.DEADLINE_EXCEEDED)
    assert is_retryable_grpc_error(error) is True


@pytest.mark.unit
def test_is_retryable_resource_exhausted():
    """RESOURCE_EXHAUSTED status code is retryable."""
    error = create_mock_grpc_error(grpc.StatusCode.RESOURCE_EXHAUSTED)
    assert is_retryable_grpc_error(error) is True


@pytest.mark.unit
def test_is_retryable_not_found():
    """NOT_FOUND status code is not retryable."""
    error = create_mock_grpc_error(grpc.StatusCode.NOT_FOUND)
    assert is_retryable_grpc_error(error) is False


@pytest.mark.unit
def test_is_retryable_invalid_argument():
    """INVALID_ARGUMENT status code is not retryable."""
    error = create_mock_grpc_error(grpc.StatusCode.INVALID_ARGUMENT)
    assert is_retryable_grpc_error(error) is False


@pytest.mark.unit
def test_is_retryable_unauthenticated():
    """UNAUTHENTICATED status code is not retryable."""
    error = create_mock_grpc_error(grpc.StatusCode.UNAUTHENTICATED)
    assert is_retryable_grpc_error(error) is False


@pytest.mark.unit
def test_is_retryable_non_grpc_error():
    """Non-gRPC errors are not retryable."""
    assert is_retryable_grpc_error(ValueError("test")) is False
    assert is_retryable_grpc_error(None) is False


@pytest.mark.unit
def test_map_grpc_error_unavailable():
    """UNAVAILABLE error maps to user-friendly message."""
    error = create_mock_grpc_error(grpc.StatusCode.UNAVAILABLE)
    result = map_grpc_error(error, "query execution")

    assert "unavailable" in result["error"].lower()
    assert "query execution" in result["error"]
    assert "server is running" in result["hint"].lower()
    assert result["grpc_status"] == "UNAVAILABLE"


@pytest.mark.unit
def test_map_grpc_error_timeout():
    """DEADLINE_EXCEEDED error maps to timeout message."""
    error = create_mock_grpc_error(grpc.StatusCode.DEADLINE_EXCEEDED)
    result = map_grpc_error(error, "data retrieval")

    assert "timeout" in result["error"].lower()
    assert "data retrieval" in result["error"]
    assert "LIMIT" in result["hint"]
    assert "timeout parameter" in result["hint"].lower()
    assert result["grpc_status"] == "DEADLINE_EXCEEDED"


@pytest.mark.unit
def test_map_grpc_error_not_found():
    """NOT_FOUND error maps to not found message."""
    error = create_mock_grpc_error(grpc.StatusCode.NOT_FOUND)
    result = map_grpc_error(error, "client lookup")

    assert "not found" in result["error"].lower()
    assert "client lookup" in result["error"]
    assert "Verify the ID" in result["hint"]
    assert result["grpc_status"] == "NOT_FOUND"


@pytest.mark.unit
def test_map_grpc_error_invalid_argument():
    """INVALID_ARGUMENT error includes details."""
    error = create_mock_grpc_error(
        grpc.StatusCode.INVALID_ARGUMENT,
        "Invalid VQL syntax"
    )
    result = map_grpc_error(error, "query")

    assert "invalid argument" in result["error"].lower()
    assert "Invalid VQL syntax" in result["error"]
    assert "parameter formats" in result["hint"].lower()
    assert result["grpc_status"] == "INVALID_ARGUMENT"


@pytest.mark.unit
def test_map_grpc_error_auth():
    """UNAUTHENTICATED error maps to auth error without stack trace."""
    error = create_mock_grpc_error(grpc.StatusCode.UNAUTHENTICATED)
    result = map_grpc_error(error, "connection")

    assert "authentication failed" in result["error"].lower()
    assert "connection" in result["error"]
    assert "certificate" in result["hint"].lower()
    assert "VELOCIRAPTOR_CONFIG" in result["hint"]
    assert result["grpc_status"] == "UNAUTHENTICATED"


@pytest.mark.unit
def test_map_grpc_error_permission_denied():
    """PERMISSION_DENIED error maps to permission message."""
    error = create_mock_grpc_error(grpc.StatusCode.PERMISSION_DENIED)
    result = map_grpc_error(error, "hunt creation")

    assert "permission denied" in result["error"].lower()
    assert "hunt creation" in result["error"]
    assert "permissions" in result["hint"].lower()
    assert result["grpc_status"] == "PERMISSION_DENIED"


@pytest.mark.unit
def test_map_grpc_error_internal():
    """INTERNAL error maps to internal server error."""
    error = create_mock_grpc_error(grpc.StatusCode.INTERNAL, "Database error")
    result = map_grpc_error(error, "data storage")

    assert "internal server error" in result["error"].lower()
    assert "Database error" in result["error"]
    assert "server logs" in result["hint"].lower()
    assert result["grpc_status"] == "INTERNAL"


@pytest.mark.unit
def test_map_grpc_error_unknown_code():
    """Unknown gRPC status code uses fallback."""
    error = create_mock_grpc_error(grpc.StatusCode.CANCELLED, "User cancelled")
    result = map_grpc_error(error, "operation")

    assert "grpc error" in result["error"].lower()
    assert "operation" in result["error"]
    assert "User cancelled" in result["error"]
    assert result["grpc_status"] == "CANCELLED"


@pytest.mark.unit
def test_map_grpc_error_exception_handling():
    """Handles exceptions when getting status code."""
    mock_error = Mock(spec=grpc.RpcError)
    # Configure code() to raise an exception
    mock_error.code = Mock(side_effect=Exception("No code available"))

    result = map_grpc_error(mock_error, "test operation")

    assert "unknown error" in result["error"].lower()
    assert "test operation" in result["error"]
    assert result["grpc_status"] == "UNKNOWN"


# ==================== VQL Helper Tests ====================


@pytest.mark.unit
def test_vql_hint_symbol_not_found():
    """Symbol not found error provides plugin hint."""
    error_msg = "symbol 'pslist' not found"
    hint = extract_vql_error_hint(error_msg)

    assert "pslist" in hint
    assert "plugin" in hint.lower() or "function" in hint.lower()
    assert "vql_help" in hint.lower()


@pytest.mark.unit
def test_vql_hint_symbol_not_found_case_insensitive():
    """Symbol not found detection is case insensitive."""
    error_msg = "Symbol 'Windows.System.Users' NOT FOUND"
    hint = extract_vql_error_hint(error_msg)

    assert "Windows.System.Users" in hint
    assert "plugin" in hint.lower() or "function" in hint.lower()


@pytest.mark.unit
def test_vql_hint_syntax_error():
    """Syntax error provides VQL-specific hints."""
    error_msg = "syntax error at line 1"
    hint = extract_vql_error_hint(error_msg)

    assert "syntax error" in hint.lower()
    assert "semicolon" in hint.lower()
    assert "vql_help" in hint.lower()


@pytest.mark.unit
def test_vql_hint_parentheses():
    """Parentheses error provides balance hint."""
    error_msg = "expected ) at position 42"
    hint = extract_vql_error_hint(error_msg)

    assert "parentheses" in hint.lower()
    assert "(" in hint
    assert ")" in hint


@pytest.mark.unit
def test_vql_hint_let_in_select():
    """LET in SELECT error provides statement separation hint."""
    error_msg = "LET cannot appear in SELECT statement"
    hint = extract_vql_error_hint(error_msg)

    assert "LET" in hint
    assert "SELECT" in hint
    assert "separate" in hint.lower()


@pytest.mark.unit
def test_vql_hint_let_select_keyword_detection():
    """Detects LET and SELECT together in error."""
    error_msg = "Unexpected LET keyword after SELECT"
    hint = extract_vql_error_hint(error_msg)

    assert "LET" in hint
    assert "SELECT" in hint


@pytest.mark.unit
def test_vql_hint_type_mismatch():
    """Type error provides type conversion hint."""
    error_msg = "type mismatch: cannot convert string to int"
    hint = extract_vql_error_hint(error_msg)

    assert "type" in hint.lower()
    assert "int()" in hint or "str()" in hint


@pytest.mark.unit
def test_vql_hint_plugin_not_available():
    """Plugin not available error provides OS/config hints."""
    error_msg = "plugin 'windows.registry' not available"
    hint = extract_vql_error_hint(error_msg)

    assert "plugin" in hint.lower()
    assert "not available" in hint.lower()
    assert "disabled" in hint.lower() or "OS" in hint


@pytest.mark.unit
def test_vql_hint_column_not_found():
    """Column not found error suggests field inspection."""
    error_msg = "column 'ProcessName' not found in result"
    hint = extract_vql_error_hint(error_msg)

    assert "column" in hint.lower() or "field" in hint.lower()
    assert "SELECT *" in hint


@pytest.mark.unit
def test_vql_hint_default_fallback():
    """Unknown error provides general troubleshooting."""
    error_msg = "Some unknown VQL error occurred"
    hint = extract_vql_error_hint(error_msg)

    assert "vql_help" in hint.lower()
    assert "syntax" in hint.lower()
    assert "Some unknown VQL error occurred" in hint
