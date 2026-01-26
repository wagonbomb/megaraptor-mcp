# Phase 3: Error Handling - Research

**Researched:** 2026-01-25
**Domain:** Python MCP error handling, gRPC exception patterns, input validation
**Confidence:** HIGH

## Summary

Phase 3 implements comprehensive error handling for 35 MCP tools that communicate with Velociraptor via gRPC. The domain spans three critical areas: (1) gRPC error handling with proper StatusCode mapping, (2) MCP tool error reporting using FastMCP patterns, and (3) input validation to prevent malformed requests.

The current codebase has minimal error handling - only `vql.py` wraps queries in try/except, and `deployment.py` catches ImportError. Tools directly return JSON error objects like `{"error": "..."}` without leveraging MCP's error handling capabilities. Phase 2 smoke tests validate that tools don't raise exceptions, but error scenarios (timeouts, malformed VQL, non-existent resources, invalid parameters) are untested.

The standard approach uses three layers:
1. **Input validation layer** - Validate parameters before execution (negative limits, empty IDs, malformed syntax)
2. **gRPC exception layer** - Catch grpc.RpcError, map StatusCode to actionable messages, implement retry with exponential backoff
3. **MCP error layer** - Return structured error responses (not ToolError for FastMCP compatibility)

**Primary recommendation:** Wrap all MCP tool functions with input validation, gRPC exception handling that maps StatusCode to user-friendly messages, and retry logic for transient failures (UNAVAILABLE, DEADLINE_EXCEEDED). Return structured JSON error responses instead of raising exceptions to maintain compatibility with the current test infrastructure that checks for `{"error": "..."}` patterns.

## Standard Stack

The established libraries/tools for error handling in Python gRPC/MCP applications:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| grpcio | >=1.60.0 | gRPC Python library with StatusCode enums | Already in project. Provides 16 standard StatusCode values (UNAVAILABLE, DEADLINE_EXCEEDED, NOT_FOUND, etc.) for error handling. Official gRPC implementation. |
| tenacity | >=8.2.3 | Retry logic with exponential backoff | Industry standard for Python retry patterns. Provides @retry decorator with wait_exponential, stop_after_attempt, retry_if_exception_type. Used by major projects (OpenAI SDK, AWS SDK). |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mcp | >=1.0.0 | MCP SDK types (TextContent) | Already in project. Use for structured error responses. Note: FastMCP masks unexpected exceptions by default. |
| grpcio-status | >=1.60.0 | Rich gRPC status support | Optional. Use if need Google's extended error model with detailed error messages. Currently not needed - standard StatusCode sufficient. |

### Validation (Choose One)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Built-in validation | N/A | Manual parameter checking | Recommended for this project. Minimal dependencies, explicit control, clear error messages. Good fit for ~10 validation rules. |
| pydantic | >=2.0 | Schema-based validation | Overkill for simple parameter validation. Use if building typed API client or need complex nested validation. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | backoff library | backoff (2.2.1) is simpler but less flexible. tenacity supports combining strategies (fixed + jitter), stop conditions, and better asyncio support. Choose backoff only if <5 retry scenarios. |
| Built-in validation | pydantic | Pydantic adds dependency and requires BaseModel classes for every input. Built-in validation with clear if/raise is more explicit for small parameter sets. |
| JSON error objects | FastMCP ToolError | Current tests expect `{"error": "..."}` JSON. ToolError would require test infrastructure changes. Keep JSON pattern for consistency. |

**Installation:**
```bash
# Add to pyproject.toml dependencies
pip install tenacity>=8.2.3

# grpcio already present at >=1.60.0
# mcp already present at >=1.0.0
```

## Architecture Patterns

