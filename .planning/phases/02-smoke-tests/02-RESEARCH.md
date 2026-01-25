# Phase 2: Smoke Tests - Research

**Researched:** 2026-01-25
**Domain:** MCP server integration testing, smoke test patterns, JSON Schema validation
**Confidence:** MEDIUM

## Summary

Phase 2 establishes comprehensive smoke testing for 35 MCP tools against a live Velociraptor deployment. Smoke tests verify basic operability - that each tool is callable, returns non-error responses, and produces valid JSON output structures. This phase focuses on fast, broad validation rather than deep functional testing.

**Primary domain areas investigated:**
1. **MCP server testing patterns** - MCP Inspector approach, tool invocation patterns
2. **Smoke test organization** - pytest parametrization for endpoint coverage
3. **JSON Schema validation** - jsonschema library for output structure validation
4. **Multiple assertion patterns** - pytest-check for comprehensive field validation
5. **VQL output structures** - Understanding Velociraptor JSON response formats
6. **Resource browsing** - Testing velociraptor:// URI patterns

The standard approach is to use pytest parametrization to run smoke tests across all 35 MCP tools, validating HTTP-like response codes (non-error), JSON Schema conformance, and basic field presence. Phase 1 established the VelociraptorClient fixture; Phase 2 extends this with MCP server invocation patterns and comprehensive output validation.

**Primary recommendation:** Use pytest.mark.parametrize to test all 35 MCP tools with basic inputs, pytest-check for multiple field assertions, and jsonschema for structure validation. Organize tests by MCP capability (tools, resources, prompts) rather than by Velociraptor domain (clients, artifacts, hunts).

## Standard Stack

The established libraries/tools for MCP server smoke testing:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest-check | >=2.6.2 | Multiple assertions per test | Essential for smoke tests - check all output fields without stopping at first failure. Shows complete validation picture for each tool. Already in pyproject.toml from Phase 1. |
| jsonschema | >=4.26.0 | JSON Schema validation | MCP tools return JSON. Validates output structure matches expected format. Latest version (Jan 7, 2026) supports Draft 2020-12. Already in pyproject.toml from Phase 1. |
| pytest | >=7.0.0 | Test runner with parametrization | Core test framework. Parametrize feature critical for testing all 35 tools efficiently. Already in project. |

### Supporting (Already in Project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | >=0.21.0 | Async test support | MCP tools are async functions - already handles async test execution |
| pytest-timeout | >=2.2.0 | Test timeout management | Prevents hanging on slow artifact collections or VQL queries |

### MCP Testing Tools (Development Only)
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| MCP Inspector | latest | Interactive MCP server testing | Development/debugging only - not for automated tests. Use npx @modelcontextprotocol/inspector |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| jsonschema | Pydantic | Pydantic requires defining Python classes for every response type. jsonschema uses declarative JSON schemas. Choose Pydantic only if building a typed client library. |
| pytest-check | pytest-soft-assertions | pytest-soft-assertions is unmaintained (last update 2020). pytest-check is actively maintained with 2.6.2 release in 2024. |
| Parametrized tests | Individual test per tool | 35 individual tests = massive code duplication. Parametrization tests all tools with 1 function. Only use individual tests for tools needing unique setup. |

**Installation:**
```bash
# Already installed from Phase 1
# pytest>=7.0.0, pytest-asyncio>=0.21.0, pytest-timeout>=2.2.0
# pytest-check>=2.6.2, jsonschema>=4.26.0

# No new dependencies needed for Phase 2
```

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── conftest.py                          # EXISTING: Session/module fixtures
├── integration/
│   ├── test_dfir_tools.py              # EXISTING: VQL integration tests
│   ├── test_smoke_mcp_tools.py         # NEW: Smoke tests for 35 MCP tools
│   ├── test_smoke_resources.py         # NEW: Smoke tests for resource URIs
│   ├── test_smoke_prompts.py           # NEW: Smoke tests for prompts
│   ├── schemas/
│   │   ├── __init__.py                 # NEW: Schema registry
│   │   ├── client_schemas.py           # NEW: Client tool output schemas
│   │   ├── artifact_schemas.py         # NEW: Artifact tool output schemas
│   │   ├── hunt_schemas.py             # NEW: Hunt tool output schemas
│   │   ├── flow_schemas.py             # NEW: Flow tool output schemas
│   │   ├── vql_schemas.py              # NEW: VQL tool output schemas
│   │   └── deployment_schemas.py       # NEW: Deployment tool output schemas
│   └── helpers/
│       ├── wait_helpers.py             # EXISTING: Flow completion polling
│       ├── cleanup_helpers.py          # EXISTING: Entity cleanup
│       ├── target_registry.py          # EXISTING: Client capability tracking
│       └── mcp_helpers.py              # NEW: MCP tool invocation helpers
└── fixtures/                           # EXISTING: Config files
```

### Pattern 1: Parametrized Smoke Test for All MCP Tools
**What:** Single test function that runs against all 35 MCP tools using pytest.mark.parametrize with tool name and minimal valid input.

**When to use:** For broad coverage smoke testing - verify every tool is callable and returns valid output structure.

**Example:**
```python
# tests/integration/test_smoke_mcp_tools.py
import pytest
import json
from pytest_check import check
from jsonschema import validate, ValidationError

from megaraptor_mcp.server import create_server
from tests.integration.schemas import get_tool_schema

# Define minimal valid inputs for each tool
TOOL_SMOKE_INPUTS = [
    # Client tools
    ("list_clients", {"limit": 10}),
    ("get_client_info", {"client_id": "C.test"}),
    ("label_client", {"client_id": "C.test", "labels": ["TEST-smoke"], "operation": "add"}),
    ("quarantine_client", {"client_id": "C.test", "quarantine": True}),

    # Artifact tools
    ("list_artifacts", {"limit": 10}),
    ("get_artifact", {"artifact_name": "Generic.Client.Info"}),
    ("collect_artifact", {"client_id": "C.test", "artifacts": ["Generic.Client.Info"]}),

    # Hunt tools
    ("create_hunt", {"artifacts": ["Generic.Client.Info"], "description": "TEST-smoke"}),
    ("list_hunts", {"limit": 10}),
    ("get_hunt_results", {"hunt_id": "H.test"}),
    ("modify_hunt", {"hunt_id": "H.test", "state": "PAUSED"}),

    # Flow tools
    ("list_flows", {"client_id": "C.test", "limit": 10}),
    ("get_flow_results", {"client_id": "C.test", "flow_id": "F.test"}),
    ("get_flow_status", {"client_id": "C.test", "flow_id": "F.test"}),
    ("cancel_flow", {"client_id": "C.test", "flow_id": "F.test"}),

    # VQL tools
    ("run_vql", {"query": "SELECT * FROM info()"}),
    ("vql_help", {"topic": "SELECT"}),

    # Deployment tools (18 more entries...)
]


