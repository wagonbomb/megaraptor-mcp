# Coding Conventions

**Analysis Date:** 2026-01-24

## Naming Patterns

**Files:**
- Snake case for module names: `config.py`, `client.py`, `certificate_manager.py`
- Package directories use underscores: `megaraptor_mcp`, `deployment`, `security`
- Avoid hyphens in Python module names

**Functions:**
- Snake case for all function names: `load_config()`, `get_client()`, `register_client_tools()`
- Private/internal functions prefixed with single underscore: `_load_cert_or_key()`, `_temp_cert_files()`, `_create_channel()`
- Async functions use `async def` with snake case: `async def run_vql()`

**Classes:**
- PascalCase for all class names: `VelociraptorClient`, `CertificateManager`, `DeploymentConfig`
- Dataclasses use `@dataclass` decorator: `VelociraptorConfig`, `DeploymentResult`, `StoredCredential`
- Abstract base classes use `ABC` suffix pattern: `BaseDeployer`

**Variables:**
- Snake case for all variables: `api_url`, `client_cert`, `deployment_id`
- Constants in UPPER_SNAKE_CASE: `VELOCIRAPTOR_IMAGE`, `DOCKER_STARTUP_TIMEOUT`, `HEALTH_CHECK_INTERVAL`
- Type hints use modern syntax: `dict[str, Any]`, `list[str]`, `Optional[str]` (Python 3.10+)

**Enums:**
- Class name in PascalCase: `DeploymentTarget`, `DeploymentState`
- Enum values in UPPER_SNAKE_CASE: `DOCKER`, `BINARY`, `PROVISIONING`, `RUNNING`

## Code Style

**Formatting:**
- No explicit formatter configured (no black/ruff config found)
- Follows PEP 8 style guide
- Line length: No strict limit enforced in configuration
- Indentation: 4 spaces

**Linting:**
- No linting tool configured (no .pylintrc, .flake8, or eslint config)
- Code uses type hints extensively for clarity
- Python 3.10+ features used (e.g., `dict[str, Any]` instead of `Dict[str, Any]`)

**Module Structure:**
- Docstring at module top level describing purpose
- Imports grouped: stdlib, third-party, local (though not always strictly separated)
- No wildcard imports observed (`from x import *`)

## Import Organization

**Order Observed:**
1. Standard library (`import asyncio`, `import json`, `import os`)
2. Third-party modules (`from mcp.server import Server`, `import pytest`, `import yaml`)
3. Local application imports (`from . import __version__`, `from ..client import get_client`)

**Path Aliases:**
- Relative imports used: `from . import __version__`, `from ..tools import register_client_tools`
- Absolute imports within package: `from megaraptor_mcp.client import VelociraptorClient`
- No import aliases or abbreviations observed (`as` not typically used)

## Docstrings

**Style:** Google-style docstrings (Sphinx-compatible format)

**Pattern:**
```python
def function_name(arg1: str, arg2: int) -> list[dict]:
    """One-line summary of what the function does.

    Extended description if needed, explaining the behavior and any
    important details about usage.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When specific condition occurs
    """
```

**Module Docstrings:** Always present at top of file, describing purpose of module

**Class Docstrings:** Present for all classes with attributes listed

**Function Docstrings:**
- Always include one-line summary
- Include Args, Returns sections when applicable
- Include Raises section if exceptions are documented
- Observed in `server.py`, `config.py`, `client.py`, `tools/clients.py`

## Error Handling

**Patterns Observed:**

**Validation Errors:**
```python
def validate(self) -> None:
    """Validate that required configuration is present."""
    errors = []
    if not self.api_url:
        errors.append("API URL is required")
    if errors:
        raise ValueError(f"Invalid configuration: {'; '.join(errors)}")
```
Located in: `src/megaraptor_mcp/config.py` (lines 106-120)

**File Not Found Errors:**
```python
if not path.exists():
    raise FileNotFoundError(f"Config file not found: {config_path}")
```
Located in: `src/megaraptor_mcp/config.py` (lines 34-35)

**Import Errors with Fallback:**
```python
try:
    import pyvelociraptor
    from pyvelociraptor import api_pb2
    from pyvelociraptor import api_pb2_grpc
except ImportError:
    # Define minimal stubs if pyvelociraptor not installed
    api_pb2 = None
    api_pb2_grpc = None
```
Located in: `src/megaraptor_mcp/client.py` (lines 17-24)

