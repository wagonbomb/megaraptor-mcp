# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** All 35 MCP tools work reliably against real Velociraptor deployments with actionable output and graceful error handling
**Current focus:** Phase 5 - Output Quality

## Current Position

Phase: 5 of 6 (Output Quality) - In Progress
Plan: 2 of 5 complete (05-02-PLAN.md)
Status: Hash and timestamp validation tests complete — QUAL-01 and QUAL-02 requirements satisfied
Last activity: 2026-01-26 — Completed 05-02-PLAN.md (hash validation and timestamp accuracy tests)

Progress: [████████░░] 68% (4 of 6 phases complete, 2 of 5 plans in phase 5)

## Performance Metrics

**Velocity:**
- Total plans completed: 17
- Average duration: 5.3 min
- Total execution time: 1.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-test-infrastructure | 3 | 10min | 3.3min |
| 02-smoke-tests | 6 | 30min | 5.0min |
| 03-error-handling | 4 | 33min | 8.3min |
| 04-os-specific-artifacts | 2 | 18min | 9.0min |
| 05-output-quality | 2 | 6min | 3.0min |

**Recent Trend:**
- Last 5 plans: 15min, 10min, 8min, 3min, 3min
- Trend: Fast infrastructure plans (3min), comprehensive testing plans (8-15min)

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

**From 03-02 execution (Client and Artifact Tools Error Handling):**
- Input validation at function entry before any operations - fails fast on format errors
- Basic injection protection for search parameters (semicolons, SQL comments)
- Three-tier exception handling: ValueError → validation, grpc.RpcError → server errors, Exception → generic
- 404-style errors with hints pointing to list_* tools to find valid IDs
- All error responses include 'error' and 'hint' fields for consistent user experience
- Generic exception handlers must never expose stack traces or internal error details

**From 03-03 execution (Hunt, Flow, and VQL Tool Error Handling):**
- Validate inputs immediately at function entry using error_handling validators
- Add contextual hints to 404 errors (e.g., "Use list_hunts() to see available hunts")
- Pre-execution VQL syntax validation catches common mistakes (trailing semicolons, empty queries)
- Server INVALID_ARGUMENT errors enhanced with VQL-specific hints from extract_vql_error_hint
- Two-layer VQL validation: basic syntax before execution, detailed hints from server errors

**From 03-04 execution (Deployment Error Handling & Comprehensive Testing):**
- Comprehensive testing reveals bugs - 29-test suite discovered validation bugs in 3 tool modules
- Validation pattern must be consistent - try/except ValueError, not if-check
- Test-driven bug discovery - comprehensive error scenario testing identified bugs missed in code review
- Auto-fix bugs discovered during testing (deviation Rule 1) - fixed hunts.py, flows.py, vql.py
- validate_deployment_id() function for deployment ID format validation (must start with 'vr-')
- All "not found" errors enhanced with hints suggesting appropriate list_* tools
- 75/75 smoke tests pass - error handling doesn't break normal operation

**From 04-01 execution (Linux Artifact Testing):**
- OS-specific artifact schemas validate critical fields only (avoid brittleness)
- TargetRegistry.get_by_artifact() method for artifact-based target selection
- Flexible field name matching supports multiple Velociraptor versions
- Linux.Sys.Users artifact validated against schema with proper capability checks

**From 04-02 execution (Windows Artifact Testing with Skip Guards):**
- Skip guard pattern for unavailable test targets (skip_no_windows_target decorator)
- has_windows_target() helper returns False when no Windows target available
- Windows marker registered for test filtering (pytest -m windows)
- Tests skip gracefully with clear messages, run automatically when target added

**From 05-01 execution (Baseline Infrastructure):**
- Placeholder baselines populated by test execution, not synthetic data
- Deterministic hashing via normalized JSON (sorted keys, consistent separators)
- Central metadata.json documents hashes and test conditions for all baselines
- compute_forensic_hash() ensures same data always produces same hash
- Baseline metadata tracks SHA-256 hash, test conditions, critical fields
- Artifact name to filename conversion (Linux.Sys.Users -> linux_sys_users.json)

**From 05-02 execution (Hash and Timestamp Validation Tests):**
- Use pytest.approx(abs=2.0) for timestamp drift validation - allows for network latency and query execution time
- Skip test gracefully when baseline hash not populated - enables incremental baseline population
- Multi-format timestamp parsing (RFC3339, ISO8601, Unix epoch) via parse_velociraptor_timestamp()
- Unit tests validate helpers without live server - fast feedback loop
- Hash validation pattern: compute hash, compare to metadata, skip with hash if not populated
- Timestamp accuracy via pytest.approx - record before/after time, validate flow timestamp within tolerance

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 4 consideration:** Windows container availability may require VM fallback or Windows testing deferral if winamd64/velociraptor-client image unavailable.

**Phase 6 consideration:** Physical lab or cloud VM infrastructure needed for deployment validation beyond Docker containers.

## Session Continuity

Last session: 2026-01-26T19:52:33Z
Stopped at: Completed 05-02-PLAN.md — Hash and timestamp validation tests complete
Resume file: None

---
*State initialized: 2026-01-25*
*Next step: Continue Phase 5 - VQL correctness tests (05-03)*
