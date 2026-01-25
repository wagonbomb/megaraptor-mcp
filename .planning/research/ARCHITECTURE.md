# Architecture Patterns: Real-World Validation Testing

**Domain:** DFIR Testing - Velociraptor MCP Server Validation
**Researched:** 2026-01-24

## Recommended Architecture

The validation testing architecture extends the existing three-layer test infrastructure (unit → integration → validation) while maintaining strict isolation boundaries and reusing proven fixture patterns.

### High-Level Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    Validation Test Layer                     │
│  (New: Real-world artifact collection, multi-target)         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│               Integration Test Layer                         │
│  (Existing: Docker, API health checks, VQL queries)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   Unit Test Layer                            │
│  (Existing: Mocks, no external dependencies)                 │
└──────────────────────────────────────────────────────────────┘

           ┌───────────────────────────────────┐
           │    Existing Infrastructure        │
           │  - conftest.py fixtures           │
           │  - MockVelociraptorServer         │
           │  - Docker Compose setup           │
           │  - test-lab.sh orchestration      │
           └───────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Validation Test Suite** | Execute real artifact collection against live targets | ValidatedTargetFixture, ValidationRunner, VelociraptorClient |
| **ValidatedTargetFixture** | Provide configured test targets (Docker, VM, physical) | Docker infrastructure, SSH/WinRM, test-lab.sh |
| **ValidationRunner** | Orchestrate collection → verification → cleanup | VelociraptorClient, ArtifactValidator |
| **ArtifactValidator** | Verify collected data against expectations | Artifact collection results, validation schemas |
| **TargetRegistry** | Track available test targets and capabilities | conftest.py, environment config |

## Integration Points with Existing Test Infrastructure

### Point 1: Fixture Layering (CRITICAL)

**Existing Pattern:**
```python
# conftest.py (lines 92-145)
@pytest.fixture(scope="session")
def docker_compose_up(docker_available, velociraptor_configs_exist):
    """Start test infrastructure for integration tests."""
    # Starts Docker containers, waits for health
    yield True
    # Teardown if we started it
```

**Integration Strategy:**
Validation fixtures extend session-scoped infrastructure without restarting containers.

```python
# New validation fixture extends existing
@pytest.fixture(scope="session")
def validation_targets(docker_compose_up, velociraptor_client):
    """Provide configured targets for validation testing.

    Depends on docker_compose_up to ensure infrastructure running.
    Adds target registration and capability discovery.
    """
    if not docker_compose_up:
        pytest.skip("Infrastructure not available")

    # Register Docker container as primary target
    registry = TargetRegistry()
    registry.register_target(
        target_id="docker-client",
        target_type="docker",
        container_name="vr-test-client",
        capabilities=["linux", "generic_artifacts"],
    )

    # Optionally register physical/VM targets from environment
    if os.getenv("VALIDATION_PHYSICAL_HOST"):
        registry.register_target(
            target_id="physical-linux",
            target_type="ssh",
            host=os.getenv("VALIDATION_PHYSICAL_HOST"),
            capabilities=["linux", "full_filesystem"],
        )

    yield registry
    # No teardown needed - docker_compose_up handles infrastructure
```

**Confidence:** HIGH - Pattern follows existing fixture dependency chain from conftest.py

**Why this works:**
- Reuses `docker_compose_up` session fixture (no container restarts)
- Extends capabilities without breaking existing integration tests
- Allows optional physical targets via environment variables

### Point 2: VelociraptorClient Reuse

**Existing Pattern:**
```python
# tests/integration/test_dfir_tools.py (lines 28-54)
@pytest.fixture(scope="module")
def velociraptor_client(docker_compose_up, velociraptor_api_config):
    """Create a Velociraptor client for testing."""
    config = VelociraptorConfig.from_config_file(config_path)
    client = VelociraptorClient(config)
    return client
```

**Integration Strategy:**
Validation tests use the same client fixture, no modifications needed.

