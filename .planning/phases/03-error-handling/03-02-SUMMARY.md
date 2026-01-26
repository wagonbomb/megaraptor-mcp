---
phase: 03-error-handling
plan: 02
subsystem: error-handling
tags: [grpc, validation, error-handling, clients, artifacts]

# Dependency graph
requires:
  - phase: 03-01
    provides: Validation functions and gRPC error mapping utilities
provides:
  - Client tools (list_clients, get_client_info, label_client, quarantine_client) with full error handling
  - Artifact tools (list_artifacts, get_artifact, collect_artifact) with full error handling
  - Integration tests verifying error handling behavior
affects: [03-03, 03-04, vql, flows, hunts]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Input validation at function entry before any operations
    - gRPC error wrapping with map_grpc_error for user-friendly messages
    - 404-style errors with actionable hints for missing resources
    - Generic exception handler without exposing stack traces

key-files:
  created:
    - tests/integration/test_error_handling_clients_artifacts.py
  modified:
    - src/megaraptor_mcp/tools/clients.py
    - src/megaraptor_mcp/tools/artifacts.py

key-decisions:
  - "Validate inputs before any gRPC calls to fail fast on format errors"
  - "Basic injection protection for search parameters (semicolons, SQL comments)"
  - "Generic exception handlers must never expose internal error details or stack traces"
  - "All error responses include 'hint' field with actionable guidance"

patterns-established:
  - "Three-tier error handling: ValueError for validation, grpc.RpcError for server errors, Exception for unexpected failures"
  - "Error responses always return JSON with 'error' and 'hint' fields"
  - "404-style errors mention list_* tools to help users find valid IDs"

# Metrics
duration: 5.2min
completed: 2026-01-26
---

# Phase 3 Plan 2: Client and Artifact Tools Error Handling Summary

**User-facing client and artifact tools now return clear, actionable errors with hints instead of crashes or cryptic gRPC messages**

## Performance

- **Duration:** 5.2 min
- **Started:** 2026-01-26T03:06:40Z
- **Completed:** 2026-01-26T03:11:49Z
- **Tasks:** 3
- **Files modified:** 2 tool files, 1 test file created

## Accomplishments
- All 4 client management tools (list_clients, get_client_info, label_client, quarantine_client) have comprehensive error handling
- All 3 artifact tools (list_artifacts, get_artifact, collect_artifact) have comprehensive error handling
- Input validation catches format errors before expensive gRPC calls
- gRPC errors mapped to user-friendly messages with actionable hints
- 18 integration tests verify error handling behavior across all scenarios
- No stack traces exposed in any error response

## Task Commits

Each task was committed atomically:

1. **Task 1: Add error handling to clients.py** - `2cd4a28` (feat)
2. **Task 2: Add error handling to artifacts.py** - `2018480` (feat)
3. **Task 3: Integration tests for client and artifact error handling** - `ab720e0` (test)

## Files Created/Modified

**Created:**
- `tests/integration/test_error_handling_clients_artifacts.py` - Integration tests for error handling in clients and artifacts tools (18 tests)

**Modified:**
- `src/megaraptor_mcp/tools/clients.py` - Added validation, gRPC error handling, and 404-style errors to all 4 client tools
- `src/megaraptor_mcp/tools/artifacts.py` - Added validation, gRPC error handling, and 404-style errors to all 3 artifact tools

## Decisions Made

**1. Input validation before gRPC calls:**
- Validate client_id, limit, artifact_type, and other parameters at function entry
- Fails fast with clear validation error messages before making expensive server calls
- Reduces server load from malformed requests

**2. Basic injection protection for search parameters:**
- Detect semicolons and SQL comment markers (--) in search queries
- Return clear error instead of passing to server
- Prevents accidental VQL injection in user input

**3. Three-tier exception handling:**
- ValueError → validation errors with hints about correct format
- grpc.RpcError → map_grpc_error for user-friendly server errors
- Exception → generic error without exposing internal details
- Ensures users never see Python stack traces

**4. 404-style errors with hints:**
- Non-existent resources return clear "not found" messages
- Hints point users to list_* tools to find valid IDs
- Makes tools discoverable and self-documenting

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - error handling utilities from 03-01 worked as designed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Client and artifact tools now have production-grade error handling. Ready to apply same patterns to:
- VQL tools (03-03)
- Flow tools (03-03)
- Hunt tools (03-03)
- Remaining tools in 03-04

**Pattern established:** All future MCP tools should follow the same three-tier error handling approach (validate → gRPC error → generic) for consistent user experience.

---
*Phase: 03-error-handling*
*Completed: 2026-01-26*
