# Domain Pitfalls: DFIR Tool Validation Against Live Velociraptor

**Domain:** DFIR tool validation and integration testing
**Researched:** 2026-01-24
**Confidence:** HIGH

## Executive Summary

Testing DFIR tools against live Velociraptor deployments requires careful attention to test isolation, connection lifecycle, timing issues with asynchronous operations, and evidence integrity. This document catalogs pitfalls specific to validating 35 MCP tools against live Velociraptor containers, physical servers, and deployed agents.

**Critical finding:** The most dangerous pitfalls involve gRPC connection resource leaks and incomplete cleanup between tests, which can cause cascading failures that mask actual bugs while creating false positives.

## Critical Pitfalls

These mistakes cause rewrites, test infrastructure failures, or data corruption.

### Pitfall 1: gRPC Connection Pooling Without Lifecycle Management

**What goes wrong:** Tests create new gRPC channels for every API call without proper cleanup, leading to connection exhaustion and memory leaks. Streaming calls left running don't just leak client resources but remain active on the server.

**Why it happens:**
- gRPC channels are meant to be long-lived and reused
- Tests often follow "setup-execute-teardown" patterns that don't align with connection pooling
- Failed connections don't reduce memory, causing gradual memory growth
- Developers assume garbage collection will handle cleanup

**Consequences:**
- Test suite becomes progressively slower as leaked connections accumulate
- "Connection refused" errors appear in later tests despite server being healthy
- Server-side resource exhaustion causes cascading failures across tests
- Timeout errors that are actually connection pool exhaustion
- False negatives where tests pass individually but fail in suite

**Prevention:**
```python
# BAD - Creates new channel per test
def test_list_clients():
    client = VelociraptorClient()
    client.connect()
    results = client.query("SELECT * FROM clients()")
    # Missing cleanup - channel leaked

# GOOD - Reuse channel with proper cleanup
@pytest.fixture(scope="module")
def velociraptor_client():
    client = VelociraptorClient()
    client.connect()
    yield client
    client.close()  # Guaranteed cleanup

def test_list_clients(velociraptor_client):
    results = velociraptor_client.query("SELECT * FROM clients()")
```

**Detection:**
- Monitor Docker container memory: `docker stats vr-test-server`
- Check open connections: `netstat -an | grep 8001 | wc -l` increasing over time
- Tests pass individually but fail when run as suite
- `grpc._channel._InactiveRpcError` exceptions increase over test run

**Phase impact:** Phase 1 (test infrastructure setup) must establish connection lifecycle patterns. Addressing later causes test suite rewrite.

### Pitfall 2: Test Isolation Failure - Velociraptor State Pollution

**What goes wrong:** Tests don't clean up artifacts, hunts, flows, or labels created during execution, causing subsequent tests to fail due to unexpected server state. Test data accumulates across runs, making debugging impossible.

**Why it happens:**
- Velociraptor persists all data to disk (flows, hunts, collected artifacts)
- Docker volume `vr-server-data` survives container restarts
- Tests create hunts/flows/labels but don't remove them
- Assumption that container restart = clean state (false with volumes)
- Incomplete understanding of Velociraptor's data persistence model

**Consequences:**
- Test results become non-deterministic (pass/fail depends on previous runs)
- "Expected 0 hunts but found 47" failures
- Label collision errors when tests expect clean client state
- Flow ID conflicts when tests hardcode expected IDs
- Cannot reproduce failures locally vs CI
- Debugging requires manual Velociraptor inspection

**Prevention:**
```python
# BAD - No cleanup
def test_create_hunt(velociraptor_client):
    hunt_id = create_hunt(client, artifact="Windows.System.Pslist")
    assert hunt_id is not None
    # Hunt remains in system forever

# GOOD - Explicit cleanup
@pytest.fixture
def isolated_hunt(velociraptor_client):
    hunt_id = create_hunt(velociraptor_client,
                          artifact="Windows.System.Pslist",
                          description="TEST-HUNT-CLEANUP")
    yield hunt_id
    # Cleanup: archive and delete
    modify_hunt(velociraptor_client, hunt_id, state="ARCHIVED")

# BETTER - Test-specific cleanup markers
@pytest.fixture(autouse=True)
def cleanup_test_artifacts(velociraptor_client, request):
    """Clean up artifacts created during test."""
    test_name = request.node.name
    yield
    # Delete hunts with test name in description
    hunts = velociraptor_client.query(
        f"SELECT hunt_id FROM hunts() WHERE hunt_description =~ '{test_name}'"
    )
    for hunt in hunts:
        modify_hunt(velociraptor_client, hunt["hunt_id"], state="ARCHIVED")
```