```python
# Validation tests reuse existing client fixture
def test_collect_browser_history(validation_targets, velociraptor_client):
    """Validate browser history collection on real target."""
    target = validation_targets.get_target("docker-client")

    # Use existing client - no new connection needed
    flow = velociraptor_client.query(
        f"SELECT collect_client(client_id='{target.client_id}', "
        f"artifacts='Generic.Client.BrowserHistory') FROM scope()"
    )

    # Validate results
    assert len(flow) > 0
```

**Confidence:** HIGH - Client abstraction proven in integration tests (test_dfir_tools.py)

**Why this works:**
- VelociraptorClient already tested against live infrastructure
- No new authentication or connection management needed
- Validation tests are just integration tests with stricter assertions

### Point 3: Test Isolation with Markers

**Existing Pattern:**
```python
# pyproject.toml (lines 70-74)
markers = [
    "unit: Unit tests (no external dependencies)",
    "integration: Requires Docker infrastructure",
    "slow: Long-running tests",
]

# tests/integration/test_dfir_tools.py (line 17)
pytestmark = [pytest.mark.integration, pytest.mark.slow]
```

**Integration Strategy:**
Add validation marker, build on existing infrastructure requirements.

```python
# pyproject.toml - add new marker
markers = [
    "unit: Unit tests (no external dependencies)",
    "integration: Requires Docker infrastructure",
    "slow: Long-running tests",
    "validation: Real-world artifact collection (requires live targets)",
]

# tests/validation/test_artifact_collection.py
pytestmark = [pytest.mark.validation, pytest.mark.slow]

# Run selectively
# pytest -m validation              # Validation tests only
# pytest -m "integration or validation"  # Both integration and validation
# pytest -m "not validation"        # Skip expensive validation tests
```

**Confidence:** HIGH - Marker system already proven for test categorization

**Why this works:**
- Follows established pattern for test categorization
- Allows CI/CD to run validation tests separately (nightly builds)
- Developers can skip validation during rapid iteration

### Point 4: Docker Infrastructure Extension

**Existing Pattern:**
```python
# tests/docker-compose.test.yml (lines 37-53)
velociraptor-client:
    image: wlambert/velociraptor:latest
    container_name: vr-test-client
    command: ["/bin/bash", "-c", "...velociraptor client -v"]
    depends_on:
      velociraptor-server:
        condition: service_healthy
```

**Integration Strategy:**
Validation tests use existing client container as primary target. No new containers needed for initial validation.

**Confidence:** HIGH - Container already enrolled and communicating with server

**Why this works:**
- Existing client container provides real Linux target
- Already has Velociraptor agent running and enrolled
- Can collect artifacts, test VQL, verify results
- No infrastructure changes needed for Phase 1 validation

**Optional Enhancement for Future Phases:**
```yaml
# docker-compose.test.yml - add Windows client for multi-OS validation
velociraptor-client-windows:
    image: winamd64/velociraptor-client:latest
    container_name: vr-test-client-windows
    depends_on:
      velociraptor-server:
        condition: service_healthy
```

### Point 5: Artifact Validation Pattern

**New Component:**
Artifact validators verify collected data matches expectations.

```python
# tests/validation/validators/artifact_validator.py
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class ValidationRule:
    """Defines expectations for collected artifact data."""
    field: str
    validator: callable
    error_message: str

class ArtifactValidator:
    """Validates collected artifact data against expectations."""

    def __init__(self, artifact_name: str):
        self.artifact_name = artifact_name
        self.rules: List[ValidationRule] = []

    def add_rule(self, field: str, validator: callable, error_message: str):
        """Register validation rule for artifact field."""
        self.rules.append(ValidationRule(field, validator, error_message))

    def validate(self, results: List[Dict[str, Any]]) -> ValidationReport:
        """Validate collected artifact results."""
        report = ValidationReport(artifact_name=self.artifact_name)

        if not results:
            report.add_failure("No results collected")
            return report

        for rule in self.rules:
            for row in results:
                if rule.field not in row:
                    report.add_failure(
                        f"Missing field: {rule.field}",
                        context=row
                    )
                    continue

                if not rule.validator(row[rule.field]):
                    report.add_failure(
                        rule.error_message,
                        context={rule.field: row[rule.field]}
                    )

        return report
```

