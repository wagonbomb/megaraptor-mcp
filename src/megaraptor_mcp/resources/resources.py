"""
MCP Resources for browsing Velociraptor data.

Provides browsable resources for clients, hunts, and artifacts.
"""

import json
from typing import Any
from urllib.parse import urlparse

from mcp.server import Server
from mcp.types import Resource, TextContent

from ..client import get_client


def register_resources(server: Server) -> None:
    """Register MCP resources with the server."""

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available Velociraptor resources."""
        return [
            Resource(
                uri="velociraptor://clients",
                name="Velociraptor Clients",
                description="Browse connected Velociraptor endpoints",
                mimeType="application/json",
            ),
            Resource(
                uri="velociraptor://hunts",
                name="Velociraptor Hunts",
                description="Browse Velociraptor hunt campaigns",
                mimeType="application/json",
            ),
            Resource(
                uri="velociraptor://artifacts",
                name="Velociraptor Artifacts",
                description="Browse available Velociraptor artifacts",
                mimeType="application/json",
            ),
            Resource(
                uri="velociraptor://server-info",
                name="Server Information",
                description="Velociraptor server information and status",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        """Read a Velociraptor resource."""
        parsed = urlparse(uri)

        if parsed.scheme != "velociraptor":
            raise ValueError(f"Unknown resource scheme: {parsed.scheme}")

        path = parsed.netloc + parsed.path
        path_parts = path.strip("/").split("/")

        client = get_client()

        # Route to appropriate handler
        if path_parts[0] == "clients":
            return await _handle_clients_resource(client, path_parts[1:])
        elif path_parts[0] == "hunts":
            return await _handle_hunts_resource(client, path_parts[1:])
        elif path_parts[0] == "artifacts":
            return await _handle_artifacts_resource(client, path_parts[1:])
        elif path_parts[0] == "server-info":
            return await _handle_server_info_resource(client)
        else:
            raise ValueError(f"Unknown resource path: {path}")


async def _handle_clients_resource(client: Any, path_parts: list[str]) -> str:
    """Handle clients resource requests."""
    if not path_parts or not path_parts[0]:
        # List all clients
        vql = "SELECT client_id, os_info.hostname AS hostname, os_info.system AS os, labels, last_seen_at FROM clients() LIMIT 100"
        results = client.query(vql)

        return json.dumps({
            "type": "client_list",
            "count": len(results),
            "clients": results,
        }, indent=2, default=str)
    else:
        # Get specific client
        client_id = path_parts[0]
        vql = f"SELECT * FROM clients(client_id='{client_id}')"
        results = client.query(vql)

        if not results:
            return json.dumps({"error": f"Client {client_id} not found"})

        return json.dumps({
            "type": "client_detail",
            "client": results[0],
        }, indent=2, default=str)


async def _handle_hunts_resource(client: Any, path_parts: list[str]) -> str:
    """Handle hunts resource requests."""
    if not path_parts or not path_parts[0]:
        # List all hunts
        vql = "SELECT hunt_id, hunt_description, state, artifacts, create_time, stats FROM hunts() LIMIT 50"
        results = client.query(vql)

        return json.dumps({
            "type": "hunt_list",
            "count": len(results),
            "hunts": results,
        }, indent=2, default=str)
    else:
        # Get specific hunt
        hunt_id = path_parts[0]

        if len(path_parts) > 1 and path_parts[1] == "results":
            # Get hunt results
            vql = f"SELECT * FROM hunt_results(hunt_id='{hunt_id}') LIMIT 1000"
            results = client.query(vql)

            return json.dumps({
                "type": "hunt_results",
                "hunt_id": hunt_id,
                "count": len(results),
                "results": results,
            }, indent=2, default=str)
        else:
            # Get hunt details
            vql = f"SELECT * FROM hunts() WHERE hunt_id = '{hunt_id}'"
            results = client.query(vql)

            if not results:
                return json.dumps({"error": f"Hunt {hunt_id} not found"})

            return json.dumps({
                "type": "hunt_detail",
                "hunt": results[0],
            }, indent=2, default=str)


async def _handle_artifacts_resource(client: Any, path_parts: list[str]) -> str:
    """Handle artifacts resource requests."""
    if not path_parts or not path_parts[0]:
        # List all artifacts
        vql = "SELECT name, description, type FROM artifact_definitions() LIMIT 500"
        results = client.query(vql)

        # Group by category (first part of name)
        categories = {}
        for artifact in results:
            name = artifact.get("name", "")
            category = name.split(".")[0] if "." in name else "Other"
            if category not in categories:
                categories[category] = []
            categories[category].append({
                "name": name,
                "description": (artifact.get("description", "") or "")[:100],
                "type": artifact.get("type", ""),
            })

        return json.dumps({
            "type": "artifact_list",
            "total_count": len(results),
            "categories": categories,
        }, indent=2, default=str)
    else:
        # Get specific artifact
        artifact_name = "/".join(path_parts)  # Handle nested names like Windows.System.Pslist
        vql = f"SELECT * FROM artifact_definitions(names='{artifact_name}')"
        results = client.query(vql)

        if not results:
            return json.dumps({"error": f"Artifact {artifact_name} not found"})

        return json.dumps({
            "type": "artifact_detail",
            "artifact": results[0],
        }, indent=2, default=str)


async def _handle_server_info_resource(client: Any) -> str:
    """Handle server info resource request."""
    vql = "SELECT * FROM info()"
    results = client.query(vql)

    # Get server version and other info
    version_vql = "SELECT server_version() AS version FROM scope()"
    version_results = client.query(version_vql)

    return json.dumps({
        "type": "server_info",
        "info": results[0] if results else {},
        "version": version_results[0].get("version") if version_results else "unknown",
    }, indent=2, default=str)
