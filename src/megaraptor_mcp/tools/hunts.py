"""
Hunt tools for Velociraptor MCP.

Provides tools for creating and managing Velociraptor hunts (mass collection campaigns).
"""

import json
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..client import get_client


def register_hunt_tools(server: Server) -> None:
    """Register hunt tools with the MCP server."""

    @server.tool()
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

    @server.tool()
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

    @server.tool()
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

    @server.tool()
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
        client = get_client()

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
