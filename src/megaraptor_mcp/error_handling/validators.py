"""
Input validation functions for Velociraptor MCP tools.

Provides validation for common parameters like client IDs, limits, hunt IDs,
flow IDs, and basic VQL syntax checking.
"""


def validate_client_id(client_id: str) -> str:
    """Validate a Velociraptor client ID.

    Args:
        client_id: The client ID to validate

    Returns:
        The validated client ID

    Raises:
        ValueError: If the client ID is invalid
    """
    if not client_id:
        raise ValueError(
            "Client ID cannot be empty. "
            "Hint: Use list_clients tool to find valid client IDs."
        )

    if not client_id.startswith("C."):
        raise ValueError(
            f"Invalid client ID format: '{client_id}'. "
            "Must start with 'C.' (e.g., 'C.1234567890abcdef'). "
            "Hint: Use list_clients tool to find valid client IDs."
        )

    return client_id


def validate_limit(limit: int, min_val: int = 1, max_val: int = 10000) -> int:
    """Validate a limit parameter for result pagination.

    Args:
        limit: The limit value to validate
        min_val: Minimum allowed value (default: 1)
        max_val: Maximum allowed value (default: 10000)

    Returns:
        The validated limit

    Raises:
        ValueError: If the limit is out of range
    """
    if limit < min_val:
        raise ValueError(
            f"Limit must be at least {min_val}, got {limit}. "
            "Hint: Use a positive integer for limit."
        )

    if limit > max_val:
        raise ValueError(
            f"Limit cannot exceed {max_val}, got {limit}. "
            "Hint: For large result sets, use pagination or filtering in VQL."
        )

    return limit


def validate_hunt_id(hunt_id: str) -> str:
    """Validate a Velociraptor hunt ID.

    Args:
        hunt_id: The hunt ID to validate

    Returns:
        The validated hunt ID

    Raises:
        ValueError: If the hunt ID is invalid
    """
    if not hunt_id:
        raise ValueError(
            "Hunt ID cannot be empty. "
            "Hint: Use list_hunts tool to find valid hunt IDs."
        )

    if not hunt_id.startswith("H."):
        raise ValueError(
            f"Invalid hunt ID format: '{hunt_id}'. "
            "Must start with 'H.' (e.g., 'H.1234567890'). "
            "Hint: Use list_hunts tool to find valid hunt IDs."
        )

    return hunt_id


def validate_flow_id(flow_id: str) -> str:
    """Validate a Velociraptor flow ID.

    Args:
        flow_id: The flow ID to validate

    Returns:
        The validated flow ID

    Raises:
        ValueError: If the flow ID is invalid
    """
    if not flow_id:
        raise ValueError(
            "Flow ID cannot be empty. "
            "Hint: Use list_flows tool to find valid flow IDs."
        )

    if not flow_id.startswith("F."):
        raise ValueError(
            f"Invalid flow ID format: '{flow_id}'. "
            "Must start with 'F.' (e.g., 'F.1234567890'). "
            "Hint: Use list_flows tool to find valid flow IDs."
        )

    return flow_id


def validate_vql_syntax_basics(query: str) -> str:
    """Perform basic VQL syntax validation.

    Args:
        query: The VQL query to validate

    Returns:
        The validated query

    Raises:
        ValueError: If basic syntax issues are detected
    """
    if not query or not query.strip():
        raise ValueError(
            "VQL query cannot be empty. "
            "Hint: Use vql_help tool to learn VQL syntax."
        )

    query_stripped = query.strip()

    # VQL doesn't use semicolons
    if query_stripped.endswith(";"):
        raise ValueError(
            "VQL queries should not end with a semicolon (;). "
            "Hint: Unlike SQL, VQL doesn't use semicolons as statement terminators."
        )

    # Basic check for SELECT keyword
    query_upper = query_stripped.upper()
    if "SELECT" not in query_upper:
        raise ValueError(
            "VQL query must contain a SELECT statement. "
            "Hint: VQL is a query language based on SQL-like syntax. "
            "Use vql_help(topic='syntax') for more information."
        )

    return query
