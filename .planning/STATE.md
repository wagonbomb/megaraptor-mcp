# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** All 35 MCP tools work reliably against real Velociraptor deployments with actionable output and graceful error handling
**Current focus:** Phase 3 - Error Handling

## Current Position

Phase: 3 of 6 (Error Handling) - In Progress
Plan: 1 of 1 complete (03-01-PLAN.md)
Status: Phase 3 complete (error handling foundation established)
Last activity: 2026-01-26 — Completed 03-01-PLAN.md (Error Handling Foundation)

Progress: [█████░░░░░] 50% (3 of 6 phases complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 4.2 min
- Total execution time: 0.7 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-test-infrastructure | 3 | 10min | 3.3min |
| 02-smoke-tests | 6 | 30min | 5.0min |
| 03-error-handling | 1 | 8min | 8.0min |

**Recent Trend:**
- Last 5 plans: 4min, 4min, 12min, 8min, 8min
- Trend: Stable at 8min for complex implementation plans

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Test container first: Lower risk, faster iteration — validates infrastructure before physical deployments
- On-prem before cloud: Validate core functionality before platform-specific deployments
- Gap analysis over new features: Understand capability needs before building new tools

**From 01-01 execution:**
- Module-scoped fixture to prevent gRPC connection exhaustion
- Explicit connect/close calls for clear lifecycle management
- Autouse fixture for global client state reset between tests

**From 01-02 execution:**
- Best-effort cleanup: log warnings but don't fail tests if cleanup errors occur
- Function-scoped autouse fixture for cleanup: runs after every test to prevent pollution
- TEST- prefix convention: All test entities use TEST- prefix for easy identification

**From 01-03 execution:**
- Session-scoped target_registry to discover enrolled clients once per test session
- Autouse certificate check fixture fails fast before cryptic gRPC errors
- Graceful degradation when cryptography library unavailable
- OS-based capability inference (Linux, Windows, Darwin)

**From 02-01 execution:**
- Keep schemas minimal - only validate critical fields to avoid brittleness
- Module scope for target_registry and enrolled_client_id fixtures
- Register smoke marker in pytest configuration

**From 02-02 execution:**
- TOOL_SMOKE_INPUTS as single source of truth for all 35 MCP tools
- Deployment tools expected to fail gracefully in test environment (missing infrastructure)
- Meta-test ensures no tools are missed as codebase evolves

**From 02-03 execution:**
- Use flexible field name matching (e.g., 'Hostname' or 'hostname' or 'Fqdn') to support multiple Velociraptor versions
- Wait for artifact completion in smoke tests when validating result structures (exception to general smoke test rule)
- Apply 30s timeout to individual flows plus 60s pytest timeout for defense in depth

**From 02-04 execution:**
- Test resource handlers directly instead of through MCP server decorator
- Parametrize VQL queries with common patterns for comprehensive coverage
- Use soft assertions (pytest-check) for detailed smoke test failure reporting
- Test error conditions return JSON gracefully, not exceptions

**From 02-05 execution (Gap Closure - FastMCP Migration):**
- Module-level FastMCP instance exported as 'mcp' for tool decorator access
- Tools imported lazily via _register_all() to trigger registration
- FastMCP call_tool() returns tuple (content_list, metadata) - test helpers updated accordingly

**From 02-06 execution (Gap Closure - Artifact Collection Fixes):**
- source() VQL requires artifact + source params, not just artifact name
- Use Linux.Sys.Pslist for Linux containers (Generic.System.Pslist doesn't exist in 0.75.x)
- Inject VELOCIRAPTOR_CONFIG_PATH env var via autouse fixture for MCP tool tests
- Deployment tools expected to fail gracefully with "Deployment not found" errors

**From 03-01 execution (Error Handling Foundation):**
- Tenacity library for retry logic - well-maintained, flexible decorator-based retry library
- Selective retry strategy - only retry transient errors (UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED)
- No retry on validation, auth, or not-found errors that require user intervention
- 30-second default timeout for query operations - balances responsiveness and completion
- Exponential backoff with 1s min, 10s max, 3 attempts - prevents thundering herd
- Pattern-based VQL hints via regex - actionable guidance without server API dependency
- Structured error format - dicts with error/hint/grpc_status fields for consistent consumption

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 4 consideration:** Windows container availability may require VM fallback or Windows testing deferral if winamd64/velociraptor-client image unavailable.

**Phase 6 consideration:** Physical lab or cloud VM infrastructure needed for deployment validation beyond Docker containers.

## Session Continuity

Last session: 2026-01-26T03:03:05Z
Stopped at: Completed 03-01-PLAN.md (Error Handling Foundation)
Resume file: None

---
*State initialized: 2026-01-25*
*Next step: /gsd:plan-phase 04 (Phase 3 complete, error handling foundation established)*
