# Phase 5: Output Quality - Research

**Researched:** 2026-01-26
**Domain:** Forensic validation testing for DFIR artifact collection
**Confidence:** MEDIUM

## Summary

Phase 5 focuses on validating forensic output quality through hash verification, timestamp accuracy testing, completeness validation, and baseline comparison. The standard approach combines Python's built-in hashlib for file integrity verification with pytest's parametrization features for testing multiple known-good baselines, jsonschema for field completeness validation (already in use), and pytest.approx for timestamp drift tolerance testing.

NIST's Computer Forensics Tool Testing (CFTT) program establishes the methodology for forensic tool validation, though specific false positive rate thresholds (<1%) require domain-specific definition based on artifact types. The forensics community uses known-good reference datasets (NIST CFReDS portal) for ground truth validation, though this project will create artifact-specific fixtures given the unique Velociraptor VQL environment.

The existing test infrastructure (pytest + jsonschema + pytest-check) provides the foundation. Key additions needed: hashlib for hash verification, pytest.approx for timestamp tolerance validation, and structured test fixtures with known-good baselines documented per QUAL-05 requirement.

**Primary recommendation:** Use Python's built-in hashlib.sha256() for hash verification, pytest.approx(rel=1e-3) for timestamp drift tolerance (±1 second), and parametrized fixtures with known-good JSON baselines stored in tests/fixtures/ for VQL result correctness validation.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hashlib | stdlib | SHA-256 hash verification | Python standard library, forensically sound, FIPS-validated algorithms |
| jsonschema | 4.26.0 | Field completeness validation | Already in use, supports lazy validation with all errors reported |
| pytest-check | 2.6.2+ | Soft assertions for multiple failures | Already in use, allows reporting all validation failures in single test run |
| pytest.approx | pytest builtin | Timestamp drift tolerance testing | Built into pytest, handles floating-point comparison with configurable tolerance |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| freezegun | 1.5.0+ | Time mocking for timestamp testing | When testing timestamp accuracy validation logic itself |
| pytest.mark.parametrize | pytest builtin | Baseline comparison testing | For testing multiple known-good datasets against validation logic |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hashlib | cryptography library | Overkill - hashlib sufficient for hash verification without additional dependencies |
| pytest.approx | Manual tolerance checking | Reinventing the wheel - pytest.approx handles edge cases (infinity, NaN) |
| Custom baseline format | NIST CFReDS datasets | CFReDS datasets are disk images, not VQL results - need artifact-specific baselines |

**Installation:**
```bash
# Core already installed via pyproject.toml:
# - jsonschema>=4.26.0
# - pytest-check>=2.6.2

# Optional for advanced time testing:
pip install freezegun>=1.5.0
```

## Architecture Patterns

### Recommended Project Structure
```
tests/fixtures/
├── README.md                    # Documents known-good datasets (QUAL-05)
├── baselines/                   # Known-good VQL results
│   ├── linux_sys_users.json    # Linux.Sys.Users baseline
│   ├── generic_client_info.json # Generic.Client.Info baseline
│   └── metadata.json           # Hashes, timestamps, test conditions
└── [existing config files]
```

### Pattern 1: Hash Verification Against Known-Good
**What:** Compute SHA-256 hash of artifact collection results and compare against baseline hash
**When to use:** QUAL-01 requirement - validate collected artifacts match expected values
**Example:**
```python
# Source: Python hashlib documentation
import hashlib
import json

def compute_artifact_hash(artifact_results):
    """Compute deterministic SHA-256 hash of VQL results.

    Sorts JSON keys for deterministic output across Python versions.
    """
    normalized = json.dumps(artifact_results, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def test_linux_sys_users_hash_validation(velociraptor_client, target_registry):
    """Validate Linux.Sys.Users collection matches known-good hash."""
    # Collect artifact
    results = collect_and_retrieve_artifact(...)

    # Compute hash
    actual_hash = compute_artifact_hash(results)

    # Load known-good hash from fixture metadata
    with open("tests/fixtures/baselines/metadata.json") as f:
        baselines = json.load(f)
    expected_hash = baselines["Linux.Sys.Users"]["sha256"]

    # Validate
    assert actual_hash == expected_hash, \
        f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
```