@pytest.mark.smoke
@pytest.mark.parametrize("tool_name,inputs", TOOL_SMOKE_INPUTS)
async def test_mcp_tool_smoke(
    tool_name: str,
    inputs: dict,
    velociraptor_client,
    enrolled_client_id
):
    """Smoke test: Verify MCP tool is callable and returns valid output.

    This test validates:
    1. Tool can be invoked without errors
    2. Tool returns TextContent (not error)
    3. Response is valid JSON
    4. Response matches expected JSON schema
    5. Required fields are present
    """
    server = create_server()

    # Replace placeholders with real test client ID
    if "client_id" in inputs and inputs["client_id"] == "C.test":
        inputs["client_id"] = enrolled_client_id

    # Invoke the MCP tool
    try:
        result = await server.call_tool(tool_name, inputs)
    except Exception as e:
        pytest.fail(f"Tool {tool_name} raised exception: {e}")

    # Validate response structure
    with check: assert result is not None, f"{tool_name} returned None"
    with check: assert len(result) > 0, f"{tool_name} returned empty result"

    # First content should be TextContent
    content = result[0]
    with check: assert hasattr(content, 'type'), f"{tool_name} missing 'type' field"
    with check: assert content.type == "text", f"{tool_name} returned type={content.type}, expected 'text'"

    # Parse JSON response
    try:
        response_data = json.loads(content.text)
    except json.JSONDecodeError as e:
        pytest.fail(f"{tool_name} returned invalid JSON: {e}")

    # Validate against JSON schema if defined
    schema = get_tool_schema(tool_name)
    if schema:
        try:
            validate(instance=response_data, schema=schema)
        except ValidationError as e:
            pytest.fail(f"{tool_name} schema validation failed: {e.message}")

    # Check for error field (tool-specific error handling)
    with check: assert "error" not in response_data or response_data["error"] is None, \
        f"{tool_name} returned error: {response_data.get('error')}"
```

**Source:** [pytest parametrization documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html), [MCP Inspector testing patterns](https://modelcontextprotocol.io/docs/tools/inspector)

### Pattern 2: JSON Schema Validation with Reusable Schemas
**What:** Define JSON schemas for each MCP tool's expected output structure, store in separate modules, load dynamically per tool.

**When to use:** For validating MCP tool output structure - ensures tools return consistent, parseable JSON for AI assistants.

**Example:**
```python
# tests/integration/schemas/client_schemas.py
"""JSON schemas for client management tool outputs."""

LIST_CLIENTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["client_id", "hostname"],
        "properties": {
            "client_id": {
                "type": "string",
                "pattern": "^C\\."
            },
            "hostname": {"type": "string"},
            "os": {"type": "string"},
            "labels": {
                "type": "array",
                "items": {"type": "string"}
            },
            "last_seen_at": {"type": "string"}
        }
    }
}

GET_CLIENT_INFO_SCHEMA = {
    "type": "object",
    "required": ["client_id", "os_info"],
    "properties": {
        "client_id": {"type": "string", "pattern": "^C\\."},
        "os_info": {
            "type": "object",
            "required": ["hostname", "system"],
            "properties": {
                "hostname": {"type": "string"},
                "system": {"type": "string"},
                "release": {"type": "string"}
            }
        }
    }
}

