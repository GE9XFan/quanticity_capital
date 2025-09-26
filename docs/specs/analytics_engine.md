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

## Metric Specifications
1. **Dealer Greeks & Exposures**
   - Input: options chains + greeks, IBKR positions.
   - Output: per symbol delta, gamma, vega, theta, charm, vanna, volga aggregated by dealer assumption.
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
