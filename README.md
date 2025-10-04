# Quanticity Capital – Unusual Whales REST Capture

Phase 0 is focused on **calling the live Unusual Whales REST API**, validating the responses, and saving the raw JSON to disk while also mirroring the latest snapshot of each endpoint into Redis. Nothing else is wired yet—no WebSockets, no analytics, no FastAPI. This repository now contains only the tooling required for that task.

## Repository Layout

```
src/
  config/            Runtime settings (pydantic-settings)
  clients/           HTTP client wrapper around httpx
  ingestion/         Endpoint catalogue + ingestion runner
  cli/               CLI entry point (`python -m src.cli.uw_rest_fetch`)

data/unusual_whales/raw/   Raw JSON responses organised by endpoint (history)
logs/                      Timestamped log files from each run
Redis (runtime)            Latest snapshot per endpoint (`uw:rest:<endpoint>[:<symbol>]` – see `docs/storage_plan.md`)
```

All other code from earlier phases has been archived under `archive/` for reference.

## Prerequisites

- Python 3.11
- A valid Unusual Whales API token (advanced plan)

Create/activate a virtualenv and install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the example environment file and set your token (and optional overrides):

```bash
cp .env.example .env
# edit .env and set UNUSUAL_WHALES_API_TOKEN=...
```

Start Redis (required when `STORE_TO_REDIS=true`):

```bash
# Option A: local server (background)
redis-server &

# Option B: Docker container
docker run --rm -p 6379:6379 redis:7
```

## Fetching REST Data

Run the fetcher to hit every documented REST endpoint for the configured tickers (defaults to `SPY,QQQ,IWM`). This command talks to the live API—no mocks.

```bash
# One-time run (about 100 requests for SPY/QQQ/IWM)
make uw-rest-fetch

# Equivalent direct invocation
python -m src.cli.uw_rest_fetch

# Continuous mode (fetch every 15 minutes)
python -m src.cli.uw_rest_fetch --loop --interval 900

# Continuous mode for N iterations (example: 3 loops)
python -m src.cli.uw_rest_fetch --loop --interval 900 --max-iterations 3
```

Outputs:

- Raw responses written to `data/unusual_whales/raw/<endpoint>/<ticker>_<timestamp>.json`
- Per-endpoint indexes (`index.ndjson`) that track when each file was created
- Structured logs in `logs/unusual_whales_rest_<timestamp>.log`
- Redis hashes updated with the latest payload for each endpoint (enable via `STORE_TO_REDIS=true`)

The CLI prints a summary when the run completes, including success/failure counts, Redis write stats, and the destination directory.

### Monitoring the Run

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
  # List keys created during the run
  redis-cli KEYS 'uw:rest:*'

  # Global endpoint example
  redis-cli HGETALL uw:rest:market_tide

  # Ticker endpoint example
  redis-cli HGETALL uw:rest:flow_alerts:SPY
  ```

- **Loop mode**: each cycle prints start/end markers and Redis success counters so you can watch progress in real time. Use `Ctrl+C` to stop cleanly.
- **Loop mode**: each cycle prints start/end markers and Redis success counters so you can watch progress in real time. Press `Ctrl+C` to stop; the CLI handles shutdown and exits with a clear status code.

## Configuration Reference

All runtime settings come from environment variables (see `src/config/settings.py` for defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `UNUSUAL_WHALES_API_TOKEN` | – | **Required** API token |
| `TARGET_SYMBOLS` | `SPY,QQQ,IWM` | Comma-separated list of tickers |
| `STORE_TO_REDIS` | `true` | Write latest payloads into Redis hashes |
| `FETCH_INTERVAL_SECONDS` | `0` | Loop interval in seconds (`0` runs once) |
| `REQUEST_TIMEOUT_SECONDS` | `30.0` | HTTP timeout per request |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `100` | Max requests per minute (hard cap 120) |
| `RATE_LIMIT_LEEWAY_SECONDS` | `0.5` | Extra wait inserted between calls |

## Next Steps (after Phase 0)

1. Decide how to persist the latest payloads (Redis snapshots, Postgres archive, etc.).
2. Introduce scheduling so the fetcher runs continuously or on a cadence.
3. Expand into WebSocket ingestion once the REST flow is locked down.
4. Build analytics, signals, and the rest of the trading pipeline on top of the captured data.

Until we explicitly move to the next phase, this repository’s only contract is: **call the real API, save the real JSON, and log any errors.**
