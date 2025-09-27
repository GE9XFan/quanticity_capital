# Agents & Automation Playbook

## 1. Purpose & Scope
This document keeps every human and automated agent aligned while delivering the Quantum Trading System. It extends the architecture blueprint (`quantum-trading-architecture.md`) and the implementation knowledge base (`implementation-guides/`) with explicit guidance on:
- Which agents exist (human owners and automated assistants) and what they are accountable for.
- How agents collaborate across phases, build cards, contracts, and runbooks.
- Required evidence, tooling, and escalation paths so that automation never diverges from the documented plan.

> **Effective Date:** Saturday, 27 September 2025 00:00 UTC  
> **Maintainer:** Michael Merrick (Platform & Programme Lead)

---

## 2. Governance Principles
1. **Documentation First.** No agent may perform work that is not pre-authorised by build cards or runbooks. Missing documentation is treated as a blocker.  
2. **Evidence Oriented.** Every automated action must emit artefacts into `docs/evidence/` and link them to the relevant checklist entry (`implementation-guides/VALIDATION_CHECKLIST.md`).  
3. **Contract Integrity.** Payloads, schemas, and external integrations MUST reference `implementation-guides/contracts/`. Agents raise `schema-drift` incidents when a payload deviates.  
4. **Least Privilege.** Agents operate with the minimal permissions required for their role. Secrets are sourced through Phase 0 controls (`implementation-guides/phase-0-foundations/README.md`).  
5. **Runbook Driven Recovery.** When an alert fires or a task fails, agents consult runbooks before taking discretionary action.  
6. **Versioned Decisions.** All non-trivial changes (code, contracts, infrastructure) must reference a build card ID and provide a commit summary referencing this `agents.md` when the workflow is agent-led.

---

## 3. Agent Catalog

| Agent ID | Type | Owner / Contact | Mission | Key Artefacts | Triggers & Inputs | Outputs & Evidence | Escalation |
|----------|------|-----------------|---------|---------------|-------------------|--------------------|------------|
| A-000 | **Programme Steward** (human) | Michael Merrick | Owns roadmap, approves agent scopes & evidence packages | `implementation-guides/timeline.yaml`, `phase-metrics.yaml`, this doc | Phase checkpoints, escalations from any agent | Roadmap updates, approvals, sign-offs | Direct call; if unavailable, freeze automation and log in `docs/evidence/` |
| A-010 | **Codex Implementation Agent** (GPT-5, Codex CLI) | Operated by Programme Steward | Execute documented build cards, update guides, produce tests | `implementation-guides/build-cards/`, `phase-1-data/`, `contracts/` | User instructions + build card prerequisites | Pull requests, doc updates, test logs in `docs/evidence/phase*` | Pause work & request direction if documentation gap or conflicting change |
| A-020 | **QA & Validation Agent** (automation scripts/tests) | Test Engineering Lead (TBD) | Run prescribed pytest suites, contract validators, live smoke checks | `tests/`, `scripts/validate_contract.py`, live scripts under `scripts/` | Triggered post-implementation, before checklist sign-off | Test reports stored in `docs/evidence/phase*/tests/`, metrics exports | On failure, file incident referencing relevant runbook (e.g., `runbooks/schema-drift.md`) |
| A-030 | **Data Ingestion Ops Agent** (future automation) | Data Engineering Lead | Monitor AlphaVantage/IBKR ingest health, enforce rate limits | `implementation-guides/phase-1-data/layer-1-ingestion/` runbooks, Grafana dashboards | Telemetry alerts (`data_ingestion.*`), scheduled verifications | Incident tickets, annotated dashboards, runbook execution notes | If outage >15 min, escalate to Programme Steward |
| A-040 | **Storage Reliability Agent** (future automation) | Platform Ops Lead | Manage Redis TS schema bootstrap, backups, audits | `implementation-guides/phase-1-data/layer-2-storage/`, scripts in `scripts/redis_*` | CARD_003/CARD_007/CARD_008 triggers, cron schedules | Bootstrap manifests, backup manifests, audit logs in `docs/evidence/phase1/storage/` | Escalate to Platform Ops + Programme Steward on backup failure |
| A-050 | **Analytics Integrity Agent** (planned) | Quant Lead | Validate analytics outputs (regime, liquidity, VPIN) meet contracts | `implementation-guides/build-cards/` (future analytics cards), `tests/layer3/` | Phase 2 start, nightly validation jobs | Model validation dossiers, coverage reports | Escalate to Programme Steward and Data Engineering for upstream data issues |
| A-060 | **Execution & Risk Control Agent** (planned) | Trading Systems Lead | Ensure order/risk pipelines conform to contracts & failover runbooks | `tests/layer5/`, `tests/layer6/`, `runbooks/` TBD | Start of Phase 3, pre-production readiness checkpoint | Failover drill logs, reconciliation reports | Escalate to Programme Steward + Risk officer |
| A-070 | **Reporting & Social Agent** (planned) | AI Programs Lead | Automate reporting, dashboards, social distribution verification | `tests/layer8/`, `tests/layer9/`, Phase 4 docs | Phase 4 automation window, release cadences | Report artefact proofs, delivery success logs | Escalate to Programme Steward + Comms lead |
| A-080 | **Observability Agent** (monitoring automation) | Platform Ops Lead | Maintain dashboards, alert routing, evidence snapshots | `implementation-guides/appendices/monitoring-guide.md`, Grafana JSON | Dashboard drift detection, new metrics onboarding | Dashboard exports, alert runbook links | Escalate to Platform Ops + Programme Steward |

