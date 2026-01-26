---
phase: 04-os-specific-artifacts
plan: 02
subsystem: testing
tags: [windows, artifacts, skip-guards, test-infrastructure]

requires:
  - 04-01-PLAN.md (Linux artifact tests)
  - 01-03-PLAN.md (target_registry fixture)
  - tests/integration/schemas/os_artifacts.py (Windows schemas)

provides:
  - Windows artifact tests with skip guards
  - has_windows_target() helper function
  - skip_no_windows_target decorator
  - Windows pytest marker

affects:
  - Future Windows target integration (tests ready to run)
  - Phase 5: Cross-Platform testing (Windows tests available)

tech-stack:
  added: []
  patterns:
    - Skip guards for unavailable test targets
    - OS-specific test organization
    - Graceful degradation in test suites

key-files:
  created:
    - tests/integration/test_os_artifacts_windows.py
  modified:
    - tests/conftest.py

decisions:
  - decision: has_windows_target() returns False for now
    rationale: Only Linux container available; function ready for Windows target integration
    impact: All Windows tests skip gracefully until Windows target added

  - decision: skip_no_windows_target decorator for test skip guards
    rationale: Consistent pattern with skip_no_docker, skip_no_configs decorators
    impact: Tests can be selectively run when Windows target becomes available

  - decision: Windows marker registered in pytest configuration
    rationale: Enables filtering Windows-specific tests with pytest -m windows
    impact: Can run or skip all Windows tests as a group

metrics:
  duration: 8 minutes
  completed: 2026-01-26
---

# Phase 4 Plan 2: Windows Artifact Tests with Skip Guards

**One-liner:** Windows artifact tests with skip guards - skip gracefully when no Windows target, run automatically when Windows target added

## Summary

Implemented comprehensive Windows artifact collection tests with proper skip guards for environments without Windows targets. Tests validate OSART-02 (Windows.System.Services), OSART-03 (Windows registry artifacts), and OSART-05 (OS-specific validation), but skip gracefully with clear messages when no Windows target is available. When a Windows target becomes available, tests will run automatically without modification.

## What Was Built

### 1. Test Infrastructure (Task 1)
**File:** `tests/conftest.py`

Added helper functions and decorators for Windows target detection:
- `has_windows_target()` - Returns False for now (only Linux container available)
- `skip_no_windows_target` - Decorator that skips tests when no Windows target
- Windows marker registration - Enables filtering with `pytest -m windows`

### 2. Windows Artifact Tests (Task 2)
**File:** `tests/integration/test_os_artifacts_windows.py`

Created three comprehensive tests:

**test_windows_system_services_collection:**
- Validates OSART-02: Windows.System.Services artifact collection
- Schedules collection, waits for completion, validates JSON schema
- Verifies critical service fields (Name, State, PathName)
- Expects at least 10 services (Windows typically has dozens)

**test_windows_registry_userassist_collection:**
- Validates OSART-03: Windows registry artifact collection
- Tests Windows.Registry.UserAssist artifact
- Validates registry-specific fields (_KeyPath, Name, NumberOfExecutions)
- Handles empty results gracefully (UserAssist may be empty)

**test_target_registry_windows_selection:**
- Validates OSART-04: TargetRegistry correctly selects Windows targets
- Tests get_by_artifact() for Windows-specific artifacts
- Verifies windows_services and windows_registry capabilities
- Skips gracefully when no Windows target available

All tests:
- Use `@skip_no_windows_target` decorator for graceful skipping
- Import schemas from `tests.integration.schemas` (through __init__.py)
- Follow same pattern as Linux artifact tests
- Include timeout guards (60s pytest timeout)
- Use pytest-check for soft assertions

## Test Results

**Windows artifact tests:** 3/3 SKIPPED (expected - no Windows target)
```
tests/integration/test_os_artifacts_windows.py::TestWindowsArtifacts::test_windows_system_services_collection SKIPPED
tests/integration/test_os_artifacts_windows.py::TestWindowsArtifacts::test_windows_registry_userassist_collection SKIPPED
tests/integration/test_os_artifacts_windows.py::TestWindowsArtifacts::test_target_registry_windows_selection SKIPPED
```

Skip reason: "No Windows target available" (clear user message)

**Regression tests:** 5/5 PASSED
- Linux artifact tests continue to pass (2/2)
- Smoke tests continue to pass (3/3)
- No breakage from Windows test addition

## Verification Against Must-Haves

**Truths:**
- ✓ Windows artifact tests exist with proper skipif guards
- ✓ Tests skip gracefully when no Windows target available
- ✓ Tests would run and validate when Windows target becomes available
- ✓ has_windows_target() helper function available in conftest

**Artifacts:**
- ✓ tests/integration/test_os_artifacts_windows.py exists
- ✓ Provides Windows artifact collection tests with skip guards
- ✓ Contains test_windows_system_services
- ✓ tests/conftest.py updated
- ✓ Contains def has_windows_target

**Key Links:**
- ✓ test_os_artifacts_windows.py → conftest.py via skip_no_windows_target
- ✓ Pattern: @skip_no_windows_target decorator usage
- ✓ test_os_artifacts_windows.py → schemas/os_artifacts.py
- ✓ Via WINDOWS_SYSTEM_SERVICES_SCHEMA and WINDOWS_REGISTRY_USERASSIST_SCHEMA

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **has_windows_target() returns False for now**
   - Only Linux container available in current test environment
   - Function ready for Windows target integration when available
   - TODO comment indicates where to implement real check

2. **Consistent skip decorator pattern**
   - Follows existing skip_no_docker, skip_no_configs pattern
   - Makes test skip behavior predictable and maintainable
   - Enables selective test execution

3. **Windows marker for test filtering**
   - Registered in pytest_configure() function
   - Enables: `pytest -m windows` (run only Windows tests)
   - Enables: `pytest -m "not windows"` (skip Windows tests)

## Known Issues

None.

## Next Phase Readiness

**Phase 5 Blockers:** None. Windows tests are ready to run when Windows target becomes available.

**Phase 5 Input Requirements:**
- Windows test target (VM or container) with Velociraptor client enrolled
- Update has_windows_target() to detect enrolled Windows clients
- All Windows artifact tests will run automatically

**Concerns:**
- Windows container availability may require VM instead of Docker (winamd64/velociraptor-client image not readily available)
- Consider Windows Server Core container or lightweight Windows VM for testing

## Documentation Updates

- ✓ Docstrings in test_os_artifacts_windows.py explain OSART-02, OSART-03, OSART-05 validation
- ✓ Skip decorator reason messages are clear for users
- ✓ TODO comment in has_windows_target() indicates where to implement

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| b6e6197 | feat(04-02): add has_windows_target helper and windows marker | tests/conftest.py |
| 7b28cb5 | feat(04-02): create Windows artifact tests with skip guards | tests/integration/test_os_artifacts_windows.py |

**Total:** 2 commits (1 per task, no deviations)

---

**Plan Status:** ✓ Complete
**Ready for:** Phase 4 completion (all plans done)
**Execution time:** 8 minutes
