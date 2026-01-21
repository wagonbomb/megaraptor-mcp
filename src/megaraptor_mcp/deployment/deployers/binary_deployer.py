"""
Binary-based Velociraptor server deployment.

Deploys Velociraptor as a standalone binary on a target system via SSH.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Any

from .base import BaseDeployer, DeploymentResult, DeploymentInfo
from ..profiles import DeploymentProfile, DeploymentState, DeploymentTarget
from ..security.credential_store import generate_password

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


# Velociraptor binary download URLs
VELOCIRAPTOR_RELEASES_URL = "https://github.com/Velocidex/velociraptor/releases/latest/download"
VELOCIRAPTOR_BINARIES = {
    "linux_amd64": "velociraptor-v{version}-linux-amd64",
    "linux_arm64": "velociraptor-v{version}-linux-arm64",
    "darwin_amd64": "velociraptor-v{version}-darwin-amd64",
    "darwin_arm64": "velociraptor-v{version}-darwin-arm64",
}


class BinaryDeployer(BaseDeployer):
    """Deploy Velociraptor servers as standalone binaries.

    This deployer SSHs into target hosts and deploys Velociraptor
    as a standalone binary with systemd service management.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the binary deployer.

        Args:
            storage_path: Path for storing deployment data

        Raises:
            ImportError: If paramiko package is not installed
        """
        if not HAS_PARAMIKO:
            raise ImportError(
                "paramiko package required for binary deployment. "
                "Install with: pip install paramiko"
            )

        super().__init__(storage_path)

    @property
    def target_type(self) -> DeploymentTarget:
        """Return the deployment target type."""
        return DeploymentTarget.BINARY

    async def deploy(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
        target_host: str,
        ssh_user: str = "root",
        ssh_key_path: Optional[str] = None,
        ssh_password: Optional[str] = None,
        velociraptor_version: str = "latest",
    ) -> DeploymentResult:
        """Deploy Velociraptor server as a binary via SSH.

        Args:
            config: Deployment configuration
            profile: Deployment profile
            certificates: Certificate bundle
            target_host: Target hostname or IP
            ssh_user: SSH username (default: root)
            ssh_key_path: Path to SSH private key
            ssh_password: SSH password (if not using key)
            velociraptor_version: Velociraptor version to deploy

        Returns:
            DeploymentResult with deployment details
        """
        deployment_id = config.deployment_id

        try:
            # Connect via SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": target_host,
                "username": ssh_user,
            }
            if ssh_key_path:
                connect_kwargs["key_filename"] = ssh_key_path
            elif ssh_password:
                connect_kwargs["password"] = ssh_password
            else:
                return DeploymentResult(
                    success=False,
                    deployment_id=deployment_id,
                    message="SSH authentication required",
                    error="Must provide either ssh_key_path or ssh_password",
                )

            await asyncio.to_thread(ssh.connect, **connect_kwargs)

            # Create deployment directory
            deployment_dir = self.storage_path / deployment_id
            deployment_dir.mkdir(parents=True, exist_ok=True)

            # Generate admin password
            admin_password = generate_password(24)

            # Detect target architecture
            _, stdout, _ = await asyncio.to_thread(
                ssh.exec_command, "uname -m"
            )
            arch = (await asyncio.to_thread(stdout.read)).decode().strip()
            arch_map = {
                "x86_64": "amd64",
                "aarch64": "arm64",
                "arm64": "arm64",
            }
            arch = arch_map.get(arch, "amd64")

            # Detect OS
            _, stdout, _ = await asyncio.to_thread(
                ssh.exec_command, "uname -s"
            )
            os_type = (await asyncio.to_thread(stdout.read)).decode().strip().lower()

            binary_key = f"{os_type}_{arch}"
            if binary_key not in VELOCIRAPTOR_BINARIES:
                return DeploymentResult(
                    success=False,
                    deployment_id=deployment_id,
                    message=f"Unsupported platform: {binary_key}",
                    error=f"No binary available for {os_type} {arch}",
                )

            # Create directories on target
            commands = [
                "mkdir -p /opt/velociraptor/{data,logs,config}",
                "mkdir -p /etc/velociraptor",
            ]
            for cmd in commands:
                await asyncio.to_thread(ssh.exec_command, cmd)

            # Generate and upload server configuration
            server_config = self._generate_server_config(config, certificates)
            config_file = deployment_dir / "server.config.yaml"
            config_file.write_text(server_config)

            sftp = await asyncio.to_thread(ssh.open_sftp)
            await asyncio.to_thread(
                sftp.put,
                str(config_file),
                "/etc/velociraptor/server.config.yaml",
            )

            # Upload certificates
            for name, content in [
                ("ca.crt", certificates.ca_cert),
                ("server.crt", certificates.server_cert),
                ("server.key", certificates.server_key),
            ]:
                local_path = deployment_dir / name
                local_path.write_text(content)
                await asyncio.to_thread(
                    sftp.put,
                    str(local_path),
                    f"/etc/velociraptor/{name}",
                )

            # Download and install Velociraptor binary
            download_url = f"{VELOCIRAPTOR_RELEASES_URL}/velociraptor-{velociraptor_version}-{os_type}-{arch}"
            install_commands = [
                f"curl -L -o /usr/local/bin/velociraptor '{download_url}' || wget -O /usr/local/bin/velociraptor '{download_url}'",
                "chmod +x /usr/local/bin/velociraptor",
            ]

            for cmd in install_commands:
                _, stdout, stderr = await asyncio.to_thread(ssh.exec_command, cmd)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error = (await asyncio.to_thread(stderr.read)).decode()
                    return DeploymentResult(
                        success=False,
                        deployment_id=deployment_id,
                        message="Failed to install Velociraptor binary",
                        error=error,
                    )

            # Create systemd service
            service_content = self._generate_systemd_service(config)
            service_file = deployment_dir / "velociraptor.service"
            service_file.write_text(service_content)
            await asyncio.to_thread(
                sftp.put,
                str(service_file),
                "/etc/systemd/system/velociraptor.service",
            )

            # Enable and start service
            service_commands = [
                "systemctl daemon-reload",
                "systemctl enable velociraptor",
                "systemctl start velociraptor",
            ]
            for cmd in service_commands:
                await asyncio.to_thread(ssh.exec_command, cmd)

            await asyncio.to_thread(sftp.close)
            await asyncio.to_thread(ssh.close)

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
                    "target_host": target_host,
                    "ssh_user": ssh_user,
                    "install_path": "/usr/local/bin/velociraptor",
                    "config_path": "/etc/velociraptor/server.config.yaml",
                    "admin_username": config.admin_username,
                },
            )
            self.save_deployment_info(info)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message="Velociraptor server deployed successfully",
                server_url=server_url,
                api_url=api_url,
                admin_password=admin_password,
                details={
                    "target_host": target_host,
                    "gui_port": config.gui_port,
                    "frontend_port": config.frontend_port,
                    "profile": profile.name,
                    "auto_destroy_at": auto_destroy_at,
                    "ca_fingerprint": certificates.ca_fingerprint,
                },
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Deployment failed",
                error=str(e),
            )

    def _generate_server_config(self, config: Any, certificates: Any) -> str:
        """Generate Velociraptor server configuration."""
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
            },
            "Frontend": {
                "hostname": config.server_hostname,
                "bind_address": f"{config.bind_address}:{config.frontend_port}",
                "certificate": "/etc/velociraptor/server.crt",
                "private_key": "/etc/velociraptor/server.key",
            },
            "Datastore": {
                "implementation": "FileBaseDataStore",
                "location": config.data_path,
            },
            "Logging": {
                "output_directory": config.log_path,
                "separate_logs_per_component": True,
            },
            "ca_certificate": "/etc/velociraptor/ca.crt",
        }

        return yaml.dump(server_config, default_flow_style=False)

    def _generate_systemd_service(self, config: Any) -> str:
        """Generate systemd service file."""
        return f"""[Unit]
