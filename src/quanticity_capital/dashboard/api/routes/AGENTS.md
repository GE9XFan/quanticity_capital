# API Routes

Create route modules grouped by feature:
- `health.py`
- `analytics.py`
- `signals.py`
- `trades.py`
- `social.py`
- `scheduler.py`
- `watchdog.py`

Each router should declare response models aligning with the spec. Keep Redis access centralized through dependency helpers.
