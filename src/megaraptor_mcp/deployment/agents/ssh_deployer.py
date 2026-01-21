"""
SSH-based agent deployment.

Pushes Velociraptor agents to Linux/macOS systems via SSH.
"""

import asyncio
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

try:
    import paramiko
    from paramiko.ssh_exception import SSHException, AuthenticationException
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


@dataclass
class SSHCredentials:
    """SSH connection credentials.

    Attributes:
        username: SSH username
        password: SSH password (if not using key)
        key_path: Path to SSH private key
        key_passphrase: Passphrase for encrypted key
        port: SSH port (default 22)
    """
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    key_passphrase: Optional[str] = None
    port: int = 22


@dataclass
class DeploymentTarget:
    """A target for agent deployment.

    Attributes:
        hostname: Target hostname or IP
        credentials: SSH credentials (uses default if None)
        target_os: Target OS (linux or macos)
    """
    hostname: str
    credentials: Optional[SSHCredentials] = None
    target_os: str = "linux"


@dataclass
class DeploymentResult:
    """Result of a single deployment.

    Attributes:
        hostname: Target hostname
        success: Whether deployment succeeded
        message: Status message
        error: Error message if failed
        enrolled: Whether agent enrolled with server
        client_id: Velociraptor client ID if enrolled
    """
    hostname: str
    success: bool
    message: str
    error: Optional[str] = None
    enrolled: bool = False
    client_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hostname": self.hostname,
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "enrolled": self.enrolled,
            "client_id": self.client_id,
        }


