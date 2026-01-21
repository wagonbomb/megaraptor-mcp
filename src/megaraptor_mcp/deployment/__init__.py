"""
Velociraptor deployment infrastructure.

Provides rapid deployment capabilities for Velociraptor servers and agents
during active security incidents.
"""

from .profiles import DeploymentProfile, get_profile, PROFILES

__all__ = [
    "DeploymentProfile",
    "get_profile",
    "PROFILES",
]
