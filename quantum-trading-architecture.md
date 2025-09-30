# Quantum Trading Platform - Simplified Architecture with Unusual Whales

## What We're Building and Why

We're building an automated options trading system that finds and trades 0DTE/1DTE opportunities, then sells that intelligence as a premium subscription service. 

The edge: Unusual Whales provides pre-calculated Greeks, GEX/DEX/VPIN-equivalent flow toxicity metrics, and congressional trading data. We combine this with IBKR Level 2 depth, execute complex trailing stop strategies, and use AI oversight to catch anomalies before they blow up accounts.

Revenue model is simple:
- **Premium ($149/month)**: Real-time signals with exact strikes, automated alerts, full reports
- **Basic ($49/month)**: Same signals delayed 60 seconds, less detail
- **Free**: 5-minute delayed teasers to attract subscribers

---

## The System Flow (How It Actually Works)

```
1. DATA INGESTION (The Foundation)
   ↓
2. ANALYTICS (Minimal - UW Does Most)  
   ↓
3. SIGNAL GENERATION (Find The Trades)
   ↓
4. RISK & EXECUTION (Make The Trades)
   ↓
5. AI OVERSEER (Watch Everything)
   ↓
6. REPORTING (Package The Intelligence)
   ↓
7. DISTRIBUTION (Deliver To Subscribers)
```

Each layer depends on the previous one. The key change: Unusual Whales eliminates 80% of analytics computation.

---

## Part 1: Data Ingestion (Config-Driven Architecture)
*Without data, nothing else matters - but without flexibility, the system dies*

### The Config-Driven Revolution

Instead of hardcoding every API endpoint, we use a **single generic fetcher** driven by a `data_sources.yaml` config file. This transforms data ingestion from a coding task to a configuration task.

**Core Architecture:**
- Generic fetcher class reads endpoint definitions from YAML
- Config specifies: URL patterns, parameters, symbols, Redis keys, TTLs, fetch intervals
- System automatically picks up config changes (hot-reload capable)
- New data source = edit YAML, zero code changes
- IBKR remains special (WebSocket-based, needs dedicated handler)

### Config Schema Structure

```yaml
data_sources:
  unusual_whales:
    base_url: "https://api.unusualwhales.com/api"
    auth:
      type: "bearer"
      token_env: "UW_API_TOKEN"

    rate_limits:
      requests_per_minute: 120  # 2 requests per second
      burst_size: 20

    endpoints:
      spot_gex:
        path: "/stocks/{symbol}/spot-gex-exposures"
        interval_seconds: 60
        symbols: ["SPY", "QQQ", "IWM"]
        redis_key: "raw:uw:spot_gex:{symbol}"
        ttl_seconds: 180
        params:
          date: "today"  # Dynamic replacement at runtime
        transform: "parse_gex"  # Optional data transformer
        retry_policy:
          attempts: 3
          backoff: "exponential"
        priority: "critical"  # For failure handling
        cost_per_call: 0.01  # Track API spend
```

### What We're Fetching

**Critical Real-time (< 2 min intervals):**
- `Spot GEX per minute` - REAL-TIME gamma updates! (60s)
- `Flow Alerts` - Unusual activity detection (60s)
- `Call/Put Net Ticks` - Directional pressure (60s)
- `Greek Flow` - Greeks-weighted flow (120s)
- `Flow per strike intraday` - MOC predictor (120s)
- `Option Chains` - Full chains with Greeks (120s)

**Market Structure (5-15 min intervals):**
- `Greek Exposure By Strike` - Granular GEX (300s)
- `Greek Exposure By Strike And Expiry` - Complete matrix (300s)
- `Off/Lit Price Levels` - Dark pool analysis (300s)
- `Darkpool Trades` - Hidden prints (300s)
- `Max Pain` - Pin risk calculations (900s)
- `IV Rank & Term Structure` - Volatility surface (900s)
- `Historical Risk Reversal Skew` - Regime detection (900s)

**Slower Moving (hourly+):**
- `Congress Trades` - Political insider activity (3600s)
- `Insider Transactions` - CEO/CFO trades (3600s)
- `After-Hours Earnings` - Post-market earnings reports (3600s)
- `Pre-Market Earnings` - Morning earnings releases (3600s)
- `Historical Earnings` - Past earnings for context (daily)

**News & Sentiment:**
- `News Headlines` - Market-moving news with sentiment (300s)
  - Includes: headline text, ticker, sentiment score
  - Filters: major news only, by significance
  - Source attribution and impact assessment

**IBKR (Special WebSocket Handler):**
- Market depth snapshots (2s intervals, 10 levels)
- Tick-by-tick trades (real-time stream)
- Account updates (event-driven)
- Historical bars for technical indicators
- Real-time P&L and position updates

### Redis Storage Pattern

The generic fetcher automatically stores to Redis using config-defined keys:
```
raw:uw:spot_gex:SPY → {1-minute GEX updates}
raw:uw:gex_strike:SPY → {GEX by strike}
raw:uw:gex_matrix:SPY → {Complete GEX/DEX by strike & expiry}
raw:uw:flow_intraday:SPY → {Intraday flow by strike}
raw:uw:offlit:SPY → {Dark pool vs lit levels}
raw:uw:skew:SPY → {Risk reversal for regime}
raw:uw:congress → {Recent political trades}
raw:ibkr:depth:SPY → {Order book snapshot}
```

TTLs ensure automatic cleanup - no unbounded growth.

### Operational Benefits of Config-Driven Design

**Instant Adaptability:**
- Market closed? Reduce fetch intervals in config
- API rate limit hit? Throttle specific endpoints
- New symbol hot? Add to symbols list
- Endpoint deprecated? Comment it out

**Cost Management:**
- Track spend per endpoint with `cost_per_call`
- Disable expensive endpoints during testing
- A/B test different data combinations
- Audit trail of what data you're paying for

**Failure Resilience:**
- Priority levels determine retry aggressiveness
- Fallback behaviors for non-critical endpoints
- Circuit breakers per endpoint, not system-wide
- Graceful degradation when specific data unavailable

**Development Velocity:**
- Test with subset of symbols
- Mock endpoints for backtesting
- Different configs for dev/staging/prod
- No code changes for data source adjustments

### Advanced Config Features

**Dynamic Parameters:**
- `"today"` - Replaced with current date
- `"market_hours"` - Only fetch during RTH
- `"last_n_days:5"` - Rolling window
- `"0-2"` - Expiry ranges for options

**Transform Specifications:**
```yaml
transform: "parse_gex"  # Points to transform function
transform_config:
  flatten_nested: true
  parse_timestamps: true
  calculate_deltas: true
```

**Dependencies and Conditions:**
```yaml
depends_on: ["spot_gex"]  # Only fetch if dependency fresh
conditions:
  market_state: "open"
  time_range: "09:30-16:00"
```

**Multi-Source Aggregation:**
```yaml
aggregate:
  sources: ["uw_flow", "ibkr_trades"]
  method: "merge_on_timestamp"
  redis_key: "aggregated:flow:{symbol}"
```

### Interactive Brokers Integration Details

**Connection Architecture:**
```python
# IBKR TWS API connection (not REST, uses ib_insync or similar)
ibkr_config = {
    'host': '127.0.0.1',
    'port': 7497,  # Paper: 7497, Live: 7496
    'client_id': 1,
    'account': 'DU1234567'  # Paper account for testing
}
```

**Data Subscriptions We Get From IBKR:**

1. **US Equities & Options:**
   - Market depth (Level 2) for SPY, QQQ, IWM, and Mag 7
   - Real-time trades and quotes
   - Options chains with real-time bid/ask
   - Redis: `raw:ibkr:depth:{symbol}`, `raw:ibkr:options:{symbol}:{strike}:{expiry}`

2. **Global Indices (Real-time with your subscriptions):**
   - **US**: SPX, NDX, RUT, VIX (cash indices)
   - **Europe**: DAX, FTSE 100, CAC 40, STOXX 50, IBEX 35
   - **Asia**: Nikkei 225, Hang Seng, ASX 200, KOSPI
   - **Futures**: ES, NQ, YM, RTY (better than cash for overnight)
   - Redis: `raw:ibkr:index:{symbol}` with 5s updates

3. **Futures (24-hour real-time):**
   - **Equity futures**: ES, NQ, YM, RTY, VX (VIX futures)
   - **Commodities**: CL (oil), GC (gold), SI (silver), NG (nat gas)
   - **Bonds**: ZB (30Y), ZN (10Y), ZF (5Y), ZT (2Y)
   - **Currencies**: 6E (EUR), 6B (GBP), 6J (JPY), DX (Dollar Index)
   - Redis: `raw:ibkr:futures:{symbol}`

4. **Forex (Spot with IDEALPRO routing):**
   - Major pairs: EUR.USD, GBP.USD, USD.JPY, AUD.USD
   - Crosses: EUR.GBP, EUR.JPY, GBP.JPY
   - EM: USD.MXN, USD.ZAR, USD.TRY
   - Redis: `raw:ibkr:fx:{pair}` with tick-by-tick updates

5. **Crypto (via Paxos through IBKR):**
   - BTC.USD, ETH.USD (main pairs)
   - Limited but real-time when markets open
   - Redis: `raw:ibkr:crypto:{symbol}`

6. **Economic Indicators:**
   - Bond yields via futures (ZB, ZN yield calculation)
   - Dollar strength via DX futures
   - Volatility via VIX cash and VX futures
   - Redis: `raw:ibkr:macro:{indicator}`

7. **Account & Execution Data:**
   - Positions with real-time P&L
   - Buying power across all currencies
   - Margin requirements by product
   - Order status and fill quality
   - Redis: `raw:ibkr:account:*`

**Execution Capabilities:**

```python
# Order types we'll use
order_types = {
    'market': 'For urgent entries when liquidity good',
    'limit': 'Default for entries with price control',
    'stop': 'Initial stop loss orders',
    'trailing_stop': 'Dynamic stops that follow price',
    'adaptive': 'IBKR smart routing for best fill',
    'bracket': 'Entry + stop + target in one order'
}

# Execution logic
execution_config = {
    'max_slippage_bps': 10,  # Cancel if slippage > 10 basis points
    'use_adaptive': True,  # Let IBKR smart route
    'split_orders': True,  # Break large orders into chunks
    'max_chunk_size': 100,  # Maximum contracts per order
    'retry_attempts': 3,
    'cancel_timeout': 5  # Cancel unfilled after 5 seconds
}
```

**IBKR-Specific Handlers:**

1. **Connection Manager:**
   - Auto-reconnect on disconnect
   - Gateway vs TWS detection
   - Multiple account support
   - Health check every 30s

2. **Market Data Handler:**
   - Subscription management (max 100 simultaneous)
   - Snapshot vs streaming logic
   - Throttling for API limits
   - Data validation and gap detection

3. **Execution Handler:**
   - Order placement with smart routing
   - Fill tracking and slippage calculation
   - Bracket order management
   - Position reconciliation

