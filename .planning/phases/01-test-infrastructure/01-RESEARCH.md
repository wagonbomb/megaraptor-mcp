# Phase 1: Test Infrastructure - Research

**Researched:** 2026-01-25
**Domain:** Python integration testing with pytest, Docker, gRPC connection lifecycle
**Confidence:** HIGH

## Summary

Phase 1 establishes the foundational test infrastructure for validating 35 MCP tools against a live Velociraptor deployment. The project already has pytest + pytest-asyncio with 104 unit tests using mocks. This phase adds integration testing capabilities with proper connection lifecycle management, async operation handling, state cleanup, and container orchestration.

**Primary domain areas investigated:**
1. **Container lifecycle management** - pytest-docker for programmatic Docker Compose integration
2. **Connection lifecycle** - gRPC channel pooling with module-scoped fixtures
3. **Async operation handling** - Wait helpers for flow completion polling
4. **State cleanup** - Autouse fixtures for Velociraptor entity removal
5. **Certificate monitoring** - Preventing x509 expiration test failures
6. **Target management** - Registry pattern for capability-based client selection

**Primary recommendation:** Extend existing conftest.py fixtures with module-scoped VelociraptorClient lifecycle, implement wait_for_flow_completion helper, add autouse cleanup fixtures for test isolation, and create TargetRegistry for client management. Use pytest-docker to replace manual subprocess calls for better container health checking.

## Standard Stack

The established libraries/tools for pytest-based Docker integration testing with gRPC services:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest-docker | >=3.2.5 | Container lifecycle with health checks | Industry standard for Docker-based integration tests. Replaces manual subprocess calls with pytest-native fixtures. Session-scoped by default. |
| pytest-check | >=2.6.2 | Multiple assertions per test | Critical for DFIR validation - check all output fields without stopping at first failure. Provides complete validation picture. |
| jsonschema | >=4.26.0 | VQL output schema validation | Velociraptor returns JSON. Validates output structure matches expected format. Latest version (Jan 7, 2026) supports Draft 2020-12. |

### Supporting (Already in Project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=7.0.0 | Test runner | Core test framework (already present) |
| pytest-asyncio | >=0.21.0 | Async test support | Already handles async VelociraptorClient methods |
| pytest-timeout | >=2.2.0 | Test timeout management | Already prevents hanging tests |
| docker | >=7.0.0 | Docker SDK | Already in deployment dependencies |
| grpcio | >=1.60.0 | gRPC client | Already used by VelociraptorClient |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-docker | testcontainers-python 4.14.0 | Testcontainers requires rewriting docker-compose.yml in Python. pytest-docker works with existing compose file. Choose testcontainers only if needing dynamic container configuration per test. |
| pytest-docker | pytest-docker-compose | pytest-docker-compose more opinionated about fixture scopes. pytest-docker gives finer control needed for existing conftest.py patterns. |
| jsonschema | pytest-jsonschema | pytest-jsonschema unmaintained since 2020. Core jsonschema more flexible and better maintained. |

**Installation:**
```bash
# Add to pyproject.toml [project.optional-dependencies] dev section
pip install pytest-docker>=3.2.5 pytest-check>=2.6.2 jsonschema>=4.26.0

# Or update pyproject.toml dev dependencies:
# dev = [
#     "pytest>=7.0.0",
#     "pytest-asyncio>=0.21.0",
#     "pytest-timeout>=2.2.0",
#     "pytest-docker>=3.2.5",
#     "pytest-check>=2.6.2",
#     "jsonschema>=4.26.0",
# ]
```

## Architecture Patterns

### Recommended Fixture Structure
```
tests/
├── conftest.py                      # Session/module fixtures (extend existing)
│   ├── docker_compose_up            # EXISTING: Session-scoped container lifecycle
│   ├── velociraptor_api_config      # EXISTING: API connection config
│   ├── velociraptor_client          # NEW: Module-scoped client with lifecycle
│   ├── enrolled_client_id           # NEW: Wait for client enrollment
│   └── cleanup_velociraptor_state   # NEW: Autouse cleanup fixture
├── fixtures/
│   ├── server.config.yaml           # EXISTING: Server config
│   ├── client.config.yaml           # EXISTING: Client config
│   └── api_client.yaml              # EXISTING: API client config
└── integration/
    ├── test_dfir_tools.py           # EXISTING: Integration tests
    └── helpers/
        ├── wait_helpers.py          # NEW: wait_for_flow_completion, wait_for_hunt
        └── cleanup_helpers.py       # NEW: Entity cleanup utilities
```

