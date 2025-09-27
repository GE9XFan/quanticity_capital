# Layer 1 Test Inventory

Track automated tests covering data ingestion components. Owners: Michael Merrick.

| Test File                             | Purpose                                      | Notes |
|--------------------------------------|----------------------------------------------|-------|
| `test_rate_limiter.py`               | Validates Redis token bucket behavior        | Covers burst, persistence, refills |
| `test_option_normalizer.py`          | Ensures AlphaVantage payload parsing         | Uses fixtures from `schemas/` |
| `test_ibkr_wrapper.py`               | Simulates IBKR event flow                    | Requires mocked `ib_async` client |
| `test_indicator_cache.py`            | Verifies indicator caching logic             | Ensures cache invalidation + TTL |
| `test_alphavantage_client.py`        | Confirms API wrapper handles retries & errors| Uses live-sim fixture or VCR recordings |
| `test_stream_health_checks.py`       | Validates streaming observability heartbeat  | Exercises metrics + alert hooks |
