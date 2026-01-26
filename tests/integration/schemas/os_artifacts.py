"""OS-specific artifact JSON schemas for validation.

Schemas validate only critical fields - keep minimal to avoid brittleness.
Do NOT use additionalProperties: false - allow new fields across versions.

Field types accept both string and integer where VQL may return either.
"""

# Linux artifact schemas

LINUX_SYS_USERS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["User"],  # Only most critical field required
        "properties": {
            "User": {"type": "string"},
            "Uid": {"type": ["string", "integer"]},  # May be string or int
            "Gid": {"type": ["string", "integer"]},
            "Homedir": {"type": "string"},
            "Shell": {"type": "string"},
            "Description": {"type": "string"},
        }
    }
}


# Windows artifact schemas (for future Windows target testing)

WINDOWS_SYSTEM_SERVICES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["Name"],  # Only most critical field required
        "properties": {
            "Name": {"type": "string"},
            "DisplayName": {"type": "string"},
            "State": {"type": "string"},
            "PathName": {"type": "string"},
            "ServiceDll": {"type": "string"},
            "AbsoluteExePath": {"type": "string"},
        }
    }
}


WINDOWS_REGISTRY_USERASSIST_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        # UserAssist may return empty results - no required fields
        # When results exist, validate structure
        "properties": {
            "_KeyPath": {"type": "string"},
            "Name": {"type": "string"},  # ROT13-decoded application name
            "User": {"type": "string"},
            "LastExecution": {"type": "string"},  # Timestamp string
            "NumberOfExecutions": {"type": ["integer", "string"]},
        }
    }
}
