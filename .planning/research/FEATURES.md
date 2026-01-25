# Feature Landscape: DFIR MCP Tool Validation

**Domain:** Digital Forensics & Incident Response Tool Testing
**Researched:** 2026-01-24

## Table Stakes

Features users expect. Missing = validation feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Functional Smoke Testing** | Confirms basic tool operations work (list, get, query) | Low | Container-based, fast feedback (<5min) |
| **Error Handling Validation** | DFIR tools must gracefully handle network failures, invalid input, missing resources | Medium | Test timeouts, malformed VQL, non-existent clients |
| **Output Structure Validation** | Responses must match expected schemas for AI assistant parsing | Low | Schema validation against OpenAPI/JSON schemas |
| **Connectivity Health Checks** | Verify API connection, authentication, server reachability | Low | Precondition for all other tests |
| **Basic VQL Correctness** | VQL queries must execute without syntax errors | Medium | Syntax validation, basic query execution |
| **Tool Method Availability** | All 35 MCP tools must be callable and return responses | Low | Method signature verification |
| **Deployment Verification** | Docker/binary deployments must result in running, accessible servers | Medium | Container health checks, port binding validation |
| **Repeatability** | Same test inputs produce same outputs (NIST requirement) | Medium | Run tests multiple times, compare results |
| **Reproducibility** | Tests pass in different environments (local, CI, container) | Medium | Cross-environment validation per NIST standards |

## Differentiators

Features that set comprehensive validation apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Real-World Data Validation** | Test against actual DFIR workflows, not just mocks | High | Requires enrolled clients, artifact collections, hunt data |
| **Performance Benchmarking** | Measure response times, pagination efficiency, large result handling | Medium | Identifies scalability issues before production |
| **End-to-End Workflow Testing** | Full investigation workflows (triage → collect → analyze) | High | Multi-tool coordination, state management |
| **False Positive Detection** | Measure error rates in tool outputs (NIST metric) | High | Requires known-good baseline datasets |
| **VQL Query Coverage** | Test VQL plugin ecosystem (pslist, registry, network, etc.) | High | Validates breadth of DFIR capabilities |
| **Agent Deployment Validation** | SSH/WinRM/GPO deployment to real endpoints | High | Physical lab or VMs required |
| **Multi-Client Hunt Testing** | Hunts across multiple enrolled endpoints | Medium | Validates scalability, coordination |
| **Rollback and Recovery** | Test deployment rollback, error recovery, cleanup | Medium | Ensures operational safety |
| **Output Quality Metrics** | Validate forensic soundness (hashing, chain of custody) | High | DFIR-specific correctness beyond functional tests |
| **Parallel Test Execution** | Isolated container tests run in parallel | Medium | Performance gain, reduces feedback time |
| **AI-Enhanced Error Detection** | Use LLMs to detect anomalies in tool outputs | High | Emerging DFIR-Metric pattern from 2025/2026 |

## Anti-Features

Testing approaches to explicitly NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Mock-Only Testing** | Already done (104 tests). Mocks miss real integration issues (SQL syntax, constraints, gRPC timeouts) | Test against real Velociraptor containers using Testcontainers pattern |
| **Manual Test Repetition** | DFIR validation requires frequent revalidation (quarterly/biannually per forensic standards) | Automate smoke, sanity, and regression test suites |
| **Production Testing First** | Testing in production risks evidence contamination, violates forensic integrity | Test container → physical lab → cloud (progression pattern) |
| **Ignoring NIST Standards** | DFIR tools must meet admissibility standards (Daubert, NIST CFTT) | Validate repeatability, reproducibility, error rates |
| **Generic API Testing** | DFIR has domain-specific requirements (chain of custody, forensic soundness, artifact integrity) | Use DFIR-specific metrics: hash validation, timeline accuracy, artifact completeness |
| **Single-Environment Testing** | Tests that only pass in one environment aren't reproducible | Run tests in container, local, CI environments |
| **Testing Without Real Endpoints** | Many tools (collect_artifact, hunts, flows) need enrolled clients | Enroll test client in container, validate against real agent |
| **Shallow Pagination Testing** | Large hunt results (thousands of rows) expose pagination bugs at scale | Test with offset-based and cursor-based patterns, measure performance degradation |
| **Undocumented Test Data** | Forensic validation requires known-good datasets for comparison | Document test artifacts, expected outputs, baseline metrics |
| **Skipping Error Cases** | DFIR tools encounter network failures, malformed queries, permission errors frequently | Negative testing (timeouts, invalid input, missing resources) is table stakes |

