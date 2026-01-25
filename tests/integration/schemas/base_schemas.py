"""Base JSON schemas for MCP tool output validation.

Schemas validate only critical fields - keep minimal to avoid brittleness.
Do NOT use additionalProperties: false - allow new fields.
"""

# Client tool schemas
LIST_CLIENTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["client_id"],
        "properties": {
            "client_id": {"type": "string", "pattern": "^C\\."},
            "hostname": {"type": "string"},
        }
    }
}

GET_CLIENT_INFO_SCHEMA = {
    "type": "object",
    "required": ["client_id"],
    "properties": {
        "client_id": {"type": "string", "pattern": "^C\\."},
    }
}

# Artifact tool schemas
LIST_ARTIFACTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "type": {"type": "string"},
        }
    }
}

COLLECT_ARTIFACT_SCHEMA = {
    "type": "object",
    "required": ["flow_id"],
    "properties": {
        "flow_id": {"type": "string"},
        "status": {"type": "string"},
    }
}

# VQL tool schemas
RUN_VQL_SCHEMA = {
    "type": "object",
    "required": ["results"],
    "properties": {
        "query": {"type": "string"},
        "row_count": {"type": "integer"},
        "results": {"type": "array"},
    }
}

# Hunt tool schemas
LIST_HUNTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "hunt_id": {"type": "string"},
            "state": {"type": "string"},
        }
    }
}

CREATE_HUNT_SCHEMA = {
    "type": "object",
    "required": ["hunt_id"],
    "properties": {
        "hunt_id": {"type": "string"},
        "status": {"type": "string"},
    }
}

# Flow tool schemas
LIST_FLOWS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "flow_id": {"type": "string"},
            "state": {"type": "string"},
        }
    }
}

GET_FLOW_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "flow_id": {"type": "string"},
        "state": {"type": "string"},
        "client_id": {"type": "string"},
    }
}

# Deployment tool schemas (minimal - many return similar structure)
DEPLOYMENT_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "deployment_id": {"type": "string"},
        "state": {"type": "string"},
    }
}

LIST_DEPLOYMENTS_SCHEMA = {
    "type": "object",
    "required": ["deployments"],
    "properties": {
        "count": {"type": "integer"},
        "deployments": {"type": "array"},
    }
}