**Detection:**
- Check hunt count before/after test run: `SELECT count() FROM hunts()`
- Inspect flows for test client: `SELECT * FROM flows(client_id='C.test')`
- Tests fail on second run but pass on first run with clean container
- Error messages reference unexpected entities: "Found existing label 'test-label'"

**Phase impact:** Must design cleanup strategy in Phase 1. Retrofitting cleanup into 35 tools after implementation is extremely expensive.

### Pitfall 3: Async Operation Timing - Flow Completion Race Conditions

**What goes wrong:** Tests don't wait for asynchronous artifact collection flows to complete before asserting results. VQL queries are asynchronous, but tests treat them as synchronous, leading to intermittent failures.

**Why it happens:**
- Velociraptor artifact collection is inherently async (flows execute on remote clients)
- VQL `collect_client()` returns immediately with flow_id, not results
- Tests assume immediate availability of flow results
- Hardcoded sleep statements that are too short for slow environments
- No awareness of `System.Flow.Completion` event monitoring

**Consequences:**
- Flaky tests that pass locally but fail in CI (timing differences)
- Tests query flow results before flow completes: "Flow F.123 has no results"
- False negatives where test passes but didn't actually validate collection
- Timeout errors on slower test infrastructure
- Developers increase timeouts instead of fixing root cause

**Prevention:**
```python
# BAD - Race condition
def test_collect_artifact(velociraptor_client, test_client_id):
    flow_id = collect_artifact(velociraptor_client,
                                test_client_id,
                                "Generic.Client.Info")
    # Immediate query - flow may not be complete
    results = get_flow_results(velociraptor_client, test_client_id, flow_id)
    assert len(results) > 0  # Flaky - may be empty

# GOOD - Wait for completion
def wait_for_flow_completion(client, client_id, flow_id, timeout=60):
    """Wait for flow to complete using System.Flow.Completion."""
    start = time.time()
    while time.time() - start < timeout:
        status = client.query(
            f"SELECT state FROM flows(client_id='{client_id}', flow_id='{flow_id}')"
        )
        if status and status[0].get("state") == "FINISHED":
            return True
        time.sleep(2)
    raise TimeoutError(f"Flow {flow_id} did not complete in {timeout}s")

def test_collect_artifact(velociraptor_client, test_client_id):
    flow_id = collect_artifact(velociraptor_client,
                                test_client_id,
                                "Generic.Client.Info")
    wait_for_flow_completion(velociraptor_client, test_client_id, flow_id)
    results = get_flow_results(velociraptor_client, test_client_id, flow_id)
    assert len(results) > 0  # Reliable
```

**Detection:**
- Tests pass with `pytest -v` (slower, more I/O) but fail with `pytest -q`
- Adding `time.sleep(10)` makes test pass
- Errors: "Flow has no results" or "Flow not found"
- Test reliability varies by machine speed
- CI failure rate > 5% for async tests

**Phase impact:** Phase 1 must establish async testing patterns. Phase 2+ (hunt operations, multi-client flows) will compound timing issues if not addressed early.

### Pitfall 4: Certificate Expiration in Long-Running Test Infrastructure

**What goes wrong:** Self-signed certificates generated for test Velociraptor server expire after a short period (often 1 year default), causing all tests to fail with x509 certificate errors. Test infrastructure that worked for months suddenly breaks completely.

**Why it happens:**
- Velociraptor `config generate` creates certificates with 1-year expiration by default
- Test fixtures (server.config.yaml) are generated once and committed or cached
- No monitoring of certificate expiration dates
- Assumption that test infrastructure is permanent