LABEL_CLIENT_SCHEMA = {
    "type": "object",
    "required": ["client_id", "operation", "current_labels"],
    "properties": {
        "client_id": {"type": "string"},
        "operation": {"type": "string", "enum": ["add", "remove"]},
        "labels_modified": {
            "type": "array",
            "items": {"type": "string"}
        },
        "current_labels": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}


# tests/integration/schemas/__init__.py
"""Schema registry for MCP tool output validation."""

from .client_schemas import LIST_CLIENTS_SCHEMA, GET_CLIENT_INFO_SCHEMA, LABEL_CLIENT_SCHEMA
from .artifact_schemas import LIST_ARTIFACTS_SCHEMA, GET_ARTIFACT_SCHEMA
from .vql_schemas import RUN_VQL_SCHEMA

_SCHEMA_REGISTRY = {
    "list_clients": LIST_CLIENTS_SCHEMA,
    "get_client_info": GET_CLIENT_INFO_SCHEMA,
    "label_client": LABEL_CLIENT_SCHEMA,
    "list_artifacts": LIST_ARTIFACTS_SCHEMA,
    "get_artifact": GET_ARTIFACT_SCHEMA,
    "run_vql": RUN_VQL_SCHEMA,
    # ... 35 total tool schemas
}

def get_tool_schema(tool_name: str) -> dict | None:
    """Get JSON schema for a tool's output."""
    return _SCHEMA_REGISTRY.get(tool_name)
```

**Source:** [JSON Schema validation best practices](https://python-jsonschema.readthedocs.io/en/stable/validate/), [API testing JSON patterns](https://www.qabash.com/practical-json-patterns-api-to-assertions-in-pytest/)

### Pattern 3: Multiple Assertions with pytest-check
**What:** Use pytest-check's `with check:` blocks to validate multiple fields without stopping at first failure. Shows complete validation picture for smoke tests.

**When to use:** When validating MCP tool output - need to see ALL field failures, not just first one.

**Example:**
```python
# tests/integration/test_smoke_mcp_tools.py
from pytest_check import check

def test_generic_client_info_artifact(velociraptor_client, enrolled_client_id):
    """Smoke test: Generic.Client.Info returns expected structure."""

    # Collect artifact
    vql = f"""
    SELECT collect_client(
        client_id='{enrolled_client_id}',
        artifacts=['Generic.Client.Info']
    ) AS collection
    FROM scope()
    """
    result = velociraptor_client.query(vql)

    # Wait for flow completion
    from tests.integration.helpers.wait_helpers import wait_for_flow_completion
    flow_id = result[0]["collection"]["flow_id"]
    wait_for_flow_completion(velociraptor_client, enrolled_client_id, flow_id)

    # Get flow results
    results_vql = f"""
    SELECT * FROM source(
        client_id='{enrolled_client_id}',
        flow_id='{flow_id}',
        artifact='Generic.Client.Info'
    )
    """
    results = velociraptor_client.query(results_vql)

    # Validate all expected fields (don't stop at first failure)
    with check: assert len(results) > 0, "Generic.Client.Info returned no results"

    if results:
        info = results[0]

        # Check all critical fields
        with check: assert "Hostname" in info, "Missing 'Hostname' field"
        with check: assert "OS" in info, "Missing 'OS' field"
        with check: assert "Platform" in info, "Missing 'Platform' field"
        with check: assert "ClientId" in info, "Missing 'ClientId' field"

        # Validate field types
        if "Hostname" in info:
            with check: assert isinstance(info["Hostname"], str), "Hostname not a string"
            with check: assert len(info["Hostname"]) > 0, "Hostname is empty"

        if "ClientId" in info:
            with check: assert info["ClientId"].startswith("C."), \
                f"ClientId has wrong format: {info['ClientId']}"
```

**Source:** [pytest-check documentation](https://pypi.org/project/pytest-check/), [delayed assert patterns](https://pythontest.com/strategy/delayed-assert/)

### Pattern 4: Resource URI Smoke Testing
**What:** Test velociraptor:// resource URIs return valid data structures for MCP resource browsing.

**When to use:** For validating MCP resource endpoints - SMOKE-07 requirement.

**Example:**
```python
# tests/integration/test_smoke_resources.py
import pytest
from pytest_check import check
from jsonschema import validate

from megaraptor_mcp.server import create_server
from tests.integration.schemas.resource_schemas import RESOURCE_SCHEMAS

RESOURCE_URIS = [
    "velociraptor://clients",
    "velociraptor://hunts",
    "velociraptor://artifacts",
    "velociraptor://server-info",
    "velociraptor://deployments",
]


@pytest.mark.smoke
@pytest.mark.parametrize("uri", RESOURCE_URIS)
async def test_resource_uri_smoke(uri: str, velociraptor_client):
    """Smoke test: Resource URI returns valid data."""

    server = create_server()

    # Read resource
    try:
        result = await server.read_resource(uri)
    except Exception as e:
        pytest.fail(f"Resource {uri} raised exception: {e}")

    # Validate response
    with check: assert result is not None, f"Resource {uri} returned None"
    with check: assert len(result) > 0, f"Resource {uri} returned empty result"

    # Validate content
    content = result[0]
    with check: assert hasattr(content, 'uri'), f"Resource {uri} missing 'uri' field"
    with check: assert hasattr(content, 'text'), f"Resource {uri} missing 'text' field"

    # Parse and validate against schema
    import json
    try:
        data = json.loads(content.text)
    except json.JSONDecodeError as e:
        pytest.fail(f"Resource {uri} returned invalid JSON: {e}")

    # Schema validation
    schema = RESOURCE_SCHEMAS.get(uri.split("://")[1].split("/")[0])
    if schema:
        validate(instance=data, schema=schema)
```

**Source:** [MCP resources documentation](https://modelcontextprotocol.io/docs/concepts/resources), Phase 2 requirements SMOKE-07

### Pattern 5: VQL Query Smoke Testing
**What:** Test basic VQL queries execute without syntax errors and return expected JSON structure.

**When to use:** For validating VQL execution capability - SMOKE-04 requirement.

**Example:**
```python
# tests/integration/test_smoke_vql.py
import pytest
from pytest_check import check

SMOKE_VQL_QUERIES = [
    ("info", "SELECT * FROM info()"),
    ("clients", "SELECT client_id, hostname FROM clients() LIMIT 10"),
    ("artifacts", "SELECT name, type FROM artifact_definitions() LIMIT 10"),
    ("hunts", "SELECT hunt_id, state FROM hunts() LIMIT 10"),
    ("flows", "SELECT * FROM flows() LIMIT 10"),
]


@pytest.mark.smoke
@pytest.mark.parametrize("query_name,vql", SMOKE_VQL_QUERIES)
def test_vql_query_smoke(
    query_name: str,
    vql: str,
    velociraptor_client
):
    """Smoke test: Basic VQL query executes without syntax errors."""

    # Execute VQL
    try:
        result = velociraptor_client.query(vql)
    except Exception as e:
        pytest.fail(f"VQL query '{query_name}' raised exception: {e}")

    # Validate result structure
    with check: assert result is not None, f"VQL '{query_name}' returned None"
    with check: assert isinstance(result, list), \
        f"VQL '{query_name}' returned {type(result)}, expected list"

    # Result may be empty (no error) but should be list
    # Empty list = valid query but no matching data
    # This is acceptable for smoke tests
```

**Source:** [Velociraptor VQL documentation](https://docs.velociraptor.app/docs/vql/fundamentals/), Phase 2 requirements SMOKE-04

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Testing all 35 tools | 35 individual test functions | pytest.mark.parametrize with tool list | Parametrization eliminates code duplication, makes adding new tools trivial, and ensures consistent validation logic across all tools. |
| JSON validation | Manual isinstance() and key checking | jsonschema with schema definitions | Schema validation catches structure changes, provides clear error messages, and serves as documentation. Manual checking is verbose and error-prone. |
| Multiple field assertions | Standard pytest assertions | pytest-check with `with check:` blocks | Smoke tests need to see ALL failures, not just first. Standard assertions hide subsequent issues. pytest-check shows complete validation picture. |
| MCP server invocation | Direct tool function calls | Server.call_tool() through MCP protocol | Direct calls bypass MCP protocol validation. call_tool() tests the actual integration path AI assistants use. |
| Output format validation | String parsing and regex | JSON Schema Draft 2020-12 | JSON Schema handles complex types (dates, URIs, enums), nested objects, optional fields. Regex is brittle and incomplete. |

**Key insight:** Smoke testing is about breadth, not depth. Use parametrization to maximize coverage with minimal code. Use formal validation (JSON Schema) rather than ad-hoc assertions. Focus on "can it be called and does it return valid structure" not "does it perform the operation correctly" (that's for integration tests).

## Common Pitfalls

### Pitfall 1: Testing Functionality Instead of Callability

**What goes wrong:** Smoke tests verify the tool performs its operation correctly (e.g., artifact collection completes successfully) instead of just verifying the tool is callable and returns valid structure.

**Why it happens:**
- Confusion between smoke tests and integration tests
- Desire to test "real" behavior, not just structure
- Copying integration test patterns into smoke tests
- Assumption that smoke = shallow integration

**Consequences:**
- Smoke tests take too long (waiting for artifact collections to complete)
- Flaky smoke tests (async operations may timeout)
- False negatives (tool works but operation fails due to test environment)
- Defeats purpose of smoke tests (fast validation of basic operability)

**How to avoid:**
```python
# BAD - Testing functionality (this is an integration test)
@pytest.mark.smoke
def test_collect_artifact_smoke(velociraptor_client, enrolled_client_id):
    result = collect_artifact(enrolled_client_id, ["Generic.Client.Info"])
    flow_id = result["flow_id"]

    # Wait for collection to complete (TOO SLOW FOR SMOKE TEST)
    wait_for_flow_completion(velociraptor_client, enrolled_client_id, flow_id)

    # Get results and validate (TOO DEEP FOR SMOKE TEST)
    results = get_flow_results(velociraptor_client, enrolled_client_id, flow_id)
    assert len(results) > 0
    assert "Hostname" in results[0]

# GOOD - Testing callability (true smoke test)
@pytest.mark.smoke
async def test_collect_artifact_smoke(enrolled_client_id):
    server = create_server()

    # Just invoke the tool and check it returns valid structure
    result = await server.call_tool("collect_artifact", {
        "client_id": enrolled_client_id,
        "artifacts": ["Generic.Client.Info"]
    })

    # Validate response structure only
    assert result is not None
    assert len(result) > 0

    content = json.loads(result[0].text)
    assert "flow_id" in content  # Tool returned flow_id
    # Don't wait for completion - that's integration testing
```

**Warning signs:**
- Smoke tests use wait_for_flow_completion or polling
- Smoke tests take >5 seconds per tool
- Smoke tests fail intermittently due to timeouts
- pytest -m smoke takes >60 seconds total

**Phase impact:** Establish clear smoke/integration test boundary in Phase 2. Retrofitting after implementation leads to slow CI pipelines.

**Source:** [API smoke testing best practices](https://blog.qasource.com/a-complete-guide-to-smoke-testing-in-software-qa), [smoke testing definition](https://apidog.com/blog/api-testing-method-smoke-tests/)

### Pitfall 2: Hardcoding Test Client IDs

**What goes wrong:** Tests use hardcoded client IDs like "C.1234567890abcdef" that don't exist in test environment, causing all tests to fail.

**Why it happens:**
- Copying client IDs from development environment
- Not using enrolled_client_id fixture
- Assumption that test client has predictable ID
- Tests written before test infrastructure is running

**Consequences:**
- All client-dependent tests fail with "Client not found"
- Tests pass in one environment but fail in another
- False negatives masking real issues
- Cannot run tests on fresh test infrastructure

**How to avoid:**
```python
# BAD - Hardcoded client ID
@pytest.mark.smoke
async def test_get_client_info_smoke():
    server = create_server()
    result = await server.call_tool("get_client_info", {
        "client_id": "C.1234567890abcdef"  # WRONG - doesn't exist
    })

# GOOD - Use enrolled_client_id fixture
@pytest.mark.smoke
async def test_get_client_info_smoke(enrolled_client_id):
    server = create_server()
    result = await server.call_tool("get_client_info", {
        "client_id": enrolled_client_id  # Correct - dynamically discovered
    })

# ALTERNATIVE - Use placeholder replacement pattern
TOOL_SMOKE_INPUTS = [
    ("get_client_info", {"client_id": "C.test"}),  # Placeholder
]

@pytest.mark.parametrize("tool_name,inputs", TOOL_SMOKE_INPUTS)
async def test_tool_smoke(tool_name, inputs, enrolled_client_id):
    # Replace placeholders before invocation
    if "client_id" in inputs and inputs["client_id"] == "C.test":
        inputs["client_id"] = enrolled_client_id

    result = await server.call_tool(tool_name, inputs)
```

**Warning signs:**
- All client-dependent tests fail on CI but pass locally
- Error messages: "Client C.1234... not found"
- Tests fail after container restart
- Need to update test code when test environment changes

**Phase impact:** Use enrolled_client_id fixture from Phase 1. Don't hardcode any Velociraptor entity IDs.

**Source:** Phase 1 research on fixture patterns, existing conftest.py enrolled_client_id fixture

### Pitfall 3: Schema Validation Too Strict

**What goes wrong:** JSON schemas require all possible fields, causing tests to fail when Velociraptor returns optional fields or adds new fields in updates.

**Why it happens:**
- Copying complete response structure into schema
- Using "additionalProperties": false
- Not distinguishing required vs optional fields
- Schema created from single response example

**Consequences:**
- Tests fail when Velociraptor adds new fields (brittle)
- Tests fail when optional fields are absent
- Schema becomes maintenance burden
- False positives masking real issues

**How to avoid:**
```python
# BAD - Schema too strict
LIST_CLIENTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": [
            "client_id", "hostname", "os", "release",
            "labels", "last_seen_at", "first_seen_at", "last_ip"  # TOO MANY
        ],
        "additionalProperties": False  # WRONG - breaks on new fields
    }
}

