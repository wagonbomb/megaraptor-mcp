"""
Offline collector generator.

Creates self-contained collection packages for air-gapped systems
that don't have network connectivity to the Velociraptor server.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any


@dataclass
class CollectorConfig:
    """Configuration for offline collector.

    Attributes:
        artifacts: List of artifacts to collect
        parameters: Artifact parameters
        output_format: Output format (json, csv, zip)
        encrypt_output: Encrypt output with password
        encryption_password: Password for encryption
        max_file_size: Maximum file size to collect (bytes)
        timeout: Collection timeout in seconds
        deployment_id: Associated deployment ID
    """
    artifacts: list[str]
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    output_format: str = "zip"
    encrypt_output: bool = False
    encryption_password: Optional[str] = None
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    timeout: int = 3600  # 1 hour
    deployment_id: Optional[str] = None


@dataclass
class GeneratedCollector:
    """Result of collector generation.

    Attributes:
        file_path: Path to the generated collector
        file_size: Size in bytes
        checksum: SHA256 checksum
        artifacts: List of artifacts included
        target_os: Target operating system
        encrypted: Whether output will be encrypted
        instructions: Usage instructions
    """
    file_path: Path
    file_size: int
    checksum: str
    artifacts: list[str]
    target_os: str
    encrypted: bool
    instructions: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "file_path": str(self.file_path),
            "file_size": self.file_size,
            "checksum": self.checksum,
            "artifacts": self.artifacts,
            "target_os": self.target_os,
            "encrypted": self.encrypted,
            "instructions": self.instructions,
        }


class OfflineCollectorGenerator:
    """Generates offline collection packages.

    Offline collectors are self-contained executables that can collect
    forensic artifacts without requiring network connectivity to a
    Velociraptor server. They're useful for:
    - Air-gapped systems
    - Initial triage before full deployment
    - One-time collections
    """

    # Common triage artifact sets
    ARTIFACT_SETS = {
        "windows_triage": [
            "Windows.KapeFiles.Targets",
            "Windows.System.Pslist",
            "Windows.Network.Netstat",
            "Windows.Detection.Autoruns",
            "Windows.EventLogs.Evtx",
        ],
        "windows_quick": [
            "Windows.System.Pslist",
            "Windows.Network.Netstat",
            "Windows.System.Services",
        ],
        "linux_triage": [
            "Linux.Sys.Pslist",
            "Linux.Network.Netstat",
            "Linux.Sys.Users",
            "Linux.Sys.Crontab",
            "Linux.Sys.Services",
        ],
        "macos_triage": [
            "MacOS.Sys.Pslist",
            "MacOS.Network.Netstat",
            "MacOS.Sys.Users",
            "MacOS.Sys.LaunchAgents",
        ],
        "memory": [
            "Windows.Memory.Acquisition",
        ],
        "ransomware": [
            "Windows.Detection.Ransomware",
            "Windows.Forensics.Usn",
            "Windows.System.Pslist",
            "Windows.Detection.Autoruns",
        ],
    }

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        velociraptor_binary: Optional[str] = None,
    ):
        """Initialize the collector generator.

        Args:
            output_dir: Directory for generated collectors
            velociraptor_binary: Path to local Velociraptor binary
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
        return base.expanduser() / "megaraptor-mcp" / "collectors"

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum."""
        import hashlib

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _generate_collection_spec(self, config: CollectorConfig) -> dict:
        """Generate collection specification."""
        spec = {
            "artifacts": config.artifacts,
            "parameters": config.parameters,
            "timeout": config.timeout,
            "max_upload_bytes": config.max_file_size,
        }

        if config.encrypt_output and config.encryption_password:
            spec["output_encryption"] = {
                "enabled": True,
                "password": config.encryption_password,
            }

        return spec

    async def generate_windows_collector(
        self,
        config: CollectorConfig,
    ) -> GeneratedCollector:
        """Generate a Windows offline collector.

        Args:
            config: Collector configuration

        Returns:
            Generated collector details
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_name = f"velociraptor-collector-windows-{timestamp}.zip"
        output_path = self.output_dir / output_name

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create collection specification
            spec = self._generate_collection_spec(config)
            spec_file = tmppath / "collection_spec.json"
            spec_file.write_text(json.dumps(spec, indent=2))

            # Create batch script
            batch_script = tmppath / "collect.bat"
            batch_script.write_text(self._generate_windows_script(config))

            # Create PowerShell script
            ps_script = tmppath / "collect.ps1"
            ps_script.write_text(self._generate_powershell_script(config))

            # Create instructions
            instructions = self._generate_windows_instructions(config)
            (tmppath / "README.txt").write_text(instructions)

            # Create info file
            info = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "artifacts": config.artifacts,
                "deployment_id": config.deployment_id,
                "encrypted": config.encrypt_output,
            }
            (tmppath / "collector_info.json").write_text(json.dumps(info, indent=2))

            # Create ZIP package
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in tmppath.iterdir():
                    zf.write(file, file.name)

        return GeneratedCollector(
            file_path=output_path,
            file_size=output_path.stat().st_size,
            checksum=self._calculate_checksum(output_path),
            artifacts=config.artifacts,
            target_os="windows",
            encrypted=config.encrypt_output,
            instructions=instructions,
        )

    async def generate_linux_collector(
        self,
        config: CollectorConfig,
    ) -> GeneratedCollector:
        """Generate a Linux offline collector.

        Args:
            config: Collector configuration

        Returns:
            Generated collector details
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_name = f"velociraptor-collector-linux-{timestamp}.tar.gz"
        output_path = self.output_dir / output_name

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create collection specification
            spec = self._generate_collection_spec(config)
            spec_file = tmppath / "collection_spec.json"
            spec_file.write_text(json.dumps(spec, indent=2))

            # Create shell script
            shell_script = tmppath / "collect.sh"
            shell_script.write_text(self._generate_linux_script(config))
            os.chmod(shell_script, 0o755)

            # Create instructions
            instructions = self._generate_linux_instructions(config)
            (tmppath / "README.txt").write_text(instructions)

            # Create info file
            info = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "artifacts": config.artifacts,
                "deployment_id": config.deployment_id,
                "encrypted": config.encrypt_output,
            }
            (tmppath / "collector_info.json").write_text(json.dumps(info, indent=2))

            # Create tarball
            import tarfile

            with tarfile.open(output_path, "w:gz") as tf:
                for file in tmppath.iterdir():
                    tf.add(file, arcname=file.name)

        return GeneratedCollector(
            file_path=output_path,
            file_size=output_path.stat().st_size,
            checksum=self._calculate_checksum(output_path),
            artifacts=config.artifacts,
            target_os="linux",
            encrypted=config.encrypt_output,
            instructions=instructions,
        )

    async def generate_macos_collector(
        self,
        config: CollectorConfig,
    ) -> GeneratedCollector:
        """Generate a macOS offline collector.

        Args:
            config: Collector configuration

        Returns:
            Generated collector details
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_name = f"velociraptor-collector-macos-{timestamp}.tar.gz"
        output_path = self.output_dir / output_name

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create collection specification
            spec = self._generate_collection_spec(config)
            spec_file = tmppath / "collection_spec.json"
            spec_file.write_text(json.dumps(spec, indent=2))

            # Create shell script
            shell_script = tmppath / "collect.sh"
            shell_script.write_text(self._generate_macos_script(config))
            os.chmod(shell_script, 0o755)

            # Create instructions
            instructions = self._generate_macos_instructions(config)
            (tmppath / "README.txt").write_text(instructions)

            # Create tarball
            import tarfile

            with tarfile.open(output_path, "w:gz") as tf:
                for file in tmppath.iterdir():
                    tf.add(file, arcname=file.name)

        return GeneratedCollector(
            file_path=output_path,
            file_size=output_path.stat().st_size,
            checksum=self._calculate_checksum(output_path),
            artifacts=config.artifacts,
            target_os="macos",
            encrypted=config.encrypt_output,
            instructions=instructions,
        )

    def _generate_windows_script(self, config: CollectorConfig) -> str:
        """Generate Windows batch collection script."""
        artifacts_args = " ".join(f'--artifact "{a}"' for a in config.artifacts)
        return f"""@echo off
setlocal

echo =====================================
echo Velociraptor Offline Collector
echo =====================================
echo.

:: Check for administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script requires administrator privileges
    echo Please run as Administrator
    pause
    exit /b 1
)

:: Create output directory
set OUTPUT_DIR=%~dp0collection_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set OUTPUT_DIR=%OUTPUT_DIR: =0%
mkdir "%OUTPUT_DIR%"

echo Starting collection...
echo Output directory: %OUTPUT_DIR%
echo.

:: Download Velociraptor if not present
if not exist "%~dp0velociraptor.exe" (
    echo Downloading Velociraptor...
    curl -L -o "%~dp0velociraptor.exe" https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-windows-amd64.exe
)

:: Run collection
"%~dp0velociraptor.exe" collect --output "%OUTPUT_DIR%" {artifacts_args}

echo.
echo =====================================
echo Collection complete!
echo Output saved to: %OUTPUT_DIR%
echo =====================================
pause
"""

    def _generate_powershell_script(self, config: CollectorConfig) -> str:
        """Generate PowerShell collection script."""
        artifacts = ", ".join(f'"{a}"' for a in config.artifacts)
        return f"""#Requires -RunAsAdministrator

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Velociraptor Offline Collector" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

$OutputDir = Join-Path $PSScriptRoot ("collection_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

Write-Host "Starting collection..." -ForegroundColor Yellow
Write-Host "Output directory: $OutputDir"
Write-Host ""

$VelociraptorPath = Join-Path $PSScriptRoot "velociraptor.exe"

# Download Velociraptor if not present
if (-not (Test-Path $VelociraptorPath)) {{
    Write-Host "Downloading Velociraptor..." -ForegroundColor Yellow
    $DownloadUrl = "https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-windows-amd64.exe"
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $VelociraptorPath
}}

# Run collection
$Artifacts = @({artifacts})
$ArtifactArgs = $Artifacts | ForEach-Object {{ "--artifact", $_ }}

& $VelociraptorPath collect --output $OutputDir @ArtifactArgs

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Collection complete!" -ForegroundColor Green
Write-Host "Output saved to: $OutputDir" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
"""

    def _generate_linux_script(self, config: CollectorConfig) -> str:
        """Generate Linux shell collection script."""
        artifacts_args = " ".join(f'--artifact "{a}"' for a in config.artifacts)
        return f"""#!/bin/bash

echo "====================================="
echo "Velociraptor Offline Collector"
echo "====================================="
echo ""

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script requires root privileges"
    echo "Please run with sudo"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/collection_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "Starting collection..."
echo "Output directory: $OUTPUT_DIR"
echo ""

VELOCIRAPTOR="$SCRIPT_DIR/velociraptor"

# Download Velociraptor if not present
if [ ! -f "$VELOCIRAPTOR" ]; then
    echo "Downloading Velociraptor..."
    curl -L -o "$VELOCIRAPTOR" https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-linux-amd64
    chmod +x "$VELOCIRAPTOR"
fi

# Run collection
"$VELOCIRAPTOR" collect --output "$OUTPUT_DIR" {artifacts_args}

echo ""
echo "====================================="
echo "Collection complete!"
echo "Output saved to: $OUTPUT_DIR"
echo "====================================="
"""

    def _generate_macos_script(self, config: CollectorConfig) -> str:
        """Generate macOS shell collection script."""
        artifacts_args = " ".join(f'--artifact "{a}"' for a in config.artifacts)
        return f"""#!/bin/bash

echo "====================================="
echo "Velociraptor Offline Collector"
echo "====================================="
echo ""

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script requires root privileges"
    echo "Please run with sudo"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/collection_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "Starting collection..."
echo "Output directory: $OUTPUT_DIR"
echo ""

VELOCIRAPTOR="$SCRIPT_DIR/velociraptor"

# Download Velociraptor if not present
if [ ! -f "$VELOCIRAPTOR" ]; then
    echo "Downloading Velociraptor..."
    curl -L -o "$VELOCIRAPTOR" https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-darwin-amd64
    chmod +x "$VELOCIRAPTOR"
fi

# Run collection
"$VELOCIRAPTOR" collect --output "$OUTPUT_DIR" {artifacts_args}

echo ""
echo "====================================="
echo "Collection complete!"
echo "Output saved to: $OUTPUT_DIR"
echo "====================================="
"""

    def _generate_windows_instructions(self, config: CollectorConfig) -> str:
        """Generate Windows usage instructions."""
        return f"""Velociraptor Offline Collector - Windows
========================================

This package collects forensic artifacts from Windows systems without
requiring network connectivity to a Velociraptor server.

ARTIFACTS COLLECTED:
{chr(10).join('  - ' + a for a in config.artifacts)}

USAGE:
1. Extract this ZIP to the target system
2. Right-click "collect.bat" and select "Run as Administrator"
   OR
   Open PowerShell as Administrator and run: .\\collect.ps1
3. Wait for collection to complete
4. Retrieve the "collection_*" folder with results

OUTPUT:
Collection results will be saved to a timestamped folder in the
same directory as the scripts.

NOTES:
- Administrator privileges required
- Collection may take several minutes depending on artifacts
- Do not interrupt the collection process
- Keep the output folder secure - it may contain sensitive data
{f"{chr(10)}OUTPUT ENCRYPTION:{chr(10)}Output will be encrypted with the provided password." if config.encrypt_output else ""}
"""

    def _generate_linux_instructions(self, config: CollectorConfig) -> str:
        """Generate Linux usage instructions."""
        return f"""Velociraptor Offline Collector - Linux
======================================

This package collects forensic artifacts from Linux systems without
requiring network connectivity to a Velociraptor server.

ARTIFACTS COLLECTED:
{chr(10).join('  - ' + a for a in config.artifacts)}

USAGE:
1. Extract this archive to the target system:
   tar -xzf velociraptor-collector-linux-*.tar.gz
2. Run the collection script as root:
   sudo ./collect.sh
3. Wait for collection to complete
4. Retrieve the "collection_*" folder with results

OUTPUT:
Collection results will be saved to a timestamped folder in the
same directory as the script.

NOTES:
- Root privileges required
- Collection may take several minutes depending on artifacts
- Do not interrupt the collection process
- Keep the output folder secure - it may contain sensitive data
"""

    def _generate_macos_instructions(self, config: CollectorConfig) -> str:
        """Generate macOS usage instructions."""
        return f"""Velociraptor Offline Collector - macOS
======================================

This package collects forensic artifacts from macOS systems without
requiring network connectivity to a Velociraptor server.

ARTIFACTS COLLECTED:
{chr(10).join('  - ' + a for a in config.artifacts)}

USAGE:
1. Extract this archive to the target system:
   tar -xzf velociraptor-collector-macos-*.tar.gz
2. Run the collection script as root:
   sudo ./collect.sh
3. Wait for collection to complete
4. Retrieve the "collection_*" folder with results

OUTPUT:
Collection results will be saved to a timestamped folder in the
same directory as the script.

NOTES:
- Root privileges required
- You may need to allow the binary in Security & Privacy settings
- Collection may take several minutes depending on artifacts
- Do not interrupt the collection process
- Keep the output folder secure - it may contain sensitive data
"""

    async def generate(
        self,
        config: CollectorConfig,
        target_os: str = "windows",
    ) -> GeneratedCollector:
        """Generate an offline collector for the specified OS.

        Args:
            config: Collector configuration
            target_os: Target operating system (windows, linux, macos)

        Returns:
            Generated collector details
        """
        generators = {
            "windows": self.generate_windows_collector,
            "linux": self.generate_linux_collector,
            "macos": self.generate_macos_collector,
            "darwin": self.generate_macos_collector,
        }

        generator = generators.get(target_os.lower())
        if not generator:
            raise ValueError(f"Unsupported target OS: {target_os}")

        return await generator(config)

    @classmethod
    def get_artifact_set(cls, set_name: str) -> list[str]:
        """Get a predefined artifact set.

        Args:
            set_name: Name of the artifact set

        Returns:
            List of artifact names

        Raises:
            ValueError: If set name is not recognized
        """
        if set_name not in cls.ARTIFACT_SETS:
            available = ", ".join(cls.ARTIFACT_SETS.keys())
            raise ValueError(f"Unknown artifact set '{set_name}'. Available: {available}")
        return cls.ARTIFACT_SETS[set_name].copy()
