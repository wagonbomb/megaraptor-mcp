"""
Docker-based Velociraptor server deployment.

Uses Docker Compose for rapid deployment of Velociraptor servers.
"""

import asyncio
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Any

from .base import BaseDeployer, DeploymentResult, DeploymentInfo
from ..profiles import DeploymentProfile, DeploymentState, DeploymentTarget
from ..security.credential_store import generate_password

try:
    import docker
    from docker.errors import DockerException, NotFound, APIError
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


# Velociraptor Docker image
VELOCIRAPTOR_IMAGE = "velocidex/velociraptor:latest"


class DockerDeployer(BaseDeployer):
    """Deploy Velociraptor servers using Docker.

    This deployer uses Docker to run Velociraptor in a container,
    making deployment fast and consistent across environments.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the Docker deployer.

        Args:
            storage_path: Path for storing deployment data

        Raises:
            ImportError: If docker package is not installed
        """
        if not HAS_DOCKER:
            raise ImportError(
                "docker package required for Docker deployment. "
                "Install with: pip install docker"
            )

        super().__init__(storage_path)
        self._client: Optional[docker.DockerClient] = None

    @property
    def target_type(self) -> DeploymentTarget:
        """Return the deployment target type."""
        return DeploymentTarget.DOCKER

    @property
    def client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def _container_name(self, deployment_id: str) -> str:
        """Get the container name for a deployment."""
        return f"velociraptor-{deployment_id}"

    async def deploy(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
    ) -> DeploymentResult:
        """Deploy Velociraptor server using Docker.

        Args:
            config: Deployment configuration
            profile: Deployment profile
            certificates: Certificate bundle

        Returns:
            DeploymentResult with deployment details
        """
        deployment_id = config.deployment_id
        container_name = self._container_name(deployment_id)

        try:
            # Check Docker is available
            self.client.ping()
        except DockerException as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Docker connection failed",
                error=str(e),
            )

        # Create deployment directory
        deployment_dir = self.storage_path / deployment_id
        deployment_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Pull the image
            await asyncio.to_thread(
                self.client.images.pull, VELOCIRAPTOR_IMAGE
            )

            # Generate admin password
            admin_password = generate_password(24)

            # Save certificates
            certs_dir = deployment_dir / "certs"
            certs_dir.mkdir(exist_ok=True)
            (certs_dir / "ca.crt").write_text(certificates.ca_cert)
            (certs_dir / "server.crt").write_text(certificates.server_cert)
            (certs_dir / "server.key").write_text(certificates.server_key)

            # Generate server configuration
            server_config = self._generate_server_config(config, certificates)
            config_file = deployment_dir / "server.config.yaml"
            config_file.write_text(server_config)

            # Create data directories
            data_dir = deployment_dir / "data"
            data_dir.mkdir(exist_ok=True)
            logs_dir = deployment_dir / "logs"
            logs_dir.mkdir(exist_ok=True)

            # Volume mounts
            volumes = {
                str(config_file.absolute()): {
                    "bind": "/etc/velociraptor/server.config.yaml",
                    "mode": "ro",
                },
                str(certs_dir.absolute()): {
                    "bind": "/etc/velociraptor/certs",
                    "mode": "ro",
                },
                str(data_dir.absolute()): {
                    "bind": "/opt/velociraptor/data",
                    "mode": "rw",
                },
                str(logs_dir.absolute()): {
                    "bind": "/opt/velociraptor/logs",
                    "mode": "rw",
                },
            }

            # Port mappings
            ports = {
                f"{config.gui_port}/tcp": config.gui_port,
                f"{config.frontend_port}/tcp": config.frontend_port,
            }

            # Resource limits from profile
            mem_limit = profile.resource_limits.get("memory", "4g")
            cpu_count = int(profile.resource_limits.get("cpus", "2"))

            # Create and start container
            container = await asyncio.to_thread(
                self.client.containers.run,
                VELOCIRAPTOR_IMAGE,
                command=["frontend", "-c", "/etc/velociraptor/server.config.yaml"],
                name=container_name,
                detach=True,
                ports=ports,
                volumes=volumes,
                mem_limit=mem_limit,
                cpu_count=cpu_count,
                restart_policy={"Name": "unless-stopped"},
                labels={
                    "megaraptor.deployment_id": deployment_id,
                    "megaraptor.profile": profile.name,
                },
            )

            # Calculate auto-destroy time
            auto_destroy_at = None
            if profile.auto_destroy_hours:
                destroy_time = datetime.now(timezone.utc) + timedelta(
                    hours=profile.auto_destroy_hours
                )
                auto_destroy_at = destroy_time.isoformat()

            # Create deployment info
            server_url = f"https://{config.server_hostname}:{config.gui_port}"
            api_url = f"https://{config.server_hostname}:{config.gui_port}/api/"

            info = DeploymentInfo(
                deployment_id=deployment_id,
                profile=profile.name,
                target=self.target_type.value,
                state=DeploymentState.RUNNING,
                server_url=server_url,
                api_url=api_url,
                created_at=self._now_iso(),
                auto_destroy_at=auto_destroy_at,
                metadata={
                    "container_id": container.id[:12],
                    "container_name": container_name,
                    "image": VELOCIRAPTOR_IMAGE,
                    "admin_username": config.admin_username,
                },
            )
            self.save_deployment_info(info)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message=f"Velociraptor server deployed successfully",
                server_url=server_url,
                api_url=api_url,
                admin_password=admin_password,
                details={
                    "container_id": container.id[:12],
                    "container_name": container_name,
                    "gui_port": config.gui_port,
                    "frontend_port": config.frontend_port,
                    "profile": profile.name,
                    "auto_destroy_at": auto_destroy_at,
                    "ca_fingerprint": certificates.ca_fingerprint,
                },
            )

        except Exception as e:
            # Cleanup on failure
            try:
                container = self.client.containers.get(container_name)
                container.remove(force=True)
            except Exception:
                pass

            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Deployment failed",
                error=str(e),
            )

    def _generate_server_config(self, config: Any, certificates: Any) -> str:
        """Generate Velociraptor server configuration.

        Args:
            config: Deployment configuration
            certificates: Certificate bundle

        Returns:
            YAML configuration string
        """
        import yaml

        server_config = {
            "version": {
                "name": "megaraptor-deployment",
            },
            "Client": {
                "server_urls": [f"https://{config.server_hostname}:{config.frontend_port}/"],
                "ca_certificate": certificates.ca_cert,
                "nonce": os.urandom(8).hex(),
            },
            "API": {
                "hostname": config.server_hostname,
                "bind_address": f"{config.bind_address}:{config.gui_port}",
                "bind_scheme": "https",
            },
            "GUI": {
                "bind_address": f"{config.bind_address}:{config.gui_port}",
                "bind_scheme": "https",
                "public_url": f"https://{config.server_hostname}:{config.gui_port}/",
                "initial_users": [
                    {
                        "name": config.admin_username,
                        "password_hash": "",  # Will be set by Velociraptor
                    }
                ],
            },
            "Frontend": {
                "hostname": config.server_hostname,
                "bind_address": f"{config.bind_address}:{config.frontend_port}",
                "certificate": certificates.server_cert,
                "private_key": certificates.server_key,
            },
            "Datastore": {
                "implementation": "FileBaseDataStore",
                "location": config.data_path,
            },
            "Logging": {
                "output_directory": config.log_path,
                "separate_logs_per_component": True,
            },
            "ca_certificate": certificates.ca_cert,
            "frontend_certificate": certificates.server_cert,
            "frontend_private_key": certificates.server_key,
        }

        return yaml.dump(server_config, default_flow_style=False)

    async def destroy(self, deployment_id: str, force: bool = False) -> DeploymentResult:
        """Destroy a Docker deployment.

        Args:
            deployment_id: The deployment to destroy
            force: Force destruction

        Returns:
            DeploymentResult indicating success/failure
        """
        container_name = self._container_name(deployment_id)

        try:
            container = self.client.containers.get(container_name)

            # Stop and remove container
            await asyncio.to_thread(container.stop, timeout=30)
            await asyncio.to_thread(container.remove, v=True)

            # Update state
            info = self.load_deployment_info(deployment_id)
            if info:
                info.state = DeploymentState.DESTROYED
                self.save_deployment_info(info)

            # Optionally clean up deployment directory
            if force:
                self.delete_deployment_info(deployment_id)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message="Deployment destroyed successfully",
            )

        except NotFound:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Container not found",
                error=f"Container {container_name} does not exist",
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Failed to destroy deployment",
                error=str(e),
            )

    async def get_status(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get the status of a Docker deployment.

        Args:
            deployment_id: The deployment identifier

        Returns:
            DeploymentInfo, or None if not found
        """
        info = self.load_deployment_info(deployment_id)
        if not info:
            return None

        container_name = self._container_name(deployment_id)

        try:
            container = self.client.containers.get(container_name)
            status = container.status

            # Map Docker status to deployment state
            state_map = {
                "running": DeploymentState.RUNNING,
                "exited": DeploymentState.STOPPED,
                "paused": DeploymentState.STOPPED,
                "restarting": DeploymentState.PROVISIONING,
                "dead": DeploymentState.FAILED,
            }
            info.state = state_map.get(status, DeploymentState.FAILED)

            # Get health check results
            health = await self.health_check(deployment_id)
            info.health = health

        except NotFound:
            info.state = DeploymentState.DESTROYED

        return info

    async def health_check(self, deployment_id: str) -> dict[str, Any]:
        """Perform a health check on a Docker deployment.

        Args:
            deployment_id: The deployment identifier

        Returns:
            Dictionary with health status
        """
        container_name = self._container_name(deployment_id)
        health = {
            "healthy": False,
            "container_running": False,
            "api_responsive": False,
            "checks": [],
        }

        # Check container status
        try:
            container = self.client.containers.get(container_name)
            health["container_running"] = container.status == "running"
            health["checks"].append({
                "name": "container_status",
                "status": "pass" if health["container_running"] else "fail",
                "message": f"Container status: {container.status}",
            })
        except NotFound:
            health["checks"].append({
                "name": "container_status",
                "status": "fail",
                "message": "Container not found",
            })
            return health

        # Check API responsiveness
        if health["container_running"] and HAS_HTTPX:
            info = self.load_deployment_info(deployment_id)
            if info and info.api_url:
                try:
                    async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                        response = await client.get(info.api_url)
                        health["api_responsive"] = response.status_code < 500
                        health["checks"].append({
                            "name": "api_health",
                            "status": "pass" if health["api_responsive"] else "warn",
                            "message": f"API responded with status {response.status_code}",
                        })
                except Exception as e:
                    health["checks"].append({
                        "name": "api_health",
                        "status": "fail",
                        "message": f"API check failed: {str(e)}",
                    })

        health["healthy"] = health["container_running"]
        return health

    async def get_logs(
        self,
        deployment_id: str,
        tail: int = 100,
        since: Optional[datetime] = None,
    ) -> Optional[str]:
        """Get container logs.

        Args:
            deployment_id: The deployment identifier
            tail: Number of lines to return
            since: Only return logs since this time

        Returns:
            Log output string, or None if not found
        """
        container_name = self._container_name(deployment_id)

        try:
            container = self.client.containers.get(container_name)
            logs = await asyncio.to_thread(
                container.logs,
                tail=tail,
                since=since,
                timestamps=True,
            )
            return logs.decode("utf-8")
        except NotFound:
            return None

    async def restart(self, deployment_id: str) -> DeploymentResult:
        """Restart a deployment.

        Args:
            deployment_id: The deployment identifier

        Returns:
            DeploymentResult indicating success/failure
        """
        container_name = self._container_name(deployment_id)

        try:
            container = self.client.containers.get(container_name)
            await asyncio.to_thread(container.restart, timeout=30)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message="Deployment restarted successfully",
            )

        except NotFound:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Container not found",
                error=f"Container {container_name} does not exist",
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Failed to restart deployment",
                error=str(e),
            )