# GOOD - Schema validates only critical fields
LIST_CLIENTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["client_id", "hostname"],  # Only critical fields
        "properties": {
            "client_id": {"type": "string", "pattern": "^C\\."},
            "hostname": {"type": "string"},
            "os": {"type": "string"},  # Optional - no error if missing
            "labels": {"type": "array", "items": {"type": "string"}}
        }
        # No additionalProperties constraint - allows new fields
    }
}
```

**Warning signs:**
- Schema validation failures mention "additional properties"
- Tests fail after Velociraptor version upgrade
- Schema has 20+ required fields
- Schema validation errors reference obscure nested fields

**Phase impact:** Keep schemas minimal in Phase 2. Only validate fields AI assistants actually need to parse.

**Source:** [JSON Schema validation best practices](https://python-jsonschema.readthedocs.io/en/stable/validate/), [API response validation patterns](https://www.qabash.com/practical-json-patterns-api-to-assertions-in-pytest/)

### Pitfall 4: MCP Server Instance Reuse

**What goes wrong:** Tests reuse a single MCP server instance across all tests, causing state pollution when tools have side effects or maintain internal state.

**Why it happens:**
- Performance optimization attempt (avoid creating server per test)
- Copying session-scoped fixture patterns from VelociraptorClient
- Assumption that MCP server is stateless
- Module-scoped server fixture

**Consequences:**
- Tests pass when run individually but fail when run together
- Order-dependent test failures
- Tool invocation counts or state leak between tests
- Cannot isolate test failures

**How to avoid:**
```python
# BAD - Module-scoped server (state pollution)
@pytest.fixture(scope="module")
def mcp_server():
    server = create_server()
    yield server
    # State persists across all tests in module

