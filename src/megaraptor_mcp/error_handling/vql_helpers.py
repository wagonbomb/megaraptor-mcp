"""
VQL error parsing and hint extraction.

Helps users understand VQL errors from the server and provides actionable hints.
"""

import re


def extract_vql_error_hint(error_message: str) -> str:
    """Extract actionable hints from VQL error messages.

    Parses common VQL error patterns and provides helpful hints for resolution.

    Args:
        error_message: The error message from the Velociraptor server

    Returns:
        A user-friendly hint for resolving the error
    """
    error_lower = error_message.lower()

    # Symbol not found - likely plugin/function name issue
    if "symbol" in error_lower and "not found" in error_lower:
        # Try to extract the symbol name
        match = re.search(r"symbol[:\s]+['\"]?(\w+)['\"]?\s+not found", error_message, re.IGNORECASE)
        symbol = match.group(1) if match else "unknown"

        return (
            f"VQL symbol '{symbol}' not found. This usually means:\n"
            "1. The plugin or function name is misspelled\n"
            "2. The plugin is not loaded on the server\n"
            "3. You're using an artifact-specific function in a generic query\n\n"
            "Hint: Use vql_help tool to search for available plugins and functions."
        )

    # Syntax error - general VQL syntax issues
    if "syntax error" in error_lower:
        return (
            "VQL syntax error detected. Common issues:\n"
            "1. VQL doesn't use semicolons (;) at the end of statements\n"
            "2. Function arguments use keyword syntax: function(arg=value)\n"
            "3. String literals must use double quotes, not single quotes\n"
            "4. Check parentheses and bracket matching\n\n"
            "Hint: Use vql_help(topic='syntax') for VQL syntax reference."
        )

    # Parentheses balance issues
    if "expected )" in error_lower or "expected (" in error_lower:
        return (
            "Unbalanced parentheses in VQL query.\n"
            "Hint: Check that all opening '(' have matching closing ')' and vice versa.\n"
            "Function calls, subqueries, and grouped expressions all need balanced parentheses."
        )

    # LET statement in wrong place
    if ("let" in error_lower and "select" in error_lower) or "let cannot appear" in error_lower:
        return (
            "LET statements must be separate from SELECT statements in VQL.\n"
            "Correct pattern:\n"
            "  LET my_var = value\n"
            "  SELECT * FROM info()\n\n"
            "Hint: LET binds variables that can be used in subsequent statements."
        )

    # Type mismatch or conversion issues
    if "type" in error_lower and ("mismatch" in error_lower or "convert" in error_lower):
        return (
            "VQL type error - attempting to use incompatible data types.\n"
            "Common causes:\n"
            "1. Passing wrong type to function (e.g., string where int expected)\n"
            "2. Arithmetic on non-numeric values\n"
            "3. Comparison between incompatible types\n\n"
            "Hint: Use type conversion functions like int(), str(), or check your data types."
        )

    # Plugin not available
    if "plugin" in error_lower and ("not available" in error_lower or "not found" in error_lower):
        return (
            "VQL plugin not available on this server.\n"
            "This could mean:\n"
            "1. Plugin is disabled in server configuration\n"
            "2. Plugin requires specific OS (Windows/Linux/Mac)\n"
            "3. Plugin name is misspelled\n\n"
            "Hint: Use vql_help tool to list available plugins for this server."
        )

    # Column/field not found
    if "column" in error_lower and "not found" in error_lower:
        return (
            "Column or field not found in query result.\n"
            "This usually means:\n"
            "1. The field name is misspelled\n"
            "2. The plugin doesn't return that field\n"
            "3. Field is only available in certain contexts\n\n"
            "Hint: Use 'SELECT * FROM plugin()' first to see available fields."
        )

    # Default hint for unrecognized errors
    return (
        "VQL query error. General troubleshooting steps:\n"
        "1. Use vql_help(topic='syntax') to review VQL syntax\n"
        "2. Simplify the query to isolate the issue\n"
        "3. Check the Velociraptor documentation for the specific plugin or function\n"
        "4. Verify you're using the correct VQL dialect for your server version\n\n"
        f"Original error: {error_message}"
    )
