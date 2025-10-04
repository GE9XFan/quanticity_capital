# REST Ingestion Documentation

## Overview

The REST ingestion system fetches data from 30+ Unusual Whales endpoints and stores raw JSON responses to disk for further processing. This Phase 0 implementation focuses on reliable data capture with proper rate limiting and error handling.

## Architecture

```
src/
  config/
    settings.py         # Pydantic settings with env var loading
  clients/
    unusual_whales.py   # httpx-based async HTTP client with retry logic
  ingestion/
    uw_endpoints.py     # Data-driven endpoint definitions
    rest_runner.py      # Orchestrates fetching all endpoints
  cli/
    uw_rest_fetch.py    # CLI entry point with logging setup
```

## Running the Fetcher

### Latest Run Snapshot

| Date (UTC) | Symbols | Requests | Success | Failures |
|------------|---------|----------|---------|----------|
| 2025-10-04 21:12 | SPY, QQQ, IWM | 243 | 243 | 0 |
| 2025-10-04 20:10 | SPY, QQQ, IWM | 81 | 81 | 0 |

The table is updated after every verified live pull. Review the log files in `logs/` for detailed timing and retry behaviour.

### Basic Usage

```bash
# 1) Set your API token in .env
echo "UNUSUAL_WHALES_API_TOKEN=your_token_here" >> .env

# 2) (Optional) Opt into Redis snapshots and adjust loop interval
# echo "STORE_TO_REDIS=true" >> .env
# echo "FETCH_INTERVAL_SECONDS=0" >> .env

# 3) Start Redis if snapshots are enabled
redis-server &
# or: docker run --rm -p 6379:6379 redis:7

# 4) Run the fetcher once
make uw-rest-fetch

# 5) Run continuously (every 15 minutes)
python -m src.cli.uw_rest_fetch --loop --interval 900

# 6) Loop a fixed number of times (example: 3 iterations)
python -m src.cli.uw_rest_fetch --loop --interval 900 --max-iterations 3
```

Use `Ctrl+C` at any time to stop the loop gracefully; the CLI will close Redis connections before exiting.

### Configuration

All settings via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `UNUSUAL_WHALES_API_TOKEN` | (required) | Your API token |
| `TARGET_SYMBOLS` | `SPY,QQQ,IWM` | Comma-separated ticker list |
| `STORE_TO_REDIS` | `true` | Enable Redis snapshot writing |
| `ENABLE_HISTORY_STREAMS` | `true` | Append history feeds to capped Redis streams |
| `REDIS_STREAM_MAXLEN` | `5000` | Max entries to keep per stream |
| `STORE_TO_POSTGRES` | `false` | Persist history feeds into Postgres |
| `POSTGRES_DSN` | `postgresql://postgres:postgres@localhost:5432/quanticity` | Postgres connection string |
| `FETCH_INTERVAL_SECONDS` | `0` | Loop interval in seconds (`0` disables loop) |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `100` | Max API requests/minute |
| `RATE_LIMIT_LEEWAY_SECONDS` | `0.5` | Extra safety delay |
| `REQUEST_TIMEOUT_SECONDS` | `30.0` | HTTP request timeout |

### Output Structure

Data saved to `data/unusual_whales/raw/`:

```
data/unusual_whales/raw/
  darkpool/
    SPY_2024-01-20T15-30-00.json
    QQQ_2024-01-20T15-30-01.json
    index.ndjson
  greek_exposure/
    SPY_2024-01-20T15-30-02.json
    index.ndjson
  economic_calendar/
    2024-01-20T15-30-03.json
    index.ndjson
  ...
```

Each JSON file contains:
```json
{
  "metadata": {
    "saved_at": "2024-01-20T15:30:00",
    "endpoint_key": "darkpool",
    "ticker": "SPY",
    "status_code": 200,
    "timestamp": 1705764600.0
  },
  "data": {
    // Raw API response
  }
}
```

## Monitoring the Run

- **Logs** (latest run):

  ```bash
  tail -f "$(ls -t logs/unusual_whales_rest_*.log | head -n 1)"
  ```

