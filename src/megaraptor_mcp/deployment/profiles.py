"""
Deployment profiles for different use cases.

Profiles define deployment characteristics such as auto-destroy timers,
resource allocation, and security settings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DeploymentTarget(Enum):
    """Supported deployment targets."""
    DOCKER = "docker"
    BINARY = "binary"
    AWS = "aws"
    AZURE = "azure"


class DeploymentState(Enum):
    """Deployment lifecycle states."""
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DESTROYED = "destroyed"


@dataclass
class DeploymentProfile:
    """Configuration profile for a deployment.

    Attributes:
        name: Profile identifier (rapid, standard, enterprise)
        description: Human-readable description
        auto_destroy_hours: Hours until auto-destruction (None = never)
        default_target: Preferred deployment target
        allowed_targets: List of allowed deployment targets
        max_clients: Maximum number of clients (None = unlimited)
        enable_monitoring: Enable built-in health monitoring
        enable_ssl_pinning: Enforce SSL certificate pinning
        credential_expiry_hours: API credential lifetime (None = never)
        log_retention_days: Days to retain logs
        resource_limits: Resource constraints for containers
    """
    name: str
    description: str
    auto_destroy_hours: Optional[int] = None
    default_target: DeploymentTarget = DeploymentTarget.DOCKER
    allowed_targets: list[DeploymentTarget] = field(default_factory=list)
    max_clients: Optional[int] = None
    enable_monitoring: bool = True
    enable_ssl_pinning: bool = True
    credential_expiry_hours: Optional[int] = None
    log_retention_days: int = 30
    resource_limits: dict = field(default_factory=dict)

    def allows_target(self, target: DeploymentTarget) -> bool:
        """Check if the profile allows a specific deployment target."""
        return target in self.allowed_targets


# Predefined deployment profiles
PROFILES: dict[str, DeploymentProfile] = {
    "rapid": DeploymentProfile(
        name="rapid",
        description="Rapid incident response deployment - auto-destroys after 72 hours",
        auto_destroy_hours=72,
        default_target=DeploymentTarget.DOCKER,
        allowed_targets=[DeploymentTarget.DOCKER],
        max_clients=500,
        enable_monitoring=True,
        enable_ssl_pinning=True,
        credential_expiry_hours=72,
        log_retention_days=7,
        resource_limits={
            "memory": "4g",
            "cpus": "2",
        },
    ),
    "standard": DeploymentProfile(
        name="standard",
        description="Standard deployment for extended investigations",
        auto_destroy_hours=None,
        default_target=DeploymentTarget.DOCKER,
        allowed_targets=[
            DeploymentTarget.DOCKER,
            DeploymentTarget.BINARY,
            DeploymentTarget.AWS,
            DeploymentTarget.AZURE,
        ],
        max_clients=2000,
        enable_monitoring=True,
        enable_ssl_pinning=True,
        credential_expiry_hours=None,
        log_retention_days=30,
        resource_limits={
            "memory": "8g",
            "cpus": "4",
        },
    ),
    "enterprise": DeploymentProfile(
        name="enterprise",
        description="Permanent enterprise infrastructure deployment",
        auto_destroy_hours=None,
        default_target=DeploymentTarget.BINARY,
        allowed_targets=[
            DeploymentTarget.BINARY,
            DeploymentTarget.AWS,
            DeploymentTarget.AZURE,
        ],
        max_clients=None,
        enable_monitoring=True,
        enable_ssl_pinning=True,
        credential_expiry_hours=None,
        log_retention_days=90,
        resource_limits={
            "memory": "16g",
            "cpus": "8",
        },
    ),
}


def get_profile(name: str) -> DeploymentProfile:
    """Get a deployment profile by name.

    Args:
        name: Profile name (rapid, standard, enterprise)

    Returns:
        The deployment profile configuration

    Raises:
        ValueError: If the profile name is not recognized
    """
    if name not in PROFILES:
        available = ", ".join(PROFILES.keys())
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return PROFILES[name]
