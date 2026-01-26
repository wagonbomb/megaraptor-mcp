# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** All 35 MCP tools work reliably against real Velociraptor deployments with actionable output and graceful error handling
**Current focus:** Phase 2 - Smoke Tests (Gap Closure)

## Current Position

Phase: 2 of 6 (Smoke Tests) - Gap Closure Complete
Plan: 6 of 6 complete (02-06-PLAN.md)
Status: Phase 2 complete (all gaps closed)
Last activity: 2026-01-25 — Completed 02-06-PLAN.md (Artifact Collection Fixes)

Progress: [███░░░░░░░] 33% (2 of 6 phases complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 9
- Average duration: 4.0 min
- Total execution time: 0.6 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-test-infrastructure | 3 | 10min | 3.3min |
| 02-smoke-tests | 6 | 30min | 5.0min |

**Recent Trend:**
- Last 5 plans: 3min, 4min, 4min, 12min, 8min
- Trend: Gap closure plans taking longer due to diagnostic work

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

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 4 consideration:** Windows container availability may require VM fallback or Windows testing deferral if winamd64/velociraptor-client image unavailable.

**Phase 6 consideration:** Physical lab or cloud VM infrastructure needed for deployment validation beyond Docker containers.

## Session Continuity

Last session: 2026-01-25T11:10:00Z
Stopped at: Completed 02-06-PLAN.md (Gap Closure - Artifact Collection Fixes)
Resume file: None

---
*State initialized: 2026-01-25*
*Next step: /gsd:plan-phase 03 (Phase 2 fully complete, all 75 smoke tests passing)*
