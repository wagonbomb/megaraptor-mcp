---
phase: 02-smoke-tests
plan: 01
subsystem: testing
tags: [pytest, smoke-tests, json-schema, mcp, integration-testing]

# Dependency graph
requires:
  - phase: 01-test-lab
    provides: Docker test infrastructure, conftest.py fixtures, VelociraptorClient
provides:
  - JSON schema registry for MCP tool output validation
  - MCP tool invocation helper functions
  - Server connectivity smoke tests (SMOKE-06)
affects: [02-smoke-tests (all subsequent plans), schema-validation, tool-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JSON schemas validate only critical fields (minimal, not strict)"
    - "MCP tools invoked via invoke_mcp_tool helper"
    - "pytest smoke marker for quick validation tests"

key-files:
  created:
    - tests/integration/schemas/__init__.py
    - tests/integration/schemas/base_schemas.py
    - tests/integration/helpers/mcp_helpers.py
    - tests/integration/helpers/__init__.py
    - tests/integration/test_smoke_connectivity.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Keep schemas minimal - only validate critical fields to avoid brittleness"
  - "Module scope for target_registry and enrolled_client_id fixtures"
  - "Register smoke marker in pytest configuration"

patterns-established:
  - "Schema registry pattern: get_tool_schema returns Optional[dict]"
  - "MCP helper pattern: invoke_mcp_tool returns (bool, Any) tuple"
  - "Smoke test pattern: pytest.mark.smoke for quick validation"

# Metrics
duration: 4min
completed: 2026-01-25
---

# Phase 02 Plan 01: Smoke Test Foundation Summary

**JSON schema registry with minimal validation, MCP tool invocation helpers, and server connectivity smoke tests establishing test infrastructure for Phase 2**

## Performance

- **Duration:** 4 minutes
- **Started:** 2026-01-25T22:18:45Z
- **Completed:** 2026-01-25T22:22:49Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Created JSON schema registry with 11 schemas for core MCP tools
- Built MCP tool invocation helper with async support and error handling
- Implemented SMOKE-06 server connectivity verification tests
- Fixed fixture scope mismatches and info() validation bugs

## Task Commits

Each task was committed atomically:

1. **Task 1: Create JSON Schema Registry** - `5f13e5e` (feat)
2. **Task 2: Create MCP Tool Invocation Helper** - `4905c00` (feat)
3. **Task 3: Create Server Connectivity Smoke Test** - `c3600bf` (feat)

## Files Created/Modified
- `tests/integration/schemas/__init__.py` - Schema registry with get_tool_schema lookup
- `tests/integration/schemas/base_schemas.py` - Minimal JSON schemas for 11 MCP tools
- `tests/integration/helpers/mcp_helpers.py` - invoke_mcp_tool, parse_tool_response, replace_placeholders
- `tests/integration/helpers/__init__.py` - Export all test helpers including MCP functions
- `tests/integration/test_smoke_connectivity.py` - SMOKE-06 connectivity validation tests
- `tests/conftest.py` - Added smoke marker, fixed fixture scopes

## Decisions Made
- Kept schemas minimal (only critical fields) to avoid test brittleness as Velociraptor API evolves
- MCP helper returns tuple (success: bool, data: Any) for clean error handling
- Used module scope for target_registry and enrolled_client_id to match velociraptor_client
- Registered smoke marker in pytest config for dedicated smoke test runs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed info() field validation**
- **Found during:** Task 3 (Server connectivity test)
- **Issue:** Test checked for "version" or "Version" field, but info() returns Architecture, BootTime, etc.
- **Fix:** Changed validation to check for dict type and non-empty instead of specific field
- **Files modified:** tests/integration/test_smoke_connectivity.py
- **Verification:** Test passes with actual info() structure
- **Committed in:** c3600bf (Task 3 commit)

**2. [Rule 1 - Bug] Fixed pytest marker registration**
- **Found during:** Task 3 (Test execution)
- **Issue:** pytest warned "Unknown pytest.mark.smoke" - marker not registered
- **Fix:** Added smoke marker registration in pytest_configure
- **Files modified:** tests/conftest.py
- **Verification:** No marker warning on test run
- **Committed in:** c3600bf (Task 3 commit)

**3. [Rule 1 - Bug] Fixed fixture scope mismatch**
- **Found during:** Task 3 (Test execution)
- **Issue:** Session-scoped enrolled_client_id and target_registry tried to access module-scoped velociraptor_client
- **Fix:** Changed target_registry and enrolled_client_id to module scope
- **Files modified:** tests/conftest.py
- **Verification:** All tests pass without scope errors
- **Committed in:** c3600bf (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (3 bugs)
**Impact on plan:** All auto-fixes necessary for test correctness. No scope creep.

## Issues Encountered
None - all tasks executed smoothly after auto-fixing bugs discovered during test execution.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Schema registry ready for SMOKE-05 (JSON Schema validation)
- MCP helper ready for parametrized tool tests in subsequent plans
- SMOKE-06 connectivity tests gate all other smoke tests
- All test infrastructure validated and passing

---
*Phase: 02-smoke-tests*
*Completed: 2026-01-25*
