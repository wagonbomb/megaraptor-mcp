# Roadmap: Megaraptor MCP

## Overview

This roadmap validates all 35 MCP tools against real Velociraptor deployments through progressive testing layers. Starting with foundational test infrastructure and connection lifecycle patterns, we establish smoke tests for basic functionality, validate error handling across failure modes, expand to OS-specific artifacts, verify forensic output quality, and culminate in end-to-end deployment validation. Each phase builds verifiable capabilities that unblock the next, ensuring all tools work reliably in production DFIR workflows.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Test Infrastructure** - Foundation for all validation testing
- [x] **Phase 2: Smoke Tests** - Basic tool functionality verification
- [x] **Phase 3: Error Handling** - Failure mode and edge case validation
- [x] **Phase 4: OS-Specific Artifacts** - Multi-platform artifact validation
- [x] **Phase 5: Output Quality** - Forensic soundness and correctness
- [x] **Phase 6: Deployment & Gap Analysis** - End-to-end deployment validation

## Phase Details

### Phase 1: Test Infrastructure
**Goal**: All validation tests can reliably connect to Velociraptor, manage container lifecycle, wait for async operations, and clean up test artifacts without state pollution

**Depends on**: Nothing (first phase)

**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06

**Success Criteria** (what must be TRUE):
  1. Test suite starts and stops Velociraptor container automatically (subprocess approach, pytest-docker deferred)
  2. VelociraptorClient fixture establishes connections with proper lifecycle (no connection leaks)
  3. Cleanup fixtures remove all test-created entities (hunts, flows, labels) after each test
  4. wait_for_flow_completion helper reliably detects async operation completion without race conditions
  5. Certificate expiration monitoring alerts before test infrastructure fails

**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Dependencies and enhanced client fixture with lifecycle management
- [x] 01-02-PLAN.md — Wait helpers and cleanup fixtures for async operations and state isolation
- [x] 01-03-PLAN.md — Target registry and certificate expiration monitoring

### Phase 2: Smoke Tests
**Goal**: All 35 MCP tools are callable against live Velociraptor and return valid, parseable responses for basic operations

**Depends on**: Phase 1

**Requirements**: SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04, SMOKE-05, SMOKE-06, SMOKE-07

**Success Criteria** (what must be TRUE):
  1. User can invoke all 35 MCP tools and receive non-error responses
  2. Generic.Client.Info artifact collection completes and returns valid client metadata
  3. Generic.System.Pslist returns process list with expected structure (PID, name, command line)
  4. Basic VQL queries execute without syntax errors and return results
  5. All tool outputs validate against JSON schemas for AI assistant parsing

**Plans**: 6 plans (4 original + 2 gap closure)

Plans:
- [x] 02-01-PLAN.md — Schema registry, MCP helpers, and server connectivity verification
- [x] 02-02-PLAN.md — Parametrized smoke tests for all 35 MCP tools
- [x] 02-03-PLAN.md — Artifact collection smoke tests (Generic.Client.Info, Generic.System.Pslist)
- [x] 02-04-PLAN.md — VQL execution and resource URI smoke tests
- [x] 02-05-PLAN.md — [GAP CLOSURE] Migrate to FastMCP for SDK 1.25.0 compatibility
- [x] 02-06-PLAN.md — [GAP CLOSURE] Fix artifact collection after FastMCP migration

### Phase 3: Error Handling
**Goal**: All MCP tools handle failure scenarios gracefully with actionable error messages and no exposed stack traces

**Depends on**: Phase 2

**Requirements**: ERR-01, ERR-02, ERR-03, ERR-04, ERR-05, ERR-06, ERR-07

**Success Criteria** (what must be TRUE):
  1. Network timeouts return clear error messages instead of hanging or crashing
  2. Malformed VQL syntax errors provide correction hints to users
  3. Requests for non-existent resources (clients, hunts, flows) return 404-style errors with context
  4. Invalid parameters (negative limits, empty IDs) are validated with clear messages before execution
  5. Authentication and permission errors are caught and reported without stack traces