**Usage in Validation Tests:**
```python
def test_browser_history_collection(validation_targets, velociraptor_client):
    """Validate browser history artifact collection."""
    target = validation_targets.get_target("docker-client")

    # Collect artifact
    results = collect_artifact(
        client=velociraptor_client,
        client_id=target.client_id,
        artifact="Generic.Client.BrowserHistory"
    )

    # Validate structure
    validator = ArtifactValidator("Generic.Client.BrowserHistory")
    validator.add_rule(
        field="url",
        validator=lambda v: isinstance(v, str) and len(v) > 0,
        error_message="URL must be non-empty string"
    )
    validator.add_rule(
        field="title",
        validator=lambda v: isinstance(v, str),
        error_message="Title must be string"
    )
    validator.add_rule(
        field="visit_count",
        validator=lambda v: isinstance(v, int) and v >= 0,
        error_message="Visit count must be non-negative integer"
    )

    report = validator.validate(results)
    assert report.passed, f"Validation failed:\n{report.format()}"
```

**Confidence:** MEDIUM - Pattern common in data validation, not yet tested in this codebase

**Why this works:**
- Separates collection from validation (single responsibility)
- Reusable validators across different artifacts
- Clear failure reports for debugging

## Data Flow

### Validation Test Execution Flow

```
1. pytest discovers validation tests (marked with @pytest.mark.validation)
   └─> Requires: validation_targets fixture
       └─> Depends on: docker_compose_up fixture
           └─> Starts infrastructure if not running (existing pattern)

2. validation_targets fixture initializes
   ├─> Checks docker_compose_up (infrastructure ready)
   ├─> Creates TargetRegistry
   ├─> Registers Docker client container
   │   └─> Queries Velociraptor for enrolled client ID
   └─> Optionally registers physical/VM targets from environment

3. Test executes artifact collection
   ├─> Selects target from registry (by capabilities)
   ├─> Uses velociraptor_client to trigger collection
   │   └─> Reuses existing VelociraptorClient (no new connection)
   ├─> Waits for flow completion
   └─> Retrieves results via VQL query

4. Test validates collected data
   ├─> Creates ArtifactValidator for artifact type
   ├─> Defines validation rules (field types, constraints)
   ├─> Runs validation against results
   └─> Asserts validation passed

5. Test cleanup (automatic)
   └─> No cleanup needed - containers persist for session
       (Existing docker_compose_up handles teardown)
```

### State Management

**Where State Lives:**
- **Infrastructure state:** Docker Compose manages container lifecycle
- **Test target state:** TargetRegistry (session-scoped fixture)
- **Velociraptor connection:** VelociraptorClient (module-scoped, reused)
- **Validation results:** ValidationReport (per-test, ephemeral)

**No New Global State Required:** Validation tests are stateless, using existing fixtures.

## Patterns to Follow

### Pattern 1: Fixture Composition Over Duplication

**What:** Build validation fixtures by composing existing fixtures, not duplicating infrastructure setup.

**When:** Creating any validation test fixture.

**Example:**
```python
# GOOD: Compose existing fixtures
@pytest.fixture(scope="session")
def validation_targets(docker_compose_up, velociraptor_api_config):
    """Extends docker_compose_up without duplicating setup."""
    registry = TargetRegistry()
    # ... register targets using existing infrastructure
    yield registry

# BAD: Duplicate infrastructure setup
@pytest.fixture(scope="session")
def validation_infrastructure():
    """Don't do this - duplicates docker_compose_up logic."""
    # Start containers (WRONG - already done by docker_compose_up)
    subprocess.run(["docker", "compose", "up", "-d"])
```

**Why:** Prevents test infrastructure drift, reduces maintenance, ensures consistency.

**Source:** Existing conftest.py pattern (lines 92-145)

### Pattern 2: Capability-Based Target Selection

**What:** Select test targets based on capabilities, not specific target IDs.

