# Quanticity Capital – Unusual Whales REST Capture

Phase 0 is focused on **calling the live Unusual Whales REST API**, validating the responses, and saving the raw JSON to disk. Nothing else is wired yet—no Redis, no WebSockets, no FastAPI. This repository now contains only the tooling required for that task.

## Repository Layout

```
src/
  config/            Runtime settings (pydantic-settings)
  clients/           HTTP client wrapper around httpx
  ingestion/         Endpoint catalogue + ingestion runner
  cli/               CLI entry point (`python -m src.cli.uw_rest_fetch`)

data/unusual_whales/raw/   Raw JSON responses organised by endpoint
logs/                      Timestamped log files from each run
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

## Fetching REST Data

Run the fetcher to hit every documented REST endpoint for the configured tickers (defaults to `SPY,QQQ,IWM`). This command talks to the live API—no mocks.

```bash
make uw-rest-fetch
# or: python -m src.cli.uw_rest_fetch
```

Outputs:

- Raw responses written to `data/unusual_whales/raw/<endpoint>/<ticker>_<timestamp>.json`
- Per-endpoint indexes (`index.ndjson`) that track when each file was created
- Structured logs in `logs/unusual_whales_rest_<timestamp>.log`

The CLI prints a summary when the run completes, including success/failure counts and the destination directory.

## Configuration Reference

All runtime settings come from environment variables (see `src/config/settings.py` for defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `UNUSUAL_WHALES_API_TOKEN` | – | **Required** API token |
| `TARGET_SYMBOLS` | `SPY,QQQ,IWM` | Comma-separated list of tickers |
| `REQUEST_TIMEOUT_SECONDS` | `30.0` | HTTP timeout per request |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `100` | Max requests per minute (hard cap 120) |
| `RATE_LIMIT_LEEWAY_SECONDS` | `0.5` | Extra wait inserted between calls |

## Next Steps (after Phase 0)

1. Decide how to persist the latest payloads (Redis snapshots, Postgres archive, etc.).
2. Introduce scheduling so the fetcher runs continuously or on a cadence.
3. Expand into WebSocket ingestion once the REST flow is locked down.
4. Build analytics, signals, and the rest of the trading pipeline on top of the captured data.

Until we explicitly move to the next phase, this repository’s only contract is: **call the real API, save the real JSON, and log any errors.**
