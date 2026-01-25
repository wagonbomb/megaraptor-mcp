---
phase: 01-test-infrastructure
plan: 03
subsystem: testing
tags: [pytest, fixtures, certificate-monitoring, target-registry, test-infrastructure]

# Dependency graph
requires:
  - phase: 01-01
    provides: VelociraptorClient fixture with lifecycle management
provides:
  - TargetRegistry for capability-based test client selection
  - Certificate expiration monitoring preventing x509 errors
  - Session-scoped fixtures for target discovery and cert validation
affects: [01-test-infrastructure, 02-validation, 04-integration-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Capability-based test targeting with OS detection"
    - "Autouse certificate monitoring at session start"
    - "Registry pattern for test target management"

key-files:
  created:
    - tests/integration/helpers/target_registry.py
    - tests/integration/helpers/cert_monitor.py
  modified:
    - tests/integration/helpers/__init__.py
    - tests/conftest.py

key-decisions:
  - "Session-scoped target_registry to discover enrolled clients once per test session"
  - "Autouse certificate check fixture fails fast before cryptic gRPC errors"
  - "Graceful degradation when cryptography library unavailable"

patterns-established:
  - "TestTarget dataclass for representing enrolled clients with capabilities"
  - "OS-based capability inference (Linux, Windows, Darwin)"
  - "Certificate expiration warnings at 30 days, errors at 7 days"

# Metrics
duration: 3min
completed: 2026-01-25
---

# Phase 01 Plan 03: Target Registry and Certificate Expiration Monitoring Summary

**TargetRegistry for OS-specific test targeting and certificate monitoring preventing x509 infrastructure failures**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-25T20:50:32Z
- **Completed:** 2026-01-25T20:53:54Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Created TargetRegistry for capability-based test client selection with OS detection
- Implemented certificate expiration monitoring with configurable warn/error thresholds
- Added session-scoped fixtures for automatic target discovery and cert validation
- Enabled Phase 4 OS-specific artifact testing against appropriate targets

## Task Commits

Each task was committed atomically:

1. **Task 1: Create TargetRegistry for capability-based target selection** - `4b397d8` (feat)
2. **Task 2: Create certificate expiration monitor** - `46bf53f` (feat)
3. **Task 3: Add target_registry and cert check fixtures to conftest.py** - `8770f80` (feat)

## Files Created/Modified
- `tests/integration/helpers/target_registry.py` - TargetRegistry and TestTarget classes for managing enrolled clients
- `tests/integration/helpers/cert_monitor.py` - Certificate expiration checking with graceful degradation
- `tests/integration/helpers/__init__.py` - Updated exports for new modules
- `tests/conftest.py` - Added target_registry, enrolled_client_id, and check_certificate_expiration fixtures

## Decisions Made

**Session-scoped target_registry**: Discovers enrolled clients once per test session to avoid repeated queries. Waits for client enrollment before proceeding, failing with clear skip message if no clients available.

**Autouse certificate check**: Automatically validates certificates at session start (scope="session", autouse=True) to fail fast with actionable error message instead of cryptic gRPC x509 errors mid-test.

**Graceful cryptography handling**: Certificate monitoring works without cryptography library installed (returns True with skip message). This prevents hard dependency for users who don't need cert validation.

**Capability inference by OS**: TestTarget automatically infers capabilities based on OS type (linux_filesystem, windows_registry, etc.) to enable capability-based test targeting in Phase 4.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all imports worked, integration tests passed on first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 4 OS-specific testing:**
- TargetRegistry can select targets by OS type (Linux, Windows, Darwin)
- TargetRegistry can select targets by capability (windows_registry, linux_filesystem, etc.)
- enrolled_client_id fixture provides simple access to any enrolled client

**Infrastructure health monitoring:**
- Certificate expiration checks prevent cryptic failures
- Clear regeneration instructions when certs expire soon
- Supports multiple config formats (server, client, API)

**No blockers or concerns.**

---
*Phase: 01-test-infrastructure*
*Completed: 2026-01-25*
