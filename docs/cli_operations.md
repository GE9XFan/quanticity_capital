# CLI & Operations Reference

Practical command glossary for running the Quanticity stack as a solo operator. Commands assume the
virtual environment is active (`source .venv/bin/activate`) and `APP_ENV` set for the current
workspace. All commands use the Python module namespace (`python -m ...`) to ensure consistent
packaging. All CLI invocations are safety-aware: if the target module’s feature gate is disabled, the
command performs no action and logs a `module_disabled` event (no side effects).

## 1. Environment Safety
- Set `APP_ENV` explicitly (`export APP_ENV=dev` or `prod`). CLI commands honour env prefixes for Redis
  keys and social publishing guardrails.
- Feature-gated modules default to disabled; enabling requires editing appropriate config file and
  restarting orchestrator modules.
- Token buckets and rate limits apply even to manual dispatch/replay commands, preventing accidental
  API bursts.

## 2. Orchestrator & Module Lifecycle
| Action | Command | Notes |
|--------|---------|-------|
| Start orchestrator (all enabled modules) | `python -m src.main` | Reads `config/runtime.yml`. |
| Start specific module | `python -m src.main --module scheduler` | Modules: `scheduler`, `analytics`, `signal`, `execution`. |
| Stop module | `python -m src.main --stop scheduler` | Graceful shutdown with state flush. |
| Show running tasks | `python -m src.main --status` | Displays module heartbeat TTLs. |

## 3. Scheduler CLI (`src.scheduler.cli`)
| Command | Purpose | Example |
|---------|---------|---------|
| `python -m src.scheduler.cli snapshot` | Print upcoming runs, bucket levels, rotation pointers. | `... snapshot --filter analytics` |
| `python -m src.scheduler.cli tail --job <job>` | Stream scheduled events for a job. | `... tail --job analytics.refresh.high_frequency` |
| `python -m src.scheduler.cli dispatch --job <job> [--rotation SYMBOL]` | Manually dispatch job respecting token buckets. | `... dispatch --job signal.evaluate.0dte --rotation SPY` |
| `python -m src.scheduler.cli replay --job <job> --since <ISO>` | Re-emit events tagged `event_type=replay` (respects token buckets). | `... replay --job signal.evaluate.0dte --since 2025-09-27T14:00:00Z` |
| `python -m src.scheduler.cli reload` | Acquire lock, drain loop, reload `config/schedule.yml`, flush state. |  |
| `python -m src.scheduler.cli pause --job <job>` | Pause job via `state:scheduler:pause` key (TTL optional). |  |
| `python -m src.scheduler.cli resume --job <job>` | Remove pause key and resume scheduling. |  |

## 4. Analytics CLI (`src.analytics.cli`)
| Command | Purpose | Notes |
|---------|---------|-------|
| `python -m src.analytics.cli refresh --symbol <SYM> --metrics ...` | Manually compute metrics for a symbol. | Uses live Redis inputs; respects quality guards. |
| `python -m src.analytics.cli replay --symbol <SYM> --from <ISO> --to <ISO>` | Recompute metrics using captured fixtures. | Useful for diffing changes. |
| `python -m src.analytics.cli dump --symbol <SYM>` | Output latest `derived:analytics:{symbol}` bundle. |  |

## 5. Signal CLI (`src.signal.cli`)
| Command | Purpose | Notes |
|---------|---------|-------|
| `python -m src.signal.cli evaluate --symbol <SYM> --strategy <STRAT>` | Force evaluation (respecting noise/risk gates). | Idempotent via `decision_sha`. |
| `python -m src.signal.cli list --status <pending|approved|active>` | Inspect signals across statuses. | Optionally filter by symbol. |
| `python -m src.signal.cli approve --signal-id <ID>` | Manual approval (writes to `signal:approved`). | Watchdog equivalent. |
| `python -m src.signal.cli reject --signal-id <ID> --reason <text>` | Reject pending signal. | Updates `state:signal:last`. |
| `python -m src.signal.cli halt --symbol <SYM> --strategy <STRAT>` | Set halt key with TTL. | `resume` removes it. |
| `python -m src.signal.cli refresh-config --strategy <STRAT>` | Reload strategy config cache from Postgres. |  |

## 6. Execution CLI (`src.execution.cli`)
| Command | Purpose | Notes |
|---------|---------|-------|
| `python -m src.execution.cli cancel --trade-id <ID>` | Cancel open orders for trade. | Ensures reduce-only semantics. |
| `python -m src.execution.cli adjust-stop --trade-id <ID> --percent <N>` | Modify stop parameters. | Writes to `exec:stop_monitor`. |
| `python -m src.execution.cli flatten --symbol <SYM>` | Cancel orders & flatten all positions for symbol. |  |
| `python -m src.execution.cli reconcile [--symbol <SYM>]` | Force IBKR reconciliation (open orders/fills). | Invokes recovery steps on reconnect. |
| `python -m src.execution.cli scale-out --trade-id <ID> --qty <N> --reason <TXT>` | Manual partial exit. | Obeys reduce-only logic. |
| `python -m src.execution.cli scaling --trade-id <ID> --enable-in <bool> --enable-out <bool>` | Toggle scaling feature gates per trade. |  |
| `python -m src.execution.cli tp-plan --trade-id <ID>` | Show resolved TP tiers. |  |
| `python -m src.execution.cli sim supervisor --feed <path>` | Run supervisor loop against recorded quotes. | Facilitates offline testing. |

