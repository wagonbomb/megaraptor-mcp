"""
MCP Resources for browsing Velociraptor data.

Provides browsable resources for clients, hunts, and artifacts.
"""

import json
from typing import Any

from ..server import mcp
from ..client import get_client


# Resource handler functions
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


async def _handle_deployments_resource(path_parts: list[str]) -> str:
    """Handle deployments resource requests."""
    try:
        from ..deployment.deployers import DockerDeployer, BinaryDeployer
        from ..deployment.profiles import DeploymentState

        if not path_parts or not path_parts[0]:
            # List all deployments
            all_deployments = []

            # Get Docker deployments
            try:
                docker_deployer = DockerDeployer()
                deployments = docker_deployer.list_deployments()
                all_deployments.extend([d.to_dict() for d in deployments])
            except Exception:
                pass

            # Get binary deployments
            try:
                binary_deployer = BinaryDeployer()
                deployments = binary_deployer.list_deployments()
                all_deployments.extend([d.to_dict() for d in deployments])
            except Exception:
                pass

            return json.dumps({
                "type": "deployment_list",
                "count": len(all_deployments),
                "deployments": all_deployments,
            }, indent=2, default=str)

        else:
            # Get specific deployment
            deployment_id = path_parts[0]

            # Try Docker first
            try:
                deployer = DockerDeployer()
                info = await deployer.get_status(deployment_id)
                if info:
                    health = await deployer.health_check(deployment_id)
                    return json.dumps({
                        "type": "deployment_detail",
                        "deployment": info.to_dict(),
                        "health": health,
                    }, indent=2, default=str)
            except Exception:
                pass

            # Try binary deployer
            try:
                deployer = BinaryDeployer()
                info = await deployer.get_status(deployment_id)
                if info:
                    health = await deployer.health_check(deployment_id)
                    return json.dumps({
                        "type": "deployment_detail",
                        "deployment": info.to_dict(),
                        "health": health,
                    }, indent=2, default=str)
            except Exception:
                pass

            return json.dumps({
                "error": f"Deployment {deployment_id} not found"
            }, indent=2)

    except ImportError as e:
        return json.dumps({
            "type": "deployment_list",
            "count": 0,
            "deployments": [],
            "note": f"Deployment features require additional packages: {str(e)}",
        }, indent=2)


# Register resources using FastMCP @mcp.resource() decorator
@mcp.resource("velociraptor://clients")
async def clients_resource() -> str:
    """Browse connected Velociraptor endpoints."""
    client = get_client()
    return await _handle_clients_resource(client, [])


@mcp.resource("velociraptor://clients/{client_id}")
async def client_detail_resource(client_id: str) -> str:
    """Get details for a specific Velociraptor client."""
    client = get_client()
    return await _handle_clients_resource(client, [client_id])


@mcp.resource("velociraptor://hunts")
async def hunts_resource() -> str:
    """Browse Velociraptor hunt campaigns."""
    client = get_client()
    return await _handle_hunts_resource(client, [])


@mcp.resource("velociraptor://hunts/{hunt_id}")
async def hunt_detail_resource(hunt_id: str) -> str:
    """Get details for a specific hunt."""
    client = get_client()
    return await _handle_hunts_resource(client, [hunt_id])


@mcp.resource("velociraptor://hunts/{hunt_id}/results")
async def hunt_results_resource(hunt_id: str) -> str:
    """Get results from a specific hunt."""
    client = get_client()
    return await _handle_hunts_resource(client, [hunt_id, "results"])


@mcp.resource("velociraptor://artifacts")
async def artifacts_resource() -> str:
    """Browse available Velociraptor artifacts."""
    client = get_client()
    return await _handle_artifacts_resource(client, [])


@mcp.resource("velociraptor://artifacts/{artifact_name}")
async def artifact_detail_resource(artifact_name: str) -> str:
    """Get details for a specific artifact."""
    client = get_client()
    return await _handle_artifacts_resource(client, [artifact_name])


@mcp.resource("velociraptor://server-info")
async def server_info_resource() -> str:
    """Velociraptor server information and status."""
    client = get_client()
    return await _handle_server_info_resource(client)


@mcp.resource("velociraptor://deployments")
async def deployments_resource() -> str:
    """List of Velociraptor deployments managed by Megaraptor MCP."""
    return await _handle_deployments_resource([])


@mcp.resource("velociraptor://deployments/{deployment_id}")
async def deployment_detail_resource(deployment_id: str) -> str:
    """Get details for a specific deployment."""
    return await _handle_deployments_resource([deployment_id])
