# BUILD CARD 008: Redis Backup Automation

**Difficulty:** ⭐⭐⭐☆☆
**Time:** 4 hours
**Prerequisites:**
- CARD_007 complete
- Access to backup storage (S3/Glacier)
- Backup strategy defined in `backup-strategy.md`

## Objective
Automate Redis snapshot creation, upload, verification, and retention enforcement according to the storage backup strategy.

## Success Criteria
- [ ] Scheduled job triggers hourly/daily backups per policy
- [ ] Checksums logged and stored with manifest entries
- [ ] Failure alerts emit to monitoring stack
- [ ] Integration test `pytest tests/layer2/test_redis_backup.py` mocks backup flow

## Implementation
1. Develop `scripts/redis_backup.py` with subcommands `snapshot`, `upload`, `verify`.
2. Store backup metadata in `storage/backups/manifest.json`.
3. Configure scheduler (cron/Kubernetes job) using documented frequencies.
4. Add alert rules for backup failures pointing to `backup-strategy.md` runbook section.

## Verification
- `pytest tests/layer2/test_redis_backup.py`
- Dry-run `python scripts/redis_backup.py snapshot --env dev --dry-run`
- Confirm manifest entries and metrics `storage.backup.success` in monitoring dashboard.

## Links to Next Cards
- CARD_010 (future): Cold Storage Restore Drill
- [CARD_009](CARD_009.md): Query Helper API
