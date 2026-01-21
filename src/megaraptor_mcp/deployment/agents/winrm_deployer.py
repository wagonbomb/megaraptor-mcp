"""
WinRM-based agent deployment.

Pushes Velociraptor agents to Windows systems via WinRM.
"""

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any

try:
    import winrm
    from winrm.exceptions import WinRMTransportError, WinRMOperationTimeoutError
    HAS_WINRM = True
except ImportError:
    HAS_WINRM = False


@dataclass
class WinRMCredentials:
    """WinRM connection credentials.

    Attributes:
        username: Windows username (DOMAIN\\user or user@domain)
        password: Windows password
        use_ssl: Use HTTPS (default True)
        verify_ssl: Verify SSL certificate (default False for self-signed)
        transport: Transport method (ntlm, kerberos, basic)
    """
    username: str
    password: str
    use_ssl: bool = True
    verify_ssl: bool = False
    transport: str = "ntlm"


@dataclass
class DeploymentTarget:
    """A target for agent deployment.

    Attributes:
        hostname: Target hostname or IP
        port: WinRM port (5986 for HTTPS, 5985 for HTTP)
        credentials: WinRM credentials (uses default if None)
    """
    hostname: str
    port: int = 5986
    credentials: Optional[WinRMCredentials] = None


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