### Pattern 1: Module-Scoped Client Fixture with Explicit Lifecycle
**What:** VelociraptorClient fixture with module scope that reuses gRPC channel across tests in a module, with explicit connect/close lifecycle.

**When to use:** For all integration tests that need Velociraptor API access.

**Example:**
```python
# tests/conftest.py
from megaraptor_mcp.client import VelociraptorClient, reset_client

@pytest.fixture(scope="module")
def velociraptor_client(velociraptor_api_config):
    """Create module-scoped Velociraptor client with explicit lifecycle.

    Connection is reused across all tests in a module to prevent
    gRPC channel exhaustion (PITFALL 1 from research).
    """
    from megaraptor_mcp.config import VelociraptorConfig

    config = VelociraptorConfig.from_config_file(
        velociraptor_api_config["config_path"]
    )
    client = VelociraptorClient(config)
    client.connect()

    yield client

    # Explicit cleanup
    client.close()
    reset_client()  # Reset global client state


@pytest.fixture(autouse=True)
def reset_global_client_state():
    """Reset global client before each test for isolation.

    Mitigates global _client instance anti-pattern in client.py.
    """
    reset_client()
    yield
    reset_client()
```

**Source:** [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html), [gRPC connection pooling best practices](https://oneuptime.com/blog/post/2026-01-08-grpc-connection-pooling/view)

### Pattern 2: Wait for Async Flow Completion
**What:** Helper function that polls Velociraptor for flow completion status to avoid race conditions.

**When to use:** Any test that triggers artifact collection or flow execution.

**Example:**
```python
# tests/integration/helpers/wait_helpers.py
import time
from typing import Optional

def wait_for_flow_completion(
    client,
    client_id: str,
    flow_id: str,
    timeout: int = 60,
    poll_interval: int = 2
) -> bool:
    """Wait for Velociraptor flow to complete.

    Args:
        client: VelociraptorClient instance
        client_id: Client ID (e.g., "C.123...")
        flow_id: Flow ID (e.g., "F.456...")
        timeout: Maximum wait time in seconds
        poll_interval: Time between status checks

    Returns:
        True if flow completed successfully

    Raises:
        TimeoutError: If flow doesn't complete in timeout period

    Note: Uses VQL query to check flow state, not System.Flow.Completion
    event (which requires event monitoring setup).
    """
    start = time.time()

    while time.time() - start < timeout:
        # Query flow status
        status = client.query(
            f"SELECT state FROM flows("
            f"client_id='{client_id}', "
            f"flow_id='{flow_id}')"
        )

        if status and len(status) > 0:
            state = status[0].get("state", "")
            if state == "FINISHED":
                return True
            elif state == "ERROR":
                raise RuntimeError(
                    f"Flow {flow_id} failed with ERROR state"
                )

        time.sleep(poll_interval)

    raise TimeoutError(
        f"Flow {flow_id} did not complete in {timeout}s"
    )


def wait_for_client_enrollment(
    client,
    timeout: int = 60,
    poll_interval: int = 5
) -> str:
    """Wait for test client to enroll and return client ID.

    Args:
        client: VelociraptorClient instance
        timeout: Maximum wait time in seconds
        poll_interval: Time between enrollment checks

    Returns:
        Client ID of first enrolled client

    Raises:
        TimeoutError: If no clients enroll in timeout period
    """
    start = time.time()

    while time.time() - start < timeout:
        clients = client.query(
            "SELECT client_id FROM clients() LIMIT 10"
        )
        if len(clients) > 0:
            return clients[0]["client_id"]
        time.sleep(poll_interval)

    raise TimeoutError(
        f"No clients enrolled in {timeout}s timeout period"
    )
```

**Source:** [pytest async patterns](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html), [Velociraptor VQL documentation](https://docs.velociraptor.app/docs/vql/fundamentals/)

### Pattern 3: Autouse Cleanup Fixtures for State Isolation
**What:** Autouse fixture that runs after each test to clean up Velociraptor entities (hunts, flows, labels) created during testing.

**When to use:** All integration tests to prevent state pollution between tests.

**Example:**
```python
# tests/conftest.py
@pytest.fixture(autouse=True, scope="function")
def cleanup_velociraptor_state(request, velociraptor_client):
    """Clean up Velociraptor entities after each test.

    Prevents state pollution (PITFALL 2 from research) by removing:
    - Hunts created during test
    - Flows initiated during test
    - Labels applied during test

    Uses test name marker to identify test-created entities.
    """
    test_name = request.node.name

    # Before test: record baseline state
    initial_hunts = velociraptor_client.query(
        "SELECT count() FROM hunts()"
    )
    initial_hunt_count = initial_hunts[0]["count()"] if initial_hunts else 0

    yield  # Test runs here

    # After test: cleanup test entities
    try:
        # Archive hunts with test name in description
        test_hunts = velociraptor_client.query(
            f"SELECT hunt_id FROM hunts() "
            f"WHERE hunt_description =~ 'TEST-{test_name}'"
        )
        for hunt in test_hunts:
            # Archive hunt (can't delete directly)
            velociraptor_client.query(
                f"SELECT modify_hunt("
                f"hunt_id='{hunt['hunt_id']}', "
                f"state='ARCHIVED') FROM scope()"
            )

        # Remove labels with TEST- prefix
        test_labels = velociraptor_client.query(
            "SELECT * FROM clients() WHERE 'TEST-' IN labels"
        )
        for client_data in test_labels:
            client_id = client_data["client_id"]
            velociraptor_client.query(
                f"SELECT label(client_id='{client_id}', "
                f"op='remove', labels='TEST-*') FROM scope()"
            )

    except Exception as e:
        # Log cleanup failure but don't fail test
        print(f"Cleanup warning for {test_name}: {e}")
```

**Source:** [pytest autouse fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html), [pytest setup and teardown](https://pytest-with-eric.com/pytest-best-practices/pytest-setup-teardown/)

### Pattern 4: pytest-docker Health Check Integration
**What:** Replace manual subprocess Docker Compose calls with pytest-docker fixtures that include built-in health checking.

**When to use:** When enhancing existing docker_compose_up fixture (optional Phase 1 improvement).

**Example:**
```python
# tests/conftest.py
import pytest
import requests

@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Provide docker-compose file path for pytest-docker."""
    return str(Path(__file__).parent / "docker-compose.test.yml")


@pytest.fixture(scope="session")
def docker_services(docker_compose_file):
    """Start Docker services via pytest-docker.

    This is OPTIONAL enhancement - can keep existing docker_compose_up
    fixture. pytest-docker provides better health checking.
    """
    # pytest-docker handles: up, health checks, teardown
    pass  # Fixture auto-provided by pytest-docker plugin


def is_velociraptor_api_responsive(url):
    """Check if Velociraptor API is responsive."""
    try:
        # Note: Will fail cert validation, but connection proves server up
        requests.get(url, verify=False, timeout=5)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


@pytest.fixture(scope="session")
def velociraptor_api(docker_ip, docker_services):
    """Ensure Velociraptor API is up and responsive.

    ALTERNATIVE to existing docker_compose_up fixture.
    Only use if migrating to pytest-docker.
    """
    port = docker_services.port_for("velociraptor-server", 8001)
    url = f"https://{docker_ip}:{port}"

    docker_services.wait_until_responsive(
        timeout=60.0,
        pause=2.0,
        check=lambda: is_velociraptor_api_responsive(url)
    )

    return url
```

**Source:** [pytest-docker documentation](https://github.com/avast/pytest-docker), [pytest-docker wait_until_responsive pattern](https://github.com/avast/pytest-docker/blob/master/tests/test_integration.py)

### Pattern 5: Target Registry for Capability-Based Client Selection
**What:** Registry that tracks enrolled clients and their capabilities (OS, artifact support) for test targeting.

**When to use:** Tests that need specific client capabilities (e.g., Windows-only artifacts).

**Example:**
```python
# tests/integration/helpers/target_registry.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TestTarget:
    """Represents a test target client."""
    client_id: str
    hostname: str
    os_type: str  # "linux", "windows", "darwin"
    capabilities: List[str]  # ["generic_artifacts", "windows_registry", etc.]
    container_name: Optional[str] = None  # If Docker container


class TargetRegistry:
    """Registry of available test targets with capabilities."""

    def __init__(self):
        self.targets: List[TestTarget] = []

    def register_target(
        self,
        client_id: str,
        hostname: str,
        os_type: str,
        capabilities: List[str],
        container_name: Optional[str] = None
    ):
        """Register a test target."""
        target = TestTarget(
            client_id=client_id,
            hostname=hostname,
            os_type=os_type,
            capabilities=capabilities,
            container_name=container_name
        )
        self.targets.append(target)

    def get_by_capability(self, capability: str) -> Optional[TestTarget]:
        """Get first target with specified capability."""
        for target in self.targets:
            if capability in target.capabilities:
                return target
        return None

    def get_by_os(self, os_type: str) -> Optional[TestTarget]:
        """Get first target with specified OS type."""
        for target in self.targets:
            if target.os_type == os_type:
                return target
        return None


# tests/conftest.py
@pytest.fixture(scope="session")
def target_registry(docker_compose_up, velociraptor_client):
    """Provide registry of available test targets.

    Discovers enrolled clients and registers them with capabilities.
    """
    if not docker_compose_up:
        pytest.skip("Docker infrastructure not available")

    registry = TargetRegistry()

    # Wait for at least one client to enroll
    from tests.integration.helpers.wait_helpers import wait_for_client_enrollment
    client_id = wait_for_client_enrollment(velociraptor_client)

    # Query client info to determine capabilities
    client_info = velociraptor_client.query(
        f"SELECT * FROM clients(client_id='{client_id}')"
    )

    if client_info:
        info = client_info[0]
        os_info = info.get("os_info", {})
        os_type = os_info.get("system", "linux").lower()

        # Determine capabilities based on OS
        capabilities = ["generic_artifacts"]
        if "linux" in os_type:
            capabilities.extend(["linux_filesystem", "linux_processes"])
        elif "windows" in os_type:
            capabilities.extend(["windows_registry", "windows_prefetch"])

        registry.register_target(
            client_id=client_id,
            hostname=info.get("hostname", "vr-test-client"),
            os_type=os_type,
            capabilities=capabilities,
            container_name="vr-test-client"
        )

    yield registry
```

**Source:** [pytest markers for categorization](https://pytest-with-eric.com/pytest-best-practices/pytest-markers/), integration testing patterns from ARCHITECTURE.md research

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container lifecycle | Manual `subprocess.run(["docker", "compose", "up"])` | pytest-docker fixtures | Handles health checking, port mapping, cleanup on failure. Manual approach leaks containers on test failure. |
| Health checking | Manual polling loops in conftest.py | pytest-docker `wait_until_responsive()` | Built-in timeout handling, configurable pause intervals, cleaner error messages. |
| gRPC channel management | Creating new channel per test | Module-scoped fixture with connection pooling | Prevents connection exhaustion. gRPC channels are designed to be long-lived and reused. |
| Multiple assertions | Stopping at first assertion failure | pytest-check with `with check:` blocks | DFIR validation needs to see all field failures, not just first. pytest-check collects all failures and reports together. |
| VQL output validation | Manual `isinstance()` and field checking | jsonschema with schema definitions | Formal contract validation. Reusable schemas. Better error messages showing exact schema violations. |
| Test timeout handling | try/except with time.sleep | pytest-timeout plugin (already installed) | Already in project. Provides process-level timeout enforcement. |

**Key insight:** Integration testing with Docker and gRPC has well-established patterns. The most expensive mistakes come from not using connection pooling (causing resource leaks) and not using structured health checking (causing flaky tests).

## Common Pitfalls

### Pitfall 1: gRPC Connection Pooling Without Lifecycle Management

**What goes wrong:** Tests create new gRPC channels for every API call without proper cleanup, leading to connection exhaustion and memory leaks.

**Why it happens:**
- gRPC channels are meant to be long-lived and reused
- Tests often follow "setup-execute-teardown" patterns that don't align with connection pooling
- Developers assume garbage collection will handle cleanup
- Failed connections don't reduce memory, causing gradual memory growth

**Consequences:**
- Test suite becomes progressively slower as leaked connections accumulate
- "Connection refused" errors appear in later tests despite server being healthy
- Server-side resource exhaustion causes cascading failures
- False negatives where tests pass individually but fail in suite

**How to avoid:**
```python
# BAD - Creates new channel per test (WRONG)
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

**Warning signs:**
- Monitor Docker container memory: `docker stats vr-test-server`
- Check open connections: `netstat -an | grep 8001 | wc -l` increasing over time
- Tests pass individually but fail when run as suite
- `grpc._channel._InactiveRpcError` exceptions increase over test run

**Phase impact:** Phase 1 must establish connection lifecycle patterns. Addressing later causes test suite rewrite.

**Source:** [gRPC connection pooling best practices](https://oneuptime.com/blog/post/2026-01-08-grpc-connection-pooling/view), [gRPC performance guidelines](https://grpc.io/docs/guides/performance/)

### Pitfall 2: Test Isolation Failure - Velociraptor State Pollution

**What goes wrong:** Tests don't clean up artifacts, hunts, flows, or labels created during execution, causing subsequent tests to fail due to unexpected server state.

**Why it happens:**
- Velociraptor persists all data to disk (flows, hunts, collected artifacts)
- Docker volume `vr-server-data` survives container restarts
- Tests create hunts/flows/labels but don't remove them
- Assumption that container restart = clean state (false with volumes)

**Consequences:**
- Test results become non-deterministic (pass/fail depends on previous runs)
- "Expected 0 hunts but found 47" failures
- Label collision errors when tests expect clean client state
- Cannot reproduce failures locally vs CI

**How to avoid:**
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
    # Cleanup: archive hunt
    modify_hunt(velociraptor_client, hunt_id, state="ARCHIVED")
```

**Warning signs:**
- Check hunt count before/after test run: `SELECT count() FROM hunts()`
- Inspect flows for test client: `SELECT * FROM flows(client_id='C.test')`
- Tests fail on second run but pass on first run with clean container

**Phase impact:** Must design cleanup strategy in Phase 1. Retrofitting cleanup into existing tests after implementation is extremely expensive.

**Source:** [pytest setup and teardown](https://pytest-with-eric.com/pytest-best-practices/pytest-setup-teardown/), Velociraptor persistence model from PITFALLS.md research

### Pitfall 3: Async Operation Timing - Flow Completion Race Conditions

**What goes wrong:** Tests don't wait for asynchronous artifact collection flows to complete before asserting results. VQL queries are asynchronous, but tests treat them as synchronous.

**Why it happens:**
- Velociraptor artifact collection is inherently async (flows execute on remote clients)
- VQL `collect_client()` returns immediately with flow_id, not results
- Tests assume immediate availability of flow results
- Hardcoded sleep statements that are too short for slow environments

**Consequences:**
- Flaky tests that pass locally but fail in CI (timing differences)
- Tests query flow results before flow completes: "Flow F.123 has no results"
- False negatives where test passes but didn't actually validate collection
- Timeout errors on slower test infrastructure

**How to avoid:**
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
    """Wait for flow to complete using polling."""
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

**Warning signs:**
- Tests pass with `pytest -v` (slower) but fail with `pytest -q`
- Adding `time.sleep(10)` makes test pass
- Errors: "Flow has no results" or "Flow not found"
- Test reliability varies by machine speed

**Phase impact:** Phase 1 must establish async testing patterns. Phase 2+ (hunt operations, multi-client flows) will compound timing issues if not addressed early.

**Source:** [pytest async patterns](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html), [Velociraptor VQL events](https://docs.velociraptor.app/docs/vql/events/)

### Pitfall 4: Certificate Expiration in Long-Running Test Infrastructure

**What goes wrong:** Self-signed certificates generated for test Velociraptor server expire after a short period (often 1 year default), causing all tests to fail with x509 certificate errors.

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

**How to avoid:**
```bash
# Add to conftest.py or test-lab.sh
def check_cert_expiration(config_path):
    """Check certificate expiration and warn if < 30 days."""
    import yaml
    from datetime import datetime
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend

    with open(config_path) as f:
        config = yaml.safe_load(f)

    cert_pem = config.get("Frontend", {}).get("certificate", "")
    if cert_pem:
        cert = x509.load_pem_x509_certificate(
            cert_pem.encode(),
            default_backend()
        )
        days_left = (cert.not_valid_after - datetime.now()).days

        if days_left < 30:
            warnings.warn(
                f"Certificate expires in {days_left} days. "
                f"Regenerate with: ./scripts/test-lab.sh generate-config"
            )
```

**Warning signs:**
- All tests fail with: `grpc._channel._InactiveRpcError: status = StatusCode.UNAVAILABLE`
- Docker logs show: `x509: certificate has expired or is not yet valid`
- Tests worked previously with no code changes

**Phase impact:** Set up certificate monitoring in Phase 1. Document regeneration procedure in README.

**Source:** [Certificate lifecycle management trends 2026](https://certera.com/blog/certificate-life-cycle-management-emerging-trends-to-watch-in-2026/), [Velociraptor certificate issues](https://github.com/Velocidex/velociraptor/issues/3583)

### Pitfall 5: Docker Volume Persistence Assumptions

**What goes wrong:** Developers assume `docker compose down` cleans all state, but volumes persist data. Tests accumulate server state across runs.

**Why it happens:**
- Docker compose separates container lifecycle from volume lifecycle
- `docker compose down` stops containers but preserves volumes
- `docker compose down -v` removes volumes but isn't the default
- Confusion about named volumes vs anonymous volumes

**Consequences:**
- Test state pollution (see Pitfall 2)
- Inability to reproduce "clean slate" failures
- Disk space exhaustion from accumulated test data
- CI cache poisoning when volumes are cached incorrectly

**How to avoid:**
```bash
# Document in README or test-lab.sh
# Stop containers, preserve data
docker compose -f tests/docker-compose.test.yml down

# Stop containers, remove ALL data (clean slate)
docker compose -f tests/docker-compose.test.yml down -v --remove-orphans

# Check volume status
docker volume ls | grep vr-test
docker volume inspect vr-test-server-data
```

**Warning signs:**
- `docker volume ls` shows `vr-test-server-data` even after `docker compose down`
- Disk space usage increases over time: `docker system df`
- Tests behave differently after full cleanup vs partial cleanup

**Phase impact:** Document in Phase 1. Add volume management commands to test-lab.sh.

**Source:** [Docker cleanup commands](https://medium.com/@cbaah123/docker-cleanup-commands-remove-images-containers-and-volumes-2a469a08ca78), existing docker-compose.test.yml volume configuration

### Pitfall 6: Test Client Enrollment Race Condition

**What goes wrong:** Tests assume Velociraptor client container is enrolled and online immediately after `docker compose up`, but enrollment takes time.

**Why it happens:**
- Client enrollment is async (requires server health, then enrollment handshake)
- Docker compose `depends_on: service_healthy` doesn't guarantee client enrollment
- No built-in "wait for enrollment" mechanism

**Consequences:**
- First few tests fail with "Client not found"
- Tests pass on second run after client enrolled
- Flaky test behavior in CI

**How to avoid:**
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

**Warning signs:**
- Tests fail immediately after `docker compose up`
- VQL query `SELECT * FROM clients()` returns empty list
- Docker logs show client running but tests fail

**Phase impact:** Fix in Phase 1 test fixtures. Affects all client-dependent tests.

**Source:** [Velociraptor client deployment troubleshooting](https://docs.velociraptor.app/docs/troubleshooting/deployment/client/), pytest-docker wait patterns

## Code Examples

Verified patterns for Phase 1 implementation:

### Example 1: Enhanced docker_compose_up with Health Checking
```python
# tests/conftest.py
@pytest.fixture(scope="session")
def docker_compose_up(docker_available: bool, velociraptor_configs_exist: bool):
    """Start test infrastructure for integration tests.

    Enhanced with better health checking and cleanup handling.
    """
    if not docker_available:
        pytest.skip("Docker not available")
        return

    if not velociraptor_configs_exist:
        pytest.skip("Velociraptor configs not generated")
        return

    # Check if already running
    already_running = is_velociraptor_running()

    if not already_running:
        # Start containers
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.fail(f"Failed to start Docker Compose: {result.stderr}")

        # Wait for health check with better error reporting
        for i in range(HEALTH_CHECK_RETRIES):
            if is_velociraptor_running():
                # Additional check: API is responsive
                time.sleep(5)  # Give API time to initialize
                break
            time.sleep(HEALTH_CHECK_INTERVAL)
        else:
            # Get container logs for debugging
            logs = subprocess.run(
                ["docker", "logs", "vr-test-server"],
                capture_output=True,
                text=True,
            )
            # Cleanup on failure
            subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
                capture_output=True,
            )
            pytest.fail(
                f"Velociraptor server failed to become healthy.\n"
                f"Logs:\n{logs.stdout}\n{logs.stderr}"
            )

    yield True

    # Only tear down if we started it (preserve manual runs)
    if not already_running:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down"],
            capture_output=True,
        )
```

### Example 2: VelociraptorClient Module Fixture
```python
# tests/conftest.py
from megaraptor_mcp.client import VelociraptorClient, reset_client
from megaraptor_mcp.config import VelociraptorConfig

@pytest.fixture(scope="module")
def velociraptor_client(velociraptor_api_config):
    """Create module-scoped Velociraptor client with lifecycle management.

    Reuses gRPC connection across all tests in a module to prevent
    connection exhaustion (critical for integration tests).
    """
    config = VelociraptorConfig.from_config_file(
        velociraptor_api_config["config_path"]
    )
    client = VelociraptorClient(config)

    # Explicit connection
    client.connect()

    yield client

    # Explicit cleanup
    try:
        client.close()
    finally:
        reset_client()  # Reset global client state
```

### Example 3: Autouse Cleanup Fixture
```python
# tests/conftest.py
@pytest.fixture(autouse=True, scope="function")
def cleanup_velociraptor_state(request, velociraptor_client):
    """Clean up Velociraptor entities after each test.

    Automatically removes test-created hunts, flows, and labels
    to prevent state pollution between tests.
    """
    test_name = request.node.name

    yield  # Test runs here

    # After test: cleanup
    try:
        # Archive hunts with TEST- prefix in description
        test_hunts = velociraptor_client.query(
            "SELECT hunt_id, hunt_description FROM hunts() "
            "WHERE hunt_description =~ 'TEST-'"
        )
        for hunt in test_hunts:
            if test_name in hunt.get("hunt_description", ""):
                velociraptor_client.query(
                    f"SELECT modify_hunt("
                    f"hunt_id='{hunt['hunt_id']}', "
                    f"state='ARCHIVED') FROM scope()"
                )

        # Remove TEST- labels
        labeled_clients = velociraptor_client.query(
            "SELECT client_id, labels FROM clients() "
            "WHERE 'TEST-' IN labels"
        )
        for client_data in labeled_clients:
            # Remove all TEST- prefixed labels
            test_labels = [
                label for label in client_data.get("labels", [])
                if label.startswith("TEST-")
            ]
            for label in test_labels:
                velociraptor_client.query(
                    f"SELECT label(client_id='{client_data['client_id']}', "
                    f"op='remove', labels='{label}') FROM scope()"
                )

    except Exception as e:
        # Log cleanup failure but don't fail test
        print(f"Cleanup warning for {test_name}: {e}")
```

### Example 4: Using pytest-check for Multiple Assertions
```python
# tests/integration/test_dfir_tools.py
from pytest_check import check

def test_client_list_comprehensive(velociraptor_client):
    """Validate client list output structure and content."""
    result = velociraptor_client.query(
        "SELECT client_id, hostname, os_info FROM clients() LIMIT 10"
    )

    # Check all conditions, report all failures
    with check:
        assert isinstance(result, list), "Result should be a list"
    with check:
        assert len(result) > 0, "Should return at least one client"

    if result:
        first_client = result[0]
        with check:
            assert "client_id" in first_client, "Client should have 'client_id' field"
        with check:
            assert "hostname" in first_client, "Client should have 'hostname' field"
        with check:
            assert "os_info" in first_client, "Client should have 'os_info' field"

        if "client_id" in first_client:
            with check:
                assert first_client["client_id"].startswith("C."), \
                    "Client ID should start with 'C.'"
```

### Example 5: Schema Validation with jsonschema
```python
# tests/integration/schemas.py
"""VQL output schemas for validation."""

CLIENT_LIST_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["client_id", "hostname"],
        "properties": {
            "client_id": {
                "type": "string",
                "pattern": "^C\\."
            },
            "hostname": {
                "type": "string",
                "minLength": 1
            },
            "os_info": {
                "type": "object"
            }
        }
    }
}

# tests/integration/test_dfir_tools.py
import jsonschema
from .schemas import CLIENT_LIST_SCHEMA

def test_client_list_schema(velociraptor_client):
    """Validate client list output against JSON schema."""
    result = velociraptor_client.query(
        "SELECT client_id, hostname, os_info FROM clients() LIMIT 10"
    )

    # Validate against schema
    jsonschema.validate(instance=result, schema=CLIENT_LIST_SCHEMA)

    # Schema validation passed, now check content quality
    assert len(result) > 0, "Should return at least one client"
```

**Source:** All examples based on existing conftest.py patterns, enhanced with research from pytest-docker, pytest-check, and jsonschema documentation.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual `subprocess.run(["docker", "compose"])` | pytest-docker fixtures with `wait_until_responsive()` | 2024+ | Better health checking, automatic cleanup, cleaner error messages |
| Function-scoped client fixtures | Module-scoped client with connection pooling | gRPC best practices | Prevents connection exhaustion, faster test execution |
| Bare assertions stopping at first failure | pytest-check with multiple `with check:` blocks | pytest-check 2.0+ (2023) | See all validation failures, better for DFIR output validation |
| Manual JSON field checking | jsonschema validation | jsonschema 4.0+ (2021) | Formal contract validation, reusable schemas, better error messages |
| Hardcoded sleep for async operations | Polling with `wait_for_*` helpers | Modern async testing | Reliable timing, configurable timeouts, clear failure messages |

**Deprecated/outdated:**
- pytest-grpc (0.8.0 from 2020): Unmaintained. Use real Velociraptor container instead of gRPC mocks.
- pytest-docker-compose: Less flexible than pytest-docker for existing compose files.
- testcontainers-python: Overkill when docker-compose.yml already exists.

## Open Questions

Things that couldn't be fully resolved:

1. **Should we migrate to pytest-docker or enhance existing subprocess approach?**
   - What we know: pytest-docker provides better health checking and cleanup
   - What's unclear: Migration effort vs benefit for existing working infrastructure
   - Recommendation: Phase 1 keeps existing docker_compose_up, add pytest-docker in Phase 2 if needed. Existing approach works, don't break it without proven benefit.

2. **What's the optimal cleanup strategy for flows?**
   - What we know: Flows persist indefinitely, no built-in expiration
   - What's unclear: Whether to delete flows or just archive completed ones
   - Recommendation: Start with archiving hunts only (can't delete). Document flow cleanup pattern after observing accumulation rate.

3. **How to handle certificate rotation in CI/CD?**
   - What we know: Certificates expire, need regeneration
   - What's unclear: Best automation approach (regenerate on every CI run vs monitor and rotate)
   - Recommendation: Phase 1 adds cert expiration check. Phase 2 implements auto-regeneration if check fails.

4. **Should cleanup be autouse or explicit?**
   - What we know: Autouse ensures cleanup always runs, but adds overhead
   - What's unclear: Performance impact of checking for entities after every test
   - Recommendation: Start with autouse for safety. Optimize to explicit fixtures if performance becomes issue.

## Sources

### Primary (HIGH confidence)
- [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html) - Official pytest fixture patterns
- [pytest-docker GitHub](https://github.com/avast/pytest-docker) - Docker integration testing
- [pytest-check PyPI](https://pypi.org/project/pytest-check/) - Multiple assertions per test
- [jsonschema documentation](https://python-jsonschema.readthedocs.io/) - JSON schema validation
- [gRPC connection pooling best practices](https://oneuptime.com/blog/post/2026-01-08-grpc-connection-pooling/view) - gRPC lifecycle management
- [Velociraptor VQL documentation](https://docs.velociraptor.app/docs/vql/fundamentals/) - VQL query patterns

### Secondary (MEDIUM confidence)
- [pytest autouse fixtures](https://pytest-with-eric.com/fixtures/pytest-fixture-autouse/) - Autouse patterns
- [pytest setup and teardown](https://pytest-with-eric.com/pytest-best-practices/pytest-setup-teardown/) - Cleanup strategies
- [pytest async patterns](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html) - Async testing
- [pytest markers](https://pytest-with-eric.com/pytest-best-practices/pytest-markers/) - Test categorization
- [Integration testing with Docker Compose](https://xnuinside.medium.com/integration-testing-for-bunch-of-services-with-pytest-docker-compose-4892668f9cba) - Docker patterns

### Tertiary (LOW confidence - WebSearch only)
- [Certificate lifecycle management 2026](https://certera.com/blog/certificate-life-cycle-management-emerging-trends-to-watch-in-2026/) - Certificate trends
- [Docker cleanup commands](https://medium.com/@cbaah123/docker-cleanup-commands-remove-images-containers-and-volumes-2a469a08ca68) - Volume management

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via PyPI, actively maintained, widely used
- Architecture patterns: HIGH - Based on official pytest documentation and existing conftest.py
- Connection lifecycle: HIGH - gRPC best practices + existing VelociraptorClient implementation
- Async patterns: MEDIUM - Polling approach verified but not tested with Velociraptor specifically
- Cleanup strategies: MEDIUM - Pattern is standard but VQL cleanup queries need validation
- Certificate monitoring: LOW - Pattern is sound but integration with test-lab.sh needs implementation

**Research date:** 2026-01-25
**Valid until:** 90 days (stable domain - pytest, Docker, gRPC are mature technologies)

**Next phase considerations:**
- Phase 2 will need these patterns for artifact collection validation
- Phase 3+ will extend cleanup patterns for hunts and large-scale flows
- All future phases depend on connection lifecycle patterns established here
