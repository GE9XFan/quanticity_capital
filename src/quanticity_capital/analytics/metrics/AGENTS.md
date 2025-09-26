# Analytics Metrics Plugins

Place individual metric implementations here. Each module should expose a callable like `async def compute(context) -> MetricResult` where `context` provides cached data and configuration.

Reference `docs/specs/analytics_engine.md` for required metrics and JSON payload shapes.
