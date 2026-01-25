# Technology Stack for Real-World DFIR Tool Validation

**Project:** Megaraptor MCP - Real-World Validation Testing
**Researched:** 2026-01-24
**Confidence:** HIGH

## Executive Summary

This stack research focuses on what's needed to validate 35 existing MCP tools against live Velociraptor infrastructure. The project already has pytest + pytest-asyncio with mocked tests. This research identifies additions for:

1. **Real container integration** - Managing Docker test infrastructure programmatically
2. **Output quality validation** - Multi-assertion checking and schema validation
3. **Performance validation** - Load testing for large result sets
4. **gRPC validation** - Testing against real Velociraptor gRPC API

**Key recommendation:** Keep existing pytest/asyncio foundation. Add targeted plugins for output validation (pytest-check) and container management (pytest-docker). Defer heavy performance testing (Locust) until validation phase shows need.

## Current Stack (DO NOT CHANGE)

Based on `pyproject.toml`, the project has:

| Technology | Version | Purpose |
|------------|---------|---------|
| pytest | >=7.0.0 | Test runner |
| pytest-asyncio | >=0.21.0 | Async test support |
| pytest-timeout | >=2.2.0 | Test timeout management |
| docker | >=7.0.0 | Docker API (deployment feature) |
| grpcio | >=1.60.0 | gRPC client (Velociraptor API) |

Test infrastructure exists in `tests/conftest.py` with:
- Docker availability checking (`has_docker()`)
- Docker Compose lifecycle management (`docker_compose_up` fixture)
- Velociraptor API config fixtures
- Test isolation (temp directories, env var cleanup)

## Recommended Stack Additions

### Integration Test Enhancement

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **pytest-docker** | >=3.2.5 | Programmatic container control | Better than manual subprocess calls for container lifecycle. Replaces manual `docker compose` subprocess in conftest.py with pytest-native fixtures. |
| **pytest-check** | >=2.6.2 | Multiple assertions per test | CRITICAL for DFIR tool validation. When validating VQL output structure, need to check multiple fields without stopping at first failure. Provides complete validation picture. |

**Integration rationale:**
- `pytest-docker` works with existing `docker-compose.test.yml` file
- `pytest-check` enhances existing test classes without breaking current assertions
- Both integrate cleanly with pytest-asyncio (no conflicts)

### Output Quality Validation

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **jsonschema** | >=4.26.0 | JSON Schema validation | Velociraptor VQL returns JSON. Schema validation ensures output structure matches expected format. Latest version (Jan 7, 2026) supports Draft 2020-12. |

**Why NOT pytest-jsonschema or pytest-schema:**
- `pytest-jsonschema` (0.2.0) last updated 2020, unmaintained
- `pytest-schema` adds unnecessary abstraction layer
- Core `jsonschema` library more flexible, better maintained, zero pytest integration issues

### Performance Testing (DEFERRED)

| Library | Version | Purpose | Decision |
|---------|---------|---------|----------|
| **Locust** | 2.43.1 | Load testing | DEFER to Phase 2. Wait until container validation reveals performance issues. Installing now adds complexity without proven need. |
| **pytest-benchmark** | Latest | Microbenchmarking | DEFER. Not needed for integration testing. Useful if profiling individual function performance, but validation focuses on end-to-end correctness. |

