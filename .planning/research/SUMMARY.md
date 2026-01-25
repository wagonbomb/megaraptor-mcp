# Project Research Summary

**Project:** Megaraptor MCP - Real-World Validation Testing
**Domain:** DFIR Tool Testing & Quality Assurance
**Researched:** 2026-01-24
**Confidence:** HIGH

## Executive Summary

This project extends an existing MCP server with 35 Velociraptor DFIR tools from mock-based unit tests to real-world validation against live Velociraptor infrastructure. The expert approach centers on container-based testing with Docker-managed Velociraptor servers and enrolled clients, progressing through smoke tests, sanity tests, integration tests, and finally end-to-end workflow validation. This follows established DFIR validation standards (NIST CFTT) while maintaining forensic integrity.

The recommended approach keeps the existing pytest/asyncio foundation and adds three targeted libraries: pytest-docker for container lifecycle management, pytest-check for comprehensive multi-assertion validation, and jsonschema for VQL output structure validation. The architecture extends existing test fixtures through composition rather than duplication, using session-scoped infrastructure to avoid expensive container restarts. Start with Generic artifacts on Linux containers, validate output structure first (low complexity), then expand to content validation and multi-OS targets.

Critical risks include gRPC connection leaks (causes cascading test failures), incomplete cleanup of Velociraptor state between tests (non-deterministic results), and async flow completion race conditions (flaky tests). Mitigate these by establishing connection lifecycle patterns in Phase 1, implementing mandatory cleanup fixtures for all Velociraptor entities, and creating async operation wait helpers before any artifact collection tests. Certificate expiration monitoring is essential for long-term test infrastructure stability.

## Key Findings

### Recommended Stack

The project has a solid pytest foundation (7.0.0+) with asyncio support and Docker integration already in place. Research recommends adding three core libraries for validation testing while deferring performance testing tools until validation reveals need.

**Core technologies:**
- **pytest-docker 3.2.5**: Container lifecycle management - Works with existing docker-compose.test.yml, replaces manual subprocess calls, provides health check waiting and automatic teardown
- **pytest-check 2.6.2**: Multi-assertion validation - Critical for DFIR validation where you need complete picture of output quality, not just first failure
- **jsonschema 4.26.0**: VQL output schema validation - Formal contract validation for VQL query results, ensures output structure matches expectations for AI parsing

**Defer to Phase 2:**
- **Locust**: Performance/load testing - Wait until validation reveals performance issues, premature optimization
- **pytest-xdist**: Parallel execution - Nice-to-have for speed but not critical for initial validation
- **pytest-cov**: Coverage reporting - Useful for gap analysis but not required for validation milestone

**Skip entirely:**
- **pytest-grpc**: Unmaintained (2020), real Velociraptor container superior to mocked gRPC
- **testcontainers-python**: docker-compose.yml already exists, pytest-docker leverages it better
- **grpc_testing**: Project moving away from mocks toward real container testing

### Expected Features

DFIR tool validation has well-established expectations from NIST Computer Forensics Tool Testing Program (CFTT). Missing table stakes features make validation feel incomplete and fail to meet admissibility standards.

**Must have (table stakes):**
- **Functional Smoke Testing** - All 35 MCP tools callable with basic operations working, container-based, <5min feedback
- **Error Handling Validation** - Graceful handling of timeouts, malformed VQL, missing resources, network failures
- **Output Structure Validation** - Responses match expected schemas (JSON Schema validation against VQL results)
- **Connectivity Health Checks** - API connection, authentication, server reachability before tests
- **Basic VQL Correctness** - VQL queries execute without syntax errors
- **Repeatability & Reproducibility** - NIST requirement: same inputs produce same outputs, tests pass across environments

**Should have (competitive differentiators):**
- **Real-World Data Validation** - Test against actual DFIR workflows with enrolled clients and artifact collections
- **Performance Benchmarking** - Response times, pagination efficiency, large result handling
- **End-to-End Workflow Testing** - Full investigation workflows (triage, collect, analyze)
- **VQL Query Coverage** - Test VQL plugin ecosystem breadth (pslist, registry, network)
- **Parallel Test Execution** - Isolated container tests run in parallel for faster feedback

**Defer (v2+):**
- **False Positive Detection** - Requires known-good baseline datasets, high complexity
- **Agent Deployment Validation** - SSH/WinRM/GPO deployment to real endpoints needs physical lab
- **Multi-Client Hunt Testing** - Requires scalability infrastructure beyond initial validation
- **AI-Enhanced Error Detection** - Emerging DFIR-Metric pattern from 2025/2026, not mature yet

