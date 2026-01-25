"""Target registry for capability-based test client selection.

Provides a registry of enrolled Velociraptor clients and their capabilities
to enable OS-specific and capability-specific test targeting.
"""

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from megaraptor_mcp.client import VelociraptorClient


@dataclass
class TestTarget:
    """Represents a test target client with its capabilities."""

    client_id: str
    hostname: str
    os_type: str  # "linux", "windows", "darwin"
    os_version: str = ""
    capabilities: List[str] = field(default_factory=list)
    container_name: Optional[str] = None

    def has_capability(self, capability: str) -> bool:
        """Check if target has a specific capability."""
        return capability in self.capabilities

    def is_os(self, os_type: str) -> bool:
        """Check if target matches OS type (case-insensitive)."""
        return self.os_type.lower() == os_type.lower()


class TargetRegistry:
    """Registry of available test targets with their capabilities.

    Discovers enrolled Velociraptor clients and tracks their OS type
    and supported capabilities for test targeting.

    Usage:
        registry = TargetRegistry()
        registry.discover_targets(client)

        linux_target = registry.get_by_os("linux")
        windows_target = registry.get_by_capability("windows_registry")
    """

    # Standard capabilities by OS
    LINUX_CAPABILITIES = [
        "generic_artifacts",
        "linux_filesystem",
        "linux_processes",
        "linux_users",
        "linux_network",
    ]

    WINDOWS_CAPABILITIES = [
        "generic_artifacts",
        "windows_registry",
        "windows_prefetch",
        "windows_eventlog",
        "windows_filesystem",
        "windows_processes",
    ]

    DARWIN_CAPABILITIES = [
        "generic_artifacts",
        "darwin_filesystem",
        "darwin_processes",
    ]

    def __init__(self):
        self.targets: List[TestTarget] = []

    def register_target(
        self,
        client_id: str,
        hostname: str,
        os_type: str,
        os_version: str = "",
        capabilities: Optional[List[str]] = None,
        container_name: Optional[str] = None,
    ) -> TestTarget:
        """Register a test target manually.

        Args:
            client_id: Velociraptor client ID (C.xxx)
            hostname: Client hostname
            os_type: Operating system type (linux, windows, darwin)
            os_version: OS version string
            capabilities: List of capabilities (auto-detected if None)
            container_name: Docker container name if applicable

        Returns:
            The registered TestTarget
        """
        if capabilities is None:
            capabilities = self._infer_capabilities(os_type)

        target = TestTarget(
            client_id=client_id,
            hostname=hostname,
            os_type=os_type.lower(),
            os_version=os_version,
            capabilities=capabilities,
            container_name=container_name,
        )
        self.targets.append(target)
        return target

    def discover_targets(self, client: "VelociraptorClient") -> List[TestTarget]:
        """Discover and register all enrolled clients.

        Queries Velociraptor for enrolled clients and registers them
        with auto-detected capabilities based on OS.

        Args:
            client: VelociraptorClient instance

        Returns:
            List of discovered TestTargets
        """
        discovered = []

        try:
            clients = client.query(
                "SELECT client_id, os_info, agent_information FROM clients()"
            )

            for client_data in clients:
                client_id = client_data.get("client_id")
                if not client_id:
                    continue

                os_info = client_data.get("os_info", {})
                hostname = os_info.get("hostname", os_info.get("fqdn", "unknown"))
                os_type = os_info.get("system", "linux").lower()
                os_version = os_info.get("platform_version", "")

                target = self.register_target(
                    client_id=client_id,
                    hostname=hostname,
                    os_type=os_type,
                    os_version=os_version,
                )
                discovered.append(target)

        except Exception as e:
            print(f"Target discovery warning: {e}")

        return discovered

    def get_by_capability(self, capability: str) -> Optional[TestTarget]:
        """Get first target with specified capability.

        Args:
            capability: Required capability string

        Returns:
            TestTarget with capability, or None if not found
        """
        for target in self.targets:
            if target.has_capability(capability):
                return target
        return None

    def get_by_os(self, os_type: str) -> Optional[TestTarget]:
        """Get first target with specified OS type.

        Args:
            os_type: OS type (linux, windows, darwin)

        Returns:
            TestTarget with matching OS, or None if not found
        """
        for target in self.targets:
            if target.is_os(os_type):
                return target
        return None

    def get_all_by_os(self, os_type: str) -> List[TestTarget]:
        """Get all targets with specified OS type.

        Args:
            os_type: OS type (linux, windows, darwin)

        Returns:
            List of TestTargets with matching OS
        """
        return [t for t in self.targets if t.is_os(os_type)]

    def get_all_by_capability(self, capability: str) -> List[TestTarget]:
        """Get all targets with specified capability.

        Args:
            capability: Required capability string

        Returns:
            List of TestTargets with capability
        """
        return [t for t in self.targets if t.has_capability(capability)]

    def _infer_capabilities(self, os_type: str) -> List[str]:
        """Infer capabilities based on OS type.

        Args:
            os_type: Operating system type

        Returns:
            List of inferred capabilities
        """
        os_lower = os_type.lower()
        if "linux" in os_lower:
            return self.LINUX_CAPABILITIES.copy()
        elif "windows" in os_lower:
            return self.WINDOWS_CAPABILITIES.copy()
        elif "darwin" in os_lower or "macos" in os_lower:
            return self.DARWIN_CAPABILITIES.copy()
        else:
            return ["generic_artifacts"]

    def __len__(self) -> int:
        return len(self.targets)

    def __bool__(self) -> bool:
        return len(self.targets) > 0
