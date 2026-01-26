# Megaraptor MCP

## What This Is

An MCP server that exposes Velociraptor DFIR platform capabilities to AI assistants. Enables security analysts to interact with Velociraptor through natural language for endpoint visibility, threat hunting, and incident response. Includes deployment automation for standing up Velociraptor infrastructure.

## Core Value

All 35 MCP tools work reliably against real Velociraptor deployments with actionable output and graceful error handling.

## Current State

**Version:** v1.0 Quality & Real-World Validation (shipped 2026-01-26)

**Codebase:**
- 19,672 lines of Python
- 35 MCP tools, 10 resources, 8 prompts
- FastMCP-based server (MCP SDK 1.25.0 compatible)
- Comprehensive error handling with validators, hints, and retry logic

**Test Coverage:**
- 104+ integration tests
- 6 phases of validation (infrastructure, smoke, errors, OS-specific, quality, deployment)
- NIST CFTT compliance (<1% false positive rate)

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Format: - ✓ [Requirement] — v[X.Y] -->

**Pre-v1.0:**
- ✓ Tool infrastructure (35 MCP tools registered)
- ✓ Resource browsing (velociraptor:// URI scheme)
- ✓ 8 workflow prompts for guided DFIR operations
- ✓ Deployment automation (Docker, Binary, AWS, Azure)
- ✓ Agent deployment via SSH/WinRM
- ✓ Certificate management and credential storage
- ✓ Test lab infrastructure (104 tests passing)

**v1.0:**
- ✓ Every DFIR tool tested against live Velociraptor container — v1.0
- ✓ Error handling validated with edge cases and failure modes — v1.0
- ✓ Output quality verified for DFIR workflow utility — v1.0
- ✓ Docker deployment end-to-end validated — v1.0
- ✓ Agent deployment tests (skip-guarded for missing infrastructure) — v1.0
- ✓ Gap analysis document with needed additions — v1.0

### Active

<!-- Current scope. Building toward these in next milestone. -->

- [ ] Timeline generation tool for DFIR event sequencing
- [ ] IOC extraction tool for threat hunting
- [ ] Report generation tool for documentation
- [ ] File remediation tool for response capability
- [ ] AWS CloudFormation deployment validation
- [ ] Azure ARM template deployment validation
- [ ] Performance testing with large result sets (10K+ rows)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Mobile agent deployment — Focus on server/workstation endpoints first
- UI/visualization features — MCP is API-first for AI assistants
- Real-time monitoring dashboards — Out of scope for CLI tool
- AI-enhanced error detection — Emerging pattern, not mature for production

## Context

**Technical Environment:**
- Python 3.10+ MCP server with async gRPC client
- Velociraptor 0.72+ with gRPC API enabled
- FastMCP for tool registration (MCP SDK 1.25.0+)
- Tenacity for retry logic with exponential backoff

**v1.0 Accomplishments:**
- Migrated to FastMCP for SDK compatibility
- Comprehensive error handling module (validators, gRPC mapping, VQL hints)
- OS-specific artifact testing (Linux working, Windows skip-guarded)
- NIST CFTT forensic quality validation
- Gap analysis identifying 4 critical tool additions needed

**Known Issues:**
- Windows artifact tests require Windows target (skip-guarded)
- SSH/WinRM agent deployment tests require targets (skip-guarded)
- Placeholder baseline files awaiting live population

## Constraints

- **Progression**: On-prem validated → Cloud testing (v2)
- **Focus**: Quality over quantity — validate before adding
- **Phase Numbering**: Continues from v1.0 (phases 1-6 complete, v2 starts at phase 7)

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Test container first | Lower risk, faster iteration | ✓ Good — enabled rapid validation |
| On-prem before cloud | Validate core before platform-specific | ✓ Good — deferred cloud to v2 |
| Gap analysis over new features | Understand needs before building | ✓ Good — identified 4 critical gaps |
| Subprocess container lifecycle | pytest-docker deferred for simplicity | ✓ Good — works reliably |
| FastMCP migration | MCP SDK 1.25.0 compatibility | ✓ Good — all 35 tools work |
| Skip guards for missing infra | Tests ready when targets available | ✓ Good — no false failures |
| NIST CFTT compliance | Forensic soundness requirement | ✓ Good — <1% false positive validated |

---
*Last updated: 2026-01-26 after v1.0 milestone completion*
