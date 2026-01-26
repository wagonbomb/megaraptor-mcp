# Phase 4: OS-Specific Artifacts - Research

**Researched:** 2026-01-25
**Domain:** Velociraptor OS-specific artifact collection and validation
**Confidence:** HIGH

## Summary

Phase 4 implements OS-specific artifact collection with proper validation across Linux and Windows targets. Research identifies available artifacts, validation approaches, and testing strategies that work within current infrastructure constraints.

**Key findings:**
1. Linux artifacts (Linux.Sys.Users, Linux.Sys.Pslist) are well-documented with clear schemas and available for immediate testing against the existing Docker container
2. Windows artifacts (Windows.System.Services, Windows.Registry.UserAssist) are documented but require Windows targets - Docker containers require Windows hosts
3. Existing test infrastructure already supports capability-based target selection via TargetRegistry with OS-based capability inference
4. JSON Schema validation is already established in the codebase (jsonschema>=4.26.0) for output validation
5. pytest provides multiple patterns for conditional test skipping based on target availability

**Primary recommendation:** Implement Linux artifact tests immediately against existing container infrastructure. Add Windows artifact tests with pytest.skipif guards that activate when Windows targets become available (VM or Windows host). Use JSON Schema for artifact output validation following existing patterns.

## Standard Stack

### Core Artifacts

**Linux Artifacts (HIGH confidence - official docs verified):**

| Artifact | Purpose | Output Fields | Use Case |
|----------|---------|---------------|----------|
| Linux.Sys.Users | User account enumeration | User, Description, Uid, Gid, Homedir, Shell | User account auditing, compromise detection |
| Linux.Sys.Pslist | Process enumeration | Pid, Name, Cmdline, Exe | Running process inventory (already tested in Phase 2) |
| Linux.Sys.Services | Service enumeration | Service details | Persistence detection |

**Windows Artifacts (HIGH confidence - official docs verified):**

| Artifact | Purpose | Output Fields | Use Case |
|----------|---------|---------------|----------|
| Windows.System.Services | Service enumeration | Name, DisplayName, State, PathName, ServiceDll, AbsoluteExePath | Service-based persistence detection |
| Windows.Registry.UserAssist | User program execution history | _KeyPath, Name, User, LastExecution, NumberOfExecutions | User activity forensics, lateral movement detection |

### Validation Libraries

**Already in codebase:**
- `jsonschema>=4.26.0` - JSON Schema validation (used in tests/integration/schemas/)
- Pattern: Minimal schemas validating only critical fields to avoid version brittleness

**Not needed:**
- Pydantic (5-50x faster, but unnecessary - artifact validation is not a performance bottleneck)
- Marshmallow (adds complexity without benefit for simple field validation)

### Test Infrastructure

**Already available:**
- `pytest.mark.skipif` - Conditional test skipping based on platform or target availability
- `pytest.param()` with marks - Per-parameter conditional skipping
- `TargetRegistry` - Capability-based test target selection (tests/integration/helpers/target_registry.py)
- Module-scoped fixtures for target discovery

## Architecture Patterns

### Pattern 1: Capability-Based Target Selection

**What:** Use TargetRegistry to select appropriate test targets based on OS and capabilities.

**Current implementation:**
```python
# From tests/integration/helpers/target_registry.py
class TargetRegistry:
    LINUX_CAPABILITIES = [
        "generic_artifacts",
        "linux_filesystem",
        "linux_processes",
        "linux_users",
        "linux_network",
    ]

    WINDOWS_CAPABILITIES = [
        "generic_artifacts",
        "windows_registry",
        "windows_prefetch",
        "windows_eventlog",
        "windows_filesystem",
        "windows_processes",
    ]

    def get_by_capability(self, capability: str) -> Optional[TestTarget]:
        """Get first target with specified capability."""

    def get_by_os(self, os_type: str) -> Optional[TestTarget]:
        """Get first target with specified OS type."""
```

**Enhancement needed:** Add OS-specific capability mapping:
- `linux_users` → Linux.Sys.Users artifact support
- `windows_registry` → Windows.Registry.* artifact support
- `windows_services` → Windows.System.Services artifact support

