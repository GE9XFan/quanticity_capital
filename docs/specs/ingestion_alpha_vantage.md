# Alpha Vantage Ingestion – Iterative Build Guide (September 2025)

## Objective
Deliver a dependable Alpha Vantage pipeline by implementing one endpoint at a time, only advancing after the user supplies exact API inputs and signs off on Redis persistence (structure + TTL). This reset replaces the earlier broad scope to keep the solo-dev workflow manageable and verifiable.

## Ground Rules
- **Python 3.11 + venv:** All commands run inside the project virtual environment. Dependencies are tracked in `requirements.txt` and added only when the code that needs them lands.
- **Configuration first:** Each endpoint requires entries in `.env` (API key) and `config/alpha_vantage.yml` for cadence, symbols, and request parameters before code exists.
- **User handshake:** No implementation starts without the user providing: endpoint name, target symbols, full querystring (function + params), a representative JSON payload, expected refresh cadence, and the TTL that should be enforced in Redis.
- **Sequential delivery:** Finish, document, and validate one endpoint entirely before starting the next.

## Implementation Workflow
1. **Capture Inputs**
   - Record the request in `docs/alpha_vantage_endpoints.md` with status `awaiting-params`.
   - Once the user supplies parameters + sample JSON, update the tracking entry to `ready-to-build`.
   - Store the sample JSON under `docs/samples/alpha_vantage/<endpoint>/<symbol>.json` for regression tests.
2. **Configure**
   - Add a section to `config/alpha_vantage.yml`:
     ```yaml
     realtime_options:
       function: REALTIME_OPTIONS
       symbols: [SPY, QQQ]
       params:
         require_greeks: true
       cadence_seconds: 12
       redis:
         key_pattern: "raw:alpha_vantage:realtime_options:{symbol}"
         ttl_seconds: 24
     ```
   - Update `requirements.txt` if new dependencies are required.
3. **Implement**
   - Every endpoint module should stay thin and delegate to the shared runner in `src/ingestion/alpha_vantage/_shared.py`.
     - Instantiate `AlphaVantageIngestionRunner` with a validator that knows how to vet the payload for that endpoint.
     - The runner already wires `httpx.AsyncClient`, retry/backoff logic, Redis persistence, and heartbeat updates so individual modules remain declarative.
     - Request construction must still draw configuration strictly from `config/alpha_vantage.yml` (no hard-coded defaults beyond the API key env var).
   - If an endpoint requires custom retry handling, pass the relevant HTTP status codes (`retry_status_codes`) when constructing the runner (e.g., retry 429 throttles).
4. **Verify**
   - Run the module manually (`python -m src.ingestion.alpha_vantage.<endpoint_slug> --symbol SPY`).
   - Inspect Redis with `redis-cli` or a helper script; capture the stored JSON and TTL in `docs/verification/<endpoint_slug>_<date>.json`.
   - Update the tracking table status to `awaiting-signoff` and share the captured file with the user for confirmation.
   - Once approved, tag the entry `done` and note any follow-up actions (e.g., additional symbols, different TTLs).

## Redis Contract
- Default key template: `raw:alpha_vantage:<endpoint_slug>[:<symbol>]` (symbols optional for aggregate endpoints).
- Stored payload schema:
  ```json
  {
    "symbol": "SPY",
    "endpoint": "REALTIME_OPTIONS",
    "requested_at": "2025-09-26T14:03:12Z",
    "ttl_applied": 24,
    "request_params": { "require_greeks": true },
    "data": { /* raw Alpha Vantage JSON */ }
  }
  ```
- TTL values come directly from the user handshake. Never guess or round; surface mismatches immediately.
- Maintain a heartbeat key alongside data writes: `state:alpha_vantage:<endpoint_slug>[:<symbol>]` storing the last success timestamp.

## Error Handling & Backoff
- Use exponential backoff intervals `[1s, 3s, 7s]` with a max of three attempts per request.
- On final failure, log the HTTP status/body excerpt and set the heartbeat key with `status="error"` so monitoring can surface the issue.
- Propagate Alpha Vantage throttling headers (`Note` or `Information` fields) into structured logs for troubleshooting; the shared runner surfaces these via `PayloadValidationError` so they never reach Redis silently.

## Testing & Regression Artifacts
- For each implemented endpoint, add a pytest module under `tests/ingestion/alpha_vantage/test_<endpoint_slug>.py` that replays the stored sample JSON, exercising the normalization + Redis write helpers without hitting the live API.
- Keep captured live responses small—trim arrays if necessary before committing to `docs/verification/` while preserving structure needed for tests.

## Out of Scope (Until the User Requests It)
- Additional endpoints (macro, fundamentals, analytics batches) beyond those explicitly queued in `docs/alpha_vantage_endpoints.md`.
- Async orchestration or scheduling layers—the initial focus is on manual runs validated by the user.
- Automatic symbol discovery or dynamic TTL calculation.

## Success Criteria
- Every endpoint has: configuration, implementation, test coverage using recorded samples, a verification artifact, and user sign-off.
- Redis keys match agreed naming, TTLs, and contain complete Alpha Vantage payloads plus metadata.
- No additional endpoints are started without written confirmation of inputs.
