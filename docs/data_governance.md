# Data Governance & Audit Trail

## Mission & Scope
- Provide a unified framework for data classification, retention, and access across Redis, Postgres, S3, and external vendors.
- Guarantee that every trading decision and outbound communication is reconstructible for internal audit or regulatory review.
- Define controls that keep customer-facing artifacts (dashboards, social posts, reports) consistent with source-of-truth data while safeguarding sensitive information.

## Data Classification
| Class | Description | Examples | Storage tier | Access |
|-------|-------------|----------|--------------|--------|
| Critical Trading | Data driving signal, execution, risk decisions | `derived:analytics:*`, `trading.signals`, `trading.trades` | Redis (short-term), Postgres (long-term) | Core services, risk, compliance |
| Operational Metrics | Health, latency, watchdog telemetry | `metrics:*`, `system:heartbeat:*`, observability logs | Redis, Postgres snapshots | Operations, engineering |
| Communications | Templates, outbound payloads, localization | `social:payload:*`, S3 exports, `templates/*` | Redis (short-term), S3 (90d) | Marketing, stakeholders |
| Reference | Static metadata: symbols, accounts, configs | `reference.symbols`, `config/*` | Postgres, Git | Engineering, risk |
| Audit Artifacts | Immutable logs, approvals, schemas | `watchdog:review:*`, `reporting.tiles`, alert streams | Postgres, S3 Glacier | Compliance only |

## Storage & Retention Policies
| Data source | Primary store | TTL / retention | Rationale |
|-------------|--------------|-----------------|-----------|
| Redis `raw:*` (ingestion) | Redis volatile | TTL 6–900s per feed | Matches ingestion cadences; stale data auto purged |
| Redis `derived:*` (analytics) | Redis volatile | TTL 20–120s | Keeps latest analytics for downstream modules |
| Redis `state:*` (locks, heartbeats) | Redis volatile | TTL 2× cadence | Prevents zombie locks |
| Redis `social:payload:*` | Redis volatile | TTL 2h | Enables resends without long-term storage |
| Redis `reporting:tiles:*` | Redis volatile | TTL 60s | Web UI caches live state only |
| Postgres `trading.*` | Postgres | 7 years | Trade reconstruction, tax, compliance |
| Postgres `analytics.*` baselines | Postgres | 2 years | Support anomaly detection backtests |
| Postgres `audit.metrics_snapshots` | Postgres | 30 days | Ops dashboards; older data archived to S3 monthly |
| Postgres `reporting.tiles` | Postgres | 180 days | Enables drift analysis & investor reporting |
| S3 `reporting_exports/{env}` | S3 Standard (90d) → Glacier (7y) | Regulatory & investor reports |
| Watchdog approvals (`watchdog:review:*`) | Redis (2h) → Postgres (`compliance.watchdog_reviews`) | 7 years | Supervisory record |
| Logs (structured JSON) | Filebeat → S3 | 2 years | Security investigations |

Retention values are mastered in `config/retention.yml`; cleanup jobs (Redis sweeps, S3 lifecycle policies, Postgres archive scripts) must read from this file so the doc, config, and automation stay in lockstep.

## Access Controls
- **Role matrix** (enforced in API gateway & database schemas):
  - `role:engineer` → read/write non-production Redis, read-only production analytics, no trading tables.
  - `role:trader` → read/write signals, read execution, no schema modifications.
  - `role:risk` → read-only trading & analytics, write risk overrides (logged).
  - `role:compliance` → read-only all stores, can trigger regulatory exports.
  - `role:product` → read communications, dashboards; no trading access.
- Redis access via TLS auth tokens per environment; production tokens rotated every 30 days.
- Postgres uses managed roles (`trading_rw`, `analytics_ro`, `compliance_ro`) with strict GRANT statements; migrations apply through CI only.
- S3 buckets enforce bucket policies requiring MFA for delete and server-side encryption (SSE-S3).

## Audit Logging
- Every state-changing CLI / API call emits structured logs with `user_id`, `env`, `action`, `payload_hash`.
- Watchdog approvals/rejections stored in Postgres with reviewer, timestamp, reason; Redis copy purely for live workflows.
- Execution module records `trade:events` to Postgres `trading.execution_events` (immutable); reconciliation job validates no missing sequences.
- Alert dispatcher stores final payload in `state:alerts:last:{dedupe_key}`; dead letters persisted for inspection.
- Export jobs append metadata to `compliance.exports` (fields: `type`, `run_id`, `schema_hash`, `location`, `requested_by`).

