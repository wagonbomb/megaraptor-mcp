"""
Client management tools for Velociraptor MCP.

Provides tools for listing, searching, and managing Velociraptor clients (endpoints).
"""

import json
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..client import get_client


def register_client_tools(server: Server) -> None:
    """Register client management tools with the MCP server."""

    @server.tool()
    async def list_clients(
        search: Optional[str] = None,
        limit: int = 100,
    ) -> list[TextContent]:
        """Search and list Velociraptor clients (endpoints).

        Args:
            search: Optional search query. Supports prefixes like 'label:' and 'host:'.
                   Examples: 'label:production', 'host:workstation-01', 'windows'
            limit: Maximum number of clients to return (default 100)

        Returns:
            List of clients with their ID, hostname, OS, labels, and last seen time.
        """
        client = get_client()

        if search:
            vql = f"SELECT * FROM clients(search='{search}') LIMIT {limit}"
        else:
            vql = f"SELECT * FROM clients() LIMIT {limit}"

        results = client.query(vql)

        # Format the results
        formatted = []
        for row in results:
            client_info = {
                "client_id": row.get("client_id", ""),
                "hostname": row.get("os_info", {}).get("hostname", ""),
                "os": row.get("os_info", {}).get("system", ""),
                "release": row.get("os_info", {}).get("release", ""),
                "labels": row.get("labels", []),
                "last_seen_at": row.get("last_seen_at", ""),
                "first_seen_at": row.get("first_seen_at", ""),
                "last_ip": row.get("last_ip", ""),
            }
            formatted.append(client_info)

        return [TextContent(
            type="text",
            text=json.dumps(formatted, indent=2)
        )]

    @server.tool()
    async def get_client_info(client_id: str) -> list[TextContent]:
        """Get detailed information about a specific Velociraptor client.

        Args:
            client_id: The client ID (e.g., 'C.1234567890abcdef')

        Returns:
            Detailed client information including hardware, OS, IP addresses.
        """
        client = get_client()

        vql = f"SELECT * FROM clients(client_id='{client_id}')"
        results = client.query(vql)

        if not results:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Client {client_id} not found"})
            )]

        # Return the full client info
        return [TextContent(
            type="text",
            text=json.dumps(results[0], indent=2, default=str)
        )]

    @server.tool()
    async def label_client(
        client_id: str,
        labels: list[str],
        operation: str = "add",
    ) -> list[TextContent]:
        """Add or remove labels from a Velociraptor client.

        Args:
            client_id: The client ID (e.g., 'C.1234567890abcdef')
            labels: List of label names to add or remove
            operation: Either 'add' or 'remove' (default: 'add')

        Returns:
            Updated client labels.
        """
        client = get_client()

        if operation not in ("add", "remove"):
            return [TextContent(
                type="text",
                text=json.dumps({"error": "Operation must be 'add' or 'remove'"})
            )]

        # Build the VQL for label modification
        labels_str = ", ".join(f"'{label}'" for label in labels)

        if operation == "add":
            vql = f"SELECT label(client_id='{client_id}', labels=[{labels_str}], op='set') FROM scope()"
        else:
            vql = f"SELECT label(client_id='{client_id}', labels=[{labels_str}], op='remove') FROM scope()"

        results = client.query(vql)

        # Get updated client info
        info_vql = f"SELECT labels FROM clients(client_id='{client_id}')"
        info_results = client.query(info_vql)

        return [TextContent(
            type="text",
            text=json.dumps({
                "client_id": client_id,
                "operation": operation,
                "labels_modified": labels,
                "current_labels": info_results[0].get("labels", []) if info_results else [],
            }, indent=2)
        )]

    @server.tool()
    async def quarantine_client(
        client_id: str,
        quarantine: bool = True,
        message: Optional[str] = None,
    ) -> list[TextContent]:
        """Quarantine or unquarantine a Velociraptor client.

        Quarantining a client isolates it from the network while maintaining
        communication with the Velociraptor server.

        Args:
            client_id: The client ID (e.g., 'C.1234567890abcdef')
            quarantine: True to quarantine, False to unquarantine (default: True)
            message: Optional message to include with the quarantine action

        Returns:
            Quarantine status of the client.
        """
        client = get_client()

        if quarantine:
            # Quarantine the client using the Windows.Remediation.Quarantine artifact
            # or appropriate artifact for the client's OS
            vql = f"""
            SELECT collect_client(
                client_id='{client_id}',
                artifacts='Windows.Remediation.Quarantine',
                env=dict(MessageBox='{message or "System quarantined by administrator"}')
            ) FROM scope()
            """
        else:
            # Unquarantine
            vql = f"""
            SELECT collect_client(
                client_id='{client_id}',
                artifacts='Windows.Remediation.Quarantine',
                env=dict(RemovePolicy='Y')
            ) FROM scope()
            """

        results = client.query(vql)

        return [TextContent(
            type="text",
            text=json.dumps({
                "client_id": client_id,
                "action": "quarantine" if quarantine else "unquarantine",
                "status": "initiated",
                "message": message,
                "result": results[0] if results else None,
            }, indent=2, default=str)
        )]