### Recommended Error Handling Structure
```
src/megaraptor_mcp/
├── tools/
│   ├── clients.py           # Add input validation, gRPC error handling
│   ├── artifacts.py         # Add input validation, gRPC error handling
│   ├── hunts.py            # Add input validation, gRPC error handling
│   ├── flows.py            # Add input validation, gRPC error handling
│   ├── vql.py              # Enhance existing try/except with StatusCode mapping
│   └── deployment.py       # Add validation, enhance ImportError handling
├── error_handling.py        # NEW: Shared error handling utilities
│   ├── validators.py        # Parameter validation functions
│   ├── grpc_handlers.py    # gRPC exception mapping
│   └── retry_decorators.py # Retry logic decorators
└── client.py               # Add timeout parameters, retry logic to query()
```

### Pattern 1: Input Validation Before Execution
**What:** Validate all user inputs before making gRPC calls. Check for negative limits, empty IDs, invalid enum values, malformed syntax patterns.

**When to use:** Every MCP tool that accepts user parameters. Validate at tool entry point before any API calls.

**Example:**
```python
# src/megaraptor_mcp/error_handling/validators.py
def validate_client_id(client_id: str) -> str:
    """Validate Velociraptor client ID format.

    Args:
        client_id: Client ID to validate

    Returns:
        Validated client ID

    Raises:
        ValueError: If client_id is invalid
    """
    if not client_id:
        raise ValueError("client_id cannot be empty")

    if not client_id.startswith("C."):
        raise ValueError(
            f"Invalid client_id format: '{client_id}'. "
            "Must start with 'C.' (e.g., 'C.1234567890abcdef')"
        )

    return client_id


def validate_limit(limit: int, min_val: int = 1, max_val: int = 10000) -> int:
    """Validate result limit parameter.

    Args:
        limit: Number of results to return
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated limit

    Raises:
        ValueError: If limit is out of range
    """
    if limit < min_val:
        raise ValueError(
            f"limit must be at least {min_val}, got {limit}"
        )

    if limit > max_val:
        raise ValueError(
            f"limit cannot exceed {max_val}, got {limit}. "
            f"Use pagination for larger result sets."
        )

    return limit


def validate_vql_syntax_basics(query: str) -> str:
    """Basic VQL syntax validation.

    Args:
        query: VQL query string

    Returns:
        Query string

    Raises:
        ValueError: If query has obvious syntax errors
    """
    if not query or not query.strip():
        raise ValueError("VQL query cannot be empty")

    # VQL doesn't use semicolons
    if query.rstrip().endswith(";"):
        raise ValueError(
            "VQL syntax error: Remove semicolon at end of query. "
            "VQL does not use semicolons like SQL."
        )

    # Check for basic SELECT FROM structure
    query_upper = query.upper()
    if "SELECT" not in query_upper:
        raise ValueError(
            "VQL query must contain SELECT statement. "
            "Example: SELECT * FROM clients()"
        )

    return query
```

### Pattern 2: gRPC Exception Handling with StatusCode Mapping
**What:** Catch grpc.RpcError, extract StatusCode, map to user-friendly messages with actionable guidance.

**When to use:** Wrap all client.query() calls and gRPC API interactions.

