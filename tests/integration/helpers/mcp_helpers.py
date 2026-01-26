"""MCP tool invocation helpers for smoke tests.

Provides clean interface for invoking MCP tools in tests.
"""

import json
from typing import Any, Optional

# Import mcp and trigger tool registration
from megaraptor_mcp.server import mcp
from megaraptor_mcp import tools  # noqa: F401 - triggers @mcp.tool() registration


async def invoke_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[bool, Any]:
    """Invoke an MCP tool and return parsed response.

    Args:
        tool_name: Name of the MCP tool to invoke
        arguments: Dictionary of arguments to pass to the tool

    Returns:
        Tuple of (success: bool, response: Any)
        - success=True, response=parsed JSON data
        - success=False, response=error message string
    """
    try:
        result = await mcp.call_tool(tool_name, arguments)

        if not result:
            return False, "Tool returned empty result"

        # FastMCP's call_tool returns (content_list, metadata_dict)
        # Handle both tuple and list return types
        if isinstance(result, tuple):
            content_list = result[0]  # First element is the content list
        else:
            content_list = result

        if not content_list:
            return False, "Tool returned empty content"

        # First content item should be TextContent
        content = content_list[0]

        if not hasattr(content, 'text'):
            return False, f"Response missing 'text' attribute: {type(content)}"

        # Parse JSON response
        try:
            data = json.loads(content.text)

            # Check for error field in response
            if isinstance(data, dict) and "error" in data and data["error"]:
                return False, data["error"]

            return True, data

        except json.JSONDecodeError as e:
            # Some tools return plain text (like vql_help)
            return True, content.text

    except Exception as e:
        return False, str(e)


def parse_tool_response(result: list) -> tuple[bool, Any]:
    """Parse an MCP tool result into usable data.

    Args:
        result: Raw result from mcp.call_tool() - may be tuple or list

    Returns:
        Tuple of (success: bool, data: Any)
    """
    if not result:
        return False, "Empty result"

    # FastMCP's call_tool returns (content_list, metadata_dict)
    if isinstance(result, tuple):
        content_list = result[0]
    else:
        content_list = result

    if not content_list:
        return False, "Empty content"

    content = content_list[0]

    if not hasattr(content, 'text'):
        return False, f"Missing 'text' attribute: {type(content)}"

    try:
        data = json.loads(content.text)

        if isinstance(data, dict) and "error" in data and data["error"]:
            return False, data["error"]

        return True, data

    except json.JSONDecodeError:
        # Plain text response
        return True, content.text


def replace_placeholders(arguments: dict, client_id: Optional[str] = None) -> dict:
    """Replace placeholder values in tool arguments.

    Args:
        arguments: Tool arguments dict
        client_id: Real client ID to substitute

    Returns:
        Arguments with placeholders replaced
    """
    result = arguments.copy()

    if client_id:
        for key in ["client_id"]:
            if key in result and result[key] in ("C.placeholder", "C.test"):
                result[key] = client_id

    return result
