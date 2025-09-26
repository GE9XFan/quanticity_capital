# Scheduler State Persistence

## Goals
- Preserve token bucket levels and job next-run timestamps across orchestrator restarts.
- Allow external inspection of scheduler state via Redis keys.
- Minimize Redis writes: only update state when it changes significantly (dispatch, refill, reconfiguration).

## Redis Keys
- `state:scheduler:bucket:<name>` (Hash)
  - `tokens`: float string
  - `last_refill`: ISO8601 timestamp
  - `capacity`: int
  - `refill_interval_ms`: milliseconds
  - `max_burst`: optional int
- `state:scheduler:job:<job_id>` (Hash)
  - `next_run_at`: ISO8601 timestamp or empty
  - `last_run_at`: ISO8601 timestamp or empty
  - `enabled`: `0/1`
  - `priority`: string
  - `bucket`: bucket name
  - `jitter_seconds`: int or empty
- `state:scheduler:jobs` (Set)
  - Contains all active job IDs for iteration.

## Persistence Strategy
1. **Initialization**
   - Load existing bucket hashes; if present, seed token bucket manager tokens and last_refill.
   - Load job hashes; reuse `next_run_at` if valid future timestamp.
2. **On Dispatch**
   - Update job hash with new `last_run_at` and `next_run_at`.
3. **On Refill/Consume**
   - After consuming tokens, write `tokens` & `last_refill` back to bucket hash (throttle writes by interval, e.g., only when tokens change by >0.1 or every second).
4. **Resilience**
   - Use pipeline/MULTI for atomic updates per job event.
   - TTL optional (e.g., 1 day) to avoid stale state when scheduler down. Reset TTL on updates.

## Introspection Support
- CLI endpoint uses the hashes and set to display current state.

