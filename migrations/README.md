# Database Migrations

## Overview

This directory contains PostgreSQL database migrations for the Quanticity Capital trading platform.

## Prerequisites

- PostgreSQL 16.10+ installed and running
- Database created: `createdb quanticity_capital`
- Python packages: `psycopg2-binary`

## Running Migrations

### Option 1: Using psql (Recommended)

```bash
# Connect to your database
psql -U postgres -d quanticity_capital

# Run the migration
\i /Users/michaelmerrick/quanticity_capital/migrations/001_initial_schema.sql

# Verify tables were created
\dt
\dv
```

### Option 2: Using psql from command line

```bash
psql -U postgres -d quanticity_capital -f migrations/001_initial_schema.sql
```

### Option 3: Using Python script

```python
import psycopg2
from pathlib import Path

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="quanticity_capital",
    user="postgres",
    password="your_password"
)

# Read and execute migration
migration_file = Path("migrations/001_initial_schema.sql")
with open(migration_file, 'r') as f:
    sql = f.read()

with conn.cursor() as cur:
    cur.execute(sql)
    conn.commit()

print("Migration completed successfully")
conn.close()
```

## Migration Files

| File | Description | Date |
|------|-------------|------|
| `001_initial_schema.sql` | Initial schema for IB account and portfolio data | 2025-10-03 |

## Schema Overview

### Tables Created:

1. **contracts** - Contract details (normalized reference)
2. **account_summary** - Account summary snapshots (3-min updates)
3. **account_values** - Detailed account values (3-min updates)
4. **positions** - Position snapshots
5. **pnl_daily** - Daily account-level P&L
6. **pnl_positions** - Position-level P&L

### Views Created:

1. **v_latest_account_summary** - Most recent summary for each tag
2. **v_current_positions** - Current non-zero positions
3. **v_latest_eod_pnl** - End-of-day P&L snapshots

### Functions Created:

1. **cleanup_old_data()** - Removes data older than retention period

## Data Retention

- **account_summary:** 2 years
- **account_values:** 2 years
- **positions:** 2 years
- **pnl_positions:** 2 years
- **pnl_daily:** 3 years (longer for annual reporting)
- **contracts:** Retained if referenced by recent positions

## Scheduled Cleanup

Run the cleanup function daily:

```sql
-- Manual execution
SELECT cleanup_old_data();

-- Or schedule with pg_cron (if installed)
SELECT cron.schedule('cleanup-old-data', '0 0 * * *', 'SELECT cleanup_old_data()');
```

## Verifying Migration

```sql
-- Check tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Check views exist
SELECT viewname FROM pg_views WHERE schemaname = 'public';

-- Check sample data (after populating)
SELECT * FROM v_latest_account_summary;
SELECT * FROM v_current_positions;
```

## Rollback

To rollback this migration:

```sql
DROP VIEW IF EXISTS v_latest_eod_pnl;
DROP VIEW IF EXISTS v_current_positions;
DROP VIEW IF EXISTS v_latest_account_summary;

DROP TABLE IF EXISTS pnl_positions CASCADE;
DROP TABLE IF EXISTS pnl_daily CASCADE;
DROP TABLE IF EXISTS positions CASCADE;
DROP TABLE IF EXISTS account_values CASCADE;
DROP TABLE IF EXISTS account_summary CASCADE;
DROP TABLE IF EXISTS contracts CASCADE;

DROP FUNCTION IF EXISTS cleanup_old_data();
DROP FUNCTION IF EXISTS update_contract_timestamp();
```

## Database Configuration

Update `.env` file with your database credentials:

```bash
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/quanticity_capital
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quanticity_capital
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

## Troubleshooting

### Permission Errors

```sql
-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE quanticity_capital TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
```

### Migration Already Run

The migration uses `CREATE TABLE IF NOT EXISTS`, so it's safe to run multiple times. However, best practice is to track which migrations have been applied.

### Check Table Sizes

```sql
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Next Steps

After running migrations:

1. Verify tables created: `\dt`
2. Test insert/select operations
3. Set up scheduled cleanup job
4. Configure application database connection
5. Run integration tests

## Field Mapping Reference

See `docs/3.1 Data Storage Strategy.md` for complete field mapping documentation between IB API and database schema.