class SSHDeployer:
    """Deploys Velociraptor agents via SSH.

    This deployer pushes agent binaries and configuration to Linux
    and macOS systems using SSH.
    """

    BINARY_URLS = {
        "linux_amd64": "https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-linux-amd64",
        "linux_arm64": "https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-linux-arm64",
        "darwin_amd64": "https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-darwin-amd64",
        "darwin_arm64": "https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-darwin-arm64",
    }

    def __init__(self, default_credentials: Optional[SSHCredentials] = None):
        """Initialize the SSH deployer.

        Args:
            default_credentials: Default credentials for targets

        Raises:
            ImportError: If paramiko is not installed
        """
        if not HAS_PARAMIKO:
            raise ImportError(
                "paramiko package required for SSH deployment. "
                "Install with: pip install paramiko"
            )

        self.default_credentials = default_credentials

    def _get_client(self, target: DeploymentTarget) -> paramiko.SSHClient:
        """Create an SSH client for a target.

        Args:
            target: Deployment target

        Returns:
            Connected SSH client
        """
        creds = target.credentials or self.default_credentials
        if not creds:
            raise ValueError(f"No credentials provided for {target.hostname}")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": target.hostname,
            "port": creds.port,
            "username": creds.username,
        }

        if creds.key_path:
            connect_kwargs["key_filename"] = creds.key_path
            if creds.key_passphrase:
                connect_kwargs["passphrase"] = creds.key_passphrase
        elif creds.password:
            connect_kwargs["password"] = creds.password
        else:
            raise ValueError("Must provide either key_path or password")

        client.connect(**connect_kwargs)
        return client

    async def _detect_architecture(self, client: paramiko.SSHClient) -> str:
        """Detect the target architecture.

        Args:
            client: Connected SSH client

        Returns:
            Architecture string (amd64 or arm64)
        """
        _, stdout, _ = await asyncio.to_thread(
            client.exec_command, "uname -m"
        )
        arch = (await asyncio.to_thread(stdout.read)).decode().strip()

        arch_map = {
            "x86_64": "amd64",
            "amd64": "amd64",
            "aarch64": "arm64",
            "arm64": "arm64",
        }
        return arch_map.get(arch, "amd64")

    async def deploy_agent(
        self,
        target: DeploymentTarget,
        client_config: str,
        binary_url: Optional[str] = None,
        labels: list[str] = None,
    ) -> DeploymentResult:
        """Deploy Velociraptor agent to a single target.

        Args:
            target: Deployment target
            client_config: Client configuration YAML
            binary_url: URL to download binary (auto-detected if None)
            labels: Labels to apply to the client

        Returns:
            Deployment result
        """
        labels = labels or []
        client = None

        try:
            client = await asyncio.to_thread(self._get_client, target)

            # Detect architecture
            arch = await self._detect_architecture(client)

            # Determine binary URL
            os_name = "darwin" if target.target_os == "macos" else "linux"
            binary_key = f"{os_name}_{arch}"
            url = binary_url or self.BINARY_URLS.get(binary_key)
            if not url:
                return DeploymentResult(
                    hostname=target.hostname,
                    success=False,
                    message=f"No binary available for {binary_key}",
                )

            # Create directories
            commands = [
                "sudo mkdir -p /etc/velociraptor",
                "sudo mkdir -p /opt/velociraptor",
            ]
            for cmd in commands:
                _, stdout, stderr = await asyncio.to_thread(
                    client.exec_command, cmd
                )
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error = (await asyncio.to_thread(stderr.read)).decode()
                    return DeploymentResult(
                        hostname=target.hostname,
                        success=False,
                        message="Failed to create directories",
                        error=error,
                    )

            # Write configuration
            sftp = await asyncio.to_thread(client.open_sftp)
            try:
                # Write to temp file first, then move with sudo
                temp_config = f"/tmp/velociraptor_config_{id(target)}.yaml"
                with sftp.file(temp_config, "w") as f:
                    f.write(client_config)

                _, stdout, stderr = await asyncio.to_thread(
                    client.exec_command,
                    f"sudo mv {temp_config} /etc/velociraptor/client.config.yaml && sudo chmod 600 /etc/velociraptor/client.config.yaml"
                )
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error = (await asyncio.to_thread(stderr.read)).decode()
                    return DeploymentResult(
                        hostname=target.hostname,
                        success=False,
                        message="Failed to write configuration",
                        error=error,
                    )
            finally:
                await asyncio.to_thread(sftp.close)

            # Download binary
            download_cmd = f"sudo curl -L -o /usr/local/bin/velociraptor '{url}' && sudo chmod +x /usr/local/bin/velociraptor"
            _, stdout, stderr = await asyncio.to_thread(
                client.exec_command, download_cmd
            )
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                # Try wget as fallback
                download_cmd = f"sudo wget -O /usr/local/bin/velociraptor '{url}' && sudo chmod +x /usr/local/bin/velociraptor"
                _, stdout, stderr = await asyncio.to_thread(
                    client.exec_command, download_cmd
                )
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error = (await asyncio.to_thread(stderr.read)).decode()
                    return DeploymentResult(
                        hostname=target.hostname,
                        success=False,
                        message="Failed to download binary",
                        error=error,
                    )

            # Create and enable service based on OS
            if target.target_os == "macos":
                result = await self._setup_macos_service(client)
            else:
                result = await self._setup_linux_service(client)

            if not result["success"]:
                return DeploymentResult(
                    hostname=target.hostname,
                    success=False,
                    message="Failed to setup service",
                    error=result.get("error", "Unknown error"),
                )

            return DeploymentResult(
                hostname=target.hostname,
                success=True,
                message="Agent deployed and service started",
                enrolled=False,  # Would need to verify with server
            )

        except AuthenticationException as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="SSH authentication failed",
                error=str(e),
            )

        except SSHException as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="SSH connection error",
                error=str(e),
            )

        except Exception as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="Deployment failed",
                error=str(e),
            )

        finally:
            if client:
                await asyncio.to_thread(client.close)

    async def _setup_linux_service(self, client: paramiko.SSHClient) -> dict:
        """Setup systemd service on Linux.

        Args:
            client: Connected SSH client

        Returns:
            Result dictionary
        """
        service_content = """[Unit]
Description=Velociraptor Agent
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/velociraptor client -c /etc/velociraptor/client.config.yaml
Restart=always
RestartSec=10
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""
        # Write service file
        sftp = await asyncio.to_thread(client.open_sftp)
        try:
            temp_service = f"/tmp/velociraptor.service"
            with sftp.file(temp_service, "w") as f:
                f.write(service_content)

            commands = [
                f"sudo mv {temp_service} /etc/systemd/system/velociraptor.service",
                "sudo systemctl daemon-reload",
                "sudo systemctl enable velociraptor",
                "sudo systemctl start velociraptor",
            ]

            for cmd in commands:
                _, stdout, stderr = await asyncio.to_thread(
                    client.exec_command, cmd
                )
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error = (await asyncio.to_thread(stderr.read)).decode()
                    return {"success": False, "error": error}

            return {"success": True}

        finally:
            await asyncio.to_thread(sftp.close)

    async def _setup_macos_service(self, client: paramiko.SSHClient) -> dict:
        """Setup launchd service on macOS.

        Args:
            client: Connected SSH client

        Returns:
            Result dictionary
        """
        plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.velocidex.velociraptor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/velociraptor</string>
        <string>client</string>
        <string>-c</string>
        <string>/etc/velociraptor/client.config.yaml</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
        sftp = await asyncio.to_thread(client.open_sftp)
        try:
            temp_plist = "/tmp/com.velocidex.velociraptor.plist"
            with sftp.file(temp_plist, "w") as f:
                f.write(plist_content)

            commands = [
                f"sudo mv {temp_plist} /Library/LaunchDaemons/com.velocidex.velociraptor.plist",
                "sudo launchctl load /Library/LaunchDaemons/com.velocidex.velociraptor.plist",
            ]

            for cmd in commands:
                _, stdout, stderr = await asyncio.to_thread(
                    client.exec_command, cmd
                )
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error = (await asyncio.to_thread(stderr.read)).decode()
                    return {"success": False, "error": error}

            return {"success": True}

        finally:
            await asyncio.to_thread(sftp.close)

    async def deploy_to_multiple(
        self,
        targets: list[DeploymentTarget],
        client_config: str,
        binary_url: Optional[str] = None,
        labels: list[str] = None,
        concurrency: int = 10,
    ) -> list[DeploymentResult]:
        """Deploy agent to multiple targets concurrently.

        Args:
            targets: List of deployment targets
            client_config: Client configuration YAML
            binary_url: URL to download binary
            labels: Labels to apply to clients
            concurrency: Maximum concurrent deployments

        Returns:
            List of deployment results
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def deploy_with_semaphore(target: DeploymentTarget) -> DeploymentResult:
            async with semaphore:
                return await self.deploy_agent(target, client_config, binary_url, labels)

        tasks = [deploy_with_semaphore(target) for target in targets]
        return await asyncio.gather(*tasks)

    async def check_agent_status(self, target: DeploymentTarget) -> dict[str, Any]:
        """Check the status of an agent on a target.

        Args:
            target: Deployment target

        Returns:
            Status information
        """
        client = None
        try:
            client = await asyncio.to_thread(self._get_client, target)

            status = {"hostname": target.hostname, "reachable": True}

            # Check binary exists
            _, stdout, _ = await asyncio.to_thread(
                client.exec_command, "test -f /usr/local/bin/velociraptor && echo yes || echo no"
            )
            status["binary_exists"] = (await asyncio.to_thread(stdout.read)).decode().strip() == "yes"

            # Check config exists
            _, stdout, _ = await asyncio.to_thread(
                client.exec_command, "test -f /etc/velociraptor/client.config.yaml && echo yes || echo no"
            )
            status["config_exists"] = (await asyncio.to_thread(stdout.read)).decode().strip() == "yes"

            # Check service status
            if target.target_os == "macos":
                _, stdout, _ = await asyncio.to_thread(
                    client.exec_command, "sudo launchctl list | grep velociraptor || true"
                )
                output = (await asyncio.to_thread(stdout.read)).decode().strip()
                status["service_running"] = "velociraptor" in output
            else:
                _, stdout, _ = await asyncio.to_thread(
                    client.exec_command, "systemctl is-active velociraptor || true"
                )
                output = (await asyncio.to_thread(stdout.read)).decode().strip()
                status["service_running"] = output == "active"

            # Get version
            if status["binary_exists"]:
                _, stdout, _ = await asyncio.to_thread(
                    client.exec_command, "/usr/local/bin/velociraptor --version 2>&1 || true"
                )
                status["version"] = (await asyncio.to_thread(stdout.read)).decode().strip()

            return status

        except Exception as e:
            return {
                "hostname": target.hostname,
                "reachable": False,
                "error": str(e),
            }

        finally:
            if client:
                await asyncio.to_thread(client.close)

    async def uninstall_agent(self, target: DeploymentTarget) -> DeploymentResult:
        """Uninstall Velociraptor agent from a target.

        Args:
            target: Deployment target

        Returns:
            Deployment result
        """
        client = None
        try:
            client = await asyncio.to_thread(self._get_client, target)

            if target.target_os == "macos":
                commands = [
                    "sudo launchctl unload /Library/LaunchDaemons/com.velocidex.velociraptor.plist 2>/dev/null || true",
                    "sudo rm -f /Library/LaunchDaemons/com.velocidex.velociraptor.plist",
                    "sudo rm -f /usr/local/bin/velociraptor",
                    "sudo rm -rf /etc/velociraptor",
                ]
            else:
                commands = [
                    "sudo systemctl stop velociraptor 2>/dev/null || true",
                    "sudo systemctl disable velociraptor 2>/dev/null || true",
                    "sudo rm -f /etc/systemd/system/velociraptor.service",
                    "sudo systemctl daemon-reload",
                    "sudo rm -f /usr/local/bin/velociraptor",
                    "sudo rm -rf /etc/velociraptor",
                ]

            for cmd in commands:
                _, stdout, stderr = await asyncio.to_thread(
                    client.exec_command, cmd
                )
                await asyncio.to_thread(stdout.channel.recv_exit_status)

            return DeploymentResult(
                hostname=target.hostname,
                success=True,
                message="Agent uninstalled successfully",
            )

        except Exception as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="Uninstall failed",
                error=str(e),
            )

        finally:
            if client:
                await asyncio.to_thread(client.close)
