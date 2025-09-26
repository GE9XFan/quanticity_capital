# Local Environment Setup Checklist

1. Install Python 3.11 (via Homebrew `brew install python@3.11` or python.org installer).
2. Create the virtual environment: `python3.11 -m venv .venv`.
3. Activate the environment:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows (PowerShell): `.venv\\Scripts\\Activate.ps1`
4. Upgrade pip and install dependencies: `python -m pip install --upgrade pip` then `pip install -r requirements.txt`.
5. Copy `.env.example` to `.env` and fill in secrets (`ALPHAVANTAGE_API_KEY`, `REDIS_URL`, `IBKR_*`, etc.).
6. Verify Redis connectivity (e.g., `redis-cli ping`) before running ingestion scripts.
7. Run smoke tests when available: `pytest`.

Document any platform-specific notes or additional steps here as the project evolves.
