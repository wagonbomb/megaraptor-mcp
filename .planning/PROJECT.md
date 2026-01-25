# Megaraptor MCP

## What This Is

An MCP server that exposes Velociraptor DFIR platform capabilities to AI assistants. Enables security analysts to interact with Velociraptor through natural language for endpoint visibility, threat hunting, and incident response. Includes deployment automation for standing up Velociraptor infrastructure.

## Core Value

All 35 MCP tools work reliably against real Velociraptor deployments with actionable output and graceful error handling.

## Current Milestone: v1.0 Quality & Real-World Validation

**Goal:** Validate all MCP tools and deployment features against real Velociraptor infrastructure, document capability gaps.

**Target features:**
- Comprehensive DFIR tool validation against live Velociraptor
- End-to-end on-prem deployment testing (container → physical → agents)
- Gap analysis documenting needed tool additions

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Tool infrastructure (35 MCP tools registered)
- Resource browsing (velociraptor:// URI scheme)
- 8 workflow prompts for guided DFIR operations
- Deployment automation (Docker, Binary, AWS, Azure)
- Agent deployment via SSH/WinRM
- Certificate management and credential storage
- Test lab infrastructure (104 tests passing)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Every DFIR tool tested against live Velociraptor container
- [ ] Error handling validated with edge cases and failure modes
- [ ] Output quality verified for DFIR workflow utility
- [ ] Performance tested with large result sets
- [ ] Docker deployment end-to-end validated
- [ ] Physical/virtual server deployment validated
- [ ] Agent deployment to endpoints validated
- [ ] Gap analysis document with needed additions

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Cloud deployment testing (AWS/Azure) — Deferred to post-on-prem validation
- New tool implementation — Focus on validating existing tools first
- UI/visualization features — MCP is API-first for AI assistants

## Context

**Technical Environment:**
- Python 3.10+ MCP server with async gRPC client
- Velociraptor 0.72+ with gRPC API enabled
- Test container available for initial validation
- Physical lab infrastructure for advanced testing

**Prior Work:**
- Phase 1-2 test lab infrastructure complete (104 tests)
- Mocked tests provide baseline, now need real integration
- Deployment features built but need e2e validation

**Known Issues:**
- Some tools only tested with mocks, not live server
- VQL error handling may need improvement
- Large result pagination untested at scale

## Constraints

- **Test Infrastructure**: Must use existing test container before physical servers
- **Progression**: Container → Physical → Cloud (not parallel)
- **Focus**: Quality over quantity — validate before adding

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Test container first | Lower risk, faster iteration | — Pending |
| On-prem before cloud | Validate core before platform-specific | — Pending |
| Gap analysis over new features | Understand needs before building | — Pending |

---
*Last updated: 2026-01-24 after milestone v1.0 initialization*
