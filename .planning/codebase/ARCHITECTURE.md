# Architecture

**Analysis Date:** 2026-01-24

## Pattern Overview

**Overall:** MCP Server with Layered Architecture

Megaraptor MCP follows the Model Context Protocol (MCP) server pattern with a clean layered architecture: transport layer → server factory → tool/resource/prompt registration → business logic layer (client wrapper) → external Velociraptor API.

**Key Characteristics:**
- **MCP Compliance**: Implements MCP protocol for stdio transport with AI assistant integration
- **Separation of Concerns**: Tools, resources, and prompts clearly separated
- **Async-First Design**: All MCP handlers use async/await for concurrency
- **Lazy Initialization**: Global client instance created on-demand with context manager support
- **Pluggable Deployers**: Deployment infrastructure uses strategy pattern with multiple backend implementations
- **Configuration Flexibility**: Supports both file-based and environment variable configuration

## Layers

**Transport Layer:**
- Purpose: Handle MCP protocol communication over stdio
- Location: `src/megaraptor_mcp/server.py`
- Contains: `run_server()`, `create_server()`, MCP Server initialization
- Depends on: MCP framework (mcp), all tool/resource/prompt modules
- Used by: Entry point `main()`, CLI invocation

**Server Factory Layer:**
- Purpose: Instantiate and configure the MCP server with all capabilities
- Location: `src/megaraptor_mcp/server.py::create_server()`
- Contains: Registration calls for tools, resources, and prompts
- Depends on: Tool/resource/prompt register functions
- Used by: `run_server()` before starting transport

**Tool Registration Layer:**
- Purpose: Expose Velociraptor capabilities as MCP tools through decorator pattern
- Location: `src/megaraptor_mcp/tools/`
- Contains: Six register functions that bind async functions to server
- Depends on: MCP Server, VelociraptorClient
- Used by: Server factory during initialization

