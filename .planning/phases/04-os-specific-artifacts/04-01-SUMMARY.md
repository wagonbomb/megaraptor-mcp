# Plan 04-01 Summary: Linux Artifact Testing

**Completed:** 2026-01-26
**Duration:** ~5 min
**Status:** All tasks complete

## What Was Built

### Task 1: TargetRegistry Enhancement
- Added `get_by_artifact()` method to TargetRegistry class
- Maps artifact names to OS capabilities:
  - `Linux.*` → Linux target
  - `Windows.Registry.*` → Windows target with registry capability
  - `Windows.*` → Windows target
  - `Generic.*` → Any target
- Added `windows_services` to WINDOWS_CAPABILITIES list
- Commit: `7037246`

### Task 2: OS-Specific Schemas
- Created `tests/integration/schemas/os_artifacts.py` with minimal schemas
- LINUX_SYS_USERS_SCHEMA requires only `User` field (minimal, version-resilient)
- WINDOWS_SYSTEM_SERVICES_SCHEMA requires only `Name` field
- WINDOWS_REGISTRY_USERASSIST_SCHEMA has no required fields (may return empty)
- Updated `__init__.py` to export new schemas
- Commit: `0b3309d`

### Task 3: Linux.Sys.Users Test
- Created `tests/integration/test_os_artifacts_linux.py`
- `test_linux_sys_users_collection`: Collects and validates user data from Linux container
- `test_target_registry_get_by_artifact`: Validates artifact-to-target mapping
- Uses flexible field matching for version resilience
- Commit: `f4cd562`

## Verification

```
pytest tests/integration/test_os_artifacts_linux.py -v
2 passed in 4.04s
```

## Files Modified

| File | Change |
|------|--------|
| `tests/integration/helpers/target_registry.py` | Added get_by_artifact() method |
| `tests/integration/schemas/os_artifacts.py` | New file with OS-specific schemas |
| `tests/integration/schemas/__init__.py` | Export new schemas |
| `tests/integration/test_os_artifacts_linux.py` | New file with Linux artifact tests |

## Decisions Made

- **Minimal schema validation**: Only require most critical field per artifact to avoid version brittleness
- **Flexible field matching**: Check multiple field name variants (User/user/Username) for version resilience
- **No additionalProperties restriction**: Allow new fields across Velociraptor versions

## Requirements Validated

- OSART-01: Linux.Sys.Users artifact collection and validation works ✓
- OSART-04: TargetRegistry selects appropriate test targets based on artifact capabilities ✓
- OSART-05: OS-specific validation schemas for complex artifact types ✓ (partial - Linux schemas)