## 7. Watchdog & Social CLI (`src.watchdog.cli`, `src.social.cli`)
| Command | Purpose | Notes |
|---------|---------|-------|
| `python -m src.watchdog.cli list` | Show recent watchdog reviews. | Includes current status and reviewer. |
| `python -m src.watchdog.cli stats` | Summarise pending volume, SLA averages, autopilot score buckets. | Mirrors dashboard counters. |
| `python -m src.watchdog.cli approve --signal-id <ID>` | Manual approval override. | Requires reviewer role. |
| `python -m src.watchdog.cli reject --signal-id <ID> --reason <TXT>` | Reject pending signal with audit note. | Updates `watchdog:review:{signal_id}`. |
| `python -m src.social.cli queue` | Inspect pending social posts by channel. | Shows depth vs ceiling. |
| `python -m src.social.cli publish --message-id <ID>` | Force publish or drop message. | Honors env guard + token buckets. |
| `python -m src.social.cli deadletters --channel <name>` | Dump failed/back-pressured payloads from `state:social:dead_letter:{channel}:*`. | Handy during vendor outages. |
| `python -m src.social.cli resend --event-id <ID> --channel <name>` | Load `social:payload:{event_id}` and requeue with fresh dispatch id. | Still tagged `event_type=replay` for public-tier safety. |

All commands automatically no-op (with `module_disabled` log) if their module feature gate is off.

## 8. Reporting CLI (`src.reporting.cli`)
| Command | Purpose | Notes |
|---------|---------|-------|
| `python -m src.reporting.cli refresh --dashboard <name>` | Force tile recomputation for a dashboard. | Respects per-tile `max_runtime_ms` and token buckets. |
| `python -m src.reporting.cli status` | Print heartbeat age, last refresh latency, tile counts. | Reads `system:heartbeat:reporting:*`. |
| `python -m src.reporting.cli export --date <ISO> --format <csv|pdf>` | Generate and upload report for date. | In `APP_ENV=prod`, PDF exports require `CONFIRM=YES`; CSV writes schema hash to `reporting:exports:schema_hash:{dashboard}`. |
| `python -m src.reporting.cli deadletters --since <ISO>` | Inspect failed exports (`state:reporting:dead_letter:*`). | Pair with `export` to replay. |
| `python -m src.reporting.cli compare --dashboard <name> --window <7d>` | Compare tiles vs Postgres snapshots, detect drift. | Stores explainer JSON at `reporting:compare:last:{dashboard}` when drift detected. |

## 9. Observability Shortcuts
| Task | Command |
|------|---------|
| Check scheduler heartbeat TTL | `redis-cli ttl system:heartbeat:scheduler` |
| Check signal engine metrics | `redis-cli HGETALL metrics:signals` |
| Tail execution events | `redis-cli XREAD STREAMS stream:trades 0-0` |
| View analytics bundle | `python -m src.tools.peek redis derived:analytics:SPY` |
| Check reporting dashboard heartbeat | `redis-cli ttl system:heartbeat:reporting:ops_console` |

## 10. Incident Playbooks
1. **API rate-limit breach**
   - Inspect `metrics:scheduler.bucket_starved` and logs for `bucket_empty`.
   - Pause offending jobs (`scheduler.cli pause`), adjust token bucket capacity, reload config.
2. **Stuck pending signal**
   - `signal.cli list --status pending`, evaluate `pending_timeout` alert.
   - Use `signal.cli reject` or `approve` as appropriate; ensure watchdog/social aware.
3. **Execution slippage anomaly**
   - Review `metrics:execution`, inspect `trade:state` snapshot.
   - Potentially set `state:signal:halt:{symbol}`; flatten positions via execution CLI.
4. **Cold start after downtime**
   - Start scheduler; verify catch-up limited (`max_catchup_iterations`).
   - Inspect `system:schedule:last_run:*` to confirm analytics jobs recently fired before enabling
     signal/execution modules.
   - Resume modules sequentially (ingestion → analytics → signal → execution) watching heartbeats.
5. **Dashboard degradation**
   - Check `system:heartbeat:reporting:*` and `metrics:reporting.tiles_status_total` for elevated `warning`/`stale` counts.
   - Use `reporting.cli status` plus `reporting.cli compare` to review drift explainers stored in `reporting:compare:last:{dashboard}`.
   - Re-run exports (`reporting.cli export`) when data sources recover and verify schema hash stability before distribution.

## 11. Command Naming Rules
- Use verbs (`evaluate`, `dispatch`, `replay`, `flatten`) for actions; nouns for inspections (`snapshot`, `list`).
- All CLIs located under `src.<module>.cli`. Avoid shell aliases for reproducibility across operators.
- Commands log structured JSON to stdout; redirect to files when running long sessions (`... tail ... | jq`).

Keep this reference updated whenever new commands or feature gates are introduced. Add quick examples
for real-world incident response to reduce toil.
