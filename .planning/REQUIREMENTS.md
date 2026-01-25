# Requirements: Megaraptor MCP

**Defined:** 2026-01-24
**Core Value:** All 35 MCP tools work reliably against real Velociraptor deployments

## v1 Requirements

Requirements for milestone v1.0 Quality & Real-World Validation. Each maps to roadmap phases.

### Test Infrastructure

- [ ] **INFRA-01**: Test suite integrates pytest-docker for container lifecycle management
- [ ] **INFRA-02**: Module-scoped VelociraptorClient fixture with explicit connection lifecycle
- [ ] **INFRA-03**: Cleanup fixtures remove Velociraptor entities (hunts, flows, labels) after tests
- [ ] **INFRA-04**: wait_for_flow_completion helper polls for async operation completion
- [ ] **INFRA-05**: Certificate expiration monitoring integrated into test infrastructure
- [ ] **INFRA-06**: TargetRegistry provides capability-based target selection (OS, artifact support)

### Smoke Tests

- [ ] **SMOKE-01**: All 35 MCP tools are callable and return non-error responses
- [ ] **SMOKE-02**: Generic.Client.Info artifact collection works against live container
- [ ] **SMOKE-03**: Generic.System.Pslist returns valid process list structure
- [ ] **SMOKE-04**: Basic VQL query execution completes without syntax errors
- [ ] **SMOKE-05**: Output structure validated against JSON Schema for AI parsing
- [ ] **SMOKE-06**: Server connectivity and authentication verified before test runs
- [ ] **SMOKE-07**: Resource browsing (velociraptor:// URIs) returns valid data

### Error Handling

- [ ] **ERR-01**: Network timeout errors are caught and return clear error messages
- [ ] **ERR-02**: Malformed VQL syntax errors return actionable correction hints
- [ ] **ERR-03**: Non-existent resource requests (clients, hunts, flows) return 404-style errors
- [ ] **ERR-04**: Invalid parameters (negative limits, empty IDs) are validated with clear messages
- [ ] **ERR-05**: Authentication/permission errors are handled gracefully
- [ ] **ERR-06**: No stack traces exposed to users in error responses
- [ ] **ERR-07**: Retry logic handles transient connection failures

### OS-Specific Artifacts

- [ ] **OSART-01**: Linux.Sys.Users artifact collection and validation works
- [ ] **OSART-02**: Windows.System.Services artifact collection works (Windows target required)
- [ ] **OSART-03**: Windows registry artifact validation (UserAssist or similar)
- [ ] **OSART-04**: Multi-OS target support in TargetRegistry with capability filtering
- [ ] **OSART-05**: OS-specific validation schemas for complex artifact types

### Output Quality

- [ ] **QUAL-01**: Hash validation confirms collected artifacts match expected values
- [ ] **QUAL-02**: Timeline accuracy testing verifies timestamps within ±1 second drift
- [ ] **QUAL-03**: Artifact completeness validation ensures all expected fields present
- [ ] **QUAL-04**: VQL result correctness compared against known-good baselines
- [ ] **QUAL-05**: Known-good test dataset documented in tests/fixtures/README.md
- [ ] **QUAL-06**: NIST CFTT false positive rate requirement (<1%) validated

### Deployment Validation

- [ ] **DEPLOY-01**: Docker deployment profile creates running, accessible server
- [ ] **DEPLOY-02**: Binary deployment profile creates running server on target system
- [ ] **DEPLOY-03**: Full investigation workflow (triage → collect → analyze) completes e2e
- [ ] **DEPLOY-04**: Deployment rollback cleans up resources successfully
- [ ] **DEPLOY-05**: Agent deployment via SSH connects agent to server
- [ ] **DEPLOY-06**: Agent deployment via WinRM connects Windows agent to server

### Gap Analysis

- [ ] **GAP-01**: Gap analysis document identifies missing tool capabilities
- [ ] **GAP-02**: Deployment improvement recommendations documented
- [ ] **GAP-03**: Cloud testing requirements scoped for next milestone

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Performance & Scalability

- **PERF-01**: Large result pagination handles 10K+ rows efficiently
- **PERF-02**: Concurrent VQL query performance benchmarked
- **PERF-03**: Memory usage profiled under load conditions
- **PERF-04**: Response time baselines documented for all tools

### Multi-Client Testing

- **MULTI-01**: Multi-client hunts execute across 3-5 enrolled endpoints
- **MULTI-02**: Hunt result aggregation works at scale
- **MULTI-03**: Parallel artifact collection stress tested

### Cloud Deployment

- **CLOUD-01**: AWS CloudFormation deployment validated
- **CLOUD-02**: Azure ARM template deployment validated
- **CLOUD-03**: Cross-cloud deployment consistency verified

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| AI-enhanced error detection | Emerging pattern (2025/2026), not mature for production |
| Real-time monitoring dashboards | MCP is API-first for AI assistants, not UI |
| Mobile agent deployment | Focus on server/workstation endpoints first |
| False positive detection | Requires extensive baseline datasets, deferred to v2 |
| pytest-xdist parallelization | Nice-to-have optimization, not validation requirement |
| New tool implementation | Focus on validating existing 35 tools first |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| INFRA-06 | Phase 1 | Pending |
| SMOKE-01 | Phase 2 | Pending |
| SMOKE-02 | Phase 2 | Pending |
| SMOKE-03 | Phase 2 | Pending |
| SMOKE-04 | Phase 2 | Pending |
| SMOKE-05 | Phase 2 | Pending |
| SMOKE-06 | Phase 2 | Pending |
| SMOKE-07 | Phase 2 | Pending |
| ERR-01 | Phase 3 | Pending |
| ERR-02 | Phase 3 | Pending |
| ERR-03 | Phase 3 | Pending |
| ERR-04 | Phase 3 | Pending |
| ERR-05 | Phase 3 | Pending |
| ERR-06 | Phase 3 | Pending |
| ERR-07 | Phase 3 | Pending |
| OSART-01 | Phase 4 | Pending |
| OSART-02 | Phase 4 | Pending |
| OSART-03 | Phase 4 | Pending |
| OSART-04 | Phase 4 | Pending |
| OSART-05 | Phase 4 | Pending |
| QUAL-01 | Phase 5 | Pending |
| QUAL-02 | Phase 5 | Pending |
| QUAL-03 | Phase 5 | Pending |
| QUAL-04 | Phase 5 | Pending |
| QUAL-05 | Phase 5 | Pending |
| QUAL-06 | Phase 5 | Pending |
| DEPLOY-01 | Phase 6 | Pending |
| DEPLOY-02 | Phase 6 | Pending |
| DEPLOY-03 | Phase 6 | Pending |
| DEPLOY-04 | Phase 6 | Pending |
| DEPLOY-05 | Phase 6 | Pending |
| DEPLOY-06 | Phase 6 | Pending |
| GAP-01 | Phase 6 | Pending |
| GAP-02 | Phase 6 | Pending |
| GAP-03 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-24 after initial definition*
