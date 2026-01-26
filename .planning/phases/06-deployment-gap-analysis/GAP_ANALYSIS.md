# Megaraptor MCP Gap Analysis

**Version:** 1.0
**Date:** 2026-01-26
**Scope:** v1.0 Quality & Real-World Validation Milestone

## Executive Summary

This document identifies capability gaps in the 35 MCP tools based on real-world DFIR workflow requirements. It provides recommendations for deployment improvements and scopes cloud testing requirements for the next milestone.

The analysis is structured around four core DFIR workflows: Triage, Collection, Analysis, and Remediation. Each workflow is evaluated against the current tool capabilities, identifying gaps that would benefit from future tool development.

**Key Findings:**
- 35 MCP tools provide comprehensive coverage for core DFIR operations
- Critical gaps exist in timeline generation, IOC extraction, and automated reporting
- Deployment automation is functional but would benefit from persistence and profile enhancements
- Cloud deployment validation is scoped for v2 milestone

## Tool Capability Assessment

This section systematically evaluates the 35 MCP tools against real-world DFIR investigation workflows. Each workflow category identifies current tool coverage and gaps.

### Current Tool Inventory

The Megaraptor MCP provides 35 tools across six categories:

| Category | Count | Tools |
|----------|-------|-------|
| Client Management | 4 | list_clients, get_client_info, label_client, quarantine_client |
| Artifact Operations | 3 | list_artifacts, get_artifact, collect_artifact |
| Hunt Operations | 4 | create_hunt, list_hunts, get_hunt_results, modify_hunt |
| Flow Operations | 4 | list_flows, get_flow_results, get_flow_status, cancel_flow |
| VQL Operations | 2 | run_vql, vql_help |
| Deployment Operations | 18 | Server, agent, and configuration tools |

### Triage Workflow Assessment

Triage involves rapid assessment of endpoint state to determine if further investigation is warranted.

| Step | Capability | Current Tool | Gap Status |
|------|------------|--------------|------------|
| List processes | Running process enumeration | run_vql + pslist() | Covered |
| Network connections | Active network state | run_vql + netstat() | Covered |
| Quick client info | System identification | get_client_info | Covered |
| User sessions | Active login sessions | run_vql + users() | Covered |
| File system check | Recent file activity | run_vql + glob() | Covered |
| Memory state | Process memory analysis | collect_artifact | Partial - requires specific artifact |
| Autoruns | Persistence mechanisms | collect_artifact | Covered - Windows.Sys.StartupItems |
| Browser history | Web activity | collect_artifact | Covered - Browser.* artifacts |

**Triage Gaps:**
- No dedicated "quick triage" tool that bundles common queries
- Memory analysis requires knowing specific artifact names

### Collection Workflow Assessment

Collection involves gathering forensic artifacts for detailed analysis.

| Step | Capability | Current Tool | Gap Status |
|------|------------|--------------|------------|
| Schedule collection | Artifact scheduling | collect_artifact | Covered |
| Mass collection | Hunt creation | create_hunt | Covered |
| Offline collection | Air-gapped systems | create_offline_collector | Covered |
| Progress monitoring | Flow status | get_flow_status | Covered |
| Cancel collection | Stop running flow | cancel_flow | Covered |
| Result retrieval | Get collected data | get_flow_results | Covered |
| Hunt results | Get hunt data | get_hunt_results | Covered |
| Artifact browsing | List available artifacts | list_artifacts | Covered |

**Collection Gaps:**
- No bulk collection scheduling (multiple artifacts in single call)
- No collection templates for common scenarios (malware, lateral movement)

### Analysis Workflow Assessment

Analysis involves examining collected data to identify indicators of compromise and understand attacker activity.

| Step | Capability | Current Tool | Gap Status |
|------|------------|--------------|------------|
| Ad-hoc queries | VQL execution | run_vql | Covered |
| Result retrieval | Flow/hunt results | get_flow_results, get_hunt_results | Covered |
| VQL reference | Query syntax help | vql_help | Covered |
| Client labeling | Tag endpoints | label_client | Covered |
| Timeline generation | Event timeline | N/A | GAP: No timeline tool |
| IOC extraction | Indicator extraction | N/A | GAP: No IOC extraction tool |
| Correlation | Cross-endpoint analysis | N/A | GAP: Manual VQL required |
| Report generation | Investigation summary | N/A | GAP: No reporting tool |

