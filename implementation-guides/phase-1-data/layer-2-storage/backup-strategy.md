# Backup Strategy

## Goals
- Maintain recoverable snapshots of Redis data with minimal RPO/RTO.
- Support compliance retention timelines for trade and analytics data.

## Snapshot Policy
- Hourly RDB snapshots stored locally with retention of 24 hours.
- Daily snapshots exported to S3 bucket `s3://quantum-backups/redis/` with 30-day retention.
- Weekly full backup archived to Glacier (or equivalent) for 1-year retention.

## Automation
- Schedule backup jobs via `scripts/redis_backup.py` triggered by cron or orchestrator.
- Use server-side encryption (SSE-S3 or SSE-KMS) for all cloud backups.
- Record backup metadata (timestamp, checksum, size) in `storage/backups/manifest.json`.

## Restore Procedure
1. Identify required snapshot from manifest.
2. Pull snapshot into staging environment and run validation `scripts/redis_restore_check.py`.
3. For production incidents, coordinate with Platform Ops before restoring.
4. After restore, execute `scripts/bootstrap_redis_timeseries.py --audit` to confirm rules intact.

## Testing
- Quarterly restore drills documented in `runbooks/redis-restore.md` (TBD).
- Automated checksum verification appended to CI pipeline.

## Notifications
- Emit backup success/failure metrics `storage.backup.success` and `storage.backup.failure`.
- Alert on backup failure or missing snapshot older than 26 hours.
