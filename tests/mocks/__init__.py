"""Mock implementations for megaraptor-mcp tests.

Provides mock objects for:
- Velociraptor gRPC server
- Docker client
- SSH connections
"""

try:
    from .mock_velociraptor import MockVelociraptorServer, MockVelociraptorClient

    __all__ = ["MockVelociraptorServer", "MockVelociraptorClient"]
except ImportError:
    # Allow import to succeed even if dependencies are missing
    __all__ = []