**Analysis Gaps (Critical):**
1. **Timeline generation** - No tool to generate unified event timelines across artifacts
2. **IOC extraction** - No tool to extract and format indicators (hashes, IPs, domains)
3. **Cross-endpoint correlation** - Hunt results require manual correlation
4. **Report generation** - No automated investigation summary generation

### Remediation Workflow Assessment

Remediation involves containing threats and restoring systems to a known-good state.

| Step | Capability | Current Tool | Gap Status |
|------|------------|--------------|------------|
| Client isolation | Network quarantine | quarantine_client | Covered |
| Flow cancellation | Stop running flow | cancel_flow | Covered |
| Hunt control | Start/stop hunts | modify_hunt | Covered |
| Label compromised | Mark endpoints | label_client | Covered |
| File remediation | Delete/quarantine files | N/A | GAP: No file remediation tool |
| Process termination | Kill malicious processes | N/A | GAP: Manual VQL required |
| Registry cleanup | Remove persistence | N/A | GAP: Manual VQL required |
| Rollback tracking | Document changes | N/A | GAP: No change tracking |

**Remediation Gaps:**
1. **File remediation** - No dedicated tool for file quarantine/deletion
2. **Process termination** - Requires manual VQL `execve()` or artifact
3. **Registry cleanup** - Requires manual VQL for Windows registry modification
4. **Change tracking** - No audit trail of remediation actions

## Critical Tool Gaps Summary

Based on the workflow assessment, the following gaps are prioritized for future development:

### Priority 1: High-Value Missing Tools

| Gap | Workflow Impact | Recommended Tool | Complexity |
|-----|-----------------|------------------|------------|
| Timeline generation | Analysis blocked without it | `generate_timeline` | Medium |
| IOC extraction | Threat hunting slowed | `extract_iocs` | Low |
| Report generation | Documentation manual | `generate_report` | Medium |

### Priority 2: Enhancement Opportunities

| Gap | Workflow Impact | Recommended Enhancement | Complexity |
|-----|-----------------|-------------------------|------------|
| Quick triage bundle | Triage slower | `quick_triage` tool | Low |
| Collection templates | Collection planning manual | Template system | Medium |
| File remediation | Response limited | `remediate_file` tool | High |

### Priority 3: Future Considerations

| Gap | Workflow Impact | Notes |
|-----|-----------------|-------|
| Cross-endpoint correlation | Manual correlation required | Complex - may need server-side support |
| Change tracking | Audit trail missing | Requires architecture decision |
| Process termination | Manual VQL | Security considerations for remote exec |

## Deployment Improvement Recommendations

Based on validation testing in Phase 6 and analysis of the deployment automation implementation, the following improvements are recommended for future development.

### Priority 1: Critical Improvements

These improvements address issues that impact reliability and user experience in production deployments.

#### 1.1 Health Check Timeout Configuration

**Issue:** Default health check timeout (120s) may be insufficient for slow networks or resource-constrained environments.

**Current Behavior:** Health check uses hardcoded timeout value that cannot be adjusted per-environment.

**Recommendation:** Make timeout configurable via environment variable (`MEGARAPTOR_HEALTH_TIMEOUT`) with sensible default.

**Rationale:** Different deployment environments have different latency characteristics. Incident response scenarios may involve degraded networks or overloaded systems where 120s is insufficient.

**Implementation Effort:** Low (configuration change)

#### 1.2 Certificate Validation Error Messages

**Issue:** Self-signed certificate errors produce generic SSL/TLS error messages that don't guide users to resolution.

**Current Behavior:** gRPC connection fails with `ssl.SSLCertVerificationError` without actionable guidance.

**Recommendation:** Add explicit self-signed certificate detection with user-friendly message: "Self-signed certificate detected. Use `--insecure` flag or add certificate to trusted store."

**Rationale:** Most incident response deployments use self-signed certificates for rapid deployment. Users need clear guidance on how to proceed.

**Implementation Effort:** Low (error message enhancement)

#### 1.3 Deployment State Persistence

**Issue:** Deployment registry is stored in memory only; state is lost on tool restart.

**Current Behavior:** After restart, users must re-register deployments manually or re-run deployment commands.

**Recommendation:** Persist deployment registry to disk (JSON file in `~/.megaraptor/deployments.json`) with automatic load on startup.

**Rationale:** Users expect to reconnect to existing deployments after tool restart. Losing state causes confusion and requires redundant operations.

**Implementation Effort:** Medium (file I/O, migration handling)

