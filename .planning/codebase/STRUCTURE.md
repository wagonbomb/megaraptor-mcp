# Codebase Structure

**Analysis Date:** 2026-01-24

## Directory Layout

```
megaraptor-mcp/
├── src/                                # Source code root
│   └── megaraptor_mcp/                # Main package
│       ├── __init__.py                # Package init, version
│       ├── __main__.py                # CLI entry point (python -m)
│       ├── server.py                  # MCP server factory and stdio transport
│       ├── client.py                  # Velociraptor gRPC API client wrapper
│       ├── config.py                  # Configuration loading (file + env)
│       ├── tools/                     # MCP tool implementations (6 modules)
│       │   ├── __init__.py            # Tool module exports
│       │   ├── clients.py             # Client/endpoint management tools
│       │   ├── artifacts.py           # Artifact browsing and collection tools
│       │   ├── hunts.py               # Hunt creation and management tools
│       │   ├── flows.py               # Collection flow tracking tools
│       │   ├── vql.py                 # VQL query execution tools
│       │   └── deployment.py          # Server and agent deployment tools
│       ├── resources/                 # MCP resource implementations
│       │   ├── __init__.py            # Resource module exports
│       │   └── resources.py           # Resource list/read handlers
│       ├── prompts/                   # MCP prompt templates
│       │   ├── __init__.py            # Prompt module exports
│       │   └── prompts.py             # DFIR and deployment workflow prompts
│       └── deployment/                # Deployment automation infrastructure
│           ├── __init__.py            # Deployment module exports
│           ├── profiles.py            # Deployment profiles (rapid/standard/enterprise)
│           ├── deployers/             # Multi-target deployment implementations
│           │   ├── __init__.py        # Deployer exports
│           │   ├── base.py            # Abstract BaseDeployer interface
│           │   ├── docker_deployer.py # Docker container deployment
│           │   ├── binary_deployer.py # Binary SSH/WinRM deployment
│           │   └── cloud_deployer.py  # AWS and Azure cloud deployment
│           ├── agents/                # Agent deployment and generation
│           │   ├── __init__.py        # Agent module exports
│           │   ├── ssh_deployer.py    # SSH agent deployment
│           │   ├── winrm_deployer.py  # WinRM agent deployment
│           │   ├── ansible_gen.py     # Ansible playbook generation
│           │   ├── installer_gen.py   # Agent installer generation
│           │   └── offline_collector.py # Offline collector builder
│           ├── security/              # Cryptography and credential management
│           │   ├── __init__.py        # Security module exports
│           │   ├── certificate_manager.py # TLS certificate generation
│           │   └── credential_store.py    # Secure credential storage
│           └── templates/             # Jinja2 templates for config generation
│               └── __init__.py        # Templates module (contains embedded templates)
├── tests/                             # Test suite
│   ├── __init__.py                    # Test package init
│   ├── conftest.py                    # Pytest configuration and shared fixtures
│   ├── unit/                          # Unit tests (no external dependencies)
│   │   ├── __init__.py
│   │   ├── test_config.py             # Configuration loading tests
│   │   ├── test_certificate_manager.py # Certificate generation tests
│   │   ├── test_credential_store.py   # Credential storage tests
│   │   └── test_profiles.py           # Deployment profile tests
│   ├── integration/                   # Integration tests (requires Docker)
│   │   ├── __init__.py
│   │   ├── test_dfir_tools.py         # DFIR tool functionality tests
│   │   └── test_docker_deployment.py  # Docker deployment tests
│   ├── mocks/                         # Test mocks and fixtures
│   │   ├── __init__.py
│   │   └── mock_velociraptor.py       # Mock Velociraptor gRPC server
│   └── fixtures/                      # Test data and shared fixtures
│       └── __init__.py
├── scripts/                           # Utility scripts
│   └── test-lab.sh                    # Docker-based test lab setup script
├── .planning/                         # GSD planning documents
│   └── codebase/                      # Architecture/structure analysis (this directory)
├── pyproject.toml                     # Python package metadata and dependencies
├── README.md                          # Project overview and documentation
├── LICENSE                            # MIT license
└── .gitignore                         # Git ignore rules
```

## Directory Purposes

**src/megaraptor_mcp/:**
- Purpose: Main application package
- Contains: MCP server implementation, Velociraptor API client, tools, resources, prompts
- Key files: `server.py` (entry point), `client.py` (API wrapper), `config.py` (configuration)

**src/megaraptor_mcp/tools/:**
- Purpose: Tool implementations exposing Velociraptor capabilities as MCP tools
- Contains: Six tool modules + one deployment module (55KB+ of implementation)
- Key files: Individual register functions (`register_*_tools()`) that bind async handlers to server

