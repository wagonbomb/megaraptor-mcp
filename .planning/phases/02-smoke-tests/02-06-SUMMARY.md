---
phase: 02-smoke-tests
plan: 06
subsystem: testing
tags: [vql, artifacts, smoke-tests, source-function, linux-pslist]

# Dependency graph
requires:
  - phase: 02-05
    provides: FastMCP migration with working MCP tool registration
provides:
  - Fixed artifact collection VQL using proper source() syntax
  - Linux.Sys.Pslist artifact for Linux container testing
  - MCP tool smoke tests with proper config injection
  - 100% smoke test pass rate (75/75 tests)
affects: [03-phase-name, future-artifact-tests]

# Tech tracking
tech-stack:
  added: []
  patterns: [source-vql-syntax, velociraptor-config-injection]

key-files:
  created: []
  modified:
    - tests/integration/test_smoke_artifacts.py
    - tests/integration/test_smoke_mcp_tools.py

key-decisions:
  - "source() VQL requires artifact + source params, not just artifact name"
  - "Use Linux.Sys.Pslist for Linux containers (Generic.System.Pslist doesn't exist in 0.75.x)"
  - "Inject VELOCIRAPTOR_CONFIG_PATH env var via fixture for MCP tool tests"
  - "Deployment tools expected to fail gracefully with 'Deployment not found'"

patterns-established:
  - "source() VQL pattern: source(client_id, flow_id, artifact, source) for multi-source artifacts"
  - "Config injection pattern: autouse fixture sets VELOCIRAPTOR_CONFIG_PATH before tool invocation"
  - "Graceful failure handling: deployment tools return error strings, not exceptions"

# Metrics
duration: 8min
completed: 2026-01-25
---

# Phase 02 Plan 06: Gap Closure - Artifact Collection Fixes Summary

**Fixed artifact collection VQL source() syntax and MCP tool config injection to achieve 100% smoke test pass rate**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-01-25T11:00:00Z
- **Completed:** 2026-01-25T11:08:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Fixed Generic.Client.Info artifact test by using proper source() VQL syntax
- Replaced non-existent Generic.System.Pslist with Linux.Sys.Pslist for Linux containers
- Added config injection fixture for MCP tool smoke tests
- Achieved 100% smoke test pass rate (75/75 tests passing)

## Task Commits

Each task was committed atomically:

1. **Task 1-2: Fix artifact collection VQL** - `a54b4a3` (fix)
   - Fixed source() to use artifact='Generic.Client.Info', source='BasicInformation'
   - Renamed test_generic_system_pslist to test_process_list_artifact
   - Changed artifact from Generic.System.Pslist to Linux.Sys.Pslist

2. **Task 3: Fix MCP tool smoke tests** - `2ed7e56` (fix)
   - Added set_velociraptor_config fixture to inject VELOCIRAPTOR_CONFIG_PATH
   - Updated deployment tool graceful failure list

## Files Created/Modified
- `tests/integration/test_smoke_artifacts.py` - Fixed VQL source() syntax and artifact names
- `tests/integration/test_smoke_mcp_tools.py` - Added config injection fixture

## Decisions Made

1. **source() VQL syntax** - The source() VQL function requires both `artifact` and `source` parameters when artifacts have multiple sources. For Generic.Client.Info, the correct call is `source(client_id, flow_id, artifact='Generic.Client.Info', source='BasicInformation')`, not just `source(artifact='Generic.Client.Info')`.

2. **Linux process list artifact** - Generic.System.Pslist does not exist in Velociraptor 0.75.x. Linux containers use Linux.Sys.Pslist instead. Windows/macOS will have their own platform-specific artifacts (Windows.System.Pslist, MacOS.Sys.Pslist) to be tested in Phase 4.

3. **Config injection pattern** - MCP tools use get_client() which loads config from VELOCIRAPTOR_CONFIG_PATH environment variable. Added autouse fixture to set this before tool invocation and reset the global client after.

4. **Deployment tool handling** - All 18 deployment tools are expected to fail with "Deployment not found" in the test environment since no actual deployment infrastructure exists. These graceful failures are acceptable for smoke tests.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

1. **VQL source() returning empty results** - Diagnostic revealed that source() was returning empty because artifacts with multiple sources require specifying which source to query. The flow showed `artifacts_with_results: ['Generic.Client.Info/BasicInformation', 'Generic.Client.Info/DetailedInfo', 'Generic.Client.Info/LinuxInfo']` which indicated the need for source parameter.

2. **Missing artifact** - Generic.System.Pslist is not a built-in artifact in Velociraptor 0.75.x. Discovered via artifact_definitions() query that Linux.Sys.Pslist is the correct artifact for Linux process enumeration.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 75 smoke tests pass (100% pass rate)
- VQL, resource, MCP tool, and artifact tests all verified
- Ready for Phase 3 planning
- Phase 4 will need to handle Windows/macOS-specific artifacts

---
*Phase: 02-smoke-tests*
*Completed: 2026-01-25*