**Deferral rationale:**
- Performance testing requires baseline metrics (don't have yet)
- Container validation will reveal if performance testing needed
- Locust requires Python >=3.10 (project supports 3.10+, compatible but unnecessary now)
- pytest-benchmark (5.2.3) better for unit-level performance, not integration

### gRPC Testing (EVALUATE)

| Library | Version | Purpose | Decision |
|---------|---------|---------|----------|
| **pytest-grpc** | 0.8.0 | gRPC service testing | SKIP. Last updated May 2020 (6 years old). Project already has `grpcio` and real Velociraptor server for testing. Mock gRPC server not needed - that's what test container provides. |
| **grpc_testing** | Built-in | Official gRPC testing | SKIP. For mocking gRPC services. Project moving AWAY from mocks toward real container testing. |

**gRPC testing rationale:**
- Existing approach (real Velociraptor in Docker) is superior to mocked gRPC
- pytest-grpc unmaintained (0.8.0 from 2020)
- gRPC error handling tested via real API responses, not mocks

### Test Execution Optimization (OPTIONAL)

| Library | Version | Purpose | Decision |
|---------|---------|---------|----------|
| **pytest-xdist** | >=3.8.0 | Parallel test execution | OPTIONAL. Useful for running 104+ tests faster. Integration tests are slow (Docker startup). Parallel execution with `-n auto` can speed up test suite. Add if test runtime becomes problematic. |
| **pytest-cov** | >=7.0.0 | Coverage reporting | OPTIONAL. Good for identifying untested code paths. Not critical for validation milestone but useful for gap analysis. Already works with existing pytest config. |

**Optimization rationale:**
- pytest-xdist safe to add, speeds up existing tests with no code changes
- pytest-cov useful for gap analysis (active requirement: "Gap analysis document with needed additions")
- Both mature, well-maintained pytest plugins

## Recommended Installation

### Phase 1: Core Validation Stack (REQUIRED)

```bash
# Add to pyproject.toml [project.optional-dependencies] dev section:
pip install pytest-docker>=3.2.5
pip install pytest-check>=2.6.2
pip install jsonschema>=4.26.0
```

**Integration notes:**
- pytest-docker uses existing `tests/docker-compose.test.yml`
- pytest-check: No config needed, import as `from pytest_check import check`
- jsonschema: Use directly in test assertions, no pytest plugin needed

### Phase 2: Optional Enhancements (ADD AS NEEDED)

```bash
# If test suite runtime becomes issue:
pip install pytest-xdist>=3.8.0

# For gap analysis and coverage reporting:
pip install pytest-cov>=7.0.0

# If performance issues discovered in container validation:
pip install locust>=2.43.1
```

## Container Management Strategy

### Current Approach (in conftest.py)

```python
# Manual subprocess calls
subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"])
```

### Recommended Approach (pytest-docker)

```python
# pytest-docker provides docker_compose_file and docker_services fixtures
@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return str(Path(__file__).parent / "docker-compose.test.yml")

@pytest.fixture(scope="session")
def docker_services(docker_compose_file):
    # pytest-docker handles: up, health checks, teardown
    pass
```

**Benefits:**
- Automatic health check waiting (replace manual `is_velociraptor_running()` polling)
- Better error messages on container failure
- Port mapping helpers for connecting to containers
- Integrates with pytest's fixture lifecycle

**Migration path:**
- Keep existing fixtures initially (backward compatible)
- Gradually migrate tests to use `docker_services` fixture
- Remove manual subprocess code once migration complete

## Output Validation Pattern

### Current Pattern

```python
def test_list_artifacts(self, velociraptor_client):
    result = velociraptor_client.query("SELECT name, description FROM artifact_definitions() LIMIT 50")
    assert isinstance(result, list)
    assert len(result) > 0
```

**Problem:** Stops at first assertion failure. If `isinstance` fails, don't see `len` result.

### Recommended Pattern (pytest-check)

```python
from pytest_check import check

def test_list_artifacts_comprehensive(self, velociraptor_client):
    result = velociraptor_client.query("SELECT name, description FROM artifact_definitions() LIMIT 50")

    # Check all conditions, report all failures
    with check: assert isinstance(result, list), "Result should be a list"
    with check: assert len(result) > 0, "Should return at least one artifact"

    if result:  # If we got results, validate structure
        first_artifact = result[0]
        with check: assert "name" in first_artifact, "Artifact should have 'name' field"
        with check: assert "description" in first_artifact, "Artifact should have 'description' field"
        with check: assert first_artifact["name"].startswith("Generic."), "Should return Generic artifacts"
```

**Benefits:**
- See all validation failures in single test run
- Better for DFIR output quality validation (validates structure, content, format)
- Backward compatible (can mix `assert` and `check`)

### Schema Validation Pattern (jsonschema)

```python
import jsonschema

# Define schema for VQL client list response
CLIENT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["client_id", "os_info"],
        "properties": {
            "client_id": {"type": "string", "pattern": "^C\\."},
            "os_info": {"type": "object"}
        }
    }
}

def test_list_clients_schema(self, velociraptor_client):
    result = velociraptor_client.query("SELECT * FROM clients() LIMIT 10")

    # Validate against schema
    jsonschema.validate(instance=result, schema=CLIENT_SCHEMA)

    # Schema validation passes, now check content quality
    with check: assert len(result) <= 10, "LIMIT 10 should be respected"
```

**Benefits:**
- Formal contract validation (output structure matches expectations)
- Reusable schemas across multiple tests
- Better error messages (shows exact schema violation)

## Version Compatibility Matrix

All recommended libraries compatible with existing stack:

| Library | Python 3.10 | Python 3.11 | Python 3.12 | Async Support | Notes |
|---------|-------------|-------------|-------------|---------------|-------|
| pytest-docker 3.2.5 | ✓ | ✓ | ✓ | ✓ | Works with pytest-asyncio |
| pytest-check 2.6.2 | ✓ | ✓ | ✓ | ✓ | No conflicts |
| jsonschema 4.26.0 | ✓ | ✓ | ✓ | ✓ | Dropped 3.8, requires 3.10+ |
| pytest-xdist 3.8.0 | ✓ | ✓ | ✓ | ✓ | Some async test limitations |
| pytest-cov 7.0.0 | ✓ | ✓ | ✓ | ✓ | Coverage.py 7.13.1 |
| locust 2.43.1 | ✓ | ✓ | ✓ | ✓ | Requires 3.10+, event-based |

**Compatibility notes:**
- jsonschema 4.26.0 dropped Python 3.8 support (Jan 7, 2026) - OK, project requires 3.10+
- pytest-check 2.6.2 supports Python 3.9-3.14 - OK
- pytest-docker 3.2.5 uses docker-compose V2 plugin - OK, modern approach
- All libraries work with pytest 7.0+ (project uses 7.0.0+)

## Alternative Approaches Considered

### Testcontainers-python (REJECTED)

| Aspect | testcontainers-python 4.14.0 | Current Approach |
|--------|------------------------------|------------------|
| Container lifecycle | Programmatic Python API | docker-compose.yml |
| Learning curve | Steeper (new API) | Shallow (existing compose file) |
| Port management | Automatic random ports | Fixed ports in compose file |
| Multi-container | Requires code | Declarative YAML |

**Rejection rationale:**
- Project already has `docker-compose.test.yml` (line 18 of conftest.py)
- testcontainers requires rewriting container definitions in Python
- pytest-docker works with existing compose file
- Testcontainers better for projects without existing Docker Compose setup

**When to reconsider:**
- If needing dynamic container configuration per test
- If container definitions too complex for compose YAML
- If requiring programmatic port discovery (not needed, test uses fixed ports)

### pytest-docker-compose (ALTERNATIVE)

pytest-docker-compose (separate from pytest-docker) automatically spins up compose stack.

**Why pytest-docker instead:**
- pytest-docker more actively maintained (3.2.5 recent)
- pytest-docker gives finer-grained control (current conftest.py needs it)
- pytest-docker-compose opinionated about fixture scopes (less flexible)
- Current implementation closer to pytest-docker patterns

### grpc-testing vs Real Server (DECISION: REAL SERVER)

**Mock approach:**
```python
from grpc_testing import server_from_dictionary
# Create mock gRPC server in Python
```

**Real server approach (CHOSEN):**
```python
# Use real Velociraptor in Docker container
client = VelociraptorClient(config_from_test_container)
```

**Why real server:**
- Validation goal: "validate tools work against real Velociraptor"
- Mocks hide edge cases (error handling, network issues, version differences)
- Test container already exists (docker-compose.test.yml)
- Real server validates gRPC + VQL + Velociraptor logic together

## Installation Script

```bash
# Update pyproject.toml [project.optional-dependencies] dev section
# BEFORE:
# dev = [
#     "pytest>=7.0.0",
#     "pytest-asyncio>=0.21.0",
#     "pytest-timeout>=2.2.0",
# ]

# AFTER (Phase 1 - Core validation):
# dev = [
#     "pytest>=7.0.0",
#     "pytest-asyncio>=0.21.0",
#     "pytest-timeout>=2.2.0",
#     "pytest-docker>=3.2.5",      # Container lifecycle management
#     "pytest-check>=2.6.2",        # Multiple assertions per test
#     "jsonschema>=4.26.0",         # VQL output schema validation
# ]

# AFTER (Phase 2 - Add if needed):
# dev = [
#     "pytest>=7.0.0",
#     "pytest-asyncio>=0.21.0",
#     "pytest-timeout>=2.2.0",
#     "pytest-docker>=3.2.5",
#     "pytest-check>=2.6.2",
#     "jsonschema>=4.26.0",
#     "pytest-xdist>=3.8.0",       # Optional: Parallel execution
#     "pytest-cov>=7.0.0",          # Optional: Coverage for gap analysis
# ]

# Install Phase 1:
pip install -e ".[dev]"

# Or install directly:
pip install pytest-docker pytest-check jsonschema
```

## Migration Path

### Step 1: Add Libraries (Non-Breaking)

```bash
pip install pytest-docker pytest-check jsonschema
```

All three libraries can coexist with current test suite. No breaking changes.

### Step 2: Enhance Existing Tests (Incremental)

```python
# tests/integration/test_dfir_tools.py
# ADD pytest-check to existing tests (backward compatible)

from pytest_check import check  # Add import

class TestArtifactOperations:
    def test_list_artifacts(self, velociraptor_client):
        result = velociraptor_client.query(
            "SELECT name, description FROM artifact_definitions() LIMIT 50"
        )

        # OLD: assert isinstance(result, list)
        # NEW: Multiple checks
        with check: assert isinstance(result, list), "Result type validation"
        with check: assert len(result) > 0, "Should return artifacts"

        if result:
            with check: assert "name" in result[0], "Artifact has name field"
            with check: assert "description" in result[0], "Artifact has description field"
```

### Step 3: Add Schema Validation (New Tests)

```python
# tests/integration/test_output_quality.py (NEW FILE)
import jsonschema
from pytest_check import check

# Define schemas for VQL outputs
SCHEMAS = {
    "client_list": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["client_id"],
            "properties": {
                "client_id": {"type": "string", "pattern": "^C\\."}
            }
        }
    }
}

class TestOutputQuality:
    """Validate VQL output structure and quality."""

    def test_client_list_schema(self, velociraptor_client):
        result = velociraptor_client.query("SELECT * FROM clients() LIMIT 10")
        jsonschema.validate(instance=result, schema=SCHEMAS["client_list"])
```

### Step 4: Migrate Container Management (Later)

```python
# tests/conftest.py
# CURRENT: Manual subprocess
# FUTURE: pytest-docker fixtures
# Can do this AFTER validation tests working
```

## What NOT to Add

### Avoid These Libraries

| Library | Why NOT |
|---------|---------|
| **pytest-mock** | unittest.mock (built-in) sufficient. Project moving away from mocks. |
| **responses** | HTTP mocking library. Project uses gRPC, not HTTP. |
| **pytest-vcr / vcrpy** | Records/replays HTTP interactions. Not applicable to gRPC. |
| **hypothesis** | Property-based testing. Overkill for validation milestone. |
| **faker** | Test data generation. VQL queries return real Velociraptor data. |
| **pytest-bdd** | BDD testing. Not project's test style. |

### Avoid These Approaches

**Don't:** Install Locust immediately
**Why:** Performance testing premature. Validate correctness first, then performance.

**Don't:** Replace pytest with another test runner
**Why:** 104 existing tests. pytest deeply integrated.

**Don't:** Add pytest-grpc for gRPC mocking
**Why:** Real Velociraptor container superior to mocks for validation.

**Don't:** Add testcontainers-python
**Why:** docker-compose.test.yml already exists. pytest-docker leverages it.

**Don't:** Add multiple assertion libraries
**Why:** pytest-check sufficient for multi-assertion needs.

## Testing Anti-Patterns to Avoid

Based on research into pytest best practices for integration testing:

### Anti-Pattern 1: Fixture Scope Conflicts

**Problem:** Using `module` and `function` scope fixtures on same container in one file.

```python
# WRONG: Causes docker-compose conflicts
@pytest.fixture(scope="module")
def docker_compose_module():
    subprocess.run(["docker", "compose", "up"])

@pytest.fixture(scope="function")
def docker_compose_function():
    subprocess.run(["docker", "compose", "up"])  # CONFLICT!
```

**Solution:** Use session-scoped `docker_compose_up` (existing pattern correct).

### Anti-Pattern 2: Stopping at First Assertion

**Problem:** Can't diagnose output quality issues fully.

```python
# WRONG: Stops at first failure
def test_client_output(result):
    assert "client_id" in result  # Fails here, never check other fields
    assert "os_info" in result    # Never executed
    assert "hostname" in result   # Never executed
```

**Solution:** Use pytest-check (recommended above).

### Anti-Pattern 3: No Schema Validation

**Problem:** VQL output structure changes undetected.

```python
# WRONG: Only checks presence, not structure
def test_artifact(result):
    assert len(result) > 0  # Could be malformed JSON
```

**Solution:** Use jsonschema (recommended above).

### Anti-Pattern 4: Manual Container Cleanup

**Problem:** Containers left running on test failure.

```python
# WRONG: No cleanup on exception
def test_something():
    subprocess.run(["docker", "compose", "up"])
    # Test fails here - containers keep running
    subprocess.run(["docker", "compose", "down"])  # Never executed
```

**Solution:** pytest-docker handles cleanup automatically (even on failure).

## Summary

### Core Recommendations (Phase 1)

**ADD:**
- pytest-docker 3.2.5 (container lifecycle)
- pytest-check 2.6.2 (multi-assertion validation)
- jsonschema 4.26.0 (output schema validation)

**DEFER:**
- Locust (performance testing until needed)
- pytest-benchmark (microbenchmarking not required)
- pytest-xdist (nice-to-have, not critical)
- pytest-cov (useful for gap analysis, not validation)

**SKIP:**
- pytest-grpc (unmaintained, real container better)
- testcontainers-python (docker-compose.yml already exists)
- grpc_testing (moving away from mocks)

### Integration Points

All recommended libraries integrate cleanly:
- pytest-docker works with existing docker-compose.test.yml
- pytest-check enhances existing test assertions (no breaking changes)
- jsonschema pure Python library (no pytest plugin conflicts)
- All compatible with pytest 7.0+ and pytest-asyncio 0.21.0+

### Next Steps

1. Add pytest-docker, pytest-check, jsonschema to dev dependencies
2. Create output quality test suite using pytest-check
3. Define VQL output schemas using jsonschema
4. Validate all 35 MCP tools against live container
5. Document findings for gap analysis
6. Add pytest-xdist if test runtime becomes issue
7. Add Locust only if performance issues discovered

## Sources

- [pytest-docker PyPI](https://pypi.org/project/pytest-docker/)
- [pytest-docker GitHub](https://github.com/avast/pytest-docker)
- [pytest-check PyPI](https://pypi.org/project/pytest-check/)
- [jsonschema 4.26.0 Documentation](https://python-jsonschema.readthedocs.io/)
- [jsonschema PyPI](https://pypi.org/project/jsonschema/)
- [Locust Documentation 2.43.1](https://docs.locust.io/en/stable/)
- [Locust PyPI](https://pypi.org/project/locust/)
- [testcontainers-python PyPI](https://pypi.org/project/testcontainers/)
- [testcontainers-python GitHub Releases](https://github.com/testcontainers/testcontainers-python/releases)
- [pytest-docker-compose PyPI](https://pypi.org/project/pytest-docker-compose/)
- [Python Integration Tests: docker-compose vs testcontainers](https://medium.com/codex/python-integration-tests-docker-compose-vs-testcontainers-94986d7547ce)
- [pytest-xdist PyPI](https://pypi.org/project/pytest-xdist/)
- [pytest-xdist Documentation](https://pytest-xdist.readthedocs.io/)
- [pytest-cov 7.0.0 Documentation](https://pytest-cov.readthedocs.io/)
- [pytest-cov PyPI](https://pypi.org/project/pytest-cov/)
- [pytest-grpc PyPI](https://pypi.org/project/pytest-grpc/)
- [gRPC Testing Documentation](https://grpc.github.io/grpc/python/grpc_testing.html)
- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
- [Integration testing with Pytest & Docker compose](https://xnuinside.medium.com/integration-testing-for-bunch-of-services-with-pytest-docker-compose-4892668f9cba)
- [pytest Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
