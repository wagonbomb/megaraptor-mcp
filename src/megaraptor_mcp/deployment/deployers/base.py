"""
Abstract base class for deployment implementations.

Defines the interface that all deployers must implement.
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Any

from ..profiles import DeploymentProfile, DeploymentState, DeploymentTarget


@dataclass
class DeploymentResult:
    """Result of a deployment operation.

    Attributes:
        success: Whether the operation succeeded
        deployment_id: The deployment identifier
        message: Human-readable status message
        server_url: URL to access the server (if applicable)
        api_url: URL for API access (if applicable)
        admin_password: Initial admin password (only shown once)
        error: Error message if failed
        details: Additional deployment details
    """
    success: bool
    deployment_id: str
    message: str
    server_url: Optional[str] = None
    api_url: Optional[str] = None
    admin_password: Optional[str] = None
    error: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        """Convert to dictionary.

        Args:
            include_secrets: Include sensitive data like passwords

        Returns:
            Dictionary representation
        """
        result = {
            "success": self.success,
            "deployment_id": self.deployment_id,
            "message": self.message,
            "server_url": self.server_url,
            "api_url": self.api_url,
            "details": self.details,
        }
        if self.error:
            result["error"] = self.error
        if include_secrets and self.admin_password:
            result["admin_password"] = self.admin_password
        elif self.admin_password:
            result["admin_password"] = "*** REDACTED - Only shown once at creation ***"
        return result


@dataclass
class DeploymentInfo:
    """Information about an existing deployment.

    Attributes:
        deployment_id: Unique identifier
        profile: Deployment profile used
        target: Deployment target type
        state: Current deployment state
        server_url: Server access URL
        api_url: API access URL
        created_at: Creation timestamp
        auto_destroy_at: Scheduled destruction time
        health: Current health status
        version: Velociraptor version
        client_count: Number of connected clients
        metadata: Additional metadata
    """
    deployment_id: str
    profile: str
    target: str
    state: DeploymentState
    server_url: Optional[str]
    api_url: Optional[str]
    created_at: str
    auto_destroy_at: Optional[str]
    health: dict[str, Any] = field(default_factory=dict)
    version: Optional[str] = None
    client_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "deployment_id": self.deployment_id,
            "profile": self.profile,
            "target": self.target,
            "state": self.state.value,
            "server_url": self.server_url,
            "api_url": self.api_url,
            "created_at": self.created_at,
            "auto_destroy_at": self.auto_destroy_at,
            "health": self.health,
            "version": self.version,
            "client_count": self.client_count,
            "metadata": self.metadata,
        }


class BaseDeployer(ABC):
    """Abstract base class for Velociraptor deployers.

    All deployment implementations must inherit from this class and
    implement the required methods.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the deployer.

        Args:
            storage_path: Path for storing deployment data
        """
        self.storage_path = storage_path or self._default_storage_path()
        self.storage_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default_storage_path() -> Path:
        """Get the default storage path."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", "~"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
        return base.expanduser() / "megaraptor-mcp" / "deployments"

    @property
    @abstractmethod
    def target_type(self) -> DeploymentTarget:
        """Return the deployment target type."""
        pass

    @abstractmethod
    async def deploy(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
    ) -> DeploymentResult:
        """Deploy a Velociraptor server.

        Args:
            config: Deployment configuration
            profile: Deployment profile
            certificates: Certificate bundle for TLS

        Returns:
            DeploymentResult with deployment details
        """
        pass

    @abstractmethod
    async def destroy(self, deployment_id: str, force: bool = False) -> DeploymentResult:
        """Destroy a deployment.

        Args:
            deployment_id: The deployment to destroy
            force: Force destruction even if unhealthy

        Returns:
            DeploymentResult indicating success/failure
        """
        pass

    @abstractmethod
    async def get_status(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get the status of a deployment.

        Args:
            deployment_id: The deployment identifier

        Returns:
            DeploymentInfo, or None if not found
        """
        pass

    @abstractmethod
    async def health_check(self, deployment_id: str) -> dict[str, Any]:
        """Perform a health check on a deployment.

        Args:
            deployment_id: The deployment identifier

        Returns:
            Dictionary with health status details
        """
        pass

    def save_deployment_info(self, info: DeploymentInfo) -> None:
        """Save deployment information to disk.

        Args:
            info: Deployment information to save
        """
        deployment_dir = self.storage_path / info.deployment_id
        deployment_dir.mkdir(parents=True, exist_ok=True)
        info_file = deployment_dir / "info.json"
        info_file.write_text(json.dumps(info.to_dict(), indent=2))

    def load_deployment_info(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Load deployment information from disk.

        Args:
            deployment_id: The deployment identifier

        Returns:
            DeploymentInfo, or None if not found
        """
        info_file = self.storage_path / deployment_id / "info.json"
        if not info_file.exists():
            return None

        data = json.loads(info_file.read_text())
        data["state"] = DeploymentState(data["state"])
        return DeploymentInfo(**data)

    def list_deployments(self, target_filter: Optional[DeploymentTarget] = None) -> list[DeploymentInfo]:
        """List all deployments.

        Args:
            target_filter: Only return deployments of this target type

        Returns:
            List of deployment information
        """
        deployments = []
        if not self.storage_path.exists():
            return deployments

        for deployment_dir in self.storage_path.iterdir():
            if not deployment_dir.is_dir():
                continue
            info = self.load_deployment_info(deployment_dir.name)
            if info:
                if target_filter and info.target != target_filter.value:
                    continue
                deployments.append(info)

        return deployments

    def delete_deployment_info(self, deployment_id: str) -> bool:
        """Delete deployment information from disk.

        Args:
            deployment_id: The deployment identifier

        Returns:
            True if deleted, False if not found
        """
        import shutil

        deployment_dir = self.storage_path / deployment_id
        if not deployment_dir.exists():
            return False

        shutil.rmtree(deployment_dir)
        return True

    def _now_iso(self) -> str:
        """Get current UTC time in ISO format."""
        return datetime.now(timezone.utc).isoformat()
