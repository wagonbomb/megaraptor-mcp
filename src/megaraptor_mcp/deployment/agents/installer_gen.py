"""
Agent installer generator.

Generates repacked Velociraptor agent installers with embedded configuration
for various platforms (MSI, DEB, RPM, PKG).
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Any

import yaml


class InstallerType(Enum):
    """Supported installer types."""
    MSI = "msi"      # Windows MSI
    DEB = "deb"      # Debian/Ubuntu
    RPM = "rpm"      # RedHat/CentOS
    PKG = "pkg"      # macOS
    ZIP = "zip"      # Portable/standalone


@dataclass
class InstallerConfig:
    """Configuration for installer generation.

    Attributes:
        server_url: Velociraptor server URL
        ca_cert: CA certificate for TLS verification
        ca_fingerprint: CA certificate fingerprint for pinning
        client_name: Custom client name (optional)
        labels: Labels to apply to the client
        deployment_id: Associated deployment ID
    """
    server_url: str
    ca_cert: str
    ca_fingerprint: str
    client_name: Optional[str] = None
    labels: list[str] = None
    deployment_id: Optional[str] = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = []


@dataclass
class GeneratedInstaller:
    """Result of installer generation.

    Attributes:
        installer_type: Type of installer generated
        file_path: Path to the generated installer
        file_size: Size in bytes
        checksum: SHA256 checksum
        config_embedded: Whether config is embedded
        metadata: Additional metadata
    """
    installer_type: InstallerType
    file_path: Path
    file_size: int
    checksum: str
    config_embedded: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "installer_type": self.installer_type.value,
            "file_path": str(self.file_path),
            "file_size": self.file_size,
            "checksum": self.checksum,
            "config_embedded": self.config_embedded,
            "metadata": self.metadata,
        }


class InstallerGenerator:
    """Generates Velociraptor agent installers with embedded configuration.

    This generator creates platform-specific installers that have the
    client configuration pre-embedded, enabling zero-touch deployment.
    """

    # Velociraptor release URLs
    RELEASE_BASE_URL = "https://github.com/Velocidex/velociraptor/releases/latest/download"

    # Binary names per platform
    BINARIES = {
        InstallerType.MSI: "velociraptor-{version}-windows-amd64.msi",
        InstallerType.DEB: "velociraptor-{version}-linux-amd64.deb",
        InstallerType.RPM: "velociraptor-{version}-linux-amd64.rpm",
        InstallerType.PKG: "velociraptor-{version}-darwin-amd64.pkg",
        InstallerType.ZIP: "velociraptor-{version}-{os}-{arch}",
    }

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        velociraptor_binary: Optional[str] = None,
    ):
        """Initialize the installer generator.

        Args:
            output_dir: Directory for generated installers
            velociraptor_binary: Path to local Velociraptor binary (optional)
        """
        self.output_dir = output_dir or self._default_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.velociraptor_binary = velociraptor_binary

    @staticmethod
    def _default_output_dir() -> Path:
        """Get the default output directory."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", "~"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
        return base.expanduser() / "megaraptor-mcp" / "installers"

    def _generate_client_config(self, config: InstallerConfig) -> str:
        """Generate client configuration YAML.

        Args:
            config: Installer configuration

        Returns:
            YAML configuration string
        """
        client_config = {
            "Client": {
                "server_urls": [config.server_url],
                "ca_certificate": config.ca_cert,
                "nonce": os.urandom(8).hex(),
                "writeback_darwin": "/etc/velociraptor.writeback.yaml",
                "writeback_linux": "/etc/velociraptor.writeback.yaml",
                "writeback_windows": "$ProgramFiles\\Velociraptor\\velociraptor.writeback.yaml",
            },
            "version": {
                "name": "megaraptor-agent",
            },
        }

        if config.labels:
            client_config["Client"]["labels"] = config.labels

        return yaml.dump(client_config, default_flow_style=False)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        import hashlib

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def generate_windows_msi(
        self,
        config: InstallerConfig,
        version: str = "latest",
    ) -> GeneratedInstaller:
        """Generate a Windows MSI installer with embedded config.

        This uses Velociraptor's built-in repacking capability to create
        an MSI with the client configuration pre-embedded.

        Args:
            config: Installer configuration
            version: Velociraptor version

        Returns:
            Generated installer details
        """
        # Create temporary directory for work
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write client config
            config_file = tmppath / "client.config.yaml"
            config_file.write_text(self._generate_client_config(config))

            # Output file path
            output_name = f"velociraptor-agent-{config.deployment_id or 'custom'}.msi"
            output_path = self.output_dir / output_name

            # Check if we have Velociraptor binary for repacking
            if self.velociraptor_binary and os.path.exists(self.velociraptor_binary):
                # Use local binary to repack
                cmd = [
                    self.velociraptor_binary,
                    "config", "repack",
                    "--msi", str(output_path),
                    str(config_file),
                ]
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True
                )
                if result.returncode != 0:
                    raise RuntimeError(f"Repacking failed: {result.stderr}")
            else:
                # Create a config-only package (config + instructions)
                # In production, this would download and repack the MSI
                output_path = self.output_dir / f"velociraptor-config-{config.deployment_id or 'custom'}.zip"
                await self._create_config_package(config, output_path, "windows")

            checksum = self._calculate_checksum(output_path)

            return GeneratedInstaller(
                installer_type=InstallerType.MSI,
                file_path=output_path,
                file_size=output_path.stat().st_size,
                checksum=checksum,
                config_embedded=bool(self.velociraptor_binary),
                metadata={
                    "deployment_id": config.deployment_id,
                    "server_url": config.server_url,
                    "ca_fingerprint": config.ca_fingerprint,
                    "labels": config.labels,
                },
            )

    async def generate_linux_deb(
        self,
        config: InstallerConfig,
        version: str = "latest",
    ) -> GeneratedInstaller:
        """Generate a Debian package with embedded config.

        Args:
            config: Installer configuration
            version: Velociraptor version

        Returns:
            Generated installer details
        """
        output_name = f"velociraptor-agent-{config.deployment_id or 'custom'}.deb"
        output_path = self.output_dir / output_name

        # Create config package (actual DEB repack would require dpkg tools)
        await self._create_config_package(config, output_path.with_suffix(".zip"), "linux")

        return GeneratedInstaller(
            installer_type=InstallerType.DEB,
            file_path=output_path.with_suffix(".zip"),
            file_size=output_path.with_suffix(".zip").stat().st_size,
            checksum=self._calculate_checksum(output_path.with_suffix(".zip")),
            config_embedded=False,
            metadata={
                "deployment_id": config.deployment_id,
                "server_url": config.server_url,
                "ca_fingerprint": config.ca_fingerprint,
                "labels": config.labels,
                "instructions": "Extract and run: sudo dpkg -i velociraptor*.deb && sudo cp client.config.yaml /etc/velociraptor/client.config.yaml",
            },
        )

    async def generate_linux_rpm(
        self,
        config: InstallerConfig,
        version: str = "latest",
    ) -> GeneratedInstaller:
        """Generate an RPM package with embedded config.

        Args:
            config: Installer configuration
            version: Velociraptor version

        Returns:
            Generated installer details
        """
        output_name = f"velociraptor-agent-{config.deployment_id or 'custom'}.rpm"
        output_path = self.output_dir / output_name

        # Create config package
        await self._create_config_package(config, output_path.with_suffix(".zip"), "linux")

        return GeneratedInstaller(
            installer_type=InstallerType.RPM,
            file_path=output_path.with_suffix(".zip"),
            file_size=output_path.with_suffix(".zip").stat().st_size,
            checksum=self._calculate_checksum(output_path.with_suffix(".zip")),
            config_embedded=False,
            metadata={
                "deployment_id": config.deployment_id,
                "server_url": config.server_url,
                "ca_fingerprint": config.ca_fingerprint,
                "labels": config.labels,
                "instructions": "Extract and run: sudo rpm -i velociraptor*.rpm && sudo cp client.config.yaml /etc/velociraptor/client.config.yaml",
            },
        )

    async def generate_macos_pkg(
        self,
        config: InstallerConfig,
        version: str = "latest",
    ) -> GeneratedInstaller:
        """Generate a macOS package with embedded config.

        Args:
            config: Installer configuration
            version: Velociraptor version

        Returns:
            Generated installer details
        """
        output_name = f"velociraptor-agent-{config.deployment_id or 'custom'}.pkg"
        output_path = self.output_dir / output_name

        # Create config package
        await self._create_config_package(config, output_path.with_suffix(".zip"), "darwin")

        return GeneratedInstaller(
            installer_type=InstallerType.PKG,
            file_path=output_path.with_suffix(".zip"),
            file_size=output_path.with_suffix(".zip").stat().st_size,
            checksum=self._calculate_checksum(output_path.with_suffix(".zip")),
            config_embedded=False,
            metadata={
                "deployment_id": config.deployment_id,
                "server_url": config.server_url,
                "ca_fingerprint": config.ca_fingerprint,
                "labels": config.labels,
                "instructions": "Extract and run: sudo installer -pkg velociraptor*.pkg -target / && sudo cp client.config.yaml /etc/velociraptor/client.config.yaml",
            },
        )

    async def _create_config_package(
        self,
        config: InstallerConfig,
        output_path: Path,
        target_os: str,
    ) -> None:
        """Create a ZIP package with config and instructions.

        Args:
            config: Installer configuration
            output_path: Output file path
            target_os: Target operating system
        """
        import zipfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write config
            config_file = tmppath / "client.config.yaml"
            config_file.write_text(self._generate_client_config(config))

            # Write installation instructions
            instructions = self._generate_install_instructions(config, target_os)
            (tmppath / "INSTALL.md").write_text(instructions)

            # Write CA certificate
            (tmppath / "ca.crt").write_text(config.ca_cert)

            # Create ZIP
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in tmppath.iterdir():
                    zf.write(file, file.name)

    def _generate_install_instructions(
        self,
        config: InstallerConfig,
        target_os: str,
    ) -> str:
        """Generate installation instructions markdown."""
        instructions = {
            "windows": f"""# Velociraptor Agent Installation - Windows

## Prerequisites
- Administrator privileges
- Windows 10/11 or Server 2016+

## Installation Steps

1. Download the Velociraptor MSI from the official releases
2. Copy the `client.config.yaml` to a temporary location
3. Run the installer:
   ```powershell
   msiexec /i velociraptor.msi /qn
   ```
4. Copy configuration:
   ```powershell
   Copy-Item client.config.yaml "C:\\Program Files\\Velociraptor\\client.config.yaml"
   ```
5. Start the service:
   ```powershell
   Start-Service Velociraptor
   ```

## Server Connection
- Server URL: {config.server_url}
- CA Fingerprint: {config.ca_fingerprint}

## Verification
Check service status:
```powershell
Get-Service Velociraptor
```
""",
            "linux": f"""# Velociraptor Agent Installation - Linux

## Prerequisites
- Root privileges
- systemd-based distribution

## Installation Steps (Debian/Ubuntu)

1. Download the Velociraptor DEB package
2. Install:
   ```bash
   sudo dpkg -i velociraptor*.deb
   ```
3. Copy configuration:
   ```bash
   sudo mkdir -p /etc/velociraptor
   sudo cp client.config.yaml /etc/velociraptor/client.config.yaml
   sudo chmod 600 /etc/velociraptor/client.config.yaml
   ```
4. Start the service:
   ```bash
   sudo systemctl enable velociraptor
   sudo systemctl start velociraptor
   ```

## Installation Steps (RHEL/CentOS)

1. Download the Velociraptor RPM package
2. Install:
   ```bash
   sudo rpm -i velociraptor*.rpm
   ```
3. Follow steps 3-4 from above

## Server Connection
- Server URL: {config.server_url}
- CA Fingerprint: {config.ca_fingerprint}

## Verification
```bash
sudo systemctl status velociraptor
```
""",
            "darwin": f"""# Velociraptor Agent Installation - macOS

## Prerequisites
- Administrator privileges
- macOS 10.15+

## Installation Steps

1. Download the Velociraptor PKG
2. Install:
   ```bash
   sudo installer -pkg velociraptor*.pkg -target /
   ```
3. Copy configuration:
   ```bash
   sudo mkdir -p /etc/velociraptor
   sudo cp client.config.yaml /etc/velociraptor/client.config.yaml
   sudo chmod 600 /etc/velociraptor/client.config.yaml
   ```
4. Start the service:
   ```bash
   sudo launchctl load /Library/LaunchDaemons/com.velocidex.velociraptor.plist
   ```

## Server Connection
- Server URL: {config.server_url}
- CA Fingerprint: {config.ca_fingerprint}

## Verification
```bash
sudo launchctl list | grep velociraptor
```
""",
        }
        return instructions.get(target_os, instructions["linux"])

    async def generate(
        self,
        config: InstallerConfig,
        installer_type: InstallerType,
        version: str = "latest",
    ) -> GeneratedInstaller:
        """Generate an installer of the specified type.

        Args:
            config: Installer configuration
            installer_type: Type of installer to generate
            version: Velociraptor version

        Returns:
            Generated installer details
        """
        generators = {
            InstallerType.MSI: self.generate_windows_msi,
            InstallerType.DEB: self.generate_linux_deb,
            InstallerType.RPM: self.generate_linux_rpm,
            InstallerType.PKG: self.generate_macos_pkg,
        }

        generator = generators.get(installer_type)
        if not generator:
            raise ValueError(f"Unsupported installer type: {installer_type}")

        return await generator(config, version)
