"""Deployment helpers for end-to-end deployment testing.

These helpers support testing the full deployment lifecycle including
waiting for health checks, verifying server accessibility, and confirming
container cleanup after rollback.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from megaraptor_mcp.deployment.deployers.base import BaseDeployer, DeploymentInfo

logger = logging.getLogger(__name__)


async def wait_for_deployment_healthy(
    deployer: "BaseDeployer",
    deployment_id: str,
    timeout: int = 120,
    poll_interval: int = 5,
) -> dict[str, Any]:
    """Wait for a deployment to become healthy.

    Polls the deployer's health_check() method until the deployment
    reports healthy=True or the timeout is reached.

    Args:
        deployer: The deployer instance managing the deployment
        deployment_id: The deployment identifier to check
        timeout: Maximum wait time in seconds (default 120)
        poll_interval: Time between health checks in seconds (default 5)

    Returns:
        Health check dictionary on success

    Raises:
        TimeoutError: If deployment doesn't become healthy within timeout
    """
    elapsed = 0

    while elapsed < timeout:
        health = await deployer.health_check(deployment_id)

        if health.get("healthy"):
            logger.info(f"Deployment {deployment_id} is healthy after {elapsed}s")
            return health

        logger.debug(
            f"Deployment {deployment_id} not healthy yet (elapsed: {elapsed}s). "
            f"Status: {health}"
        )

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(
        f"Deployment {deployment_id} did not become healthy within {timeout}s. "
        f"Last health check: {health}"
    )


async def verify_deployment_accessible(info: "DeploymentInfo") -> bool:
    """Verify that a deployment's server URL is accessible.

    Attempts to connect to the server URL and verifies it responds
    with a non-error status code (< 500).

    Args:
        info: DeploymentInfo object containing server_url

    Returns:
        True if server responds with status < 500, False otherwise
    """
    if not info or not info.server_url:
        logger.warning("No server_url in deployment info")
        return False

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed, cannot verify accessibility")
        return False

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            response = await client.get(info.server_url)
            accessible = response.status_code < 500

            logger.info(
                f"Server {info.server_url} responded with status {response.status_code} "
                f"(accessible: {accessible})"
            )

            return accessible

    except Exception as e:
        logger.warning(f"Failed to connect to {info.server_url}: {e}")
        return False


def verify_container_removed(deployer: "BaseDeployer", deployment_id: str) -> bool:
    """Verify that a Docker container has been removed.

    Attempts to retrieve the container for the deployment. If the container
    is not found (docker.errors.NotFound), the container has been successfully
    removed.

    Args:
        deployer: The Docker deployer instance
        deployment_id: The deployment identifier

    Returns:
        True if container is removed (NotFound), False if it still exists
    """
    # Lazy import to avoid import errors when Docker is unavailable
    try:
        import docker
        from docker.errors import NotFound
    except ImportError:
        logger.warning("docker module not installed, cannot verify container removal")
        return False

    try:
        # Get the container name using the deployer's naming convention
        container_name = deployer._container_name(deployment_id)

        # Try to get the container
        client = deployer.client
        container = client.containers.get(container_name)

        # Container still exists
        logger.warning(
            f"Container {container_name} still exists with status: {container.status}"
        )
        return False

    except NotFound:
        # Container not found = successfully removed
        logger.info(f"Container for deployment {deployment_id} has been removed")
        return True

    except Exception as e:
        logger.warning(f"Error checking container status: {e}")
        return False
