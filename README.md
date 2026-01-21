# Megaraptor MCP

A Model Context Protocol (MCP) server that provides AI assistants with access to [Velociraptor](https://docs.velociraptor.app/) - the powerful digital forensics and incident response (DFIR) platform.

## Overview

Megaraptor MCP enables AI assistants like Claude to interact with Velociraptor servers for:

- **Endpoint Management**: Search, interrogate, and manage Velociraptor clients
- **Artifact Collection**: Schedule forensic artifact collection on endpoints
- **Threat Hunting**: Create and manage hunts across multiple endpoints
- **VQL Queries**: Execute arbitrary Velociraptor Query Language queries
- **Incident Response**: Pre-built DFIR workflow prompts for common scenarios

## Features

### MCP Tools (15 tools)

| Category | Tool | Description |
|----------|------|-------------|
| **Clients** | `list_clients` | Search and list Velociraptor endpoints |
| | `get_client_info` | Get detailed information about a client |
| | `label_client` | Add/remove labels from clients |
| | `quarantine_client` | Quarantine or release endpoints |
| **Artifacts** | `list_artifacts` | List available Velociraptor artifacts |
| | `get_artifact` | Get full artifact definition |
| | `collect_artifact` | Schedule artifact collection on a client |
| **Hunts** | `create_hunt` | Create a mass collection campaign |
| | `list_hunts` | List existing hunts |
| | `get_hunt_results` | Retrieve results from a hunt |
| | `modify_hunt` | Start, pause, stop, or archive hunts |
| **Flows** | `list_flows` | List collection flows for a client |
| | `get_flow_results` | Get results from a collection |
| | `get_flow_status` | Check collection status |
| | `cancel_flow` | Cancel a running collection |
| **VQL** | `run_vql` | Execute arbitrary VQL queries |
| | `vql_help` | Get help on VQL syntax and plugins |

### MCP Resources

Browse Velociraptor data through standardized URIs:

- `velociraptor://clients` - Browse connected endpoints
- `velociraptor://clients/{client_id}` - View specific client details
- `velociraptor://hunts` - Browse hunt campaigns
- `velociraptor://hunts/{hunt_id}` - View specific hunt details
- `velociraptor://artifacts` - Browse available artifacts
- `velociraptor://server-info` - View server information

### MCP Prompts

Pre-built DFIR workflow prompts:

| Prompt | Description |
|--------|-------------|
| `investigate_endpoint` | Comprehensive endpoint investigation workflow |
| `threat_hunt` | Create and execute threat hunting campaigns |
| `triage_incident` | Rapid incident triage and scoping |
| `malware_analysis` | Analyze suspicious files or processes |
| `lateral_movement` | Detect lateral movement indicators |

## Installation

### Prerequisites

- Python 3.10 or higher
- A running Velociraptor server with API access enabled
- API client credentials (see [Configuration](#configuration))

### Install from source

```bash
git clone https://github.com/yourusername/megaraptor-mcp.git
cd megaraptor-mcp
pip install -e .
```

### Install dependencies

```bash
pip install mcp pyvelociraptor pyyaml grpcio
```

## Configuration

Megaraptor MCP supports two authentication methods:

### Option 1: Config File (Recommended)

1. Generate an API client config on your Velociraptor server:

```bash
velociraptor --config server.config.yaml config api_client \
    --name mcp-client \
    --role reader,investigator \
    api_client.yaml
```

2. Set the environment variable:

```bash
export VELOCIRAPTOR_CONFIG_PATH=/path/to/api_client.yaml
```

### Option 2: Environment Variables

Set individual configuration values:

```bash
export VELOCIRAPTOR_API_URL=https://velociraptor.example.com:8001
export VELOCIRAPTOR_CLIENT_CERT=/path/to/client.crt  # or PEM content
export VELOCIRAPTOR_CLIENT_KEY=/path/to/client.key   # or PEM content
export VELOCIRAPTOR_CA_CERT=/path/to/ca.crt          # or PEM content
```

### API Roles

Assign appropriate roles to your API client based on required capabilities:

| Role | Capabilities |
|------|--------------|
| `reader` | Read clients, artifacts, hunts, flows |
| `investigator` | Above + collect artifacts, create hunts |
| `administrator` | Full access (use with caution) |

## Usage

### Running the Server

```bash
# Using the installed command
megaraptor-mcp

# Or as a Python module
python -m megaraptor_mcp
```

### Claude Desktop Integration

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "velociraptor": {
      "command": "python",
      "args": ["-m", "megaraptor_mcp"],
      "env": {
        "VELOCIRAPTOR_CONFIG_PATH": "/path/to/api_client.yaml"
      }
    }
  }
}
```

### Example Interactions

**List connected endpoints:**
```
Use the list_clients tool to show all Windows endpoints
```

**Investigate an endpoint:**
```
Use the investigate_endpoint prompt for client C.1234567890abcdef
```

**Create a threat hunt:**
```
Create a hunt for the file hash a1b2c3d4e5f6... across all endpoints
```

**Run custom VQL:**
```
Run this VQL query: SELECT * FROM pslist() WHERE Name =~ 'suspicious'
```

## VQL Reference

VQL (Velociraptor Query Language) is the core query language. Common patterns:

```sql
-- List all clients
SELECT * FROM clients()

-- Search for clients by hostname
SELECT * FROM clients(search='host:workstation')

-- Get running processes from collected data
SELECT * FROM source(client_id='C.xxx', flow_id='F.xxx')

-- Create a hunt
SELECT hunt(artifacts='Windows.System.Pslist', description='Process audit')
FROM scope()
```

For complete VQL reference, see: https://docs.velociraptor.app/vql_reference/

## Project Structure

```
megaraptor-mcp/
├── pyproject.toml           # Project configuration
├── README.md                # This file
├── src/
│   └── megaraptor_mcp/
│       ├── __init__.py      # Package initialization
│       ├── __main__.py      # Module entry point
│       ├── server.py        # MCP server main entry
│       ├── client.py        # Velociraptor API wrapper
│       ├── config.py        # Configuration handling
│       ├── tools/           # MCP tool implementations
│       │   ├── clients.py   # Client management tools
│       │   ├── artifacts.py # Artifact tools
│       │   ├── hunts.py     # Hunt management tools
│       │   ├── flows.py     # Flow/collection tools
│       │   └── vql.py       # VQL query tools
│       ├── resources/       # MCP resource implementations
│       │   └── resources.py
│       └── prompts/         # MCP prompt implementations
│           └── prompts.py
└── tests/                   # Test suite
    └── test_config.py
```

## Security Considerations

- **API Credentials**: Store API client credentials securely. The config file contains private keys.
- **Principle of Least Privilege**: Use the minimum required roles for API clients.
- **Network Security**: Ensure API connections are only accessible from trusted networks.
- **Audit Logging**: Velociraptor logs all API actions. Review logs regularly.
- **Quarantine Caution**: The quarantine tool can isolate endpoints from the network.

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Resources

- [Velociraptor Documentation](https://docs.velociraptor.app/)
- [Velociraptor GitHub](https://github.com/Velocidex/velociraptor)
- [VQL Reference](https://docs.velociraptor.app/vql_reference/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [pyvelociraptor](https://github.com/Velocidex/pyvelociraptor)

## Acknowledgments

- The Velociraptor team at Velocidex for creating an amazing DFIR platform
- Anthropic for the Model Context Protocol specification
