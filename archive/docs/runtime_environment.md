# Runtime Environment

The streamlined stack depends only on Python, Redis, and the external APIs.

## Required Local Tools

| Component | Recommended Version | Notes |
|-----------|---------------------|-------|
| Python | 3.11.x | Used for everything (`python -m venv .venv`). |
| pip | Latest bundled with Python | No `pip-compile` workflow—`requirements.txt` lists all packages directly. |
| Redis | 7.x or newer | Local server (Homebrew, Docker, or remote instance). |

Optional but handy:

- Docker Desktop (if you prefer running Redis in a container).
- `redis-cli` for ad‑hoc inspection.

## Python Dependencies
Instal with `pip install -r requirements.txt`. The file now contains a small, human-managed list:

- `fastapi`
- `uvicorn[standard]`
- `redis`
- `httpx`
- `websockets`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`
- `ibapi`
- `anthropic`

Run `pip freeze > docs/runtime_versions.txt` whenever you need to capture an exact state.

## Environment Variables
Copy `.env.example` to `.env` and fill in values. At minimum you’ll need `REDIS_URL` and `UNUSUAL_WHALES_API_TOKEN`. If you skip optional credentials (IB or Anthropic) the related loops will log a warning and idle.

## Launch Checklist

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit values
redis-server  # or use docker run redis:7
python -m src.system.runtime
```

Use `python scripts/show_latest.py` in another terminal to verify data is flowing.

That’s the entire runtime footprint—one interpreter, one Redis, and the two external APIs when you’re ready to hook them in.
