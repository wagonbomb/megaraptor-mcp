"""
Error handling utilities for Velociraptor MCP server.

Provides validators, gRPC error mapping, and VQL error hint extraction.
"""

from .validators import (
    validate_client_id,
    validate_limit,
    validate_hunt_id,
    validate_flow_id,
    validate_vql_syntax_basics,
)
from .grpc_handlers import (
    is_retryable_grpc_error,
    map_grpc_error,
)
from .vql_helpers import (
    extract_vql_error_hint,
)

__all__ = [
    # Validators
    "validate_client_id",
    "validate_limit",
    "validate_hunt_id",
    "validate_flow_id",
    "validate_vql_syntax_basics",
    # gRPC handlers
    "is_retryable_grpc_error",
    "map_grpc_error",
    # VQL helpers
    "extract_vql_error_hint",
]
