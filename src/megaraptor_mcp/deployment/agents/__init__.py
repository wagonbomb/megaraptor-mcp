"""
Agent deployment infrastructure.

Provides tools for generating agent installers, offline collectors,
and pushing agents via WinRM/SSH.
"""

from .installer_gen import InstallerGenerator, InstallerType
from .offline_collector import OfflineCollectorGenerator
from .winrm_deployer import WinRMDeployer
from .ssh_deployer import SSHDeployer
from .ansible_gen import AnsiblePlaybookGenerator

__all__ = [
    "InstallerGenerator",
    "InstallerType",
    "OfflineCollectorGenerator",
    "WinRMDeployer",
    "SSHDeployer",
    "AnsiblePlaybookGenerator",
]
