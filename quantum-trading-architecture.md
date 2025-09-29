# Quantum Trading Platform - Simplified Architecture

## What We're Building and Why

We're building an automated options trading system that finds and trades 0DTE/1DTE opportunities, then sells that intelligence as a premium subscription service. 

The edge: Most retail traders can't calculate Greeks in real-time, can't monitor order flow, and definitely can't execute complex trailing stop strategies. We do all of this automatically and deliver the signals in a way they can actually trade.

Revenue model is simple:
- **Premium ($297/month)**: Real-time signals with exact strikes, automated alerts, full reports
- **Basic ($97/month)**: Same signals delayed 60 seconds, less detail
- **Free**: 5-minute delayed teasers to attract subscribers

---

## The System Flow (How It Actually Works)

```
1. DATA INGESTION (The Foundation)
   ↓
2. ANALYTICS (Turn Data Into Intelligence)  
   ↓
3. SIGNAL GENERATION (Find The Trades)
   ↓
4. RISK & EXECUTION (Make The Trades)
   ↓
5. REPORTING (Package The Intelligence)
   ↓
6. DISTRIBUTION (Deliver To Subscribers)
```

Each layer depends on the previous one. You can't generate signals without analytics. You can't compute analytics without data. This is the build order.

---

## Part 1: Data Ingestion
*Without data, nothing else matters*

### What We Need

**From AlphaVantage (Primary Options Data):**
- Real-time options chains with Greeks (every 5 seconds for 0DTE symbols)
- Historical options (for backtesting and pattern recognition)
- Intraday price data (1-minute bars)
- Technical indicators (RSI, MACD, etc.)
- Macro data (GDP, CPI, Fed rates)

Focus universe = SPX, SPY, QQQ, IWM, AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA (Magnificent 7). Everything else is secondary.

**AlphaVantage endpoints we actually call:**
- `function=REALTIME_OPTIONS&symbol={TICKER}&require_greeks=true`
- `function=HISTORICAL_OPTIONS&symbol={TICKER}&date={YYYY-MM-DD}` for structured historical pulls when real-time stream missed strikes
- `function=TIME_SERIES_INTRADAY&symbol={TICKER}&interval=1min&outputsize=compact` for live underlyings
- `function=RSI`, `function=MACD`, `function=BBANDS` aligned with the strategy watchlist
- `function=REAL_GDP`, `function=CPI`, `function=FEDERAL_FUNDS_RATE` for macro context

**Call Budgeting (Premium plan = 600 calls/minute):**
| Stream | Symbols | Cadence | Calls/min | Notes |
| --- | --- | --- | --- | --- |
| 0DTE chains + Greeks | SPX, SPY, QQQ, IWM | 5s staggered | 48 | Offset each symbol by 1s to avoid bursts |
| Intraday underlyings | Focus universe (SPX, SPY, QQQ, IWM + Mag 7) | 15s | 44 | Batch updates so equities alternate every cycle |
| Technical indicators | Strategy watchlist | 60s | 20 | Cache locally; only refresh when inputs change |
| Macro + reference | All | 5m | <5 | Run on a separate scheduler window |
| Historical refresh | Rolling backfill | Nightly | N/A | Throttle to 300/min while markets closed |

Rules of thumb:
- Budget real-time requests first, then fit slower cadences into remaining quota.
- Queue historical backfills after 16:30 ET so the real-time scheduler never waits.
- Use a simple leaky-bucket to smooth bursts; if quota overshoots, drop optional technical indicator pulls instead of Greeks.

**From IBKR (Execution & Real-time Verification):**
- Live market quotes (backup/verification of AlphaVantage)
- Order book depth (critical for liquidity analysis)
- Tick-by-tick trades (for VPIN calculation)
- Account data (positions, P&L, buying power)
- Order execution gateway

