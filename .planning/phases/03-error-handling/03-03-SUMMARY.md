---
phase: 03-error-handling
plan: 03
subsystem: error-handling
tags: [grpc, error-handling, validation, vql, velociraptor]

# Dependency graph
requires:
  - phase: 03-01
    provides: Error handling foundation (validators, gRPC mappers, VQL hint extraction)
provides:
  - Error handling for hunt tools (create_hunt, list_hunts, get_hunt_results, modify_hunt)
  - Error handling for flow tools (list_flows, get_flow_results, get_flow_status, cancel_flow)
  - Enhanced VQL tool with pre-execution syntax validation and server error hints
affects: [04-windows-artifacts, 05-linux-artifacts, integration-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Input validation at function entry before any operations"
    - "gRPC error wrapping with user-friendly messages and hints"
    - "404-style errors with actionable guidance for non-existent resources"
    - "VQL-specific error hint extraction from INVALID_ARGUMENT errors"

key-files:
  created: []
  modified:
    - src/megaraptor_mcp/tools/hunts.py
    - src/megaraptor_mcp/tools/flows.py
    - src/megaraptor_mcp/tools/vql.py

key-decisions:
  - "Validate inputs before operations to provide immediate feedback"
  - "Add contextual hints to 404 errors (e.g., 'use list_hunts() to see available hunts')"
  - "Extract VQL-specific hints from server errors for INVALID_ARGUMENT responses"

patterns-established:
  - "Pattern 1: Input validation using error_handling validators (validate_hunt_id, validate_flow_id, validate_client_id, validate_limit)"
  - "Pattern 2: Graceful gRPC error handling with try/except wrapping all external calls"
  - "Pattern 3: Structured error responses as JSON dicts (error/hint/grpc_status fields)"

# Metrics
duration: 5min
completed: 2026-01-26
---

# Phase 3 Plan 3: Tool Error Handling Summary

**Hunt, flow, and VQL tools with comprehensive error handling: input validation, gRPC error mapping, and VQL-specific syntax hints**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-26T03:06:55Z
- **Completed:** 2026-01-26T03:11:50Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Added error handling to all 4 hunt tools with input validation and 404-style hints
- Added error handling to all 4 flow tools with input validation and contextual error messages
- Enhanced VQL tool with pre-execution syntax validation and server error hint extraction

## Task Commits

Each task was committed atomically:

1. **Task 1: Add error handling to hunts.py** - `2e4c703` (feat)
   - Input validation for all 4 hunt tools
   - gRPC error mapping with user-friendly messages
   - 404-style hints for non-existent hunts

2. **Task 2: Add error handling to flows.py** - `dd2d51d` (feat)
   - Input validation for all 4 flow tools
   - gRPC error mapping with user-friendly messages
   - 404-style hints for non-existent flows

3. **Task 3: Enhance vql.py with syntax validation and error hints** - `accb38c` (feat)
   - Pre-execution VQL syntax validation
   - VQL-specific error hint extraction from INVALID_ARGUMENT errors
   - Input validation for query and max_rows

## Files Created/Modified
- `src/megaraptor_mcp/tools/hunts.py` - Hunt tools with full error handling (create_hunt, list_hunts, get_hunt_results, modify_hunt)
- `src/megaraptor_mcp/tools/flows.py` - Flow tools with full error handling (list_flows, get_flow_results, get_flow_status, cancel_flow)
- `src/megaraptor_mcp/tools/vql.py` - VQL tool with syntax validation and error hints (run_vql, vql_help)

## Decisions Made

**Input validation strategy:**
- Validate inputs immediately at function entry using error_handling validators
- Return structured error responses before attempting any operations
- Provides fast feedback and prevents cryptic server errors

**404-style error hints:**
- Add contextual hints to not-found errors (e.g., "Use list_hunts() to see available hunts")
- Helps users discover correct IDs and understand available resources
- Applied to hunt_id, flow_id, and client_id not-found scenarios

**VQL error enhancement:**
- Pre-execution syntax validation catches common mistakes (trailing semicolons, empty queries)
- Server INVALID_ARGUMENT errors enhanced with VQL-specific hints from extract_vql_error_hint
- Two-layer validation: basic syntax before execution, detailed hints from server errors

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 4 (Windows Artifacts):**
- Core tools (clients, artifacts, hunts, flows, VQL) have comprehensive error handling
- Error handling foundation provides validators, mappers, and hint extraction
- Structured error responses consistent across all tools
- All must_haves from plan satisfied:
  - create_hunt with invalid parameters returns validation error
  - get_hunt_results with non-existent hunt returns 404-style error
  - get_flow_status with non-existent flow returns 404-style error with hint
  - run_vql with malformed syntax returns VQL-specific error hints
  - run_vql with trailing semicolon gets pre-emptive validation error

**No blockers or concerns**

---
*Phase: 03-error-handling*
*Completed: 2026-01-26*
