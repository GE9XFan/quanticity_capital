# CLI & Operations Reference

A lightweight CLI stub now ships with the repository skeleton. Use this page to track entry points,
document flags, and capture operational runbooks as additional commands land.

## Current Status
- `quanticity-capital` (or `python -m quanticity_capital.main`) bootstraps logging and emits a
  readiness message. It accepts `--log-level` and `--version` flags.
- The Makefile provides dependency install helpers only; no operational targets exist yet.
- Broader operational playbooks still live in prose within other docs until functional modules are
  implemented.

## Usage
```bash
# Inside an activated virtual environment
quanticity-capital --help
quanticity-capital --log-level DEBUG
python -m quanticity_capital.main --version
```

## Next Steps When Code Lands
- Document each CLI module as it is implemented, including expected environment variables, guardrails,
  and rollback steps.
- Capture incident response flows for ingestion, analytics, signal, and execution modules once they
  exist.
- Provide concrete, copy-pasteable commands only after verifying them against the real codebase.

Keep this file aligned with the live repository so operational context stays trustworthy.