**Anti-features to avoid:**
- **Mock-Only Testing** - Already done (104 tests), mocks miss real integration issues
- **Production Testing First** - Risks evidence contamination, violates forensic integrity
- **Single-Environment Testing** - Tests must pass in container, local, and CI environments
- **Shallow Pagination Testing** - Large hunt results expose bugs at scale, must test with thousands of rows

### Architecture Approach

The validation architecture extends the existing three-layer test infrastructure (unit, integration, validation) through fixture composition. All validation tests reuse session-scoped Docker infrastructure and module-scoped VelociraptorClient connections without requiring new containers or authentication. The TargetRegistry abstraction enables capability-based target selection (by OS, artifact support) rather than hardcoded client IDs, allowing tests to adapt to available infrastructure.

**Major components:**
1. **ValidationTargetFixture** - Extends docker_compose_up, registers enrolled clients from Docker/VMs/physical hosts, provides capability-based selection for tests
2. **ArtifactValidator** - Separates collection from validation, defines reusable field validation rules, produces structured ValidationReport objects for debugging
3. **ValidationRunner** - Orchestrates collection → verification → cleanup workflow, waits for async flow completion, ensures test isolation through cleanup
4. **TargetRegistry** - Tracks available test targets, queries Velociraptor for enrolled client IDs dynamically, prevents hardcoded client ID brittleness

**Key patterns to follow:**
- **Fixture Composition Over Duplication** - Build validation fixtures by composing existing fixtures (docker_compose_up, velociraptor_client), never duplicate infrastructure setup
- **Capability-Based Target Selection** - Select targets by capabilities ("windows", "linux", "full_filesystem") not specific IDs, tests adapt to infrastructure
- **Parametrized Artifact Validation** - Use pytest.mark.parametrize to test multiple artifacts with same structure, reduces duplication
- **Validation Report Objects** - Return structured reports instead of bare assertions for better failure diagnostics

### Critical Pitfalls

**1. gRPC Connection Pooling Without Lifecycle Management**
Prevent by using module-scoped velociraptor_client fixture with explicit close() in teardown. Detection: Docker container memory grows, netstat shows increasing connections, tests pass individually but fail in suite. Must establish in Phase 1 - addressing later causes test suite rewrite.

**2. Test Isolation Failure - Velociraptor State Pollution**
Prevent by implementing cleanup fixtures that archive/delete hunts, flows, labels created during tests. Use test name markers in entity descriptions for automated cleanup. Detection: Tests fail on second run with "expected 0 hunts but found 47" errors. Critical for Phase 1 - retrofitting cleanup into 35 tools after implementation is extremely expensive.

**3. Async Operation Timing - Flow Completion Race Conditions**
Prevent by creating wait_for_flow_completion helper that polls System.Flow.Completion events, never use hardcoded sleep. Detection: Tests pass with pytest -v but fail with pytest -q, adding sleep(10) fixes it. Must implement before Phase 2 artifact collection - timing issues compound with hunt operations.

**4. Certificate Expiration in Long-Running Test Infrastructure**
Prevent by adding cert expiration check to test-lab.sh status command, regenerate configs older than 30 days in CI. Detection: All tests fail overnight with x509 errors despite no code changes. Set up monitoring in Phase 1 for long-term stability.

**5. Docker Volume Persistence Assumptions**
Prevent by documenting volume lifecycle in test-lab.sh (down vs clean commands), add volume inspection command. Detection: Tests behave differently after ./test-lab.sh clean vs down. Document in Phase 1 to avoid state confusion.

## Implications for Roadmap

Based on research, validation work should progress through container-based testing phases before expanding to physical infrastructure. Start with low-complexity Generic artifacts to establish patterns, then increase validation strictness and target diversity.

### Phase 1: Test Infrastructure & Core Patterns
**Rationale:** Must establish connection lifecycle, cleanup patterns, and async operation handling before any artifact validation. These foundational patterns prevent expensive rewrites if addressed later. All validation tests depend on this infrastructure.

**Delivers:**
- pytest-docker, pytest-check, jsonschema installed and integrated
- validation_targets fixture extending docker_compose_up
- wait_for_flow_completion helper for async operations
- Cleanup fixture pattern for Velociraptor entities
- First smoke test validating Generic.Client.Info

**Addresses:**
- Connectivity Health Checks (FEATURES.md table stakes)
- Functional Smoke Testing foundation
- Tool Method Availability verification

**Avoids:**
- gRPC connection leaks (Pitfall 1) via module-scoped client fixture
- Certificate expiration surprises (Pitfall 4) via monitoring
- Docker volume confusion (Pitfall 5) via documentation

**Research flag:** Standard pytest patterns - NO ADDITIONAL RESEARCH NEEDED