### Level 2 Depth Handling (IBKR)
- Snapshot the top 10 price levels every 2 seconds, aggregate to a rolling 60-second window.
- Store each snapshot in Redis with `ttl=180` so stale books fall out automatically.
- Maintain a lightweight `orderflow:ibkr:L2:SYMBOL` stream for deltas, capped at 500 entries per symbol to avoid memory creep.
- Tag each snapshot with `source_ts` from TWS; downstream modules drop anything older than 5 seconds.

### AlphaVantage + IBKR Connectivity Checklist
- Ensure TWS API is live on port 7497 with `Read-Only API` disabled and `Master API client ID` reserved for automation.
- Emit a heartbeat from each client every 30 seconds; if two heartbeats fail, trip a circuit breaker that halts new orders until reconnection.
- Log AlphaVantage latency; if p95 > 2s for 3 minutes, temporarily promote IBKR quotes to primary pricing.
- Rotate AlphaVantage API keys only during market close windows to avoid cascading reconnects.

### How We Store It (Dead Simple)

Everything goes into Redis as raw JSON:
```
raw:av:options:SPY → {entire AlphaVantage response}
raw:ibkr:SPY → {current quote from IBKR}
raw:ibkr:depth:SPY → {order book snapshot}
```

No complex normalization. No DTOs. Just store what comes from the APIs.

Why this matters: When AlphaVantage changes their format (they will), you update one extraction function, not 50 normalizer classes.

---

## Part 2: Analytics Engine
*Transform raw data into tradeable intelligence*

### The Analytics Pipeline (In Order of Dependency)

**Level 1 - Basic Computations (Need only price data):**
- **Greeks Aggregation**: Sum of all gamma, delta, theta across strikes
- **Price Bars**: Convert ticks to 1m/5m/15m OHLCV bars
- **Technical Indicators**: Calculate RSI, MACD, Bollinger Bands

**Level 2 - Market Microstructure (Need order book data):**
- **Liquidity Scoring**: Bid-ask spread, depth at each level
- **Order Book Imbalance**: Buy pressure vs sell pressure
- **Smart Money Flow**: Large orders hitting the tape

**Level 3 - Advanced Analytics (Need Level 1+2):**
- **VPIN**: Toxic order flow detection using volume buckets
- **Gamma Exposure (GEX)**: Market maker positioning
- **Regime Classification**: Trending vs mean-reverting market state

**Level 4 - Predictive (Need everything above):**
- **MOC Imbalance Predictor**: Forecast closing auction imbalance
- **Volatility Forecast**: Next period implied move
- **Mean Reversion Probability**: Chance of snapback after moves

Each level reads from Redis, computes, and writes results back:
```
analytics:greeks:SPY → {"gamma": 45000, "delta": -2000}
analytics:vpin:SPY → {"value": 0.73, "signal": "toxic"}
analytics:regime → {"state": "trending", "confidence": 0.85}
```

### Analytics Output Standards
- **VPIN** uses 1,000-share volume buckets; each bucket computes `order_imbalance / total_volume`, and a 50-bucket rolling average drives the signal. Tag outputs with `confidence` based on bucket count > 30.
- **Gamma Exposure (GEX)** sums `open_interest * contract_gamma * price_multiplier` per strike, then net longs minus shorts. Flag regimes where |GEX| shifts >20% in 5 minutes as `anomaly:gex` for downstream throttles.
- **Regime Classification** blends 3 indicators: volatility percentile, moving-average slope, and liquidity score. Confidence = min of individual confidences so the weakest link drives caution.
- **Volatility Forecast** applies a simple EWMA of implied and realized volatility spread; recalibrate decay factors weekly off realized error stored in `analytics:vol_forecast:metrics`.

Every analytics job publishes a heartbeat (`analytics:STATUS → {"module": "greeks", "ts": ...}`) and emits anomaly flags back into Redis (`analytics:alerts`) when inputs fall outside expected ranges (missing Greeks, stale order book, abrupt deltas). Downstream modules must check both the payload and the latest heartbeat before trusting the data.