4. **Risk Controls:**
   - Pre-trade margin check
   - Position limits per symbol
   - Daily loss limits
   - Order rate limiting

**Integration with UW Data:**

```python
# Verification layer - compare IBKR with UW
def verify_data_consistency():
    uw_bid = redis.get('raw:uw:chains:SPY:440C')['bid']
    ibkr_bid = redis.get('raw:ibkr:options:SPY:440C:20240115')['bid']

    if abs(uw_bid - ibkr_bid) > 0.05:
        alert("Price divergence detected")

    # Use IBKR for execution, UW for analytics
    return ibkr_bid  # Always execute on IBKR prices
```

**Why IBKR is Critical:**

1. **Execution** - Only way to actually place trades
2. **Real L2 Depth** - UW doesn't provide order book depth
3. **Account Data** - Real-time P&L and positions
4. **Tick Data** - Microsecond precision for VPIN
5. **Verification** - Cross-check UW data for anomalies

### Additional Data Sources for Complete Market Picture

**What IBKR Already Gives Us (No need for external sources!):**
Since you have full IBKR market data subscriptions:
- ✅ Global indices (real-time DAX, FTSE, Nikkei, etc.)
- ✅ Futures (24-hour ES, NQ, CL, GC, bonds)
- ✅ Forex (tick-by-tick EUR.USD, GBP.USD, etc.)
- ✅ Crypto (BTC, ETH via Paxos)
- ✅ All US equities and options with Level 2

**Earnings Calendar Options (Since no Alpha Vantage):**

1. **Unusual Whales Earnings APIs** (Already have!):
   - After-hours earnings
   - Pre-market earnings
   - Historical earnings
   - This covers most of what we need!

2. **Yahoo Finance** (Free, no API key):
   ```python
   import yfinance as yf
   # Get earnings calendar for next 5 days
   from yahoo_earnings_calendar import YahooEarningsCalendar
   yec = YahooEarningsCalendar()
   earnings = yec.earnings_between(start_date, end_date)
   ```
   - Update daily at 6 AM ET
   - Redis: `raw:yahoo:earnings_calendar`

3. **Nasdaq.com Scraper** (Free, reliable):
   - Scrape: `https://www.nasdaq.com/market-activity/earnings`
   - More comprehensive than Yahoo
   - Update twice daily
   - Redis: `raw:nasdaq:earnings`

4. **Financial Modeling Prep** (Free tier: 250 requests/day):
   - `https://financialmodelingprep.com/api/v3/earning_calendar`
   - Good for detailed earnings data
   - Redis: `raw:fmp:earnings`

**⚠️ CRITICAL GAP - Economic Calendar API Needed:**

We need a proper API (not a scraper) for economic events:
- FOMC meetings and minutes releases
- Economic data: CPI, PPI, NFP, GDP, unemployment
- Central bank decisions (Fed, ECB, BOJ, BOE)
- Treasury auctions and Fed speakers

**Options to investigate:**
1. **TradingEconomics API** - Has free tier with 2000 requests/month
2. **FXStreet API** - Professional economic calendar
3. **Econoday** - Institutional grade but may be expensive
4. **FRED API** (Federal Reserve) - Free but only US data
5. **DailyFX API** - Part of IG Group, reliable

This is the only missing piece in our data architecture. Without it, we could miss trading major economic events that cause volatility spikes.

**IBKR Configuration for Global Markets:**
```python
# Since you have all IBKR subscriptions, use them!
ibkr_market_data = {
    'us_equities': ['SPY', 'QQQ', 'IWM'] + MAG7,
    'global_indices': {
        'europe': ['DAX', 'FTSE', 'CAC', 'STOXX50', 'IBEX'],
        'asia': ['N225', 'HSI', 'ASX200', 'KOSPI', 'TOPIX'],
        'americas': ['BOVESPA', 'TSX60']
    },
    'futures': {
        'equity': ['ES', 'NQ', 'YM', 'RTY', 'VX'],
        'energy': ['CL', 'NG', 'RB', 'HO'],
        'metals': ['GC', 'SI', 'HG', 'PL'],
        'bonds': ['ZB', 'ZN', 'ZF', 'ZT'],
        'fx': ['6E', '6B', '6J', '6A', 'DX']
    },
    'forex': ['EUR.USD', 'GBP.USD', 'USD.JPY', 'AUD.USD'],
    'crypto': ['BTC.USD', 'ETH.USD']
}
```

### Rate Limiting Strategy for 120 requests/minute

**Smart Scheduling Approach:**
```yaml
# In config, add priority and scheduling
rate_limit_config:
  max_requests_per_minute: 120  # UW limit
  buffer: 10  # Keep 10 requests as buffer

  priority_groups:
    critical:  # 60 requests/min reserved
      - spot_gex  # Must have every minute
      - flow_alerts  # Critical for signals
      - call_put_ticks  # Direction changes

    important:  # 40 requests/min
      - greek_flow
      - flow_intraday
      - option_chains

    nice_to_have:  # 10 requests/min
      - max_pain
      - iv_rank
      - risk_reversal_skew

    background:  # Use spare capacity
      - congress_trades
      - insider_trades
      - earnings_data

# Dynamic scheduler logic
scheduler_rules:
  market_hours:  # 9:30 AM - 4:00 PM ET
    critical: "run_always"
    important: "run_if_capacity"
    nice_to_have: "skip_if_busy"
    background: "once_per_hour"

  pre_market:  # 4:00 AM - 9:30 AM ET
    critical: "reduce_to_5min"
    important: "reduce_to_15min"
    nice_to_have: "run_normal"
    background: "run_normal"

  after_hours:  # 4:00 PM - 8:00 PM ET
    all: "reduce_frequency_50%"

  weekend:
    all: "minimum_updates_only"
```

**Request Counter Implementation:**
```python
# Track requests in rolling window
rate_limiter = {
    'uw': RollingWindow(60),  # 60-second window
    'yahoo': RollingWindow(60),
    'requests_this_minute': 0,
    'last_reset': time.time()
}

def can_make_request(source='uw'):
    if source == 'uw':
        return rate_limiter['requests_this_minute'] < 110  # Leave buffer
    return True  # Other sources less strict
```

### Why This Architecture Wins

1. **Zero-downtime updates** - Change endpoints without restart
2. **Self-documenting** - Config file IS the documentation
3. **Testability** - Swap configs for different scenarios
4. **Cost control** - See exactly what costs money
5. **Vendor agnostic** - Add new data sources without architectural changes
6. **Antifragile** - Adapts to API changes via config edits
7. **Rate limit aware** - Automatic prioritization based on market state

The entire data ingestion layer becomes **one generic fetcher + one IBKR handler + config files**. Maybe 500 lines of Python for the fetcher, 300 lines for IBKR handler.

---

## Part 2: Analytics Engine (Enhanced)
*UW does the heavy lifting, we combine and enhance for trading signals*

### What UW Already Gives Us (No Computation Needed)

- **Greeks**: All Greeks for every strike/expiry (individual + aggregated)
- **GEX/DEX**: Gamma and Delta exposure pre-calculated
- **Spot GEX per minute**: Real-time gamma updates every 60 seconds!
- **GEX by Strike & Expiry**: Complete gamma surface matrix
- **Greek Flow**: Greeks-weighted flow analysis (better than raw volume)
- **Flow Analysis**: Institutional vs retail, opening vs closing
- **Max Pain**: Calculated for all expiries
- **Flow Toxicity**: Their flow analysis effectively replaces VPIN
- **Risk Reversal Skew**: Historical skew for regime detection
- **Off/Lit Levels**: Dark pool vs public market activity
- **IV Term Structure**: Complete volatility surface
- **Call/Put Ticks**: Net directional pressure metrics
- **News Sentiment**: Headline sentiment scores per ticker

### What We Need to Calculate (Missing Analytics)

**Level 1 - Market Microstructure:**
- **Liquidity Scoring**:
  - Combine IBKR bid-ask spread with depth at each level
  - Output: A/B/C/D grade per symbol for execution quality
- **Order Book Imbalance**:
  - (Bid Volume - Ask Volume) / (Bid Volume + Ask Volume)
  - Critical for MOC and entry timing
- **Execution Cost Model**:
  - Expected slippage based on order size and current liquidity
  - Needed for position sizing

**Level 2 - Flow Analytics:**
- **Flow Momentum Score**:
  - Rate of change in UW flow (acceleration/deceleration)
  - 5min, 15min, 60min windows
- **Smart Money Divergence**:
  - When Congress/insiders trade opposite to retail flow
  - Alert when divergence > 2 standard deviations
- **MOC Imbalance Predictor**:
  - Combine 2-4 PM flow asymmetry with dark pool prints
  - Output expected imbalance size and confidence

**Level 3 - Regime & Market State:**
- **Regime Classification**:
  - Trending: Risk reversal skew aligned with price direction
  - Mean-reverting: Price far from max pain with high GEX
  - Volatile: IV term structure inverted or IV rank > 80%
- **Gamma Flip Point**:
  - Calculate exact price where dealers flip from long to short gamma
  - Critical for 0DTE entry/exit
- **Pin Risk Score**:
  - Probability of pinning at max pain based on GEX concentration
  - Higher score = avoid directional trades

**Level 4 - Position & Risk Analytics:**
- **Correlation Matrix**:
  - Real-time correlation between positions
  - Prevent concentration risk
- **Portfolio Greeks**:
  - Aggregate delta, gamma, theta, vega across all positions
  - Alert when limits exceeded
- **Expected Move Calibration**:
  - Compare UW implied move vs historical realized
  - Adjust position sizing based on accuracy

**Level 5 - Signal Quality Metrics:**
- **Signal Confluence Score**:
  - How many indicators align (flow, GEX, Congress, etc.)
  - Higher score = higher position size
- **Backtest Performance**:
  - Track each signal type's win rate and average return
  - Auto-disable underperforming signals
- **Timing Optimizer**:
  - Best time to enter based on historical fill quality
  - E.g., "0DTE calls fill best at 10:15 AM"

### Analytics Pipeline Architecture

```python
# All analytics read from Redis and write back
analytics_modules = {
    'microstructure': {
        'inputs': ['raw:ibkr:depth:*', 'raw:ibkr:trades:*'],
        'outputs': ['analytics:liquidity:*', 'analytics:book_imbalance:*']
    },
    'flow': {
        'inputs': ['raw:uw:flow_intraday:*', 'raw:uw:congress', 'raw:uw:darkpool'],
        'outputs': ['analytics:flow_momentum:*', 'analytics:smart_divergence:*']
    },
    'regime': {
        'inputs': ['raw:uw:spot_gex:*', 'raw:uw:skew:*', 'raw:uw:iv_rank:*'],
        'outputs': ['analytics:regime', 'analytics:gamma_flip:*', 'analytics:pin_risk:*']
    },
    'risk': {
        'inputs': ['raw:ibkr:account:*', 'analytics:*'],
        'outputs': ['analytics:portfolio_greeks', 'analytics:correlation_matrix']
    }
}
```

