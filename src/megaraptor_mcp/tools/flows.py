"""
Flow tools for Velociraptor MCP.

Provides tools for tracking and managing Velociraptor collection flows.
"""

import json
from typing import Optional

from mcp.types import TextContent

from ..server import mcp
from ..client import get_client


@mcp.tool()
async def list_flows(
    client_id: str,
    limit: int = 50,
) -> list[TextContent]:
    """List collection flows for a Velociraptor client.

    Args:
        client_id: The client ID (e.g., 'C.1234567890abcdef')
        limit: Maximum number of flows to return (default 50)

    Returns:
        List of flows with their status and artifacts.
    """
    client = get_client()

    vql = f"SELECT * FROM flows(client_id='{client_id}') LIMIT {limit}"
    results = client.query(vql)

    # Format the results
    formatted = []
    for row in results:
        flow = {
            "flow_id": row.get("session_id", ""),
            "state": row.get("state", ""),
            "artifacts": row.get("artifacts_with_results", []),
            "request": {
                "artifacts": row.get("request", {}).get("artifacts", []),
                "creator": row.get("request", {}).get("creator", ""),
            },
            "create_time": row.get("create_time", ""),
            "start_time": row.get("start_time", ""),
            "active_time": row.get("active_time", ""),
            "total_uploaded_bytes": row.get("total_uploaded_bytes", 0),
            "total_collected_rows": row.get("total_collected_rows", 0),
            "total_logs": row.get("total_logs", 0),
        }
        formatted.append(flow)

    return [TextContent(
        type="text",
        text=json.dumps(formatted, indent=2, default=str)
    )]


@mcp.tool()
async def get_flow_results(
    client_id: str,
    flow_id: str,
    artifact: Optional[str] = None,
    limit: int = 1000,
) -> list[TextContent]:
    """Get results from a specific Velociraptor collection flow.

    Args:
        client_id: The client ID (e.g., 'C.1234567890abcdef')
        flow_id: The flow ID (e.g., 'F.1234567890')
        artifact: Optional specific artifact to get results for
        limit: Maximum number of result rows to return (default 1000)

    Returns:
        Collection results data.
    """
    client = get_client()

    # Build the VQL query
    if artifact:
        vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='{artifact}'
        ) LIMIT {limit}
        """
    else:
        vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}'
        ) LIMIT {limit}
        """

    results = client.query(vql)

    return [TextContent(
        type="text",
        text=json.dumps({
            "client_id": client_id,
            "flow_id": flow_id,
            "artifact": artifact,
            "result_count": len(results),
            "results": results,
        }, indent=2, default=str)
    )]


@mcp.tool()
async def get_flow_status(
    client_id: str,
    flow_id: str,
) -> list[TextContent]:
    """Get the status of a specific collection flow.

    Args:
        client_id: The client ID (e.g., 'C.1234567890abcdef')
        flow_id: The flow ID (e.g., 'F.1234567890')

    Returns:
        Flow status including state, progress, and any errors.
    """
    client = get_client()

    vql = f"SELECT * FROM flows(client_id='{client_id}', flow_id='{flow_id}')"
    results = client.query(vql)

    if not results:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": f"Flow {flow_id} not found for client {client_id}"
            })
        )]

    flow = results[0]

    # Extract detailed status
    status = {
        "client_id": client_id,
        "flow_id": flow_id,
        "state": flow.get("state", ""),
        "artifacts_requested": flow.get("request", {}).get("artifacts", []),
        "artifacts_with_results": flow.get("artifacts_with_results", []),
        "create_time": flow.get("create_time", ""),
        "start_time": flow.get("start_time", ""),
        "active_time": flow.get("active_time", ""),
        "execution_duration": flow.get("execution_duration", 0),
        "total_uploaded_bytes": flow.get("total_uploaded_bytes", 0),
        "total_collected_rows": flow.get("total_collected_rows", 0),
        "outstanding_requests": flow.get("outstanding_requests", 0),
        "backtrace": flow.get("backtrace", ""),
        "status": flow.get("status", ""),
    }

    return [TextContent(
        type="text",
        text=json.dumps(status, indent=2, default=str)
    )]


@mcp.tool()
async def cancel_flow(
    client_id: str,
    flow_id: str,
) -> list[TextContent]:
    """Cancel a running collection flow.

    Args:
        client_id: The client ID (e.g., 'C.1234567890abcdef')
        flow_id: The flow ID (e.g., 'F.1234567890')

    Returns:
        Cancellation status.
    """
    client = get_client()

    vql = f"SELECT cancel_flow(client_id='{client_id}', flow_id='{flow_id}') FROM scope()"
    results = client.query(vql)

    return [TextContent(
        type="text",
        text=json.dumps({
            "client_id": client_id,
            "flow_id": flow_id,
            "action": "cancelled",
            "result": results[0] if results else None,
        }, indent=2, default=str)
    )]
