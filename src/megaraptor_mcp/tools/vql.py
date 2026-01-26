"""
VQL query tool for Velociraptor MCP.

Provides a tool for executing arbitrary VQL (Velociraptor Query Language) queries.
"""

import grpc
import json
from typing import Any, Optional

from mcp.types import TextContent

from ..server import mcp
from ..client import get_client
from ..error_handling import (
    validate_vql_syntax_basics,
    validate_limit,
    map_grpc_error,
    extract_vql_error_hint,
)


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
    - SELECT * FROM pslist()  -- List processes (client artifact)
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
        # Input validation
        if not query or not query.strip():
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "query parameter is required and cannot be empty"
                })
            )]

        max_rows = validate_limit(max_rows)
        query = validate_vql_syntax_basics(query)

        # Add LIMIT if not already present and query doesn't have one
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

    except grpc.RpcError as e:
        error_response = map_grpc_error(e, "VQL query execution")

        # For INVALID_ARGUMENT errors, try to extract VQL-specific hints
        if error_response.get("grpc_status") == "INVALID_ARGUMENT":
            error_message = str(e)
            vql_hint = extract_vql_error_hint(error_message)
            if vql_hint:
                error_response["vql_hint"] = vql_hint

        error_response["query"] = query
        return [TextContent(
            type="text",
            text=json.dumps(error_response)
        )]

    except ValueError as e:
        # Validation errors
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "hint": "Check VQL syntax and max_rows parameter"
            })
        )]

    except Exception:
        # Generic errors - don't expose internals
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to execute VQL query",
                "hint": "Check VQL syntax and Velociraptor server connection"
            })
        )]


@mcp.tool()
async def vql_help(
    topic: Optional[str] = None,
) -> list[TextContent]:
    """Get help on VQL (Velociraptor Query Language).

    Args:
        topic: Optional topic to get help on. Options:
               - 'syntax': VQL syntax basics
               - 'plugins': Common VQL plugins
               - 'functions': Common VQL functions
               - 'examples': Example queries

    Returns:
        Help text for the requested topic.
    """
    help_content = {
        "syntax": """
# VQL Syntax Basics

VQL follows a SQL-like syntax:

```
SELECT column1, column2, ...
FROM plugin(arg1=value1, arg2=value2, ...)
WHERE condition
ORDER BY column
LIMIT n
```

Key differences from SQL:
- Uses plugins instead of tables
- Plugins are function calls with named arguments
- Supports LET for variable assignment
- Supports foreach() for iteration
""",
        "plugins": """
# Common VQL Plugins

## Client Information
- clients() - List/search clients
- client_info() - Get info about a specific client

## Collections
- collect_client() - Schedule artifact collection
- flows() - List collection flows
- source() - Get collection results

## Hunts
- hunt() - Create a hunt
- hunts() - List hunts
- hunt_results() - Get hunt results

## System Info (Client)
- info() - Basic system info
- pslist() - Process list
- netstat() - Network connections
- users() - User accounts

## File System (Client)
- glob() - File search with wildcards
- read_file() - Read file contents
- stat() - File metadata
- hash() - Calculate file hashes

## Windows Specific
- wmi() - WMI queries
- registry() - Registry access
- evtx() - Event log parsing
""",
        "functions": """
# Common VQL Functions

## String Functions
- format() - Format strings
- split() - Split string
- regex_replace() - Regex replacement
- base64encode/decode() - Base64 encoding

## Time Functions
- now() - Current timestamp
- timestamp() - Parse timestamp
- humanize() - Human-readable time

## Data Functions
- count() - Count rows
- enumerate() - Add row numbers
- filter() - Filter rows
- dict() - Create dictionary
- array() - Create array

## File Functions
- read_file() - Read file
- hash() - Calculate hash
- upload() - Upload file to server
""",
        "examples": """
# VQL Example Queries

## List all Windows clients
```
SELECT * FROM clients() WHERE os_info.system = 'windows'
```

## Find processes by name
```
SELECT * FROM pslist() WHERE Name =~ 'chrome'
```

## Search for files
```
SELECT * FROM glob(globs='C:/Users/*/Downloads/*.exe')
```

## Get recent event logs
```
SELECT * FROM Artifact.Windows.EventLogs.Evtx(
    EvtxGlob='%SystemRoot%/System32/Winevt/Logs/Security.evtx',
    StartDate=now() - 86400
)
```

## Collect artifact and wait for results
```
LET flow <= SELECT collect_client(
    client_id='C.xxx',
    artifacts='Windows.System.Pslist'
) FROM scope()

SELECT * FROM source(
    client_id='C.xxx',
    flow_id=flow[0].collect_client.flow_id
)
```
""",
    }

    if topic and topic in help_content:
        return [TextContent(
            type="text",
            text=help_content[topic]
        )]
    else:
        # Return overview of all topics
        overview = """
# VQL Help

VQL (Velociraptor Query Language) is the core query language for Velociraptor.

Available help topics:
- syntax: VQL syntax basics
- plugins: Common VQL plugins
- functions: Common VQL functions
- examples: Example queries

Use vql_help(topic='<topic>') to get detailed help on a specific topic.

For complete VQL reference, see: https://docs.velociraptor.app/vql_reference/
"""
        return [TextContent(
            type="text",
            text=overview
        )]