**Example:**
```python
# src/megaraptor_mcp/error_handling/grpc_handlers.py
import grpc
from typing import Optional

def map_grpc_error(error: grpc.RpcError, operation: str) -> dict:
    """Map gRPC error to user-friendly error response.

    Args:
        error: gRPC error
        operation: Description of what was being attempted

    Returns:
        Error response dict with 'error' and 'hint' fields
    """
    status_code = error.code()
    details = error.details() if hasattr(error, 'details') else str(error)

    # Map status codes to user messages
    # Source: https://grpc.github.io/grpc/python/grpc.html
    error_map = {
        grpc.StatusCode.UNAVAILABLE: {
            "error": f"Velociraptor server unavailable during {operation}",
            "hint": "Check that the Velociraptor server is running and accessible. "
                   "Verify VELOCIRAPTOR_CONFIG_PATH points to valid API config.",
        },
        grpc.StatusCode.DEADLINE_EXCEEDED: {
            "error": f"Operation timed out: {operation}",
            "hint": "Query took too long to complete. Try reducing the limit parameter "
                   "or narrowing the search criteria.",
        },
        grpc.StatusCode.NOT_FOUND: {
            "error": f"Resource not found: {operation}",
            "hint": "The requested client, hunt, flow, or artifact does not exist. "
                   "Verify the ID is correct.",
        },
        grpc.StatusCode.INVALID_ARGUMENT: {
            "error": f"Invalid parameter: {operation}",
            "hint": f"Server rejected the request. Details: {details}",
        },
        grpc.StatusCode.UNAUTHENTICATED: {
            "error": "Authentication failed",
            "hint": "API credentials are invalid or expired. "
                   "Regenerate API config and update VELOCIRAPTOR_CONFIG_PATH.",
        },
        grpc.StatusCode.PERMISSION_DENIED: {
            "error": f"Permission denied: {operation}",
            "hint": "API credentials lack permission for this operation. "
                   "Check user roles in Velociraptor GUI.",
        },
        grpc.StatusCode.INTERNAL: {
            "error": f"Server internal error during {operation}",
            "hint": f"Velociraptor server encountered an error. Details: {details}",
        },
    }

    mapped = error_map.get(
        status_code,
        {
            "error": f"Unexpected error during {operation}: {status_code.name}",
            "hint": f"Details: {details}",
        }
    )

    # Add status code for debugging
    mapped["grpc_status"] = status_code.name

    return mapped


def handle_grpc_call(operation: str):
    """Decorator to handle gRPC errors with user-friendly messages.

    Usage:
        @handle_grpc_call("listing clients")
        def list_clients(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except grpc.RpcError as e:
                error_response = map_grpc_error(e, operation)
                return [TextContent(
                    type="text",
                    text=json.dumps(error_response, indent=2)
                )]
            except ValueError as e:
                # Input validation errors
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "hint": "Check parameter format and try again.",
                    }, indent=2)
                )]
        return wrapper
    return decorator
```

### Pattern 3: Retry Logic for Transient Failures
**What:** Automatically retry operations that fail due to transient issues (network timeouts, server temporarily unavailable).

**When to use:** For client.query() calls and any network operations. Don't retry on validation errors or PERMISSION_DENIED.

**Example:**
```python
# src/megaraptor_mcp/client.py (enhanced)
import grpc
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
)

def is_retryable_grpc_error(exception):
    """Check if gRPC error is transient and retryable.

    Retry on:
    - UNAVAILABLE (server down/restarting)
    - DEADLINE_EXCEEDED (timeout)
    - RESOURCE_EXHAUSTED (rate limiting)

    Don't retry on:
    - INVALID_ARGUMENT (bad parameters)
    - NOT_FOUND (resource doesn't exist)
    - PERMISSION_DENIED (auth issue)
    - UNAUTHENTICATED (credential issue)
    """
    if not isinstance(exception, grpc.RpcError):
        return False

    retryable_codes = {
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
    }

    return exception.code() in retryable_codes


class VelociraptorClient:
    """Client for interacting with Velociraptor server via gRPC API."""

    @retry(
        retry=retry_if_exception(is_retryable_grpc_error),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def query(
        self,
        vql: str,
        env: Optional[dict[str, Any]] = None,
        org_id: Optional[str] = None,
        timeout: Optional[float] = 30.0,  # NEW: Add timeout parameter
    ) -> list[dict[str, Any]]:
        """Execute a VQL query and return results with retry logic.

        Automatically retries on transient failures:
        - Network unavailable (3 attempts with exponential backoff)
        - Timeout exceeded (3 attempts)
        - Rate limiting (3 attempts)

        Does NOT retry on:
        - Invalid VQL syntax
        - Permission denied
        - Resource not found

        Args:
            vql: The VQL query to execute
            env: Optional environment variables for the query
            org_id: Optional organization ID for multi-tenant setups
            timeout: Query timeout in seconds (default 30.0)

        Returns:
            List of result rows as dictionaries

        Raises:
            grpc.RpcError: If query fails after retries
        """
        if self._stub is None:
            self.connect()

        # Build the request
        env_list = []
        if env:
            for key, value in env.items():
                env_list.append(
                    api_pb2.VQLEnv(key=key, value=json.dumps(value))
                )

        request = api_pb2.VQLCollectorArgs(
            Query=[api_pb2.VQLRequest(VQL=vql)],
            env=env_list,
            org_id=org_id or "",
        )

        # Execute with timeout
        results = []
        for response in self._stub.Query(request, timeout=timeout):
            if response.Response:
                try:
                    rows = json.loads(response.Response)
                    if isinstance(rows, list):
                        results.extend(rows)
                    else:
                        results.append(rows)
                except json.JSONDecodeError:
                    pass

        return results
```