**Consequences:**
- Entire test suite fails overnight with cryptic TLS errors
- "x509: certificate has expired or is not yet valid" errors
- gRPC authentication handshake failures
- Developer confusion (worked yesterday, broken today, no code changes)
- Lost productivity while regenerating configs and debugging

**Prevention:**
```bash
# BAD - Generated once, forgotten
./scripts/test-lab.sh generate-config
# Certificates expire in 365 days

# GOOD - Check expiration before tests
check_cert_expiration() {
    local server_config="$1"
    # Extract certificate and check expiration
    local cert_expiry=$(docker run --rm -v "$FIXTURES_DIR:/config" \
        wlambert/velociraptor:latest \
        /opt/velociraptor/linux/velociraptor config show --config /config/server.config.yaml \
        | grep -A 20 "Frontend.certificate" \
        | openssl x509 -noout -enddate 2>/dev/null || echo "")

    if [[ -n "$cert_expiry" ]]; then
        log_warn "Certificate expiration: $cert_expiry"
    fi
}

# BETTER - Regenerate configs in CI
if [[ -f "$SERVER_CONFIG" ]]; then
    # Check if config is older than 30 days
    if [[ $(find "$SERVER_CONFIG" -mtime +30) ]]; then
        log_warn "Config older than 30 days, regenerating..."
        cmd_generate_config
    fi
fi
```

**Detection:**
- All tests fail with: `grpc._channel._InactiveRpcError: <_InactiveRpcError of RPC that terminated with: status = StatusCode.UNAVAILABLE`
- Docker logs show: `x509: certificate has expired or is not yet valid: current time 2026-01-24 is after 2025-01-24`
- Tests worked previously with no code changes
- `openssl x509 -in server.config.yaml -noout -dates` shows past expiration

**Phase impact:** Set up certificate monitoring in Phase 1. Document regeneration procedure. Consider automated rotation for long-term test infrastructure.

## Moderate Pitfalls

These mistakes cause delays, debugging sessions, or technical debt.

### Pitfall 5: Docker Volume Persistence Assumptions

**What goes wrong:** Developers assume `docker compose down` cleans all state, but volumes persist data. Tests accumulate server state across runs. Conversely, developers assume volumes are permanent and lose test data unexpectedly.

**Why it happens:**
- Docker compose separates container lifecycle from volume lifecycle
- `docker compose down` stops containers but preserves volumes
- `docker compose down -v` removes volumes but isn't the default
- Confusion about named volumes vs anonymous volumes

**Consequences:**
- Test state pollution (covered in Pitfall 2)
- Inability to reproduce "clean slate" failures
- Disk space exhaustion from accumulated test data
- CI cache poisoning when volumes are cached incorrectly

**Prevention:**
```bash
# Document volume behavior in test-lab.sh
cmd_down() {
    log_info "Stopping test infrastructure (preserving data)..."
    docker compose -f "$COMPOSE_FILE" down
    log_info "To remove ALL data, use: $0 clean"
}

cmd_clean() {
    log_info "Stopping and cleaning test infrastructure..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
    log_info "All containers, volumes, and networks removed."
}

# Add volume inspection command
cmd_inspect_volumes() {
    log_info "Test infrastructure volumes:"
    docker volume ls | grep vr-test
    docker volume inspect vr-test-server-data | jq '.[0].Mountpoint'
}
```

**Detection:**
- `docker volume ls` shows `vr-test-server-data` even after `docker compose down`
- Disk space usage increases over time: `docker system df`
- Tests behave differently after `./test-lab.sh clean` vs `./test-lab.sh down`

**Phase impact:** Document in Phase 1. Add volume management commands to test-lab.sh.

### Pitfall 6: VQL Query Timeout Misunderstanding

**What goes wrong:** Tests run complex VQL queries that exceed Velociraptor's 10-minute notebook timeout, causing silent failures or incomplete results. Developers don't understand timeout applies to server-side query execution.

**Why it happens:**
- Velociraptor server has hardcoded 10-minute query timeout (in config)
- Tests don't account for slow operations (filesystem traversal, large hunts)
- Timeout error messages are unclear (query returns empty result)
- Confusion between client collection timeout and VQL query timeout

