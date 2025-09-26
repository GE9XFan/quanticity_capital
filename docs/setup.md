# Local Environment Setup Checklist

1. Install Python 3.11 (via Homebrew `brew install python@3.11` or python.org installer).
2. Create the virtual environment: `python3.11 -m venv .venv`.
3. Activate the environment:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows (PowerShell): `.venv\\Scripts\\Activate.ps1`
4. Upgrade pip and install dependencies: `python -m pip install --upgrade pip` then `pip install -r requirements.txt`.
5. Copy `.env.example` to `.env` and fill in secrets (`ALPHAVANTAGE_API_KEY`, `REDIS_URL`, `IBKR_*`, etc.).
   - Configuration load order: `.env` → `config/runtime.json` → `config/alpha_vantage.yml`/`config/ibkr.yml`.
6. Duplicate `config/ibkr.yml` if you need environment-specific overrides; adjust host/port, symbol lists, or stream maxlen values as required (quotes, level2, account bundle, executions).
7. Verify Redis connectivity (e.g., `redis-cli ping`) before running ingestion scripts.
8. Run smoke tests when available: `pytest`.
9. Run `python src/main.py` to confirm the bootstrap script loads environment variables and resolves configuration files.

Document any platform-specific notes or additional steps here as the project evolves.