#### 1.4 Connection Retry on Transient Failures

**Issue:** Initial connection failures are not retried, requiring manual intervention.

**Current Behavior:** First connection attempt fails immediately on transient network errors.

**Recommendation:** Apply existing tenacity retry logic to initial deployment connections, not just query operations.

**Rationale:** Transient network issues are common in incident response environments. Automatic retry improves reliability without user intervention.

**Implementation Effort:** Low (extend existing retry decorator)

### Priority 2: Enhancement Recommendations

These improvements enhance usability and operational flexibility.

#### 2.1 Minimal Deployment Profile

**Issue:** Only three profiles available (rapid, standard, enterprise); no option for resource-constrained environments.

**Current Behavior:** "Rapid" profile is smallest option but may still exceed available resources in some scenarios.

**Recommendation:** Add "minimal" profile optimized for single-investigator, low-resource scenarios:
- Reduced memory limits (512MB vs 2GB)
- Single frontend only
- Disabled non-essential services
- Faster startup time

**Rationale:** Some IR scenarios (embedded systems, IoT investigation) require minimal footprint. Current profiles assume adequate resources.

**Implementation Effort:** Medium (new profile definition, testing)

#### 2.2 Container Image Version Pinning

**Issue:** Latest tag used by default, leading to inconsistent deployments over time.

**Current Behavior:** `deploy_server_docker` pulls `velociraptor:latest` unless version specified.

**Recommendation:** Default to specific known-good version (e.g., `0.75.2`) with explicit `--latest` flag for newest version.

**Rationale:** Version consistency is critical for reproducible investigations and cross-deployment comparison. Latest tag introduces variability.

**Implementation Effort:** Low (configuration change)

#### 2.3 Network Isolation Options for Docker

**Issue:** No built-in network isolation for deployed Velociraptor servers.

**Current Behavior:** Docker containers use default bridge network, potentially accessible to other containers.

**Recommendation:** Add `--network-isolated` flag to create dedicated Docker network per deployment with configurable firewall rules.

**Rationale:** Security best practice for incident response. Isolated deployment prevents lateral movement if server compromised.

**Implementation Effort:** Medium (Docker network configuration)

#### 2.4 Deployment Tagging and Metadata

**Issue:** Deployments have minimal metadata, making it difficult to distinguish between multiple deployments.

**Current Behavior:** Deployments identified only by auto-generated ID.

**Recommendation:** Allow user-provided tags, descriptions, and investigation case numbers when creating deployments.

**Rationale:** Incident responders often manage multiple simultaneous deployments. Rich metadata improves organization and auditability.

**Implementation Effort:** Low (extend deployment data model)

#### 2.5 Pre-Deployment Validation Checks

**Issue:** Deployment failures occur after resources are partially provisioned.

**Current Behavior:** Port conflicts, missing dependencies discovered during deployment.

**Recommendation:** Add `--validate-only` mode that checks prerequisites before deployment:
- Port availability
- Docker/SSH connectivity
- Disk space requirements
- Network accessibility

**Rationale:** Catching issues early prevents partial deployments and simplifies troubleshooting.

**Implementation Effort:** Medium (validation framework)

### Priority 3: Future Considerations

These are architectural enhancements for future milestones.

#### 3.1 Multi-Server Deployments

**Issue:** Single server deployment only; no support for distributed architectures.

**Current Behavior:** Each deployment is a single Velociraptor server instance.

**Recommendation:** Add multi-frontend support for enterprise scale:
- Load balancer configuration
- Shared datastore
- Frontend auto-scaling

**Rationale:** Large enterprises require scalable deployments that handle thousands of endpoints. Current architecture limits scale.

**Implementation Effort:** High (architectural change)

#### 3.2 Kubernetes Deployment Support

**Issue:** Docker only; no Kubernetes support for cloud-native environments.

**Current Behavior:** Deployment limited to Docker containers and binary installations.

**Recommendation:** Add Helm chart or Kubernetes manifest generation:
- StatefulSet for server
- ConfigMap for configuration
- Secret management for certificates
- Ingress configuration

**Rationale:** Enterprise environments increasingly use Kubernetes. Native support reduces deployment friction.

**Implementation Effort:** High (new deployment path)

#### 3.3 Deployment Templates and Presets

**Issue:** Deployment configuration requires manual parameter specification each time.

**Current Behavior:** Users must provide configuration options for each deployment.

**Recommendation:** Support deployment templates that capture common configurations:
- Save current deployment as template
- Apply template to new deployments
- Organization-wide template sharing

