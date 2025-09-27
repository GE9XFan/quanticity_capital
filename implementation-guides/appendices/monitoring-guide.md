# Monitoring Guide

Baseline observability expectations for the Quantum Trading System. Reference this guide when wiring alerts in each layer implementation.

## Metrics Namespaces
- `data_ingestion.*`: Rate limiting, API latency, error counts
- `analytics.*`: Greeks latency, regime likelihoods, liquidity stress
- `signals.*`: Decision throughput, validation failures, backtest runtime
- `execution.*`: Order lifecycle, broker connectivity, pacing violations
- `risk.*`: Exposure, VaR, stop triggers, override counts
- `ai.*`: Decision latency, approval rate, escalation backlog
- `report.*`: Generation latency, delivery success
- `social.*`: Channel throughput, retry counts

## Alerting Principles
- Tie every alert to a runbook in the relevant layer directory.
- Include environment, severity, and recommended action in alert payloads.
- Suppress duplicate alerts through aggregation windows to reduce noise.
- Validate alert wiring during phase exit reviews.

## Dashboards to Build
1. **Data Health:** API call volume vs limits, ingestion latency, cache hit rates.
2. **Analytics Performance:** Greeks compute SLA, VPIN vs price divergence, regime probabilities.
3. **Execution & Risk:** Orders per minute, reject reasons, net Greeks exposure, VaR trend.
4. **AI Oversight:** Approval outcome breakdown, SLA compliance, override backlog age.
5. **Reporting & Social:** Report generation timeline, delivery success per channel, narrative sentiment vs returns.

## Logging Standards
- Use structured logging (JSON) with `layer`, `component`, `correlation_id`, and `environment` fields.
- Preserve raw broker/API messages in append-only storage for audit.
- Redact credentials and PII before logs leave the local environment.

## Tracing Expectations
- Propagate trace IDs from ingestion through execution and AI decisions.
- Instrument asynchronous workers with context propagation tools (`contextvars`, OpenTelemetry).

## Incident Response
- Critical alerts trigger on-call paging; ensure contact rotation stored in `timeline.yaml` or internal tooling.
- Post-incident reviews must update the relevant guide’s risk section and runbook.