Each calculation runs on schedule:
- Microstructure: Every 2 seconds (matches IBKR depth updates)
- Flow analytics: Every 60 seconds
- Regime: Every 5 minutes
- Risk: Continuous with position changes

---

## Part 3: Signal Generation
*Where we actually find trades*

### Symbol Universe by Strategy Type

**IMPORTANT: Single-Leg Long Options Only**
- **Buy calls** for bullish setups
- **Buy puts** for bearish setups
- **No naked selling, no spreads, no complex strategies**
- **Maximum risk = premium paid (no margin risk)**

**0DTE/1DTE Strategies:** SPX, SPY, QQQ, IWM only
- Most liquid with tightest spreads
- Gamma effects most pronounced
- Best for intraday scalping

**14-Day+ Strategies:** Magnificent 7 (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA)
- More time for thesis to play out
- Better for directional plays with catalyst
- Lower theta decay than 0DTE

### ⚠️ Note on API Responses
**IMPORTANT**: The exact data requirements below may need adjustment based on actual UW API response formats. During implementation, validate each endpoint's response structure and adjust field mappings accordingly.

### Strategy Modules with Detailed Data Requirements

**0DTE Gamma Scalping (Simplest - build first):**
- **Symbols**: SPX, SPY, QQQ, IWM
- **Data Requirements**:
  ```python
  # From Unusual Whales (every 60 seconds)
  uw_data = {
      'spot_gex': redis.get('raw:uw:spot_gex:{symbol}'),  # Need: total_gamma, flip_point
      'gex_by_strike': redis.get('raw:uw:gex_strike:{symbol}'),  # Need: {strike: gamma_exposure}
      'option_chains': redis.get('raw:uw:chains:{symbol}'),  # Need: bid, ask, volume, OI
      'call_put_ticks': redis.get('raw:uw:ticks:{symbol}')  # Need: net_ticks, direction
  }

  # From IBKR (every 2 seconds)
  ibkr_data = {
      'depth': redis.get('raw:ibkr:depth:{symbol}'),  # Need: 10 levels bid/ask with size
      'last_trade': redis.get('raw:ibkr:trades:{symbol}'),  # Need: price, size, timestamp
      'spread': redis.get('raw:ibkr:options:{symbol}:{strike}:{expiry}')  # Need: bid, ask
  }

  # From Analytics (pre-calculated)
  analytics = {
      'liquidity_score': redis.get('analytics:liquidity:{symbol}'),  # Need: grade A-D
      'gamma_flip': redis.get('analytics:gamma_flip:{symbol}'),  # Need: flip_price
      'book_imbalance': redis.get('analytics:book_imbalance:{symbol}')  # Need: ratio
  }
  ```
- **Signal Trigger Logic**:
  - Price within 0.1% of max gamma strike AND
  - Liquidity score >= B AND
  - Book imbalance supports direction
- **Risk**: Max 2% per trade, 6% daily

**1DTE Overnight (Build second):**
- **Symbols**: SPX, SPY, QQQ, IWM
- **Data Requirements**:
  ```python
  # From Unusual Whales (3:30 PM check)
  uw_data = {
      'greek_flow': redis.get('raw:uw:greek_flow:{symbol}'),  # Need: net_delta, net_gamma, premium
      'skew': redis.get('raw:uw:skew:{symbol}'),  # Need: current_skew, 20day_avg, direction
      'congress': redis.get('raw:uw:congress'),  # Need: ticker, transaction_type, amount
      'flow_alerts': redis.get('raw:uw:flow_alerts'),  # Need: symbol, type, size, sentiment
      'iv_rank': redis.get('raw:uw:iv_rank:{symbol}')  # Need: current_rank, percentile
  }

  # From Analytics
  analytics = {
      'regime': redis.get('analytics:regime'),  # Need: state (trending/mean-reverting)
      'smart_divergence': redis.get('analytics:smart_divergence:{symbol}'),  # Need: score, direction
      'flow_momentum': redis.get('analytics:flow_momentum:{symbol}')  # Need: 60min momentum
  }
  ```
- **Signal Trigger Logic**:
  - Risk reversal skew shifted > 1 std dev from mean AND
  - Greek flow net delta aligns with skew direction AND
  - Congress trades in same direction OR no opposing trades
- **Risk**: Position sized for overnight margin

**MOC Imbalance Trading (Enhanced - build third):**
- **Symbols**: SPY, QQQ, IWM (most liquid for MOC)
- **Data Requirements**:
  ```python
  # Detection Phase (2:00-3:30 PM continuous monitoring)
  uw_afternoon_flow = {
      'flow_intraday': redis.get('raw:uw:flow_intraday:{symbol}'),  # Need: strike_volume[14:00-15:30]
      'offlit': redis.get('raw:uw:offlit:{symbol}'),  # Need: dark_pool_pct, lit_pct, divergence
      'call_put_ticks': redis.get('raw:uw:ticks:{symbol}'),  # Need: call_ticks, put_ticks, net
      'greek_flow': redis.get('raw:uw:greek_flow:{symbol}')  # Need: cumulative_delta[14:00-15:30]
  }

  # Entry Phase (3:30 PM snapshot)
  entry_data = {
      'ibkr_depth': redis.get('raw:ibkr:depth:{symbol}'),  # Need: bid/ask imbalance
      'option_spreads': redis.get('raw:ibkr:options:{symbol}:0DTE'),  # Need: ATM spreads
      'moc_predictor': redis.get('analytics:moc_pred:{symbol}')  # Need: size, direction, confidence
  }
  ```
- **Signal Trigger Logic**:
  - Flow asymmetry > 60% to one side (calls or puts) AND
  - Dark pool % diverges from lit by > 10% AND
  - MOC predictor confidence > 70%
- **Position Sizing**: Scale based on expected move (0.2-0.5% typical)
- **Risk**: Max 1% per trade, hard stop if direction flips

**14-Day+ High IV Long Options (Build fourth):**
- **Symbols**: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA
- **Strategy**: Buy calls or puts when IV elevated but directional catalyst expected
- **Data Requirements**:
  ```python
  # For high IV directional plays
  uw_volatility_data = {
      'iv_rank': redis.get('raw:uw:iv_rank:{symbol}'),  # Need: current_rank, 30d_percentile
      'gex_matrix': redis.get('raw:uw:gex_matrix:{symbol}'),  # Need: {strike: {expiry: gamma}}
      'max_pain': redis.get('raw:uw:max_pain:{symbol}'),  # Need: {expiry: max_pain_strike}
      'skew': redis.get('raw:uw:skew:{symbol}'),  # Need: put/call skew direction
      'earnings': redis.get('raw:uw:earnings:{symbol}'),  # Need: next_earnings_date
      'congress': redis.get('raw:uw:congress')  # Need: recent activity in symbol
  }

  # From IBKR for execution
  ibkr_options = {
      'chain': redis.get('raw:ibkr:options:{symbol}:14-21DTE'),  # Need: ATM and OTM strikes
      'spreads': redis.get('raw:ibkr:spreads:{symbol}')  # Need: bid-ask for liquidity check
  }

  # Analytics for entry
  analytics = {
      'gamma_walls': redis.get('analytics:gamma_walls:{symbol}'),  # Need: breakout levels
      'flow_momentum': redis.get('analytics:flow_momentum:{symbol}')  # Need: directional bias
  }
  ```
- **Signal Trigger Logic**:
  - Buy CALLS when: Congress buying + call skew rising + above gamma support
  - Buy PUTS when: Insider selling + put skew rising + below gamma resistance
  - Only enter if expected catalyst (earnings, Fed, etc.) within expiry
  - Avoid if IV rank > 80% (too expensive)
- **Risk**: Max 2% per position (high IV = expensive premium)

**14-Day+ Directional Long Options (Build fifth):**
- **Symbols**: Magnificent 7 primarily
- **Strategy**: Buy calls (bullish) or puts (bearish) based on institutional signals
- **Data Requirements**:
  ```python
  # For directional conviction plays
  uw_directional = {
      'congress': redis.get('raw:uw:congress'),  # Need: {ticker, type, amount, date, member}
      'insiders': redis.get('raw:uw:insiders'),  # Need: {ticker, insider_name, shares, value}
      'darkpool': redis.get('raw:uw:darkpool'),  # Need: {symbol, size, price, above/below_market}
      'flow_alerts': redis.get('raw:uw:flow_alerts'),  # Need: sweeps > $1M, unusual activity
      'news': redis.get('raw:uw:news:{symbol}')  # Need: sentiment_score, headline, impact
  }

  # Analytics for confirmation
  analytics = {
      'smart_divergence': redis.get('analytics:smart_divergence:{symbol}'),  # Need: score > 2 std
      'flow_momentum': redis.get('analytics:flow_momentum:{symbol}'),  # Need: 3-day trend
      'regime': redis.get('analytics:regime')  # Need: trending vs mean-reverting
  }
  ```
- **Signal Trigger Logic**:
  - **BUY CALLS**: Congress buying > $500K + Dark pool accumulation > 2σ + Flow momentum positive
  - **BUY PUTS**: Insider selling cluster (3+) + Dark pool distribution + Put skew increasing
  - Strike selection: ATM for high conviction, OTM for lottery tickets
  - Expiry: 14-21 days to reduce theta decay
- **Position Sizing**:
  - Scale in over 2-3 days if signal strengthens
  - Max 3% risk per position
- **Exit Rules**:
  - Take 50% at 100% gain
  - Trail stop at 25% once up 50%+
  - Full exit before earnings

**Swing Trades (Build last - optional):**
- **Symbols**: SPY, QQQ + select Mag 7
- Trigger: Multi-day UW institutional accumulation + regime alignment
- Entry: Scaled over 1-2 days
- Exit: Target or time-based (5-10 days max)
- Risk: Portfolio heat max 20%
- Dependencies: UW congress trades, dark pool prints, regime classification

Each strategy reads analytics and writes signals:
```
signals:pending → {"id": "SIG-001", "strategy": "0dte", "symbol": "SPY", ...}
signals:active → {"id": "SIG-001", "entry": 440.5, "stop": 439.0, ...}
```

---

## Part 4: Risk Management & Execution
*Turn signals into actual trades with protection*

### Risk Rules for Long Options Only

**Position Sizing (Critical for survival):**
- 0DTE: Max 1-2% account risk per trade
- 1DTE: Max 2-3% account risk per trade
- 14-Day+: Max 3-5% account risk per trade
- Daily max loss: 6% of account
- Never risk more than you can afford to lose (options can go to zero)

### The Execution Pipeline

**Risk Validation (Before any trade):**
- Check daily loss limit not exceeded
- Verify position size within limits
- No more than 3 positions in same direction
- Buying power verification
- Time-of-day restrictions (no 0DTE after 3:30 PM)

