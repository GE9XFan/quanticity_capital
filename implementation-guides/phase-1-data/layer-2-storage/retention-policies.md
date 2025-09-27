# Retention Policies

## Objectives
- Balance hot storage performance with long-term compliance retention.
- Ensure analytics can access required lookbacks without manual intervention.

## Retention Matrix
| Data Stream | Granularity | Retention | Storage Tier |
|-------------|-------------|-----------|--------------|
| Option chain ticks | 1s | 7 days | Redis hot |
| Option chain aggregated | 1m | 30 days | Redis warm |
| Greeks | 1m | 90 days | Redis warm |
| Liquidity stress | 5m | 180 days | Redis warm |
| Macro overlay | 1d | 5 years | Cold storage (S3/Parquet) |

## Policy Controls
- Redis retention enforced via `TS.CREATE RETENTION` per contract spec.
- Cold storage archiving executed nightly via `storage/data_persistence.py` jobs.
- Verification: `scripts/redis_retention_audit.py` compares expected TTL vs actual.

## Compliance Considerations
- Align retention with regulatory requirements (minimum 7 years for trade data as needed).
- Document deletion procedures for data subject requests.
- Record retention changes in `contracts/version-history.md` with approver sign-off.

## Review Cadence
- Quarterly review with Data Governance team.
- Trigger ad hoc review when new strategies or jurisdictions onboarded.
