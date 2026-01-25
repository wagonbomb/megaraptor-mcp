# Testing Patterns

**Analysis Date:** 2026-01-24

## Test Framework

**Runner:**
- pytest 7.0.0+
- Config: `pyproject.toml` (lines 67-77)

**Async Support:**
- pytest-asyncio 0.21.0+ with `asyncio_mode = "auto"`
- Automatically handles async test functions and fixtures

**Additional Plugins:**
- pytest-timeout 2.2.0+ for timeout management
- Automatic timeout enforcement on slow tests

**Run Commands:**
```bash
pytest                        # Run all tests
pytest tests/                 # Run all tests in tests directory
pytest -m unit                # Run unit tests only
pytest -m integration         # Run integration tests only
pytest -v                     # Verbose output with test names
pytest -x                     # Stop on first failure
pytest --tb=short             # Short traceback format
```

## Test Organization

**Directory Structure:**
```
tests/
├── conftest.py              # Shared fixtures and configuration
├── fixtures/                # Test fixture files (configs, etc.)
│   └── __init__.py
├── mocks/                   # Mock objects and test doubles
│   ├── __init__.py
│   └── mock_velociraptor.py
├── unit/                    # Unit tests (no external dependencies)
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_certificate_manager.py
│   ├── test_credential_store.py
│   └── test_profiles.py
└── integration/             # Integration tests (requires Docker)
    ├── __init__.py
    ├── test_dfir_tools.py
    └── test_docker_deployment.py
```

**File Naming:**
- Test files: `test_*.py` (e.g., `test_config.py`)
- Located adjacent to functionality or in dedicated test directories
- One test file per module being tested

## Test Markers

**Configured Markers:**
```python
markers = [
    "unit: Unit tests (no external dependencies)",
    "integration: Requires Docker infrastructure",
    "slow: Long-running tests",
]
```
Located in: `pyproject.toml` (lines 70-74)

**Usage Pattern:**
```python
@pytest.mark.unit
class TestVelociraptorConfig:
    """Tests for VelociraptorConfig class."""

@pytest.mark.integration
@pytest.mark.slow
class TestClientManagement:
    """Tests for client management via VQL."""
```
Located in: `tests/unit/test_config.py` (line 11) and `tests/integration/test_dfir_tools.py` (line 17)

## Test File Structure

**Typical Pattern:**
```python
"""Module-level docstring describing test purpose.

Extended description of what these tests verify and any
special requirements (Docker, configs, etc.).
"""

import pytest
from megaraptor_mcp.config import VelociraptorConfig

@pytest.mark.unit
class TestVelociraptorConfig:
    """Tests for VelociraptorConfig class."""

    def test_from_config_file(self, tmp_path):
        """Test loading config from a YAML file."""
        # Arrange
        config_data = {...}
        config_file = tmp_path / "api_client.yaml"

        # Act
        config = VelociraptorConfig.from_config_file(str(config_file))

        # Assert
        assert config.api_url == "https://velociraptor.example.com:8001"

    def test_validate_missing_url(self):
        """Test validation fails without API URL."""
        config = VelociraptorConfig(...)
        with pytest.raises(ValueError, match="API URL is required"):
            config.validate()
```
Located in: `tests/unit/test_config.py`

**Test Class Organization:**
- Group related tests in test classes
- One test class per main class being tested: `TestVelociraptorConfig`
- Test method names describe specific scenario: `test_from_config_file`, `test_validate_missing_url`
- Docstrings for all test methods explaining what is tested

## Fixture Patterns

**Session-Level Fixtures (shared across all tests):**
```python
@pytest.fixture(scope="session")
def docker_available() -> bool:
    """Check if Docker is available for tests."""
    return has_docker()

@pytest.fixture(scope="session")
def docker_compose_up(docker_available: bool, velociraptor_configs_exist: bool) -> Generator[bool, None, None]:
    """Start test infrastructure for integration tests."""
    if not docker_available:
        pytest.skip("Docker not available")
    # ... start Docker Compose ...
    yield True
    # ... cleanup ...
```
Located in: `tests/conftest.py` (lines 80-145)

**Function-Level Fixtures (isolated per test):**
```python
@pytest.fixture
def temp_deployment_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide an isolated directory for deployment artifacts."""
    deploy_dir = tmp_path / "deployments"
    deploy_dir.mkdir()
    yield deploy_dir
    # Cleanup handled automatically by tmp_path
```
Located in: `tests/conftest.py` (lines 164-174)

**Fixture Dependencies:**
```python
@pytest.fixture
def docker_compose_up(docker_available: bool, velociraptor_configs_exist: bool) -> Generator[bool, None, None]:
    """Fixtures can depend on other fixtures"""
    if not docker_available:
        pytest.skip(...)
```
Fixtures are injected as parameters and automatically resolved.