# GOOD - Function-scoped server (clean state per test)
@pytest.fixture(scope="function")
def mcp_server():
    """Create fresh MCP server for each test."""
    server = create_server()
    yield server
    # New server instance per test

# ALTERNATIVE - Explicitly reset state if server supports it
@pytest.fixture(scope="module")
def mcp_server():
    server = create_server()
    yield server

@pytest.fixture(autouse=True)
def reset_server_state(mcp_server):
    """Reset server state before each test."""
    yield  # Test runs
    # Reset any accumulated state
    mcp_server.reset()  # If such method exists
```

**Warning signs:**
- Tests pass in isolation but fail in suite
- First test passes, subsequent tests fail
- Test results depend on execution order
- pytest -k test_specific_tool passes, pytest -m smoke fails

**Phase impact:** Determine server lifecycle strategy in Phase 2. Document if server can be reused or must be per-test.

**Source:** [pytest fixture scopes](https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session), MCP server patterns

### Pitfall 5: Not Testing Error Conditions

**What goes wrong:** Smoke tests only test happy path (valid inputs), never test how tools handle invalid inputs, missing parameters, or non-existent entities.

**Why it happens:**
- Smoke tests focus on "does it work" not "does it fail gracefully"
- Assumption that error handling is tested elsewhere
- No negative test cases in parametrization
- Desire to keep smoke tests simple

**Consequences:**
- Tools crash on invalid input instead of returning error responses
- Unhelpful error messages to AI assistants
- No validation that error responses are JSON-formatted
- Production failures from edge cases

**How to avoid:**
```python
# GOOD - Include negative test cases in smoke tests
TOOL_SMOKE_INPUTS = [
    # Happy path
    ("list_clients", {"limit": 10}, False),

    # Error cases
    ("get_client_info", {"client_id": "C.nonexistent"}, True),
    ("collect_artifact", {"client_id": "C.test", "artifacts": ["NonExistent.Artifact"]}, True),
    ("modify_hunt", {"hunt_id": "H.nonexistent", "state": "PAUSED"}, True),
]

@pytest.mark.parametrize("tool_name,inputs,expect_error", TOOL_SMOKE_INPUTS)
async def test_tool_smoke(tool_name, inputs, expect_error, enrolled_client_id):
    # Replace placeholders
    if "client_id" in inputs and inputs["client_id"] == "C.test":
        inputs["client_id"] = enrolled_client_id

    result = await server.call_tool(tool_name, inputs)

    # Parse response
    content = json.loads(result[0].text)

    if expect_error:
        # Should return error in JSON, not raise exception
        with check: assert "error" in content, \
            f"{tool_name} should return error for invalid input"
        with check: assert isinstance(content["error"], str), \
            f"{tool_name} error should be a string"
    else:
        # Should not return error
        with check: assert "error" not in content or content["error"] is None, \
            f"{tool_name} returned unexpected error: {content.get('error')}"
```

**Warning signs:**
- All smoke tests use valid inputs only
- No tests verify error message format
- Tools raise exceptions instead of returning error JSON
- Error responses are not JSON-formatted

**Phase impact:** Add negative test cases in Phase 2. Verify error responses are JSON and helpful to AI assistants.

**Source:** [MCP error handling best practices](https://modelcontextprotocol.info/docs/best-practices/), API testing error scenarios

## Code Examples

Verified patterns from official sources:

### Example 1: Parametrized Smoke Test Suite
```python
# tests/integration/test_smoke_mcp_tools.py
"""Smoke tests for all 35 MCP tools.

These tests verify basic operability:
- Tool is callable
- Tool returns non-error response
- Response is valid JSON
- Response structure matches schema
"""

import pytest
import json
from pytest_check import check
from jsonschema import validate, ValidationError

from megaraptor_mcp.server import create_server
from tests.integration.schemas import get_tool_schema


# Define minimal valid inputs for each of 35 tools
TOOL_SMOKE_INPUTS = [
    # Client management tools (4 tools)
    ("list_clients", {"limit": 10}),
    ("get_client_info", {"client_id": "C.placeholder"}),
    ("label_client", {
        "client_id": "C.placeholder",
        "labels": ["TEST-smoke"],
        "operation": "add"
    }),
    ("quarantine_client", {"client_id": "C.placeholder", "quarantine": True}),

    # Artifact tools (3 tools)
    ("list_artifacts", {"limit": 10}),
    ("get_artifact", {"artifact_name": "Generic.Client.Info"}),
    ("collect_artifact", {
        "client_id": "C.placeholder",
        "artifacts": ["Generic.Client.Info"]
    }),

    # Hunt tools (4 tools)
    ("create_hunt", {
        "artifacts": ["Generic.Client.Info"],
        "description": "TEST-smoke-hunt"
    }),
    ("list_hunts", {"limit": 10}),
    ("get_hunt_results", {"hunt_id": "H.placeholder"}),
    ("modify_hunt", {"hunt_id": "H.placeholder", "state": "PAUSED"}),

    # Flow tools (4 tools)
    ("list_flows", {"client_id": "C.placeholder", "limit": 10}),
    ("get_flow_results", {
        "client_id": "C.placeholder",
        "flow_id": "F.placeholder"
    }),
    ("get_flow_status", {
        "client_id": "C.placeholder",
        "flow_id": "F.placeholder"
    }),
    ("cancel_flow", {
        "client_id": "C.placeholder",
        "flow_id": "F.placeholder"
    }),

    # VQL tools (2 tools)
    ("run_vql", {"query": "SELECT * FROM info()"}),
    ("vql_help", {"topic": "SELECT"}),

    # Deployment tools (18 tools - examples shown)
    ("deploy_server_docker", {
        "deployment_name": "TEST-smoke-docker",
        "platform": "linux"
    }),
    ("list_deployments", {}),
    ("get_deployment_status", {"deployment_id": "DEP.placeholder"}),
    # ... 15 more deployment tools
]