**Consequences:**
- Tests timeout on large datasets but pass on small datasets
- VQL queries return partial results without indication of truncation
- Tests appear to pass but didn't complete validation
- Production workflows fail after passing test validation

**Prevention:**
```python
# BAD - Complex query without timeout handling
def test_hunt_all_clients(velociraptor_client):
    # This may timeout on 1000+ clients
    results = velociraptor_client.query("""
        SELECT * FROM hunt_results(hunt_id='H.123')
    """)
    assert len(results) > 0

# GOOD - Paginate or limit scope
def test_hunt_all_clients(velociraptor_client):
    # Test with limited scope
    results = velociraptor_client.query("""
        SELECT * FROM hunt_results(hunt_id='H.123') LIMIT 100
    """)
    assert len(results) > 0

# BETTER - Use streaming for large results
def test_hunt_all_clients(velociraptor_client):
    count = 0
    for row in velociraptor_client.query_stream("""
        SELECT * FROM hunt_results(hunt_id='H.123')
    """):
        count += 1
        if count > 1000:  # Safety limit
            break
    assert count > 0
```

**Detection:**
- VQL queries return empty list when expecting results
- Server logs show: "Query cancelled: deadline exceeded"
- Tests pass with `LIMIT 10` but fail with `LIMIT 1000`
- Timeout errors appear in production but not tests

**Phase impact:** Phase 2+ (hunts, large-scale collections) will hit this. Establish pagination patterns in Phase 1.

### Pitfall 7: Certificate Validation Errors from Hostname Mismatch

**What goes wrong:** Tests connect to Velociraptor using `localhost` or `127.0.0.1`, but certificate was generated for `velociraptor-server` Docker hostname, causing x509 validation failures.

**Why it happens:**
- Docker networking uses service names as hostnames
- Certificate CN/SAN doesn't include `localhost`
- Config generation uses default hostname
- Port forwarding exposes service on localhost, but cert validation still applies

**Consequences:**
- Tests fail with: `x509: certificate is not valid for any names, but wanted to match VelociraptorServer`
- Connection errors despite server being healthy
- Developers disable TLS verification (security risk)

**Prevention:**
```bash
# Generate config with multiple SANs
docker run --rm --entrypoint "" wlambert/velociraptor:latest \
    /opt/velociraptor/linux/velociraptor config generate \
    --merge '{
      "Frontend": {
        "hostname": "localhost",
        "bind_address": "0.0.0.0"
      }
    }' > "$SERVER_CONFIG"
```

**Detection:**
- gRPC errors: `grpc._channel._InactiveRpcError: status = StatusCode.UNAVAILABLE`
- Docker logs: `transport: authentication handshake failed`
- Tests work inside Docker network but fail from host

**Phase impact:** Fix in Phase 1 during test infrastructure setup.

### Pitfall 8: Test Client Enrollment Race Condition

**What goes wrong:** Tests assume Velociraptor client container is enrolled and online immediately after `docker compose up`, but enrollment takes time. Tests query for client that doesn't exist yet.

**Why it happens:**
- Client enrollment is async (requires server health, then enrollment handshake)
- Docker compose `depends_on: service_healthy` doesn't guarantee client enrollment
- No built-in "wait for enrollment" mechanism

**Consequences:**
- First few tests fail with "Client not found"
- Tests pass on second run after client enrolled
- Flaky test behavior in CI

**Prevention:**
```python
# Add to conftest.py
def wait_for_client_enrollment(client, timeout=60):
    """Wait for test client to enroll."""
    start = time.time()
    while time.time() - start < timeout:
        clients = client.query("SELECT client_id FROM clients() LIMIT 10")
        if len(clients) > 0:
            return clients[0]["client_id"]
        time.sleep(5)
    raise TimeoutError("No clients enrolled in timeout period")

@pytest.fixture(scope="session")
def enrolled_client_id(velociraptor_client):
    """Get enrolled test client ID."""
    return wait_for_client_enrollment(velociraptor_client)
```

**Detection:**
- Tests fail immediately after `docker compose up`
- VQL query `SELECT * FROM clients()` returns empty list
- Docker logs show client running but tests fail