## Feature Dependencies

```
Connectivity Health Checks
  └─> Functional Smoke Testing
        ├─> Error Handling Validation
        │     └─> Output Quality Metrics
        ├─> Output Structure Validation
        │     └─> Real-World Data Validation
        └─> Basic VQL Correctness
              ├─> VQL Query Coverage
              └─> Multi-Client Hunt Testing

Deployment Verification
  └─> Agent Deployment Validation
        └─> End-to-End Workflow Testing

Repeatability + Reproducibility (parallel, independent requirement)
```

**Critical Path:** Container deployment → Health checks → Smoke tests → Error handling → Real-world workflows

## Test Category Breakdown

### Category 1: Smoke Tests (Container-Based)
**Purpose:** First line of defense, verify build stability
**Scope:** All 35 MCP tools callable, basic operations work
**Infrastructure:** Docker container with Velociraptor server
**Speed:** Fast (<5 minutes total)
**Run Frequency:** Every commit, PR gate

**What to Test:**
- Tool registration and availability
- Basic CRUD operations (list, get, create where applicable)
- Server connectivity and authentication
- Simple VQL query execution
- Resource browsing (velociraptor:// URIs)

**Success Criteria:**
- All tools return non-error responses
- Basic queries complete within timeout
- No authentication failures
- Server health endpoint responds

### Category 2: Sanity Tests (Container + Single Client)
**Purpose:** Validate recent changes haven't broken critical workflows
**Scope:** Key DFIR operations with enrolled test client
**Infrastructure:** Docker container + enrolled client agent
**Speed:** Medium (10-20 minutes)
**Run Frequency:** Post-merge, nightly builds

**What to Test:**
- Client management (list, label, quarantine)
- Artifact collection on enrolled client
- Flow status tracking and results retrieval
- Hunt creation and execution
- VQL queries against client data
- Error handling for common failures

**Success Criteria:**
- Collections complete successfully
- Results match expected structure
- Errors are graceful with clear messages
- State transitions (running → completed) work correctly

### Category 3: Integration Tests (Container + Multiple Clients)
**Purpose:** Validate multi-client coordination and scalability
**Scope:** Hunts, bulk operations, large result sets
**Infrastructure:** Docker container + 3-5 enrolled clients
**Speed:** Slow (30-60 minutes)
**Run Frequency:** Weekly, pre-release

**What to Test:**
- Multi-client hunts
- Large result pagination
- Concurrent collections
- Client search and filtering
- VQL aggregations across clients
- Performance under load

**Success Criteria:**
- Hunts complete across all clients
- Pagination handles 1000+ results
- No race conditions or deadlocks
- Response times within acceptable limits

### Category 4: End-to-End Workflow Tests (Lab Environment)
**Purpose:** Validate complete DFIR investigation workflows
**Scope:** Real-world incident response scenarios
**Infrastructure:** Physical/VM lab with Windows/Linux endpoints
**Speed:** Very Slow (1-2 hours)
**Run Frequency:** Pre-release, milestone validation

**What to Test:**
- Deployment automation (Docker, Binary)
- Agent deployment (SSH, WinRM)
- Full investigation workflow (triage → collect → analyze)
- Deployment profiles (rapid, standard, enterprise)
- Rollback and recovery scenarios
- Certificate and credential management

**Success Criteria:**
- Server deploys and agents connect
- Investigation artifacts collected successfully
- Output is forensically sound (hashes match, timestamps accurate)
- Deployments can be torn down cleanly

### Category 5: Error Handling & Edge Cases
**Purpose:** Validate graceful degradation and error messages
**Scope:** All tools under failure conditions
**Infrastructure:** Container with simulated failures
**Speed:** Medium (15-30 minutes)
**Run Frequency:** Weekly, regression suite

**What to Test:**
- Network timeouts and connection failures
- Malformed VQL syntax
- Non-existent resources (clients, hunts, flows)
- Invalid parameters (negative limits, empty IDs)
- Permission/authentication errors
- Server overload (rate limiting)

**Success Criteria:**
- No stack traces exposed to users
- Error messages are clear and actionable
- HTTP status codes are correct (400, 404, 500 series)
- Retry logic handles transient failures
- Tools don't crash on bad input

### Category 6: Output Quality & Forensic Soundness
**Purpose:** Ensure DFIR-specific correctness
**Scope:** Artifact integrity, timeline accuracy, hash validation
**Infrastructure:** Container + known-good test datasets
**Speed:** Medium (20-40 minutes)
**Run Frequency:** Weekly, pre-release

**What to Test:**
- Hash validation (collected artifacts match expected hashes)
- Timeline accuracy (timestamps are correct and consistent)
- Artifact completeness (all expected data present)
- VQL result correctness (compare against known outputs)
- False positive rate (per NIST CFTT methodology)
- Data integrity (no corruption in collection/transfer)

**Success Criteria:**
- All hashes match baseline
- Timestamps within acceptable drift (±1 second)
- Zero false positives on known-good datasets
- VQL results match reference outputs
- Collected data is bit-for-bit identical to source

### Category 7: Performance & Scalability
**Purpose:** Identify performance bottlenecks before production
**Scope:** Large result sets, concurrent operations, pagination
**Infrastructure:** Container with performance test data
**Speed:** Slow (45-60 minutes)
**Run Frequency:** Weekly, pre-release

**What to Test:**
- Pagination performance (offset vs cursor-based)
- Large hunt results (10K+ rows)
- Concurrent VQL queries
- Client search with thousands of clients
- Artifact collection time vs size
- Memory usage under load

**Success Criteria:**
- Response times scale sub-linearly with result size
- No memory leaks or resource exhaustion
- Pagination remains fast at high offsets
- Concurrent operations don't cause contention
- Performance metrics documented for baseline

## MVP Recommendation

For milestone v1.0, prioritize:

1. **Smoke Tests (Category 1)** - Gate for all commits
2. **Sanity Tests (Category 2)** - Validate core DFIR workflows
3. **Error Handling (Category 5)** - Ensure robustness
4. **End-to-End Docker Deployment (Category 4 subset)** - Prove deployment automation works

Defer to post-v1.0:

- **Multi-Client Integration (Category 3)**: Requires lab infrastructure scaling
- **Agent Deployment (Category 4 full)**: Physical/cloud deployment testing
- **Performance Benchmarking (Category 7)**: Optimization phase, not initial validation
- **AI-Enhanced Error Detection**: Emerging pattern, not mature enough for v1.0

## Infrastructure Requirements

| Test Category | Infrastructure | Setup Complexity | Estimated Cost |
|---------------|----------------|------------------|----------------|
| Smoke | Docker container | Low | Free (local) |
| Sanity | Docker + 1 client | Medium | Free (local) |
| Integration | Docker + 3-5 clients | Medium-High | Free (local) or $50/mo (cloud VMs) |
| End-to-End | Physical lab / cloud VMs | High | $200-500/mo (cloud) or one-time hardware |
| Error Handling | Docker + mocks | Low | Free |
| Output Quality | Docker + test datasets | Medium | Free |
| Performance | Docker + generated data | Medium | Free (local) |

**Recommended Progression:**
1. Container (Smoke, Sanity, Error, Output Quality) - Week 1-2
2. Container + Clients (Integration subset) - Week 3
3. Physical Lab (End-to-End deployment) - Week 4+

## Test Data Requirements

| Test Type | Data Needed | Source |
|-----------|-------------|--------|
| Smoke | Velociraptor server config, API credentials | Auto-generated by test fixture |
| Sanity | Enrolled test client, sample artifacts | Docker Compose setup script |
| Integration | 3-5 enrolled clients, hunt data | Container orchestration script |
| Output Quality | Known-good artifact baselines, expected hashes | Curated test dataset (store in tests/fixtures/) |
| Performance | Large hunt results (10K+ rows) | Generated synthetic data or real hunt exports |
| Error Handling | Malformed VQL, invalid IDs | Test case definitions (hardcoded) |

**Critical:** Document all test datasets in `tests/fixtures/README.md` with:
- Artifact purpose
- Expected outputs
- Hash baselines
- Update date

This is a NIST requirement for forensic tool validation.

## Validation Criteria Summary

| Aspect | Metric | Target |
|--------|--------|--------|
| **Tool Coverage** | % of 35 tools tested | 100% |
| **Error Handling** | % of error cases handled gracefully | 95%+ |
| **Repeatability** | Test runs producing same result | 100% (NIST) |
| **Reproducibility** | Pass rate across environments | 95%+ (NIST) |
| **False Positive Rate** | Incorrect results / total results | <1% (NIST CFTT) |
| **Response Time** | P95 latency for basic queries | <2 seconds |
| **Output Correctness** | Results matching known-good baselines | 100% |
| **Deployment Success** | Successful deploys / total attempts | 95%+ |

## Known Gaps (From Current Implementation)

Based on existing 104 tests (mocks only):

**Missing:**
- Real Velociraptor server integration (Category 1-4)
- Agent enrollment and deployment (Category 4)
- Large result pagination tests (Category 3, 7)
- VQL error handling validation (Category 5)
- Output quality metrics (Category 6)
- Performance baselines (Category 7)

**Present:**
- Unit tests for configuration, credentials, certificates
- Mock-based tool tests
- Deployment profile validation

**Gap Priority:**
1. HIGH: Real server integration (Categories 1-2)
2. HIGH: Error handling validation (Category 5)
3. MEDIUM: End-to-end deployment (Category 4)
4. MEDIUM: Output quality validation (Category 6)
5. LOW: Performance benchmarking (Category 7)
6. LOW: Multi-client testing (Category 3)

## Sources

### DFIR Standards and Validation
- [Validation of Forensic Tools - Josh Brunty's Blog](https://joshbrunty.github.io/2021/11/01/validation.html)
- [NIST Computer Forensics Tool Testing Program (CFTT)](https://www.nist.gov/itl/ssd/software-quality-group/computer-forensics-tool-testing-program-cftt)
- [Tool Testing - AboutDFIR](https://aboutdfir.com/resources/tool-testing/)
- [Digital Forensic Standards and Best Practices - Eclipse Forensics](https://eclipseforensics.com/digital-forensic-standards-and-best-practices/)
- [DFIR-Metric Benchmark Dataset (arXiv 2025)](https://arxiv.org/pdf/2505.19973)

### Velociraptor Testing
- [Incident Response Analysis in VDI: Velociraptor](https://www.infoguard.ch/en/blog/dfir-velociraptor-scans-vhdx)
- [Using Velociraptor for large-scale endpoint visibility](https://www.pentestpartners.com/security-blog/using-velociraptor-for-large-scale-endpoint-visibility-and-rapid-threat-hunting/)
- [Velociraptor Support Policy](https://docs.velociraptor.app/docs/overview/support/)

### API Testing and Error Handling
- [Best Practices for API Error Handling - Postman](https://blog.postman.com/best-practices-for-api-error-handling/)
- [REST API Testing Guide 2026](https://talent500.com/blog/rest-api-testing-guide-2026/)
- [How to ensure API quality in 2026](https://apiquality.io/ensure-api-quality-2026/)
- [Best Practices for Consistent API Error Handling - Zuplo](https://zuplo.com/learning-center/best-practices-for-api-error-handling)

### Container-Based Testing
- [How to Write Integration Tests for Rust APIs with Testcontainers (2026)](https://oneuptime.com/blog/post/2026-01-07-rust-testcontainers/view)
- [What is Testcontainers?](https://testcontainers.com/guides/introducing-testcontainers/)
- [Integration Testing in Containers - Ensono](https://www.ensono.com/insights-and-news/expert-opinions/integration-testing-in-containers/)
- [Integration testing for Go applications using Testcontainers - Azure Blog](https://devblogs.microsoft.com/cosmosdb/integration-testing-for-go-applications-using-testcontainers-and-containerized-databases/)

### Performance and Pagination Testing
- [Pagination Performance Testing in Spring Boot](https://medium.com/@AlexanderObregon/pagination-performance-testing-in-spring-boot-rest-endpoints-8aedd293c1fb)
- [API Pagination Patterns - Mulesoft](https://www.mulesoft.com/api/design/api-pagination-patterns)
- [Simple Pagination Testing - LoadForge](https://loadforge.com/directory/advanced-api-patterns/simple-pagination-testing)
- [Pagination for large result sets - Microsoft Learn](https://learn.microsoft.com/en-us/sharepoint/dev/general-development/pagination-for-large-result-sets)

### Testing Progression Patterns
- [Smoke Testing vs Sanity Testing in 2026 - BrowserStack](https://www.browserstack.com/guide/sanity-testing-vs-smoke-testing)
- [The Smoke, Sanity, and Regression Testing Triad - CloudBees](https://www.cloudbees.com/blog/the-smoke-sanity-and-regression-testing-triad)
- [Understanding Smoke, Sanity & Regression Testing - Qentelli](https://qentelli.com/thought-leadership/insights/explained-smoke-testing-vs-sanity-testing-vs-regression-testing)