@pytest.mark.smoke
@pytest.mark.parametrize("tool_name,inputs", TOOL_SMOKE_INPUTS)
async def test_mcp_tool_callable(
    tool_name: str,
    inputs: dict,
    enrolled_client_id: str
):
    """Smoke test: MCP tool is callable and returns valid structure.

    Validates SMOKE-01: All 35 MCP tools are callable and return non-error responses.
    """
    server = create_server()

    # Replace placeholders with actual test IDs
    inputs = _replace_placeholders(inputs, enrolled_client_id)

    # Invoke tool via MCP protocol
    try:
        result = await server.call_tool(tool_name, inputs)
    except Exception as e:
        pytest.fail(f"Tool '{tool_name}' raised exception: {e}")

    # Validate response structure
    with check: assert result is not None, f"{tool_name}: returned None"
    with check: assert len(result) > 0, f"{tool_name}: returned empty list"

    # First element should be TextContent
    content = result[0]
    with check: assert hasattr(content, 'type'), f"{tool_name}: missing 'type' attribute"
    with check: assert content.type == "text", \
        f"{tool_name}: returned type='{content.type}', expected 'text'"

    # Parse JSON response
    try:
        response_data = json.loads(content.text)
    except json.JSONDecodeError as e:
        pytest.fail(f"{tool_name}: returned invalid JSON: {e}")

    # Validate against schema if defined
    schema = get_tool_schema(tool_name)
    if schema:
        try:
            validate(instance=response_data, schema=schema)
        except ValidationError as e:
            pytest.fail(f"{tool_name}: schema validation failed: {e.message}")

    # Check for error responses
    if isinstance(response_data, dict):
        with check: assert "error" not in response_data or response_data["error"] is None, \
            f"{tool_name}: returned error: {response_data.get('error')}"


def _replace_placeholders(inputs: dict, client_id: str) -> dict:
    """Replace placeholder IDs with real test IDs."""
    result = inputs.copy()

    if "client_id" in result and result["client_id"] == "C.placeholder":
        result["client_id"] = client_id

    # Other placeholders can remain - tools should handle gracefully
    return result
```

**Source:** [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html), Phase 2 SMOKE-01 requirement

### Example 2: Schema Validation Helper
```python
# tests/integration/schemas/__init__.py
"""JSON schema registry for MCP tool output validation.

Schemas validate only critical fields that AI assistants need to parse.
Keep schemas minimal - only require fields that MUST be present.
"""

from typing import Optional
from .client_schemas import (
    LIST_CLIENTS_SCHEMA,
    GET_CLIENT_INFO_SCHEMA,
    LABEL_CLIENT_SCHEMA,
    QUARANTINE_CLIENT_SCHEMA
)
from .artifact_schemas import (
    LIST_ARTIFACTS_SCHEMA,
    GET_ARTIFACT_SCHEMA,
    COLLECT_ARTIFACT_SCHEMA
)
from .vql_schemas import RUN_VQL_SCHEMA, VQL_HELP_SCHEMA
from .hunt_schemas import (
    CREATE_HUNT_SCHEMA,
    LIST_HUNTS_SCHEMA,
    GET_HUNT_RESULTS_SCHEMA,
    MODIFY_HUNT_SCHEMA
)
from .flow_schemas import (
    LIST_FLOWS_SCHEMA,
    GET_FLOW_RESULTS_SCHEMA,
    GET_FLOW_STATUS_SCHEMA,
    CANCEL_FLOW_SCHEMA
)
from .deployment_schemas import (
    DEPLOY_SERVER_SCHEMA,
    LIST_DEPLOYMENTS_SCHEMA,
    # ... 16 more deployment schemas
)


# Registry of all tool schemas
_SCHEMA_REGISTRY = {
    # Client tools
    "list_clients": LIST_CLIENTS_SCHEMA,
    "get_client_info": GET_CLIENT_INFO_SCHEMA,
    "label_client": LABEL_CLIENT_SCHEMA,
    "quarantine_client": QUARANTINE_CLIENT_SCHEMA,

    # Artifact tools
    "list_artifacts": LIST_ARTIFACTS_SCHEMA,
    "get_artifact": GET_ARTIFACT_SCHEMA,
    "collect_artifact": COLLECT_ARTIFACT_SCHEMA,

    # Hunt tools
    "create_hunt": CREATE_HUNT_SCHEMA,
    "list_hunts": LIST_HUNTS_SCHEMA,
    "get_hunt_results": GET_HUNT_RESULTS_SCHEMA,
    "modify_hunt": MODIFY_HUNT_SCHEMA,

    # Flow tools
    "list_flows": LIST_FLOWS_SCHEMA,
    "get_flow_results": GET_FLOW_RESULTS_SCHEMA,
    "get_flow_status": GET_FLOW_STATUS_SCHEMA,
    "cancel_flow": CANCEL_FLOW_SCHEMA,

    # VQL tools
    "run_vql": RUN_VQL_SCHEMA,
    "vql_help": VQL_HELP_SCHEMA,

    # Deployment tools (18 total)
    "deploy_server_docker": DEPLOY_SERVER_SCHEMA,
    "list_deployments": LIST_DEPLOYMENTS_SCHEMA,
    # ... 16 more
}


def get_tool_schema(tool_name: str) -> Optional[dict]:
    """Get JSON schema for a tool's output.

    Returns None if no schema defined for tool (validation skipped).
    """
    return _SCHEMA_REGISTRY.get(tool_name)


def validate_tool_output(tool_name: str, output: dict) -> None:
    """Validate tool output against its schema.

    Raises:
        ValidationError: If output doesn't match schema
        ValueError: If output is not a dict
    """
    from jsonschema import validate, ValidationError

    if not isinstance(output, dict):
        raise ValueError(f"Tool output must be dict, got {type(output)}")

    schema = get_tool_schema(tool_name)
    if schema is None:
        # No schema defined - skip validation
        return

    validate(instance=output, schema=schema)