Description=Velociraptor Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/velociraptor frontend -c /etc/velociraptor/server.config.yaml
Restart=always
RestartSec=10
User=root
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""

    async def destroy(self, deployment_id: str, force: bool = False) -> DeploymentResult:
        """Destroy a binary deployment.

        Args:
            deployment_id: The deployment to destroy
            force: Force destruction

        Returns:
            DeploymentResult indicating success/failure
        """
        info = self.load_deployment_info(deployment_id)
        if not info:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Deployment not found",
                error=f"No deployment with ID {deployment_id}",
            )

        target_host = info.metadata.get("target_host")
        ssh_user = info.metadata.get("ssh_user", "root")

        if not target_host:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Missing target host",
                error="Cannot destroy: target_host not in deployment metadata",
            )

        # Note: This requires SSH credentials to be provided
        # In a real implementation, you'd need to store or re-request credentials
        return DeploymentResult(
            success=False,
            deployment_id=deployment_id,
            message="Manual destruction required",
            error=f"SSH to {ssh_user}@{target_host} and run: systemctl stop velociraptor && rm -rf /opt/velociraptor /etc/velociraptor",
            details={
                "target_host": target_host,
                "ssh_user": ssh_user,
                "commands": [
                    "systemctl stop velociraptor",
                    "systemctl disable velociraptor",
                    "rm -f /etc/systemd/system/velociraptor.service",
                    "rm -f /usr/local/bin/velociraptor",
                    "rm -rf /opt/velociraptor",
                    "rm -rf /etc/velociraptor",
                    "systemctl daemon-reload",
                ],
            },
        )

    async def get_status(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get the status of a binary deployment.

        Args:
            deployment_id: The deployment identifier

        Returns:
            DeploymentInfo, or None if not found
        """
        info = self.load_deployment_info(deployment_id)
        if not info:
            return None

        # Note: Full status check would require SSH connection
        # For now, return stored info
        return info

    async def health_check(self, deployment_id: str) -> dict[str, Any]:
        """Perform a health check on a binary deployment.

        Args:
            deployment_id: The deployment identifier

        Returns:
            Dictionary with health status
        """
        info = self.load_deployment_info(deployment_id)
        health = {
            "healthy": False,
            "service_running": False,
            "api_responsive": False,
            "checks": [],
        }

        if not info:
            health["checks"].append({
                "name": "deployment_info",
                "status": "fail",
                "message": "Deployment info not found",
            })
            return health

        # Note: Full health check would require SSH connection
        # For now, just check API responsiveness
        try:
            import httpx

            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                response = await client.get(info.api_url)
                health["api_responsive"] = response.status_code < 500
                health["healthy"] = health["api_responsive"]
                health["checks"].append({
                    "name": "api_health",
                    "status": "pass" if health["api_responsive"] else "fail",
                    "message": f"API responded with status {response.status_code}",
                })
        except ImportError:
            health["checks"].append({
                "name": "api_health",
                "status": "skip",
                "message": "httpx not installed, cannot check API",
            })
        except Exception as e:
            health["checks"].append({
                "name": "api_health",
                "status": "fail",
                "message": f"API check failed: {str(e)}",
            })

        return health