### Pattern 4: VQL Syntax Error Hints
**What:** Parse VQL error messages from Velociraptor and provide correction hints.

**When to use:** When client.query() fails with INVALID_ARGUMENT or returns VQL error in response.

**Example:**
```python
# src/megaraptor_mcp/error_handling/vql_helpers.py
def extract_vql_error_hint(error_message: str) -> str:
    """Extract actionable hint from VQL error message.

    Common VQL errors:
    - "Symbol X not found" -> suggest available symbols
    - "Syntax error" -> suggest checking VQL documentation
    - "Expected )" -> suggest balancing parentheses

    Args:
        error_message: Raw error from Velociraptor

    Returns:
        User-friendly hint
    """
    error_lower = error_message.lower()

    if "symbol" in error_lower and "not found" in error_lower:
        return (
            "VQL plugin or function not found. "
            "Check plugin name spelling and ensure artifact is installed. "
            "Use 'vql_help' tool to see available plugins."
        )

    if "syntax error" in error_lower:
        return (
            "VQL syntax error. Common issues:\n"
            "- VQL doesn't use semicolons (remove trailing ;)\n"
            "- Use keyword arguments: plugin(arg=value) not plugin(value)\n"
            "- Check parentheses balance"
        )

    if "expected" in error_lower and ")" in error_lower:
        return (
            "Missing or extra parenthesis. "
            "Check that all opening '(' have matching closing ')'."
        )

    if "let" in error_lower and ("select" in error_lower or "from" in error_lower):
        return (
            "Cannot use LET inside SELECT. "
            "LET is a separate statement. Use: LET x = ... SELECT ... FROM ..."
        )

    return "Check VQL syntax. Use 'vql_help(topic=\"syntax\")' for VQL reference."
```

### Pattern 5: Resource Not Found (404-Style) Errors
**What:** When querying for specific resource (client, hunt, flow) returns empty results, return structured 404-style error.

**When to use:** In get_client_info, get_hunt_results, get_flow_status, etc. when results list is empty.

**Example:**
```python
# src/megaraptor_mcp/tools/clients.py (enhanced)
@mcp.tool()
async def get_client_info(client_id: str) -> list[TextContent]:
    """Get detailed information about a specific Velociraptor client.

    Args:
        client_id: The client ID (e.g., 'C.1234567890abcdef')

    Returns:
        Detailed client information including hardware, OS, IP addresses.
    """
    try:
        # Validate input
        client_id = validate_client_id(client_id)

        client = get_client()
        vql = f"SELECT * FROM clients(client_id='{client_id}')"
        results = client.query(vql)

        if not results:
            # 404-style error
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Client not found: {client_id}",
                    "hint": (
                        "Client does not exist or has never connected. "
                        "Use 'list_clients' to see available clients."
                    ),
                    "resource_type": "client",
                    "resource_id": client_id,
                }, indent=2)
            )]

        return [TextContent(
            type="text",
            text=json.dumps(results[0], indent=2, default=str)
        )]

    except grpc.RpcError as e:
        error_response = map_grpc_error(e, f"fetching client {client_id}")
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

    except ValueError as e:
        # Validation error
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "hint": "Check client_id format and try again.",
            }, indent=2)
        )]
```