**Order Execution (If validated):**
- Use limit orders at mid or better
- If no fill in 30 seconds, cross spread up to 25%
- Cancel if spread > 10% (too wide)
- Monitor fill quality via IBKR

**Profit Taking & Stop Loss (Long Options Specific):**
- **0DTE/1DTE Exits:**
  - Take 25% off at 50% gain
  - Take 50% off at 100% gain
  - Trail remainder with 25% stop
  - Hard stop at -50% (don't ride to zero)

- **14-Day+ Exits:**
  - Take 50% at 100% gain
  - Trail stop at 25% after 50% gain
  - Time stop: Exit if down 30% after 5 days
  - Always exit before earnings

**Position & P&L Tracking:**
```
positions:active → {"SPY_440C": {"qty": 10, "entry": 2.50, "current": 5.00}}
risk:exposure → {"delta": 1500, "gamma": 300, "theta": -200}
pnl:realized → {"day": 2500, "week": 8000, "month": 35000}
```

---

## Part 5: AI Overseer & Automated Review
*The system that watches the system - powered by Claude*

### Claude API Integration

```python
# Claude API configuration
claude_config = {
    'api_key': os.environ['CLAUDE_API_KEY'],
    'model': 'claude-3-haiku-20240307',  # Fast, cheap for monitoring
    'max_tokens': 500,
    'temperature': 0.3  # Lower for consistency
}

# Use cases for Claude
claude_tasks = {
    'anomaly_analysis': 'Analyze unusual patterns in real-time',
    'trade_narrative': 'Write explanations for signals',
    'risk_summary': 'Summarize portfolio risk in plain English',
    'market_commentary': 'Generate report narratives'
}
```

### Anomaly Detection Pipeline

**Real-time Monitoring (Every 30 seconds):**
```python
def monitor_data_quality():
    checks = {
        'uw_staleness': {
            'spot_gex': 90,  # Should update every 60s, alert at 90s
            'flow_alerts': 120,  # Should update every 60s, alert at 120s
            'option_chains': 180  # Should update every 120s, alert at 180s
        },
        'ibkr_connection': {
            'last_heartbeat': 30,  # TWS heartbeat every 10s, alert at 30s
            'position_sync': 60  # Position reconciliation
        },
        'data_divergence': {
            'price_diff': 0.02,  # UW vs IBKR price difference
            'greek_diff': 0.10,  # Greeks mismatch threshold
            'spread_diff': 0.15  # Bid-ask divergence
        }
    }

    # If anomaly detected, send to Claude for analysis
    if anomaly_detected:
        prompt = f"Analyze this trading anomaly: {anomaly_details}"
        response = claude.messages.create(
            model=claude_config['model'],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=claude_config['max_tokens']
        )

        # Take action based on severity
        if "CRITICAL" in response.content:
            halt_trading()
        elif "WARNING" in response.content:
            send_discord_alert(response.content)
```

### Trade Validation & Explanation

**Pre-Trade Validation:**
```python
def validate_signal(signal):
    # Hard rules (no AI needed)
    validations = {
        'position_size': signal.risk <= 0.05,  # Max 5% risk
        'daily_loss': get_daily_pnl() > -0.06,  # 6% daily stop
        'liquidity': signal.spread < 0.10,  # Max 10% spread
        'time_check': not (signal.is_0dte and time > "15:30")
    }

    # AI sanity check for complex signals
    if signal.complexity == 'high':
        prompt = f"""
        Review this options trade signal:
        Symbol: {signal.symbol}
        Direction: {signal.direction}
        Entry: {signal.entry}
        Triggers: {signal.triggers}

        Is this trade logical? Any red flags?
        """

        ai_review = claude.messages.create(
            model=claude_config['model'],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )

        if "RED FLAG" in ai_review.content or "AVOID" in ai_review.content:
            signal.add_warning(ai_review.content)

    return all(validations.values())
```

**Post-Trade Explanation:**
```python
def generate_trade_explanation(trade):
    prompt = f"""
    Write a brief explanation for subscribers about this trade:
    - Bought {trade.quantity} {trade.symbol} {trade.strike} {trade.type}
    - Triggers: {', '.join(trade.triggers)}
    - Key data: GEX at {trade.gex_level}, Congress {trade.congress_activity}

    Keep it under 3 sentences. Focus on WHY we entered.
    """

    explanation = claude.messages.create(
        model=claude_config['model'],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )

    # Store for reports
    redis.set(f'trade:explanation:{trade.id}', explanation.content)
    return explanation.content
```

### Trade Data Persistence

**Real-time Trade Recording:**
```python
def persist_trade(trade):
    # Store in Redis immediately
    trade_data = {
        'id': trade.id,
        'timestamp': trade.timestamp,
        'symbol': trade.symbol,
        'strike': trade.strike,
        'expiry': trade.expiry,
        'type': trade.type,  # CALL or PUT
        'quantity': trade.quantity,
        'entry_price': trade.entry_price,
        'current_price': trade.current_price,
        'pnl': trade.pnl,
        'triggers': trade.triggers,
        'explanation': generate_trade_explanation(trade)
    }

    # Store in Redis with no expiry
    redis.hset(f'trades:active:{trade.id}', mapping=trade_data)
    redis.zadd('trades:history', {trade.id: trade.timestamp})

    # Also track by date for daily archiving
    date_key = f'trades:daily:{trade.date}'
    redis.sadd(date_key, trade.id)
```

**Evening Archive Process (Run at 6 PM ET):**
```python
def archive_daily_trades():
    today = datetime.now().strftime('%Y-%m-%d')

    # Get all trades from today
    trade_ids = redis.smembers(f'trades:daily:{today}')
    trades = []

    for trade_id in trade_ids:
        trade_data = redis.hgetall(f'trades:active:{trade_id}')
        trades.append(trade_data)

    # Convert to DataFrame
    df = pd.DataFrame(trades)

    # Save as parquet for efficient storage
    archive_path = f'/archive/trades/{today}.parquet'
    df.to_parquet(archive_path, compression='snappy')

    # Generate daily summary with Claude
    prompt = f"""
    Summarize today's trading:
    - Total trades: {len(trades)}
    - Win rate: {calculate_win_rate(trades)}%
    - Total P&L: ${calculate_total_pnl(trades)}
    - Best trade: {get_best_trade(trades)}
    - Worst trade: {get_worst_trade(trades)}

    Write a brief performance summary (2-3 sentences).
    """

    summary = claude.messages.create(
        model=claude_config['model'],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )

    # Store summary
    redis.set(f'summary:daily:{today}', summary.content)

    return {'archived': len(trades), 'path': archive_path}
```

### Telegram Admin Control Interface

```python
class TelegramAdminBot:
    """Personal control interface for remote management"""

    def __init__(self):
        self.bot = telegram.Bot(token=os.environ['TELEGRAM_BOT_TOKEN'])
        self.admin_chat_id = os.environ['TELEGRAM_ADMIN_CHAT']
        self.pending_approvals = {}

    async def send_for_approval(self, item_type, content):
        """Send reports, trades, or alerts for admin approval"""

        approval_id = str(uuid.uuid4())[:8]

        message = f"""
🔔 **{item_type} - Approval Required**
ID: {approval_id}

{content}

Reply with:
- ✅ or 'approve' to proceed
- ❌ or 'reject' to cancel
- 'edit: [changes]' to modify
"""

        msg = await self.bot.send_message(
            chat_id=self.admin_chat_id,
            text=message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{approval_id}")],
                [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{approval_id}")],
                [InlineKeyboardButton("📝 Edit", callback_data=f"edit_{approval_id}")]
            ])
        )

        self.pending_approvals[approval_id] = {
            'type': item_type,
            'content': content,
            'message_id': msg.message_id,
            'timestamp': time.time()
        }

        return approval_id

    async def handle_admin_response(self, update):
        """Process admin commands from Telegram"""

        if update.callback_query:
            data = update.callback_query.data
            action, approval_id = data.split('_')

            if approval_id in self.pending_approvals:
                item = self.pending_approvals[approval_id]

                if action == 'approve':
                    await self.execute_approved_action(item)
                    await self.bot.send_message(
                        self.admin_chat_id,
                        f"✅ {item['type']} approved and executed"
                    )
                elif action == 'reject':
                    await self.bot.send_message(
                        self.admin_chat_id,
                        f"❌ {item['type']} rejected"
                    )
                elif action == 'edit':
                    await self.bot.send_message(
                        self.admin_chat_id,
                        "Reply with your edits:"
                    )
                    # Wait for text response with edits

                del self.pending_approvals[approval_id]

    async def send_critical_alert(self, alert):
        """Send critical system alerts directly to admin"""

        message = f"""
🚨 **CRITICAL ALERT**
Time: {datetime.now().strftime('%H:%M:%S')}

{alert['message']}

Details:
{json.dumps(alert['details'], indent=2)}

System Status: {'HALTED' if alert['halt_trading'] else 'RUNNING'}
"""

        await self.bot.send_message(
            chat_id=self.admin_chat_id,
            text=message,
            parse_mode='Markdown'
        )

# Example usage
admin_bot = TelegramAdminBot()

# Send morning report for approval
await admin_bot.send_for_approval(
    'MORNING REPORT',
    report_content
)

# Send critical trade for approval
await admin_bot.send_for_approval(
    'HIGH RISK TRADE',
    f"BUY 50 SPY 440C @ 2.50 (Risk: $1250)"
)
```

### Alert Escalation

```python
alert_levels = {
    'INFO': {
        'channels': ['log'],
        'examples': ['Trade filled', 'Position updated']
    },
    'WARNING': {
        'channels': ['log', 'discord', 'admin_telegram'],
        'examples': ['High slippage', 'Stale data', 'Wide spreads']
    },
    'CRITICAL': {
        'channels': ['log', 'discord', 'admin_telegram', 'email'],
        'examples': ['TWS disconnected', 'Daily loss limit hit', 'Data feed down']
    }
}

def send_alert(level, message, details=None):
    # Add Claude analysis for context
    if level in ['WARNING', 'CRITICAL']:
        prompt = f"Briefly explain this trading alert: {message}. Details: {details}"
        ai_context = claude.messages.create(
            model=claude_config['model'],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        message = f"{message}\n{ai_context.content}"

    # Send to appropriate channels
    for channel in alert_levels[level]['channels']:
        dispatch_alert(channel, message)
```

---

## Part 6: Premium Content Generation
*Package the intelligence for subscribers*

### Three Daily Market Reports

#### 1. Pre-Market Report (8:30 AM ET)
*"Here's what smart money is positioned for today"*

**Market Overview Section:**
- Previous session recap with index performance (SPY, QQQ, IWM, VIX)
- Overnight futures movement and implied open
- Volume/breadth analysis from yesterday's close
- UW dark pool vs lit market divergence signals

**Macro & Economic Drivers:**
- Today's economic calendar (Fed speakers, data releases)
- Bond yields and dollar positioning
- Oil, gold, crypto overnight moves
- UW Risk Reversal Skew showing regime state

**Technical Setup with UW Data:**
- **UW Spot GEX levels** - Where gamma will act as magnet/resistance
- **UW Max Pain** - The pin risk for today's expiry
- **UW GEX by Strike heatmap** - Visual of gamma walls
- Key support/resistance from overnight UW flow
- 0DTE setup zones based on UW Greek exposures

**Institutional Positioning (Our Edge):**
- **UW Congressional trades** from yesterday
- **UW Insider transactions** - CEO/CFO activity
- **UW Flow Alerts** - Unusual overnight activity
- **UW Greek Flow** - Institutional vs retail positioning

**Our Trading Plan:**
- Active signals with exact strikes and entries (Premium only)
- Risk levels and position sizing
- Trailing stop adjustments
- Expected holding periods

#### 2. Intraday Report (1:00 PM ET)
*"Real-time adjustments based on flow"*

**Market Pulse:**
- Current index levels vs morning predictions
- Intraday volume patterns
- TICK, ADD, VIX movements

**Flow Analysis Update:**
- **UW Flow per strike intraday** - What's getting hit NOW
- **UW Spot GEX updates** - How gamma positioning shifted
- **UW Call/Put Net Ticks** - Directional pressure building
- MOC imbalance predictions from afternoon flow

**Position Updates:**
- Current P&L on morning trades
- Trailing stop adjustments made
- New signals triggered
- Positions closed with reasoning

**Afternoon Setup:**
- MOC play potential based on UW flow
- Power hour expectations
- Overnight hold candidates

#### 3. Market Close Report (4:10 PM ET)
*"Today's results and tomorrow's setup"*

**Session Recap:**
- Final index performance with volume analysis
- Sector rotation heatmap
- Winners/losers with UW flow context

**Trade Performance:**
- Detailed P&L breakdown by strategy
- Win rate and average gain/loss
- Trailing stop effectiveness
- AI overseer alerts triggered

**Overnight Positioning:**
- **UW Greek Exposure by Strike & Expiry** for tomorrow
- **UW Off/Lit levels** showing hidden positioning
- After-hours flow developing
- Congressional trades to watch

**Tomorrow's Playbook:**
- Pre-market levels to watch
- Economic events and earnings
- Expected volatility from UW IV Term Structure
- Initial bias based on UW skew

### Content Differentiation by Tier

**Premium ($297/month) sees everything:**
```
"BUY SPY 440C @ 2.50 (current ask 2.48-2.52)
Congress member Pelosi bought $2M NVDA calls yesterday
GEX flips negative at 438.50, max gamma at 442
Stop: 2.10, Target 1: 3.75, Target 2: 5.00
Size: 2% of portfolio"
```
Plus: All UW data visualizations, exact flow numbers, real-time updates

**Basic ($97/month) sees delayed/rounded:**
```
"Bullish SPY setup around 440 strike
Institutional flow turning positive
Key gamma level around 438-439
Trailing stop strategy active"
```
Plus: Simplified charts, 60-second delayed signals, no exact entries

**Free teaser sees directional only:**
```
"Premium members entered SPY calls this morning
Market showing bullish flow patterns
Full report available to subscribers"
```

### Report Generation Pipeline

**Data Collection (Automated from Redis):**
```python
# All data already in Redis from config-driven fetcher
data = {
    'spot_gex': redis.get('raw:uw:spot_gex:SPY'),
    'flow_intraday': redis.get('raw:uw:flow_intraday:SPY'),
    'congress': redis.get('raw:uw:congress'),
    'max_pain': redis.get('raw:uw:max_pain:SPY'),
    'signals': redis.get('signals:active'),
    'pnl': redis.get('pnl:realized')
}
```

**Visualization Generation:**
1. Plotly charts auto-generated from templates
2. GEX heatmaps with strike/expiry grid
3. Flow timeline charts
4. P&L attribution waterfalls

**AI Narrative Generation:**
- Claude/GPT writes market color commentary
- Explains why trades triggered in plain English
- Translates Greek levels to actionable insights
- Adds risk warnings where appropriate

**Distribution Timing:**
- Premium: Real-time via Discord/Email/Telegram
- Basic: 60-second delay
- Free: 5-minute delay with heavy redaction

Everything stored for compliance:
```
reports:generated → {"date": "2024-01-15", "type": "premarket", "tier": "premium"}
reports:content → {full HTML/PDF content}
reports:metrics → {subscribers_sent: 127, open_rate: 0.89}
```

---

## Part 7: Multi-Channel Distribution
*Deliver to subscribers where they want it*

### Technical Architecture

```python
# Distribution configuration
distribution_config = {
    'discord': {
        'premium_webhook': os.environ['DISCORD_PREMIUM_WEBHOOK'],
        'basic_webhook': os.environ['DISCORD_BASIC_WEBHOOK'],
        'free_webhook': os.environ['DISCORD_FREE_WEBHOOK']
    },
    'telegram_admin': {
        # Telegram is for admin control only, not subscriber distribution
        'bot_token': os.environ['TELEGRAM_BOT_TOKEN'],
        'admin_chat_id': os.environ['TELEGRAM_ADMIN_CHAT']  # Your personal chat
    },
    'twitter': {
        'api_key': os.environ['TWITTER_API_KEY'],
        'api_secret': os.environ['TWITTER_API_SECRET'],
        'access_token': os.environ['TWITTER_ACCESS_TOKEN'],
        'access_secret': os.environ['TWITTER_ACCESS_SECRET']
    },
    'reddit': {
        'client_id': os.environ['REDDIT_CLIENT_ID'],
        'client_secret': os.environ['REDDIT_CLIENT_SECRET'],
        'username': os.environ['REDDIT_USERNAME'],
        'password': os.environ['REDDIT_PASSWORD'],
        'subreddit': 'options'  # Post to r/options
    }
}
```

### Queue Management for Delays

```python
from datetime import datetime, timedelta
import asyncio
from collections import deque

class MessageQueue:
    def __init__(self):
        self.premium_queue = deque()  # Immediate
        self.basic_queue = deque()    # 60-second delay
        self.free_queue = deque()     # 5-minute delay

    def add_signal(self, signal, content_by_tier):
        timestamp = datetime.now()

        # Queue messages with appropriate delays
        self.premium_queue.append({
            'content': content_by_tier['premium'],
            'send_at': timestamp,
            'channels': ['discord', 'telegram']
        })

        self.basic_queue.append({
            'content': content_by_tier['basic'],
            'send_at': timestamp + timedelta(seconds=60),
            'channels': ['discord', 'telegram']
        })

        self.free_queue.append({
            'content': content_by_tier['free'],
            'send_at': timestamp + timedelta(minutes=5),
            'channels': ['discord', 'twitter', 'reddit']
        })

    async def process_queues(self):
        while True:
            now = datetime.now()

            # Process each queue
            for queue in [self.premium_queue, self.basic_queue, self.free_queue]:
                while queue and queue[0]['send_at'] <= now:
                    message = queue.popleft()
                    await self.send_message(message)

            await asyncio.sleep(1)  # Check every second

    async def send_message(self, message):
        for channel in message['channels']:
            if channel == 'discord':
                await self.send_discord(message['content'])
            elif channel == 'telegram':
                await self.send_telegram(message['content'])
            elif channel == 'twitter':
                await self.post_twitter(message['content'])
            elif channel == 'reddit':
                await self.post_reddit(message['content'])
```

### Message Formatting Templates (Post-Fill Only)

```python
def format_signal_message(signal, tier='premium'):
    """Format messages ONLY after IBKR confirms fill"""

    # Signal contains actual fill price from IBKR
    templates = {
        'premium': {
            'discord': f"""
📊 **FILLED** - {signal.symbol}
✅ **Bought**: {signal.quantity} {signal.strike} {signal.type} @ ${signal.entry:.2f}
**Stop Loss**: ${signal.stop:.2f} (-{signal.stop_pct:.0f}%)
**Target 1**: ${signal.target1:.2f} (+{signal.target1_pct:.0f}%)
**Target 2**: ${signal.target2:.2f} (+{signal.target2_pct:.0f}%)

📈 **Why This Trade**:
• GEX: {signal.gex_level}
• Flow: {signal.flow_description}
• Congress: {signal.congress_activity}
• Dark Pool: {signal.dark_pool_activity}

⚠️ Risk: ${signal.risk_amount:.0f} ({signal.risk_pct:.1f}% of account)
""",
            'telegram': f"""
✅ FILLED: {signal.symbol} {signal.strike} {signal.type}
Entry: ${signal.entry:.2f}
Stop: ${signal.stop:.2f}
Targets: ${signal.target1:.2f} / ${signal.target2:.2f}
Triggers: {', '.join(signal.triggers)}
"""
        },
        'basic': {
            'discord': f"""
📊 **FILLED** - {signal.symbol}
✅ **Bought**: {signal.strike} {signal.type} @ ${signal.entry:.2f}
**Stop**: Set
**Targets**: Set
**Management**: Trailing stop active
""",
            'telegram': f"""
✅ FILLED: {signal.symbol} {signal.strike} {signal.type} @ ${signal.entry:.2f}
Manage with trailing stop
"""
        },
        'free': {
            'discord': f"""
🔔 Premium members just entered a {signal.direction} position on {signal.symbol}
Join premium for exact strikes and entries!
""",
            'twitter': f"""
🚨 New {signal.direction} signal triggered on ${signal.symbol}!

Smart money is positioning {signal.direction}.

Get exact strikes, entries, and stops with premium access.

#Options #Trading #{signal.symbol}
""",
            'reddit': f"""
**Educational Alert: {signal.symbol} Options Activity**

Our system detected unusual {signal.direction} activity in {signal.symbol} options.

Key observations:
- Gamma exposure shifting
- Institutional flow detected
- Risk/reward setup identified

This is for educational purposes only. Always do your own research.
"""
        }
    }

    return templates[tier]
```

### Rate Limiting

```python
class RateLimiter:
    def __init__(self):
        self.limits = {
            'discord': {'per_second': 5, 'burst': 10},
            'telegram': {'per_second': 30, 'burst': 50},
            'twitter': {'per_15min': 50, 'per_day': 2400},
            'reddit': {'per_minute': 10, 'per_hour': 100}
        }
        self.counters = defaultdict(deque)

    async def check_rate_limit(self, platform):
        now = time.time()
        counter = self.counters[platform]

        # Remove old entries
        if platform == 'twitter':
            cutoff = now - 900  # 15 minutes
        elif platform == 'reddit':
            cutoff = now - 60  # 1 minute
        else:
            cutoff = now - 1  # 1 second

        while counter and counter[0] < cutoff:
            counter.popleft()

        # Check limits
        if platform == 'discord' and len(counter) >= self.limits['discord']['per_second']:
            await asyncio.sleep(1)
        elif platform == 'telegram' and len(counter) >= self.limits['telegram']['per_second']:
            await asyncio.sleep(0.1)
        elif platform == 'twitter' and len(counter) >= self.limits['twitter']['per_15min']:
            await asyncio.sleep(60)  # Wait a minute
        elif platform == 'reddit' and len(counter) >= self.limits['reddit']['per_minute']:
            await asyncio.sleep(60)

        # Record this request
        counter.append(now)
```

### Signal Publishing After Fill Confirmation

```python
class SignalPublisher:
    def __init__(self):
        self.message_ids = {}  # Store message IDs for thread replies

    async def publish_after_fill(self, order, fill_details):
        """Only publish signal AFTER IBKR confirms fill"""

        # Wait for IBKR fill confirmation
        if not fill_details['filled']:
            return  # Don't publish if not filled

        # Create signal with actual fill price
        signal = {
            'symbol': fill_details['symbol'],
            'strike': fill_details['strike'],
            'type': fill_details['type'],  # CALL or PUT
            'entry': fill_details['avg_fill_price'],  # Actual fill price from IBKR
            'quantity': fill_details['filled_qty'],
            'order_id': fill_details['order_id']
        }

        # Publish to all tiers with appropriate delays
        message_ids = await self.send_initial_signal(signal)

        # Store message IDs for future updates
        self.message_ids[signal['order_id']] = message_ids

        return message_ids
```

### Thread-Based Position Management Updates

```python
class PositionUpdateManager:
    """Reply to original messages when positions are managed"""

    async def update_trailing_stop(self, order_id, new_stop):
        """Reply to original message when trailing stop moves"""

        if order_id not in self.message_ids:
            return

        original_messages = self.message_ids[order_id]

        # Update each tier's message
        updates = {
            'premium': f"📈 UPDATE: Trailing stop moved to ${new_stop:.2f}",
            'basic': f"📈 UPDATE: Stop adjusted",
            'free': None  # No updates for free tier
        }

        # Reply to original Discord messages
        await self.reply_to_discord(
            original_messages['discord_premium'],
            updates['premium']
        )

        # Reply after 60 seconds for basic
        await asyncio.sleep(60)
        await self.reply_to_discord(
            original_messages['discord_basic'],
            updates['basic']
        )

    async def update_partial_exit(self, order_id, exit_details):
        """Reply when taking partial profits"""

        original_messages = self.message_ids[order_id]

        updates = {
            'premium': f"""
💰 PARTIAL EXIT: Sold {exit_details['qty']} @ ${exit_details['price']:.2f}
Profit: ${exit_details['profit']:.2f} (+{exit_details['profit_pct']:.1f}%)
Remaining: {exit_details['remaining_qty']} contracts
""",
            'basic': f"💰 PARTIAL EXIT: Target 1 hit @ ${exit_details['price']:.2f}",
            'free': None
        }

        await self.send_threaded_updates(original_messages, updates)

    async def update_full_exit(self, order_id, exit_details):
        """Reply when position fully closed"""

        original_messages = self.message_ids[order_id]

        updates = {
            'premium': f"""
✅ POSITION CLOSED
Exit: ${exit_details['price']:.2f}
P&L: ${exit_details['total_pnl']:.2f} ({exit_details['pnl_pct']:+.1f}%)
Duration: {exit_details['duration']}
""",
            'basic': f"✅ CLOSED @ ${exit_details['price']:.2f}",
            'free': None
        }

        await self.send_threaded_updates(original_messages, updates)
```

### Platform-Specific Reply Implementations

```python
# Discord - Reply to thread
async def reply_to_discord(original_message_id, update_content):
    """Reply in thread to original Discord message"""

    # Discord webhooks don't support replies directly
    # Need to use discord.py bot for thread replies
    channel = bot.get_channel(CHANNEL_ID)
    original = await channel.fetch_message(original_message_id)

    # Create or find thread
    if hasattr(original, 'thread'):
        thread = original.thread
    else:
        thread = await original.create_thread(
            name=f"Updates - {original.embeds[0].title}",
            auto_archive_duration=1440  # 24 hours
        )

    # Send update in thread
    await thread.send(update_content)

# Telegram - Reply to message
async def reply_to_telegram(original_message_id, chat_id, update_content):
    """Reply to original Telegram message"""

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(
        chat_id=chat_id,
        text=update_content,
        reply_to_message_id=original_message_id,
        parse_mode='Markdown'
    )

# Store message IDs when sending initial signals
async def send_initial_signal(signal):
    """Send signal and store message IDs for replies"""

    message_ids = {}

    # Discord Premium (immediate)
    discord_msg = await send_discord_with_id(
        format_signal_premium(signal),
        PREMIUM_WEBHOOK
    )
    message_ids['discord_premium'] = discord_msg.id

    # Telegram Premium (immediate)
    telegram_msg = await send_telegram_with_id(
        format_signal_premium(signal),
        PREMIUM_CHAT
    )
    message_ids['telegram_premium'] = telegram_msg.message_id

    # Queue basic/free with delays but store future IDs
    # ...

    return message_ids
```

### Example Flow

```python
"""
1. Signal generated, order sent to IBKR
2. IBKR fills order at 2.50
3. System publishes: "✅ FILLED: BUY SPY 440C @ 2.50" (premium immediate)
4. Price moves up, trailing stop adjusted
5. System replies to original: "📈 UPDATE: Trailing stop moved to $2.75"
6. Take profit hit at 3.75
7. System replies: "💰 PARTIAL EXIT: Sold 5 @ $3.75 (+50%)"
8. Final exit at 4.50
9. System replies: "✅ POSITION CLOSED: Exit $4.50, P&L: $200 (+80%)"

All updates thread under the original fill message!
"""
```

### Content Redaction by Tier

**Premium sees everything (immediate after fill):**
```
✅ FILLED: BUY 10 SPY 440C @ 2.50
Stop: 2.10 (-16%)
Target 1: 3.75 (+50%)
Target 2: 5.00 (+100%)
Congress: Pelosi bought $2M NVDA
GEX flips at 438.50
Dark pool accumulation detected
```

**Basic sees exact strike, no analytics (60-second delay):**
```
✅ FILLED: BUY SPY 440C @ 2.50
Stop: Set
Targets: Set
Manage with trailing stop
```

**Free sees teasers only (5-minute delay):**
```
Bullish signal on SPY!
Premium members positioned in calls.
Join for exact details.
```

---

## Part 8: System Operations & Monitoring

### React Dashboard for System Health

```javascript
// Dashboard Components Structure
const TradingDashboard = () => {
  return (
    <div className="dashboard">
      {/* System Status Bar */}
      <StatusBar>
        <SystemHealth />  // Green/Yellow/Red indicator
        <TradingActive /> // ON/OFF based on config flag
        <Uptime />        // Hours:Minutes since start
        <LastHeartbeat /> // UW and IBKR timestamps
      </StatusBar>

      {/* Data Feed Status Panel */}
      <DataFeeds>
        <FeedStatus name="UW Spot GEX" lastUpdate={} staleness={} />
        <FeedStatus name="UW Flow" lastUpdate={} staleness={} />
        <FeedStatus name="IBKR TWS" connected={} latency={} />
        <FeedStatus name="Redis" connected={} memory={} />
      </DataFeeds>

      {/* Active Positions Table */}
      <PositionsTable>
        <Position
          symbol="SPY 440C"
          quantity={10}
          entry={2.50}
          current={3.75}
          pnl={125}
          pnlPercent={50}
          actions={
            <button onClick={() => closePosition('market')}>
              Close at Market
            </button>
          }
        />
      </PositionsTable>

      {/* Today's Performance */}
      <PerformanceMetrics>
        <Metric label="Daily P&L" value={pnl} />
        <Metric label="Win Rate" value={winRate} />
        <Metric label="Trades Today" value={tradeCount} />
        <Metric label="Risk Used" value={riskPercent} />
      </PerformanceMetrics>

      {/* Recent Signals */}
      <SignalsLog limit={10} />

      {/* Alert Panel */}
      <AlertsPanel>
        <Alert level="warning" message="High slippage on SPY" />
      </AlertsPanel>
    </div>
  );
};
```

**Backend API for Dashboard:**
```python
# api/dashboard.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"])

@app.get("/api/status")
async def get_system_status():
    return {
        'trading_active': redis.get('config:trading_active'),
        'uptime': time.time() - start_time,
        'positions': get_active_positions(),
        'feeds': check_feed_status(),
        'daily_pnl': calculate_daily_pnl()
    }

@app.post("/api/position/{position_id}/close")
async def close_position_market(position_id: str):
    """Emergency close position at market"""
    position = redis.get(f'positions:active:{position_id}')
    order = MarketOrder('SELL', position['quantity'])
    ib.placeOrder(position['contract'], order)
    return {'status': 'closing', 'order_id': order.orderId}
```

### Startup/Shutdown Procedures

```python
#!/usr/bin/env python
# main.py - Single entry point executable

import asyncio
import signal
import sys
from datetime import datetime, time

class TradingSystem:
    def __init__(self):
        self.running = False
        self.components = {}

    async def startup(self):
        """Morning startup sequence"""
        print("🚀 Starting Quanticity Trading System...")

        # 1. Load configuration
        self.config = load_config('config/data_sources.yaml')

        # 2. Check market hours
        if not self.is_market_hours():
            print("❌ Outside market hours")
            return False

        # 3. Connect Redis
        self.redis = await connect_redis()
        print("✅ Redis connected")

        # 4. Connect IBKR TWS
        self.ib = await connect_ibkr()
        print("✅ IBKR TWS connected")

        # 5. Reconcile positions
        await self.reconcile_positions()
        print("✅ Positions reconciled")

        # 6. Start data feeds
        await self.start_data_feeds()
        print("✅ Data feeds active")

        # 7. Start components
        await self.start_trading_components()
        print("✅ All systems operational")

        # 8. Start dashboard API
        await self.start_dashboard()

        self.running = True
        return True

    async def reconcile_positions(self):
        """Match IBKR positions with Redis on startup"""

        # Get positions from IBKR
        ibkr_positions = self.ib.positions()

        for pos in ibkr_positions:
            if pos.contract.secType == 'OPT':
                # Check if we have this in Redis
                redis_key = f"positions:active:{pos.contract.symbol}_{pos.contract.strike}{pos.contract.right}"

                if not self.redis.exists(redis_key):
                    # Position exists in IBKR but not Redis - restore it
                    print(f"⚠️ Restoring position from IBKR: {pos.contract.localSymbol}")

                    position_data = {
                        'symbol': pos.contract.symbol,
                        'strike': pos.contract.strike,
                        'type': 'CALL' if pos.contract.right == 'C' else 'PUT',
                        'quantity': pos.position,
                        'avg_cost': pos.avgCost,
                        'restored_from_ibkr': True
                    }

                    self.redis.hset(redis_key, mapping=position_data)

    async def shutdown(self):
        """Evening shutdown sequence"""
        print("🔴 Initiating shutdown...")

        # 1. Stop accepting new trades
        self.redis.set('config:trading_active', 'false')

        # 2. Archive today's trades
        await archive_daily_trades()

        # 3. Generate end-of-day report
        await generate_eod_report()

        # 4. Disconnect feeds
        await self.stop_data_feeds()

        # 5. Disconnect IBKR (positions remain open)
        self.ib.disconnect()

        # 6. Final Redis backup
        await self.backup_critical_data()

        print("✅ Shutdown complete. Positions preserved in IBKR.")

    def is_market_hours(self):
        """Check if we should be running"""
        now = datetime.now()
        weekday = now.weekday()

        # No weekends
        if weekday >= 5:
            return False

        current_time = now.time()

        # Pre-market: 4:00 AM - 9:30 AM ET
        # Market: 9:30 AM - 4:00 PM ET
        # Post-market: 4:00 PM - 8:00 PM ET

        market_start = time(4, 0)  # 4:00 AM
        market_end = time(20, 0)   # 8:00 PM

        return market_start <= current_time <= market_end

    async def run(self):
        """Main execution loop"""

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        if not await self.startup():
            sys.exit(1)

        # Main loop
        while self.running:
            # Check if still in market hours
            if not self.is_market_hours():
                print("Market hours ended")
                break

            # Check config for trading active flag
            trading_active = self.redis.get('config:trading_active')
            if trading_active == 'false':
                print("⏸️ Trading paused via config")
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(1)

        await self.shutdown()

if __name__ == "__main__":
    system = TradingSystem()
    asyncio.run(system.run())
```

### Emergency Procedures & Safeguards

```python
class EmergencyManager:
    """Handle all emergency scenarios"""

    def __init__(self, redis, ib, telegram_admin):
        self.redis = redis
        self.ib = ib
        self.admin = telegram_admin
        self.circuit_breaker_triggered = False

    async def check_daily_loss_limit(self):
        """Circuit breaker for daily losses"""
        daily_pnl = float(self.redis.get('pnl:daily') or 0)
        account_value = float(self.redis.get('account:value') or 100000)

        loss_percent = abs(daily_pnl / account_value * 100)

        if loss_percent >= 6.0:  # 6% daily loss limit
            await self.trigger_circuit_breaker()
            return True

        elif loss_percent >= 4.0:  # Warning at 4%
            await self.admin.send_critical_alert({
                'message': f'Approaching daily loss limit: {loss_percent:.1f}%',
                'halt_trading': False
            })

        return False

    async def trigger_circuit_breaker(self):
        """Emergency stop all trading"""
        self.circuit_breaker_triggered = True

        # 1. Stop all new trades immediately
        self.redis.set('config:trading_active', 'false')
        self.redis.set('emergency:circuit_breaker', 'true')

        # 2. Cancel all pending orders
        open_orders = self.ib.openOrders()
        for order in open_orders:
            self.ib.cancelOrder(order)

        # 3. Alert admin
        await self.admin.send_critical_alert({
            'message': 'CIRCUIT BREAKER TRIGGERED - Daily loss limit hit',
            'details': {
                'daily_pnl': self.redis.get('pnl:daily'),
                'open_positions': len(self.get_active_positions())
            },
            'halt_trading': True
        })

    async def handle_api_outage(self):
        """Handle data feed failures"""

        # Check UW API staleness
        last_uw_update = float(self.redis.get('heartbeat:uw') or 0)
        if time.time() - last_uw_update > 120:  # 2 minutes
            await self.emergency_stop("UW API down for 2+ minutes")

        # Check IBKR connection
        if not self.ib.isConnected():
            # Try reconnect once
            try:
                self.ib.connect('127.0.0.1', 7497, clientId=1)
            except:
                await self.emergency_stop("IBKR TWS disconnected")

    async def handle_massive_gap(self, symbol, gap_percent):
        """Handle massive gap moves"""

        if abs(gap_percent) > 5:  # 5% gap
            # 1. Flatten all positions in that symbol
            positions = self.get_positions_for_symbol(symbol)
            for pos in positions:
                await self.close_position_market(pos)

            # 2. Alert admin
            await self.admin.send_critical_alert({
                'message': f'Massive gap detected in {symbol}: {gap_percent:.1f}%',
                'details': {'positions_closed': len(positions)},
                'halt_trading': False
            })

    async def emergency_stop(self, reason):
        """Complete emergency shutdown"""

        # 1. Stop trading
        self.redis.set('config:trading_active', 'false')

        # 2. Log emergency
        self.redis.lpush('emergency:log', json.dumps({
            'timestamp': time.time(),
            'reason': reason
        }))

        # 3. Alert admin
        await self.admin.send_critical_alert({
            'message': f'EMERGENCY STOP: {reason}',
            'halt_trading': True
        })
```

### Strategy Performance Tracking & Degradation Detection

```python
class PerformanceTracker:
    """Track strategy performance and detect degradation"""

    def __init__(self):
        self.rolling_window = 20  # trades
        self.baseline_win_rate = 0.55  # 55% expected win rate

    async def track_trade_performance(self, trade):
        """Record trade results"""

        metrics = {
            'symbol': trade['symbol'],
            'strategy': trade['strategy'],
            'entry': trade['entry_price'],
            'exit': trade['exit_price'],
            'pnl': trade['pnl'],
            'pnl_percent': trade['pnl_percent'],
            'duration': trade['duration_minutes'],
            'slippage': trade['slippage'],
            'timestamp': trade['exit_time']
        }

        # Store in Redis sorted set by timestamp
        self.redis.zadd(
            f"performance:{trade['strategy']}",
            {json.dumps(metrics): trade['exit_time']}
        )

    async def detect_strategy_degradation(self, strategy_name):
        """Detect if strategy is underperforming"""

        # Get last N trades
        recent_trades = self.redis.zrange(
            f"performance:{strategy_name}",
            -self.rolling_window,
            -1
        )

        if len(recent_trades) < self.rolling_window:
            return None  # Not enough data

        # Calculate metrics
        wins = sum(1 for t in recent_trades if json.loads(t)['pnl'] > 0)
        win_rate = wins / len(recent_trades)

        avg_win = np.mean([json.loads(t)['pnl'] for t in recent_trades if json.loads(t)['pnl'] > 0])
        avg_loss = np.mean([json.loads(t)['pnl'] for t in recent_trades if json.loads(t)['pnl'] <= 0])

        # Degradation checks
        degradation_signals = []

        if win_rate < self.baseline_win_rate - 0.1:  # 10% below baseline
            degradation_signals.append(f"Win rate dropped to {win_rate:.1%}")

        if abs(avg_loss) > avg_win * 1.5:  # Losses 50% bigger than wins
            degradation_signals.append(f"Risk/reward deteriorated")

        # Check for consecutive losses
        last_5 = recent_trades[-5:]
        if all(json.loads(t)['pnl'] < 0 for t in last_5):
            degradation_signals.append("5 consecutive losses")

        if degradation_signals:
            await self.alert_degradation(strategy_name, degradation_signals)

            # Auto-disable if severe
            if len(degradation_signals) >= 2:
                self.redis.set(f"strategy:{strategy_name}:enabled", "false")
                return "DISABLED"

        return "OK"

    async def generate_performance_report(self):
        """Daily performance analytics"""

        return {
            '0dte_gamma': {
                'trades': 15,
                'win_rate': 0.60,
                'avg_win': 125,
                'avg_loss': -75,
                'profit_factor': 2.5,
                'sharpe': 1.8
            },
            '14d_directional': {
                'trades': 5,
                'win_rate': 0.40,
                'avg_win': 450,
                'avg_loss': -150,
                'profit_factor': 1.2,
                'sharpe': 0.9
            }
        }
```

### Data Backup & Recovery

```python
class DataManager:
    """Handle data persistence and recovery"""

    async def backup_critical_data(self):
        """Backup critical Redis data to disk"""

        critical_keys = [
            'positions:active:*',
            'trades:history',
            'pnl:*',
            'performance:*'
        ]

        backup_data = {}
        for pattern in critical_keys:
            keys = self.redis.keys(pattern)
            for key in keys:
                backup_data[key] = self.redis.get(key)

        # Save to disk with timestamp
        backup_file = f"backups/redis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)

        # Keep only last 7 days of backups
        self.cleanup_old_backups()

    async def recover_from_ibkr(self):
        """Recover all position data from IBKR if Redis lost"""

        positions = self.ib.positions()
        portfolio = self.ib.portfolio()

        for item in portfolio:
            if item.contract.secType == 'OPT':
                # Reconstruct position data
                position_data = {
                    'symbol': item.contract.symbol,
                    'strike': item.contract.strike,
                    'type': 'CALL' if item.contract.right == 'C' else 'PUT',
                    'quantity': item.position,
                    'market_value': item.marketValue,
                    'avg_cost': item.averageCost,
                    'unrealized_pnl': item.unrealizedPNL,
                    'realized_pnl': item.realizedPNL
                }

                # Store in Redis
                key = f"positions:recovered:{item.contract.localSymbol}"
                self.redis.hset(key, mapping=position_data)

        print(f"✅ Recovered {len(positions)} positions from IBKR")
```

---

## Building This System - Detailed Implementation Plan

### Required Python Packages
```bash
# Core requirements
pip install redis==5.0.1
pip install aiohttp==3.9.1
pip install pandas==2.1.4
pip install pyarrow==14.0.1  # For parquet files
pip install pyyaml==6.0.1
pip install python-dotenv==1.0.0

# API integrations
pip install ib_insync==0.9.86  # Interactive Brokers
pip install anthropic==0.18.1  # Claude API
pip install discord.py==2.3.2
pip install python-telegram-bot==20.7
pip install tweepy==4.14.0
pip install praw==7.7.1  # Reddit

# Additional utilities
pip install apscheduler==3.10.4  # Task scheduling
pip install watchdog==3.0.0  # File monitoring for config reload
pip install loguru==0.7.2  # Better logging
```

### Phase 1: Foundation & Config System (Day 1-2)

**1.1 Project Structure:**
```
quanticity_capital/
├── config/
│   ├── data_sources.yaml      # API endpoints configuration
│   └── .env                    # API keys and secrets
├── src/
│   ├── data_ingestion/
│   │   ├── generic_fetcher.py # Config-driven fetcher
│   │   ├── ibkr_handler.py    # IBKR WebSocket special case
│   │   └── transformers.py    # Data transformation functions
│   ├── analytics/
│   │   ├── microstructure.py  # Liquidity, book imbalance
│   │   ├── flow_analysis.py   # Flow momentum, MOC predictor
│   │   └── regime.py          # Market regime classification
│   ├── signals/
│   │   ├── zerodте.py         # 0DTE strategies
│   │   └── directional.py     # 14-day strategies
│   ├── execution/
│   │   ├── risk_manager.py    # Position sizing, validation
│   │   └── order_manager.py   # IBKR order execution
│   ├── ai_overseer/
│   │   └── claude_monitor.py  # Claude integration
│   └── distribution/
│       └── messenger.py       # Multi-channel distribution
├── logs/
├── archive/                    # Daily trade archives
└── main.py                     # Entry point
```

**1.2 Generic Fetcher Implementation:**
```python
# src/data_ingestion/generic_fetcher.py
class GenericFetcher:
    def __init__(self, config_path):
        self.config = yaml.safe_load(open(config_path))
        self.redis = redis.Redis(decode_responses=False)
        self.setup_config_watcher()

    async def fetch_endpoint(self, source, endpoint_name, endpoint_config):
        """Fetch data from any endpoint defined in config"""
        url = f"{source['base_url']}{endpoint_config['path']}"

        # Symbol expansion if needed
        if '{symbol}' in url:
            for symbol in endpoint_config['symbols']:
                await self._fetch_single(url.format(symbol=symbol), endpoint_config)
        else:
            await self._fetch_single(url, endpoint_config)

    def setup_config_watcher(self):
        """Hot-reload config on changes"""
        observer = Observer()
        observer.schedule(ConfigReloadHandler(self), path='config/', recursive=False)
        observer.start()
```

**1.3 Test with Live APIs:**
```python
# test_live_apis.py
def test_unusual_whales():
    """Test UW API connectivity and response format"""
    response = requests.get(
        "https://api.unusualwhales.com/api/stocks/SPY/spot-gex-exposures",
        headers={"Authorization": f"Bearer {UW_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert 'total_gamma' in data  # Verify expected fields
    print(f"✓ UW API working: {data['total_gamma']}")

def test_ibkr_connection():
    """Test IBKR TWS connection"""
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)  # Paper trading port
    assert ib.isConnected()
    print("✓ IBKR TWS connected")
    ib.disconnect()
```

### Phase 2: Data Pipeline (Day 3-4)

**2.1 Complete Configuration:**
```yaml
# config/data_sources.yaml
data_sources:
  unusual_whales:
    base_url: "https://api.unusualwhales.com/api"
    # ... (all endpoints as defined earlier)

  # IBKR handled separately due to WebSocket nature
```

**2.2 IBKR WebSocket Handler:**
```python
# src/data_ingestion/ibkr_handler.py
class IBKRHandler:
    def __init__(self):
        self.ib = IB()
        self.redis = redis.Redis()
        self.subscriptions = {}

    async def connect(self):
        self.ib.connect('127.0.0.1', 7497, clientId=1)

    async def subscribe_market_depth(self, symbol):
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.reqMktDepth(contract, numRows=10)
        self.ib.pendingTickersEvent += self.on_depth_update

    def on_depth_update(self, ticker):
        """Store depth in Redis with TTL"""
        depth_data = {
            'bids': ticker.domBids,
            'asks': ticker.domAsks,
            'timestamp': time.time()
        }
        self.redis.setex(
            f'raw:ibkr:depth:{ticker.symbol}',
            10,  # 10 second TTL
            json.dumps(depth_data)
        )
```

**2.3 Verify Data Flow:**
```python
# verify_data_flow.py
def verify_all_feeds():
    r = redis.Redis()

    required_feeds = [
        'raw:uw:spot_gex:SPY',
        'raw:uw:flow_intraday:SPY',
        'raw:ibkr:depth:SPY',
        'raw:ibkr:trades:SPY'
    ]

    for feed in required_feeds:
        data = r.get(feed)
        if data:
            age = time.time() - json.loads(data).get('timestamp', 0)
            print(f"✓ {feed}: {age:.1f}s old")
        else:
            print(f"✗ {feed}: NO DATA")
```

### Phase 3: Analytics Engine (Day 5)

**3.1 Microstructure Analytics:**
```python
# src/analytics/microstructure.py
def calculate_liquidity_score(symbol):
    depth = redis.get(f'raw:ibkr:depth:{symbol}')

    # Calculate spread
    best_bid = depth['bids'][0]['price']
    best_ask = depth['asks'][0]['price']
    spread_bps = (best_ask - best_bid) / best_bid * 10000

    # Calculate depth
    bid_depth = sum(level['size'] for level in depth['bids'][:5])
    ask_depth = sum(level['size'] for level in depth['asks'][:5])

    # Score A-D based on spread and depth
    if spread_bps < 5 and min(bid_depth, ask_depth) > 1000:
        score = 'A'
    elif spread_bps < 10 and min(bid_depth, ask_depth) > 500:
        score = 'B'
    else:
        score = 'C'

    redis.setex(f'analytics:liquidity:{symbol}', 60, score)
```

### Phase 4: Signal Generation (Day 6-7)

**4.1 0DTE Strategy Implementation:**
```python
# src/signals/zerodte.py
class ZeroDTEGammaScalping:
    def __init__(self):
        self.redis = redis.Redis()
        self.symbols = ['SPX', 'SPY', 'QQQ', 'IWM']

    async def check_signals(self):
        for symbol in self.symbols:
            # Get required data
            spot_gex = self.redis.get(f'raw:uw:spot_gex:{symbol}')
            liquidity = self.redis.get(f'analytics:liquidity:{symbol}')

            # Check trigger conditions
            if self.near_max_gamma(spot_gex) and liquidity in ['A', 'B']:
                signal = {
                    'symbol': symbol,
                    'strategy': '0dte_gamma',
                    'direction': self.get_direction(spot_gex),
                    'confidence': 0.85,
                    'triggers': ['max_gamma', 'good_liquidity']
                }

                # Validate and execute
                if self.validate_signal(signal):
                    await self.execute_signal(signal)
```

### Phase 5: Execution & Risk (Day 7-8)

**5.1 Order Execution:**
```python
# src/execution/order_manager.py
class OrderManager:
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=1)

    async def execute_option_order(self, signal):
        # Create option contract
        contract = Option(
            signal['symbol'],
            signal['expiry'],
            signal['strike'],
            signal['right'],  # 'C' or 'P'
            'SMART'
        )

        # Create order
        order = LimitOrder(
            'BUY',
            signal['quantity'],
            signal['limit_price']
        )

        # Place and monitor
        trade = self.ib.placeOrder(contract, order)

        # Wait for fill or timeout
        await asyncio.sleep(30)
        if not trade.isDone():
            self.ib.cancelOrder(order)
```

### Phase 6: AI Overseer (Day 8)

**6.1 Claude Integration:**
```python
# src/ai_overseer/claude_monitor.py
from anthropic import Anthropic

class ClaudeMonitor:
    def __init__(self):
        self.client = Anthropic(api_key=os.environ['CLAUDE_API_KEY'])

    async def validate_signal(self, signal):
        prompt = f"""
        Review this options signal:
        {json.dumps(signal, indent=2)}

        Is this logical? Any concerns?
        Reply with APPROVE or REJECT and brief reason.
        """

        response = self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        return "APPROVE" in response.content
```

### Phase 7: Distribution (Day 9-10)

**7.1 Multi-Channel Messenger:**
```python
# src/distribution/messenger.py
class Messenger:
    def __init__(self):
        self.discord_webhook = os.environ['DISCORD_WEBHOOK']
        self.telegram_bot = telegram.Bot(os.environ['TELEGRAM_TOKEN'])
        self.queue = MessageQueue()

    async def send_signal(self, signal):
        # Format for each tier
        premium_msg = self.format_premium(signal)
        basic_msg = self.format_basic(signal)
        free_msg = self.format_free(signal)

        # Queue with delays
        await self.queue.add_signal(signal, {
            'premium': premium_msg,
            'basic': basic_msg,
            'free': free_msg
        })
```

### Phase 8: Final Integration (Day 10)

**8.1 Main Entry Point:**
```python
# main.py
async def main():
    # Initialize components
    fetcher = GenericFetcher('config/data_sources.yaml')
    ibkr = IBKRHandler()
    analytics = AnalyticsEngine()
    signals = SignalGenerator()
    overseer = ClaudeMonitor()
    messenger = Messenger()

    # Connect IBKR
    await ibkr.connect()

    # Start all tasks
    tasks = [
        fetcher.start(),
        ibkr.start(),
        analytics.start(),
        signals.start(),
        overseer.start(),
        messenger.start()
    ]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
```

### Testing Procedures

**End-to-End Test:**
```python
def test_paper_trading():
    """Test complete flow with paper account"""

    # 1. Verify data feeds
    assert redis.get('raw:uw:spot_gex:SPY')

    # 2. Check analytics
    assert redis.get('analytics:liquidity:SPY')

    # 3. Generate test signal
    test_signal = create_test_signal()

    # 4. Execute on paper
    result = execute_paper_trade(test_signal)

    # 5. Verify distribution
    assert discord_message_sent()

    print("✓ Full pipeline working")
```

---

## Why This Architecture Works

1. **Config-driven flexibility** - Add/remove data sources without touching code, adapt to API changes instantly
2. **Unusual Whales eliminates complexity** - No Greeks calculation, no GEX computation, pre-flagged institutional flow
3. **Generic fetcher pattern** - One fetcher to rule them all, ~500 lines handles infinite endpoints
4. **Redis with TTLs** - Data expires automatically, no unbounded growth
5. **AI Overseer catches issues** - Anomalies detected before losses
6. **Progressive building** - Start with 2-3 endpoints Day 1, full system Day 10

The entire system is **~2000 lines of Python** instead of 20,000:
- Generic fetcher: ~500 lines
- IBKR handler: ~300 lines
- Analytics modules: ~400 lines
- Strategy engines: ~400 lines
- AI overseer: ~200 lines
- Report/distribution: ~200 lines

One person can understand, debug, enhance, and most importantly - **adapt it on the fly**.


## Critical Success Factors

1. **Config-driven agility** - Must be able to adapt endpoints without code changes
2. **UW API rate limits** - 120 requests/minute means smart scheduling in config
3. **UW Spot GEX per minute** - The 1-minute gamma updates are GOLD for 0DTE
4. **Flow per strike intraday** - Essential for MOC prediction
5. **Off/Lit levels** - Dark pool activity reveals true institutional intent
6. **Generic fetcher reliability** - Must handle retries, transforms, failures gracefully
7. **IBKR connectivity** - TWS must stay connected for execution
8. **Hot-reload working** - Config changes picked up without restart
9. **Overseer vigilance** - Must catch anomalies within 60 seconds
10. **Report quality** - Subscribers pay for clarity with these insights
11. **⚠️ Economic Calendar API** - MUST find proper API for FOMC, CPI, NFP events

The config-driven approach means you can tune the system while it's running - if MOC prediction needs more frequent flow data, just change the interval in YAML.

## Data Completeness Summary

**What We Have:**
- ✅ Options flow and Greeks (UW)
- ✅ Congressional/insider trading (UW)
- ✅ Dark pool and institutional flow (UW)
- ✅ News headlines with sentiment (UW)
- ✅ Earnings calendar (UW + supplementary)
- ✅ Global markets, futures, FX, crypto (IBKR)
- ✅ Level 2 depth and execution (IBKR)

**What We Need:**
- ❌ Economic calendar API for major events (FOMC, CPI, NFP, etc.)

Once we secure the economic calendar API, the data ingestion layer is 100% complete.