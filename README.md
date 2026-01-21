# Megaraptor MCP

A Model Context Protocol (MCP) server that provides AI assistants with access to [Velociraptor](https://docs.velociraptor.app/) - the powerful digital forensics and incident response (DFIR) platform.

## Overview

Megaraptor MCP enables AI assistants like Claude to interact with Velociraptor servers for:

- **Endpoint Management**: Search, interrogate, and manage Velociraptor clients
- **Artifact Collection**: Schedule forensic artifact collection on endpoints
- **Threat Hunting**: Create and manage hunts across multiple endpoints
- **VQL Queries**: Execute arbitrary Velociraptor Query Language queries
- **Incident Response**: Pre-built DFIR workflow prompts for common scenarios
- **Deployment Automation**: Deploy Velociraptor servers and agents across infrastructure (Docker, binary, cloud, GPO, SSH, WinRM, Ansible)

## Features

### MCP Tools (33 tools)

#### Core DFIR Tools (15 tools)

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

#### Deployment Tools (18 tools)

| Category | Tool | Description |
|----------|------|-------------|
| **Server Deployment** | `deploy_server_binary` | Deploy Velociraptor server as standalone binary |
| | `deploy_server_docker` | Deploy Velociraptor server using Docker |
| | `deploy_server_cloud` | Deploy Velociraptor server to AWS/Azure cloud |
| | `generate_server_config` | Generate server configuration with certificates |
| **Agent Deployment** | `deploy_agent_gpo` | Generate GPO deployment package for Windows |
| | `deploy_agent_winrm` | Deploy agents via WinRM to Windows endpoints |
| | `deploy_agent_ssh` | Deploy agents via SSH to Linux/macOS endpoints |
| | `deploy_agent_ansible` | Generate Ansible playbook for agent deployment |
| | `build_offline_collector` | Build standalone offline collector |
| | `generate_client_config` | Generate client configuration file |
| **Deployment Management** | `list_deployments` | List tracked deployment operations |
| | `get_deployment_status` | Get detailed status of a deployment |
| | `verify_deployment` | Verify deployment health and connectivity |
| | `rollback_deployment` | Rollback a failed deployment |
| **Credentials** | `store_credential` | Securely store deployment credentials |
| | `list_credentials` | List stored credential aliases |
| | `delete_credential` | Remove stored credentials |
| **Utilities** | `download_velociraptor` | Download Velociraptor binary for platform |

### MCP Resources

Browse Velociraptor data through standardized URIs:

- `velociraptor://clients` - Browse connected endpoints
- `velociraptor://clients/{client_id}` - View specific client details
- `velociraptor://hunts` - Browse hunt campaigns
- `velociraptor://hunts/{hunt_id}` - View specific hunt details
- `velociraptor://artifacts` - Browse available artifacts
- `velociraptor://server-info` - View server information
- `velociraptor://deployments` - Browse deployment operations and status

### MCP Prompts (8 prompts)

Pre-built DFIR and deployment workflow prompts:

| Prompt | Category | Description |
|--------|----------|-------------|
| `investigate_endpoint` | DFIR | Comprehensive endpoint investigation workflow |
| `threat_hunt` | DFIR | Create and execute threat hunting campaigns |
| `triage_incident` | DFIR | Rapid incident triage and scoping |
| `malware_analysis` | DFIR | Analyze suspicious files or processes |
| `lateral_movement` | DFIR | Detect lateral movement indicators |
| `deploy_velociraptor` | Deployment | Interactive Velociraptor deployment wizard |
| `scale_deployment` | Deployment | Plan enterprise-scale agent rollout |
| `troubleshoot_deployment` | Deployment | Diagnose and fix deployment issues |

## Installation

### Prerequisites

- Python 3.10 or higher
- A running Velociraptor server with API access enabled
- API client credentials (see [Configuration](#configuration))

### Install from source

```bash
git clone https://github.com/yourusername/megaraptor-mcp.git
cd megaraptor-mcp

# Core DFIR functionality only
pip install -e .

# With deployment features
pip install -e ".[deployment]"

# With cloud deployment (AWS/Azure)
pip install -e ".[cloud]"

# All features
pip install -e ".[all]"
```

### Optional Dependencies

| Extra | Features | Packages |
|-------|----------|----------|
| `deployment` | Agent/server deployment | paramiko, pywinrm, cryptography, jinja2 |
| `cloud` | Cloud deployment | boto3, azure-mgmt-compute |
| `all` | All features | All of the above |

### Install dependencies manually

```bash
# Core only
pip install mcp pyvelociraptor pyyaml grpcio

# For deployment features
pip install paramiko pywinrm cryptography jinja2

# For cloud deployment
pip install boto3 azure-mgmt-compute azure-identity
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

## Deployment Features

Megaraptor MCP includes comprehensive deployment automation for Velociraptor infrastructure.

### Server Deployment

Deploy Velociraptor servers using multiple methods:

| Method | Use Case | Command |
|--------|----------|---------|
| **Binary** | On-premise, direct installation | `deploy_server_binary` |
| **Docker** | Container environments, quick testing | `deploy_server_docker` |
| **Cloud** | AWS/Azure managed deployments | `deploy_server_cloud` |

**Example: Deploy Docker server**
```
Deploy a Velociraptor server using Docker on server.example.com with SSH credentials "prod-server"
```

### Agent Deployment

Multiple agent deployment methods for different environments:

| Method | Target | Best For |
|--------|--------|----------|
| **GPO** | Windows (Active Directory) | Enterprise Windows environments |
| **WinRM** | Windows (remote) | Windows without AD, smaller deployments |
| **SSH** | Linux/macOS | Unix-like systems |
| **Ansible** | Multi-platform | Large-scale infrastructure automation |
| **Offline Collector** | Air-gapped | Isolated networks, forensic collection |

**Example: Deploy agents via GPO**
```
Generate a GPO deployment package for 500 Windows endpoints using the enterprise profile
```

**Example: Deploy via Ansible**
```
Create an Ansible playbook to deploy Velociraptor agents to all Linux servers in inventory.yml
```

### Deployment Profiles

Pre-configured deployment profiles for different scenarios:

| Profile | Use Case | Characteristics |
|---------|----------|-----------------|
| **rapid** | Quick testing, POC | Minimal config, self-signed certs |
| **standard** | Production single-site | Proper certificates, standard hardening |
| **enterprise** | Large-scale multi-site | HA config, advanced monitoring, compliance |

### Credential Management

Securely store deployment credentials:

```
Store SSH credentials for prod-servers with username admin and key file ~/.ssh/prod_key
```

Credentials are encrypted at rest using AES-256-GCM with a locally-generated key.

### Offline Collectors

Build standalone collectors for air-gapped environments:

```
Build an offline collector for Windows that collects browser history and network connections
```

Collectors include embedded configuration and can run without network connectivity.

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
│       ├── prompts/         # MCP prompt implementations
│       │   └── prompts.py
│       └── deployment/      # Deployment automation
│           ├── __init__.py  # Deployment module init
│           ├── tools.py     # Deployment tool implementations
│           ├── server/      # Server deployment
│           │   ├── __init__.py
│           │   ├── binary.py    # Binary deployment
│           │   ├── docker.py    # Docker deployment
│           │   └── cloud.py     # Cloud deployment (AWS/Azure)
│           ├── agent/       # Agent deployment
│           │   ├── __init__.py
│           │   ├── gpo.py       # GPO package generation
│           │   ├── winrm.py     # WinRM deployment
│           │   ├── ssh.py       # SSH deployment
│           │   ├── ansible.py   # Ansible playbook generation
│           │   └── offline.py   # Offline collector builder
│           ├── credentials.py   # Secure credential storage
│           ├── config_generator.py  # Config file generation
│           └── profiles.py  # Deployment profiles (rapid/standard/enterprise)
└── tests/                   # Test suite
    ├── test_config.py
    └── test_deployment.py
```

## Security Considerations

### API Security

- **API Credentials**: Store API client credentials securely. The config file contains private keys.
- **Principle of Least Privilege**: Use the minimum required roles for API clients.
- **Network Security**: Ensure API connections are only accessible from trusted networks.
- **Audit Logging**: Velociraptor logs all API actions. Review logs regularly.
- **Quarantine Caution**: The quarantine tool can isolate endpoints from the network.

### Deployment Security

- **Credential Encryption**: Deployment credentials are encrypted at rest using AES-256-GCM. The `.keyfile` is generated locally and should be protected.
- **Generated Configs**: Server and client configurations contain CA certificates and private keys. These are excluded from git via `.gitignore`.
- **Ansible Playbooks**: Generated playbooks may contain CA certificates. Store securely and limit access.
- **Cloud Templates**: CloudFormation and ARM templates may contain sensitive parameters. Review before committing.
- **SSH/WinRM**: Use key-based authentication where possible. Avoid storing passwords in plain text.
- **Offline Collectors**: Built collectors contain embedded configuration. Protect as you would agent binaries.
- **GPO Packages**: MSI packages contain embedded configuration. Control access to distribution share.

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