### Pattern 2: Timestamp Accuracy Validation
**What:** Validate timestamps are within ±1 second drift using pytest.approx
**When to use:** QUAL-02 requirement - timeline accuracy testing
**Example:**
```python
# Source: pytest.approx documentation
from datetime import datetime
from pytest import approx

def parse_timestamp(ts_string):
    """Parse Velociraptor timestamp to Unix epoch seconds."""
    # Velociraptor typically returns RFC3339/ISO8601
    dt = datetime.fromisoformat(ts_string.replace('Z', '+00:00'))
    return dt.timestamp()

def test_timestamp_accuracy_within_drift(velociraptor_client):
    """Validate artifact timestamps within ±1 second of expected."""
    # Collect artifact with known timestamp
    results = collect_artifact_with_timestamp(...)

    actual_ts = parse_timestamp(results[0]["Timestamp"])
    expected_ts = 1234567890.0  # Known-good baseline timestamp

    # pytest.approx default is 1e-6 relative tolerance
    # For ±1 second on timestamps ~1e9, use absolute tolerance
    assert actual_ts == approx(expected_ts, abs=1.0), \
        f"Timestamp drift exceeds ±1s: {actual_ts - expected_ts}s"
```

### Pattern 3: Completeness Validation with jsonschema
**What:** Validate all expected fields present using existing jsonschema patterns
**When to use:** QUAL-03 requirement - artifact completeness validation
**Example:**
```python
# Source: Existing tests/integration/schemas/os_artifacts.py pattern
from jsonschema import validate, ValidationError

# Already established pattern from Phase 4
LINUX_SYS_USERS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["User"],  # Minimal required fields
        "properties": {
            "User": {"type": "string"},
            "Uid": {"type": ["string", "integer"]},
            "Gid": {"type": ["string", "integer"]},
        }
    }
}

def test_artifact_completeness(velociraptor_client):
    """Validate all expected fields present in artifact results."""
    results = collect_artifact(...)

    # jsonschema validates structure AND completeness
    validate(instance=results, schema=LINUX_SYS_USERS_SCHEMA)

    # Additional completeness checks for critical fields
    with check:
        assert all("User" in r for r in results), \
            "Missing User field in some results"
    with check:
        assert all(r.get("User") for r in results), \
            "Empty User field values found"
```

### Pattern 4: VQL Result Correctness via Parametrized Baselines
**What:** Compare VQL query results against multiple known-good baselines
**When to use:** QUAL-04 requirement - VQL result correctness validation
**Example:**
```python
# Source: pytest parametrize documentation
import pytest
import json

def load_baseline(artifact_name):
    """Load known-good baseline for artifact."""
    path = f"tests/fixtures/baselines/{artifact_name.lower().replace('.', '_')}.json"
    with open(path) as f:
        return json.load(f)

@pytest.mark.parametrize("artifact_name,expected_fields", [
    ("Linux.Sys.Users", ["User", "Uid", "Gid"]),
    ("Generic.Client.Info", ["Hostname", "OS"]),
])
def test_vql_result_correctness(artifact_name, expected_fields, velociraptor_client):
    """Validate VQL results match known-good baseline structure."""
    # Collect artifact
    results = collect_artifact(velociraptor_client, artifact_name)

    # Load baseline
    baseline = load_baseline(artifact_name)

    # Validate field presence matches baseline
    if baseline:
        baseline_fields = set(baseline[0].keys())
        actual_fields = set(results[0].keys())

        # Critical fields must be present
        for field in expected_fields:
            assert field in actual_fields, \
                f"Missing critical field {field} in {artifact_name}"
```