**Rationale:** Standardized deployments reduce configuration errors and ensure consistency across an organization's IR capability.

**Implementation Effort:** Medium (template system)

### Deployment Recommendations Summary

| Priority | ID | Recommendation | Effort | Impact |
|----------|-----|----------------|--------|--------|
| 1 | 1.1 | Health check timeout config | Low | High |
| 1 | 1.2 | Certificate error messages | Low | High |
| 1 | 1.3 | Deployment state persistence | Medium | High |
| 1 | 1.4 | Connection retry | Low | Medium |
| 2 | 2.1 | Minimal profile | Medium | Medium |
| 2 | 2.2 | Version pinning | Low | Medium |
| 2 | 2.3 | Network isolation | Medium | Medium |
| 2 | 2.4 | Deployment tagging | Low | Low |
| 2 | 2.5 | Pre-deployment validation | Medium | Medium |
| 3 | 3.1 | Multi-server deployments | High | High |
| 3 | 3.2 | Kubernetes support | High | High |
| 3 | 3.3 | Deployment templates | Medium | Medium |

**Recommended v2 Focus:** Priority 1 items (1.1-1.4) should be addressed first as they have highest impact with lowest effort. Priority 2 items can be prioritized based on user feedback.

## Cloud Testing Requirements (v2 Scope)

This section scopes the cloud testing requirements for the next milestone. Cloud deployment validation was explicitly deferred from v1.0 to focus on on-premises validation first.

**Important:** This is a SCOPING document, not implementation. It defines what cloud testing should cover when the project is ready to validate cloud deployments.

### Background

The Megaraptor MCP includes CloudFormation and ARM template deployment capabilities (via `deploy_server_cloud`), but these have not been validated against actual cloud infrastructure. v1.0 focused on:
- Docker deployment validation (local and remote)
- Binary deployment via SSH
- Agent enrollment mechanisms

Cloud validation is the logical next step after on-premises patterns are proven.

### AWS Testing Requirements

#### CLOUD-01: AWS CloudFormation Deployment Validation

**Objective:** Validate that the CloudFormation template deploys a functional Velociraptor server with all expected capabilities.

**Test Scope:**

| Test Case | Description | Pass Criteria |
|-----------|-------------|---------------|
| Stack Creation | Template deploys without errors | Stack status: CREATE_COMPLETE |
| EC2 Accessibility | Server is network-reachable | SSH and HTTPS ports respond |
| API Health | Velociraptor API responds | Health endpoint returns 200 |
| Agent Enrollment | Client can enroll | Client appears in list_clients |
| Artifact Collection | Basic collection works | collect_artifact succeeds |
| Stack Deletion | Cleanup is complete | All resources removed |

**Infrastructure Prerequisites:**

| Resource | Requirement | Notes |
|----------|-------------|-------|
| AWS Account | Full CloudFormation permissions | IAM role or user credentials |
| VPC | Existing or template-created | Internet gateway required for agent enrollment |
| EC2 Permissions | Launch t3.medium or larger | Velociraptor needs 2GB+ RAM |
| Security Group | Allow 443, 8000, 8001 | GUI, frontend, admin ports |
| S3 Bucket | Optional - for state persistence | Terraform state if using TF wrapper |

**Test Environment Variables:**

```bash
# Required
AWS_ACCESS_KEY_ID=<access-key>
AWS_SECRET_ACCESS_KEY=<secret-key>
AWS_DEFAULT_REGION=us-east-1

# Optional
AWS_VPC_ID=vpc-xxx         # Use existing VPC
AWS_SUBNET_ID=subnet-xxx   # Use existing subnet
```

**Estimated Test Duration:** 15-30 minutes per full cycle (create, validate, destroy)

**Cost Estimate:** $0.10-0.20 per test cycle (t3.medium spot pricing)

#### CLOUD-01 Test Implementation Outline

```python
@pytest.mark.cloud
@pytest.mark.aws
@skip_if_no_aws_credentials
async def test_aws_cloudformation_deployment():
    """Full AWS CloudFormation deployment lifecycle test."""
    # 1. Deploy stack
    result = await deploy_server_cloud(
        provider="aws",
        template="cloudformation",
        region="us-east-1",
        instance_type="t3.medium"
    )
    assert result.success

    try:
        # 2. Wait for healthy
        await wait_for_deployment_healthy(result.deployment_id, timeout=300)

        # 3. Validate API
        health = await get_deployment_status(result.deployment_id)
        assert health["api_healthy"]

        # 4. Test artifact collection (requires enrolled client)
        # Note: May need separate agent deployment test

    finally:
        # 5. Cleanup
        await destroy_deployment(result.deployment_id, force=True)

        # 6. Verify cleanup
        # Check AWS for orphaned resources
```