```

**Source:** [JSON Schema best practices](https://python-jsonschema.readthedocs.io/en/stable/validate/), schema organization patterns

### Example 3: Generic.Client.Info Artifact Smoke Test
```python
# tests/integration/test_smoke_mcp_tools.py

@pytest.mark.smoke
def test_generic_client_info_artifact(
    velociraptor_client,
    enrolled_client_id
):
    """Smoke test: Generic.Client.Info artifact collection.

    Validates SMOKE-02: Generic.Client.Info artifact collection works
    against live container and returns valid client metadata.
    """
    from tests.integration.helpers.wait_helpers import wait_for_flow_completion
    from pytest_check import check

    # Collect artifact
    vql = f"""
    SELECT collect_client(
        client_id='{enrolled_client_id}',
        artifacts=['Generic.Client.Info'],
        timeout=60
    ) AS collection
    FROM scope()
    """

    result = velociraptor_client.query(vql)

    # Validate flow was created
    with check: assert len(result) > 0, "collect_client returned no results"
    with check: assert "collection" in result[0], "Missing 'collection' field"

    collection = result[0]["collection"]
    with check: assert "flow_id" in collection, "Missing 'flow_id' in collection"

    flow_id = collection["flow_id"]

    # Wait for flow completion (this is acceptable for artifact smoke test)
    try:
        wait_for_flow_completion(
            velociraptor_client,
            enrolled_client_id,
            flow_id,
            timeout=30
        )
    except TimeoutError:
        pytest.fail("Generic.Client.Info collection did not complete in 30s")

    # Get flow results
    results_vql = f"""
    SELECT * FROM source(
        client_id='{enrolled_client_id}',
        flow_id='{flow_id}',
        artifact='Generic.Client.Info'
    )
    """
    results = velociraptor_client.query(results_vql)

    # Validate expected structure
    with check: assert len(results) > 0, "Generic.Client.Info returned no results"

    if results:
        info = results[0]

        # Check critical fields that AI assistants need
        with check: assert "Hostname" in info, "Missing 'Hostname' field"
        with check: assert "OS" in info, "Missing 'OS' field"
        with check: assert "ClientId" in info, "Missing 'ClientId' field"

        # Validate field values
        if "Hostname" in info:
            with check: assert isinstance(info["Hostname"], str), \
                "Hostname should be string"
            with check: assert len(info["Hostname"]) > 0, "Hostname is empty"

        if "ClientId" in info:
            with check: assert info["ClientId"] == enrolled_client_id, \
                f"ClientId mismatch: {info['ClientId']} != {enrolled_client_id}"
```

**Source:** Phase 2 SMOKE-02 requirement, [pytest-check usage](https://pypi.org/project/pytest-check/)

### Example 4: Generic.System.Pslist Smoke Test
```python
# tests/integration/test_smoke_mcp_tools.py

@pytest.mark.smoke
def test_generic_system_pslist_artifact(
    velociraptor_client,
    enrolled_client_id
):
    """Smoke test: Generic.System.Pslist artifact collection.

    Validates SMOKE-03: Generic.System.Pslist returns valid process list
    structure (PID, name, command line).
    """
    from tests.integration.helpers.wait_helpers import wait_for_flow_completion
    from pytest_check import check

    # Collect artifact
    vql = f"""
    SELECT collect_client(
        client_id='{enrolled_client_id}',
        artifacts=['Generic.System.Pslist'],
        timeout=60
    ) AS collection
    FROM scope()
    """

    result = velociraptor_client.query(vql)
    flow_id = result[0]["collection"]["flow_id"]

    # Wait for completion
    wait_for_flow_completion(
        velociraptor_client,
        enrolled_client_id,
        flow_id,
        timeout=30
    )

    # Get results
    results_vql = f"""
    SELECT * FROM source(
        client_id='{enrolled_client_id}',
        flow_id='{flow_id}',
        artifact='Generic.System.Pslist'
    )
    """
    results = velociraptor_client.query(results_vql)

    # Validate process list structure
    with check: assert len(results) > 0, "Pslist returned no processes"

    if results:
        # Check first process entry
        process = results[0]

        # Expected fields for process list (SMOKE-03)
        with check: assert "Pid" in process or "PID" in process, \
            "Missing PID field"
        with check: assert "Name" in process or "name" in process, \
            "Missing process name field"
        with check: assert "CommandLine" in process or "command_line" in process or "Cmdline" in process, \
            "Missing command line field"

        # Validate PID is numeric
        pid_field = next((f for f in ["Pid", "PID", "pid"] if f in process), None)
        if pid_field:
            with check: assert isinstance(process[pid_field], (int, str)), \
                f"PID should be int or string, got {type(process[pid_field])}"

        # Validate name is string
        name_field = next((f for f in ["Name", "name"] if f in process), None)
        if name_field:
            with check: assert isinstance(process[name_field], str), \
                f"Process name should be string, got {type(process[name_field])}"
```

**Source:** Phase 2 SMOKE-03 requirement, VQL process list structure

### Example 5: VQL Query Execution Smoke Test
```python
# tests/integration/test_smoke_vql.py
"""Smoke tests for VQL query execution.

Validates SMOKE-04: Basic VQL queries execute without syntax errors
and return results.
"""

import pytest
from pytest_check import check

# Basic VQL queries that should work on any Velociraptor server
SMOKE_VQL_QUERIES = [
    ("server_info", "SELECT * FROM info()"),
    ("clients_list", "SELECT client_id, hostname FROM clients() LIMIT 5"),
    ("artifacts_list", "SELECT name, type FROM artifact_definitions() LIMIT 10"),
    ("hunts_list", "SELECT hunt_id, state FROM hunts() LIMIT 5"),
    ("flows_list", "SELECT * FROM flows() LIMIT 5"),
]