### Pattern 5: Known-Good Fixture Documentation
**What:** Document test datasets per QUAL-05 requirement
**When to use:** All baseline fixtures must be documented
**Example:**
```markdown
# tests/fixtures/README.md

## Known-Good Test Datasets

This directory contains known-good baselines for forensic validation testing.

### Baseline: Linux.Sys.Users

**File:** `baselines/linux_sys_users.json`
**SHA-256:** `a1b2c3d4e5f6...`
**Created:** 2026-01-26
**Test Conditions:**
- OS: Ubuntu 22.04 Docker container
- Velociraptor: 0.75.x
- Collection method: `collect_client(artifacts=['Linux.Sys.Users'])`
- Expected users: root, nobody, www-data

**Validation:**
- Hash: SHA-256 of normalized JSON
- Timestamp: Collection time ±1 second
- Fields: User, Uid, Gid, Homedir, Shell

### Baseline Update Procedure

1. Collect artifact in controlled environment
2. Manually verify correctness (compare with `/etc/passwd`)
3. Compute SHA-256 hash of normalized JSON
4. Document test conditions in this README
5. Add baseline to `baselines/` directory
6. Update `metadata.json` with hash and timestamp
```

### Anti-Patterns to Avoid
- **Hardcoded hashes in test code:** Store hashes in fixture metadata.json for maintainability
- **Comparing raw JSON strings:** Use normalized JSON (sorted keys) for deterministic comparison
- **Testing against live system state:** Use static baselines - live state changes invalidate tests
- **Over-specifying baselines:** Only validate critical fields to avoid brittleness across Velociraptor versions
- **Ignoring timestamp precision:** Different systems/languages represent sub-second precision differently

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hash computation | Custom hash function | hashlib.sha256() | Standard library, FIPS-validated, handles encoding/buffers correctly |
| Floating-point timestamp comparison | Manual tolerance checking | pytest.approx(abs=1.0) | Handles edge cases (infinity, NaN, large numbers) |
| Time mocking for tests | Custom time override | freezegun library | Handles all datetime sources (datetime.now, time.time, etc.) |
| Multiple baseline testing | Loop with test cases | pytest.mark.parametrize | Proper test reporting, individual test IDs, parallel execution |
| Field presence validation | Manual key checking | jsonschema validation | Validates types, required fields, nested structures |

**Key insight:** Forensic validation requires deterministic, auditable operations. Use well-tested standard library functions (hashlib) and established testing patterns (pytest.approx, jsonschema) rather than custom implementations that may have subtle bugs affecting correctness.

## Common Pitfalls

### Pitfall 1: Non-Deterministic JSON Serialization
**What goes wrong:** Hash verification fails intermittently due to dictionary key ordering differences
**Why it happens:** Python dicts maintain insertion order (3.7+) but JSON serialization may not be stable across platforms
**How to avoid:** Always use `json.dumps(obj, sort_keys=True, separators=(',', ':'))` for hash computation
**Warning signs:** Hash tests pass on one machine, fail on another; hash changes when re-running same data

### Pitfall 2: Timestamp Format Inconsistencies
**What goes wrong:** Timestamp parsing fails due to format differences (RFC3339 vs ISO8601 vs Unix epoch)
**Why it happens:** Velociraptor may return timestamps in different formats depending on VQL function used
**How to avoid:** Normalize timestamp parsing - detect format and convert to Unix epoch before comparison
**Warning signs:** `ValueError: time data '...' does not match format` errors; timestamp tests fail unpredictably

### Pitfall 3: False Positive from Environmental Differences
**What goes wrong:** Baselines collected on one system don't match collections on different test systems
**Why it happens:** Docker container state, OS version, Velociraptor version differences affect output
**How to avoid:** Document test conditions in fixtures/README.md; use flexible validation (critical fields only)
**Warning signs:** Tests pass in CI, fail locally; tests fail after Velociraptor version update

### Pitfall 4: Over-Strict Hash Validation
**What goes wrong:** Minor field additions in new Velociraptor versions break all hash validation tests
**Why it happens:** Hash validation on entire result set is too brittle for evolving schemas
**How to avoid:** Hash only critical fields, or use hash validation for regression testing only
**Warning signs:** All hash tests break after Velociraptor minor version update; new field additions cause failures