### Pattern 2: Conditional Test Execution

**What:** Skip tests when required OS target is unavailable, but run when available.

**Pattern A - Skip entire test:**
```python
@pytest.mark.skipif(
    not has_windows_target(),
    reason="Windows target required for registry artifacts"
)
def test_windows_registry_userassist(target_registry, velociraptor_client):
    """Test Windows.Registry.UserAssist artifact collection."""
    target = target_registry.get_by_capability("windows_registry")
    # Test implementation
```

**Pattern B - Parametrized with conditional skip:**
```python
@pytest.mark.parametrize("artifact,os_type,capability,expected_fields", [
    ("Linux.Sys.Users", "linux", "linux_users",
     ["User", "Uid", "Gid", "Homedir"]),
    pytest.param(
        "Windows.System.Services", "windows", "windows_services",
        ["Name", "State", "PathName"],
        marks=pytest.mark.skipif(
            lambda: not has_capability("windows_services"),
            reason="Windows target not available"
        )
    ),
])
def test_os_artifact_collection(artifact, os_type, capability, expected_fields):
    """Test OS-specific artifact collection."""
    # Implementation
```

**Pattern C - Module-level skip:**
```python
# test_windows_artifacts.py
import pytest
import sys

# Get fixture to check target availability
@pytest.fixture(scope="module")
def require_windows_target(target_registry):
    if not target_registry.get_by_os("windows"):
        pytest.skip("No Windows targets available", allow_module_level=True)

class TestWindowsArtifacts:
    """Windows-specific artifact tests (skipped if no Windows target)."""
    # All tests in this class require Windows target
```

### Pattern 3: OS-Specific Artifact Schemas

**What:** Define minimal JSON schemas for OS-specific artifact output validation.

**Implementation approach:**
```python
# tests/integration/schemas/os_artifacts.py
LINUX_SYS_USERS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["User", "Uid", "Gid"],  # Critical fields
        "properties": {
            "User": {"type": "string"},
            "Uid": {"type": ["string", "integer"]},  # May be string or int
            "Gid": {"type": ["string", "integer"]},
            "Homedir": {"type": "string"},
            "Shell": {"type": "string"},
            # No additionalProperties: false - allow version differences
        }
    }
}

WINDOWS_SYSTEM_SERVICES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["Name"],  # Only require most critical field
        "properties": {
            "Name": {"type": "string"},
            "DisplayName": {"type": "string"},
            "State": {"type": "string"},
            "PathName": {"type": "string"},
            "ServiceDll": {"type": "string"},
            "AbsoluteExePath": {"type": "string"},
        }
    }
}
```

**Key principle:** Validate only critical fields. Allow optional fields to be missing. No `additionalProperties: false` to avoid version brittleness.

**Source:** Established pattern from tests/integration/schemas/base_schemas.py

### Pattern 4: Flexible Field Name Matching

**What:** Support multiple field name variations across Velociraptor versions.

**Already established in Phase 2:**
```python
# From test_smoke_artifacts.py
# Check critical fields that AI assistants need
# Field names may vary by Velociraptor version
hostname_found = any(k in info for k in ["Hostname", "hostname", "Fqdn"])
os_found = any(k in info for k in ["OS", "os", "System", "Platform"])

with check:
    assert hostname_found, \
        f"Missing hostname field. Available: {list(info.keys())}"
```

**Apply to OS-specific artifacts:** Use same flexible matching for User/user, Uid/uid, etc.

## Don't Hand-Roll

Problems that have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Windows container testing on Linux hosts | Custom Windows emulation | pytest.skipif + VM/Windows host fallback | Windows containers require Windows kernel - architectural limitation, not solvable |
| Artifact schema validation | Custom validator classes | JSON Schema (jsonschema library) | Already in project dependencies, well-tested, standard format |
| OS detection in tests | Parse /etc/os-release or registry | TargetRegistry.get_by_os() | Already implemented, session-scoped discovery |
| Complex Velociraptor setup | New test infrastructure | Existing Docker container + target_registry | Phase 1-2 infrastructure already working |
| Target capability checking | Manual OS checks per test | TargetRegistry capability inference | Centralized capability management |

