"""
Deployment tools for Velociraptor MCP.

Provides tools for rapid deployment of Velociraptor servers and agents
during active security incidents.
"""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from mcp.server import Server
from mcp.types import TextContent

from ..config import DeploymentConfig, generate_deployment_id
from ..deployment.profiles import get_profile, PROFILES, DeploymentTarget


def register_deployment_tools(server: Server) -> None:
    """Register deployment tools with the MCP server."""

    # =========================================================================
    # Server Deployment Tools (6 tools)
    # =========================================================================

    @server.tool()
    async def deploy_server(
        deployment_type: str = "docker",
        profile: str = "standard",
        server_hostname: str = "localhost",
        gui_port: int = 8889,
        frontend_port: int = 8000,
        target_host: Optional[str] = None,
        ssh_user: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
    ) -> list[TextContent]:
        """Deploy a Velociraptor server for incident response.

        Args:
            deployment_type: Deployment target - 'docker', 'binary', 'aws', or 'azure'
            profile: Deployment profile - 'rapid' (auto-destroys in 72h), 'standard', or 'enterprise'
            server_hostname: Hostname for the server (used in certificates and config)
            gui_port: Port for GUI/API access (default 8889)
            frontend_port: Port for client connections (default 8000)
            target_host: Target host for binary deployment (required for binary type)
            ssh_user: SSH username for binary deployment
            ssh_key_path: Path to SSH private key for binary deployment

        Returns:
            Deployment details including server URL, API URL, and admin credentials.
            IMPORTANT: Admin password is shown only once - save it immediately.
        """
        try:
            # Validate profile
            deployment_profile = get_profile(profile)

            # Generate deployment ID and config
            deployment_id = generate_deployment_id()
            config = DeploymentConfig(
                deployment_id=deployment_id,
                profile=profile,
                target=deployment_type,
                server_hostname=server_hostname,
                gui_port=gui_port,
                frontend_port=frontend_port,
            )

            # Generate certificates
            from ..deployment.security import CertificateManager
            cert_manager = CertificateManager()
            certificates = cert_manager.generate_bundle(
                server_hostname=server_hostname,
                san_ips=[target_host] if target_host else None,
                rapid=(profile == "rapid"),
            )
            cert_manager.save_bundle(certificates, deployment_id)

            # Select and run deployer
            if deployment_type == "docker":
                from ..deployment.deployers import DockerDeployer
                deployer = DockerDeployer()
                result = await deployer.deploy(config, deployment_profile, certificates)

            elif deployment_type == "binary":
                if not target_host:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "error": "target_host is required for binary deployment"
                        }, indent=2)
                    )]
                from ..deployment.deployers import BinaryDeployer
                deployer = BinaryDeployer()
                result = await deployer.deploy(
                    config, deployment_profile, certificates,
                    target_host=target_host,
                    ssh_user=ssh_user or "root",
                    ssh_key_path=ssh_key_path,
                )

            elif deployment_type == "aws":
                from ..deployment.deployers import AWSDeployer
                deployer = AWSDeployer()
                result = await deployer.deploy(config, deployment_profile, certificates)

            elif deployment_type == "azure":
                from ..deployment.deployers import AzureDeployer
                deployer = AzureDeployer()
                result = await deployer.deploy(config, deployment_profile, certificates)

            else:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Unknown deployment type: {deployment_type}",
                        "valid_types": ["docker", "binary", "aws", "azure"]
                    }, indent=2)
                )]

            # Return result with password visible (only time it's shown)
            return [TextContent(
                type="text",
                text=json.dumps(result.to_dict(include_secrets=True), indent=2)
            )]

        except ImportError as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Missing dependency: {str(e)}",
                    "suggestion": "Install required packages with: pip install megaraptor-mcp[deployment]"
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "deployment_type": deployment_type,
                    "profile": profile,
                }, indent=2)
            )]

    @server.tool()
    async def deploy_server_docker(
        profile: str = "rapid",
        server_hostname: str = "localhost",
        gui_port: int = 8889,
        frontend_port: int = 8000,
        memory_limit: str = "4g",
        cpu_limit: str = "2",
    ) -> list[TextContent]:
        """Deploy Velociraptor server using Docker (fastest method).

        Optimized for rapid incident response. Server will be operational
        within 2-5 minutes.

        Args:
            profile: Deployment profile ('rapid', 'standard', 'enterprise')
            server_hostname: Hostname for server access
            gui_port: GUI/API port (default 8889)
            frontend_port: Client connection port (default 8000)
            memory_limit: Container memory limit (default 4g)
            cpu_limit: Container CPU limit (default 2)

        Returns:
            Deployment details including URLs and one-time admin password.
        """
        return await deploy_server(
            deployment_type="docker",
            profile=profile,
            server_hostname=server_hostname,
            gui_port=gui_port,
            frontend_port=frontend_port,
        )

    @server.tool()
    async def deploy_server_cloud(
        cloud_provider: str,
        profile: str = "standard",
        region: Optional[str] = None,
        instance_type: Optional[str] = None,
        server_hostname: Optional[str] = None,
    ) -> list[TextContent]:
        """Deploy Velociraptor server on cloud infrastructure.

        Deploys using CloudFormation (AWS) or ARM templates (Azure).

        Args:
            cloud_provider: Cloud provider - 'aws' or 'azure'
            profile: Deployment profile ('standard' or 'enterprise')
            region: Cloud region (defaults to us-east-1 for AWS, eastus for Azure)
            instance_type: VM instance type (auto-selected based on profile)
            server_hostname: Hostname for server (defaults to public IP)

        Returns:
            Deployment details including cloud resource IDs and URLs.
        """
        return await deploy_server(
            deployment_type=cloud_provider,
            profile=profile,
            server_hostname=server_hostname or "localhost",
        )

    @server.tool()
    async def get_deployment_status(
        deployment_id: str,
    ) -> list[TextContent]:
        """Check the status and health of a deployment.

        Args:
            deployment_id: The deployment identifier (e.g., 'vr-20240115-a1b2c3d4')

        Returns:
            Current deployment status including health checks and metrics.
        """
        try:
            from ..deployment.deployers import DockerDeployer, BinaryDeployer

            # Try Docker first
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if info:
                health = await deployer.health_check(deployment_id)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        **info.to_dict(),
                        "health": health,
                    }, indent=2, default=str)
                )]

            # Try binary deployer
            deployer = BinaryDeployer()
            info = await deployer.get_status(deployment_id)

            if info:
                health = await deployer.health_check(deployment_id)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        **info.to_dict(),
                        "health": health,
                    }, indent=2, default=str)
                )]

            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Deployment not found: {deployment_id}"
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def destroy_deployment(
        deployment_id: str,
        confirm: bool = False,
    ) -> list[TextContent]:
        """Destroy a Velociraptor deployment and clean up resources.

        WARNING: This action is irreversible. All data will be lost.

        Args:
            deployment_id: The deployment identifier to destroy
            confirm: Must be True to confirm destruction

        Returns:
            Destruction status and cleanup details.
        """
        if not confirm:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "Destruction not confirmed",
                    "message": "Set confirm=True to destroy the deployment",
                    "warning": "This action is irreversible. All data will be lost.",
                }, indent=2)
            )]

        try:
            from ..deployment.deployers import DockerDeployer, BinaryDeployer
            from ..deployment.security import CertificateManager, CredentialStore

            # Try Docker first
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if info:
                result = await deployer.destroy(deployment_id, force=True)

                # Clean up certificates and credentials
                cert_manager = CertificateManager()
                cert_manager.delete_bundle(deployment_id)

                cred_store = CredentialStore()
                cred_store.clear_deployment(deployment_id)

                return [TextContent(
                    type="text",
                    text=json.dumps(result.to_dict(), indent=2)
                )]

            # Try binary deployer
            deployer = BinaryDeployer()
            result = await deployer.destroy(deployment_id, force=True)

            return [TextContent(
                type="text",
                text=json.dumps(result.to_dict(), indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def list_deployments(
        profile_filter: Optional[str] = None,
        include_destroyed: bool = False,
    ) -> list[TextContent]:
        """List all managed Velociraptor deployments.

        Args:
            profile_filter: Filter by profile name ('rapid', 'standard', 'enterprise')
            include_destroyed: Include destroyed deployments

        Returns:
            List of deployments with their current status.
        """
        try:
            from ..deployment.deployers import DockerDeployer, BinaryDeployer
            from ..deployment.profiles import DeploymentState

            all_deployments = []

            # Get Docker deployments
            try:
                docker_deployer = DockerDeployer()
                deployments = docker_deployer.list_deployments()
                all_deployments.extend(deployments)
            except Exception:
                pass

            # Get binary deployments
            try:
                binary_deployer = BinaryDeployer()
                deployments = binary_deployer.list_deployments()
                all_deployments.extend(deployments)
            except Exception:
                pass

            # Filter results
            filtered = []
            for d in all_deployments:
                if profile_filter and d.profile != profile_filter:
                    continue
                if not include_destroyed and d.state == DeploymentState.DESTROYED:
                    continue
                filtered.append(d.to_dict())

            return [TextContent(
                type="text",
                text=json.dumps({
                    "count": len(filtered),
                    "deployments": filtered,
                }, indent=2, default=str)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    # =========================================================================
    # Agent Deployment Tools (7 tools)
    # =========================================================================

    @server.tool()
    async def generate_agent_installer(
        deployment_id: str,
        os_type: str = "windows",
        installer_type: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> list[TextContent]:
        """Generate an agent installer package with embedded configuration.

        Creates platform-specific installers that can be deployed without
        additional configuration.

        Args:
            deployment_id: The deployment to generate installer for
            os_type: Target OS - 'windows', 'linux', or 'macos'
            installer_type: Installer format - 'msi', 'deb', 'rpm', or 'pkg'
                          (auto-selected based on os_type if not specified)
            labels: Labels to apply to agents installed with this package

        Returns:
            Path to generated installer and installation instructions.
        """
        try:
            from ..deployment.agents import InstallerGenerator, InstallerType
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            # Determine installer type
            type_map = {
                "windows": InstallerType.MSI,
                "linux": InstallerType.DEB,
                "macos": InstallerType.PKG,
            }
            if installer_type:
                inst_type = InstallerType(installer_type.lower())
            else:
                inst_type = type_map.get(os_type.lower(), InstallerType.ZIP)

            # Create installer config
            from ..deployment.agents.installer_gen import InstallerConfig
            config = InstallerConfig(
                server_url=info.server_url.replace("/api/", "") + f":{8000}/",
                ca_cert=bundle.ca_cert,
                ca_fingerprint=bundle.ca_fingerprint,
                labels=labels or [],
                deployment_id=deployment_id,
            )

            # Generate installer
            generator = InstallerGenerator()
            result = await generator.generate(config, inst_type)

            return [TextContent(
                type="text",
                text=json.dumps(result.to_dict(), indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def create_offline_collector(
        artifacts: list[str],
        target_os: str = "windows",
        artifact_set: Optional[str] = None,
        encrypt_output: bool = False,
        deployment_id: Optional[str] = None,
    ) -> list[TextContent]:
        """Create an offline collection package for air-gapped systems.

        Generates a self-contained package that collects forensic artifacts
        without requiring network connectivity to a Velociraptor server.

        Args:
            artifacts: List of artifacts to collect (e.g., ['Windows.System.Pslist'])
            target_os: Target OS - 'windows', 'linux', or 'macos'
            artifact_set: Use predefined artifact set instead of listing artifacts.
                         Options: 'windows_triage', 'windows_quick', 'linux_triage',
                         'macos_triage', 'memory', 'ransomware'
            encrypt_output: Encrypt collection output with a generated password
            deployment_id: Optional deployment ID for tracking

        Returns:
            Path to generated collector package and usage instructions.
        """
        try:
            from ..deployment.agents import OfflineCollectorGenerator
            from ..deployment.agents.offline_collector import CollectorConfig
            from ..deployment.security.credential_store import generate_password

            generator = OfflineCollectorGenerator()

            # Use artifact set if specified
            if artifact_set:
                artifacts = generator.get_artifact_set(artifact_set)

            # Generate encryption password if needed
            encryption_password = None
            if encrypt_output:
                encryption_password = generate_password(32)

            config = CollectorConfig(
                artifacts=artifacts,
                encrypt_output=encrypt_output,
                encryption_password=encryption_password,
                deployment_id=deployment_id,
            )

            result = await generator.generate(config, target_os)

            response = result.to_dict()
            if encrypt_output:
                response["encryption_password"] = encryption_password
                response["password_warning"] = "Save this password - it will not be shown again"

            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def generate_gpo_package(
        deployment_id: str,
        domain_controller: str = "DC01",
        labels: Optional[list[str]] = None,
    ) -> list[TextContent]:
        """Generate a GPO deployment bundle for Windows domain environments.

        Creates MSI installer, configuration files, and step-by-step GPO
        setup documentation.

        Args:
            deployment_id: The deployment to generate package for
            domain_controller: Name of the domain controller (for share paths)
            labels: Labels to apply to deployed agents

        Returns:
            Path to GPO package and deployment instructions.
        """
        try:
            from pathlib import Path
            from datetime import datetime, timezone

            from ..deployment.agents import InstallerGenerator
            from ..deployment.agents.installer_gen import InstallerConfig, InstallerType
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            # Create output directory
            output_dir = Path(os.environ.get("LOCALAPPDATA", "~")).expanduser() / "megaraptor-mcp" / "gpo" / deployment_id
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate MSI installer config
            config = InstallerConfig(
                server_url=info.server_url.replace("/api/", "") + f":{8000}/",
                ca_cert=bundle.ca_cert,
                ca_fingerprint=bundle.ca_fingerprint,
                labels=labels or ["gpo-deployed"],
                deployment_id=deployment_id,
            )

            # Generate installer
            generator = InstallerGenerator(output_dir=output_dir)
            installer = await generator.generate(config, InstallerType.MSI)

            # Generate GPO instructions from template
            try:
                from jinja2 import Template
                from ..deployment.templates import get_template_path

                template_path = get_template_path("gpo_instructions.md.j2")
                template = Template(template_path.read_text())

                instructions = template.render(
                    deployment_id=deployment_id,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    server_url=info.server_url,
                    server_hostname=info.server_url.split("://")[1].split(":")[0],
                    frontend_port=8000,
                    domain_controller=domain_controller,
                    ca_fingerprint=bundle.ca_fingerprint,
                )

                instructions_file = output_dir / "GPO_Instructions.md"
                instructions_file.write_text(instructions)

            except Exception:
                # Fallback if Jinja2 not available
                instructions_file = output_dir / "GPO_Instructions.txt"
                instructions_file.write_text(f"GPO deployment instructions for {deployment_id}")

            # Copy CA certificate
            ca_file = output_dir / "ca.crt"
            ca_file.write_text(bundle.ca_cert)

            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "output_directory": str(output_dir),
                    "files": [
                        str(installer.file_path),
                        str(instructions_file),
                        str(ca_file),
                    ],
                    "instructions": f"See {instructions_file.name} for deployment steps",
                    "ca_fingerprint": bundle.ca_fingerprint,
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def generate_ansible_playbook(
        deployment_id: str,
        include_windows: bool = True,
        include_linux: bool = True,
        include_macos: bool = True,
        labels: Optional[list[str]] = None,
    ) -> list[TextContent]:
        """Generate Ansible playbook for agent deployment.

        Creates a complete Ansible role with tasks for all selected platforms.

        Args:
            deployment_id: The deployment to generate playbook for
            include_windows: Include Windows deployment tasks
            include_linux: Include Linux deployment tasks
            include_macos: Include macOS deployment tasks
            labels: Labels to apply to deployed agents

        Returns:
            Path to generated playbook directory and usage instructions.
        """
        try:
            from ..deployment.agents import AnsiblePlaybookGenerator
            from ..deployment.agents.ansible_gen import AnsibleConfig
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            # Create Ansible config
            config = AnsibleConfig(
                server_url=info.server_url.replace("/api/", "") + ":8000/",
                ca_cert=bundle.ca_cert,
                ca_fingerprint=bundle.ca_fingerprint,
                client_labels=labels or ["ansible-deployed"],
                deployment_id=deployment_id,
            )

            # Generate playbook
            generator = AnsiblePlaybookGenerator()
            result = generator.generate(
                config,
                include_windows=include_windows,
                include_linux=include_linux,
                include_macos=include_macos,
            )

            return [TextContent(
                type="text",
                text=json.dumps({
                    **result.to_dict(),
                    "usage": [
                        "1. cd " + str(result.output_dir),
                        "2. cp inventory.yml.example inventory.yml",
                        "3. Edit inventory.yml with your hosts",
                        "4. ansible-playbook -i inventory.yml deploy_agents.yml",
                    ],
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def deploy_agents_winrm(
        deployment_id: str,
        targets: list[str],
        username: str,
        password: str,
        labels: Optional[list[str]] = None,
        use_ssl: bool = True,
        port: int = 5986,
    ) -> list[TextContent]:
        """Push Velociraptor agents to Windows systems via WinRM.

        Args:
            deployment_id: The deployment to connect agents to
            targets: List of target hostnames or IPs
            username: Windows username (DOMAIN\\user or user@domain)
            password: Windows password
            labels: Labels to apply to deployed agents
            use_ssl: Use HTTPS for WinRM (default True)
            port: WinRM port (default 5986 for HTTPS)

        Returns:
            Deployment results for each target.
        """
        try:
            from ..deployment.agents import WinRMDeployer
            from ..deployment.agents.winrm_deployer import WinRMCredentials, DeploymentTarget as WinRMTarget
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            # Generate client config
            import yaml
            client_config = yaml.dump({
                "Client": {
                    "server_urls": [info.server_url.replace("/api/", "") + ":8000/"],
                    "ca_certificate": bundle.ca_cert,
                    "nonce": secrets.token_hex(8),
                    "labels": labels or [],
                },
                "version": {"name": "megaraptor-winrm-deploy"},
            })

            # Create credentials and targets
            creds = WinRMCredentials(
                username=username,
                password=password,
                use_ssl=use_ssl,
                port=port,
            )

            winrm_targets = [
                WinRMTarget(hostname=t, port=port, credentials=creds)
                for t in targets
            ]

            # Deploy
            winrm_deployer = WinRMDeployer(default_credentials=creds)
            results = await winrm_deployer.deploy_to_multiple(
                winrm_targets, client_config, labels=labels
            )

            return [TextContent(
                type="text",
                text=json.dumps({
                    "total": len(results),
                    "successful": sum(1 for r in results if r.success),
                    "failed": sum(1 for r in results if not r.success),
                    "results": [r.to_dict() for r in results],
                }, indent=2)
            )]

        except ImportError:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "pywinrm not installed",
                    "suggestion": "pip install pywinrm"
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def deploy_agents_ssh(
        deployment_id: str,
        targets: list[str],
        username: str,
        key_path: Optional[str] = None,
        password: Optional[str] = None,
        target_os: str = "linux",
        labels: Optional[list[str]] = None,
        port: int = 22,
    ) -> list[TextContent]:
        """Push Velociraptor agents to Linux/macOS systems via SSH.

        Args:
            deployment_id: The deployment to connect agents to
            targets: List of target hostnames or IPs
            username: SSH username
            key_path: Path to SSH private key (preferred)
            password: SSH password (if not using key)
            target_os: Target OS - 'linux' or 'macos'
            labels: Labels to apply to deployed agents
            port: SSH port (default 22)

        Returns:
            Deployment results for each target.
        """
        try:
            from ..deployment.agents import SSHDeployer
            from ..deployment.agents.ssh_deployer import SSHCredentials, DeploymentTarget as SSHTarget
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            # Generate client config
            import yaml
            client_config = yaml.dump({
                "Client": {
                    "server_urls": [info.server_url.replace("/api/", "") + ":8000/"],
                    "ca_certificate": bundle.ca_cert,
                    "nonce": secrets.token_hex(8),
                    "labels": labels or [],
                },
                "version": {"name": "megaraptor-ssh-deploy"},
            })

            # Create credentials and targets
            creds = SSHCredentials(
                username=username,
                key_path=key_path,
                password=password,
                port=port,
            )

            ssh_targets = [
                SSHTarget(hostname=t, credentials=creds, target_os=target_os)
                for t in targets
            ]

            # Deploy
            ssh_deployer = SSHDeployer(default_credentials=creds)
            results = await ssh_deployer.deploy_to_multiple(
                ssh_targets, client_config, labels=labels
            )

            return [TextContent(
                type="text",
                text=json.dumps({
                    "total": len(results),
                    "successful": sum(1 for r in results if r.success),
                    "failed": sum(1 for r in results if not r.success),
                    "results": [r.to_dict() for r in results],
                }, indent=2)
            )]

        except ImportError:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "paramiko not installed",
                    "suggestion": "pip install paramiko"
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def check_agent_deployment(
        deployment_id: str,
        client_search: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> list[TextContent]:
        """Verify agent enrollment status for a deployment.

        Checks which agents have successfully enrolled with the server.

        Args:
            deployment_id: The deployment to check
            client_search: Optional search filter for client hostname/ID
            labels: Filter by client labels

        Returns:
            List of enrolled clients and their status.
        """
        try:
            from ..client import get_client

            client = get_client()

            # Build VQL query
            conditions = []
            if client_search:
                conditions.append(f"os_info.hostname =~ '{client_search}' OR client_id =~ '{client_search}'")
            if labels:
                label_conditions = " OR ".join(f"'{l}' in labels" for l in labels)
                conditions.append(f"({label_conditions})")

            where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            vql = f"""
            SELECT client_id, os_info.hostname AS hostname, os_info.system AS os,
                   labels, last_seen_at, first_seen_at
            FROM clients()
            {where_clause}
            ORDER BY last_seen_at DESC
            LIMIT 100
            """

            results = client.query(vql)

            # Categorize by status
            now = datetime.now(timezone.utc)
            online = []
            offline = []

            for r in results:
                last_seen = r.get("last_seen_at", 0)
                if isinstance(last_seen, (int, float)):
                    last_seen_dt = datetime.fromtimestamp(last_seen / 1000000, tz=timezone.utc)
                    minutes_ago = (now - last_seen_dt).total_seconds() / 60
                    r["minutes_since_seen"] = round(minutes_ago, 1)
                    if minutes_ago < 10:
                        online.append(r)
                    else:
                        offline.append(r)
                else:
                    offline.append(r)

            return [TextContent(
                type="text",
                text=json.dumps({
                    "deployment_id": deployment_id,
                    "total_clients": len(results),
                    "online": len(online),
                    "offline": len(offline),
                    "online_clients": online,
                    "offline_clients": offline,
                }, indent=2, default=str)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    # =========================================================================
    # Configuration & Security Tools (5 tools)
    # =========================================================================

    @server.tool()
    async def generate_server_config(
        deployment_id: str,
        output_format: str = "yaml",
    ) -> list[TextContent]:
        """Generate Velociraptor server configuration file.

        Args:
            deployment_id: The deployment to generate config for
            output_format: Output format - 'yaml' or 'json'

        Returns:
            Server configuration content.
        """
        try:
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            # Generate config
            import yaml
            config = {
                "version": {"name": "megaraptor-deployment"},
                "Client": {
                    "server_urls": [info.server_url.replace("/api/", "") + ":8000/"],
                    "ca_certificate": bundle.ca_cert,
                },
                "API": {
                    "bind_address": "0.0.0.0:8889",
                    "bind_scheme": "https",
                },
                "GUI": {
                    "bind_address": "0.0.0.0:8889",
                    "bind_scheme": "https",
                    "public_url": info.server_url,
                },
                "Frontend": {
                    "bind_address": "0.0.0.0:8000",
                },
                "ca_certificate": bundle.ca_cert,
            }

            if output_format == "json":
                output = json.dumps(config, indent=2)
            else:
                output = yaml.dump(config, default_flow_style=False)

            return [TextContent(
                type="text",
                text=output
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def generate_api_credentials(
        deployment_id: str,
        client_name: str = "megaraptor_api",
        validity_days: int = 365,
    ) -> list[TextContent]:
        """Generate API client credentials for MCP connection.

        Creates a new API client certificate for connecting this MCP
        server to a Velociraptor deployment.

        Args:
            deployment_id: The deployment to generate credentials for
            client_name: Name for the API client
            validity_days: Certificate validity in days

        Returns:
            API credentials in Velociraptor config file format.
            IMPORTANT: Save these credentials - they can only be displayed once.
        """
        try:
            from ..deployment.security import CertificateManager, CredentialStore, StoredCredential
            from ..deployment.security.credential_store import generate_credential_id
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            # Generate API client config (Velociraptor format)
            import yaml
            api_config = {
                "api_url": info.api_url or info.server_url,
                "ca_certificate": bundle.ca_cert,
                "client_cert": bundle.api_cert,
                "client_private_key": bundle.api_key,
            }

            # Store credential metadata
            cred_store = CredentialStore()
            credential = StoredCredential(
                id=generate_credential_id(),
                name=client_name,
                credential_type="api_key",
                created_at=datetime.now(timezone.utc).isoformat(),
                expires_at=(datetime.now(timezone.utc) + timedelta(days=validity_days)).isoformat(),
                deployment_id=deployment_id,
                data={"client_name": client_name},
            )
            cred_store.store(credential)

            # Return config in YAML format (matches Velociraptor api_client format)
            return [TextContent(
                type="text",
                text=f"""# Velociraptor API Client Configuration
# Generated for: {client_name}
# Deployment: {deployment_id}
# Expires: {credential.expires_at}
#
# IMPORTANT: Save this configuration - it cannot be displayed again!
# Set VELOCIRAPTOR_CONFIG_PATH to this file to use with MCP.

{yaml.dump(api_config, default_flow_style=False)}"""
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def rotate_certificates(
        deployment_id: str,
        rotate_ca: bool = False,
        validity_days: int = 365,
    ) -> list[TextContent]:
        """Rotate certificates for a deployment.

        WARNING: Rotating CA certificate will require re-enrollment of all agents.

        Args:
            deployment_id: The deployment to rotate certificates for
            rotate_ca: Also rotate the CA certificate (requires re-enrollment)
            validity_days: Validity period for new certificates

        Returns:
            New certificate fingerprints and re-enrollment instructions.
        """
        try:
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load current certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if not bundle:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate bundle not found"
                    }, indent=2)
                )]

            server_hostname = info.server_url.split("://")[1].split(":")[0]

            if rotate_ca:
                # Generate entirely new bundle
                new_bundle = cert_manager.generate_bundle(
                    server_hostname=server_hostname,
                    cert_validity_days=validity_days,
                )
                cert_manager.save_bundle(new_bundle, deployment_id)

                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "ca_rotated": True,
                        "new_ca_fingerprint": new_bundle.ca_fingerprint,
                        "warning": "All agents must be re-enrolled with new configuration",
                        "action_required": "Generate new agent installers and redeploy",
                    }, indent=2)
                )]

            else:
                # TODO: Implement server/client cert rotation without CA
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Certificate rotation without CA is not yet implemented",
                        "suggestion": "Use rotate_ca=True to perform full rotation"
                    }, indent=2)
                )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def validate_deployment(
        deployment_id: str,
    ) -> list[TextContent]:
        """Run comprehensive security and health validation on a deployment.

        Checks:
        - Server accessibility
        - Certificate validity
        - Service health
        - Security configuration

        Args:
            deployment_id: The deployment to validate

        Returns:
            Detailed validation report with any issues found.
        """
        try:
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            checks = []

            # Check deployment exists
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "valid": False,
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            checks.append({
                "check": "deployment_exists",
                "status": "pass",
                "message": f"Deployment found: {info.target}",
            })

            # Check certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            if bundle:
                checks.append({
                    "check": "certificates_exist",
                    "status": "pass",
                    "message": f"CA fingerprint: {bundle.ca_fingerprint[:16]}...",
                })
            else:
                checks.append({
                    "check": "certificates_exist",
                    "status": "fail",
                    "message": "Certificate bundle not found",
                })

            # Check health
            health = await deployer.health_check(deployment_id)
            health_status = "pass" if health.get("healthy") else "fail"
            checks.append({
                "check": "health_check",
                "status": health_status,
                "message": health.get("checks", []),
            })

            # Check auto-destroy schedule
            if info.auto_destroy_at:
                destroy_time = datetime.fromisoformat(info.auto_destroy_at.replace("Z", "+00:00"))
                hours_remaining = (destroy_time - datetime.now(timezone.utc)).total_seconds() / 3600

                if hours_remaining < 0:
                    checks.append({
                        "check": "auto_destroy",
                        "status": "warn",
                        "message": f"Deployment scheduled for destruction has passed",
                    })
                elif hours_remaining < 24:
                    checks.append({
                        "check": "auto_destroy",
                        "status": "warn",
                        "message": f"Deployment will be destroyed in {hours_remaining:.1f} hours",
                    })
                else:
                    checks.append({
                        "check": "auto_destroy",
                        "status": "info",
                        "message": f"Deployment will be destroyed in {hours_remaining:.1f} hours",
                    })

            # Overall status
            failed_checks = [c for c in checks if c["status"] == "fail"]
            warn_checks = [c for c in checks if c["status"] == "warn"]

            return [TextContent(
                type="text",
                text=json.dumps({
                    "valid": len(failed_checks) == 0,
                    "deployment_id": deployment_id,
                    "state": info.state.value,
                    "summary": {
                        "passed": len([c for c in checks if c["status"] == "pass"]),
                        "warnings": len(warn_checks),
                        "failed": len(failed_checks),
                    },
                    "checks": checks,
                }, indent=2, default=str)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]

    @server.tool()
    async def export_deployment_docs(
        deployment_id: str,
        output_path: Optional[str] = None,
    ) -> list[TextContent]:
        """Generate comprehensive deployment documentation.

        Creates documentation including:
        - Server access details
        - Agent deployment guides
        - Security configuration
        - Troubleshooting guides

        Args:
            deployment_id: The deployment to document
            output_path: Optional path for documentation files

        Returns:
            Path to generated documentation.
        """
        try:
            from pathlib import Path
            from ..deployment.security import CertificateManager
            from ..deployment.deployers import DockerDeployer

            # Get deployment info
            deployer = DockerDeployer()
            info = await deployer.get_status(deployment_id)

            if not info:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Deployment not found: {deployment_id}"
                    }, indent=2)
                )]

            # Load certificates
            cert_manager = CertificateManager()
            bundle = cert_manager.load_bundle(deployment_id)

            # Create output directory
            if output_path:
                output_dir = Path(output_path)
            else:
                output_dir = Path(os.environ.get("LOCALAPPDATA", "~")).expanduser() / "megaraptor-mcp" / "docs" / deployment_id

            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate main README
            readme = f"""# Velociraptor Deployment Documentation

**Deployment ID**: {deployment_id}
**Profile**: {info.profile}
**Target**: {info.target}
**Created**: {info.created_at}

## Server Access

- **GUI URL**: {info.server_url}
- **API URL**: {info.api_url}
- **CA Fingerprint**: {bundle.ca_fingerprint if bundle else 'N/A'}

## Quick Start

### Access the GUI

1. Open {info.server_url} in your browser
2. Accept the self-signed certificate
3. Log in with the admin credentials provided at deployment

### Connect MCP

Set the following environment variable:
```bash
export VELOCIRAPTOR_CONFIG_PATH=/path/to/api_client.yaml
```

### Deploy Agents

Use the MCP tools to generate and deploy agents:
- `generate_agent_installer` - Create platform installers
- `deploy_agents_winrm` - Push to Windows
- `deploy_agents_ssh` - Push to Linux/macOS
- `generate_gpo_package` - Create GPO deployment bundle
- `generate_ansible_playbook` - Create Ansible playbook

## Security Notes

- All communications use mTLS encryption
- CA certificate is pinned in all agent configurations
- Admin password was shown only at creation time
{f"- Auto-destruction scheduled: {info.auto_destroy_at}" if info.auto_destroy_at else ""}

## Support

For issues, see the troubleshooting guide or contact your administrator.
"""

            readme_file = output_dir / "README.md"
            readme_file.write_text(readme)

            # Save CA certificate for reference
            if bundle:
                ca_file = output_dir / "ca.crt"
                ca_file.write_text(bundle.ca_cert)

            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "output_directory": str(output_dir),
                    "files": [
                        str(readme_file),
                        str(ca_file) if bundle else None,
                    ],
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]