### Pitfall 5: NIST CFTT <1% False Positive Misinterpretation
**What goes wrong:** Applying statistical false positive rate to deterministic artifact collection
**Why it happens:** CFTT testing is for file carving/recovery tools (probabilistic); VQL is deterministic
**How to avoid:** Define "false positive" for your artifact type (e.g., incorrect user in Linux.Sys.Users)
**Warning signs:** Confusion about what constitutes a "false positive" in deterministic VQL queries

## Code Examples

Verified patterns from official sources:

### Hash Verification with Normalization
```python
# Source: Python hashlib documentation + forensic best practices
import hashlib
import json

def compute_forensic_hash(data, algorithm='sha256'):
    """Compute forensically sound hash of structured data.

    Args:
        data: Dictionary or list to hash
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hexadecimal hash string
    """
    # Normalize JSON for deterministic hashing
    normalized = json.dumps(
        data,
        sort_keys=True,        # Deterministic key order
        separators=(',', ':'), # No whitespace
        ensure_ascii=True      # Consistent encoding
    )

    # Compute hash
    hasher = hashlib.new(algorithm)
    hasher.update(normalized.encode('utf-8'))
    return hasher.hexdigest()

# Usage in tests
def test_artifact_hash_matches_baseline():
    results = collect_artifact(...)
    actual_hash = compute_forensic_hash(results)

    baseline = load_baseline_metadata()
    expected_hash = baseline["sha256"]

    assert actual_hash == expected_hash, \
        f"Artifact hash mismatch:\n  Expected: {expected_hash}\n  Got: {actual_hash}"
```

### Timestamp Accuracy Testing with pytest.approx
```python
# Source: pytest.approx documentation
from datetime import datetime
from pytest import approx

def parse_velociraptor_timestamp(ts_str):
    """Parse Velociraptor timestamp to Unix epoch.

    Handles multiple formats:
    - RFC3339: 2024-01-26T12:34:56Z
    - ISO8601: 2024-01-26T12:34:56+00:00
    - Unix epoch: 1234567890
    """
    if isinstance(ts_str, (int, float)):
        return float(ts_str)

    # Handle RFC3339 with Z suffix
    ts_str = ts_str.replace('Z', '+00:00')

    dt = datetime.fromisoformat(ts_str)
    return dt.timestamp()

def test_timestamp_within_drift_tolerance():
    """QUAL-02: Timestamp accuracy within ±1 second."""
    results = collect_artifact_with_known_timestamp(...)

    actual_ts = parse_velociraptor_timestamp(results[0]["LastExecution"])
    expected_ts = 1706275200.0  # Known baseline timestamp

    # ±1 second absolute tolerance
    assert actual_ts == approx(expected_ts, abs=1.0), \
        f"Timestamp drift: {abs(actual_ts - expected_ts):.2f}s exceeds ±1s tolerance"
```

