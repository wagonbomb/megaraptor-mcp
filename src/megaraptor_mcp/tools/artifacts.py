"""
Artifact tools for Velociraptor MCP.

Provides tools for listing, viewing, and collecting Velociraptor artifacts.
"""

import json
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..client import get_client


def register_artifact_tools(server: Server) -> None:
    """Register artifact tools with the MCP server."""

    @server.tool()
    async def list_artifacts(
        search: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TextContent]:
        """List available Velociraptor artifacts.

        Args:
            search: Optional search term to filter artifacts by name or description
            artifact_type: Optional type filter: 'CLIENT', 'SERVER', or 'NOTEBOOK'
            limit: Maximum number of artifacts to return (default 100)

        Returns:
            List of artifacts with their names, descriptions, and types.
        """
        client = get_client()

        # Build the VQL query
        conditions = []
        if search:
            conditions.append(f"name =~ '{search}' OR description =~ '{search}'")
        if artifact_type:
            conditions.append(f"type = '{artifact_type}'")

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        vql = f"SELECT name, description, type, parameters FROM artifact_definitions(){where_clause} LIMIT {limit}"

        results = client.query(vql)

        # Format the results
        formatted = []
        for row in results:
            artifact = {
                "name": row.get("name", ""),
                "description": (row.get("description", "") or "")[:200],  # Truncate long descriptions
                "type": row.get("type", ""),
                "has_parameters": bool(row.get("parameters")),
            }
            formatted.append(artifact)

        return [TextContent(
            type="text",
            text=json.dumps(formatted, indent=2)
        )]

    @server.tool()
    async def get_artifact(artifact_name: str) -> list[TextContent]:
        """Get the full definition of a Velociraptor artifact.

        Args:
            artifact_name: The name of the artifact (e.g., 'Windows.System.Pslist')

        Returns:
            Complete artifact definition including parameters, sources, and VQL.
        """
        client = get_client()

        vql = f"SELECT * FROM artifact_definitions(names='{artifact_name}')"
        results = client.query(vql)

        if not results:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Artifact '{artifact_name}' not found"})
            )]

        artifact = results[0]

        # Format the output
        formatted = {
            "name": artifact.get("name", ""),
            "description": artifact.get("description", ""),
            "type": artifact.get("type", ""),
            "author": artifact.get("author", ""),
            "parameters": artifact.get("parameters", []),
            "sources": artifact.get("sources", []),
            "precondition": artifact.get("precondition", ""),
            "required_permissions": artifact.get("required_permissions", []),
        }

        return [TextContent(
            type="text",
            text=json.dumps(formatted, indent=2, default=str)
        )]

    @server.tool()
    async def collect_artifact(
        client_id: str,
        artifacts: list[str],
        parameters: Optional[dict[str, Any]] = None,
        timeout: int = 600,
        urgent: bool = False,
    ) -> list[TextContent]:
        """Schedule artifact collection on a Velociraptor client.

        Args:
            client_id: The client ID (e.g., 'C.1234567890abcdef')
            artifacts: List of artifact names to collect
            parameters: Optional dict of parameters for the artifacts.
                       Format: {"ArtifactName": {"param1": "value1"}}
            timeout: Query timeout in seconds (default 600)
            urgent: If True, prioritize this collection (default False)

        Returns:
            Flow ID for tracking the collection.
        """
        client = get_client()

        # Build the artifacts list
        artifacts_str = ", ".join(f"'{a}'" for a in artifacts)

        # Build the spec parameter if parameters are provided
        spec_part = ""
        if parameters:
            spec_json = json.dumps(parameters)
            spec_part = f", spec={spec_json}"

        urgent_part = ", urgent=true" if urgent else ""

        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=[{artifacts_str}],
            timeout={timeout}
            {spec_part}
            {urgent_part}
        ) AS collection
        FROM scope()
        """

        results = client.query(vql)

        if not results:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "Failed to start collection"})
            )]

        collection = results[0].get("collection", {})

        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "collection_started",
                "client_id": client_id,
                "artifacts": artifacts,
                "flow_id": collection.get("flow_id", ""),
                "request": collection.get("request", {}),
            }, indent=2, default=str)
        )]