> **Note:** Agents A-030 onwards are roadmap placeholders. They become active once their prerequisite build cards, contracts, and runbooks are drafted and approved.

---

## 4. Engagement Workflow

1. **Authorisation**  
   - Programme Steward confirms the build card and phase alignment in `implementation-guides/build-cards/index.md`.  
   - Required prerequisites (Phase 0, configurations, contracts) must be checked as complete.
   - Verify Phase 0 onboarding acknowledgement exists at `docs/evidence/phase0/agents_ack.md`.

2. **Preparation**  
   - Agent gathers artefacts: relevant contract schemas, configuration templates, runbooks.  
   - For Codex, run `git status -sb` to confirm scope and identify pre-existing user changes (do not revert user work).  
   - Update or create plan via the Codex planning tool unless the work is trivial (<25% complexity).

3. **Execution**  
   - Follow the build card step-by-step, referencing required scripts (`scripts/stream_alpha.py`, `scripts/live_checks/`, etc.).  
   - Capture logs and results in `docs/evidence/phase*/` subdirectories (create per-card folders if needed).  
   - Update documentation when behaviour or expectations change; include inline references to relevant files and lines.

4. **Validation**  
   - Trigger QA agent to run automated tests (`pytest`, contract validators, live smoke tests).  
   - Attach outputs, screenshots, and metrics to evidence folders, referencing them in the build card or layer README.  
   - Update the applicable checklist section (`implementation-guides/VALIDATION_CHECKLIST.md`).

5. **Sign-Off**  
   - Programme Steward reviews evidence.  
   - On approval, mark build card status, update `phase-metrics.yaml`, and advance `timeline.yaml` milestones if applicable.  
   - Document lessons learned or deviations in relevant runbooks.

6. **Post-Execution Monitoring**  
   - Observability agent ensures alerts and dashboards reflect new metrics/behaviour.  
   - Storage/Backup agents verify retention and data capture as soon as new feeds go live.

---

## 5. Agent Tooling Matrix

| Tool / Script | Primary Agent | Purpose | Evidence Path |
|---------------|---------------|---------|---------------|
| `scripts/live_checks/alpha_vantage_ping.py` | Codex / QA | Validate live AlphaVantage connectivity (Phase 0, Phase 1) | `docs/evidence/phase0/alpha_vantage/` |
| `scripts/live_checks/ibkr_gateway_ping.py` | Codex / QA | Validate IBKR gateway connectivity | `docs/evidence/phase0/ibkr/` |
| `scripts/stream_alpha.py` | Codex / QA / Data Ops | Live and historical option chain streaming | `docs/evidence/phase1/alpha_vantage/` |
| `scripts/stream_alpha_indicators.py` | Codex / Data Ops | Indicator cache validation | `docs/evidence/phase1/indicators/` |
| `scripts/stream_ibkr.py` | Codex / Data Ops | IBKR parity checks | `docs/evidence/phase1/ibkr/` |
| `scripts/simulate_av_load.py` | QA Agent | Rate limiter stress test | `docs/evidence/phase1/load-tests/` |
| `scripts/bootstrap_redis_timeseries.py` | Storage Agent | Schema provisioning/audit | `docs/evidence/phase1/storage/bootstrap/` |
| `scripts/redis_backup.py` | Storage Agent | Snapshot + verification | `docs/evidence/phase1/storage/backups/` |
| `scripts/query_sample.py` | Analytics / QA | Spot-check Redis query helpers | `docs/evidence/phase1/storage/query/` |

All new tooling must be registered here with owner, purpose, and evidence location before production use.

---

## 6. Escalation Matrix

| Severity | Description | Initial Responder | Escalation Path | SLA |
|----------|-------------|-------------------|-----------------|-----|
| **Critical** | System down, data loss, regulator breach | Owning agent | Programme Steward → Executive Sponsor | Immediate (<15 min) |
| **High** | SLA breach, live trading risk, repeated automation failure | Owning agent | Programme Steward → Relevant domain lead | 1 hour |
| **Medium** | Non-blocking defect, documentation gap | Owning agent | Domain lead (Data, Platform, Quant) | 4 business hours |
| **Low** | Cosmetic issues, suggestions | Owning agent | Weekly review | As available |

Escalations must include: build card ID, phase, evidence links, impacted contracts, and proposed mitigation. File incident notes in `docs/evidence/incidents/{YYYY-MM-DD}-{id}.md`.

---

## 7. Maintenance & Review
- **Quarterly Review:** Programme Steward verifies agent roster against roadmap phases (`timeline.yaml`).  
- **After Major Incident:** Update relevant runbooks and this document to reflect new procedures.  
- **Onboarding:** New agents (human or automated) must be appended to the catalog with owner contact, tooling list, and cross-references.  
- **Audit Trail:** Every edit to `agents.md` must reference change context in the revision history below.

---

## 8. Revision History
| Date | Author | Change Summary |
|------|--------|----------------|
| 2025-09-27 | Michael Merrick | Initial comprehensive agent governance playbook |