**When:** Writing validation tests that need specific target features.

**Example:**
```python
# GOOD: Capability-based selection
def test_windows_registry_collection(validation_targets, velociraptor_client):
    """Validate Windows registry artifact."""
    target = validation_targets.get_by_capability("windows")
    if not target:
        pytest.skip("No Windows target available")
    # ... test logic

# BAD: Hardcoded target selection
def test_windows_registry_collection(validation_targets, velociraptor_client):
    """This breaks when target ID changes."""
    target = validation_targets.get_target("win-desktop-01")  # Brittle
```

**Why:** Tests adapt to available infrastructure, easier to add new targets.

**Source:** Common pattern in infrastructure testing, adapted for DFIR context

### Pattern 3: Parametrized Artifact Validation

**What:** Use pytest.mark.parametrize to test multiple artifacts with same validation pattern.

**When:** Testing multiple artifacts that share validation structure.

**Example:**
```python
@pytest.mark.parametrize("artifact,expected_fields", [
    ("Generic.Client.Info", ["client_id", "hostname", "os_info"]),
    ("Generic.System.Pslist", ["pid", "name", "ppid"]),
    ("Linux.Sys.Users", ["username", "uid", "gid"]),
])
def test_artifact_collection_fields(
    validation_targets,
    velociraptor_client,
    artifact,
    expected_fields
):
    """Validate artifact contains expected fields."""
    target = validation_targets.get_by_capability("linux")

    results = collect_artifact(
        client=velociraptor_client,
        client_id=target.client_id,
        artifact=artifact
    )

    assert len(results) > 0, f"No results for {artifact}"
    for field in expected_fields:
        assert field in results[0], f"Missing field {field} in {artifact}"
```

**Why:** Reduces test duplication, clear test failure messages, easy to add new artifacts.

**Source:** [pytest parametrize documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html)

### Pattern 4: Validation Report Objects

**What:** Return structured validation reports instead of bare assertions.

**When:** Complex validation with multiple failure points.

**Example:**
```python
# GOOD: Structured report
def test_process_list_validation(validation_targets, velociraptor_client):
    """Validate process list artifact structure and content."""
    results = collect_artifact(...)

    validator = ArtifactValidator("Windows.System.Pslist")
    validator.add_rule("pid", lambda v: v > 0, "PID must be positive")
    validator.add_rule("name", lambda v: len(v) > 0, "Name required")

    report = validator.validate(results)

    # Rich failure reporting
    if not report.passed:
        pytest.fail(
            f"Validation failed for {report.artifact_name}:\n"
            f"{report.format_failures()}"
        )

# BAD: Multiple bare assertions
def test_process_list_validation(validation_targets, velociraptor_client):
    """Hard to debug which validation failed."""
    results = collect_artifact(...)

    for row in results:
        assert row["pid"] > 0  # Which row failed?
        assert len(row["name"]) > 0  # Lost context by now
```

**Why:** Better failure diagnostics, can continue validation after first failure, clearer test intent.

**Source:** Common validation testing pattern, adapted from test data validation practices

## Anti-Patterns to Avoid

### Anti-Pattern 1: Restarting Infrastructure Per Test

**What goes wrong:** Tests create/destroy Docker containers for each test function.

**Why it happens:** Misunderstanding fixture scope or not reusing existing infrastructure.

**Consequences:**
- Tests take 10-20x longer (container startup time)
- Test flakiness from container timing issues
- Resource exhaustion in CI environments

**Prevention:**
- Always use `scope="session"` for infrastructure fixtures
- Depend on existing `docker_compose_up` fixture
- Never call `docker compose up/down` in test code

**Detection:** Tests taking >30 seconds each, Docker logs showing repeated container creation

