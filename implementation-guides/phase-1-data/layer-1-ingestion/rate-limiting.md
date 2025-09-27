# Rate Limiting & Concurrency Control

## Objective
Ensure AlphaVantage requests stay within 600 calls/minute while supporting concurrent polling of multiple symbols and tenors.

## Architecture Overview
- Token bucket implemented in `data_ingestion/rate_limit_controller.py` with Redis as shared state.
- Worker processes request tokens before hitting external API.
- Bucket refills every `refill_interval_ms` with configured burst headroom.
- Retry policy uses jittered backoff (50–150 ms) on HTTP 429 and network timeouts.

## Configuration Table
| Parameter | Description | Default | Location |
|-----------|-------------|---------|----------|
| `requests_per_minute` | Sustained throughput ceiling | 600 | `alpha_vantage.rate_limit` |
| `burst_size` | Extra tokens allowed per refill | 120 | `alpha_vantage.rate_limit` |
| `refill_interval_ms` | Refill period in milliseconds | 1000 | `alpha_vantage.rate_limit` |
| `jitter_ms.min` | Min retry delay | 50 | `alpha_vantage.rate_limit` |
| `jitter_ms.max` | Max retry delay | 150 | `alpha_vantage.rate_limit` |

## Implementation Steps
1. Instantiate `RateLimitController` with Redis connection and contract-compliant config.
2. Wrap AlphaVantage API calls with `async with rate_limiter.token()` context manager.
3. Log token acquisition latency and remaining tokens for observability.
4. On quota exhaustion, surface structured warning to logs and metrics.
5. Persist bucket state using Redis keys: `rate_limit:alpha_vantage:{interval}`.

## Monitoring
- Metrics: `data_ingestion.rate_limit.tokens_available`, `data_ingestion.rate_limit.wait_time_ms`, `data_ingestion.rate_limit.burst_events`.
- Alert threshold: available tokens < 50 for >10 seconds triggers warning.

## Testing Procedures
- Unit test concurrency with `pytest tests/layer1/test_rate_limiter.py`.
- Stress test via `python scripts/simulate_av_load.py --workers 10 --duration 300` and confirm metrics stay within limits.
- Validate persistence by restarting service mid-test and checking tokens resume correctly.

## Failure Modes
- Redis unavailable: fall back to local in-memory limiter with stricter caps; raise alert.
- Config drift: detect via contract validation and fail fast on boot.
- Clock drift: ensure Redis server time accurate; use `TIME` command to verify.