**Mock Fixtures:**
```python
@pytest.fixture
def mock_velociraptor_config(tmp_path: Path) -> dict:
    """Create a mock Velociraptor API config file."""
    import yaml
    config_data = {
        "api_url": "https://velociraptor.test:8001",
        "ca_certificate": "-----BEGIN CERTIFICATE-----\nMOCK_CA_CERT\n-----END CERTIFICATE-----",
        ...
    }
    config_file = tmp_path / "api_client.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return {"config_path": str(config_file), "config_data": config_data}
```
Located in: `tests/conftest.py` (lines 218-241)

**Autouse Fixtures (run for every test):**
```python
@pytest.fixture(autouse=True)
def isolate_test_artifacts(tmp_path: Path, monkeypatch) -> Generator[None, None, None]:
    """Ensure tests don't affect the real system."""
    test_data_home = tmp_path / "data"
    test_data_home.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(test_data_home))

    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(test_data_home))

    yield
    # Cleanup is automatic with tmp_path
```
Located in: `tests/conftest.py` (lines 245-263)

## Mocking Patterns

**Framework:** unittest.mock (built-in)

**Mock Objects:**
```python
from unittest.mock import MagicMock, AsyncMock

# Regular mock
client_mock = MagicMock()
client_mock.query.return_value = [{"client_id": "C.123"}]

# Async mock
async_client = AsyncMock()
result = await async_client.some_async_method()
```

**Test Double Pattern:**
Custom mock classes for complex objects:
```python
@dataclass
class MockClient:
    """Represents a mock Velociraptor client."""
    client_id: str
    hostname: str
    os_info: Dict[str, str] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching Velociraptor API."""
        return {...}

@dataclass
class MockArtifact:
    """Represents a mock Velociraptor artifact."""
    name: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {...}
```
Located in: `tests/mocks/mock_velociraptor.py` (lines 15-71)

**Mock Server:**
```python
class MockVelociraptorServer:
    """Mock Velociraptor server for testing.

    Simulates a Velociraptor server's gRPC API, storing state in memory.
    Use for unit tests that don't need real infrastructure.
    """

    def __init__(self):
        self.clients: Dict[str, MockClient] = {}
        self.artifacts: Dict[str, MockArtifact] = {}
        self.hunts: Dict[str, MockHunt] = {}
```
Located in: `tests/mocks/mock_velociraptor.py` (lines 133-150)

**What to Mock:**
- External API calls (Velociraptor, Docker, AWS, Azure)
- File I/O operations (use `tmp_path` fixture instead)
- Time-dependent operations (use fixed timestamps or time mocking)
- Configuration loading (use `mock_velociraptor_config` fixture)

**What NOT to Mock:**
- Core business logic
- Dataclass initialization
- Type validation
- Configuration object creation (test with real dataclass)

## Test Structure Patterns

**Arrange-Act-Assert Pattern:**
```python
def test_from_config_file(self, tmp_path):
    """Test loading config from a YAML file."""
    # Arrange
    config_data = {
        "api_url": "https://velociraptor.example.com:8001",
        "ca_certificate": "-----BEGIN CERTIFICATE-----\ntest-ca\n-----END CERTIFICATE-----",
        "client_cert": "-----BEGIN CERTIFICATE-----\ntest-cert\n-----END CERTIFICATE-----",
        "client_private_key": "-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----",
    }
    config_file = tmp_path / "api_client.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Act
    config = VelociraptorConfig.from_config_file(str(config_file))

    # Assert
    assert config.api_url == "https://velociraptor.example.com:8001"
    assert "test-ca" in config.ca_cert
```
Located in: `tests/unit/test_config.py` (lines 15-33)

**Exception Testing:**
```python
def test_validate_missing_url(self):
    """Test validation fails without API URL."""
    config = VelociraptorConfig(
        api_url="",
        client_cert="cert",
        client_key="key",
        ca_cert="ca",
    )

    with pytest.raises(ValueError, match="API URL is required"):
        config.validate()
```
Located in: `tests/unit/test_config.py` (lines 54-64)

**Boolean Assertions:**
```python
def test_allows_target_when_allowed(self):
    """Test allows_target returns True for allowed targets."""
    profile = DeploymentProfile(
        name="test",
        description="Test",
        allowed_targets=[DeploymentTarget.DOCKER, DeploymentTarget.AWS],
    )

    assert profile.allows_target(DeploymentTarget.DOCKER) is True
    assert profile.allows_target(DeploymentTarget.AWS) is True
```
Located in: `tests/unit/test_profiles.py` (lines 74-82)

**Collection Assertions:**
```python
def test_list_clients_with_limit(self, velociraptor_client):
    """Test listing clients with a limit."""
    result = velociraptor_client.query("SELECT * FROM clients() LIMIT 5")

    assert isinstance(result, list)
    assert len(result) <= 5
```
Located in: `tests/integration/test_dfir_tools.py` (lines 67-72)

## Async Testing