- **Disk outputs** (replace `<endpoint>` with e.g. `market_tide`):

  ```bash
  ls -lt data/unusual_whales/raw/<endpoint> | head
  tail -n 5 data/unusual_whales/raw/<endpoint>/index.ndjson
  ```

- **Redis snapshots** (requires `STORE_TO_REDIS=true`):

  ```bash
  redis-cli KEYS 'uw:rest:*'
  redis-cli HGETALL uw:rest:market_tide
  redis-cli HGETALL uw:rest:flow_alerts:SPY
  ```

- **Postgres history** (requires `STORE_TO_POSTGRES=true`):

  ```bash
  psql "$POSTGRES_DSN" -c "SELECT endpoint, symbol, fetched_at FROM uw_rest_history ORDER BY fetched_at DESC LIMIT 5;"
  ```

  Remember to run the DDL first:

  ```bash
  psql "$POSTGRES_DSN" -f sql/uw_rest_history.sql
  ```

## Endpoints Fetched

### Global Endpoints (no ticker required)
- `economic_calendar` - Economic events
- `market_tide` - Market-wide indicators
- `market_oi_change` - Market open interest changes
- `market_top_net_impact` - Top net impact
- `market_total_options_volume` - Total options volume
- `net_flow_expiry` - Net flow by expiry

### Per-Ticker Endpoints
- **Dark Pool**: `darkpool`
- **ETF Data**: `etf_exposure`, `etf_inoutflow`, `etf_tide`
- **Flow Data**: `flow_alerts`, `flow_per_expiry`
- **Greeks**: `greek_exposure`, `greek_exposure_expiry`, `greek_exposure_strike`, `greek_flow`
- **Volatility**: `interpolated_iv`, `iv_rank`, `volatility_term_structure`
- **Options**: `max_pain`, `net_prem_ticks`, `nope`, `oi_change`, `option_chains`, `options_volume`
- **Price**: `ohlc_1m`, `spot_exposures`, `spot_exposures_strike`
- **Stock**: `stock_state`, `stock_volume_price_levels`

## Error Handling

- **429 Rate Limit**: Waits for Retry-After header, then retries
- **5xx Server Errors**: Retries once with 5s delay
- **Network/Timeout**: Retries once with exponential backoff
- **4xx Client Errors**: Logs error, no retry

## Logging

Logs written to:
- Console (stdout) - INFO level
- `logs/unusual_whales_rest_YYYYMMDD_HHMMSS.log` - Full details

Log format:
```
2024-01-20 15:30:00 - src.ingestion.rest_runner - INFO - ✓ darkpool:SPY → data/unusual_whales/raw/darkpool/SPY_2024-01-20T15-30-00.json
```

## Development

### Adding New Endpoints

Edit `src/ingestion/uw_endpoints.py`:

```python
Endpoint(
    key="new_endpoint",
    path_template="/api/new/{ticker}/data",
    requires_ticker=True,
    query_params={"limit": 100},
    accept_header="application/json",
    description="New endpoint description"
)
```

### Customizing Rate Limits

Adjust in `.env`:
```
RATE_LIMIT_REQUESTS_PER_MINUTE=60  # More conservative
RATE_LIMIT_LEEWAY_SECONDS=1.0      # More buffer
```

### Processing Saved Data

Example script to read saved data:

```python
import json
from pathlib import Path

data_dir = Path("data/unusual_whales/raw")

# Read all darkpool data for SPY
for file in sorted(data_dir.glob("darkpool/SPY_*.json")):
    with open(file) as f:
        entry = json.load(f)
        print(f"Timestamp: {entry['metadata']['saved_at']}")
        print(f"Data: {entry['data']}")
```

## Limitations

- **Disk Storage Only**: Phase 0 saves to disk, not Redis
- **No Scheduling**: Manual runs only (add cron for automation)
- **No Deduplication**: Each run creates new files
- **Basic Retry Logic**: Simple exponential backoff

## Next Steps

1. **Redis Integration**: Store latest snapshots in Redis keys
2. **WebSocket Consumer**: Add real-time data ingestion
3. **Data Pipeline**: Connect to analytics/signals modules
4. **Scheduling**: Add automated periodic fetching
5. **Cleanup**: Implement data retention policies