@pytest.mark.smoke
@pytest.mark.parametrize("query_name,vql", SMOKE_VQL_QUERIES)
def test_vql_execution_smoke(
    query_name: str,
    vql: str,
    velociraptor_client
):
    """Smoke test: VQL query executes without syntax errors.

    Validates SMOKE-04: Basic VQL queries execute without syntax errors.
    """
    # Execute VQL query
    try:
        result = velociraptor_client.query(vql)
    except Exception as e:
        pytest.fail(f"VQL query '{query_name}' raised exception: {e}")

    # Validate result structure
    with check: assert result is not None, \
        f"VQL '{query_name}' returned None"
    with check: assert isinstance(result, list), \
        f"VQL '{query_name}' returned {type(result).__name__}, expected list"

    # Empty list is valid (no syntax error, just no matching data)
    # Don't assert len(result) > 0 - that's functional testing
```

**Source:** Phase 2 SMOKE-04 requirement, [Velociraptor VQL fundamentals](https://docs.velociraptor.app/docs/vql/fundamentals/)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Individual test per tool | pytest.mark.parametrize with tool list | pytest 3.0+ (2017) | 35 test functions → 1 parametrized test. Easier to add new tools, consistent validation. |
| Manual JSON field checking | jsonschema validation | jsonschema 4.0+ (2021) | Formal contract validation. Catches structure changes. Self-documenting schemas. |
| Stop at first assertion failure | pytest-check with multiple checks | pytest-check 2.0+ (2023) | See all field failures in smoke test. Complete validation picture. |
| MCP Inspector manual testing | Automated smoke tests in CI | MCP v1.0 (2024) | Manual testing doesn't scale to 35 tools. Automated smoke tests run on every commit. |
| Assert all fields present | Minimal schema with only required fields | 2025+ best practice | Schemas don't break on Velociraptor updates that add new fields. Tolerant validation. |

**Deprecated/outdated:**
- pytest-jsonschema (unmaintained since 2020): Use core jsonschema library instead
- pytest-soft-assertions (unmaintained since 2020): Use pytest-check instead
- Individual smoke test functions: Use parametrization for 35 tools

## Open Questions

Things that couldn't be fully resolved:

1. **How should we invoke MCP tools in tests?**
   - What we know: MCP server has create_server() that returns Server instance
   - What's unclear: Whether server.call_tool() is the correct method or if there's a test client API
   - Recommendation: Research MCP Python SDK test patterns. Start with server.call_tool() approach from MCP Inspector patterns. If that doesn't work, create a test helper that wraps tool invocation.

2. **What's the correct format for velociraptor:// resource URIs?**
   - What we know: Resources exist for clients, hunts, artifacts (from README.md)
   - What's unclear: Exact URI format and how to invoke via MCP server
   - Recommendation: Check src/megaraptor_mcp/resources.py (exists but not read). Document URI patterns from implementation. Test with server.read_resource() method.

3. **Should we test MCP prompts in smoke tests?**
   - What we know: 8 prompts exist (from README.md)
   - What's unclear: Whether prompts need smoke testing or are just templates
   - Recommendation: Phase 2 includes prompt smoke tests (similar to resource tests). Verify prompt is retrievable and returns valid template structure.

4. **How deep should artifact collection smoke tests go?**
   - What we know: SMOKE-02 and SMOKE-03 require actual artifact collection
   - What's unclear: Whether to wait for completion or just verify collection starts
   - Recommendation: Wait for completion for SMOKE-02 and SMOKE-03 only. Other artifact tests just verify collection starts (returns flow_id). Document as exception to "smoke tests don't wait" rule.

5. **What's the correct way to get an enrolled client ID dynamically?**
   - What we know: enrolled_client_id fixture exists in conftest.py
   - What's unclear: Whether this fixture will work for smoke tests or needs enhancement
   - Recommendation: Use existing enrolled_client_id fixture. If it doesn't work, enhance wait_for_client_enrollment helper to be more robust.

## Sources

### Primary (HIGH confidence)
- [pytest parametrization documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) - Official pytest parametrization patterns
- [pytest-check PyPI](https://pypi.org/project/pytest-check/) - Multiple assertions per test
- [jsonschema documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/) - JSON Schema validation
- [MCP Inspector documentation](https://modelcontextprotocol.io/docs/tools/inspector) - MCP testing tool and patterns
- [Velociraptor VQL fundamentals](https://docs.velociraptor.app/docs/vql/fundamentals/) - VQL query patterns
- Project README.md (C:\Users\Meow\Documents\Projects\megaraptor-mcp\README.md) - 35 tools, resources, prompts
- Phase 1 RESEARCH.md - pytest-check, jsonschema already in project

### Secondary (MEDIUM confidence)
- [MCP server testing best practices](https://www.merge.dev/blog/mcp-server-testing) - MCP testing approaches
- [MCP best practices guide](https://modelcontextprotocol.info/docs/best-practices/) - Architecture and implementation
- [API smoke testing guide](https://apidog.com/blog/api-testing-method-smoke-tests/) - Smoke test definition
- [Smoke testing 2026 guide](https://blog.qasource.com/a-complete-guide-to-smoke-testing-in-software-qa) - 2026 trends
- [JSON patterns in pytest](https://www.qabash.com/practical-json-patterns-api-to-assertions-in-pytest/) - API assertion patterns
- [pytest-check delayed assertions](https://pythontest.com/strategy/delayed-assert/) - Multiple failure patterns
- [Velociraptor VQL JSON format](https://docs.velociraptor.app/vql_reference/) - VQL output structure

### Tertiary (LOW confidence - WebSearch only)
- [pytest smoke plugin](https://github.com/yugokato/pytest-smoke) - Community smoke test plugin (not using)
- [Integration testing with pytest](https://medium.com/@ujwalabothe/integration-testing-with-pytest-testing-real-world-scenarios-c506f4bf1bff) - General patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project (pytest-check, jsonschema), versions verified
- Parametrization patterns: HIGH - Official pytest documentation, widely used pattern
- JSON Schema validation: HIGH - Official jsonschema docs, clear validation approach
- MCP tool invocation: MEDIUM - MCP Inspector patterns documented but test invocation API not verified
- VQL output structure: MEDIUM - Velociraptor docs cover VQL but specific JSON schemas need validation
- Resource URI testing: LOW - Resources exist but exact URI format and invocation not verified

**Research date:** 2026-01-25
**Valid until:** 30 days (MCP is fast-moving, pytest is stable, Velociraptor is stable)

**Next phase considerations:**
- Phase 3 will need actual artifact collection validation beyond smoke tests
- Phase 4+ will extend to hunt operations requiring multi-client coordination
- Smoke test patterns established here will be template for future MCP server features