### Anti-Patterns to Avoid
- **Bare except:** Never use `except Exception` without specific handling. Catch specific exception types (grpc.RpcError, ValueError, etc.)
- **Silent failures:** Don't silently ignore errors. Always return error response or raise exception.
- **Stack traces in responses:** Don't include Python stack traces in error messages. Map to user-friendly messages.
- **Retry on all errors:** Don't retry authentication errors, validation errors, or "not found" errors. Only retry transient failures.
- **Generic error messages:** Don't return "An error occurred". Provide specific, actionable messages.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry logic with backoff | Custom sleep() loops with counters | tenacity library | tenacity handles exponential backoff, jitter, max attempts, exception filtering, and async. Custom implementations miss edge cases (thundering herd, max backoff ceiling). |
| gRPC status mapping | Custom if/elif chains for error codes | grpc.StatusCode enum + dict mapping | gRPC defines 16 standard status codes. Custom mapping inevitably incomplete. Use official enum. |
| Parameter validation | Ad-hoc string checks in each tool | Centralized validator functions | Duplicate validation logic leads to inconsistency. Centralize in validators.py for reusability and testing. |
| Timeout handling | Manual timeout tracking | grpc timeout parameter + tenacity | gRPC has built-in timeout. Don't build custom timeout tracking. |
| VQL syntax parsing | Regex-based VQL validator | Basic pattern checks + server error parsing | VQL grammar is complex. Don't build full parser. Check obvious mistakes (semicolons, LET in SELECT), let server validate, parse server errors. |

**Key insight:** Error handling in distributed systems (gRPC) has many edge cases - retries need jitter to avoid thundering herd, timeouts need to be set at multiple layers, status codes have specific semantics. Use battle-tested libraries (tenacity, grpc) rather than custom implementations.

## Common Pitfalls

### Pitfall 1: Not Distinguishing Transient vs Permanent Errors
**What goes wrong:** Code retries on PERMISSION_DENIED or INVALID_ARGUMENT, wasting time on errors that will never succeed.

**Why it happens:** Developers assume "retry on any error" is safer. But retrying authentication failures or bad parameters just delays the inevitable failure.

**How to avoid:** Explicitly define retryable status codes: UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED. Never retry: PERMISSION_DENIED, UNAUTHENTICATED, INVALID_ARGUMENT, NOT_FOUND.

**Warning signs:**
- Logs show repeated auth failures
- Tests hang retrying on validation errors
- Error messages say "failed after 3 attempts" when error was permanent

### Pitfall 2: Timeout Not Set at All Layers
**What goes wrong:** Request hangs forever even though retry logic has timeout. gRPC default timeout is infinite.

**Why it happens:** Developers set timeout in retry logic but forget to pass timeout to gRPC call. gRPC waits indefinitely.

**How to avoid:** Set timeout at both layers: (1) grpc call timeout parameter, (2) tenacity stop_after_delay or test timeout. Default gRPC timeout to 30 seconds.

**Warning signs:**
- Tests hang and timeout after pytest-timeout (2 minutes)
- Retry logic never triggers because gRPC never returns
- "waiting for response" in logs with no progress

### Pitfall 3: Exposing Internal Error Details
**What goes wrong:** Python stack traces, file paths, or internal variable names leak to users in error messages.

**Why it happens:** Using str(exception) directly in error response includes full traceback.

**How to avoid:** Map exceptions to user messages. Extract only error.details() from gRPC errors. Never include traceback in JSON response.

**Warning signs:**
- Error messages contain "File /src/megaraptor_mcp/..."
- Stack traces visible in test output
- Variable names like "vql_query_obj" in error messages

### Pitfall 4: Validating After Calling API
**What goes wrong:** Invalid parameters reach Velociraptor server, causing cryptic VQL errors instead of clear validation messages.

**Why it happens:** Easier to skip validation and let server reject. But server errors are less helpful.

**How to avoid:** Validate all parameters at tool entry point before any API calls. Use validator functions for consistent checking.

**Warning signs:**
- Error messages like "VQL syntax error at line 1 char 42"
- Users pass negative limits and get VQL error instead of "limit must be positive"
- Empty client_id causes "Symbol not found" instead of "client_id cannot be empty"

