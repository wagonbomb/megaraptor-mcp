"""
Hunt tools for Velociraptor MCP.

Provides tools for creating and managing Velociraptor hunts (mass collection campaigns).
"""

import grpc
import json
from typing import Any, Optional

from mcp.types import TextContent

from ..server import mcp
from ..client import get_client
from ..error_handling import (
    validate_hunt_id,
    validate_limit,
    map_grpc_error,
)


@mcp.tool()
async def create_hunt(
    artifacts: list[str],
    description: str,
    parameters: Optional[dict[str, Any]] = None,
    include_labels: Optional[list[str]] = None,
    exclude_labels: Optional[list[str]] = None,
    os_filter: Optional[str] = None,
    timeout: int = 600,
    expires_hours: int = 24,
    paused: bool = True,
) -> list[TextContent]:
    """Create a new Velociraptor hunt to collect artifacts across multiple clients.

    Args:
        artifacts: List of artifact names to collect
        description: Description of the hunt's purpose
        parameters: Optional parameters for artifacts. Format: {"ArtifactName": {"param": "value"}}
        include_labels: Only include clients with these labels
        exclude_labels: Exclude clients with these labels
        os_filter: Filter by OS: 'windows', 'linux', 'darwin'
        timeout: Query timeout per client in seconds (default 600)
        expires_hours: Hunt expiration in hours (default 24)
        paused: Create hunt in paused state (default True for safety)

    Returns:
        Hunt ID and details.
    """
    # Input validation
    if not artifacts:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "artifacts parameter is required and cannot be empty"
            })
        )]

    if not description:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "description parameter is required and cannot be empty"
            })
        )]

    if os_filter and os_filter not in ['windows', 'linux', 'darwin']:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": f"Invalid os_filter '{os_filter}'. Must be one of: windows, linux, darwin"
            })
        )]

    try:
        client = get_client()

        # Build the artifacts list
        artifacts_str = ", ".join(f"'{a}'" for a in artifacts)

        # Build optional parameters
        parts = [
            f"artifacts=[{artifacts_str}]",
            f"description='{description}'",
            f"timeout={timeout}",
            f"expires=now() + {expires_hours * 3600}",
            f"pause={'true' if paused else 'false'}",
        ]

        if parameters:
            spec_json = json.dumps(parameters).replace("'", "\\'")
            parts.append(f"spec={spec_json}")

        if include_labels:
            labels_str = ", ".join(f"'{l}'" for l in include_labels)
            parts.append(f"include_labels=[{labels_str}]")

        if exclude_labels:
            labels_str = ", ".join(f"'{l}'" for l in exclude_labels)
            parts.append(f"exclude_labels=[{labels_str}]")

        if os_filter:
            parts.append(f"os='{os_filter}'")

        params_str = ", ".join(parts)
        vql = f"SELECT hunt({params_str}) AS hunt FROM scope()"

        results = client.query(vql)

        if not results:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "Failed to create hunt"})
            )]

        hunt = results[0].get("hunt", {})

        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "hunt_created",
                "hunt_id": hunt.get("hunt_id", ""),
                "description": description,
                "artifacts": artifacts,
                "state": "PAUSED" if paused else "RUNNING",
                "expires": hunt.get("expires", ""),
            }, indent=2, default=str)
        )]

    except grpc.RpcError as e:
        error_response = map_grpc_error(e, "hunt creation")
        return [TextContent(
            type="text",
            text=json.dumps(error_response)
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": f"Unexpected error during hunt creation: {str(e)}"
            })
        )]


@mcp.tool()
async def list_hunts(
    state: Optional[str] = None,
    limit: int = 50,
) -> list[TextContent]:
    """List Velociraptor hunts.

    Args:
        state: Optional filter by state: 'RUNNING', 'PAUSED', 'STOPPED', 'COMPLETED'
        limit: Maximum number of hunts to return (default 50)

    Returns:
        List of hunts with their status and statistics.
    """
    try:
        # Input validation
        limit = validate_limit(limit)

        if state and state.upper() not in ['RUNNING', 'PAUSED', 'STOPPED', 'COMPLETED']:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Invalid state '{state}'. Must be one of: RUNNING, PAUSED, STOPPED, COMPLETED"
                })
            )]
        client = get_client()

        vql = f"SELECT * FROM hunts() LIMIT {limit}"
        results = client.query(vql)

        # Filter by state if specified
        if state:
            results = [r for r in results if r.get("state", "").upper() == state.upper()]

        # Format the results
        formatted = []
        for row in results:
            hunt = {
                "hunt_id": row.get("hunt_id", ""),
                "description": row.get("hunt_description", ""),
                "state": row.get("state", ""),
                "artifacts": row.get("artifacts", []),
                "created_time": row.get("create_time", ""),
                "start_time": row.get("start_time", ""),
                "stats": {
                    "total_clients_scheduled": row.get("stats", {}).get("total_clients_scheduled", 0),
                    "total_clients_with_results": row.get("stats", {}).get("total_clients_with_results", 0),
                    "total_clients_with_errors": row.get("stats", {}).get("total_clients_with_errors", 0),
                },
                "creator": row.get("creator", ""),
            }
            formatted.append(hunt)

        return [TextContent(
            type="text",
            text=json.dumps(formatted, indent=2, default=str)
        )]

    except grpc.RpcError as e:
        error_response = map_grpc_error(e, "hunt listing")
        return [TextContent(
            type="text",
            text=json.dumps(error_response)
        )]

    except ValueError as e:
        # Validation errors
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "hint": "Check your limit parameter value"
            })
        )]

    except Exception:
        # Generic errors - don't expose internals
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to list hunts",
                "hint": "Check Velociraptor server connection and try again"
            })
        )]