**Phase impact:** Fix in Phase 1 test fixtures. Affects all client-dependent tests.

## Minor Pitfalls

These mistakes cause annoyance but are easily fixable.

### Pitfall 9: Hardcoded Flow/Hunt IDs in Tests

**What goes wrong:** Tests hardcode expected flow IDs like `F.123` or hunt IDs like `H.456`, which only work once. Subsequent test runs generate different IDs.

**Why it happens:**
- Copying VQL examples from documentation
- Not understanding that IDs are server-generated and unique
- Lack of awareness about ID generation patterns

**Consequences:**
- Tests fail on second run
- Error: "Flow F.123 not found"
- Copy-paste errors when duplicating tests

**Prevention:**
```python
# BAD - Hardcoded ID
def test_get_flow_results(velociraptor_client):
    results = get_flow_results(velociraptor_client, "C.123", "F.456")

# GOOD - Use fixture-generated IDs
@pytest.fixture
def test_flow(velociraptor_client, test_client_id):
    flow_id = collect_artifact(velociraptor_client,
                                test_client_id,
                                "Generic.Client.Info")
    yield flow_id

def test_get_flow_results(velociraptor_client, test_client_id, test_flow):
    results = get_flow_results(velociraptor_client, test_client_id, test_flow)
```

**Detection:**
- Tests pass once then fail
- Error messages show different IDs than test code

**Phase impact:** Establish ID handling patterns in Phase 1.

### Pitfall 10: Insufficient Test Logging for Async Operations

**What goes wrong:** When async tests fail, there's insufficient logging to understand what state the server was in. Did the flow start? Did it complete? What was the error?

**Why it happens:**
- Tests focus on happy path
- Logging added only after failures occur
- Async operations hide intermediate states

**Consequences:**
- Cannot debug flaky tests
- "Works on my machine" syndrome
- Time wasted reproducing failures

**Prevention:**
```python
import logging

# Add detailed logging
def test_collect_artifact(velociraptor_client, test_client_id, caplog):
    caplog.set_level(logging.DEBUG)

    logger.info(f"Starting artifact collection on client {test_client_id}")
    flow_id = collect_artifact(velociraptor_client,
                                test_client_id,
                                "Generic.Client.Info")
    logger.info(f"Collection started, flow_id={flow_id}")

    logger.debug("Waiting for flow completion...")
    wait_for_flow_completion(velociraptor_client, test_client_id, flow_id)
    logger.info(f"Flow {flow_id} completed")

    results = get_flow_results(velociraptor_client, test_client_id, flow_id)
    logger.info(f"Retrieved {len(results)} results")
    assert len(results) > 0
```

**Detection:**
- Test failures lack context
- Cannot determine which async step failed

**Phase impact:** Establish logging standards in Phase 1.

## Phase-Specific Warnings

Pitfalls likely to emerge in specific roadmap phases.

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Core VQL Query Tools | gRPC connection lifecycle (Pitfall 1) | Establish connection fixture pattern immediately |
| Phase 1: Client Management | Test client enrollment race (Pitfall 8) | Create `wait_for_enrollment` fixture |
| Phase 2: Artifact Collection | Async flow completion (Pitfall 3) | Implement `wait_for_flow` helper before any collection tests |
| Phase 2: Artifact Collection | VQL timeout on complex queries (Pitfall 6) | Use LIMIT in test queries, document timeout behavior |
| Phase 3: Hunt Operations | State pollution from hunts (Pitfall 2) | Mandatory cleanup fixtures for hunt tests |
| Phase 3: Hunt Operations | Large result set timeouts (Pitfall 6) | Use streaming API or pagination |
| Phase 4: Flow Management | Hardcoded flow IDs (Pitfall 9) | Establish ID fixture pattern |
| Phase 5: Label/Quarantine | Client state pollution (Pitfall 2) | Test-specific label namespacing |
| All Phases | Certificate expiration (Pitfall 4) | Add cert check to test-lab.sh status command |
| All Phases | Docker volume confusion (Pitfall 5) | Document volume lifecycle in README |