---

## Part 3: Signal Generation
*Where we actually find trades*

### Strategy Modules (In Order of Complexity)

**0DTE Gamma Scalping (Simplest - build first):**
- Trigger: High gamma concentration at strike + liquidity available
- Entry: When price approaches gamma strike with momentum
- Exit: Trailing stop or gamma unwind signal
- Risk: Max 2% per trade, 6% daily
- Dependencies: `analytics:gex`, `analytics:regime`, IBKR L2 liquidity scores
- Knobs: Max 6 contracts per ticker, trailing-stop presets (15% → 50% → 100%) pulled from `risk:trailing`
- Telemetry: Log fills + stop adjustments to `logs:signals:0dte`; emit debug snapshot when signal suppressed due to stale analytics

**1DTE Overnight (Build second):**
- Trigger: End-of-day regime signal + implied vs realized gap
- Entry: Last 30 minutes before close
- Exit: First 30 minutes after open or trailing stop
- Risk: Position sized for overnight margin
- Dependencies: `analytics:regime`, `analytics:vol_forecast`, open interest trend from AlphaVantage historical cache
- Knobs: Hard cap 1 position per symbol, margin utilisation ceiling 35%, optional `hedge_leg` flag for futures overlay
- Telemetry: Persist entry rationale to `reports:daily:notes` so the evening report can reference it automatically

**MOC Imbalance (Build third):**
- Trigger: Predicted imbalance > threshold + liquidity score
- Entry: 3:30-3:50 PM ET
- Exit: Market on close or 4:00 PM
- Risk: Can spike 300%+ in minutes, size accordingly
- Dependencies: `analytics:moc_pred`, IBKR depth snapshots (last 5), AlphaVantage intraday trend for confirmation
- Knobs: Max notional per trade = 4% equity, time-stop at 3:55 PM ET if imbalance decays, optional `iceberg_mode` to slice orders
- Telemetry: Capture order-book conditions pre/post trade to `logs:moc:depth` for post-trade analysis

**Swing Trades (Build last):**
- Trigger: Multi-day setup + regime alignment
- Entry: Scaled over 1-2 days
- Exit: Target or time-based (5-10 days max)
- Risk: Portfolio heat max 20%
- Dependencies: `analytics:regime` (higher timeframe), macro data snapshots, backtested expectancy metrics stored in Redis
- Knobs: Use laddered entries (25/50/25), cap open swings at 3 symbols, enforce minimum liquidity score > B
- Telemetry: Append daily mark-to-market note to `reports:swing_journal`; alert if price diverges >1.5 ATR from model assumption

Each strategy reads analytics and writes signals:
```
signals:pending → {"id": "SIG-001", "strategy": "0dte", "symbol": "SPY", ...}
signals:active → {"id": "SIG-001", "entry": 440.5, "stop": 439.0, ...}
```

---

## Part 4: Risk Management & Execution
*Turn signals into actual trades with protection*

### The Execution Pipeline

**Risk Validation (Before any trade):**
- Portfolio exposure check (max delta, gamma, theta)
- Correlation limits (not all same direction)
- Buying power verification
- Time-of-day restrictions

**Order Execution (If validated):**
- Smart routing based on liquidity
- Adaptive order types (limit vs market)
- Fill quality monitoring
- Partial fill handling

**Trailing Stop Management (The secret sauce):**
- Initial: 15% trailing stop
- At +100% profit: Lock in 50% minimum
- At +200% profit: Lock in 100% minimum
- At +300% profit: Lock in 200% minimum
- Never let profit turn to loss once green

**Position & P&L Tracking:**
```
positions:active → {"SPY_440C": {"qty": 10, "entry": 2.50, "current": 5.00}}
risk:exposure → {"delta": 1500, "gamma": 300, "theta": -200}
pnl:realized → {"day": 2500, "week": 8000, "month": 35000}
```