### Parametrized Baseline Testing
```python
# Source: pytest parametrize documentation
import pytest
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "baselines"

@pytest.mark.parametrize("artifact,baseline_file,critical_fields", [
    ("Linux.Sys.Users", "linux_sys_users.json", ["User", "Uid"]),
    ("Generic.Client.Info", "generic_client_info.json", ["Hostname", "OS"]),
])
def test_vql_correctness_against_baseline(
    artifact, baseline_file, critical_fields, velociraptor_client, target_registry
):
    """QUAL-04: VQL result correctness against known-good baselines."""
    # Get appropriate target
    target = target_registry.get_by_artifact(artifact)
    if not target:
        pytest.skip(f"No target available for {artifact}")

    # Collect artifact
    results = collect_artifact(velociraptor_client, target.client_id, artifact)

    # Load baseline
    baseline_path = FIXTURES_DIR / baseline_file
    with open(baseline_path) as f:
        baseline = json.load(f)

    # Validate structure matches baseline
    assert isinstance(results, list), "Results should be array"
    assert len(results) > 0, "Results should not be empty"

    # Validate critical fields present
    for field in critical_fields:
        with check:
            assert field in results[0], \
                f"Missing critical field: {field}"

    # Validate result count in expected range
    # (exact count may vary, but should be similar magnitude)
    baseline_count = len(baseline)
    actual_count = len(results)
    with check:
        assert actual_count == approx(baseline_count, rel=0.5), \
            f"Result count differs significantly: {actual_count} vs {baseline_count}"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual hash computation in test code | hashlib with normalized JSON | Python 3.x | Deterministic, auditable |
| String comparison for timestamps | pytest.approx with absolute tolerance | pytest 3.0+ | Handles drift gracefully |
| Custom field checking loops | jsonschema validation | jsonschema 4.0+ | Comprehensive, lazy error reporting |
| Single test case per artifact | pytest.mark.parametrize | pytest 2.0+ | Better coverage, parallel execution |

**Deprecated/outdated:**
- MD5/SHA1 for forensic hashing: Use SHA-256 minimum (NIST recommendation since 2011)
- Exact timestamp matching: Use ±1 second tolerance to account for system clock drift
- Testing against live system files: Use static baselines for reproducible tests

## Open Questions

Things that couldn't be fully resolved:

1. **NIST CFTT False Positive Rate Definition for VQL**
   - What we know: CFTT requires <1% false positive rate for file carving/recovery tools
   - What's unclear: How to apply this to deterministic VQL queries (not probabilistic)
   - Recommendation: Define artifact-specific "false positive" (e.g., incorrect user in Linux.Sys.Users = false positive), aim for 0% in deterministic queries, <1% for heuristic-based artifacts

2. **Baseline Update Strategy**
   - What we know: Baselines must be updated when Velociraptor versions change
   - What's unclear: Automated vs manual baseline updates, version compatibility ranges
   - Recommendation: Start with manual baseline updates documented in fixtures/README.md, consider automated baseline generation in Phase 6

3. **Cross-Platform Baseline Compatibility**
   - What we know: Docker Linux container provides controlled environment
   - What's unclear: Whether baselines are portable across Linux distributions/versions
   - Recommendation: Document test environment precisely (OS, Velociraptor version), accept some variability in non-critical fields

4. **Hash Validation Granularity**
   - What we know: Full result set hash is brittle to schema changes
   - What's unclear: Best practice for partial hashing (critical fields only vs full results)
   - Recommendation: Use full-result hashing for regression detection, field-level validation for cross-version compatibility

## Sources

### Primary (HIGH confidence)
- [Python hashlib documentation](https://docs.python.org/3/library/hashlib.html) - Standard library hash functions
- [pytest.approx API reference](https://docs.pytest.org/en/stable/reference/reference.html) - Floating-point comparison
- [jsonschema 4.26.0 documentation](https://python-jsonschema.readthedocs.io/) - JSON schema validation
- [pytest parametrize documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) - Test parametrization

### Secondary (MEDIUM confidence)
- [NIST CFTT Program](https://www.nist.gov/itl/ssd/software-quality-group/computer-forensics-tool-testing-program-cftt) - Forensic tool testing methodology
- [GitHub - spulec/freezegun](https://github.com/spulec/freezegun) - Time mocking for Python tests
- [pytest-benchmark documentation](https://pytest-benchmark.readthedocs.io/) - Timing and precision features
- [Velociraptor Artifacts documentation](https://docs.velociraptor.app/docs/vql/artifacts/) - VQL artifact validation

### Tertiary (LOW confidence - needs validation)
- [NIST CFReDS Portal](https://cfreds.nist.gov/) - Reference datasets (portal blocked by Cloudflare challenge)
- [DFIR-Metric benchmark dataset](https://link.springer.com/chapter/10.1007/978-981-95-4367-0_2) - LLM evaluation dataset, not directly applicable
- Web search results about forensic validation patterns - general guidance, not Velociraptor-specific

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - hashlib, jsonschema, pytest.approx are authoritative, well-documented
- Architecture: MEDIUM - Patterns based on existing project structure + pytest best practices
- Pitfalls: MEDIUM - Based on common forensic testing issues + Python JSON serialization gotchas

**Research date:** 2026-01-26
**Valid until:** 2026-02-26 (30 days - stable libraries, but Velociraptor version updates may affect baselines)
