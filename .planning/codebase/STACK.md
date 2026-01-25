# Technology Stack

**Analysis Date:** 2026-01-24

## Languages

**Primary:**
- Python 3.10+ - Core MCP server implementation and all business logic

**Secondary:**
- YAML - Configuration files for Velociraptor servers, clients, and Docker deployments
- Bash - Deployment scripts for cloud infrastructure (CloudFormation user data)
- JSON - Deployment metadata and credential storage

## Runtime

**Environment:**
- Python 3.10, 3.11, 3.12 (specified in `pyproject.toml` classifiers)

**Package Manager:**
- pip via setuptools
- Lockfile: Optional (project uses `pyproject.toml` without lock file in repo)

## Frameworks

**Core:**
- MCP (Model Context Protocol) 1.0.0+ - Server framework for AI assistant integration (`src/megaraptor_mcp/server.py`)
- pyvelociraptor 0.1.0+ - Velociraptor gRPC API Python client wrapper (`src/megaraptor_mcp/client.py`)

**Testing:**
- pytest 7.0.0+ - Test runner
- pytest-asyncio 0.21.0+ - Async test support
- pytest-timeout 2.2.0+ - Test timeout enforcement

**Build/Dev:**
- hatchling - Build backend
- cryptography 42.0.0+ - Certificate generation and credential encryption (deployment features)
- PyYAML 6.0+ - Configuration file parsing

## Key Dependencies

**Critical:**
- mcp 1.0.0+ - Provides Server, Tool, Resource, and Prompt APIs
- pyvelociraptor 0.1.0+ - Velociraptor gRPC API client with `api_pb2` and `api_pb2_grpc` modules
- grpcio 1.60.0+ - gRPC protocol implementation for Velociraptor API
- grpcio-tools 1.60.0+ - gRPC code generation tools
- pyyaml 6.0+ - Parses Velociraptor and deployment configuration files

**Infrastructure:**
- docker 7.0.0+ - Docker daemon interaction for container deployments (`src/megaraptor_mcp/deployment/deployers/docker_deployer.py`)
- paramiko 3.4.0+ - SSH client for remote agent deployment (`src/megaraptor_mcp/deployment/agents/ssh_deployer.py`)
- pywinrm 0.4.3+ - WinRM client for Windows remote management (`src/megaraptor_mcp/deployment/agents/winrm_deployer.py`)
- jinja2 3.1.0+ - Template engine for agent installer generation (`src/megaraptor_mcp/deployment/agents/installer_gen.py`)
- httpx 0.27.0+ - Async HTTP client for health checks (`src/megaraptor_mcp/deployment/deployers/docker_deployer.py`)
- boto3 1.34.0+ - AWS CloudFormation and EC2 interaction (optional, cloud extra)
- azure-mgmt-resource 23.0+ - Azure ARM template deployments (optional, cloud extra)
- azure-identity 1.15.0+ - Azure authentication via DefaultAzureCredential (optional, cloud extra)

## Configuration

**Environment:**
- VELOCIRAPTOR_CONFIG_PATH - Path to Velociraptor API client config file (YAML format)
- VELOCIRAPTOR_API_URL - Velociraptor API endpoint URL
- VELOCIRAPTOR_CLIENT_CERT - Client certificate content or file path
- VELOCIRAPTOR_CLIENT_KEY - Client private key content or file path
- VELOCIRAPTOR_CA_CERT - CA certificate content or file path
- AZURE_SUBSCRIPTION_ID - Azure subscription ID (optional, for cloud deployments)

**Configuration Files:**
- `pyproject.toml` - Project metadata, dependencies, and build configuration
- `.pytest.ini_options` - Pytest configuration with async mode and markers for `unit`, `integration`, and `slow` tests
- `tests/fixtures/server.config.yaml` - Test server configuration
- `tests/fixtures/client.config.yaml` - Test client configuration

## Platform Requirements

**Development:**
- Python 3.10+ interpreter
- git for version control

**Production:**
- Python 3.10+ runtime environment
- Access to Velociraptor server with gRPC API enabled
- For Docker deployments: Docker daemon
- For cloud deployments: AWS CLI or Azure CLI with appropriate credentials
- For remote deployments: SSH/WinRM access to target systems
- SSL/TLS certificates for mTLS communication with Velociraptor

## Architecture Notes

**Entry Points:**
- `megaraptor_mcp/server.py:main()` - CLI entry point defined in `pyproject.toml` as `megaraptor-mcp = "megaraptor_mcp.server:main"`
- `megaraptor_mcp/__main__.py` - Module-level execution support

**gRPC Communication:**
- Uses `grpcio.secure_channel()` with SSL credentials for TLS communication (`src/megaraptor_mcp/client.py`)
- Certificate management via `cryptography` library for PKI operations (`src/megaraptor_mcp/deployment/security/certificate_manager.py`)

**Async Execution:**
- asyncio-based concurrency throughout server and deployers
- All deployment operations are async (`deploy()`, `destroy()`, `health_check()`)

---

*Stack analysis: 2026-01-24*