**Key insight:** Test infrastructure from Phases 1-2 already handles multi-OS scenarios through capability-based targeting. The pattern is proven (75 smoke tests passing). Don't rebuild - extend.

## Common Pitfalls

### Pitfall 1: Windows Container Assumption

**What goes wrong:** Assuming Windows containers can run on Linux Docker hosts like Linux containers run on Windows hosts (WSL2).

**Why it happens:** Docker Desktop on Windows can run Linux containers via WSL2, creating false assumption of symmetry.

**Reality:** Windows containers require Windows kernel. From official Microsoft docs: "Docker containers typically share the same underlying kernel as the host operating system. This means while Linux containers can run on both Linux and Windows hosts, the reverse is not true. You can't run Windows containers on a Linux host."

**Host requirements:**
- Windows 10/11 Professional or Enterprise (Home edition cannot run Windows containers)
- Host OS version must match container OS version (ltsc2025 requires Windows Server 2025 host)
- Hyper-V role required for isolation mode

**How to avoid:**
1. Accept Linux-only testing in CI/CD on Linux hosts
2. Use pytest.skipif to skip Windows tests when no Windows target available
3. Document Windows testing requirements (VM or Windows host)
4. Consider VM-based Windows target (VirtualBox/Vagrant) for local testing

**Warning signs:**
- Docker pull succeeds but container fails to start with "image operating system mismatch" error
- Tests expecting Windows target fail immediately in Linux CI