### Azure Testing Requirements

#### CLOUD-02: Azure ARM Template Deployment Validation

**Objective:** Validate that the ARM template deploys a functional Velociraptor server with equivalent capabilities to AWS deployment.

**Test Scope:**

| Test Case | Description | Pass Criteria |
|-----------|-------------|---------------|
| Resource Group Creation | RG deploys without errors | Deployment state: Succeeded |
| VM Accessibility | Server is network-reachable | SSH and HTTPS ports respond |
| API Health | Velociraptor API responds | Health endpoint returns 200 |
| Agent Enrollment | Client can enroll | Client appears in list_clients |
| Artifact Collection | Basic collection works | collect_artifact succeeds |
| Resource Group Deletion | Cleanup is complete | All resources removed |

**Infrastructure Prerequisites:**

| Resource | Requirement | Notes |
|----------|-------------|-------|
| Azure Subscription | Contributor role | Resource deployment permissions |
| Resource Group | Template-created or existing | Template can create new RG |
| VNet Permissions | Create or use existing | Subnet with internet access |
| VM Permissions | Deploy Standard_B2s or larger | Velociraptor needs 2GB+ RAM |
| NSG | Allow 443, 8000, 8001 | GUI, frontend, admin ports |

**Test Environment Variables:**

```bash
# Required
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_CLIENT_ID=<service-principal-id>
AZURE_CLIENT_SECRET=<service-principal-secret>
AZURE_TENANT_ID=<tenant-id>

# Optional
AZURE_RESOURCE_GROUP=megaraptor-test   # Use existing RG
AZURE_LOCATION=eastus                  # Deployment region
```

**Estimated Test Duration:** 15-30 minutes per full cycle

**Cost Estimate:** $0.10-0.20 per test cycle (Standard_B2s pricing)

#### CLOUD-02 Test Implementation Outline

```python
@pytest.mark.cloud
@pytest.mark.azure
@skip_if_no_azure_credentials
async def test_azure_arm_deployment():
    """Full Azure ARM template deployment lifecycle test."""
    # 1. Deploy resources
    result = await deploy_server_cloud(
        provider="azure",
        template="arm",
        location="eastus",
        vm_size="Standard_B2s"
    )
    assert result.success

    try:
        # 2. Wait for healthy
        await wait_for_deployment_healthy(result.deployment_id, timeout=300)

        # 3. Validate API
        health = await get_deployment_status(result.deployment_id)
        assert health["api_healthy"]

    finally:
        # 4. Cleanup
        await destroy_deployment(result.deployment_id, force=True)
```

### Cross-Cloud Requirements

#### CLOUD-03: Cross-Cloud Consistency Validation

**Objective:** Verify consistent behavior and capabilities across cloud providers to ensure investigators get the same experience regardless of deployment target.

**Consistency Test Matrix:**

| Capability | AWS Baseline | Azure Must Match |
|------------|--------------|------------------|
| Velociraptor Version | Configurable, default latest | Same version |
| API Configuration | Standard endpoints | Same configuration |
| Agent Enrollment | MSI/GPO/SSH methods | Same methods |
| Artifact Collection | All standard artifacts | Same artifacts |
| VQL Execution | Full VQL support | Same queries work |
| Cleanup Behavior | Full resource removal | Equivalent cleanup |

**Cross-Cloud Test Cases:**

1. **Version Consistency:** Deploy same Velociraptor version to both clouds, verify `server_version` matches
2. **API Parity:** Same API calls work identically on both deployments
3. **Enrollment Parity:** Agents enrolled via same method connect to both clouds
4. **Artifact Parity:** Same artifact collections produce equivalent structures

**Implementation Notes:**

- Tests require both AWS and Azure credentials
- May need dedicated test orchestration for cross-cloud scenarios
- Consider parameterized tests: `@pytest.mark.parametrize("provider", ["aws", "azure"])`

### Test Automation Considerations

#### CI/CD Integration Strategy

Cloud tests have unique requirements compared to local tests:

| Consideration | Recommendation |
|---------------|----------------|
| Cost Control | Run on schedule (daily/weekly), not every commit |
| Instance Types | Use spot/preemptible instances to reduce cost |
| Budget Alerts | Set monthly budget limits ($50-100) |
| Parallel Execution | One cloud at a time to avoid cost spikes |
| Cleanup Verification | Automated check for orphaned resources |

#### Skip Guards for Cloud Tests

```python
def has_aws_credentials():
    """Check if AWS credentials are available."""
    return (
        os.environ.get("AWS_ACCESS_KEY_ID") and
        os.environ.get("AWS_SECRET_ACCESS_KEY")
    )

def has_azure_credentials():
    """Check if Azure credentials are available."""
    return (
        os.environ.get("AZURE_SUBSCRIPTION_ID") and
        os.environ.get("AZURE_CLIENT_ID") and
        os.environ.get("AZURE_CLIENT_SECRET") and
        os.environ.get("AZURE_TENANT_ID")
    )

skip_if_no_aws_credentials = pytest.mark.skipif(
    not has_aws_credentials(),
    reason="AWS credentials not configured"
)

skip_if_no_azure_credentials = pytest.mark.skipif(
    not has_azure_credentials(),
    reason="Azure credentials not configured"
)
```

#### Mock Mode for Local Development

For development without cloud credentials:

```python
@pytest.fixture
def mock_cloud_deployer(monkeypatch):
    """Mock cloud deployment for local testing."""
    async def mock_deploy(*args, **kwargs):
        return DeploymentResult(
            success=True,
            deployment_id="mock-cloud-001",
            server_url="https://localhost:8000",
            message="Mock deployment (cloud not available)"
        )

    monkeypatch.setattr(
        "megaraptor_mcp.deployment.cloud.deploy_server_cloud",
        mock_deploy
    )
```

### Estimated Resource Requirements

#### AWS Resource Budget

| Resource | Type | Est. Hourly | Monthly Cap |
|----------|------|-------------|-------------|
| EC2 | t3.medium | $0.0416 | $30 |
| EBS | 30GB gp3 | $0.08/GB | $3 |
| Data Transfer | 1GB/test | $0.09/GB | $10 |
| **Total** | | | **$43** |

#### Azure Resource Budget

| Resource | Type | Est. Hourly | Monthly Cap |
|----------|------|-------------|-------------|
| VM | Standard_B2s | $0.0416 | $30 |
| Managed Disk | 30GB Standard | $0.05/GB | $2 |
| Network | 1GB/test | $0.087/GB | $10 |
| **Total** | | | **$42** |

#### Combined Monthly Budget: $100

Allows approximately 50-100 test cycles per month across both clouds.

### Dependencies on v1.0

Cloud testing should not begin until the following v1.0 items are complete:

| Dependency | Status | Notes |
|------------|--------|-------|
| Docker deployment validation | Complete | Proves core deployment logic |
| Binary deployment validation | Complete | Proves SSH deployment path |
| Agent enrollment mechanisms | Complete | Required for full cloud tests |
| Error handling robustness | Complete | Cloud has more failure modes |
| Deployment state persistence | Recommended | Helps with test debugging |

### Cloud Testing Roadmap

**Phase 1: AWS Foundation (v2.0)**
- Implement CLOUD-01 test suite
- Validate CloudFormation template
- Document AWS-specific issues

**Phase 2: Azure Parity (v2.0)**
- Implement CLOUD-02 test suite
- Validate ARM template
- Document Azure-specific issues

**Phase 3: Cross-Cloud (v2.1)**
- Implement CLOUD-03 consistency tests
- Parameterized provider testing
- Cross-cloud documentation

**Phase 4: GCP Extension (v2.2+)**
- Evaluate GCP Deployment Manager support
- Implement if demand exists

### Cloud Testing Summary

| Requirement | Scope | Infrastructure | Est. Cost |
|-------------|-------|----------------|-----------|
| CLOUD-01 | AWS CloudFormation | AWS account, VPC, EC2 | $50/month |
| CLOUD-02 | Azure ARM | Azure subscription, VNet, VM | $50/month |
| CLOUD-03 | Cross-cloud consistency | Both clouds | Included |

**v2 Milestone Target:** Validate cloud deployments work end-to-end with same reliability as Docker deployments.

---

## Document Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-26 | Initial gap analysis - tool capabilities, deployment recommendations, cloud scope |

---

*This document satisfies requirements GAP-01, GAP-02, and GAP-03 from the v1.0 Quality & Real-World Validation milestone.*