@mcp.tool()
async def get_hunt_results(
    hunt_id: str,
    artifact: Optional[str] = None,
    limit: int = 1000,
) -> list[TextContent]:
    """Get results from a Velociraptor hunt.

    Args:
        hunt_id: The hunt ID (e.g., 'H.1234567890')
        artifact: Optional specific artifact to get results for
        limit: Maximum number of result rows to return (default 1000)

    Returns:
        Hunt results data from all clients.
    """
    try:
        # Input validation
        hunt_id = validate_hunt_id(hunt_id)
        limit = validate_limit(limit)
        client = get_client()

        # Build the VQL query
        if artifact:
            vql = f"SELECT * FROM hunt_results(hunt_id='{hunt_id}', artifact='{artifact}') LIMIT {limit}"
        else:
            vql = f"SELECT * FROM hunt_results(hunt_id='{hunt_id}') LIMIT {limit}"

        results = client.query(vql)

        return [TextContent(
            type="text",
            text=json.dumps({
                "hunt_id": hunt_id,
                "artifact": artifact,
                "result_count": len(results),
                "results": results[:limit],
            }, indent=2, default=str)
        )]

    except grpc.RpcError as e:
        error_response = map_grpc_error(e, f"hunt results for {hunt_id}")
        # Check if it's a not-found error
        if "NOT_FOUND" in error_response.get("grpc_status", ""):
            error_response["hint"] = f"Hunt {hunt_id} may not exist. Use list_hunts() to see available hunts."
        return [TextContent(
            type="text",
            text=json.dumps(error_response)
        )]

    except ValueError as e:
        # Validation errors
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "hint": "Provide a valid hunt ID starting with 'H.'"
            })
        )]

    except Exception:
        # Generic errors - don't expose internals
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to get hunt results",
                "hint": "Check hunt ID and try again"
            })
        )]


@mcp.tool()
async def modify_hunt(
    hunt_id: str,
    action: str,
) -> list[TextContent]:
    """Modify a Velociraptor hunt state.

    Args:
        hunt_id: The hunt ID (e.g., 'H.1234567890')
        action: Action to perform: 'start', 'pause', 'stop', 'archive'

    Returns:
        Updated hunt status.
    """
    try:
        # Input validation
        hunt_id = validate_hunt_id(hunt_id)

        action_map = {
            "start": "StartHuntRequest",
            "pause": "PauseHuntRequest",
            "stop": "StopHuntRequest",
            "archive": "ArchiveHuntRequest",
        }

        if action not in action_map:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Invalid action '{action}'. Must be one of: start, pause, stop, archive"
                })
            )]

        client = get_client()

        # Use the hunt() function to modify the hunt
        if action == "start":
            vql = f"SELECT hunt_update(hunt_id='{hunt_id}', state='RUNNING') FROM scope()"
        elif action == "pause":
            vql = f"SELECT hunt_update(hunt_id='{hunt_id}', state='PAUSED') FROM scope()"
        elif action == "stop":
            vql = f"SELECT hunt_update(hunt_id='{hunt_id}', state='STOPPED') FROM scope()"
        else:  # archive
            vql = f"SELECT hunt_update(hunt_id='{hunt_id}', state='ARCHIVED') FROM scope()"

        results = client.query(vql)

        return [TextContent(
            type="text",
            text=json.dumps({
                "hunt_id": hunt_id,
                "action": action,
                "status": "success",
                "result": results[0] if results else None,
            }, indent=2, default=str)
        )]

    except grpc.RpcError as e:
        error_response = map_grpc_error(e, f"modifying hunt {hunt_id}")
        # Check if it's a not-found error
        if "NOT_FOUND" in error_response.get("grpc_status", ""):
            error_response["hint"] = f"Hunt {hunt_id} may not exist. Use list_hunts() to see available hunts."
        return [TextContent(
            type="text",
            text=json.dumps(error_response)
        )]

    except ValueError as e:
        # Validation errors
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "hint": "Provide a valid hunt ID starting with 'H.'"
            })
        )]

    except Exception:
        # Generic errors - don't expose internals
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to modify hunt",
                "hint": "Check hunt ID and action parameter"
            })
        )]