**Pattern:**
```python
@pytest.fixture(scope="module")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_async_operation(self, client):
    """Test async operation."""
    result = await client.some_async_method()
    assert result is not None
```
Located in: `tests/integration/test_dfir_tools.py` (lines 20-25)

**Async Fixture Support:**
- `pytest-asyncio` with `asyncio_mode = "auto"` automatically detects async fixtures and test functions
- No need for `@pytest.mark.asyncio` decorator (pytest-asyncio automatically handles it)

## Error/Exception Testing

**Pattern with match parameter:**
```python
def test_from_config_file_not_found(self):
    """Test error when config file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        VelociraptorConfig.from_config_file("/nonexistent/path.yaml")

def test_load_no_config_raises(self, monkeypatch):
    """Test error when no configuration is available."""
    monkeypatch.delenv("VELOCIRAPTOR_CONFIG_PATH", raising=False)

    with pytest.raises(ValueError, match="No Velociraptor configuration found"):
        load_config()
```
Located in: `tests/unit/test_config.py` (lines 35-38, 102-112)

## Test Isolation

**Environment Variable Isolation:**
- Use `monkeypatch` fixture to set/unset env vars
- All isolation is automatic (monkeypatch reverts changes after test)

**File System Isolation:**
- Use `tmp_path` fixture for temporary directories
- Use `temp_deployment_dir`, `temp_certs_dir`, `temp_credentials_dir` for domain-specific temp paths
- Cleanup is automatic

**Singleton Isolation:**
- `isolate_test_artifacts` autouse fixture redirects XDG_DATA_HOME
- Prevents tests from touching real user data directories
- All tests get isolated temporary data home

**Global State:**
- `clean_env` fixture for tests that need clean environment
- Can also use `reset_client()` to clear global client instance if needed

## Test Coverage

**Requirements:** Not enforced (no coverage configuration in pyproject.toml)

**View Coverage:**
```bash
pytest --cov=src --cov-report=html  # Generates HTML report in htmlcov/
pytest --cov=src --cov-report=term  # Text report to terminal
```

**Coverage Notes:**
- Tests focus on core functionality (config, security, deployment models)
- Unit tests have high coverage of deterministic code
- Integration tests cover end-to-end workflows
- No coverage enforcement in CI

## Test Types

**Unit Tests:**
- Location: `tests/unit/`
- Scope: Individual functions, classes, dataclasses
- Dependencies: None (use mocks for anything external)
- Speed: Fast (< 1 second each)
- Examples:
  - `test_config.py`: Configuration loading and validation
  - `test_certificate_manager.py`: Certificate generation logic
  - `test_credential_store.py`: Credential encryption/storage
  - `test_profiles.py`: Deployment profile logic

**Integration Tests:**
- Location: `tests/integration/`
- Scope: End-to-end workflows with real infrastructure
- Dependencies: Docker, Velociraptor server running
- Speed: Slow (minutes)
- Examples:
  - `test_dfir_tools.py`: DFIR tool operations against real Velociraptor
  - `test_docker_deployment.py`: Docker deployment workflows
- Marked with `@pytest.mark.integration` and `@pytest.mark.slow`

**Performance Tests:**
- Not observed in current test suite
- Long-running operations flagged with `@pytest.mark.slow`

## Special Test Configurations

**Import Skipping:**
```python
# Skip all tests if cryptography is not available
pytest.importorskip("cryptography")

from cryptography import x509
from cryptography.hazmat.primitives import serialization
```
Located in: `tests/unit/test_certificate_manager.py` (line 10)

**Module-Level Skip Logic:**
```python
# These tests require Docker infrastructure
pytestmark = [pytest.mark.integration, pytest.mark.slow]
```
Located in: `tests/integration/test_dfir_tools.py` (line 17)

**Deprecation Warnings:**
```python
filterwarnings = [
    "ignore::DeprecationWarning",
]
```
Located in: `pyproject.toml` (lines 75-77)

## Common Test Data Patterns

**Temporary Directories:**
```python
def test_to_dict_excludes_data(self):
    """Test to_dict includes metadata but excludes sensitive data."""
    cred = StoredCredential(
        id="cred_001",
        name="Test Credential",
        credential_type="api_key",
        created_at="2024-01-01T00:00:00+00:00",
        expires_at="2024-12-31T23:59:59+00:00",
        deployment_id="deploy_001",
        data={"secret": "sensitive_value"},
    )

    result = cred.to_dict()
    assert "data" not in result
```
Located in: `tests/unit/test_credential_store.py` (lines 69-88)

**Timestamps:**
```python
from datetime import datetime, timezone, timedelta

future = datetime.now(timezone.utc) + timedelta(days=1)
cred = StoredCredential(
    ...
    expires_at=future.isoformat(),
    ...
)
```
Located in: `tests/unit/test_credential_store.py` (lines 39-52)

---

*Testing analysis: 2026-01-24*
