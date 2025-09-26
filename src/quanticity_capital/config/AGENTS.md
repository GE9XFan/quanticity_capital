# Config Loader Module

Wraps Pydantic models around the YAML files in `/config` and environment variables.

## Tasks
- `loader.py`: locate YAML files, merge environment overrides, provide cached settings objects.
- `models.py`: define structured config classes (ModulesSettings, RedisSettings, ScheduleConfig, etc.).
- `secrets.py`: optional helpers for `.env` handling if we integrate with `python-dotenv` or `direnv`.

## Notes
- Ensure hot-reload support for scheduler (ability to reload cadences without restart).
- Keep schema validation strict—fail fast when config invalid.
- Link to specs: `docs/specs/orchestrator.md`, `docs/specs/scheduler.md`, `docs/specs/observability.md`.