**Plans**: 4 plans

Plans:
- [x] 03-01-PLAN.md — Error handling foundation (validators, gRPC handlers, VQL helpers, client retry)
- [x] 03-02-PLAN.md — Error handling for clients.py and artifacts.py tools
- [x] 03-03-PLAN.md — Error handling for hunts.py, flows.py, and vql.py tools
- [x] 03-04-PLAN.md — Deployment tool errors and comprehensive error handling tests

### Phase 4: OS-Specific Artifacts
**Goal**: Artifact collection works across Linux and Windows targets with proper OS-specific validation

**Depends on**: Phase 2

**Requirements**: OSART-01, OSART-02, OSART-03, OSART-04, OSART-05

**Success Criteria** (what must be TRUE):
  1. Linux.Sys.Users artifact collection returns valid user account data from Linux targets
  2. Windows.System.Services artifact collection returns service data from Windows targets (if available)
  3. Windows registry artifacts (UserAssist or similar) parse and validate correctly
  4. TargetRegistry selects appropriate test targets based on OS and artifact capabilities
  5. Complex artifact types (registry, binary parsing) validate against OS-specific schemas

**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md — Linux artifact testing (TargetRegistry enhancement, schemas, Linux.Sys.Users)
- [x] 04-02-PLAN.md — Windows artifact testing (Services, Registry.UserAssist with skip guards)

### Phase 5: Output Quality
**Goal**: All artifact collections produce forensically sound output with verifiable correctness against known-good baselines

**Depends on**: Phase 4

**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06

**Success Criteria** (what must be TRUE):
  1. Collected artifact file hashes match expected values from known-good baselines
  2. Timestamp accuracy is validated within acceptable drift (±1 second)
  3. All expected fields are present and populated in artifact collections
  4. VQL query results match known-good baselines for correctness
  5. Test fixtures with known-good datasets are documented in tests/fixtures/README.md

**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md — Baseline infrastructure (fixtures directory, helper functions, README documentation)
- [x] 05-02-PLAN.md — Hash verification and timestamp accuracy validation tests
- [x] 05-03-PLAN.md — Completeness validation, VQL correctness, and NIST CFTT false positive definition

### Phase 6: Deployment & Gap Analysis
**Goal**: Deployment automation works end-to-end for Docker and binary profiles, and all capability gaps are documented

**Depends on**: Phase 5

**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06, GAP-01, GAP-02, GAP-03

**Success Criteria** (what must be TRUE):
  1. Docker deployment profile creates accessible, working Velociraptor server
  2. Binary deployment profile creates working server on target system
  3. Full investigation workflow (triage to collection to analysis) completes end-to-end
  4. Deployment rollback successfully cleans up all resources
  5. Gap analysis document identifies missing tool capabilities and improvement recommendations

**Plans**: 4 plans

Plans:
- [x] 06-01-PLAN.md — Docker deployment E2E validation (DEPLOY-01, DEPLOY-04)
- [x] 06-02-PLAN.md — Investigation workflow E2E test (DEPLOY-03)
- [x] 06-03-PLAN.md — Agent deployment tests with skip guards (DEPLOY-02, DEPLOY-05, DEPLOY-06)
- [x] 06-04-PLAN.md — Gap analysis documentation (GAP-01, GAP-02, GAP-03)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Test Infrastructure | 3/3 | Complete | 2026-01-25 |
| 2. Smoke Tests | 6/6 | Complete | 2026-01-25 |
| 3. Error Handling | 4/4 | Complete | 2026-01-26 |
| 4. OS-Specific Artifacts | 2/2 | Complete | 2026-01-26 |
| 5. Output Quality | 3/3 | Complete | 2026-01-26 |
| 6. Deployment & Gap Analysis | 4/4 | Complete | 2026-01-26 |

---
*Roadmap created: 2026-01-25*
*Milestone: v1.0 Quality & Real-World Validation*