### Execution Playbook Details
- Pre-trade exposure check calculates net Greeks after proposed order: `new_delta = current_delta + order_delta`. Reject if delta > 2,000, gamma > 500, or theta < -400.
- IBKR order tickets are templated: defaults = LMT + adaptive, time-in-force = DAY for intraday, GTC for swings. Override template only when liquidity score < B.
- Keep a manual TWS control switch: if automation fails, set `execution:mode=manual` in Redis; trading loop stops sending orders and pushes pending signals to a queue for manual execution.
- Stale-data lockout: if any pricing feed is older than 3 seconds or analytics heartbeat exceeds 10 seconds, halt order submission and surface the issue on the trading console.

---

## Part 5: AI Overseer & Automated Review
*The system that watches the system*

### Why This Matters
- One person cannot simultaneously police analytics drift, execution anomalies, and risk breaches; the overseer fills that gap.
- Automated documentation keeps compliance happy by recording every decision and exception in real time.
- Faster intervention means toxic flow or stale data halts trading before losses snowball.

### Anomaly Detection Pipeline
- **What it monitors:** analytics drift (missing Greeks, VPIN spikes, regime churn), execution quality (slippage, rejects), data feed health (latency, schema changes), and strategy performance decay.
- **How it works:**
  - `monitors:analytics` checks each computation for statistical outliers against rolling baselines.
  - `monitors:execution` scores fills versus expected prices and tracks reject reasons.
  - `monitors:data` validates every feed update against expected schema and timestamps.
  - `monitors:signals` compares predicted outcomes with realized P&L to catch model drift.
- **Trigger levels:** immediate halt when data is older than 10 seconds, Greeks fail, or IBKR disconnects; warning + log for >2% slippage, unusual volume, regime uncertainty >50%; review flag when pattern shifts or strategies underperform.

### Trade Validation Engine
- **Pre-trade checks:** sanity of the signal math, liquidity sufficiency, portfolio fit (correlation and heat), and compliance restrictions (symbol, time windows).
- **Post-trade analysis:** fill quality scoring, slippage attribution, stop placement validation, and realized-vs-expected tracking.
- **Validation rules stored in Redis:**
  - `validator:rules:0dte → {"max_contracts": 6, "max_delta": 500, "min_liquidity": "B"}`
  - `validator:rules:swing → {"max_positions": 3, "correlation_limit": 0.7}`
  - `validator:rules:moc → {"time_window": "15:30-15:50", "max_notional": 10000}`

### Explainability System
- **Coverage:** why trades triggered, why rejections occurred, how analytics cascaded into decisions, and which risk events fired.
- **Storage format:**
  - `explainer:trades → {"id": "SIG-001", "triggered_by": ["gex_spike", "regime_bullish"], "confidence": 0.85, "risk_factors": ["elevated_vpin"]}`
  - `explainer:rejects → {"id": "SIG-002", "rejected_because": "insufficient_liquidity", "details": "spread > max_allowed"}`

### AI Integration Points
- **Narrative generation (Claude/GPT):** real-time trade writeups, risk-event summaries, subscriber-friendly regime context, anomaly alerts with context.
- **Pattern recognition:** detect emerging behaviours that rules miss, suggest strategy tuning based on degradation, flag unusual correlations, and spotlight potential abuse patterns.