**src/megaraptor_mcp/resources/:**
- Purpose: Resource browsing support for standard MCP resource URIs
- Contains: Resource list and read handlers for Velociraptor entities
- Key files: `resources.py` with `register_resources()` and URI handlers

**src/megaraptor_mcp/prompts/:**
- Purpose: Pre-built DFIR workflow templates
- Contains: Eight prompts (investigate_endpoint, threat_hunt, triage_incident, malware_analysis, lateral_movement, deploy_velociraptor, scale_deployment, troubleshoot_deployment)
- Key files: `prompts.py` with `register_prompts()` and PromptMessage builders

**src/megaraptor_mcp/deployment/:**
- Purpose: Multi-target deployment automation infrastructure
- Contains: Profiles, deployers (Docker/binary/cloud), agents (SSH/WinRM/Ansible/offline), security (certificates/credentials)
- Key files: `profiles.py` (profile definitions), `deployers/*.py` (deployment backends)

**src/megaraptor_mcp/deployment/deployers/:**
- Purpose: Abstract deployment implementation with pluggable backends
- Contains: Base interface and four concrete deployer implementations
- Key files: `base.py` (BaseDeployer), `docker_deployer.py`, `binary_deployer.py`, `cloud_deployer.py`

**src/megaraptor_mcp/deployment/agents/:**
- Purpose: Agent deployment and generation for different protocols
- Contains: SSH, WinRM, Ansible, installer generation, offline collector
- Key files: Individual deployer/generator modules

**src/megaraptor_mcp/deployment/security/:**
- Purpose: Cryptography and credential management for deployments
- Contains: Certificate generation with custom SANs, credential storage/retrieval
- Key files: `certificate_manager.py` (TLS generation), `credential_store.py` (secret storage)

**tests/:**
- Purpose: Test suite for unit, integration, and mock testing
- Contains: Pytest configuration, test modules, mock implementations, test fixtures
- Key files: `conftest.py` (shared fixtures), `unit/` and `integration/` test directories

**tests/unit/:**
- Purpose: Fast unit tests with no external dependencies
- Contains: Configuration, certificate, credential, and profile tests
- Key files: Individual test modules for each component

**tests/integration/:**
- Purpose: End-to-end testing with real Docker infrastructure
- Contains: DFIR tool functionality tests, Docker deployment tests
- Key files: Test modules requiring Docker and test lab setup

**tests/mocks/:**
- Purpose: Mock implementations for testing without Velociraptor
- Contains: Mock gRPC stubs simulating Velociraptor API responses
- Key files: `mock_velociraptor.py` (gRPC mock server)

**scripts/:**
- Purpose: Utility scripts for setup and testing
- Contains: Docker test lab setup script
- Key files: `test-lab.sh` (Velociraptor + infrastructure setup)

## Key File Locations

**Entry Points:**
- `src/megaraptor_mcp/__main__.py`: Python module entry point (python -m megaraptor_mcp)
- `src/megaraptor_mcp/server.py`: CLI entry point (main() function, called by pip entry point)

**Configuration:**
- `src/megaraptor_mcp/config.py`: VelociraptorConfig class, file/environment loading, YAML parsing
- `pyproject.toml`: Project metadata, dependencies, test configuration

**Core Logic:**
- `src/megaraptor_mcp/client.py`: VelociraptorClient class, gRPC channel management, query execution
- `src/megaraptor_mcp/server.py`: MCP server creation, tool/resource/prompt registration

**Tool Implementations:**
- `src/megaraptor_mcp/tools/clients.py`: list_clients, get_client_info, label_client, quarantine_client
- `src/megaraptor_mcp/tools/artifacts.py`: list_artifacts, get_artifact, collect_artifact
- `src/megaraptor_mcp/tools/hunts.py`: create_hunt, list_hunts, get_hunt_results, modify_hunt
- `src/megaraptor_mcp/tools/flows.py`: list_flows, get_flow_results, get_flow_status, cancel_flow
- `src/megaraptor_mcp/tools/vql.py`: run_vql, vql_help
- `src/megaraptor_mcp/tools/deployment.py`: deploy_server, agent deployment, credential management (55KB)