### Phase 2: Generic Artifact Validation (Smoke Tests)
**Rationale:** Generic artifacts work on any target (cross-platform), have simple schemas, and catch most common integration bugs. Starting here validates infrastructure works before OS-specific complexity. Establishes artifact validation patterns for later phases.

**Delivers:**
- Generic.Client.Info validation (fields, types)
- Generic.System.Pslist validation (process list structure)
- Generic.Client.BrowserHistory validation (file parsing)
- ArtifactValidator framework with reusable rules
- Parametrized test patterns for similar artifacts

**Uses:**
- pytest-check for multi-assertion validation
- jsonschema for VQL output structure validation
- Existing velociraptor_client fixture

**Implements:**
- ArtifactValidator component with ValidationReport
- Capability-based target selection via TargetRegistry

**Avoids:**
- Async race conditions (Pitfall 3) via wait_for_flow_completion
- State pollution (Pitfall 2) via cleanup fixtures
- Hardcoded client IDs (Pitfall 9) via dynamic enrollment lookup

**Research flag:** Generic artifacts well-documented - NO ADDITIONAL RESEARCH NEEDED

### Phase 3: Error Handling & Edge Cases
**Rationale:** Error handling is table stakes for DFIR tools. Validating graceful degradation early prevents production issues. Can run in parallel with Phase 2 artifact expansion since it uses different test scenarios (negative testing).

**Delivers:**
- Network timeout handling validation
- Malformed VQL syntax error messages
- Non-existent resource handling (clients, hunts, flows)
- Invalid parameter testing (negative limits, empty IDs)
- Authentication/permission error validation

**Addresses:**
- Error Handling Validation (FEATURES.md table stakes)
- Output quality metrics (clear error messages)

**Avoids:**
- VQL timeout misunderstanding (Pitfall 6) via LIMIT clauses and streaming
- Insufficient test logging (Pitfall 10) via structured logging

**Research flag:** Standard error handling patterns - NO ADDITIONAL RESEARCH NEEDED

### Phase 4: OS-Specific Artifacts (Sanity Tests)
**Rationale:** After establishing patterns with Generic artifacts, expand to OS-specific validation. Requires Windows container or VM setup. Tests against enrolled client with real data collection.

**Delivers:**
- Linux.Sys.Users validation
- Windows.System.Services validation (if Windows target available)
- Windows.Registry.UserAssist validation (registry parsing)
- Multi-OS target support in TargetRegistry

**Uses:**
- Artifact validation patterns from Phase 2
- Windows Docker container (optional) or VM

**Implements:**
- OS capability filtering in TargetRegistry
- Complex validation rules (registry, binary parsing)

**Avoids:**
- Test client enrollment race (Pitfall 8) via wait_for_enrollment fixture
- Validation without expected state (Anti-pattern 3) via test data setup

**Research flag:** OS-specific artifacts may need deeper research for validation schemas - PLAN FOR RESEARCH-PHASE

### Phase 5: Output Quality & Forensic Soundness
**Rationale:** DFIR-specific correctness beyond functional testing. Validates artifact integrity, timeline accuracy, hash validation. Requires known-good baseline datasets stored in tests/fixtures/.

**Delivers:**
- Hash validation (collected artifacts match expected)
- Timeline accuracy testing (timestamp correctness)
- Artifact completeness validation (all expected data present)
- VQL result correctness (compare against baselines)
- Baseline dataset documentation

**Addresses:**
- Output Quality Metrics (FEATURES.md differentiator)
- NIST CFTT false positive rate requirements
- Forensic soundness validation

**Implements:**
- Baseline comparison framework
- Test fixture dataset with documented hashes

**Avoids:**
- Evidence integrity issues via TEST- prefixes
- Undocumented test data via fixtures/README.md

**Research flag:** NIST validation standards established - NO ADDITIONAL RESEARCH NEEDED

### Phase 6: End-to-End Deployment Validation
**Rationale:** Validates deployment automation works (Docker, Binary profiles). Tests full investigation workflow. Deferred until core artifact validation complete because it requires physical/cloud infrastructure scaling.

**Delivers:**
- Docker deployment profile validation
- Binary deployment verification
- Full investigation workflow (triage → collect → analyze)
- Deployment rollback testing

**Addresses:**
- Deployment Verification (FEATURES.md table stakes)
- End-to-End Workflow Testing (FEATURES.md differentiator)

**Uses:**
- Existing test-lab.sh automation
- Physical lab or cloud VMs

**Avoids:**
- Production testing first anti-pattern
- Single-environment testing limitation

**Research flag:** Deployment patterns well-established - NO ADDITIONAL RESEARCH NEEDED

### Phase Ordering Rationale

