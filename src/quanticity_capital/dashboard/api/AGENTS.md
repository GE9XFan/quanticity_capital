# FastAPI Application

`api/` houses the actual FastAPI app and routers.

## Expected Files
- `app.py` – creates FastAPI instance, configures middlewares, includes routers, mounts websocket manager.
- `dependencies.py` – provides Redis/Postgres clients to route handlers.
- `routes/` – split routers by domain (health, analytics, signals, trades, social, scheduler).
- `websocket.py` – connection manager for `/ws/stream`.

Follow shapes described in `docs/specs/dashboard_backend.md` for each endpoint.
