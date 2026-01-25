# Codebase Concerns

**Analysis Date:** 2026-01-24

## Tech Debt

**Certificate Rotation Without CA Not Implemented:**
- Issue: Partial implementation of certificate rotation feature. Only CA-based rotation is implemented; server/client cert rotation without CA is stubbed with a TODO.
- Files: `src/megaraptor_mcp/tools/deployment.py` (lines 1298)
- Impact: Operators cannot perform granular certificate updates without recreating the entire CA, forcing all agents to re-enroll
- Fix approach: Complete `rotate_certificates()` to handle non-CA cert rotation, implement separate rotation paths for server certs and client certs

**Global Singleton Client Pattern:**
- Issue: `VelociraptorClient` uses module-level global state with `get_client()` and `reset_client()` functions
- Files: `src/megaraptor_mcp/client.py` (lines 237-256)
- Impact: Thread safety concerns in concurrent scenarios, state pollution between test runs, difficult to manage multiple server connections
- Fix approach: Replace with dependency injection or context managers; implement proper connection pooling for multi-threaded deployments

**Credential Store Key File Permissions (Windows):**
- Issue: Credential store key file set to Unix-only permissions (0o600) with no Windows equivalent. Windows default permissions may be overly permissive.
- Files: `src/megaraptor_mcp/deployment/security/credential_store.py` (lines 130-131)
- Impact: Credentials on Windows systems may be accessible to other local users; lacks proper ACL handling
- Fix approach: Implement Windows-specific ACL setting using `os.chmod()` alternatives or `win32security` for Windows systems

## Fragile Areas

**Large Monolithic Tool Registration Module:**
- Issue: Single file `deployment.py` contains all 19 deployment tools (1554 lines) with deeply nested logic and multiple branching paths
- Files: `src/megaraptor_mcp/tools/deployment.py`
- Why fragile: Single modification can break multiple tools; difficult to test individual tools; high cognitive load for maintenance
- Safe modification: Extract tools into separate functions/modules with clear interfaces; use factory patterns for deployer selection
- Test coverage: Limited test coverage for edge cases; missing tests for error paths and mixed deployment scenarios

**Cloud Deployer Implementation (AWS/Azure):**
- Issue: 878-line file with multiple cloud providers and complex state management; duplicate error handling patterns
- Files: `src/megaraptor_mcp/deployment/deployers/cloud_deployer.py`
- Why fragile: Tight coupling between AWS and Azure logic; shared error handling that silently swallows exceptions
- Safe modification: Split into separate AWS and Azure deployer classes; consolidate error handling with structured exceptions
- Test coverage: Integration tests skipped for cloud deployments; no unit tests for CloudFormation template generation

**Bare Exception Handlers:**
- Issue: Multiple `except Exception as e:` blocks that catch all exceptions indiscriminately
- Files:
  - `src/megaraptor_mcp/deployment/deployers/docker_deployer.py` (multiple)
  - `src/megaraptor_mcp/deployment/deployers/cloud_deployer.py` (multiple)
  - `src/megaraptor_mcp/deployment/agents/ssh_deployer.py` (multiple)
  - `src/megaraptor_mcp/deployment/agents/winrm_deployer.py` (multiple)
- Why fragile: Hides programming errors; prevents proper error diagnosis; makes debugging deployment failures difficult
- Safe modification: Catch specific exceptions (SSHException, DockerException, ClientError); re-raise unexpected exceptions; log full tracebacks
- Test coverage: Error paths not systematically tested; missing tests for recovery scenarios

## Security Considerations

**Temporary Certificate Files Not Securely Deleted:**
- Risk: Certificate and key materials written to temporary files without guaranteed secure deletion; temp files could be recovered from disk
- Files: `src/megaraptor_mcp/client.py` (lines 42-81)
- Current mitigation: `tempfile.NamedTemporaryFile()` with `delete=False` and manual cleanup; vulnerable to OS crashes before deletion
- Recommendations: Use context managers to ensure deletion; implement secure deletion with overwriting (shred library); consider using in-memory temp storage or file locking

**Hardcoded Default Ports and Addresses:**
- Risk: Deployment defaults to 0.0.0.0 bind address and fixed ports (8889, 8000) without explicit security validation
- Files: `src/megaraptor_mcp/config.py` (lines 183-185)
- Current mitigation: None; relies on operator awareness
- Recommendations: Add warnings for overly permissive configs; validate network binding; require explicit approval for production deployments

**SSH Key Material in Function Parameters:**
- Risk: SSH private keys passed as string parameters; may be logged or exposed in error messages
- Files: `src/megaraptor_mcp/tools/deployment.py` (line 37), `src/megaraptor_mcp/deployment/agents/ssh_deployer.py`
- Current mitigation: Keys loaded from filesystem but can be passed as strings
- Recommendations: Enforce file-based key loading only; add parameter validation to reject key data; implement secure string handling

**Credential Store Exception Handling:**
- Risk: Decryption failures silently return empty dict, masking both corrupted stores and wrong passwords
- Files: `src/megaraptor_mcp/deployment/security/credential_store.py` (lines 170-175)
- Current mitigation: Try/except with silent failure
- Recommendations: Distinguish between missing store and decryption errors; warn on decryption failure; validate store integrity with checksums

**VQL Query Injection Risk:**
- Risk: VQL queries passed directly to API without validation or parameterization
- Files: `src/megaraptor_mcp/client.py` (lines 131-179), `src/megaraptor_mcp/tools/vql.py`
- Current mitigation: None; relies on Velociraptor server-side validation
- Recommendations: Implement VQL query sanitization; add parameterized query support; document VQL security best practices in prompts

