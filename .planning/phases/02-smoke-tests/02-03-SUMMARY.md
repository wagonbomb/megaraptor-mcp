---
phase: 02-smoke-tests
plan: 03
subsystem: testing
tags: [pytest, smoke-tests, velociraptor, artifacts, vql, pytest-check, pytest-timeout]

# Dependency graph
requires:
  - phase: 02-01
    provides: wait_for_flow_completion helper, smoke marker registration, enrolled_client_id fixture
provides:
  - Artifact collection smoke tests for Generic.Client.Info (SMOKE-02)
  - Artifact collection smoke tests for Generic.System.Pslist (SMOKE-03)
  - Flexible field name validation for cross-version compatibility
affects: [02-04, artifact-testing, integration-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Flexible field name matching for Velociraptor version compatibility"
    - "Flow completion waiting pattern for artifact collection tests"
    - "pytest.mark.timeout(60) for long-running artifact tests"

key-files:
  created:
    - tests/integration/test_smoke_artifacts.py
  modified: []

key-decisions:
  - "Use flexible field name matching (e.g., 'Hostname' or 'hostname' or 'Fqdn') to support multiple Velociraptor versions"
  - "Wait for artifact completion in smoke tests (exception to general smoke test rule) because SMOKE-02/03 specifically require validation of artifact results"
  - "Apply 30s timeout to individual flows plus 60s pytest timeout to test class for defense in depth"

patterns-established:
  - "Artifact smoke tests schedule collection, wait for completion, and validate structure"
  - "Use pytest-check for multiple field validations to show complete picture on failure"
  - "List available fields in error messages for debugging field name mismatches"

# Metrics
duration: 3min
completed: 2026-01-25
---

# Phase 2 Plan 03: Artifact Collection Smoke Tests Summary

**Generic.Client.Info and Generic.System.Pslist smoke tests with flexible field validation and flow completion waiting**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-25T22:25:55Z
- **Completed:** 2026-01-25T22:28:49Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Created artifact collection smoke tests for SMOKE-02 (Generic.Client.Info) and SMOKE-03 (Generic.System.Pslist)
- Implemented flexible field name matching to support different Velociraptor versions
- Integrated with wait_for_flow_completion helper from Phase 1 for robust async testing
- Applied pytest-timeout markers to prevent hanging on slow artifact collections

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Generic.Client.Info Smoke Test** - `8ddeb39` (feat)
2. **Task 2: Add pytest-timeout to test markers** - `81f21db` (chore)

## Files Created/Modified

- `tests/integration/test_smoke_artifacts.py` - Smoke tests for Generic.Client.Info and Generic.System.Pslist artifact collections with flexible field validation

## Decisions Made

**1. Flexible field name matching for version compatibility**
- Rationale: Velociraptor field names vary across versions and platforms (e.g., "Hostname" vs "hostname" vs "Fqdn")
- Implementation: Check multiple possible field names with `any(k in info for k in ["Hostname", "hostname", "Fqdn"])`
- Impact: Tests work across Velociraptor versions without brittle field name assumptions

**2. Wait for artifact completion in smoke tests**
- Rationale: SMOKE-02 and SMOKE-03 explicitly require validating artifact result structures, not just callability
- Implementation: Use wait_for_flow_completion helper with 30s timeout
- Impact: These artifact tests are slower than typical smoke tests (~10-15s vs <1s), but necessary for validation requirements

**3. Defense-in-depth timeout strategy**
- Rationale: Prevent hanging tests at multiple levels
- Implementation: 30s timeout on wait_for_flow_completion + 60s pytest.mark.timeout on test class
- Impact: Tests fail fast if artifact collection hangs, preventing CI pipeline delays

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Task 2 verification revealed that pytest markers were already properly configured:
- `smoke` marker registered in conftest.py from plan 02-01
- `timeout` marker provided by pytest-timeout plugin from Phase 1

No changes needed for Task 2.

## Next Phase Readiness

**Ready for next smoke test phases:**
- Artifact collection pattern established for other artifact tests
- wait_for_flow_completion helper proven reliable
- Flexible validation approach can be applied to other Velociraptor VQL results

**No blockers.**

---
*Phase: 02-smoke-tests*
*Completed: 2026-01-25*