**Source:** [pytest-docker best practices](https://github.com/avast/pytest-docker) - session-scoped fixtures for container lifecycle

### Anti-Pattern 2: Hardcoded Client IDs

**What goes wrong:** Tests reference specific Velociraptor client IDs like "C.1234567890abcdef".

**Why it happens:** Copy-pasting from manual testing or integration test examples.

**Consequences:**
- Tests fail when client re-enrolls (ID changes)
- Tests break across different environments
- Can't run tests in parallel (client ID conflicts)

**Prevention:**
- Query for enrolled clients dynamically: `SELECT * FROM clients() WHERE hostname = 'vr-test-client'`
- Use TargetRegistry to abstract client lookup
- Store target metadata (hostname, labels) not client IDs

**Detection:** Tests failing with "client not found" after container restart

**Source:** Existing integration test pattern (test_dfir_tools.py line 77) - uses VQL search patterns

### Anti-Pattern 3: Validation Without Expected State Setup

**What goes wrong:** Tests collect artifacts without first ensuring target has expected data.

**Why it happens:** Assuming clean container has browser history, processes, etc.

**Consequences:**
- False negatives (test passes when it should validate data)
- Tests fail intermittently based on container state
- Can't verify correctness, only absence of errors

**Prevention:**
```python
# GOOD: Setup expected state first
def test_browser_history_collection(validation_targets, velociraptor_client):
    """Validate browser history collection after creating test data."""
    target = validation_targets.get_by_capability("linux")

    # Setup: Create test browser history
    create_test_browser_history(target, urls=[
        "https://example.com",
        "https://test.local",
    ])

    # Collect
    results = collect_artifact(...)

    # Validate expected URLs present
    urls = [r["url"] for r in results]
    assert "https://example.com" in urls
    assert "https://test.local" in urls

# BAD: Hope data exists
def test_browser_history_collection(validation_targets, velociraptor_client):
    """What if container has no browser history?"""
    results = collect_artifact(...)
    assert len(results) > 0  # May pass with zero results
```

**Prevention Strategy:**
- Phase 1: Test artifact structure (fields, types) - no setup needed
- Phase 2: Test artifact content - setup test data first
- Phase 3: Test against known malicious patterns - setup attack scenarios

**Source:** [MANTIS DFIR testing platform](https://mantis-platform.io/docs/usecases/dfir.html) - automated attack scenarios for validation

### Anti-Pattern 4: Mixing Unit Test Mocks with Validation Tests

**What goes wrong:** Validation tests use MockVelociraptorServer instead of real infrastructure.

**Why it happens:** Confusion between test layers or desire for faster tests.

**Consequences:**
- Tests pass but code fails against real Velociraptor
- No validation of actual artifact collection
- Defeats purpose of validation testing

**Prevention:**
- Keep MockVelociraptorServer in tests/unit/ only
- Validation tests MUST use real velociraptor_client fixture
- Mark validation tests with `@pytest.mark.validation` to prevent confusion

**Detection:** Review fixture usage - validation tests should never import from tests/mocks/

**Source:** Existing test structure (tests/mocks/ vs tests/integration/) - clear separation maintained

## Scalability Considerations

| Concern | At 10 artifacts | At 100 artifacts | At 1000 artifacts |
|---------|----------------|------------------|-------------------|
| **Test Execution Time** | 2-5 minutes (sequential) | 20-50 minutes (needs parallelization) | 200-500 minutes (requires test sharding) |
| **Infrastructure** | Single Docker container sufficient | Add Windows container, categorize by OS | Multi-environment matrix (OS versions, architectures) |
| **Target Management** | Manual registration in conftest.py | TargetRegistry from config file | Dynamic target discovery via labels |
| **Validation Complexity** | Manual validators per artifact | Validator factory pattern | Schema-driven validation (JSON Schema) |
| **CI/CD Strategy** | Run on every PR | Nightly validation runs | Weekly full matrix, PR smoke tests |

### Recommended Scaling Path

**Phase 1 (10-20 artifacts):**
- Single Docker Linux target
- Manual validator creation per artifact
- Session-scoped fixtures
- Sequential test execution

**Phase 2 (20-100 artifacts):**
- Add Windows Docker target
- Validator factory with reusable rules
- pytest-xdist for parallel execution (4-8 workers)
- Categorize by artifact type (filesystem, process, network)

**Phase 3 (100+ artifacts):**
- Multi-OS matrix (Linux, Windows, macOS VM)
- Schema-driven validation (ForensicArtifacts format)
- CI sharding (split tests across jobs)
- Nightly full validation, PR subset based on changes

**Source:** [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/) for parallel execution, [ForensicArtifacts repository](https://github.com/ForensicArtifacts/artifacts) for schema-driven validation

## New vs Modified Test Infrastructure

### Files to Create (New)

| File | Purpose | Dependencies |
|------|---------|--------------|
| `tests/validation/` | New test directory for validation tests | None |
| `tests/validation/__init__.py` | Package marker | None |
| `tests/validation/conftest.py` | Validation-specific fixtures | tests/conftest.py (inherits) |
| `tests/validation/validators/` | Artifact validator modules | None |
| `tests/validation/validators/__init__.py` | Package marker | None |
| `tests/validation/validators/artifact_validator.py` | Base validator classes | None |
| `tests/validation/target_registry.py` | Target management | velociraptor_client |
| `tests/validation/test_generic_artifacts.py` | Generic artifact validation tests | validation_targets, velociraptor_client |

### Files to Modify (Existing)

| File | Modifications | Reason |
|------|---------------|--------|
| `tests/conftest.py` | Add `validation_targets` fixture (lines 280-310) | Provide target registry for validation tests |
| `pyproject.toml` | Add `validation` marker (line 73) | Test categorization |
| `scripts/test-lab.sh` | Add `test-validation` command (line 312) | Run validation tests separately |

### No Changes Needed

| Component | Why No Changes | Confidence |
|-----------|----------------|------------|
| Docker Compose setup | Existing client container sufficient for Phase 1 | HIGH |
| VelociraptorClient | Already supports artifact collection via VQL | HIGH |
| Integration test fixtures | Validation extends, doesn't replace | HIGH |
| Mock infrastructure | Remains isolated in tests/unit/ | HIGH |

## Build Order and Dependencies

### Recommended Implementation Order

**1. Foundation (Day 1-2):**
```
Create test structure:
  tests/validation/__init__.py
  tests/validation/conftest.py

Add validation marker:
  pyproject.toml (add "validation" marker)

Verify inheritance:
  pytest --co -m validation (should discover 0 tests)
```

**2. Target Management (Day 2-3):**
```
Create TargetRegistry:
  tests/validation/target_registry.py

Add validation_targets fixture:
  tests/validation/conftest.py

Test target discovery:
  Write smoke test that lists available targets
```

**3. First Validation Test (Day 3-4):**
```
Simple artifact collection:
  tests/validation/test_generic_artifacts.py

Test Generic.Client.Info (simple artifact):
  - Collect from Docker target
  - Assert results non-empty
  - Verify basic fields present

Run: pytest -m validation -v
```

**4. Validation Framework (Day 4-5):**
```
Create validator base:
  tests/validation/validators/artifact_validator.py

Enhance first test:
  Replace bare assertions with validator
  Add field type validation
  Test validation report formatting
```

**5. Expand Coverage (Day 5+):**
```
Add more artifacts:
  Generic.System.Pslist
  Linux.Sys.Users

Parametrize common patterns:
  Use @pytest.mark.parametrize for similar artifacts

Add Windows target (optional):
  Extend docker-compose.test.yml
  Test Windows-specific artifacts
```

### Dependency Graph

```
validation_targets fixture
    ├─ Depends on: docker_compose_up (session)
    ├─ Depends on: velociraptor_client (module)
    └─ Creates: TargetRegistry

TargetRegistry
    ├─ Depends on: VelociraptorClient (query enrolled clients)
    └─ Used by: All validation tests (target selection)

ArtifactValidator
    ├─ No dependencies (pure validation logic)
    └─ Used by: Validation tests (result verification)

First Validation Test
    ├─ Depends on: validation_targets
    ├─ Depends on: velociraptor_client
    └─ Optionally uses: ArtifactValidator
```

### Critical Path

**Must Complete in Order:**
1. Add validation marker to pyproject.toml
2. Create tests/validation/ directory structure
3. Implement validation_targets fixture (extends docker_compose_up)
4. Write first smoke test (proves infrastructure works)
5. Create ArtifactValidator (enables rich assertions)
6. Expand to multiple artifacts

**Can Parallelize:**
- Writing validators for different artifact types
- Adding Windows/macOS targets (independent of Linux validation)
- Creating documentation and examples

## Tool-Specific Validation Recommendations

### Suggested Validation Order (Which Tools First)

Based on artifact complexity, infrastructure requirements, and value for catching bugs:

**Tier 1: Generic Artifacts (Start Here)**
- **Generic.Client.Info** - Simplest, always works, good infrastructure test
- **Generic.System.Pslist** - Common, cross-platform, high value
- **Generic.Client.BrowserHistory** - Tests file parsing, common use case

**Why start here:**
- Work on any target (Linux/Windows)
- Low setup requirements
- High confidence validation patterns
- Catch most common integration bugs

**Tier 2: OS-Specific System Artifacts**
- **Linux.Sys.Users** - Well-defined schema, easy validation
- **Windows.System.Services** - Common in investigations
- **Windows.Registry.UserAssist** - Tests registry parsing

**Why second:**
- Require OS-specific targets
- More complex validation (registry, binary parsing)
- Higher value for real-world use cases

**Tier 3: Network and Forensic Artifacts**
- **Windows.Network.NetstatEnriched** - Network artifact validation
- **Windows.Forensics.Prefetch** - Binary parsing validation
- **Linux.Forensics.Journal** - Log parsing validation

**Why later:**
- Complex setup (need network activity, prefetch files)
- Validation requires domain expertise
- Edge cases more common

**Tier 4: Custom/Organization Artifacts**
- Custom artifacts specific to deployment
- Requires intimate knowledge of expected data

**Source:** Artifact complexity assessment based on [DFIR-Metric benchmark](https://arxiv.org/html/2505.19973v1) and practical deployment experience

### Validation Confidence Levels

| Artifact Type | Validation Approach | Confidence |
|--------------|---------------------|------------|
| **Generic.Client.Info** | Field presence + type checking | HIGH - Schema well-defined |
| **Process Lists** | Field types + PID validation | HIGH - Standard format |
| **Browser History** | URL format + timestamp validation | MEDIUM - Browser-dependent format |
| **Registry** | Key paths + value type checking | MEDIUM - Complex nested structure |
| **Binary Artifacts** | Checksum + format magic bytes | LOW - Requires forensic expertise |

## Sources

**Integration Testing with Docker:**
- [pytest-docker](https://github.com/avast/pytest-docker) - Docker-based integration tests
- [Integration testing with pytest & Docker compose](https://xnuinside.medium.com/integration-testing-for-bunch-of-services-with-pytest-docker-compose-4892668f9cba)
- [Advanced Integration Testing Techniques](https://moldstud.com/articles/p-advanced-integration-testing-techniques-for-python-developers-expert-guide-2025)

**Pytest Parametrization:**
- [pytest parametrize documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html)
- [Advanced Pytest Patterns](https://www.fiddler.ai/blog/advanced-pytest-patterns-harnessing-the-power-of-parametrization-and-factory-methods)

**DFIR Testing and Validation:**
- [SANS 2026 DFIR Summit](https://www.sans.org/cyber-security-training-events/digital-forensics-summit-2026) - Industry trends
- [Validation of Forensic Tools](https://joshbrunty.github.io/2021/11/01/validation.html) - NIST validation standards
- [MANTIS DFIR Testing Platform](https://mantis-platform.io/docs/usecases/dfir.html) - Automated artifact testing
- [DFIR-Metric Benchmark](https://arxiv.org/html/2505.19973v1) - Academic benchmark for DFIR tools
- [ForensicArtifacts Repository](https://github.com/ForensicArtifacts/artifacts) - Standardized artifact definitions

---

*Architecture research: 2026-01-24*
*Confidence: HIGH for integration points, MEDIUM for validation framework implementation*
