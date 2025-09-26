# Signal Engine

Implements strategy evaluators defined in `docs/specs/signal_engine.md`.

## Components
- `engine.py` – scheduler-triggered entrypoint that iterates strategies and symbols.
- `state.py` – manage `signal:pending`, `signal:active`, cooldown tracking.
- `sizing.py` – Kelly vs. Achilles sizing logic, referencing analytics outputs.
- `strategies/` – per-strategy rule definitions.
- `publisher.py` – writes signals to Redis and notifies watchdog/execution modules.

## Guidelines
- Validate analytics freshness; skip gracefully if stale.
- Include deduplication to prevent repeated signals; respect TTL and cooldown windows.
- Store full context with each signal (analytics snapshot reference, risk params) for watchdog transparency.