## Performance Bottlenecks

**Synchronous Cert Generation in Async Context:**
- Problem: Certificate generation (RSA-4096 key pairs) runs synchronously in async functions, blocking event loop
- Files: `src/megaraptor_mcp/deployment/security/certificate_manager.py`
- Cause: RSA key generation is CPU-intensive; no thread-pool offloading
- Improvement path: Wrap key generation with `asyncio.to_thread()` or use async-compatible crypto library

**No Connection Pooling for Velociraptor Client:**
- Problem: New gRPC channel created per client instance; no reuse of connections
- Files: `src/megaraptor_mcp/client.py` (lines 83-116)
- Cause: Single-use channel pattern; no pool management
- Improvement path: Implement connection pool with configurable size; cache channels by server endpoint

**Docker Client Not Cached:**
- Problem: Docker client recreated on each access via lazy initialization without lifecycle management
- Files: `src/megaraptor_mcp/deployment/deployers/docker_deployer.py` (lines 68-73)
- Cause: Property getter creates new client if None; no cleanup mechanism
- Improvement path: Implement resource context manager; ensure client cleanup on deployer destruction

**Synchronous File I/O in Async Deployment:**
- Problem: Multiple blocking file operations (read/write certificates, configs) in async deployment functions
- Files: `src/megaraptor_mcp/deployment/deployers/docker_deployer.py`, `src/megaraptor_mcp/deployment/deployers/binary_deployer.py`
- Cause: File operations not wrapped with `asyncio.to_thread()`
- Improvement path: Wrap all blocking I/O with thread pools; use async file libraries for critical paths

## Scaling Limits

**Single Global Client Instance:**
- Current capacity: One Velociraptor server connection per process
- Limit: Multi-server deployments require external orchestration; concurrent requests to different servers serialize through single connection
- Scaling path: Implement connection registry per server; support server-specific client creation; add connection pooling

**In-Memory Credential Store:**
- Current capacity: All credentials loaded into memory on each access
- Limit: Large deployments with hundreds of credentials will consume memory; decryption happens on every list/get operation
- Scaling path: Implement lazy decryption; add credential caching with TTL; paginate credential listing

**Docker API Resource Limits:**
- Current capacity: Default resource limits defined per profile (4GB RAM, 2 CPUs)
- Limit: No validation of host availability; deployments may fail if insufficient resources; no graceful degradation
- Scaling path: Add pre-flight capacity checks; implement resource reservation mechanism; support custom per-deployment limits

## Testing Coverage Gaps

**Integration Tests Incomplete:**
- What's not tested: Full deployment end-to-end flow (server + agent deployment); cloud deployment integration (AWS/Azure); multi-agent coordinated deployments; failure scenarios and rollback
- Files: `tests/integration/test_docker_deployment.py` (88 lines but mostly stubs)
- Risk: Deployment features may fail silently in production; broken features not caught before release
- Priority: High - deployment is critical path for users

**Error Path Testing:**
- What's not tested: Deployment failures (network errors, insufficient permissions, missing binaries); certificate generation failures; Docker unavailable scenarios; cloud auth failures
- Files: All deployer classes in `src/megaraptor_mcp/deployment/deployers/`
- Risk: Error messages unclear; recovery paths untested; silent failures possible
- Priority: High - critical for incident response reliability

**Client Configuration Validation:**
- What's not tested: Invalid certificate PEM formats; mismatched certs and keys; expired certificates; unreachable API URLs
- Files: `src/megaraptor_mcp/config.py` (basic validation only)
- Risk: Configuration errors surface at first API call, not at startup
- Priority: Medium - improves diagnostics

**Credential Store Corruption:**
- What's not tested: Partial writes; concurrent access; key file deletion; decryption with wrong key
- Files: `src/megaraptor_mcp/deployment/security/credential_store.py`
- Risk: Credentials irretrievable without manual intervention
- Priority: Medium - affects reliability of stored credentials

## Known Issues and Limitations

**CA Certificate Rotation Forces Agent Re-enrollment:**
- Symptoms: Rotating CA certificate invalidates all existing agent certificates; agents fail to connect until re-enrolled
- Files: `src/megaraptor_mcp/tools/deployment.py` (lines 1298, 1290-1295)
- Trigger: User calls `rotate_ca=True` in deployment rotation tool
- Workaround: None; requires manual agent re-enrollment via new installers

**Rapid Profile Auto-Destruction Not Enforced:**
- Symptoms: Rapid profile deployments have `auto_destroy_at` field set but no automatic cleanup runs
- Files: `src/megaraptor_mcp/config.py` (line 191), `src/megaraptor_mcp/tools/deployment.py`
- Trigger: Deployment created with `profile="rapid"` but 72 hours pass without teardown
- Workaround: Manual `destroy_deployment()` call required after 72 hours

**Docker Deployer Assumes Linux Containers:**
- Symptoms: Windows Server container support not tested; image pull timeouts not handled
- Files: `src/megaraptor_mcp/deployment/deployers/docker_deployer.py`
- Trigger: Using Docker Desktop on Windows or non-standard Docker configurations
- Workaround: None; use Linux Docker host or binary deployment

**Cloud Deployment State Not Persisted:**
- Symptoms: AWS CloudFormation stacks or Azure deployments created but metadata lost if process crashes
- Files: `src/megaraptor_mcp/deployment/deployers/cloud_deployer.py`
- Trigger: Process crash during cloud deployment
- Workaround: Manual resource cleanup via AWS/Azure console

---

*Concerns audit: 2026-01-24*
