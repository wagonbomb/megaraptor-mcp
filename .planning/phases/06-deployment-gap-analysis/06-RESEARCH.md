# Phase 6: Deployment & Gap Analysis - Research

**Researched:** 2026-01-26
**Domain:** Deployment Automation Testing, MCP Tool Gap Analysis
**Confidence:** HIGH (based on existing codebase analysis + deployment patterns)

## Summary

This phase focuses on two distinct areas: (1) validating that the existing deployment automation (Docker and Binary profiles) works end-to-end, and (2) conducting a comprehensive gap analysis of the 35 MCP tools against real-world DFIR workflows.

The deployment validation must verify Docker deployments create accessible Velociraptor servers, binary deployments work via SSH to Linux targets, agent enrollment via SSH and WinRM functions correctly, and rollback/cleanup operations properly remove resources. The existing codebase already implements DockerDeployer, BinaryDeployer, SSHDeployer, and WinRMDeployer classes with comprehensive functionality.

The gap analysis requires systematic evaluation of all 35 MCP tools against common DFIR investigation workflows (triage, collection, analysis) to identify missing capabilities and improvement recommendations. This is a documentation exercise, not implementation.

**Primary recommendation:** Leverage the existing test infrastructure (pytest fixtures, wait helpers) to create integration tests for deployment tools, then document capability gaps systematically using a workflow-driven assessment matrix.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 8.x | Test framework | Already in use, pytest.mark.integration for deployment tests |
| docker | 7.x | Docker API client | Already used by DockerDeployer |
| paramiko | 3.x | SSH connections | Already used by SSHDeployer and BinaryDeployer |
| pywinrm | 0.5.x | WinRM connections | Already used by WinRMDeployer |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27.x | Async HTTP client | Health checks, API validation |
| tenacity | 9.x | Retry logic | Already integrated for transient error handling |
| PyYAML | 6.x | Configuration files | Server config generation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| paramiko | fabric | Higher-level, but paramiko already integrated |
| httpx | aiohttp | httpx already used, simpler API |
| Manual gap analysis | Automated coverage | Manual more thorough for qualitative assessment |

**Installation:**
Already installed via `pip install megaraptor-mcp[deployment]`

## Architecture Patterns

### Recommended Test Structure
```
tests/
  integration/
    test_docker_deployment.py          # Existing, extend
    test_binary_deployment.py          # New - requires SSH target
    test_agent_deployment_ssh.py       # New - requires Linux target
    test_agent_deployment_winrm.py     # New - requires Windows target
    test_deployment_rollback.py        # New - cleanup validation
    test_investigation_workflow_e2e.py # New - full workflow test
```

### Pattern 1: Deployment Test Lifecycle
**What:** Tests create deployment, validate accessibility, then clean up
**When to use:** All deployment validation tests
**Example:**
```python
# Source: Existing test_docker_deployment.py pattern
@pytest.fixture
async def docker_deployment(docker_deployer, deployment_config):
    """Create deployment for test, cleanup after."""
    result = await docker_deployer.deploy(deployment_config, profile, certs)
    yield result
    # Cleanup in fixture teardown
    if result.success:
        await docker_deployer.destroy(result.deployment_id, force=True)
```

### Pattern 2: Health Check Polling
**What:** Poll deployment health until ready or timeout
**When to use:** After deployment creation, before validation tests
**Example:**
```python
# Source: Existing wait_helpers.py pattern
async def wait_for_deployment_healthy(deployer, deployment_id, timeout=120):
    """Wait for deployment to become healthy."""
    start = time.time()
    while time.time() - start < timeout:
        health = await deployer.health_check(deployment_id)
        if health.get("healthy"):
            return health
        await asyncio.sleep(5)
    raise TimeoutError(f"Deployment {deployment_id} not healthy after {timeout}s")
```

### Pattern 3: End-to-End Workflow Validation
**What:** Full investigation workflow from triage to analysis
**When to use:** DEPLOY-03 requirement
**Example:**
```python
async def test_full_investigation_workflow(docker_deployment, enrolled_client_id):
    """Test complete triage -> collect -> analyze workflow."""
    # 1. Triage: List processes
    triage_result = await run_vql(
        f"SELECT * FROM pslist() WHERE client_id='{enrolled_client_id}'"
    )

    # 2. Collect: Schedule artifact collection
    collect_result = await collect_artifact(
        enrolled_client_id,
        artifacts=["Generic.Client.Info"],
        timeout=60
    )
    flow_id = collect_result["flow_id"]

    # 3. Wait for completion
    await wait_for_flow_completion(enrolled_client_id, flow_id)

    # 4. Analyze: Retrieve results
    results = await get_flow_results(enrolled_client_id, flow_id)
    assert results["result_count"] > 0
```