### Implementation Details
- **Monitoring loop (runs every second):**
```python
while True:
    # Data freshness
    for feed in ["av:options", "ibkr:quotes", "ibkr:depth"]:
        age = time.time() - redis.get(f"{feed}:timestamp")
        if age > 10:
            redis.set("overseer:halt", "stale_data")
            alert_operator(f"Feed {feed} is {age}s old")

    # Analytics sanity
    greeks = redis.get("analytics:greeks:SPY")
    if greeks["gamma"] < 0 or greeks["gamma"] > 100000:
        redis.set("overseer:alert", "impossible_greeks")
        halt_signals("SPY")

    # Execution quality
    recent_fills = redis.get("execution:fills:recent")
    slippage = calculate_slippage(recent_fills)
    if slippage > 0.02:
        redis.set("overseer:warning", "high_slippage")
        notify_operator(f"Slippage {slippage*100}% exceeds threshold")

    # Generate explanations
    for signal in redis.get("signals:pending"):
        explanation = generate_explanation(signal)
        redis.set(f"explainer:signal:{signal.id}", explanation)

    time.sleep(1)
```
- **Compliance archive:** log every anomaly with context, retain validation results and explanations for seven years, and emit a daily overseer summary for review.
- **Automatic actions:** halt trading on critical anomalies, taper position sizes on warnings, flip to paper trading after repeated failures, and disable individual strategies when underperformance persists.
- **Human alerts (Discord/Telegram):**
  - `⚠️ VPIN spike to 0.89 - toxic flow detected`
  - `🛑 Greeks calculation failed 3x - halting SPY signals`
  - `📊 Slippage trending higher - review execution quality`
  - `✅ All systems normal - 47 signals validated today`
 - **Storage rotation:** keep hot data in Redis buckets by day (`explainer:trades:YYYY-MM-DD:{id}`), auto-expire after 30 days, and stream nightly archives into cold storage (S3/local) with gzip compression. Maintain a lightweight index (`archive:index:{date}`) so retrieval queries stay constant-time.

### Why This Is Critical
- The overseer never sleeps, so lunch breaks do not equal blind risk.
- Compliance-ready documentation is produced continuously, avoiding retroactive guesswork.
- Automated risk responses fire within milliseconds, not minutes.
- AI augments rule-based checks, catching subtle pattern shifts early.
- Performance attribution becomes explicit—you always know why trades worked or failed.

---

## Part 6: Premium Content Generation
*Package the intelligence for subscribers*

### Report Generation Pipeline

**Data Collection:**
1. Pull today's signals and fills
2. Get current positions and P&L
3. Fetch analytics snapshots
4. Retrieve risk metrics

**Content Creation:**
1. Generate charts (Plotly): Greeks heatmaps, P&L attribution, liquidity depth
2. Write narrative (Claude/GPT): Market regime description, trade rationale
3. Apply tier templates: Premium (full), Basic (redacted), Free (teaser)

**Report Types:**
- Pre-Market (8:30 AM): Setup for the day
- Intraday (1:00 PM): Adjustments and new signals
- Market Close (4:10 PM): Wrap-up and tomorrow's plan

Everything stored for compliance:
```
reports:generated → {"date": "2024-01-15", "type": "premarket", "tier": "premium"}
reports:content → {full HTML/PDF content}
```

---

## Part 7: Multi-Channel Distribution
*Deliver to subscribers where they want it*

### Distribution Pipeline (In Priority Order)

**Immediate (Premium only):**
1. Discord webhook to premium channel
2. Telegram alert to premium group
3. Email to premium list

**60-Second Delay (Basic):**
1. Discord webhook to basic channel (strikes rounded)
2. Telegram to basic group (no exact entries)
3. Email to basic list (simplified charts)

**5-Minute Delay (Free):**
1. Discord public channel (direction only)
2. Twitter post (teaser: "0DTE calls printing")
3. Reddit post (educational angle)

### Content Redaction by Tier

**Premium sees:**
"BUY SPY 440C @ 2.50, Stop @ 2.10, Target 5.00"

**Basic sees:**
"BUY SPY Calls around 440 strike, trailing stop active"

**Free sees:**
"Bullish SPY setup triggered, premium members entered calls"

---

## Building This as a Solo Developer

### Phase 1: Get Data Flowing (Week 1)
1. Set up Redis
2. Connect AlphaVantage, store raw options
3. Connect IBKR, store quotes and depth
4. Verify data in Redis with simple scripts