**Resource Layer:**
- Purpose: Provide browsable data resources through standard URIs (velociraptor://)
- Location: `src/megaraptor_mcp/resources/resources.py`
- Contains: `register_resources()` that binds list_resources and read_resource handlers
- Depends on: VelociraptorClient
- Used by: Server factory, AI assistants for resource browsing

**Prompt Layer:**
- Purpose: Pre-built DFIR workflow templates with templated arguments
- Location: `src/megaraptor_mcp/prompts/prompts.py`
- Contains: `register_prompts()` that defines 8 workflow prompts
- Depends on: MCP Prompt types
- Used by: Server factory, AI assistants for guided workflows

**Client Wrapper Layer:**
- Purpose: Abstract Velociraptor gRPC API interactions
- Location: `src/megaraptor_mcp/client.py`
- Contains: `VelociraptorClient` class, global instance management
- Depends on: pyvelociraptor (gRPC stubs), configuration, certificate handling
- Used by: All tools, resources, and prompts for API access

**Configuration Layer:**
- Purpose: Load and manage Velociraptor connection credentials
- Location: `src/megaraptor_mcp/config.py`
- Contains: `VelociraptorConfig` dataclass, config file parsing, environment loading
- Depends on: PyYAML for config file parsing
- Used by: VelociraptorClient during initialization

**Deployment Layer:**
- Purpose: Multi-target server and agent deployment with pluggable backends
- Location: `src/megaraptor_mcp/deployment/`
- Contains: Base deployer interface, four concrete deploers (Docker, Binary, AWS, Azure), profiles, security utilities
- Depends on: External tools (Docker, cloud SDKs, SSH, WinRM), certificates, credential storage
- Used by: `deploy_server()` and agent deployment tools

## Data Flow

**Query Execution:**

1. AI assistant calls MCP tool (e.g., `list_clients`)
2. Tool async handler receives parameters
3. Tool calls `get_client()` to obtain global VelociraptorClient instance
4. Client wraps parameters into gRPC request object (e.g., `VQLCollectorArgs`)
5. gRPC channel established via TLS credentials if not already connected
6. Query sent via `api_pb2_grpc.APIStub.Query()` streaming call
7. Results parsed from JSON response chunks
8. Tool formats results and returns as MCP TextContent with JSON payload
9. MCP transport serializes and sends to AI assistant

**State Management:**
- Global `_client` singleton maintains persistent gRPC connection across tool calls
- Certificates stored in PEM format, written to temp files for gRPC requirement
- Connection state tracked in `_channel` and `_stub` instance variables
- Context manager support (`with client:`) for connection lifecycle management

**Deployment Workflow:**

1. User calls `deploy_server()` with deployment parameters
2. Deployment ID generated, config assembled
3. CertificateManager generates TLS certificate bundle
4. Appropriate deployer selected based on deployment_type (Docker, binary, AWS, Azure)
5. Deployer.deploy() called with config, profile, and certificates
6. Deployer creates infrastructure, starts Velociraptor process
7. Deployment tracked with state progression (pending → provisioning → running)
8. Auto-destroy scheduled if profile defines timeout
9. Credentials and access URLs returned to user

## Key Abstractions

**VelociraptorClient:**
- Purpose: Single-threaded gRPC API wrapper with connection pooling
- Examples: `src/megaraptor_mcp/client.py::VelociraptorClient`
- Pattern: Singleton with lazy initialization, context manager support
- Methods: `query()`, `query_stream()`, `connect()`, `close()`

**BaseDeployer:**
- Purpose: Interface for deployment implementations
- Examples: `src/megaraptor_mcp/deployment/deployers/base.py::BaseDeployer`
- Pattern: Abstract base class with `deploy()` async method
- Implementations: DockerDeployer, BinaryDeployer, CloudDeployer

**DeploymentProfile:**
- Purpose: Configuration template for deployment parameters
- Examples: `src/megaraptor_mcp/deployment/profiles.py::DeploymentProfile`
- Pattern: Dataclass with predefined instances (rapid, standard, enterprise)
- Data: Auto-destroy timing, resource limits, client limits, security settings

**MCP Tool Registration:**
- Purpose: Bind Python async functions to MCP tool schema
- Examples: `@server.tool()` decorator in `src/megaraptor_mcp/tools/`
- Pattern: Decorator-based function registration with automatic docstring extraction
- Return: MCP TextContent with JSON payload

## Entry Points

**CLI Entry Point:**
- Location: `src/megaraptor_mcp/server.py::main()`
- Triggers: Direct script execution or pip console_scripts entry point
- Responsibilities: Async event loop setup, error handling, keyboard interrupt handling

**Module Entry Point:**
- Location: `src/megaraptor_mcp/__main__.py`
- Triggers: `python -m megaraptor_mcp`
- Responsibilities: Delegates to `main()`

**Server Initialization:**
- Location: `src/megaraptor_mcp/server.py::create_server()`
- Triggers: Called by `run_server()`
- Responsibilities: Instantiate MCP server, register all tools/resources/prompts in order

**Tool Execution:**
- Location: Each tool's async handler in `src/megaraptor_mcp/tools/*.py`
- Triggers: MCP transport receives tool call request
- Responsibilities: Parameter validation, VelociraptorClient invocation, result formatting

## Error Handling

**Strategy:** Layered error propagation with JSON error responses

**Patterns:**

- **Configuration Errors**: Raised at client initialization, propagated to entry point
  - `VelociraptorConfig.from_config_file()` raises `FileNotFoundError` if config missing
  - `VelociraptorConfig.from_env()` raises `ValueError` if required env vars missing

- **Connection Errors**: gRPC channel creation failures propagated to tool level
  - `VelociraptorClient._create_channel()` raises `ImportError` if pyvelociraptor missing
  - Stub creation raises `grpc.RpcError` if server unreachable

- **Query Errors**: VQL syntax or execution errors caught and returned as JSON error objects
  - Try-catch in tool handlers wraps `client.query()` calls
  - Exceptions converted to JSON error response with query and error message

- **Deployment Errors**: Deployer-specific exceptions converted to DeploymentResult with error flag
  - Each deployer catches and wraps deployment failures
  - Result includes error message and optional diagnostic details

- **Top-Level Error Handling**: `main()` catches all exceptions, logs with traceback, exits with status 1

## Cross-Cutting Concerns

**Logging:**
- Tool: Python standard logging module
- Approach: Configured in `server.py` with stderr stream, ISO timestamp format
- Pattern: Module-level logger instances in each file
- Levels: INFO for operational events, ERROR for exceptions

**Validation:**
- Tool: Parameter validation via MCP tool signatures
- Approach: Type hints and function signatures enforce parameters
- Pattern: VQL query validation (LIMIT clause auto-added), deploy parameter validation
- Coverage: Client IDs, artifact names, deployment targets

**Authentication:**
- Tool: Mutual TLS with gRPC
- Approach: Certificates loaded from config file or environment
- Pattern: Temporary files created for cert handoff to gRPC library
- Lifecycle: Certificates persist in memory during connection lifetime

**Secrets Management:**
- Tool: Environment variables for credential distribution
- Approach: Config file path or individual cert/key env vars
- Pattern: CredentialStore for deployment-time secret storage
- Coverage: Velociraptor API certs, SSH keys, cloud API credentials

---

*Architecture analysis: 2026-01-24*