### Anti-Patterns to Avoid
- **Hardcoded ports:** Use dynamic port allocation to avoid conflicts
- **Shared deployment state:** Each test should create/destroy its own deployment
- **Ignoring cleanup failures:** Log warnings but don't fail tests on cleanup errors
- **Testing cloud deployments without infrastructure:** Skip gracefully with clear messages

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deployment ID generation | Custom ID scheme | `generate_deployment_id()` | Already validated, consistent format |
| Certificate generation | Manual OpenSSL calls | `CertificateManager` | Handles CA, server, client certs properly |
| SSH key handling | Custom key parsing | `paramiko.SSHClient` | Handles key formats, passphrases |
| Health check polling | Custom sleep loops | `wait_for_deployment_healthy()` | Consistent timeout handling |
| Test cleanup | Manual try/finally | Pytest fixtures | Automatic teardown even on failure |

**Key insight:** The existing deployment infrastructure is comprehensive. The phase is about validation, not building new deployment features.

## Common Pitfalls

### Pitfall 1: Port Conflicts in Parallel Tests
**What goes wrong:** Multiple tests try to use same GUI/frontend ports
**Why it happens:** Fixed port assignments in test configuration
**How to avoid:** Use dynamic port allocation or serialize deployment tests
**Warning signs:** "Address already in use" errors, flaky tests

### Pitfall 2: Orphaned Docker Containers
**What goes wrong:** Test failures leave containers running, consuming resources
**Why it happens:** Cleanup code not reached due to assertion failures
**How to avoid:** Use pytest fixtures with teardown, implement container labeling for manual cleanup
**Warning signs:** `docker ps` shows test containers after test runs

### Pitfall 3: SSH/WinRM Credential Exposure
**What goes wrong:** Test credentials appear in logs or error messages
**Why it happens:** Exception handlers include sensitive parameters
**How to avoid:** Never log passwords, use credential redaction in errors
**Warning signs:** Passwords visible in CI logs

### Pitfall 4: Missing Infrastructure Skips
**What goes wrong:** Tests fail with confusing errors when infrastructure unavailable
**Why it happens:** No graceful degradation for missing Docker/SSH/WinRM targets
**How to avoid:** Skip guards that check infrastructure availability before test execution
**Warning signs:** ImportError, ConnectionRefusedError instead of pytest.skip()

### Pitfall 5: Incomplete Rollback Verification
**What goes wrong:** Rollback appears successful but leaves resources behind
**Why it happens:** Only checking return value, not actual resource state
**How to avoid:** Verify resource absence after rollback (container removed, files deleted)
**Warning signs:** Disk usage grows over test runs, stale containers accumulate

## Code Examples

Verified patterns from existing codebase:

### Docker Deployment Test
```python
# Source: tests/integration/test_docker_deployment.py
@pytest.fixture
def docker_deployer(docker_available, temp_deployment_dir):
    """Create a DockerDeployer for testing."""
    if not docker_available:
        pytest.skip("Docker not available")

    from megaraptor_mcp.deployment.deployers.docker_deployer import DockerDeployer
    return DockerDeployer(storage_path=temp_deployment_dir)

async def test_deploy_and_validate(docker_deployer, deployment_config, certificates):
    """Full deployment lifecycle test."""
    result = await docker_deployer.deploy(deployment_config, profile, certificates)

    try:
        assert result.success
        assert result.server_url

        # Wait for healthy
        health = await wait_for_deployment_healthy(
            docker_deployer, result.deployment_id
        )
        assert health["healthy"]

        # Verify API accessible
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(result.api_url)
            assert response.status_code < 500
    finally:
        await docker_deployer.destroy(result.deployment_id, force=True)
```

### Skip Guard for Infrastructure
```python
# Source: Pattern from test_os_artifacts_windows.py
def has_docker_available():
    """Check if Docker is available."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False

skip_no_docker = pytest.mark.skipif(
    not has_docker_available(),
    reason="Docker not available"
)
```