### Phase 2: Core Analytics (Week 2)
1. Calculate Greeks from options data
2. Build VPIN from tick data
3. Create regime classifier
4. Store all analytics in Redis

### Phase 3: First Strategy (Week 3)
1. Implement 0DTE gamma scalping logic
2. Generate signals to Redis
3. Paper trade in IBKR
4. Add trailing stop manager

### Phase 4: Distribution MVP (Week 4)
1. Set up Discord/Telegram bots
2. Create basic report template
3. Implement 3-tier system
4. Test with paper trades

### Phase 5: Scale Up (Month 2)
1. Add remaining strategies
2. Add all analytics modules
3. Polish reports with charts
4. Add Twitter/Reddit/Email

### Daily Operations (5 minutes morning, 5 minutes evening)

**Morning Startup:**
```bash
# Terminal 1
redis-server

# Terminal 2  
python data_service.py  # Shows: "✓ AV Connected, ✓ IBKR Connected"

# Terminal 3
python analytics.py     # Shows: "Computing: Greeks... VPIN... Regime..."

# Terminal 4
python trading.py       # Shows: "Signals: 0, Positions: 0, P&L: 0"
```
- Health checks: Confirm AlphaVantage + IBKR heartbeats < 30s old, Redis memory < 70% limit, and `analytics:alerts` is empty before enabling order flow.

**Evening Shutdown:**
- Verify reports sent
- Check P&L
- Ctrl-C all services
- Redis persists automatically
- Archive logs → rotate daily into S3/local cold storage for compliance.

### Ongoing Routines
- **Midday sweep (optional):** Review active trailing stops, reconcile IBKR fills vs Redis positions, clear any stuck signals.
- **Weekly maintenance:** Refresh historical backfills Sunday 18:00 ET, review error logs, update risk thresholds if volatility shifts.
- **Reporting QA:** Before market close report, sample one premium/basic/free output and ensure tier redactions align; note discrepancies in `reports:qa` for remediation.
- **Compliance archive:** Retain raw signals, orders, and reports for 7 years; compress weekly snapshots and verify checksums monthly.

---

## Why This Architecture Works

1. **Redis as the backbone** means services don't know about each other
2. **Raw JSON storage** means 80% less code than normalized DTOs
3. **Sequential processing** means you always know what depends on what
4. **Progressive building** means you can ship value in Week 1
5. **Terminal monitoring** means you see problems immediately

The entire system is ~2000 lines of Python instead of 20,000. One person can understand, debug, and enhance it.

---

## Suggested Implementation Order

1. **Data plumbing first:** stand up Redis, build thin collectors for AlphaVantage + IBKR, log raw payloads, and prove the quota scheduler across SPX/SPY/QQQ/IWM + the Mag 7.
2. **Foundational analytics:** implement Greeks aggregation, bar builders, and liquidity/imbalance metrics; validate heartbeats + anomaly flags in Redis.
3. **Risk + overseer scaffolding:** wire exposure checks, lockout switches, and a minimal overseer loop that watches data freshness and Greeks sanity.
4. **0DTE strategy module:** consume analytics outputs, generate signals, run them through validation, and simulate execution (no live orders yet).
5. **Execution integration:** connect to IBKR paper trading, push templated orders, confirm trailing-stop updates and manual override flows.
6. **Reporting + distribution MVP:** turn signals/fills into a premium report, then fan out tiered alerts (Discord/Telegram/email) with basic redactions.
7. **Overseer expansion:** add slippage tracking, anomaly classification, explainability storage, and archive rotation once real trade data exists.
8. **Additional strategies:** layer in 1DTE, MOC, and swing modules one at a time, reusing risk knobs and telemetry conventions.
9. **Polish cycles:** tighten compliance automation, backfill historical datasets for analytics calibration, and iterate on content templates + subscriber UX.