class WinRMDeployer:
    """Deploys Velociraptor agents via WinRM.

    This deployer pushes agent installers and configuration to Windows
    systems using WinRM (Windows Remote Management).
    """

    def __init__(self, default_credentials: Optional[WinRMCredentials] = None):
        """Initialize the WinRM deployer.

        Args:
            default_credentials: Default credentials for targets

        Raises:
            ImportError: If pywinrm is not installed
        """
        if not HAS_WINRM:
            raise ImportError(
                "pywinrm package required for WinRM deployment. "
                "Install with: pip install pywinrm"
            )

        self.default_credentials = default_credentials

    def _get_session(self, target: DeploymentTarget) -> winrm.Session:
        """Create a WinRM session for a target.

        Args:
            target: Deployment target

        Returns:
            WinRM session
        """
        creds = target.credentials or self.default_credentials
        if not creds:
            raise ValueError(f"No credentials provided for {target.hostname}")

        scheme = "https" if creds.use_ssl else "http"
        endpoint = f"{scheme}://{target.hostname}:{target.port}/wsman"

        return winrm.Session(
            endpoint,
            auth=(creds.username, creds.password),
            transport=creds.transport,
            server_cert_validation="ignore" if not creds.verify_ssl else "validate",
        )

    async def deploy_agent(
        self,
        target: DeploymentTarget,
        client_config: str,
        installer_url: Optional[str] = None,
        labels: list[str] = None,
    ) -> DeploymentResult:
        """Deploy Velociraptor agent to a single target.

        Args:
            target: Deployment target
            client_config: Client configuration YAML
            installer_url: URL to download installer (uses default if None)
            labels: Labels to apply to the client

        Returns:
            Deployment result
        """
        labels = labels or []

        try:
            session = self._get_session(target)

            # Test connectivity
            result = await asyncio.to_thread(
                session.run_ps, "Write-Output 'Connection test'"
            )
            if result.status_code != 0:
                return DeploymentResult(
                    hostname=target.hostname,
                    success=False,
                    message="WinRM connection test failed",
                    error=result.std_err.decode(),
                )

            # Create installation directory
            await asyncio.to_thread(
                session.run_ps,
                'New-Item -ItemType Directory -Path "C:\\Program Files\\Velociraptor" -Force'
            )

            # Write client configuration
            config_b64 = base64.b64encode(client_config.encode()).decode()
            write_config_script = f'''
$configContent = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{config_b64}"))
Set-Content -Path "C:\\Program Files\\Velociraptor\\client.config.yaml" -Value $configContent -Force
'''
            result = await asyncio.to_thread(session.run_ps, write_config_script)
            if result.status_code != 0:
                return DeploymentResult(
                    hostname=target.hostname,
                    success=False,
                    message="Failed to write configuration",
                    error=result.std_err.decode(),
                )

            # Download installer if not present
            download_url = installer_url or "https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-windows-amd64.msi"
            download_script = f'''
$installerPath = "C:\\Program Files\\Velociraptor\\velociraptor.msi"
if (-not (Test-Path $installerPath)) {{
    Invoke-WebRequest -Uri "{download_url}" -OutFile $installerPath
}}
'''
            result = await asyncio.to_thread(session.run_ps, download_script)
            if result.status_code != 0:
                return DeploymentResult(
                    hostname=target.hostname,
                    success=False,
                    message="Failed to download installer",
                    error=result.std_err.decode(),
                )

            # Install the agent
            install_script = '''
$installerPath = "C:\\Program Files\\Velociraptor\\velociraptor.msi"
Start-Process msiexec.exe -ArgumentList "/i", $installerPath, "/qn", "/norestart" -Wait -NoNewWindow
'''
            result = await asyncio.to_thread(session.run_ps, install_script)
            if result.status_code != 0:
                return DeploymentResult(
                    hostname=target.hostname,
                    success=False,
                    message="Failed to install agent",
                    error=result.std_err.decode(),
                )

            # Configure and start service
            service_script = '''
# Stop service if running
Stop-Service -Name Velociraptor -ErrorAction SilentlyContinue

# Copy configuration
Copy-Item "C:\\Program Files\\Velociraptor\\client.config.yaml" "C:\\Program Files\\Velociraptor\\Velociraptor.config.yaml" -Force

# Start service
Start-Service -Name Velociraptor
Get-Service -Name Velociraptor | Select-Object Status
'''
            result = await asyncio.to_thread(session.run_ps, service_script)

            return DeploymentResult(
                hostname=target.hostname,
                success=True,
                message="Agent deployed and service started",
                enrolled=False,  # Would need to verify with server
            )

        except WinRMTransportError as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="WinRM transport error",
                error=str(e),
            )

        except WinRMOperationTimeoutError as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="WinRM operation timeout",
                error=str(e),
            )

        except Exception as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="Deployment failed",
                error=str(e),
            )

    async def deploy_to_multiple(
        self,
        targets: list[DeploymentTarget],
        client_config: str,
        installer_url: Optional[str] = None,
        labels: list[str] = None,
        concurrency: int = 5,
    ) -> list[DeploymentResult]:
        """Deploy agent to multiple targets concurrently.

        Args:
            targets: List of deployment targets
            client_config: Client configuration YAML
            installer_url: URL to download installer
            labels: Labels to apply to clients
            concurrency: Maximum concurrent deployments

        Returns:
            List of deployment results
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def deploy_with_semaphore(target: DeploymentTarget) -> DeploymentResult:
            async with semaphore:
                return await self.deploy_agent(target, client_config, installer_url, labels)

        tasks = [deploy_with_semaphore(target) for target in targets]
        return await asyncio.gather(*tasks)

    async def check_agent_status(self, target: DeploymentTarget) -> dict[str, Any]:
        """Check the status of an agent on a target.

        Args:
            target: Deployment target

        Returns:
            Status information
        """
        try:
            session = self._get_session(target)

            status_script = '''
$status = @{}

# Check service status
$service = Get-Service -Name Velociraptor -ErrorAction SilentlyContinue
if ($service) {
    $status.service_exists = $true
    $status.service_status = $service.Status.ToString()
    $status.service_start_type = $service.StartType.ToString()
} else {
    $status.service_exists = $false
}

# Check binary exists
$status.binary_exists = Test-Path "C:\\Program Files\\Velociraptor\\velociraptor.exe"

# Check config exists
$status.config_exists = Test-Path "C:\\Program Files\\Velociraptor\\Velociraptor.config.yaml"

# Get version if binary exists
if ($status.binary_exists) {
    $version = & "C:\\Program Files\\Velociraptor\\velociraptor.exe" --version 2>&1
    $status.version = $version
}

$status | ConvertTo-Json
'''
            result = await asyncio.to_thread(session.run_ps, status_script)

            if result.status_code == 0:
                import json
                status = json.loads(result.std_out.decode())
                status["hostname"] = target.hostname
                status["reachable"] = True
                return status

            return {
                "hostname": target.hostname,
                "reachable": True,
                "error": result.std_err.decode(),
            }

        except Exception as e:
            return {
                "hostname": target.hostname,
                "reachable": False,
                "error": str(e),
            }

    async def uninstall_agent(self, target: DeploymentTarget) -> DeploymentResult:
        """Uninstall Velociraptor agent from a target.

        Args:
            target: Deployment target

        Returns:
            Deployment result
        """
        try:
            session = self._get_session(target)

            uninstall_script = '''
# Stop service
Stop-Service -Name Velociraptor -Force -ErrorAction SilentlyContinue

# Uninstall MSI
$product = Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like "*Velociraptor*" }
if ($product) {
    $product.Uninstall()
}

# Remove directory
Remove-Item -Path "C:\\Program Files\\Velociraptor" -Recurse -Force -ErrorAction SilentlyContinue

Write-Output "Uninstall complete"
'''
            result = await asyncio.to_thread(session.run_ps, uninstall_script)

            if result.status_code == 0:
                return DeploymentResult(
                    hostname=target.hostname,
                    success=True,
                    message="Agent uninstalled successfully",
                )

            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="Failed to uninstall agent",
                error=result.std_err.decode(),
            )

        except Exception as e:
            return DeploymentResult(
                hostname=target.hostname,
                success=False,
                message="Uninstall failed",
                error=str(e),
            )
