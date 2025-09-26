# Analytics Engine

## Purpose
Transform raw market, options, and macro data into institutional-grade analytics that power signal generation, risk management, and reporting.

## Responsibilities
- Consume latest datasets from Redis (`raw:*`), validate freshness vs. TTL, and compute required analytics metrics.
- Write consolidated outputs (per symbol and global) to `derived:*` keys and append to historical Redis/Postgres stores.
- Provide metadata describing contributing data sources, calculation timestamps, and confidence/quality flags.
- Trigger alerts when prerequisites are stale or calculations fail integrity checks.

## Processing Architecture
- Runs as asynchronous worker triggered by scheduler jobs (`analytics.refresh` for high-frequency metrics, `analytics.hourly`, etc.).
- Modular plugin design: each metric implemented as component with defined inputs/outputs.
- Caches intermediate results (e.g., implied vol surfaces) within processing cycle to avoid duplicate work.

## Base Package Scaffolding (2025-09-27)
- `config/analytics.yml` now captures source contracts (Alpha Vantage realtime options, IBKR quotes/level2/positions) and metric outputs (initially `dealer_greeks` enabled, remaining metrics staged with `enabled: false`).
- `src/analytics/config.py` parses the YAML into dataclasses (`AnalyticsConfig`, `SourceConfig`, `MetricConfig`) with Redis defaults and loader staleness windows.
- `src/analytics/contracts.py` defines canonical data structures for inputs (`OptionChain`, `QuoteSnapshot`, `Level2Book`, `PositionSnapshot`) and analytics outputs (`AnalyticsResult`, `QualityFlag`).
- `src/analytics/loaders.py` exposes async helpers to hydrate those contracts from Redis (`load_alpha_vantage_option_chains`, `load_ibkr_quotes`, `load_ibkr_level2_books`, `load_ibkr_positions`) with freshness enforcement and schema validation.
- `src/analytics/math/black_scholes.py` provides deterministic Black-Scholes greeks (delta/gamma/theta/vega/rho/charm/vanna/volga) used by the dealer analytics runner.
- Future metrics can consume these loaders and contracts to guarantee uniform precision and persistence semantics.

## Metric Specifications
1. **Dealer Greeks & Exposures**
   - Input: options chains (live Alpha Vantage) + IBKR quotes/positions.
   - Output: per symbol delta, gamma, vega, theta, rho, charm, vanna, volga aggregated by dealer assumption. Charm/vanna/volga are derived via Black-Scholes using live mark, tenor, and implied volatility.
   - Key: `derived:dealer_exposure:<symbol>` TTL 20s.
2. **VPIN / Order Flow Toxicity**
   - Input: trade volume buckets from Alpha Vantage (if available) or IBKR trades; fallback to estimates from volume/oi.
   - Output: toxicity score 0-1, bucket details.
3. **Volatility Regime**
   - Input: realized volatility (from price data), implied vol metrics.
   - Output: classification (`calm`, `elevated`, `stressed`), supporting stats.
4. **Liquidity Stress**
   - Input: level-2 depth, spreads, volume.
   - Output: liquidity index (0-100) with flag thresholds.
5. **Volume/OI Anomaly**
   - Input: historical averages from Analytics Sliding Window, current volume/oi.
   - Output: z-scores per contract and aggregated anomaly flag.
6. **Correlation Matrix**
   - Input: returns from sliding window data.
   - Output: matrix stored at `derived:correlation:<group>` with TTL 15m.
7. **MOC Imbalance**
   - Input: IBKR MOC indications (if available) or aggregated order book signals; options to integrate other feeds later.
   - Output: net imbalance notional, direction, confidence.
8. **Macro Overlays**
   - Input: macro series (GDP, CPI, inflation, etc.).
   - Output: normalized indicators (trend, surprise detection) stored daily.
9. **Futures Linkage**
   - Input: futures prices (Alpha Vantage or IBKR), underlying spot.
   - Output: basis spread, carry inference, sentiment indicators.
10. **Risk Summary**
    - Input: all metrics.
    - Output: composite risk score per symbol (`0-100`), key driver list.
11. **IV Surface Curvature & Smile Skew**
    - Input: options chain implied vols across strikes/tenors.
    - Output: curvature metrics, skew slope, smile classification.
12. **Risk Reversal Ladder**
    - Input: call/put vol spreads across tenors.
    - Output: ladder table with bias annotations.
13. **Cross-Asset Stress Index**
    - Input: equities, rates, volatility futures.
    - Output: stress score aggregated via weighted PCA.
14. **Dealer Edge Attribution (Required)**
    - Input: dealer exposures, price moves, theta decay.
    - Output: PnL decomposition into delta/gamma/vega/theta/charm/vanna/volga components with expected vs. realized analysis.

## Outputs & Storage
- Per symbol analytics bundle stored at `derived:analytics:<symbol>` TTL 20s.
- Aggregated metrics appended to Redis Stream `stream:analytics` and Postgres table `analytics.metric_snapshots`.
- Provide per metric quality flags (ok/stale/error) consumed by dashboard and watchdog.

## Validation & Quality Checks
- Check data freshness: abort metric if required `raw` key older than TTL threshold; mark metric state `stale`.
- Sanity checks for extreme values (e.g., >5 sigma) flagged for human review.
- Log calculation durations and anomalies.

## Configuration
- `config/analytics.yml`: metric enable flags, parameters (e.g., VPIN bucket size, volatility regime thresholds), weighting for risk summary.
- `config/macros.yml`: mapping of macro series to symbols or strategies.

## Integration Testing
- Run analytics against live data snapshot; verify outputs stored and TTLs respected.
- Compare computed Greeks vs. Alpha Vantage-provided values for random contracts as sanity check.
- Validate correlation matrix symmetry and diagonal = 1.
- Ensure dealer edge attribution sums to total expected PnL within tolerance.
