---
phase: 03-error-handling
plan: 01
subsystem: error-handling
tags: [tenacity, grpc, validators, error-mapping, retry-logic, vql]

# Dependency graph
requires:
  - phase: 02-smoke-tests
    provides: Test infrastructure and validated client implementation
provides:
  - Comprehensive error handling module with validators, gRPC error mapping, and VQL hint extraction
  - Retry logic with exponential backoff on transient gRPC failures
  - User-friendly error messages with actionable hints
  - Timeout parameter for query operations
affects: [04-core-tools, 05-advanced-tools, all-mcp-tools]

# Tech tracking
tech-stack:
  added: [tenacity>=8.2.3]
  patterns:
    - Input validation with user-friendly error messages and hints
    - gRPC status code mapping to actionable user guidance
    - Automatic retry on transient failures (UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED)
    - VQL error parsing for common syntax and semantic issues
    - Exponential backoff retry strategy (1s, 2s, 4s, max 10s, 3 attempts)

key-files:
  created:
    - src/megaraptor_mcp/error_handling/__init__.py
    - src/megaraptor_mcp/error_handling/validators.py
    - src/megaraptor_mcp/error_handling/grpc_handlers.py
    - src/megaraptor_mcp/error_handling/vql_helpers.py
    - tests/unit/test_error_handling.py
  modified:
    - pyproject.toml
    - src/megaraptor_mcp/client.py

key-decisions:
  - "Use tenacity for retry logic - well-maintained, flexible retry decorator library"
  - "Retry only on transient gRPC errors (UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED)"
  - "No retry on validation, auth, or not-found errors - user intervention required"
  - "30-second default timeout for query operations - balances responsiveness and completion"
  - "Exponential backoff with 1s min, 10s max - prevents thundering herd while allowing quick recovery"
  - "VQL error hints based on pattern matching - provides actionable guidance without server API dependency"

patterns-established:
  - "validate_* functions raise ValueError with hints - consistent validation pattern"
  - "is_retryable_* functions return bool - composable retry predicates"
  - "map_* functions return structured dicts with error/hint/status - consistent error format"
  - "extract_* functions return user-friendly strings - parsing/transformation pattern"

# Metrics
duration: 8min
completed: 2026-01-26
---

# Phase 03 Plan 01: Error Handling Foundation Summary

**Comprehensive error handling module with validators, gRPC retry, VQL hint extraction, and 44 passing unit tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-26T02:55:22Z
- **Completed:** 2026-01-26T03:03:05Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Created error_handling module with input validators for client_id, hunt_id, flow_id, limit, and VQL syntax
- Implemented gRPC error mapping to user-friendly messages with actionable hints for 8+ status codes
- Added automatic retry with exponential backoff on transient failures to VelociraptorClient
- Built VQL error hint extraction for 10+ common error patterns (symbol not found, syntax errors, type mismatches)
- Achieved 100% test coverage with 44 passing unit tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Add tenacity dependency and create error_handling module** - `3194896` (feat)
2. **Task 2: Enhance client.py with retry and timeout** - `ea27f56` (feat)
3. **Task 3: Unit tests for error handling utilities** - `776512e` (test)

## Files Created/Modified

### Created
- `src/megaraptor_mcp/error_handling/__init__.py` - Module exports for all error handling utilities
- `src/megaraptor_mcp/error_handling/validators.py` - Input validation functions with user-friendly hints
- `src/megaraptor_mcp/error_handling/grpc_handlers.py` - gRPC StatusCode to user message mapping
- `src/megaraptor_mcp/error_handling/vql_helpers.py` - VQL error hint extraction via pattern matching
- `tests/unit/test_error_handling.py` - Comprehensive unit tests (44 tests)

### Modified
- `pyproject.toml` - Added tenacity>=8.2.3 dependency
- `src/megaraptor_mcp/client.py` - Added @retry decorator and timeout parameter to query methods

## Decisions Made

1. **Tenacity library for retry logic** - Well-maintained, flexible decorator-based retry library with excellent exponential backoff support
2. **Selective retry strategy** - Only retry transient errors (UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED); no retry on validation, auth, or not-found errors that require user intervention
3. **30-second default timeout** - Balances responsiveness with query completion; users can override for long-running queries
4. **Exponential backoff parameters** - 1s min, 10s max, 3 attempts; prevents thundering herd while allowing quick recovery from transient issues
5. **Pattern-based VQL hints** - Extract hints via regex pattern matching rather than server API dependency; provides actionable guidance for common VQL errors
6. **Structured error format** - All error mappers return dicts with error/hint/grpc_status fields for consistent consumption by MCP tools

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

1. **Mock gRPC errors for testing** - Initial mock configuration failed because `spec=grpc.RpcError` prevents automatic attribute creation. Fixed by explicitly creating `code` and `details` as Mock objects rather than setting them via attribute assignment.
2. **VQL symbol regex** - Initial regex `\w+` didn't capture dotted symbols like "Windows.System.Users". Fixed by updating pattern to `[\w.]+` to support namespaced VQL symbols.

Both issues resolved during test development (Task 3) without impacting plan scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Error handling foundation complete and fully tested
- All 35 MCP tools can now use validators, error mapping, and VQL hints
- Client has built-in retry and timeout - ready for tool integration
- Phase 04 (core tools) can proceed with consistent error handling patterns

**Blockers:** None

**Concerns:** None - comprehensive test coverage provides confidence

---
*Phase: 03-error-handling*
*Completed: 2026-01-26*