### Rollback Verification
```python
# Source: Pattern for DEPLOY-04 requirement
async def test_deployment_rollback_cleanup(docker_deployer, deployment_config):
    """Verify rollback cleans up all resources."""
    result = await docker_deployer.deploy(deployment_config, profile, certs)
    deployment_id = result.deployment_id
    container_name = f"velociraptor-{deployment_id}"

    # Verify container exists
    container = docker_deployer.client.containers.get(container_name)
    assert container is not None

    # Perform rollback
    rollback_result = await docker_deployer.destroy(deployment_id, force=True)
    assert rollback_result.success

    # Verify container removed
    with pytest.raises(docker.errors.NotFound):
        docker_deployer.client.containers.get(container_name)

    # Verify deployment info cleaned up
    info = await docker_deployer.get_status(deployment_id)
    assert info is None or info.state.value == "DESTROYED"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual deployment testing | Automated CI/CD validation | 2024+ | Consistent, repeatable tests |
| Fixed test ports | Dynamic port allocation | Testcontainers pattern | Parallel test execution |
| Manual gap analysis | Workflow-driven assessment | NIST/SANS frameworks | Systematic coverage |

**Deprecated/outdated:**
- Static SSH key paths: Use environment variables or secure vault
- HTTP WinRM: Always use HTTPS in production, but HTTP acceptable for isolated test labs

## Gap Analysis Framework

For GAP-01, GAP-02, GAP-03 requirements, use this systematic approach:

### Workflow Categories to Evaluate
1. **Triage Workflow:** Quick assessment of endpoint state
2. **Collection Workflow:** Artifact gathering and evidence preservation
3. **Analysis Workflow:** VQL queries, timeline generation, indicator extraction
4. **Remediation Workflow:** Quarantine, cleanup, response actions
5. **Reporting Workflow:** Export, documentation, chain of custody

### Tool Coverage Matrix Template
```markdown
| Workflow Step | Required Capability | Current Tool | Gap |
|---------------|---------------------|--------------|-----|
| Triage - Process List | List running processes | run_vql + pslist() | None |
| Triage - Network Connections | Show active connections | run_vql + netstat() | None |
| Collection - Memory | Dump process memory | collect_artifact | Requires artifact |
| Analysis - Timeline | Generate timeline | N/A | Missing: timeline_generate tool |
```

### Gap Classification
- **Critical:** Blocks investigation workflow, no workaround
- **Moderate:** Workaround exists but inefficient
- **Minor:** Nice-to-have, low priority

## Open Questions

Things that couldn't be fully resolved:

1. **Binary Deployment Target Availability**
   - What we know: Binary deployment requires SSH target (Linux/macOS host)
   - What's unclear: Is a test VM or container available for binary deployment tests?
   - Recommendation: If no dedicated target, use Docker container with SSH enabled as mock target

2. **WinRM Test Target**
   - What we know: WinRM requires Windows target with WinRM enabled
   - What's unclear: Is Windows test target available in lab environment?
   - Recommendation: Skip gracefully if unavailable, document as known limitation

3. **Cloud Deployment Scope**
   - What we know: AWS/Azure deployers exist but not in Phase 6 scope
   - What's unclear: Should GAP-03 cloud scoping include actual testing?
   - Recommendation: GAP-03 is requirements scoping only, not implementation or testing

## Sources

### Primary (HIGH confidence)
- Existing codebase analysis (deployment.py, docker_deployer.py, binary_deployer.py, ssh_deployer.py, winrm_deployer.py)
- Existing test infrastructure (test_docker_deployment.py, conftest.py, wait_helpers.py)
- REQUIREMENTS.md phase 6 requirements

### Secondary (MEDIUM confidence)
- [Velociraptor Deployment Documentation](https://docs.velociraptor.app/docs/deployment/) - Official deployment patterns
- [Testcontainers Best Practices](https://www.docker.com/blog/testcontainers-best-practices/) - Container testing patterns
- [pywinrm GitHub](https://github.com/diyan/pywinrm) - WinRM library documentation

### Tertiary (LOW confidence)
- WebSearch results on Docker testing best practices 2026
- WebSearch results on DFIR gap analysis methodology

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use in codebase
- Architecture: HIGH - Patterns derived from existing test infrastructure
- Pitfalls: MEDIUM - Some based on general testing experience
- Gap analysis framework: MEDIUM - Based on DFIR methodology, not project-specific validation

**Research date:** 2026-01-26
**Valid until:** 60 days (stable domain, not fast-moving)

## Appendix: 35 MCP Tools for Gap Analysis

Current tool inventory for gap analysis:

### Client Management (4 tools)
1. `list_clients` - Search and list endpoints
2. `get_client_info` - Detailed client information
3. `label_client` - Add/remove client labels
4. `quarantine_client` - Isolate compromised endpoints

### Artifact Operations (3 tools)
5. `list_artifacts` - Search available artifacts
6. `get_artifact` - Get artifact definition
7. `collect_artifact` - Schedule artifact collection

### Hunt Operations (4 tools)
8. `create_hunt` - Create mass collection campaign
9. `list_hunts` - List hunt status
10. `get_hunt_results` - Retrieve hunt data
11. `modify_hunt` - Start/pause/stop hunts

### Flow Operations (4 tools)
12. `list_flows` - List client collection flows
13. `get_flow_results` - Retrieve flow data
14. `get_flow_status` - Check flow progress
15. `cancel_flow` - Stop running flow

### VQL Operations (2 tools)
16. `run_vql` - Execute arbitrary VQL
17. `vql_help` - VQL reference

### Deployment - Server (6 tools)
18. `deploy_server` - Generic server deployment
19. `deploy_server_docker` - Docker-specific deployment
20. `deploy_server_cloud` - Cloud deployment
21. `get_deployment_status` - Check deployment health
22. `destroy_deployment` - Remove deployment
23. `list_deployments` - List managed deployments

### Deployment - Agent (7 tools)
24. `generate_agent_installer` - Create installer packages
25. `create_offline_collector` - Air-gapped collection
26. `generate_gpo_package` - Windows GPO deployment
27. `generate_ansible_playbook` - Ansible deployment
28. `deploy_agents_winrm` - Push to Windows via WinRM
29. `deploy_agents_ssh` - Push to Linux/macOS via SSH
30. `check_agent_deployment` - Verify enrollment

### Deployment - Configuration (5 tools)
31. `generate_server_config` - Generate server YAML
32. `generate_api_credentials` - Create API client certs
33. `rotate_certificates` - Certificate rotation
34. `validate_deployment` - Security/health validation
35. `export_deployment_docs` - Generate documentation
