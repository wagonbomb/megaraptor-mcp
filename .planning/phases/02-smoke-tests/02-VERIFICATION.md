---
phase: 02-smoke-tests
verified: 2026-01-25T18:30:00Z
status: gaps_found
score: 3/5 success criteria verified
gaps:
  - criterion: "User can invoke all 35 MCP tools and receive non-error responses"
    status: failed
    reason: "MCP tool invocation architecture broken"
    artifacts:
      - path: "tests/integration/helpers/mcp_helpers.py"
        issue: "invoke_mcp_tool() calls create_server() causing AttributeError"
    missing:
      - "Refactor tool registration or test through MCP protocol"
  
  - criterion: "Generic.Client.Info artifact collection works"
    status: failed
    reason: "Artifact collection returns empty results"
    artifacts:
      - path: "tests/integration/test_smoke_artifacts.py"
        issue: "source() VQL returns 0 results"
    missing:
      - "Debug why flow completes but returns no data"
  
  - criterion: "Generic.System.Pslist returns process list"
    status: failed
    reason: "collect_client() returns None"
    artifacts:
      - path: "tests/integration/test_smoke_artifacts.py"
        issue: "VQL function unavailable or wrong signature"
    missing:
      - "Use correct collection method for this Velociraptor version"
---

# Phase 2: Smoke Tests Verification Report

**Phase Goal:** All 35 MCP tools are callable against live Velociraptor  
**Verified:** 2026-01-25T18:30:00Z  
**Status:** GAPS FOUND

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can invoke all 35 MCP tools | FAILED | All 39 tool tests fail - AttributeError on Server.tool() |
| 2 | Generic.Client.Info works | FAILED | Flow completes but returns empty results |
| 3 | Generic.System.Pslist works | FAILED | collect_client() returns None |
| 4 | Basic VQL queries execute | VERIFIED | 17/17 VQL tests pass |
| 5 | JSON schemas validate outputs | PARTIAL | Schemas exist, resources validated, tools untested |

**Score:** 1.5/5 (1 full + 0.5 partial)


### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| test_smoke_mcp_tools.py | ORPHANED | 191 lines, all 35 tools defined, BUT invocation broken |
| test_smoke_artifacts.py | ORPHANED | 208 lines, tests exist BUT VQL broken |
| test_smoke_vql.py | VERIFIED | 135 lines, 17 tests passing |
| test_smoke_resources.py | VERIFIED | 183 lines, 13 tests passing |
| test_smoke_connectivity.py | VERIFIED | 84 lines, 3 tests passing |
| schemas/base_schemas.py | VERIFIED | 119 lines, 11 schemas |
| helpers/mcp_helpers.py | STUB | invoke_mcp_tool() broken |

### Requirements Coverage

| Requirement | Status |
|-------------|--------|
| SMOKE-01: All 35 MCP tools callable | BLOCKED |
| SMOKE-02: Generic.Client.Info works | BLOCKED |
| SMOKE-03: Generic.System.Pslist works | BLOCKED |
| SMOKE-04: Basic VQL execution | SATISFIED |
| SMOKE-05: JSON Schema validation | PARTIAL |
| SMOKE-06: Server connectivity | SATISFIED |
| SMOKE-07: Resource URIs valid | SATISFIED |

**Met:** 2.5/7 requirements

### Test Results



## Gaps Summary

### Gap 1: MCP Tool Invocation Broken

**Impact:** SMOKE-01 blocked - cannot test any of 35 MCP tools

**Root Cause:** invoke_mcp_tool() calls create_server() which tries to execute @server.tool() decorators. Server object has no tool attribute at runtime.

**Fix Options:**
- Test through actual MCP protocol (stdio/SSE)
- Refactor to separate tool functions from decorators
- Mock Server.tool() (not recommended)

### Gap 2: Artifact Collection Empty Results  

**Impact:** SMOKE-02 blocked

**Root Cause:** source() VQL returns empty list despite flow completing.

**Fix:** Debug Velociraptor deployment, verify artifact execution, try alternative result methods.

### Gap 3: collect_client() Returns None

**Impact:** SMOKE-03 blocked

**Root Cause:** VQL function unavailable or wrong signature.

**Fix:** Check Velociraptor VQL reference for correct collection method.

## Human Verification Required

1. **Velociraptor Artifact Execution:** Manually trigger artifacts in UI to verify container config
2. **MCP Protocol E2E:** Test actual MCP server via stdio to verify protocol works
3. **Schema Quality:** Review schemas cover critical fields for AI assistants

---

## Verdict

**PHASE INCOMPLETE**

**Works:**
- VQL execution (17/17)
- Resources (13/13)
- Connectivity (3/3)

**Broken:**
- MCP tools (0/39) - architectural
- Artifacts (0/2) - VQL functions

**Impact:** 3/7 requirements, 3/5 criteria, 34/75 tests (45%)

**Goal NOT Achieved:** Cannot invoke any of 35 MCP tools.

**Recommendations:**
1. Fix MCP tool invocation architecture
2. Fix artifact collection VQL
3. Re-run verification

---

_Verified: 2026-01-25T18:30:00Z_  
_Verifier: Claude (gsd-verifier)_