**Source:** [Microsoft Windows Container Requirements](https://learn.microsoft.com/en-us/virtualization/windowscontainers/deploy-containers/system-requirements)

### Pitfall 2: Over-Strict Artifact Schemas

**What goes wrong:** JSON schemas with `required: ["all", "fields"]` and `additionalProperties: false` cause tests to fail across Velociraptor versions.

**Why it happens:** Velociraptor artifact schemas evolve. Version 0.72 might have field "ProcessId" while 0.75 has "Pid". New versions add fields.

**Example breakage:**
```python
# BAD: Breaks when field names change or new fields added
STRICT_SCHEMA = {
    "required": ["ProcessId", "Name", "CommandLine"],  # 0.72 field names
    "additionalProperties": false  # Breaks when 0.75 adds new fields
}

# GOOD: Resilient to version changes
FLEXIBLE_SCHEMA = {
    "required": ["Name"],  # Only most critical field
    "properties": {
        "Pid": {"type": ["integer", "string"]},  # Accept multiple types
        "Name": {"type": "string"},
    }
    # No additionalProperties restriction
}
```

**How to avoid:**
1. Require only the most critical 1-2 fields
2. Never use `additionalProperties: false`
3. Accept multiple types for numeric fields (may be int or string)
4. Use flexible field name matching for critical checks
5. Test against actual Velociraptor output, not documentation assumptions

**Established decision (Phase 2):** "Keep schemas minimal - only validate critical fields to avoid brittleness"

**Source:** .planning/STATE.md, tests/integration/schemas/base_schemas.py comments

### Pitfall 3: Assuming Generic Artifacts Exist

**What goes wrong:** Tests use "Generic.System.Pslist" or similar artifacts that don't exist in Velociraptor standard distribution.

**Why it happens:** Logical naming assumption - if Linux.Sys.Pslist and Windows.System.Pslist exist, surely Generic.System.Pslist exists for cross-platform compatibility.

**Reality:** Velociraptor 0.75.x does not include Generic.System.Pslist. Each OS has specific artifacts:
- Linux: Linux.Sys.Pslist
- Windows: Windows.System.Pslist
- macOS: (would be MacOSX.System.Pslist or similar)

**How to avoid:**
1. Query available artifacts: `SELECT name FROM artifact_definitions()`
2. Use OS-specific artifacts based on target OS
3. Let TargetRegistry handle OS-specific artifact selection
4. Document artifact availability per Velociraptor version

**Established decision (Phase 2):** "Use Linux.Sys.Pslist for Linux containers (Generic.System.Pslist doesn't exist in 0.75.x)"

**Source:** .planning/STATE.md, tests/integration/test_smoke_artifacts.py

### Pitfall 4: Forgetting Artifact Source Parameters

**What goes wrong:** VQL queries like `source(artifact='Generic.Client.Info')` fail with "source not specified" errors.

**Why it happens:** Some artifacts have multiple sources (sub-components). The `source()` VQL function requires both artifact name AND source name.

**Example:**
```python
# BAD: Missing required source parameter
results_vql = f"""
SELECT * FROM source(
    client_id='{client_id}',
    flow_id='{flow_id}',
    artifact='Generic.Client.Info'
)
"""

# GOOD: Includes source parameter
results_vql = f"""
SELECT * FROM source(
    client_id='{client_id}',
    flow_id='{flow_id}',
    artifact='Generic.Client.Info',
    source='BasicInformation'
)
"""
```

**How to avoid:**
1. Check artifact definition for sources: `SELECT sources FROM artifact_definitions() WHERE name = 'Artifact.Name'`
2. For artifacts without sub-sources (like Linux.Sys.Pslist), omit source parameter
3. For artifacts with sources (like Generic.Client.Info), specify source parameter
4. Document required sources for tested artifacts

**Established decision (Phase 2):** "source() VQL requires artifact + source params, not just artifact name"

**Source:** .planning/STATE.md, tests/integration/test_smoke_artifacts.py

### Pitfall 5: Session vs Module Scope Confusion

**What goes wrong:** Creating module-scoped fixtures that depend on session-scoped fixtures causes "ScopeMismatch" errors or unexpected behavior.

**Why it happens:** pytest fixture scope hierarchy: session > module > function. Module fixtures execute multiple times across modules, but session fixtures execute once.

**Example from existing codebase:**
```python
# CORRECT: Both fixtures have same scope
@pytest.fixture(scope="module")
def target_registry(docker_compose_up, velociraptor_client):
    """Module-scoped - discovers targets once per module."""
    # Implementation

@pytest.fixture(scope="module")
def velociraptor_client(docker_compose_up, velociraptor_api_config):
    """Module-scoped client with lifecycle management."""
    # Implementation
```

**How to avoid:**
1. Use module scope for target_registry (already established in Phase 1)
2. Use module scope for OS-specific target fixtures
3. Don't create function-scoped fixtures that re-discover targets
4. Target discovery is expensive - do it once per module, not per test

**Established decision (Phase 2):** "Module scope for target_registry and enrolled_client_id fixtures"

**Source:** .planning/STATE.md, tests/conftest.py

## Code Examples

### Example 1: Linux.Sys.Users Collection and Validation

```python
# Source: Phase 4 research, verified against official docs
# https://docs.velociraptor.app/artifact_references/pages/linux.sys.users/

def test_linux_sys_users_collection(target_registry, velociraptor_client):
    """Test Linux.Sys.Users artifact collection and validation.

    Validates OSART-01: Linux.Sys.Users artifact collection works
    """
    # Get Linux target
    target = target_registry.get_by_capability("linux_users")
    if not target:
        pytest.skip("No Linux target available")

    # Schedule artifact collection
    vql = f"""
    SELECT collect_client(
        client_id='{target.client_id}',
        artifacts=['Linux.Sys.Users'],
        timeout=30
    ) AS collection
    FROM scope()
    """

    result = velociraptor_client.query(vql)
    flow_id = result[0]["collection"]["flow_id"]

    # Wait for completion
    wait_for_flow_completion(
        velociraptor_client,
        target.client_id,
        flow_id,
        timeout=30
    )

    # Get results
    results_vql = f"""
    SELECT * FROM source(
        client_id='{target.client_id}',
        flow_id='{flow_id}',
        artifact='Linux.Sys.Users'
    )
    """
    results = velociraptor_client.query(results_vql)

    # Validate schema
    from jsonschema import validate
    from tests.integration.schemas.os_artifacts import LINUX_SYS_USERS_SCHEMA

    validate(instance=results, schema=LINUX_SYS_USERS_SCHEMA)

    # Validate critical fields present
    assert len(results) > 0, "No users returned"
    user = results[0]

    # Flexible field matching (version-resilient)
    user_found = any(k in user for k in ["User", "user", "Username"])
    uid_found = any(k in user for k in ["Uid", "uid", "UID"])

    assert user_found, f"Missing user field. Available: {list(user.keys())}"
    assert uid_found, f"Missing UID field. Available: {list(user.keys())}"
```

### Example 2: Windows.System.Services with Conditional Skip

```python
# Source: Phase 4 research, verified against official docs
# https://docs.velociraptor.app/artifact_references/pages/windows.system.services/

@pytest.mark.skipif(
    lambda: not _has_windows_target(),
    reason="Windows target required for Windows.System.Services"
)
def test_windows_system_services_collection(target_registry, velociraptor_client):
    """Test Windows.System.Services artifact collection.

    Validates OSART-02: Windows.System.Services artifact collection works

    Note: Skipped if no Windows target available. Run with Windows VM or
    Windows host to enable.
    """
    # Get Windows target
    target = target_registry.get_by_capability("windows_services")
    if not target:
        pytest.skip("No Windows target with service capability")

    # Schedule artifact collection
    vql = f"""
    SELECT collect_client(
        client_id='{target.client_id}',
        artifacts=['Windows.System.Services'],
        timeout=30
    ) AS collection
    FROM scope()
    """

    result = velociraptor_client.query(vql)
    flow_id = result[0]["collection"]["flow_id"]

    # Wait for completion
    wait_for_flow_completion(
        velociraptor_client,
        target.client_id,
        flow_id,
        timeout=30
    )

    # Get results
    results_vql = f"""
    SELECT * FROM source(
        client_id='{target.client_id}',
        flow_id='{flow_id}',
        artifact='Windows.System.Services'
    )
    """
    results = velociraptor_client.query(results_vql)

    # Validate schema
    from jsonschema import validate
    from tests.integration.schemas.os_artifacts import WINDOWS_SYSTEM_SERVICES_SCHEMA

    validate(instance=results, schema=WINDOWS_SYSTEM_SERVICES_SCHEMA)

    # Validate critical fields
    assert len(results) > 0, "No services returned"
    service = results[0]

    assert "Name" in service, f"Missing Name field. Available: {list(service.keys())}"
    assert isinstance(service["Name"], str), "Service Name should be string"
```

### Example 3: Windows.Registry.UserAssist Validation

```python
# Source: Phase 4 research, verified against official docs
# https://docs.velociraptor.app/artifact_references/pages/windows.registry.userassist/

def test_windows_registry_userassist(target_registry, velociraptor_client):
    """Test Windows.Registry.UserAssist artifact collection.

    Validates OSART-03: Windows registry artifact validation works
    """
    # Get Windows target with registry capability
    target = target_registry.get_by_capability("windows_registry")
    if not target:
        pytest.skip("No Windows target with registry capability")

    # Schedule artifact collection
    vql = f"""
    SELECT collect_client(
        client_id='{target.client_id}',
        artifacts=['Windows.Registry.UserAssist'],
        timeout=30
    ) AS collection
    FROM scope()
    """

    result = velociraptor_client.query(vql)
    flow_id = result[0]["collection"]["flow_id"]

    # Wait for completion
    wait_for_flow_completion(
        velociraptor_client,
        target.client_id,
        flow_id,
        timeout=30
    )

    # Get results
    results_vql = f"""
    SELECT * FROM source(
        client_id='{target.client_id}',
        flow_id='{flow_id}',
        artifact='Windows.Registry.UserAssist'
    )
    """
    results = velociraptor_client.query(results_vql)

    # Validate schema (registry artifacts are more complex)
    from jsonschema import validate
    from tests.integration.schemas.os_artifacts import WINDOWS_REGISTRY_USERASSIST_SCHEMA

    validate(instance=results, schema=WINDOWS_REGISTRY_USERASSIST_SCHEMA)

    # Registry artifact may return empty results (no UserAssist data on system)
    # This is valid - UserAssist only tracks Explorer-launched programs
    if len(results) > 0:
        entry = results[0]

        # Validate ROT13-decoded names present
        assert "Name" in entry, "UserAssist should decode ROT13 names"
        assert "LastExecution" in entry, "UserAssist should parse timestamps"
        assert "NumberOfExecutions" in entry, "UserAssist should parse execution count"
```

### Example 4: Parametrized Multi-OS Artifact Tests

```python
# Source: pytest parametrize documentation + Phase 4 research

@pytest.mark.parametrize("artifact,os_type,capability,expected_fields,skip_condition", [
    # Linux artifacts - always available
    (
        "Linux.Sys.Users",
        "linux",
        "linux_users",
        ["User", "Uid", "Gid"],
        None  # No skip condition
    ),
    # Windows artifacts - conditional
    pytest.param(
        "Windows.System.Services",
        "windows",
        "windows_services",
        ["Name", "State"],
        marks=pytest.mark.skipif(
            not _has_windows_target(),
            reason="Windows target not available"
        )
    ),
    pytest.param(
        "Windows.Registry.UserAssist",
        "windows",
        "windows_registry",
        ["Name", "LastExecution"],
        marks=pytest.mark.skipif(
            not _has_windows_target(),
            reason="Windows target not available"
        )
    ),
])
def test_os_artifact_collection_parametrized(
    target_registry,
    velociraptor_client,
    artifact,
    os_type,
    capability,
    expected_fields
):
    """Parametrized test for OS-specific artifacts.

    Tests multiple OS-specific artifacts with appropriate skip conditions.
    Windows tests skip gracefully when no Windows target available.
    """
    # Get appropriate target
    target = target_registry.get_by_capability(capability)
    if not target:
        pytest.skip(f"No target with {capability} capability")

    # Verify OS match
    assert target.os_type == os_type, \
        f"Target OS mismatch: expected {os_type}, got {target.os_type}"

    # Collect artifact
    # ... (collection logic)

    # Validate expected fields present
    results = velociraptor_client.query(results_vql)
    if len(results) > 0:
        row = results[0]
        for field in expected_fields:
            # Flexible field matching
            field_found = any(
                k.lower() == field.lower()
                for k in row.keys()
            )
            assert field_found, \
                f"Missing field {field} in {artifact}. Available: {list(row.keys())}"
```

### Example 5: TargetRegistry Enhancement for OS-Specific Capabilities

```python
# Source: tests/integration/helpers/target_registry.py + Phase 4 requirements

# Enhancement to existing TargetRegistry for OS-specific artifact support

def get_by_artifact(self, artifact_name: str) -> Optional[TestTarget]:
    """Get first target that supports a specific artifact.

    Maps artifact names to OS capabilities:
    - Linux.Sys.* → Linux target
    - Windows.System.* → Windows target
    - Windows.Registry.* → Windows target with registry capability

    Args:
        artifact_name: Full artifact name (e.g., 'Linux.Sys.Users')

    Returns:
        TestTarget that supports the artifact, or None
    """
    # Parse artifact OS prefix
    if artifact_name.startswith("Linux."):
        return self.get_by_os("linux")
    elif artifact_name.startswith("Windows.Registry."):
        return self.get_by_capability("windows_registry")
    elif artifact_name.startswith("Windows."):
        return self.get_by_os("windows")
    else:
        # Generic or unknown - try any target
        return self.targets[0] if self.targets else None

def get_all_by_artifact(self, artifact_name: str) -> List[TestTarget]:
    """Get all targets that support a specific artifact.

    Returns:
        List of TestTargets that support the artifact
    """
    if artifact_name.startswith("Linux."):
        return self.get_all_by_os("linux")
    elif artifact_name.startswith("Windows.Registry."):
        return self.get_all_by_capability("windows_registry")
    elif artifact_name.startswith("Windows."):
        return self.get_all_by_os("windows")
    else:
        return self.targets.copy()
```

## State of the Art

### Velociraptor Artifact Evolution

| Aspect | Legacy (pre-0.72) | Current (0.75.x) | Future (0.76+) | Impact |
|--------|------------------|------------------|----------------|--------|
| Process artifacts | Generic.System.Pslist expected | OS-specific only (Linux.Sys.Pslist) | May add Generic.* variants | Must use OS-specific artifacts in tests |
| Field naming | Mixed case (ProcessId) | Varies by artifact | Standardizing | Use flexible field matching |
| Registry parsing | Manual parsing | Binary profile parsing | Enhanced profile library | Rely on artifact parsing, don't parse raw |
| Schema validation | No standard | Community-driven | Possible official schemas | Use minimal custom schemas for now |

### Test Infrastructure Evolution

| Aspect | Phase 1-2 | Phase 4 (current) | Phase 6 (future) | Impact |
|--------|-----------|-------------------|------------------|--------|
| Test targets | Linux Docker container only | + Windows VM/host (conditional) | + Cloud VMs | Progressive capability expansion |
| Target selection | enrolled_client_id fixture | TargetRegistry with capabilities | Multi-org target pools | Capability-based selection pattern established |
| Artifact validation | Smoke tests (basic structure) | OS-specific schema validation | Performance benchmarks | Build on established smoke test patterns |

### Windows Testing Evolution

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| Docker on Windows host | Native Windows containers | Requires Windows CI runners, host/container version matching | Future consideration for dedicated Windows CI |
| VirtualBox/Vagrant VM | Works on any host, pytest-vagrant integration available | Slower, resource-intensive | Good for local development |
| Skip Windows tests | Simple, no infrastructure changes | Windows functionality untested | Current approach - implement with skip guards |
| GitHub Actions Windows runners | Cloud-based, no local setup | Requires Windows Server licensing considerations | Future consideration for CI/CD |

**Current recommendation (Phase 4):** Implement Windows tests with pytest.skipif guards. Tests pass on Linux (skip Windows tests), activate on Windows hosts when available. Document Windows testing requirements in test docstrings.

## Open Questions

### 1. Windows Testing Infrastructure

**What we know:**
- Windows containers require Windows hosts (architectural limitation)
- VirtualBox/Vagrant can provide Windows VM targets on any host
- pytest-vagrant provides pytest integration for Vagrant-managed VMs
- Current CI likely runs on Linux hosts

**What's unclear:**
- Do we have Windows VMs available for testing? (Physical lab or cloud)
- Is Windows testing a priority for Phase 4, or acceptable to defer?
- Budget for Windows Server licensing if using GitHub Actions Windows runners

**Recommendation:**
- Implement Windows tests with skip guards now (works on Linux, activates when Windows target available)
- Document Windows VM setup instructions (Vagrant + VirtualBox)
- Defer mandatory Windows testing to Phase 6 (Physical/Virtual Infrastructure)
- Mark Windows tests with `pytest.mark.windows` for easy filtering

### 2. Artifact Version Compatibility

**What we know:**
- Current test container runs Velociraptor 0.75.x
- Artifact schemas evolve across versions
- Field names may change (ProcessId → Pid)

**What's unclear:**
- Which Velociraptor versions must be supported? (0.72+, 0.75+, latest only?)
- Should tests validate against multiple Velociraptor versions?
- How often do artifact schemas break compatibility?

**Recommendation:**
- Use minimal schemas (1-2 required fields per artifact)
- Apply flexible field name matching pattern from Phase 2
- Document tested Velociraptor version in test docstrings
- Add version compatibility testing in future phase if needed

### 3. Complex Registry Artifact Validation

**What we know:**
- Windows.Registry.UserAssist parses binary structures (64-byte headers)
- ROT13 decoding applied to application names
- May return empty results on systems without UserAssist data

**What's unclear:**
- Should tests validate ROT13 decoding logic, or just final output?
- How to generate test data for registry artifacts? (Need Windows system with UserAssist entries)
- Are there simpler registry artifacts to test first?

**Recommendation:**
- Validate final output only (Name field should be decoded, not ROT13 encoded)
- Accept empty results as valid (UserAssist may not exist on clean systems)
- Consider Windows.Registry.NTUser as simpler alternative for initial registry testing
- Add registry artifact complexity to test documentation

### 4. TargetRegistry Capability Granularity

**What we know:**
- Current capabilities are OS-level (linux_users, windows_registry)
- TargetRegistry infers capabilities from OS type
- Some artifacts may require specific OS versions or configurations

**What's unclear:**
- Should capabilities be artifact-specific? (e.g., "supports_linux_sys_users")
- How to handle version-specific artifacts? (artifact added in 0.75+)
- Should TargetRegistry query artifacts from each target? (dynamic vs static)

**Recommendation:**
- Keep OS-level capabilities for Phase 4 (simpler, proven pattern)
- Map artifact names to capabilities in tests (artifact_name → capability lookup)
- Dynamic artifact discovery can be future enhancement if needed
- Current approach sufficient for Phase 4 requirements

## Sources

### Primary (HIGH confidence)

**Velociraptor Official Documentation:**
- [Linux.Sys.Users artifact](https://docs.velociraptor.app/artifact_references/pages/linux.sys.users/) - Output schema verified
- [Windows.System.Services artifact](https://docs.velociraptor.app/artifact_references/pages/windows.system.services/) - Output fields and parsing verified
- [Windows.Registry.UserAssist artifact](https://docs.velociraptor.app/artifact_references/pages/windows.registry.userassist/) - Binary parsing and output verified
- [Artifact Reference index](https://docs.velociraptor.app/artifact_references/) - Complete artifact catalog

**Microsoft Official Documentation:**
- [Windows Container Requirements](https://learn.microsoft.com/en-us/virtualization/windowscontainers/deploy-containers/system-requirements) - Host requirements verified
- [Windows Container Version Compatibility](https://learn.microsoft.com/en-us/virtualization/windowscontainers/deploy-containers/version-compatibility) - OS matching requirement verified
- [Windows Server Core and Nano Server images](https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/container-base-images) - ltsc2025 availability verified

**pytest Official Documentation:**
- [pytest skipping documentation](https://docs.pytest.org/en/stable/how-to/skipping.html) - skipif patterns verified
- [pytest parametrize documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) - Parametrization with marks verified

### Secondary (MEDIUM confidence)

**Python Schema Validation:**
- [Pydantic vs Marshmallow comparison](https://www.augmentedmind.de/2020/10/25/marshmallow-vs-pydantic-python/) - Library comparison
- [JSON Schema validation guide](https://superjson.ai/blog/2025-08-24-json-schema-validation-python-pydantic-guide/) - Validation approaches

**Testing Infrastructure:**
- [pytest-vagrant PyPI](https://pypi.org/project/pytest-vagrant/) - Vagrant integration plugin
- [VirtualBox Vagrant provider](https://developer.hashicorp.com/vagrant/docs/providers/virtualbox) - VM management

### Tertiary (LOW confidence - codebase specific)

**Project Codebase:**
- tests/integration/helpers/target_registry.py - Current TargetRegistry implementation
- tests/integration/schemas/base_schemas.py - Established schema validation patterns
- tests/conftest.py - Fixture patterns and scopes
- .planning/STATE.md - Established decisions from Phases 1-3

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Velociraptor documentation verified for all artifacts
- Architecture patterns: HIGH - Patterns verified against existing codebase and pytest documentation
- Windows container limitations: HIGH - Microsoft official documentation verified
- Schema validation approach: HIGH - jsonschema already in project dependencies
- VM testing approaches: MEDIUM - pytest-vagrant exists but not tested in this project
- Artifact version compatibility: MEDIUM - Based on Phase 2 experience, not comprehensive version testing

**Research date:** 2026-01-25

**Valid until:** 60 days (stable domain - Velociraptor artifacts and pytest patterns change slowly)

**Key assumptions:**
1. Velociraptor 0.75.x is the target version (verified from Phase 2 testing)
2. Linux Docker container remains primary test target (established in Phase 1)
3. Windows testing is desirable but not blocking (inferred from "if available" in requirements)
4. jsonschema library remains acceptable for validation (already in dependencies)
5. Current test infrastructure patterns (module-scoped fixtures, capability-based targeting) continue (established in Phases 1-2)