## Data Lineage & Provenance
1. **Ingestion** → Vendor payload stored under `raw:*` with `source`, `fetched_at`.
2. **Normalization** → Analytics job annotates `derived:*` with `inputs_sha`, `producer` (e.g., `analytics@v1.12.0`), and `computed_at`.
3. **Signal generation** → `trading.signals` row references `inputs_sha`, `analytics_version`, `strategy_revision`, and captures `producer`.
4. **Execution** → `trading.trades` links back to `signal_id`, captures broker fills, and stores the execution engine version.
5. **Reporting** → Tile payload includes `serving_version`, `is_stale`, `lineage` (list of `inputs_sha` + producers), and `producer` (reporting worker version).
6. **Exports** → PDF/CSV embed metadata block with `env`, `report_version`, `schema_hash`, `producer`, `generated_at`, and `lineage_sha`.

## Regulatory & Stakeholder Exports
| Export | Trigger | Contents | Destination | Notes |
|--------|---------|----------|-------------|-------|
| Daily supervisory bundle | 18:00 ET (compliance) | Signals, approvals, executions, PnL summary | S3 + encrypted email | Zip with JSON + CSV + checksum |
| Monthly investor pack | 1st business day | Performance, risk metrics, attribution, market commentary | S3 + email to investor list | Requires doc review step |
| Reg SHO / SEC audit trail | On request | All trades + approvals within window | Encrypted SFTP | Generated via `reporting.cli export --format csv --regulatory` |
| Social disclosure log | Weekly cron | Posts per platform with timestamps & env tags | S3 | Used for marketing compliance |

All exports use schema hashes registered in `config/export_schemas.yml`; CI fails if schema changes without approval.

Each export and watchdog review record also stores an immutable `audit_id = sha256(env|type|timestamp|payload_sha)` to provide tamper-evident dedupe keys and support external verification.

## Compliance & Monitoring Controls
- **Schema validation**: nightly job compares actual table/Redis schemas vs. expected manifests; drift raises `governance_schema_drift` alert.
  - Manifests live under `config/schema_manifests/` (Postgres column/type definitions, Redis key patterns). High-risk drift (missing column, unexpected key) fails closed and pages compliance.
- **Retention sweeps**: cron jobs delete data past retention windows (e.g., flush Redis `social:payload:*` over 2h, purge S3 >90d).
- **Sensitive data scanner**: weekly job runs regex checks on Redis/Postgres to ensure no PII leaked into public tiers.
- **Access reviews**: quarterly audit of IAM roles, documented in `compliance/access_reviews` table.
  - Store reviewer, review_date, method (manual/automated), before/after diff of grants, and sign-off user to provide evidence beyond a checkbox.
- **Immutable logs**: shipping to append-only storage (AWS CloudTrail/Kinesis) to prevent tampering.

## Incident Response
| Scenario | Immediate steps | Follow-up |
|----------|-----------------|-----------|
| Unauthorized data access | Disable compromised credentials, review Redis/Postgres logs, notify compliance | File incident report, rotate keys, update access review |
| Schema drift detected | Halt dependent jobs, revert recent migrations, regenerate schema hash | Update manifests, add regression tests |
| Export failure | Inspect `state:reporting:dead_letter:*`, rerun `reporting.cli export`, notify stakeholders | Patch template, add regression tests |
| Data retention lapse | Run cleanup scripts, document scope, notify CISO | Review automation, add monitoring |

## Change Management
- Changes to template schemas, export formats, or retention windows require PR + compliance approval tag (`@compliance-review`) before merge.
- Any update to `config/dashboard.yml`, `config/template_validation.yml`, or `config/export_schemas.yml` must include updated tests and schema hashes.
- Versioning for templates: include suffix `:vN` in filename or update release tag `templates-vYYYY.MM`; note change log in PR.
- Maintain `docs/changelog.md` entries for governance-impacting changes (schema, retention, access).

## Implementation Checklist
- [ ] Define data classification map in code (enum with enforcement hooks).
- [ ] Implement Redis/Postgres schema manifests and nightly drift job.
- [ ] Wire lineage metadata (`inputs_sha`, `serving_version`, `env`) into all payloads.
- [ ] Ensure watchdog, social, reporting exports include env tags and schema hashes.
- [ ] Automate retention sweeps with alerts on failure.
- [ ] Build compliance CLI (`python -m src.compliance.cli`) for exports/access reports.
- [ ] Configure S3 lifecycle policies (Standard → Glacier) per retention table.
- [ ] Add automated access review report (quarterly) with sign-off workflow.
- [ ] Test regulatory export end-to-end with scrubbed fixtures.
- [ ] Document rollback procedures for schema or template changes.
