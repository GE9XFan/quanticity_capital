# Config Loader Module

Wraps Pydantic models around the YAML files in `/config` and environment variables.

## Tasks
- `models.py`: Pydantic schemas for each YAML payload (runtime, schedule, symbols, analytics, watchdog, observability).
- `loader.py`: locate YAML files, merge environment overrides, provide cached `AppConfig` instances.
- `secrets.py`: optional helpers for `.env` handling if we integrate with `python-dotenv` or `direnv`.

## Notes
- Ensure hot-reload support for scheduler (ability to reload cadences without restart).
- Keep schema validation strict—fail fast when config invalid.
- Link to specs: `docs/specs/orchestrator.md`, `docs/specs/scheduler.md`, `docs/specs/observability.md`.
- Environment overrides:
  - `${ENV_VAR}` placeholders in YAML resolve from `.env` first, then the active OS environment.
  - Direct overrides use `CONFIG__PATH__TO__FIELD` environment variables (e.g. `CONFIG__RUNTIME__REDIS__URL`).
  - Values pass through JSON parsing so strings like `"false"` resolve to booleans.
- Cache invalidation: call `load_settings(reload=True)` when tests mutate the configuration directory.