## Integration-Specific Warnings

Warnings specific to integrating with existing megaraptor-mcp system.

### Warning 1: Global Client Instance Anti-Pattern

**Current code risk:** `client.py` has global `_client` instance via `get_client()`. This is incompatible with test isolation.

**Problem:**
```python
# src/megaraptor_mcp/client.py
_client: Optional[VelociraptorClient] = None

def get_client() -> VelociraptorClient:
    global _client
    if _client is None:
        _client = VelociraptorClient()
        _client.connect()
    return _client
```

**Impact on tests:**
- Global state persists across tests
- Cannot test connection failures (client cached)
- Cannot test multiple configs
- `reset_client()` exists but tests must remember to call it

**Mitigation:**
```python
# In conftest.py
@pytest.fixture(autouse=True)
def reset_global_client():
    """Reset global client before each test."""
    from megaraptor_mcp.client import reset_client
    reset_client()
    yield
    reset_client()
```

### Warning 2: Temp Certificate File Cleanup Race

**Current code risk:** `client.py` creates temp files for certificates in `_temp_cert_files()` context manager, but gRPC channel creation is async. Cleanup may happen before channel fully initializes.

**Problem:**
```python
def _create_channel(self) -> grpc.Channel:
    with self._temp_cert_files() as (ca_path, cert_path, key_path):
        # Read certs
        # Create channel
        return channel
    # Temp files deleted HERE - but channel may still need them
```

**Impact on tests:**
- Intermittent "certificate file not found" errors
- Race condition under load

**Mitigation:**
- Keep temp files alive for channel lifetime
- Store cert paths on client instance
- Add explicit cleanup in `close()`

### Warning 3: No Connection Timeout Configuration

**Current code risk:** `client.py` creates gRPC channel without timeout configuration. Tests hang indefinitely on connection failures.

**Problem:**
```python
channel = grpc.secure_channel(api_url, credentials)
# No timeout specified
```

**Impact on tests:**
- Tests hang forever if server unreachable
- pytest timeout must kill tests
- False negatives (test timeout != connection timeout)

**Mitigation:**
```python
# Add channel options
options = [
    ('grpc.max_send_message_length', 100 * 1024 * 1024),
    ('grpc.max_receive_message_length', 100 * 1024 * 1024),
    ('grpc.http2.max_pings_without_data', 0),
    ('grpc.keepalive_time_ms', 10000),
    ('grpc.keepalive_timeout_ms', 5000),
]
channel = grpc.secure_channel(api_url, credentials, options=options)
```

## Evidence Integrity Considerations

Special warnings for DFIR context.

### Test Data as Evidence Pollution

**Context:** In 2026, adversaries actively poison forensic evidence. Test data in live Velociraptor systems can contaminate real investigations.

**Risks:**
- Test hunts appear in production server
- Test artifacts collected from production endpoints
- Test labels applied to production clients
- Investigation timeline pollution

**Prevention:**
- NEVER run tests against production Velociraptor
- Isolate test infrastructure completely (separate network)
- Prefix all test entities: `TEST-HUNT-`, `TEST-LABEL-`
- Document test data markers for forensic teams
- Add "test mode" indicator to deployment configs

### Hash Validation for Test Fixtures

**Context:** Test fixtures (server configs, certificates) should be validated for integrity.

**Risks:**
- Compromised test infrastructure
- Man-in-the-middle during config generation
- Config tampering between test runs

**Prevention:**
```bash
# Generate and store hash
./scripts/test-lab.sh generate-config
sha256sum tests/fixtures/server.config.yaml > tests/fixtures/server.config.yaml.sha256

# Verify before tests
sha256sum -c tests/fixtures/server.config.yaml.sha256 || {
    log_error "Config file integrity check failed!"
    exit 1
}
```

## Quick Reference Checklist

Before implementing test infrastructure:

- [ ] gRPC connection fixtures with explicit lifecycle (Pitfall 1)
- [ ] Cleanup strategy for all Velociraptor entities (Pitfall 2)
- [ ] Async operation wait helpers (Pitfall 3)
- [ ] Certificate expiration monitoring (Pitfall 4)
- [ ] Docker volume lifecycle documented (Pitfall 5)
- [ ] VQL query pagination patterns (Pitfall 6)
- [ ] Certificate hostname configuration (Pitfall 7)
- [ ] Client enrollment wait fixture (Pitfall 8)
- [ ] No hardcoded IDs in tests (Pitfall 9)
- [ ] Comprehensive logging for async ops (Pitfall 10)
- [ ] Global client reset fixture (Warning 1)
- [ ] Test entity naming convention (Evidence Integrity)

## Sources

### Official Velociraptor Documentation
- [Configuration file Reference](https://docs.velociraptor.app/docs/deployment/references/)
- [The Velociraptor API](https://docs.velociraptor.app/docs/server_automation/server_api/)
- [Client Deployment Issues](https://docs.velociraptor.app/docs/troubleshooting/deployment/client/)
- [Server Deployment Issues](https://docs.velociraptor.app/docs/troubleshooting/deployment/server/)
- [VQL Fundamentals](https://docs.velociraptor.app/docs/vql/fundamentals/)
- [Event Queries](https://docs.velociraptor.app/docs/vql/events/)
- [How to increase notebook timeout](https://docs.velociraptor.app/knowledge_base/tips/notebook_timeout/)
- [System.Flow.Completion artifact](https://docs.velociraptor.app/artifact_references/pages/system.flow.completion/)
- [Collecting Artifacts](https://docs.velociraptor.app/docs/clients/artifacts/)

### GitHub Issues & Discussions
- [x509 certificate validation issue #962](https://github.com/Velocidex/velociraptor/issues/962)
- [Certificate expiration issue #3583](https://github.com/Velocidex/velociraptor/issues/3583)
- [Velociraptor ECS Docker deployment discussion #2920](https://github.com/Velocidex/velociraptor/discussions/2920)
- [Artifacts collection stalling issue #1914](https://github.com/Velocidex/velociraptor/issues/1914)
- [gRPC memory leaks issue #36117](https://github.com/grpc/grpc/issues/36117)
- [Testcontainers data pollution discussion #4845](https://github.com/testcontainers/testcontainers-java/discussions/4845)

### Technical Resources
- [How to Optimize gRPC Performance with Connection Pooling](https://oneuptime.com/blog/post/2026-01-08-grpc-connection-pooling/view)
- [Performance Best Practices - gRPC](https://grpc.io/docs/guides/performance/)
- [Performance best practices with gRPC - Microsoft Learn](https://learn.microsoft.com/en-us/aspnet/core/grpc/performance?view=aspnetcore-10.0)
- [Testcontainers Getting Started](https://testcontainers.com/getting-started/)
- [Docker Cleanup Commands (Jan 2026)](https://medium.com/@cbaah123/docker-cleanup-commands-remove-images-containers-and-volumes-2a469a08ca78)
- [How to Write Integration Tests for Rust APIs with Testcontainers](https://oneuptime.com/blog/post/2026-01-07-rust-testcontainers/view)

### DFIR Best Practices
- [Validation of Forensic Tools - Josh Brunty's Blog](https://joshbrunty.github.io/2021/11/01/validation.html)
- [Best Practices for Digital Evidence Collection - SWGDE](https://www.swgde.org/documents/published-complete-listing/18-f-002-best-practices-for-digital-evidence-collection/)
- [Forensics And Futures: Navigating Digital Evidence, AI, And Risk In 2026](https://lcgdiscovery.com/forensics-and-futures-navigating-digital-evidence-ai-and-risk-in-2026-part-1/)
- [10 Best Practices for Digital Evidence Collection - Cellebrite](https://cellebrite.com/en/10-best-practices-for-digital-evidence-collection/)
- [Integration Testing Best Practices in 2026](https://research.aimultiple.com/integration-testing-best-practices/)

### Code Context (from existing project)
- megaraptor-mcp test infrastructure (tests/conftest.py, tests/integration/test_dfir_tools.py)
- Test lab automation (scripts/test-lab.sh)
- Docker compose configuration (tests/docker-compose.test.yml)
- VelociraptorClient implementation (src/megaraptor_mcp/client.py)
