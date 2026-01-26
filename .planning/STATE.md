# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** All 35 MCP tools work reliably against real Velociraptor deployments with actionable output and graceful error handling
**Current focus:** Phase 6 - Deployment & Gap Analysis

## Current Position

Phase: 5 of 6 (Output Quality) - Complete
Plan: 3 of 3 complete
Status: All QUAL requirements verified — hash validation, timestamp accuracy, completeness, VQL correctness, NIST CFTT
Last activity: 2026-01-26 — Completed Phase 5 (Output Quality - forensic soundness verification)

Progress: [████████░░] 83% (5 of 6 phases complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 18
- Average duration: 5.2 min
- Total execution time: 1.6 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-test-infrastructure | 3 | 10min | 3.3min |
| 02-smoke-tests | 6 | 30min | 5.0min |
| 03-error-handling | 4 | 33min | 8.3min |
| 04-os-specific-artifacts | 2 | 18min | 9.0min |
| 05-output-quality | 3 | 15min | 5.0min |

**Recent Trend:**
- Last 5 plans: 10min, 8min, 3min, 3min, 6min
- Trend: Fast infrastructure plans (3-4min), comprehensive testing plans (8-10min)

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

**From 05-03 execution (Completeness and Correctness Validation):**
- NIST CFTT false positive rate: <1% requirement, 0% target for deterministic VQL
- Completeness validation checks field presence AND non-empty values (not just existence)
- Baseline comparison allows ±50% count variance - system state changes between runs
- False positive definitions are artifact-specific - user data vs client info have different validity rules
- Case-insensitive field matching supports multiple Velociraptor versions
- False positive detection: structural validity checks (empty usernames, null bytes, negative UIDs)
- VQL is deterministic - any false positive indicates a bug, not statistical variance

**Phase 5 Complete (Output Quality):**
- All 6 QUAL requirements verified with substantive implementations
- baseline_helpers.py: compute_forensic_hash(), load_baseline(), parse_velociraptor_timestamp()
- test_output_quality.py: 4 test classes covering hash, timestamp, completeness, VQL correctness
- Placeholder baselines designed for live population and manual verification before commit
- NIST CFTT compliance: <1% false positive rate validated via structural checks

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 4 consideration:** Windows container availability may require VM fallback or Windows testing deferral if winamd64/velociraptor-client image unavailable.

**Phase 6 consideration:** Physical lab or cloud VM infrastructure needed for deployment validation beyond Docker containers.

## Session Continuity

Last session: 2026-01-26
Stopped at: Completed Phase 5 — Output Quality verification complete
Resume file: None

---
*State initialized: 2026-01-25*
*Next step: Plan Phase 6 - Deployment & Gap Analysis*