### Pitfall 5: No Actionable Hints in Error Messages
**What goes wrong:** Error says "Operation failed" without explaining why or what to do.

**Why it happens:** Developers return raw error.details() without interpretation.

**How to avoid:** Every error response includes 'hint' field with actionable guidance. Map status codes to hints. For VQL errors, parse message and suggest fix.

**Warning signs:**
- Error messages end with period (no suggested action)
- Users ask "what does UNAVAILABLE mean?"
- Same question repeated in multiple test failures

### Pitfall 6: Retry Without Exponential Backoff
**What goes wrong:** All retries happen immediately (0.1s apart), causing "thundering herd" when server restarts.

**Why it happens:** Simple retry loop: `for i in range(3): try... except... continue`. No delay between attempts.

**How to avoid:** Use tenacity with wait_exponential. First retry after 1s, second after 2s, third after 4s (with jitter).

**Warning signs:**
- Server logs show burst of requests all at once
- Retry attempts all fail with same timestamp
- Tests fail due to rate limiting

## Code Examples

Verified patterns from official sources and current project:

### Complete MCP Tool with Error Handling
```python
# src/megaraptor_mcp/tools/clients.py (full example)
import json
import grpc
from typing import Optional
from mcp.types import TextContent

from ..server import mcp
from ..client import get_client
from ..error_handling.validators import validate_client_id, validate_limit
from ..error_handling.grpc_handlers import map_grpc_error


@mcp.tool()
async def list_clients(
    search: Optional[str] = None,
    limit: int = 100,
) -> list[TextContent]:
    """Search and list Velociraptor clients (endpoints).

    Args:
        search: Optional search query. Supports prefixes like 'label:' and 'host:'.
               Examples: 'label:production', 'host:workstation-01', 'windows'
        limit: Maximum number of clients to return (default 100, max 10000)

    Returns:
        List of clients with their ID, hostname, OS, labels, and last seen time.
    """
    try:
        # Input validation
        limit = validate_limit(limit, min_val=1, max_val=10000)

        client = get_client()

        if search:
            # Validate search doesn't contain VQL injection attempts
            if ";" in search or "--" in search:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Invalid search query",
                        "hint": "Search cannot contain ';' or '--' characters.",
                    }, indent=2)
                )]
            vql = f"SELECT * FROM clients(search='{search}') LIMIT {limit}"
        else:
            vql = f"SELECT * FROM clients() LIMIT {limit}"

        results = client.query(vql)

        # Format the results
        formatted = []
        for row in results:
            client_info = {
                "client_id": row.get("client_id", ""),
                "hostname": row.get("os_info", {}).get("hostname", ""),
                "os": row.get("os_info", {}).get("system", ""),
                "release": row.get("os_info", {}).get("release", ""),
                "labels": row.get("labels", []),
                "last_seen_at": row.get("last_seen_at", ""),
                "first_seen_at": row.get("first_seen_at", ""),
                "last_ip": row.get("last_ip", ""),
            }
            formatted.append(client_info)

        return [TextContent(
            type="text",
            text=json.dumps(formatted, indent=2)
        )]

    except grpc.RpcError as e:
        error_response = map_grpc_error(e, "listing clients")
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

    except ValueError as e:
        # Validation errors
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "hint": "Check parameter values and try again.",
            }, indent=2)
        )]

    except Exception as e:
        # Unexpected errors - log but don't expose internals
        # TODO: Add logging here
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Unexpected error listing clients",
                "hint": "Check Velociraptor server logs for details.",
            }, indent=2)
        )]
```