- **Phase 1 before all others:** Connection lifecycle and cleanup patterns must be established first to avoid expensive rewrites. These are foundational for all validation tests.
- **Phase 2 before Phase 4:** Generic artifacts establish validation patterns without OS-specific complexity. Patterns proven on simple artifacts transfer to complex ones.
- **Phase 3 parallel to Phase 2:** Error handling uses different test scenarios (negative testing) so can run concurrently without dependency conflicts.
- **Phase 5 after Phase 2/4:** Output quality validation requires artifact validation patterns to be established. Builds on functional correctness with forensic soundness.
- **Phase 6 last:** End-to-end deployment requires physical infrastructure and is less critical than artifact correctness. Core validation must work before investing in deployment testing.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 4 (OS-Specific Artifacts):** Complex validation schemas for registry keys, binary artifacts, Windows-specific forensic structures may need artifact-specific research
- **Phase 6 (Deployment):** Physical lab setup, cloud VM configuration, multi-environment orchestration may need infrastructure research if scaling beyond Docker

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** pytest fixture patterns well-documented, Docker Compose patterns established
- **Phase 2:** Generic artifact schemas simple and well-defined in Velociraptor docs
- **Phase 3:** Error handling patterns standard across API testing
- **Phase 5:** NIST CFTT validation methodology documented and stable

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | pytest-docker, pytest-check, jsonschema all actively maintained, version-compatible, integrate cleanly. Existing pytest foundation solid. |
| Features | HIGH | NIST CFTT standards well-established (20+ years), DFIR validation requirements documented extensively, clear table stakes vs differentiators |
| Architecture | HIGH | Integration points with existing test infrastructure verified via code review (conftest.py, test_dfir_tools.py). Fixture composition pattern proven. |
| Pitfalls | HIGH | gRPC connection issues, async timing, state pollution are well-documented in Velociraptor GitHub issues and gRPC best practices. Evidence-based from real deployments. |

**Overall confidence:** HIGH

Research is based on official Velociraptor documentation, NIST standards, actively maintained library docs, and existing codebase analysis. All major recommendations have concrete source citations and proven patterns.

### Gaps to Address

**Minor gaps requiring validation during implementation:**

- **VQL timeout behavior specifics:** Velociraptor documentation mentions 10-minute notebook timeout but doesn't clearly specify how it applies to API queries vs collections. Test empirically in Phase 1 to establish timeout patterns.

- **Windows container availability:** Research assumes Windows Docker container exists (winamd64/velociraptor-client) but availability may vary. Validate container exists before Phase 4, fallback to VM or defer Windows testing if unavailable.

- **Artifact-specific validation schemas:** Generic artifacts have simple schemas, but complex artifacts (prefetch, registry, binary parsing) may need artifact-specific research. Plan for research-phase spikes in Phase 4 when encountering complex validation requirements.

- **Certificate rotation in CI:** Research identifies certificate expiration monitoring need but doesn't specify CI-specific automation strategy. Design automated regeneration workflow during Phase 1 implementation based on CI platform (GitHub Actions, GitLab CI, etc).

## Sources

### Primary (HIGH confidence)
- **Velociraptor Official Documentation** - API reference, VQL fundamentals, deployment troubleshooting, System.Flow.Completion events, notebook timeout configuration
- **NIST Computer Forensics Tool Testing Program (CFTT)** - Validation methodology, repeatability/reproducibility requirements, false positive rate standards
- **pytest-docker 3.2.5 GitHub/PyPI** - Container lifecycle management, fixture patterns, health check waiting
- **pytest-check 2.6.2 PyPI** - Multi-assertion validation patterns, usage examples
- **jsonschema 4.26.0 Documentation** - JSON Schema validation, Draft 2020-12 support
- **Existing codebase** - conftest.py fixtures, test_dfir_tools.py patterns, test-lab.sh orchestration, docker-compose.test.yml configuration

### Secondary (MEDIUM confidence)
- **Velociraptor GitHub Issues** - x509 certificate validation (#962), certificate expiration (#3583), collection stalling (#1914), deployment discussions (#2920)
- **gRPC Performance Best Practices** - Connection pooling patterns, memory leak issues (#36117), channel lifecycle management
- **DFIR Validation Resources** - Josh Brunty's validation methodology, MANTIS DFIR testing platform patterns, DFIR-Metric benchmark (arXiv 2025)
- **pytest Best Practices** - Integration testing patterns, pytest-xdist parallelization, fixture scope management

### Tertiary (LOW confidence - needs validation)
- **DFIR-Metric AI-Enhanced Error Detection** - Emerging pattern from 2025/2026 research paper, not yet proven in production DFIR tools
- **ForensicArtifacts Repository** - Schema-driven validation potential for Phase 3+ scaling, not yet validated for Velociraptor artifact format compatibility

---
*Research completed: 2026-01-24*
*Ready for roadmap: yes*
