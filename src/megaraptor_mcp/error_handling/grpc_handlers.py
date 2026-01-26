"""
gRPC error handling utilities.

Maps gRPC status codes to user-friendly error messages and determines
which errors are retryable.
"""

import grpc
from typing import Any


def is_retryable_grpc_error(exception: Any) -> bool:
    """Determine if a gRPC error is retryable.

    Transient errors like UNAVAILABLE, DEADLINE_EXCEEDED, and RESOURCE_EXHAUSTED
    should be retried with exponential backoff.

    Args:
        exception: The exception to check

    Returns:
        True if the error is retryable, False otherwise
    """
    if not isinstance(exception, grpc.RpcError):
        return False

    try:
        code = exception.code()
        return code in (
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
        )
    except Exception:
        return False


def map_grpc_error(error: grpc.RpcError, operation: str) -> dict[str, str]:
    """Map a gRPC error to a user-friendly message with hints.

    Args:
        error: The gRPC error
        operation: Description of the operation that failed (e.g., "query execution")

    Returns:
        Dictionary with keys:
        - error: User-friendly error message
        - hint: Actionable hint for resolving the issue
        - grpc_status: The gRPC status code name
    """
    try:
        code = error.code()
    except Exception:
        # If we can't get the code, return a generic error
        return {
            "error": f"Unknown error during {operation}",
            "hint": "Check Velociraptor server logs for details.",
            "grpc_status": "UNKNOWN",
        }

    status_name = code.name if hasattr(code, "name") else "UNKNOWN"

    # Map status codes to user-friendly messages
    if code == grpc.StatusCode.UNAVAILABLE:
        return {
            "error": f"Velociraptor server is unavailable during {operation}",
            "hint": (
                "1. Check if the Velociraptor server is running\n"
                "2. Verify network connectivity\n"
                "3. Check server URL in configuration"
            ),
            "grpc_status": status_name,
        }

    elif code == grpc.StatusCode.DEADLINE_EXCEEDED:
        return {
            "error": f"Operation timeout during {operation}",
            "hint": (
                "1. Query took too long to execute\n"
                "2. Try adding LIMIT clause to reduce result set\n"
                "3. Increase timeout parameter if needed\n"
                "4. Check if server is under high load"
            ),
            "grpc_status": status_name,
        }

    elif code == grpc.StatusCode.NOT_FOUND:
        return {
            "error": f"Resource not found during {operation}",
            "hint": (
                "1. Verify the ID is correct (client_id, hunt_id, flow_id, etc.)\n"
                "2. Use list_* tools to find valid IDs\n"
                "3. Check if resource was deleted"
            ),
            "grpc_status": status_name,
        }

    elif code == grpc.StatusCode.INVALID_ARGUMENT:
        details = error.details() if hasattr(error, "details") else ""
        return {
            "error": f"Invalid argument during {operation}: {details}",
            "hint": (
                "1. Check parameter formats (client_id starts with 'C.', etc.)\n"
                "2. Verify VQL syntax if running a query\n"
                "3. Use vql_help tool for VQL syntax guidance"
            ),
            "grpc_status": status_name,
        }

    elif code == grpc.StatusCode.UNAUTHENTICATED:
        return {
            "error": f"Authentication failed during {operation}",
            "hint": (
                "1. Check API configuration file path\n"
                "2. Verify certificate validity\n"
                "3. Ensure VELOCIRAPTOR_CONFIG environment variable is set correctly"
            ),
            "grpc_status": status_name,
        }

    elif code == grpc.StatusCode.PERMISSION_DENIED:
        return {
            "error": f"Permission denied during {operation}",
            "hint": (
                "1. Check API client permissions in Velociraptor\n"
                "2. Verify you have necessary roles for this operation\n"
                "3. Contact Velociraptor administrator if needed"
            ),
            "grpc_status": status_name,
        }

    elif code == grpc.StatusCode.INTERNAL:
        details = error.details() if hasattr(error, "details") else ""
        return {
            "error": f"Internal server error during {operation}: {details}",
            "hint": (
                "1. Check Velociraptor server logs for details\n"
                "2. This may indicate a bug in the server\n"
                "3. Try simplifying the query if using VQL"
            ),
            "grpc_status": status_name,
        }

    elif code == grpc.StatusCode.RESOURCE_EXHAUSTED:
        return {
            "error": f"Server resources exhausted during {operation}",
            "hint": (
                "1. Server is under heavy load\n"
                "2. Try again after a delay\n"
                "3. Reduce query complexity or result set size\n"
                "4. Contact administrator if issue persists"
            ),
            "grpc_status": status_name,
        }

    else:
        # Default fallback for unmapped status codes
        details = error.details() if hasattr(error, "details") else ""
        return {
            "error": f"gRPC error during {operation}: {status_name} - {details}",
            "hint": "Check server logs or contact administrator for details.",
            "grpc_status": status_name,
        }
