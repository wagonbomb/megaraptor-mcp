"""JSON Schema registry for MCP tool output validation."""

from typing import Optional
from .base_schemas import (
    LIST_CLIENTS_SCHEMA,
    GET_CLIENT_INFO_SCHEMA,
    LIST_ARTIFACTS_SCHEMA,
    COLLECT_ARTIFACT_SCHEMA,
    RUN_VQL_SCHEMA,
    LIST_HUNTS_SCHEMA,
    CREATE_HUNT_SCHEMA,
    LIST_FLOWS_SCHEMA,
    GET_FLOW_STATUS_SCHEMA,
    DEPLOYMENT_STATUS_SCHEMA,
    LIST_DEPLOYMENTS_SCHEMA,
)
from .os_artifacts import (
    LINUX_SYS_USERS_SCHEMA,
    WINDOWS_SYSTEM_SERVICES_SCHEMA,
    WINDOWS_REGISTRY_USERASSIST_SCHEMA,
)

_SCHEMA_REGISTRY = {
    # Client tools
    "list_clients": LIST_CLIENTS_SCHEMA,
    "get_client_info": GET_CLIENT_INFO_SCHEMA,
    # label_client and quarantine_client have variable output, skip schema

    # Artifact tools
    "list_artifacts": LIST_ARTIFACTS_SCHEMA,
    # get_artifact returns full artifact definition, too variable for schema
    "collect_artifact": COLLECT_ARTIFACT_SCHEMA,

    # VQL tools
    "run_vql": RUN_VQL_SCHEMA,
    # vql_help returns text, not JSON

    # Hunt tools
    "list_hunts": LIST_HUNTS_SCHEMA,
    "create_hunt": CREATE_HUNT_SCHEMA,
    # get_hunt_results, modify_hunt have variable output

    # Flow tools
    "list_flows": LIST_FLOWS_SCHEMA,
    "get_flow_status": GET_FLOW_STATUS_SCHEMA,
    # get_flow_results, cancel_flow have variable output

    # Deployment tools
    "get_deployment_status": DEPLOYMENT_STATUS_SCHEMA,
    "list_deployments": LIST_DEPLOYMENTS_SCHEMA,
    # Most deployment tools have variable output
}


def get_tool_schema(tool_name: str) -> Optional[dict]:
    """Get JSON schema for a tool's output.

    Returns None if no schema defined (validation skipped).
    """
    return _SCHEMA_REGISTRY.get(tool_name)