### VQL Tool with Syntax Validation and Error Hints
```python
# src/megaraptor_mcp/tools/vql.py (enhanced)
import json
import grpc
from typing import Any, Optional
from mcp.types import TextContent

from ..server import mcp
from ..client import get_client
from ..error_handling.validators import validate_vql_syntax_basics
from ..error_handling.grpc_handlers import map_grpc_error
from ..error_handling.vql_helpers import extract_vql_error_hint


@mcp.tool()
async def run_vql(
    query: str,
    env: Optional[dict[str, Any]] = None,
    max_rows: int = 10000,
    org_id: Optional[str] = None,
) -> list[TextContent]:
    """Execute an arbitrary VQL (Velociraptor Query Language) query.

    VQL is the query language used by Velociraptor for forensic analysis.
    It follows a SQL-like syntax with plugins instead of tables.

    Common VQL patterns:
    - SELECT * FROM info()  -- Get server info
    - SELECT * FROM clients()  -- List all clients
    - SELECT * FROM Artifact.Windows.System.Pslist()  -- Run artifact

    Args:
        query: The VQL query to execute
        env: Optional environment variables to pass to the query.
             Use this to safely pass dynamic values instead of string interpolation.
        max_rows: Maximum number of rows to return (default 10000)
        org_id: Optional organization ID for multi-tenant deployments

    Returns:
        Query results as JSON.
    """
    try:
        # Validate VQL syntax basics
        query = validate_vql_syntax_basics(query)

        # Add LIMIT if not already present
        query_upper = query.upper()
        if "LIMIT" not in query_upper:
            query = f"{query.rstrip(';')} LIMIT {max_rows}"

        client = get_client()
        results = client.query(query, env=env, org_id=org_id)

        return [TextContent(
            type="text",
            text=json.dumps({
                "query": query,
                "row_count": len(results),
                "results": results,
            }, indent=2, default=str)
        )]

    except ValueError as e:
        # Validation error
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "query": query,
            }, indent=2)
        )]

    except grpc.RpcError as e:
        # gRPC error - might be VQL syntax error from server
        error_response = map_grpc_error(e, "executing VQL query")

        # Try to extract VQL-specific hint
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            error_details = e.details() if hasattr(e, 'details') else ""
            vql_hint = extract_vql_error_hint(error_details)
            error_response["vql_hint"] = vql_hint

        error_response["query"] = query

        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Unexpected error executing VQL",
                "hint": str(e),
                "query": query,
            }, indent=2)
        )]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bare try/except Exception | Specific exception types (grpc.RpcError, ValueError) | 2024-2025 | Better error identification and handling. Can distinguish transient vs permanent errors. |
| Manual retry loops | tenacity library with @retry decorator | 2023-2024 | Standardized backoff strategies, jitter support, cleaner code. Prevents thundering herd. |
| Generic "error occurred" messages | Structured errors with 'error' and 'hint' fields | 2025 | AI assistants can parse and act on structured errors. Users get actionable guidance. |
| FastMCP ToolError for all errors | JSON error objects with {"error": "..."} pattern | Project-specific | Maintains compatibility with existing test infrastructure that checks for error field. |
| No timeout on gRPC calls | Explicit timeout parameter (30s default) | gRPC 1.60+ | Prevents infinite hangs. Required for reliable service. |
| Return Python traceback to user | Map to user-friendly messages, hide internals | Security best practice | Prevents information leakage, improves UX. |

**Deprecated/outdated:**
- **FastMCP ToolError in this project**: While ToolError is FastMCP's recommended pattern, existing tests expect JSON `{"error": "..."}` responses. Using ToolError would require rewriting test infrastructure. Maintain JSON pattern for consistency.
- **grpcio-status for simple cases**: Rich error model (google.rpc.Status) is overkill when standard StatusCode + hint field suffices. Use only if need complex error metadata.
- **Pydantic for parameter validation**: FastMCP supports Pydantic models, but for simple validation (10-15 rules), manual checks are clearer and avoid dependency.

## Open Questions

Things that couldn't be fully resolved:

1. **VQL error message format**
   - What we know: Velociraptor returns VQL errors via gRPC INVALID_ARGUMENT status. Error message in details() field.
   - What's unclear: Exact format and consistency of VQL error messages. No official schema found.
   - Recommendation: Implement pattern matching for common errors (Symbol not found, Syntax error). Test against live server to refine patterns. Add catch-all hint for unmapped errors.

2. **Retry behavior during server restarts**
   - What we know: tenacity retries on UNAVAILABLE. Container restart takes ~30 seconds.
   - What's unclear: Whether 3 retries with exponential backoff (1s, 2s, 4s = 7s total) is enough for server restart scenario.
   - Recommendation: Start with 3 retries. Phase 6 deployment tests will validate. Increase to 5 retries if needed (1s, 2s, 4s, 8s, 16s = 31s total).

3. **Rate limiting behavior**
   - What we know: gRPC StatusCode includes RESOURCE_EXHAUSTED for rate limiting.
   - What's unclear: Whether Velociraptor implements rate limiting. No mention in docs.
   - Recommendation: Include RESOURCE_EXHAUSTED in retryable codes (defensive). If never encountered, remove in future optimization.

4. **Deployment tool error handling**
   - What we know: Deployment tools check for missing dependencies (ImportError). Expected to fail gracefully with "Deployment not found" for non-existent IDs.
   - What's unclear: Whether Docker/SSH errors should be retried. Failed deployments might leave partial state.
   - Recommendation: Don't retry deployment operations - they're not idempotent. Return clear error + cleanup instructions. Phase 6 will test deployment error scenarios.

## Sources

### Primary (HIGH confidence)
- [gRPC Python Documentation - StatusCode and RpcError](https://grpc.github.io/grpc/python/grpc.html) - Official gRPC Python API reference. Verified StatusCode enum values and exception types.
- [gRPC Error Handling Guide](https://grpc.io/docs/guides/error/) - Official gRPC error handling best practices. Verified status code semantics and error model.
- [Tenacity Documentation](https://tenacity.readthedocs.io/) - Official Python retry library docs. Verified exponential backoff patterns.
- Project codebase analysis - Direct inspection of current error handling in vql.py, deployment.py, clients.py, and test infrastructure.

### Secondary (MEDIUM confidence)
- [MCP Error Handling Best Practices](https://medium.com/@sureshddm/mcp-error-handling-dont-let-your-tools-fail-silently-1b5e02fabe4c) - MCP error handling patterns for 2026. Verified ToolError usage and mask_error_details.
- [Velociraptor VQL Documentation](https://docs.velociraptor.app/docs/vql/) - VQL syntax rules. Verified no semicolons, keyword arguments required.
- [Velociraptor 0.6.5 Release Notes](https://www.rapid7.com/blog/post/2022/06/24/velociraptor-version-0-6-5-table-transformations-multi-lingual-support-and-better-vql-error-handling-let-you-dig-deeper-than-ever/) - VQL error handling improvements. Verified log() function with ERROR level.
- [Python Input Validation Best Practices 2026](https://www.symbioticsec.ai/blog/validating-inputs-input-sanitization-step-by-step-guide) - Input sanitization patterns. Verified whitelisting approach and early validation.
- [Pydantic v2 Validation Patterns](https://docs.pydantic.dev/latest/concepts/validators/) - Pydantic validation options. Decision to use manual validation instead.

### Tertiary (LOW confidence)
- [GitHub - modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) - MCP SDK repository. Limited error handling documentation found.
- [PyVelociraptor GitHub](https://github.com/Velocidex/pyvelociraptor) - pyvelociraptor client library. No specific error handling examples found.
- Community discussions on gRPC retry patterns and VQL error messages - Multiple sources agree on patterns but no single authoritative source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - grpcio and tenacity are industry standards with official documentation
- Architecture patterns: HIGH - Patterns verified against gRPC docs, tested in similar projects
- VQL error hints: MEDIUM - Based on Velociraptor docs but exact error format needs validation
- Retry parameters: MEDIUM - Standard values but may need tuning based on deployment testing
- Deployment error handling: LOW - Needs validation in Phase 6 deployment tests

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days for stable patterns, gRPC and tenacity are mature)

**Phase dependencies:**
- Depends on Phase 2 smoke tests for baseline tool behavior
- Informs Phase 4 OS-specific artifact error handling
- Validates in Phase 6 deployment scenarios