**Optional Dependencies:**
```python
try:
    import docker
    from docker.errors import DockerException, NotFound, APIError
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False
```
Located in: `src/megaraptor_mcp/deployment/deployers/docker_deployer.py` (lines 19-25)

**Context Manager Exception Handling:**
```python
def _temp_cert_files(self):
    """Create temporary files for certificates."""
    temp_files = []
    try:
        # ... create temp files ...
        yield ca_file.name, cert_file.name, key_file.name
    finally:
        # Clean up temp files
        for f in temp_files:
            try:
                os.unlink(f)
            except OSError:
                pass
```
Located in: `src/megaraptor_mcp/client.py` (lines 41-81)

**JSON Parsing with Exception Handling:**
```python
try:
    rows = json.loads(response.Response)
    if isinstance(rows, list):
        results.extend(rows)
    else:
        results.append(rows)
except json.JSONDecodeError:
    # Non-JSON response, skip
    pass
```
Located in: `src/megaraptor_mcp/client.py` (lines 169-177)

## Logging

**Framework:** Standard `logging` module

**Configuration:**
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("megaraptor-mcp")
```
Located in: `src/megaraptor_mcp/server.py` (lines 28-33)

**Usage Pattern:**
- `logger.info()` for general informational messages
- `logger.error()` with `exc_info=True` for exception context
- Logger instance created per module: `logger = logging.getLogger(__name__)` or module name
- No structured logging (JSON) observed

**When to Log:**
- Server startup/shutdown: "Starting Megaraptor MCP Server..."
- Registration events: "Registering client management tools..."
- Error conditions with context: "Server error: {e}", exc_info=True

## Comments

**When to Comment:**
- Complex logic in deployment configuration and security operations
- Non-obvious algorithm or business logic
- API quirks or workarounds documented
- Sparse commenting observed - code is generally self-documenting through docstrings

**Pattern:**
- Single-line comments use `#` for inline explanation
- Multi-line explanations in docstrings
- Section separators used in large functions: `# =========================================================================`

## Data Structures

**Configuration Objects:**
- Use `@dataclass` for immutable config: `VelociraptorConfig`, `DeploymentConfig`
- Include `from_dict()` and `to_dict()` class methods for serialization
- Dataclass fields use type hints: `api_url: str`, `deployment_id: str`, `extra_config: dict[str, Any]`

**Result/Response Objects:**
- Dataclass for structured results: `DeploymentResult`, `DeploymentInfo`
- Include methods for safe serialization: `to_dict(include_secrets: bool = False)`
- Sensitive data redacted in default serialization

**Enums:**
- Use `Enum` class with `.value` property: `DeploymentTarget.DOCKER.value == "docker"`
- Located in: `src/megaraptor_mcp/deployment/profiles.py`

## Type Hints

**Convention:** Full type hints throughout codebase

**Patterns:**
```python
# Function arguments and returns
def query(
    self,
    vql: str,
    env: Optional[dict[str, Any]] = None,
    org_id: Optional[str] = None,
) -> list[dict[str, Any]]:

# Class attributes
class VelociraptorConfig:
    api_url: str
    client_cert: str
    ca_cert: str
    api_connection_string: Optional[str] = None

# Generics
results: list[dict[str, Any]] = []
credentials: dict[str, str] = {}
```

**Union Types:**
- Use `Optional[T]` instead of `Union[T, None]`
- Use `|` operator not observed (still using `Optional`)

## Method Organization

**Class Methods:**
- Regular instance methods: `def connect(self)`
- Static methods: `@staticmethod` for utility functions like `_default_storage_path()`
- Class methods: `@classmethod` for factory pattern: `from_config_file()`, `from_env()`, `from_dict()`
- Properties: `@property` with `@abstractmethod` for abstract properties

**Async Methods:**
- Tool handlers use `@server.tool()` decorator with `async def`
- Context manager support: `__enter__()` and `__exit__()` for connection management
- No async context managers (`async with`) observed in custom classes

## Special Methods

**Context Managers (non-async):**
```python
def __enter__(self) -> "VelociraptorClient":
    self.connect()
    return self

def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    self.close()
```
Located in: `src/megaraptor_mcp/client.py` (lines 227-234)

**Module-level Singleton:**
```python
_client: Optional[VelociraptorClient] = None

def get_client() -> VelociraptorClient:
    global _client
    if _client is None:
        _client = VelociraptorClient()
        _client.connect()
    return _client
```
Located in: `src/megaraptor_mcp/client.py` (lines 237-247)

---

*Conventions analysis: 2026-01-24*