**Deployment Infrastructure:**
- `src/megaraptor_mcp/deployment/profiles.py`: DeploymentProfile, DeploymentTarget, DeploymentState enums, PROFILES dict
- `src/megaraptor_mcp/deployment/deployers/base.py`: BaseDeployer, DeploymentResult, DeploymentInfo
- `src/megaraptor_mcp/deployment/deployers/docker_deployer.py`: Docker container deployment
- `src/megaraptor_mcp/deployment/deployers/binary_deployer.py`: SSH/WinRM binary deployment
- `src/megaraptor_mcp/deployment/deployers/cloud_deployer.py`: AWS CloudFormation and Azure ARM

**Testing:**
- `tests/conftest.py`: Pytest fixtures, Docker setup, mock client initialization
- `tests/unit/test_config.py`: Configuration loading tests
- `tests/integration/test_dfir_tools.py`: Tool functionality tests with live Velociraptor

## Naming Conventions

**Files:**
- `{feature}.py`: Standard Python modules (client.py, config.py, server.py)
- `{feature}_deployer.py`: Deployer implementations (docker_deployer.py, binary_deployer.py)
- `{feature}_manager.py`: Manager/utility classes (certificate_manager.py, credential_store.py)
- `test_{component}.py`: Unit and integration tests
- `mock_{service}.py`: Mock implementations

**Directories:**
- `src/megaraptor_mcp/`: Main package (underscore-separated)
- `tests/{unit,integration,mocks,fixtures}/`: Test organization by type
- `src/megaraptor_mcp/{tools,resources,prompts,deployment}/`: Feature groups

**Classes:**
- PascalCase: VelociraptorClient, BaseDeployer, DeploymentProfile, CertificateManager
- Suffixes: DeploymentResult, DeploymentInfo, DeploymentProfile

**Functions:**
- snake_case: register_client_tools(), get_client(), list_clients()
- Prefixes: register_* (for MCP registration), get_* (for retrieval), list_* (for enumeration), create_* (for construction)

**Constants:**
- UPPER_CASE: PROFILES (predefined profiles dict), DeploymentState enum members, DeploymentTarget enum members

## Where to Add New Code

**New DFIR Tool:**
1. Create new file: `src/megaraptor_mcp/tools/{feature}.py`
2. Implement: `register_{feature}_tools(server: Server)` function with @server.tool() decorated async handlers
3. Import and call registration: Add to `src/megaraptor_mcp/tools/__init__.py` and `server.py::create_server()`
4. Add tests: `tests/unit/test_{feature}.py` and `tests/integration/test_{feature}.py`

**New Deployment Target:**
1. Create new deployer: `src/megaraptor_mcp/deployment/deployers/{target}_deployer.py`
2. Inherit: Extend `BaseDeployer` and implement `deploy()` async method
3. Export: Add to `src/megaraptor_mcp/deployment/deployers/__init__.py`
4. Integrate: Update `tools/deployment.py::deploy_server()` to instantiate new deployer
5. Test: Add integration test in `tests/integration/test_{target}_deployment.py`

**New Resource Type:**
1. Add handler: In `src/megaraptor_mcp/resources/resources.py`, add URI case to `read_resource()`
2. Update list: Add Resource entry to `list_resources()`
3. Test: Add test in `tests/integration/test_resources.py`

**New Workflow Prompt:**
1. Add prompt definition: In `src/megaraptor_mcp/prompts/prompts.py`, add Prompt instance to `list_prompts()` return list
2. Include arguments: Define PromptArgument instances for user inputs
3. Message template: Build PromptMessage with workflow steps using TextContent blocks

**Configuration/Credentials:**
- Config file format: `src/megaraptor_mcp/config.py` (YAML, Velociraptor API client format)
- Environment variables: Documented in `VelociraptorConfig.from_env()` docstring
- Deployment credentials: Stored via CredentialStore in `src/megaraptor_mcp/deployment/security/credential_store.py`

**Utilities and Helpers:**
- Shared utilities: `src/megaraptor_mcp/config.py` for configuration helpers
- Deployment utilities: `src/megaraptor_mcp/deployment/` subdirectories
- Test fixtures: `tests/fixtures/` directory and `tests/conftest.py`

## Special Directories

**src/megaraptor_mcp/deployment/templates/:**
- Purpose: Jinja2 templates for configuration generation
- Generated: Yes - templates are compiled at runtime for config generation
- Committed: Yes - template source files are in version control
- Usage: Certificate generation, deployment config, agent installation scripts

**.planning/codebase/:**
- Purpose: GSD codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes - created by gsd:map-codebase agent
- Committed: Yes - analysis documents tracked in version control
- Usage: Reference for planning and execution phases

**tests/__pycache__/ and src/megaraptor_mcp/__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes - created automatically by Python interpreter
- Committed: No - excluded by .gitignore

---

*Structure analysis: 2026-01-24*
