# Unusual Whales API Endpoints

## Table of Contents
- [REST API Endpoints](#rest-api-endpoints)
  - [Option Contract Data](#option-contract-data)
  - [Stock-Level Option Data](#stock-level-option-data)
  - [Greek Exposure](#greek-exposure)
  - [GEX (Spot Exposures)](#gex-spot-exposures)
  - [Order Flow Metrics](#order-flow-metrics)
  - [Volatility & IV Analysis](#volatility--iv-analysis)
  - [Market Microstructure](#market-microstructure)
  - [Screening & Analytics](#screening--analytics)
  - [Insider/Corporate](#insidercorporate)
- [WebSocket Channels](#websocket-channels)

---

## REST API Endpoints

### Option Contract Data

#### Option Contract Flow (REST)
**Endpoint:** `GET /api/option-contract/{id}/flow`
**Ingestion:** Scheduled: On-demand / Intraday polling
**Priority:** High

**Description:**
Returns detailed flow data for a specific option contract including Greeks, volume breakdown (ask/bid/mid/multi), premium, and trade metadata. Use this to analyze individual contract activity and sentiment.

**Request:**
- Method: GET
- Path Parameter: `{id}` - Contract ID

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/option-contract/{id}/flow", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "ask_vol": 2,
      "bid_vol": 1,
      "canceled": false,
      "delta": "0.610546281537814",
      "er_time": "postmarket",
      "ewma_nbbo_ask": "21.60",
      "ewma_nbbo_bid": "21.45",
      "exchange": "MXOP",
      "executed_at": "2024-08-21T13:50:52.278302Z",
      "expiry": "2025-01-17",
      "flow_alert_id": null,
      "full_name": "NVIDIA CORP",
      "gamma": "0.00775013889662635",
      "id": "8ef90a2d-d881-41de-98c9-c1de4318dcb5",
      "implied_volatility": "0.604347250962543",
      "industry_type": "Semiconductors",
      "marketcap": "3130350000000.00",
      "mid_vol": 30,
      "multi_vol": 30,
      "nbbo_ask": "21.60",
      "nbbo_bid": "21.45",
      "next_earnings_date": "2024-08-28",
      "no_side_vol": 0,
      "open_interest": 6016,
      "option_chain_id": "NVDA250117C00124000",
      "option_type": "call",
      "premium": "2150.00",
      "price": "21.50",
      "report_flags": [],
      "rho": "0.2316546330093438",
      "rule_id": null,
      "sector": "Technology",
      "size": 1,
      "stock_multi_vol": 0,
      "strike": "124.0000000000",
      "tags": [
        "bid_side",
        "bearish",
        "earnings_next_week"
      ],
      "theo": "21.49999999999999",
      "theta": "-0.0640155364004474",
      "underlying_price": "128.16",
      "underlying_symbol": "NVDA",
      "upstream_condition_detail": "auto",
      "vega": "0.3140468475903719",
      "volume": 33
    }
  ]
}
```

---

#### Option Contract Intraday (REST)
**Endpoint:** `GET /api/option-contract/{id}/intraday`
**Ingestion:** Scheduled: Hourly during market hours
**Priority:** Medium

**Description:**
Returns minute-by-minute OHLC data, IV range, volume breakdown, and premium by side for a specific option contract. Use for intraday price action and volume analysis.

**Request:**
- Method: GET
- Path Parameter: `{id}` - Contract ID

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/option-contract/{id}/intraday", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "avg_price": "30.18641509433962264151",
      "close": "30.22",
      "expiry": "2024-06-21",
      "high": "30.25",
      "iv_high": "0.25478345",
      "iv_low": "0.24967245",
      "low": "30.05",
      "open": "30.15",
      "option_symbol": "AAPL240621C00190000",
      "premium_ask_side": "3138.00",
      "premium_bid_side": "1403.92",
      "premium_mid_side": "60.50",
      "premium_no_side": "0.00",
      "start_time": "2024-05-28T14:30:00.000000Z",
      "volume_ask_side": 104,
      "volume_bid_side": 47,
      "volume_mid_side": 2,
      "volume_multi": 15,
      "volume_no_side": 0,
      "volume_stock_multi": 0
    },
    {
      "avg_price": "30.2637719298245614035",
      "close": "30.20",
      "expiry": "2024-06-21",
      "high": "30.35",
      "iv_high": "0.25408976",
      "iv_low": "0.25108545",
      "low": "30.15",
      "open": "30.22",
      "option_symbol": "AAPL240621C00190000",
      "premium_ask_side": "1058.75",
      "premium_bid_side": "661.32",
      "premium_mid_side": "0.00",
      "premium_no_side": "0.00",
      "start_time": "2024-05-28T14:31:00.000000Z",
      "volume_ask_side": 35,
      "volume_bid_side": 22,
      "volume_mid_side": 0,
      "volume_multi": 5,
      "volume_no_side": 0,
      "volume_stock_multi": 0
    }
  ]
}
```

---

#### Option Contract Volume Profile (REST)
**Endpoint:** `GET /api/option-contract/{id}/volume-profile`
**Ingestion:** Scheduled: End-of-day
**Priority:** Low

**Description:**
Returns volume distribution by price level for a specific option contract, including breakdown by order type (sweep, floor, cross, multi-leg). Use for order flow analysis and identifying support/resistance levels.

**Request:**
- Method: GET
- Path Parameter: `{id}` - Contract ID

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/option-contract/{id}/volume-profile", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "ask_vol": 850,
      "bid_vol": 325,
      "cross_vol": 5,
      "date": "2024-05-28",
      "floor_vol": 10,
      "mid_vol": 25,
      "multi_vol": 40,
      "price": "3.50",
      "sweep_vol": 120,
      "transactions": 42,
      "volume": 1250
    },
    {
      "ask_vol": 620,
      "bid_vol": 275,
      "cross_vol": 0,
      "date": "2024-05-28",
      "floor_vol": 5,
      "mid_vol": 15,
      "multi_vol": 25,
      "price": "3.55",
      "sweep_vol": 90,
      "transactions": 31,
      "volume": 950
    }
  ]
}
```

---

### Stock-Level Option Data

#### Expiry Breakdown (REST)
**Endpoint:** `GET /api/stock/{ticker}/expiry-breakdown`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns aggregated data by expiration date for a ticker, including chain count, total volume, and open interest. Use for identifying popular expirations and overall positioning.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/expiry-breakdown", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "chains": 5000,
      "expiry": "2023-09-07",
      "open_interest": 554,
      "volume": 1566232
    },
    {
      "chains": 50,
      "expiry": "2023-10-20",
      "open_interest": 0,
      "volume": 1532
    },
    {
      "chains": 20,
      "expiry": "2023-11-30",
      "open_interest": 33112,
      "volume": 931
    }
  ]
}
```

---

#### Option Contracts by Ticker (REST)
**Endpoint:** `GET /api/stock/{ticker}/option-contracts`
**Ingestion:** Scheduled: Daily
**Priority:** High

**Description:**
Returns all option contracts for a ticker with detailed metrics including volume breakdown, IV, Greeks, premium, OI changes. Supports filtering via query params. Core endpoint for screening and analysis.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol
- Query Parameters: `exclude_zero_vol_chains=true`, `exclude_zero_oi_chains=true`

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/option-contracts?exclude_zero_vol_chains=true&exclude_zero_oi_chains=true", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "ask_volume": 56916,
      "avg_price": "0.77927817593516586531",
      "bid_volume": 68967,
      "floor_volume": 1815,
      "high_price": "5.75",
      "implied_volatility": "0.542805337797143",
      "last_price": "0.01",
      "low_price": "0.01",
      "mid_volume": 6393,
      "multi_leg_volume": 9871,
      "nbbo_ask": "0.01",
      "nbbo_bid": "0",
      "no_side_volume": 6393,
      "open_interest": 22868,
      "option_symbol": "AAPL240202P00185000",
      "prev_oi": 20217,
      "stock_multi_leg_volume": 13,
      "sweep_volume": 12893,
      "total_premium": "10307980.00",
      "volume": 132276
    },
    {
      "ask_volume": 54820,
      "avg_price": "0.19195350495251190385",
      "bid_volume": 60784,
      "floor_volume": 0,
      "high_price": "0.80",
      "implied_volatility": "0.462957019859562",
      "last_price": "0.01",
      "low_price": "0.01",
      "mid_volume": 2215,
      "multi_leg_volume": 5301,
      "nbbo_ask": "0.01",
      "nbbo_bid": "0",
      "no_side_volume": 2215,
      "open_interest": 19352,
      "option_symbol": "AAPL240202C00187500",
      "prev_oi": 18135,
      "stock_multi_leg_volume": 9,
      "sweep_volume": 11152,
      "total_premium": "2261577.00",
      "volume": 117819
    }
  ]
}
```

---

#### ATM Chains (REST)
**Endpoint:** `GET /api/stock/{ticker}/atm-chains`
**Ingestion:** Scheduled: Intraday polling
**Priority:** High

**Description:**
Returns at-the-money option chains for specified expirations with comprehensive trading data, OHLC, Greeks, volume/OI metrics. Critical for monitoring active strikes near current price.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol
- Query Parameters: `expirations[]` - Array of expiration dates (URL encoded)

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/atm-chains?expirations%5B%5D=2024-02-02&expirations%5B%5D=2024-01-26", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "ask_side_volume": 119403,
      "avg_price": "1.0465802437910297887119234370",
      "bid_side_volume": 122789,
      "chain_prev_close": "1.29",
      "close": "0.03",
      "cross_volume": 0,
      "er_time": "unknown",
      "floor_volume": 142,
      "high": "2.95",
      "last_fill": "2023-09-08T17:45:32Z",
      "low": "0.02",
      "mid_volume": 22707,
      "multileg_volume": 7486,
      "next_earnings_date": "2023-10-18",
      "no_side_volume": 0,
      "open": "0.92",
      "open_interest": 18680,
      "option_symbol": "TSLA230908C00255000",
      "premium": "27723806.00",
      "sector": "Consumer Cyclical",
      "stock_multi_leg_volume": 52,
      "stock_price": "247.94",
      "sweep_volume": 18260,
      "ticker_vol": 2546773,
      "total_ask_changes": 44343,
      "total_bid_changes": 43939,
      "trades": 39690,
      "volume": 264899
    }
  ]
}
```

---

#### Flow Alerts by Ticker (REST)
**Endpoint:** `GET /api/stock/{ticker}/flow-alerts`
**Ingestion:** Scheduled: Real-time or frequent polling
**Priority:** High

**Description:**
**DEPRECATED:** This endpoint will be removed. Migrate to `/api/option-trades/flow-alerts` for more detailed responses.

---

#### Flow per Expiry (REST)
**Endpoint:** `GET /api/stock/{ticker}/flow-per-expiry`
**Ingestion:** Scheduled: Intraday
**Priority:** High

**Description:**
Returns aggregated flow metrics by expiration date, including call/put premium, volume, trades, and OTM breakdowns with bid/ask side splits. Use for identifying expiry-level sentiment and positioning.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/flow-per-expiry", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_otm_premium": "3885339",
      "call_otm_trades": 10213,
      "call_otm_volume": 81598,
      "call_premium": "5839180",
      "call_premium_ask_side": "2615356",
      "call_premium_bid_side": "2722619",
      "call_trades": 11383,
      "call_volume": 89177,
      "call_volume_ask_side": 43669,
      "call_volume_bid_side": 40164,
      "date": "2024-01-22",
      "expiry": "2024-01-26",
      "put_otm_premium": "632247",
      "put_otm_trades": 2077,
      "put_otm_volume": 12164,
      "put_premium": "4802145",
      "put_premium_ask_side": "3593584",
      "put_premium_bid_side": "690572",
      "put_trades": 2744,
      "put_volume": 20101,
      "put_volume_ask_side": 7396,
      "put_volume_bid_side": 8113,
      "ticker": "BABA"
    },
    {
      "call_otm_premium": "1264038",
      "call_otm_trades": 2550,
      "call_otm_volume": 17525,
      "call_premium": "1869073",
      "call_premium_ask_side": "885103",
      "call_premium_bid_side": "832727",
      "call_trades": 2936,
      "call_volume": 19268,
      "call_volume_ask_side": 7778,
      "call_volume_bid_side": 9875,
      "date": "2024-01-22",
      "expiry": "2024-02-02",
      "put_otm_premium": "206709",
      "put_otm_trades": 588,
      "put_otm_volume": 3581,
      "put_premium": "627117",
      "put_premium_ask_side": "191982",
      "put_premium_bid_side": "354687",
      "put_trades": 847,
      "put_volume": 4709,
      "put_volume_ask_side": 1238,
      "put_volume_bid_side": 3004,
      "ticker": "BABA"
    }
  ],
  "date": "2024-01-22"
}
```

---

#### Flow per Strike (REST)
**Endpoint:** `GET /api/stock/{ticker}/flow-per-strike`
**Ingestion:** Scheduled: Intraday
**Priority:** High

**Description:**
Returns aggregated flow metrics by strike price, including call/put premium, volume, trades with bid/ask side splits. Use for identifying key strike levels and directional positioning.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/flow-per-strike", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
[
  {
    "call_premium": "9908777.0",
    "call_premium_ask_side": "5037703.0",
    "call_premium_bid_side": "4055973.0",
    "call_trades": 6338,
    "call_volume": 40385,
    "call_volume_ask_side": 20145,
    "call_volume_bid_side": 16923,
    "date": "2024-01-22",
    "put_premium": "2746872.0",
    "put_premium_ask_side": "799873.0",
    "put_premium_bid_side": "1614848.0",
    "put_trades": 841,
    "put_volume": 4306,
    "put_volume_ask_side": 1398,
    "put_volume_bid_side": 2323,
    "strike": "70.0",
    "ticker": "BABA",
    "timestamp": "2023-09-07T09:30:00-04:00"
  },
  {
    "call_premium": "4208428.0",
    "call_premium_ask_side": "1543361.0",
    "call_premium_bid_side": "1589925.0",
    "call_trades": 2875,
    "call_volume": 28218,
    "call_volume_ask_side": 14048,
    "call_volume_bid_side": 10418,
    "date": "2024-01-22",
    "put_premium": "1996364.0",
    "put_premium_ask_side": "432005.0",
    "put_premium_bid_side": "1317894.0",
    "put_trades": 323,
    "put_volume": 2270,
    "put_volume_ask_side": 482,
    "put_volume_bid_side": 1545,
    "strike": "75.0",
    "ticker": "BABA",
    "timestamp": "2023-09-07T09:29:25-04:00"
  }
]
```

---

#### Flow per Strike Intraday (REST)
**Endpoint:** `GET /api/stock/{ticker}/flow-per-strike-intraday`
**Ingestion:** Scheduled: Real-time or frequent polling
**Priority:** High

**Description:**
Returns intraday (minute-level) aggregated flow metrics by strike price. Same data structure as Flow per Strike but with higher time resolution. Use for real-time strike-level flow monitoring.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/flow-per-strike-intraday", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
[
  {
    "call_premium": "9908777.0",
    "call_premium_ask_side": "5037703.0",
    "call_premium_bid_side": "4055973.0",
    "call_trades": 6338,
    "call_volume": 40385,
    "call_volume_ask_side": 20145,
    "call_volume_bid_side": 16923,
    "date": "2024-01-22",
    "put_premium": "2746872.0",
    "put_premium_ask_side": "799873.0",
    "put_premium_bid_side": "1614848.0",
    "put_trades": 841,
    "put_volume": 4306,
    "put_volume_ask_side": 1398,
    "put_volume_bid_side": 2323,
    "strike": "70.0",
    "ticker": "BABA",
    "timestamp": "2023-09-07T09:30:00-04:00"
  },
  {
    "call_premium": "4208428.0",
    "call_premium_ask_side": "1543361.0",
    "call_premium_bid_side": "1589925.0",
    "call_trades": 2875,
    "call_volume": 28218,
    "call_volume_ask_side": 14048,
    "call_volume_bid_side": 10418,
    "date": "2024-01-22",
    "put_premium": "1996364.0",
    "put_premium_ask_side": "432005.0",
    "put_premium_bid_side": "1317894.0",
    "put_trades": 323,
    "put_volume": 2270,
    "put_volume_ask_side": 482,
    "put_volume_bid_side": 1545,
    "strike": "75.0",
    "ticker": "BABA",
    "timestamp": "2023-09-07T09:29:25-04:00"
  }
]
```

---

#### Recent Flow (REST)
**Endpoint:** `GET /api/stock/{ticker}/flow-recent`
**Ingestion:** Scheduled: Real-time or frequent polling
**Priority:** High

**Description:**
Returns recent flow activity for a ticker, aggregated by expiry with call/put premium, volume, trades, and OTM breakdowns. Use for real-time sentiment monitoring.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/flow-recent", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_otm_premium": "3885339",
      "call_otm_trades": 10213,
      "call_otm_volume": 81598,
      "call_premium": "5839180",
      "call_premium_ask_side": "2615356",
      "call_premium_bid_side": "2722619",
      "call_trades": 11383,
      "call_volume": 89177,
      "call_volume_ask_side": 43669,
      "call_volume_bid_side": 40164,
      "date": "2024-01-22",
      "expiry": "2024-01-26",
      "put_otm_premium": "632247",
      "put_otm_trades": 2077,
      "put_otm_volume": 12164,
      "put_premium": "4802145",
      "put_premium_ask_side": "3593584",
      "put_premium_bid_side": "690572",
      "put_trades": 2744,
      "put_volume": 20101,
      "put_volume_ask_side": 7396,
      "put_volume_bid_side": 8113,
      "ticker": "BABA"
    },
    {
      "call_otm_premium": "1264038",
      "call_otm_trades": 2550,
      "call_otm_volume": 17525,
      "call_premium": "1869073",
      "call_premium_ask_side": "885103",
      "call_premium_bid_side": "832727",
      "call_trades": 2936,
      "call_volume": 19268,
      "call_volume_ask_side": 7778,
      "call_volume_bid_side": 9875,
      "date": "2024-01-22",
      "expiry": "2024-02-02",
      "put_otm_premium": "206709",
      "put_otm_trades": 588,
      "put_otm_volume": 3581,
      "put_premium": "627117",
      "put_premium_ask_side": "191982",
      "put_premium_bid_side": "354687",
      "put_trades": 847,
      "put_volume": 4709,
      "put_volume_ask_side": 1238,
      "put_volume_bid_side": 3004,
      "ticker": "BABA"
    }
  ],
  "date": "2024-01-22"
}
```

---

#### Option Chains (REST)
**Endpoint:** `GET /api/stock/{ticker}/option-chains`
**Ingestion:** Scheduled: Daily
**Priority:** Low

**Description:**
Returns a simple list of all available option chain symbols for a ticker. Use for discovery and building chain lists for further queries.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/option-chains", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    "AAPL230908C00175000",
    "AAPL231020C00185000",
    "AAPL230908C00180000",
    "AAPL230908C00182500",
    "AAPL230908C00185000",
    "AAPL230908C00187500",
    "AAPL230908P00172500",
    "AAPL230908P00175000",
    "AAPL230908P00177500",
    "AAPL230908C00177500",
    "AAPL230915C00177500",
    "AAPL230915C00180000",
    "AAPL230915C00185000",
    "AAPL230915C00187500",
    "AAPL230915C00192500",
    "AAPL230915C00195000",
    "AAPL230915C00200000"
  ]
}
```

---

#### Option Price Levels (REST)
**Endpoint:** `GET /api/stock/{ticker}/option/stock-price-levels`
**Ingestion:** Scheduled: Intraday
**Priority:** Medium

**Description:**
Returns option volume aggregated by underlying stock price level, showing call/put volume at each price. Use for visualizing volume distribution and identifying price magnets.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/option/stock-price-levels", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_volume": 22074116,
      "price": "120.12",
      "put_volume": 19941285
    },
    {
      "call_volume": 220741,
      "price": "123.12",
      "put_volume": 199415
    }
  ]
}
```

---

#### Volume & OI per Expiry (REST)
**Endpoint:** `GET /api/stock/{ticker}/option/volume-oi-expiry`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns total volume and open interest aggregated by expiration date. Use for quick overview of activity concentration across the term structure.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/option/volume-oi-expiry", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "expires": "2023-09-08",
      "oi": 451630,
      "volume": 962332
    },
    {
      "expires": "2023-09-15",
      "oi": 1422982,
      "volume": 631608
    },
    {
      "expires": "2023-09-22",
      "oi": 144938,
      "volume": 111177
    },
    {
      "expires": "2023-09-29",
      "oi": 144629,
      "volume": 78604
    },
    {
      "expires": "2023-10-06",
      "oi": 38090,
      "volume": 42405
    },
    {
      "expires": "2023-10-13",
      "oi": 14371,
      "volume": 18694
    },
    {
      "expires": "2023-10-20",
      "oi": 837270,
      "volume": 244837
    },
    {
      "expires": "2023-10-27",
      "oi": 0,
      "volume": 6004
    },
    {
      "expires": "2023-11-17",
      "oi": 524204,
      "volume": 62599
    },
    {
      "expires": "2023-12-15",
      "oi": 723533,
      "volume": 72616
    },
    {
      "expires": "2024-01-19",
      "oi": 1658337,
      "volume": 98483
    },
    {
      "expires": "2024-02-16",
      "oi": 34994,
      "volume": 8947
    },
    {
      "expires": "2024-03-15",
      "oi": 304973,
      "volume": 22281
    },
    {
      "expires": "2024-04-19",
      "oi": 21399,
      "volume": 5905
    },
    {
      "expires": "2024-06-21",
      "oi": 560682,
      "volume": 23783
    },
    {
      "expires": "2024-09-20",
      "oi": 122030,
      "volume": 17994
    },
    {
      "expires": "2024-12-20",
      "oi": 63646,
      "volume": 5170
    },
    {
      "expires": "2025-01-17",
      "oi": 472809,
      "volume": 9144
    },
    {
      "expires": "2025-06-20",
      "oi": 89229,
      "volume": 3194
    },
    {
      "expires": "2025-12-19",
      "oi": 116365,
      "volume": 5856
    }
  ]
}
```

---

#### Options Volume (REST)
**Endpoint:** `GET /api/stock/{ticker}/options-volume`
**Ingestion:** Scheduled: Daily
**Priority:** High

**Description:**
Returns comprehensive daily options volume summary including call/put volume, premium, OI, bid/ask side splits, net premium, and moving averages (3/7/30 day). Core endpoint for volume analysis.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/options-volume", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "avg_30_day_call_volume": "658450.333333333333",
      "avg_30_day_put_volume": "481505.300000000000",
      "avg_3_day_call_volume": "949763.000000000000",
      "avg_3_day_put_volume": "756387.333333333333",
      "avg_7_day_call_volume": "878336.000000000000",
      "avg_7_day_put_volume": "580650.857142857143",
      "bearish_premium": "138449839",
      "bullish_premium": "152015294",
      "call_open_interest": 4358631,
      "call_premium": "208699280",
      "call_volume": 1071546,
      "call_volume_ask_side": 486985,
      "call_volume_bid_side": 514793,
      "date": "2023-09-08",
      "net_call_premium": "122015294",
      "net_put_premium": "108449839",
      "put_open_interest": 3771656,
      "put_premium": "125472872",
      "put_volume": 666386,
      "put_volume_ask_side": 298282,
      "put_volume_bid_side": 318834
    }
  ]
}
```

---

### Greek Exposure

#### Greek Exposure (REST)
**Endpoint:** `GET /api/stock/{ticker}/greek-exposure`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns historical daily Greek exposure totals (delta, gamma, vanna, charm) split by call/put. Use for understanding aggregate positioning and hedging dynamics over time.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/greek-exposure", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_charm": "102382359.5786",
      "call_delta": "227549667.4651",
      "call_gamma": "9356683.4241",
      "call_vanna": "152099632406.9564",
      "date": "2023-09-08",
      "put_charm": "-943028472.4815",
      "put_delta": "-191893077.7193",
      "put_gamma": "-12337386.0524",
      "put_vanna": "488921784213.1121"
    },
    {
      "call_charm": "81465130.0002",
      "call_delta": "210202465.3421",
      "call_gamma": "8456599.8505",
      "call_vanna": "161231587973.6811",
      "date": "2023-09-07",
      "put_charm": "-1054548432.6111",
      "put_delta": "-210881557.3003",
      "put_gamma": "-12703877.0243",
      "put_vanna": "488921784213.1121"
    }
  ]
}
```

---

#### Greek Exposure by Expiry (REST)
**Endpoint:** `GET /api/stock/{ticker}/greek-exposure/expiry`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns Greek exposure broken down by expiration date with days-to-expiry (DTE). Use for understanding positioning concentration across the term structure.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/greek-exposure/expiry", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_charm": "102382359.5786",
      "call_delta": "227549667.4651",
      "call_gamma": "9356683.4241",
      "call_vanna": "152099632406.9564",
      "date": "2022-05-20",
      "dte": 5,
      "expiry": "2022-05-25",
      "put_charm": "-943028472.4815",
      "put_delta": "-191893077.7193",
      "put_gamma": "-12337386.0524",
      "put_vanna": "488921784213.1121"
    },
    {
      "call_charm": "81465130.0002",
      "call_delta": "210202465.3421",
      "call_gamma": "8456599.8505",
      "call_vanna": "161231587973.6811",
      "date": "2022-05-20",
      "dte": 5,
      "expiry": "2022-05-25",
      "put_charm": "-1054548432.6111",
      "put_delta": "-210881557.3003",
      "put_gamma": "-12703877.0243",
      "put_vanna": "488921784213.1121"
    }
  ]
}
```

---

#### Greek Exposure by Strike (REST)
**Endpoint:** `GET /api/stock/{ticker}/greek-exposure/strike`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns Greek exposure aggregated by strike price. Use for identifying key strikes with largest Greek exposure and potential hedging levels.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/greek-exposure/strike", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_charm": "102382359.5786",
      "call_delta": "227549667.4651",
      "call_gamma": "9356683.4241",
      "call_vanna": "152099632406.9564",
      "put_charm": "-943028472.4815",
      "put_delta": "-191893077.7193",
      "put_gamma": "-12337386.0524",
      "put_vanna": "488921784213.1121",
      "strike": "150"
    },
    {
      "call_charm": "81465130.0002",
      "call_delta": "210202465.3421",
      "call_gamma": "8456599.8505",
      "call_vanna": "161231587973.6811",
      "put_charm": "-1054548432.6111",
      "put_delta": "-210881557.3003",
      "put_gamma": "-12703877.0243",
      "put_vanna": "488921784213.1121",
      "strike": "152.5"
    }
  ]
}
```

---

#### Greek Flow (REST)
**Endpoint:** `GET /api/stock/{ticker}/greek-flow`
**Ingestion:** Scheduled: Intraday
**Priority:** High

**Description:**
Returns minute-level Greek flow (delta and vega) showing directional and total flow, including OTM breakdowns. Critical for real-time hedging flow analysis and market maker positioning.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/greek-flow", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "dir_delta_flow": "-43593.96",
      "dir_vega_flow": "31243.04",
      "otm_dir_delta_flow": "14947.51",
      "otm_dir_vega_flow": "11421.03",
      "otm_total_delta_flow": "-28564.02",
      "otm_total_vega_flow": "101745.64",
      "ticker": "SPY",
      "timestamp": "2024-10-28T18:46:00Z",
      "total_delta_flow": "-21257.36",
      "total_vega_flow": "350944.58",
      "transactions": 1188,
      "volume": 12348
    }
  ]
}
```

---

#### Greeks by Strike/Expiry (REST)
**Endpoint:** `GET /api/stock/{ticker}/greeks`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns full Greek surface (delta, gamma, theta, vega, rho, charm, vanna) for all strikes and expirations, including IV for both calls and puts. Use for options pricing models and surface analysis.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/greeks", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_charm": "9.32",
      "call_delta": "0.5",
      "call_gamma": "0.0051",
      "call_option_symbol": "SPY240105C00480000",
      "call_rho": "0.0321",
      "call_theta": "-0.62",
      "call_vanna": "-0.91",
      "call_vega": "0.15",
      "call_volatility": "0.3",
      "date": "2024-01-01",
      "expiry": "2024-01-05",
      "put_charm": "9.32",
      "put_delta": "-0.51",
      "put_gamma": "0.005",
      "put_option_symbol": "SPY240105P00480000",
      "put_rho": "-0.022",
      "put_theta": "-0.62",
      "put_vanna": "-0.91",
      "put_vega": "0.15",
      "put_volatility": "0.29",
      "strike": "480.0"
    },
    {
      "call_charm": "9.32",
      "call_delta": "0.45",
      "call_gamma": "0.003",
      "call_option_symbol": "SPY240105C00490000",
      "call_rho": "0.0321",
      "call_theta": "-0.62",
      "call_vanna": "-0.91",
      "call_vega": "0.15",
      "call_volatility": "0.33",
      "date": "2024-01-01",
      "expiry": "2024-01-05",
      "put_charm": "9.32",
      "put_delta": "-0.55",
      "put_gamma": "0.007",
      "put_option_symbol": "SPY240105P00490000",
      "put_rho": "-0.022",
      "put_theta": "-0.62",
      "put_vanna": "-0.91",
      "put_vega": "0.15",
      "put_volatility": "0.32",
      "strike": "490.0"
    }
  ]
}
```

---

### GEX (Spot Exposures)

#### Spot GEX Exposures (1min) (REST)
**Endpoint:** `GET /api/stock/{ticker}/spot-exposures`
**Ingestion:** Scheduled: Real-time or frequent polling
**Priority:** High

**Description:**
Returns minute-by-minute gamma, charm, and vanna exposure per 1% move, split by OI, volume, and directional flow. Critical for understanding market maker hedging pressure and potential price pinning.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/spot-exposures", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "charm_per_one_percent_move_dir": "654769081.21",
      "charm_per_one_percent_move_oi": "5124108502049.17",
      "charm_per_one_percent_move_vol": "320909908341.10",
      "gamma_per_one_percent_move_dir": "475681.21",
      "gamma_per_one_percent_move_oi": "65476967081.41",
      "gamma_per_one_percent_move_vol": "12921519098.30",
      "price": "4650",
      "time": "2023-12-13T05:00:41.481000Z",
      "vanna_per_one_percent_move_dir": "-342349081.21",
      "vanna_per_one_percent_move_oi": "-54622844772.90",
      "vanna_per_one_percent_move_vol": "-5559678859.12"
    },
    {
      "charm_per_one_percent_move_dir": "654769081.21",
      "charm_per_one_percent_move_oi": "4736293042981.03",
      "charm_per_one_percent_move_vol": "308180334258.50",
      "gamma_per_one_percent_move_dir": "475681.21",
      "gamma_per_one_percent_move_oi": "64220497598.15",
      "gamma_per_one_percent_move_vol": "11924696599.44",
      "price": "4650",
      "time": "2023-12-13T11:29:41.501000Z",
      "vanna_per_one_percent_move_dir": "-342349081.21",
      "vanna_per_one_percent_move_oi": "-52107741026.80",
      "vanna_per_one_percent_move_vol": "-5043673317.55"
    }
  ]
}
```

---

#### Spot GEX Exposures by Strike & Expiry (REST)
**Endpoint:** `GET /api/stock/{ticker}/spot-exposures/expiry-strike`
**Ingestion:** Scheduled: Intraday
**Priority:** Medium

**Description:**
Returns granular GEX exposure breakdown by strike and expiration, split by OI/volume and bid/ask side for delta, gamma, vanna, and charm. Use for strike-level hedging flow analysis.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol
- Query Parameters: `expirations[]` - Array of expiration dates (URL encoded)

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/spot-exposures/expiry-strike?expirations%5B%5D=2024-02-02&expirations%5B%5D=2024-01-26", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_charm_ask": "2582359253.61",
      "call_charm_bid": "5820636.43",
      "call_charm_oi": "70827151575067.12",
      "call_charm_vol": "70827151575067.12",
      "call_delta_ask": "23452351.20",
      "call_delta_bid": "30499234235.52",
      "call_delta_oi": "227549667.4651",
      "call_delta_vol": "227549667.4651",
      "call_gamma_ask": "23452351.20",
      "call_gamma_bid": "30499234235.52",
      "call_gamma_oi": "5124108502049.17",
      "call_gamma_vol": "5124108502049.17",
      "call_vanna_ask": "22692351.20",
      "call_vanna_bid": "234235.52",
      "call_vanna_oi": "65476967081.41",
      "call_vanna_vol": "65476967081.41",
      "price": "4650",
      "put_charm_ask": "96836366.22",
      "put_charm_bid": "6100352354.34",
      "put_charm_oi": "2282895170748.09",
      "put_charm_vol": "2282895170748.09",
      "put_delta_ask": "9528523023.39",
      "put_delta_bid": "9342852354.34",
      "put_delta_oi": "-191893077.7193",
      "put_delta_vol": "-191893077.7193",
      "put_gamma_ask": "9528523023.39",
      "put_gamma_bid": "9342852354.34",
      "put_gamma_oi": "320909908341.10",
      "put_gamma_vol": "320909908341.10",
      "put_vanna_ask": "495803.39",
      "put_vanna_bid": "26934630.34",
      "put_vanna_oi": "12921519098.30",
      "put_vanna_vol": "12921519098.30",
      "time": "2023-12-13T05:00:41.481000Z"
    }
  ]
}
```

---

#### Spot GEX Exposures by Strike (REST)
**Endpoint:** `GET /api/stock/{ticker}/spot-exposures/strike`
**Ingestion:** Scheduled: Intraday
**Priority:** High

**Description:**
Returns GEX exposure aggregated by strike price (across all expirations), split by OI/volume and bid/ask side. Use for identifying key gamma levels and dealer hedging zones.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/spot-exposures/strike", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_charm_ask": "2582359253.61",
      "call_charm_bid": "5820636.43",
      "call_charm_oi": "70827151575067.12",
      "call_charm_vol": "70827151575067.12",
      "call_delta_ask": "23452351.20",
      "call_delta_bid": "30499234235.52",
      "call_delta_oi": "227549667.4651",
      "call_delta_vol": "227549667.4651",
      "call_gamma_ask": "23452351.20",
      "call_gamma_bid": "30499234235.52",
      "call_gamma_oi": "5124108502049.17",
      "call_gamma_vol": "5124108502049.17",
      "call_vanna_ask": "22692351.20",
      "call_vanna_bid": "234235.52",
      "call_vanna_oi": "65476967081.41",
      "call_vanna_vol": "65476967081.41",
      "price": "4650",
      "put_charm_ask": "96836366.22",
      "put_charm_bid": "6100352354.34",
      "put_charm_oi": "2282895170748.09",
      "put_charm_vol": "2282895170748.09",
      "put_delta_ask": "9528523023.39",
      "put_delta_bid": "9342852354.34",
      "put_delta_oi": "-191893077.7193",
      "put_delta_vol": "-191893077.7193",
      "put_gamma_ask": "9528523023.39",
      "put_gamma_bid": "9342852354.34",
      "put_gamma_oi": "320909908341.10",
      "put_gamma_vol": "320909908341.10",
      "put_vanna_ask": "495803.39",
      "put_vanna_bid": "26934630.34",
      "put_vanna_oi": "12921519098.30",
      "put_vanna_vol": "12921519098.30",
      "time": "2023-12-13T05:00:41.481000Z"
    }
  ]
}
```

---

### Order Flow Metrics

#### Max Pain (REST)
**Endpoint:** `GET /api/stock/{ticker}/max-pain`
**Ingestion:** Scheduled: Daily
**Priority:** Low

**Description:**
Returns max pain strike for each expiration (price where option holders lose most value). Use for identifying potential price targets based on dealer positioning.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/max-pain", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "expiry": "2024-03-04",
      "max_pain": "473"
    },
    {
      "expiry": "2024-03-05",
      "max_pain": "475"
    }
  ],
  "date": "2024-03-04"
}
```

---

#### Net Premium Ticks (REST)
**Endpoint:** `GET /api/stock/{ticker}/net-prem-ticks`
**Ingestion:** Scheduled: Intraday
**Priority:** High

**Description:**
Returns minute-level net call/put premium, volume, and net delta with bid/ask side splits. Use for tracking real-time sentiment shifts and directional flow.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/net-prem-ticks", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_volume": 1145,
      "call_volume_ask_side": 822,
      "call_volume_bid_side": 182,
      "date": "2025-03-21",
      "net_call_premium": "2234.00",
      "net_call_volume": 640,
      "net_delta": "26294.85817964231814400",
      "net_put_premium": "-11106.00",
      "net_put_volume": -137,
      "put_volume": 241,
      "put_volume_ask_side": 49,
      "put_volume_bid_side": 186,
      "tape_time": "2025-03-21T19:58:00.000000Z"
    },
    {
      "call_volume": 1255,
      "call_volume_ask_side": 912,
      "call_volume_bid_side": 192,
      "date": "2025-03-21",
      "net_call_premium": "3234.00",
      "net_call_volume": 720,
      "net_delta": "28294.85817964231814400",
      "net_put_premium": "-9106.00",
      "net_put_volume": -127,
      "put_volume": 231,
      "put_volume_ask_side": 59,
      "put_volume_bid_side": 166,
      "tape_time": "2025-03-21T19:59:00.000000Z"
    }
  ]
}
```

---

#### NOPE (REST)
**Endpoint:** `GET /api/stock/{ticker}/nope`
**Ingestion:** Scheduled: Intraday
**Priority:** Medium

**Description:**
Returns Net Options Pricing Effect (NOPE) metric - ratio of option delta flow to stock volume. Use for detecting option-driven stock movements and hedging imbalances.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/nope", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_delta": "-21257.36",
      "call_fill_delta": "-28564.02",
      "call_vol": 23421,
      "nope": "-0.000648",
      "nope_fill": "-0.000434",
      "put_delta": "-43593.96",
      "put_fill_delta": "-14947.51",
      "put_vol": 23421,
      "stock_vol": 100000,
      "timestamp": "2024-10-28T18:46:00Z"
    }
  ]
}
```

---

#### OI Change (REST)
**Endpoint:** `GET /api/stock/{ticker}/oi-change`
**Ingestion:** Scheduled: Daily
**Priority:** High

**Description:**
Returns daily open interest changes by contract with ranking, percentage change, previous volume/premium breakdown. Critical for identifying new positioning and big money flows.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/oi-change", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "avg_price": "30.0543738131838322",
      "curr_date": "2024-01-09",
      "curr_oi": 35207,
      "last_ask": "34.00",
      "last_bid": "32.90",
      "last_date": "2024-01-08",
      "last_fill": "33.50",
      "last_oi": 2119,
      "oi_change": "15.6149126946672959",
      "oi_diff_plain": 33088,
      "option_symbol": "MSFT240315C00350000",
      "percentage_of_total": "0.08879378869021333312",
      "prev_ask_volume": 32861,
      "prev_bid_volume": 235,
      "prev_mid_volume": 81,
      "prev_multi_leg_volume": 32762,
      "prev_neutral_volume": 81,
      "prev_stock_multi_leg_volume": 0,
      "prev_total_premium": "99711396.00",
      "rnk": 74,
      "trades": 187,
      "underlying_symbol": "MSFT",
      "volume": 33177
    },
    {
      "avg_price": "0.16762696308382622884",
      "curr_date": "2024-01-09",
      "curr_oi": 33253,
      "last_ask": "0.23",
      "last_bid": "0.20",
      "last_date": "2024-01-08",
      "last_fill": "0.22",
      "last_oi": 27361,
      "oi_change": "0.21534300646906180330",
      "oi_diff_plain": 5892,
      "option_symbol": "MSFT240119C00400000",
      "percentage_of_total": "0.02624444319547373013",
      "prev_ask_volume": 8915,
      "prev_bid_volume": 860,
      "prev_mid_volume": 31,
      "prev_multi_leg_volume": 214,
      "prev_neutral_volume": 31,
      "prev_stock_multi_leg_volume": 0,
      "prev_total_premium": "164375.00",
      "rnk": 1638,
      "trades": 602,
      "underlying_symbol": "MSFT",
      "volume": 9806
    }
  ]
}
```

---

#### OI per Expiry (REST)
**Endpoint:** `GET /api/stock/{ticker}/oi-per-expiry`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns call/put open interest totals by expiration date. Use for quick overview of positioning concentration across term structure.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/oi-per-expiry", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_oi": 1123,
      "date": "2024-12-02",
      "expiry": "2024-12-06",
      "put_oi": 24443
    }
  ]
}
```

---

#### OI per Strike (REST)
**Endpoint:** `GET /api/stock/{ticker}/oi-per-strike`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns call/put open interest totals by strike price. Use for identifying key strikes with largest positioning and potential support/resistance.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/oi-per-strike", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "call_oi": 1123,
      "date": "2024-12-02",
      "put_oi": 24443,
      "strike": "420"
    }
  ]
}
```

---

### Volatility & IV Analysis

#### Historical Risk Reversal Skew (REST)
**Endpoint:** `GET /api/stock/{ticker}/historical-risk-reversal-skew`
**Ingestion:** Scheduled: Daily
**Priority:** Low

**Description:**
Returns historical risk reversal skew (difference between call and put IV at same delta) by date. Use for analyzing market sentiment and tail risk pricing over time.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/historical-risk-reversal-skew", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "date": "2024-01-01",
      "delta": 10,
      "risk_reversal": "0.014",
      "ticker": "SPY"
    },
    {
      "date": "2024-01-02",
      "delta": 10,
      "risk_reversal": "0.009",
      "ticker": "SPY"
    }
  ]
}
```

---

#### Interpolated IV (REST)
**Endpoint:** `GET /api/stock/{ticker}/interpolated-iv`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns interpolated IV at standard tenors (1/5/7/14/30 days) with implied move and historical percentile. Use for term structure analysis and identifying relative value.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/interpolated-iv", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "date": "2025-05-30",
      "days": 1,
      "implied_move_perc": "0.003",
      "percentile": "100",
      "volatility": "1.739"
    },
    {
      "date": "2025-05-30",
      "days": 5,
      "implied_move_perc": "0.02",
      "percentile": "94.737",
      "volatility": "0.696"
    },
    {
      "date": "2025-05-30",
      "days": 7,
      "implied_move_perc": "0.026",
      "percentile": "52.632",
      "volatility": "0.278"
    },
    {
      "date": "2025-05-30",
      "days": 14,
      "implied_move_perc": "0.041",
      "percentile": "68.421",
      "volatility": "0.311"
    },
    {
      "date": "2025-05-30",
      "days": 30,
      "implied_move_perc": "0.058",
      "percentile": "77.193",
      "volatility": "0.299"
    }
  ]
}
```

---

#### IV Rank (REST)
**Endpoint:** `GET /api/stock/{ticker}/iv-rank`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns historical daily IV rank (percentile of current IV vs 1-year range) with close price and volatility. Use for identifying high/low IV environments for options strategies.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/iv-rank", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "close": "180.50",
      "date": "2024-01-22",
      "iv_rank_1y": "0.65",
      "updated_at": "2024-01-22T16:35:52.168490Z",
      "volatility": "0.25"
    },
    {
      "close": "181.25",
      "date": "2024-01-23",
      "iv_rank_1y": "0.72",
      "updated_at": "2024-01-23T16:35:52.168490Z",
      "volatility": "0.28"
    }
  ]
}
```

---

#### Realized Volatility (REST)
**Endpoint:** `GET /api/stock/{ticker}/volatility/realized`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns historical realized volatility (backward-looking) vs implied volatility with price. Use for comparing IV vs RV and identifying over/underpricing of options.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/volatility/realized", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "date": "2023-04-11",
      "implied_volatility": "0.23",
      "price": "150.15",
      "realized_volatility": "0.19",
      "unshifted_rv_date": "2024-05-02"
    },
    {
      "date": "2023-04-12",
      "implied_volatility": "0.22",
      "price": "148.29",
      "realized_volatility": "0.20",
      "unshifted_rv_date": "2024-05-03"
    }
  ]
}
```

---

#### Volatility Statistics (REST)
**Endpoint:** `GET /api/stock/{ticker}/volatility/stats`
**Ingestion:** Scheduled: Daily
**Priority:** Medium

**Description:**
Returns current volatility statistics including IV, RV, IV rank, and their 1-year high/low ranges. Use for quick volatility environment assessment.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/volatility/stats", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": {
    "date": "2024-01-22",
    "iv": "0.23",
    "iv_high": "0.35",
    "iv_low": "0.18",
    "iv_rank": "0.45",
    "rv": "0.21",
    "rv_high": "0.34",
    "rv_low": "0.16",
    "ticker": "AAPL"
  }
}
```

---

#### Implied Volatility Term Structure (REST)
**Endpoint:** `GET /api/stock/{ticker}/volatility/term-structure`
**Ingestion:** Scheduled: Daily
**Priority:** High

**Description:**
Returns IV term structure by expiration with DTE, implied move ($ and %), and volatility. Critical for understanding forward volatility expectations and identifying calendar spreads.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/volatility/term-structure", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "date": "2023-09-08",
      "dte": 0,
      "expiry": "2023-09-08",
      "implied_move": "3.1025",
      "implied_move_perc": "0.01765",
      "volatility": "0.2319"
    },
    {
      "date": "2023-09-08",
      "dte": 7,
      "expiry": "2023-09-15",
      "implied_move": "4.923",
      "implied_move_perc": "0.02747",
      "volatility": "0.2352"
    }
  ]
}
```

---

### Market Microstructure

#### Stock State (REST)
**Endpoint:** `GET /api/stock/{ticker}/stock-state`
**Ingestion:** Scheduled: Real-time or frequent polling
**Priority:** High

**Description:**
Returns current stock state snapshot including OHLC, volume, prev close, market time (market/premarket/postmarket), and tape timestamp. Use for real-time price monitoring.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/stock-state", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": {
    "close": "56.79",
    "high": "56.79",
    "low": "56.79",
    "market_time": "postmarket",
    "open": "56.79",
    "prev_close": "55.69",
    "tape_time": "2023-09-07T20:11:00Z",
    "total_volume": 13774488,
    "volume": 500000
  }
}
```

---

#### OHLC (REST)
**Endpoint:** `GET /api/stock/{ticker}/ohlc/{candle_size}`
**Ingestion:** Scheduled: Based on candle size
**Priority:** Medium

**Description:**
Returns OHLC candle data at specified intervals with volume breakdown and market time indicator. Use for charting and historical price analysis.

**Request:**
- Method: GET
- Path Parameters: `{ticker}` - Stock ticker symbol, `{candle_size}` - Candle interval

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/ohlc/1m", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "close": "56.79",
      "end_time": "2023-09-07T20:11:00Z",
      "high": "56.79",
      "low": "56.79",
      "market_time": "po",
      "open": "56.79",
      "start_time": "2023-09-07T20:10:00Z",
      "total_volume": 13774488,
      "volume": 29812
    },
    {
      "close": "56.79",
      "end_time": "2023-09-07T20:07:00Z",
      "high": "56.79",
      "low": "56.79",
      "market_time": "po",
      "open": "56.79",
      "start_time": "2023-09-07T20:06:00Z",
      "total_volume": 13744676,
      "volume": 10699
    }
  ]
}
```

---

#### Off/Lit Volume Price Levels (REST)
**Endpoint:** `GET /api/stock/{ticker}/stock-volume-price-levels`
**Ingestion:** Scheduled: Daily
**Priority:** Low

**Description:**
Returns lit (exchange) vs off-lit (dark pool) volume by price level. **Important:** Volume represents only Nasdaq and FINRA exchanges, not full market volume. Use for analyzing execution venue preferences.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/stock-volume-price-levels", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "lit_vol": 19941285,
      "off_vol": 22074116,
      "price": "120.12"
    },
    {
      "lit_vol": 199415,
      "off_vol": 220741,
      "price": "123.12"
    }
  ]
}
```

---

### Screening & Analytics

#### Flow Alerts (Global) (REST)
**Endpoint:** `GET /api/option-trades/flow-alerts`
**Ingestion:** Scheduled: Real-time or frequent polling
**Priority:** High

**Description:**
Returns global flow alerts (unusual options activity) triggered by proprietary rules, including alert type, premium, volume, OI ratio, sweep/multileg flags. Primary endpoint for identifying smart money flows.

**Request:**
- Method: GET

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/option-trades/flow-alerts", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "alert_rule": "RepeatedHits",
      "all_opening_trades": false,
      "created_at": "2023-12-12T16:35:52.168490Z",
      "expiry": "2023-12-22",
      "expiry_count": 1,
      "has_floor": false,
      "has_multileg": false,
      "has_singleleg": true,
      "has_sweep": true,
      "open_interest": 7913,
      "option_chain": "MSFT231222C00375000",
      "price": "4.05",
      "strike": "375",
      "ticker": "MSFT",
      "total_ask_side_prem": "151875",
      "total_bid_side_prem": "405",
      "total_premium": "186705",
      "total_size": 461,
      "trade_count": 32,
      "type": "call",
      "underlying_price": "372.99",
      "volume": 2442,
      "volume_oi_ratio": "0.30860609124226"
    }
  ]
}
```

---

#### Analyst Ratings (REST)
**Endpoint:** `GET /api/screener/analysts`
**Ingestion:** Scheduled: Daily
**Priority:** Low

**Description:**
Returns analyst rating changes with analyst name, firm, action (maintained/upgraded/downgraded), recommendation, target price. Supports filtering by ticker.

**Request:**
- Method: GET
- Query Parameters: `ticker` - Stock ticker symbol (optional)

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/screener/analysts?ticker=AAPL", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "action": "maintained",
      "analyst_name": "Tyler Radke",
      "firm": "Citi",
      "recommendation": "buy",
      "sector": "Technology",
      "target": "420.0",
      "ticker": "MSFT",
      "timestamp": "2023-09-11T11:21:12Z"
    },
    {
      "action": "maintained",
      "analyst_name": "Mark Rothschild",
      "firm": "Canaccord Genuity",
      "recommendation": "hold",
      "sector": "Conglomerates",
      "target": "11.75",
      "ticker": "DRETF",
      "timestamp": "2023-09-11T11:11:32Z"
    }
  ]
}
```

---

#### Hottest Chains (REST)
**Endpoint:** `GET /api/screener/option-contracts`
**Ingestion:** Scheduled: Intraday
**Priority:** High

**Description:**
Returns top option contracts by activity across all tickers, with comprehensive metrics (volume, premium, OI, Greeks, bid/ask changes, trades). Use for discovering hot contracts and market-wide trends.

**Request:**
- Method: GET

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/screener/option-contracts", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "ask_side_volume": 119403,
      "avg_price": "1.0465802437910297887119234370",
      "bid_side_volume": 122789,
      "chain_prev_close": "1.29",
      "close": "0.03",
      "cross_volume": 0,
      "er_time": "unknown",
      "floor_volume": 142,
      "high": "2.95",
      "last_fill": "2023-09-08T17:45:32Z",
      "low": "0.02",
      "mid_volume": 22707,
      "multileg_volume": 7486,
      "next_earnings_date": "2023-10-18",
      "no_side_volume": 0,
      "open": "0.92",
      "open_interest": 18680,
      "option_symbol": "TSLA230908C00255000",
      "premium": "27723806.00",
      "sector": "Consumer Cyclical",
      "stock_multi_leg_volume": 52,
      "stock_price": "247.94",
      "sweep_volume": 18260,
      "ticker_vol": 2546773,
      "total_ask_changes": 44343,
      "total_bid_changes": 43939,
      "trades": 39690,
      "volume": 264899
    }
  ]
}
```

---

### Insider/Corporate

#### Insider Buy/Sells (REST)
**Endpoint:** `GET /api/stock/{ticker}/insider-buy-sells`
**Ingestion:** Scheduled: Daily
**Priority:** Low

**Description:**
Returns daily insider transaction summary with purchase/sell counts and notional values by filing date. Use for tracking insider sentiment and large position changes.

**Request:**
- Method: GET
- Path Parameter: `{ticker}` - Stock ticker symbol

```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")

headers = {
    'Accept': "application/json, text/plain",
    'Authorization': "Bearer 880aa3a5-75fb-4489-b7a2-3e0a0212e7bd"
}

conn.request("GET", "/api/stock/SPY/insider-buy-sells", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
```

**Response Schema:**
```json
{
  "data": [
    {
      "filing_date": "2023-12-13",
      "purchases": 12,
      "purchases_notional": "14317122.490",
      "sells": 10,
      "sells_notional": "-1291692.4942"
    },
    {
      "filing_date": "2023-12-12",
      "purchases": 78,
      "purchases_notional": "46598915.1911",
      "sells": 211,
      "sells_notional": "-182466466.7165"
    },
    {
      "filing_date": "2023-12-11",
      "purchases": 96,
      "purchases_notional": "431722108.8184",
      "sells": 210,
      "sells_notional": "-1058043617.3548"
    }
  ]
}
```

---

## WebSocket Channels

### WebSocket Connection Guide

**Base URI:** `wss://api.unusualwhales.com/socket?token=<YOUR_API_TOKEN>`

**Connection Requirements:**
- WebSocket access for personal use requires Advanced plan
- Full examples available at: https://github.com/unusual-whales/api-examples/tree/main/examples/ws-multi-channel-multi-output

**Connecting:**
```bash
websocat "wss://api.unusualwhales.com/socket?token=<YOUR_API_TOKEN>"
```

**Joining a channel:**
```json
{"channel":"channel_name","msg_type":"join"}
```

**Server confirmation:**
```json
["channel_name",{"response":{},"status":"ok"}]
```

**Data format:**
```json
[<CHANNEL_NAME>, <PAYLOAD>]
```

**Python Example:**
```python
import websocket
import time
import rel
import json

def on_message(ws, msg):
    msg = json.loads(msg)
    channel, payload = msg
    print(f"Got a message on channel {channel}: Payload: {payload}")

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("Opened connection")
    msg = {"channel":"option_trades","msg_type":"join"}
    ws.send(json.dumps(msg))

if __name__ == "__main__":
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp("wss://api.unusualwhales.com/socket?token=<YOUR_TOKEN>",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever(dispatcher=rel, reconnect=5)  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
```

---

### Flow Alerts (WebSocket)
**Channel:** `flow-alerts`
**Ingestion:** Stream: Real-time
**Priority:** High

**Description:**
Streams live flow alerts (unusual options activity) as they are triggered. All alerts unfiltered. Use for real-time smart money tracking and immediate trade signals.

**Connection:**
```json
{"channel":"flow-alerts","msg_type":"join"}
```

**Payload Schema:**
```json
[
  "flow-alerts",
  {
    "rule_id": "5ce5ec11-087c-4c00-b164-08106b015856",
    "rule_name": "RepeatedHitsDescendingFill",
    "ticker": "DIA",
    "option_chain": "DIA241018C00415000",
    "underlying_price": 415.981,
    "volume": 106,
    "total_size": 50,
    "total_premium": 36466,
    "total_ask_side_prem": 36466,
    "total_bid_side_prem": 0,
    "start_time": 1726670212648,
    "end_time": 1726670212748,
    "url": "",
    "price": 7.3,
    "has_multileg": false,
    "has_sweep": false,
    "has_floor": false,
    "open_interest": 575,
    "all_opening_trades": false,
    "id": "29ed5829-e4ce-4934-876b-51985d2f9b70",
    "has_singleleg": true,
    "volume_oi_ratio": 0,
    "trade_ids": [
      "417f0cd6-09ae-4d43-8542-38557bb713aa",
      "4af4c646-4b21-4a27-8326-db7b0698d3d8",
      "74ddcd55-dcb3-4543-a488-16ee7ca91d45",
      "4ec49859-74a2-4d32-9911-ea329dd77326",
      "e164da3a-a6aa-41d9-a948-c17817453a21",
      "b0d98eeb-1429-4494-9dcc-8d5e7eb46f7d",
      "81b1dcad-f3f6-48a2-bf51-0bfd362ad372"
    ],
    "trade_count": 7,
    "expiry_count": 1,
    "executed_at": 1726670212748,
    "ask_vol": 52,
    "bid_vol": 49,
    "no_side_vol": 0,
    "mid_vol": 5,
    "multi_vol": 0,
    "stock_multi_vol": 0,
    "upstream_condition_details": [
      "auto",
      "slan"
    ],
    "exchanges": [
      "XCBO",
      "MPRL"
    ],
    "bid": "7.15",
    "ask": "7.3"
  }
]
```

---

### GEX by Ticker (WebSocket)
**Channel:** `gex:TICKER`
**Ingestion:** Stream: Real-time
**Priority:** High

**Description:**
Streams live ticker-level GEX updates (gamma/delta/charm/vanna per 1% move) split by OI, volume, and directional flow. Use for real-time hedging pressure monitoring.

**Connection:**
```json
{"channel":"gex:SPY","msg_type":"join"}
```

**Payload Schema:**
```json
[
  "gex:SPY",
  {
    "ticker": "SPY",
    "timestamp": 1726670396000,
    "gamma_per_one_percent_move_oi": "-262444980.31",
    "delta_per_one_percent_move_oi": "",
    "charm_per_one_percent_move_oi": "-1677926539943.05",
    "vanna_per_one_percent_move_oi": "2842602508.57",
    "price": "562.86",
    "gamma_per_one_percent_move_vol": "-934307209.58",
    "delta_per_one_percent_move_vol": "",
    "charm_per_one_percent_move_vol": "-556207588704.10",
    "vanna_per_one_percent_move_vol": "128814703.59",
    "gamma_per_one_percent_move_dir": "-9372185.61",
    "charm_per_one_percent_move_dir": "-2055997560.50",
    "vanna_per_one_percent_move_dir": "-6220855.09"
  }
]
```

---

### GEX by Strike (WebSocket)
**Channel:** `gex_strike:TICKER`
**Ingestion:** Stream: Real-time
**Priority:** High

**Description:**
Streams live strike-level GEX updates with call/put Greeks by OI and volume (ask/bid split). Use for identifying key gamma strikes and dealer hedging zones in real-time.

**Connection:**
```json
{"channel":"gex_strike:SPY","msg_type":"join"}
```

**Payload Schema:**
```json
[
  "gex_strike:SPY",
  {
    "ticker": "SPY",
    "timestamp": 1726670426000,
    "call_gamma_oi": "174792.59",
    "put_gamma_oi": "-1172037.66",
    "call_charm_oi": "85658181.72",
    "put_charm_oi": "-315259003.37",
    "call_vanna_oi": "-6103.51",
    "put_vanna_oi": "1337727.64",
    "call_gamma_vol": "15596.81",
    "put_gamma_vol": "-236.69",
    "call_charm_vol": "-326871.58",
    "put_charm_vol": "-68457.78",
    "call_vanna_vol": "2063.13",
    "put_vanna_vol": "845.06",
    "strike": "290",
    "price": "562.96",
    "call_gamma_ask_vol": "-4064.62",
    "call_gamma_bid_vol": "11532.18",
    "put_gamma_ask_vol": "-140.95",
    "put_gamma_bid_vol": "95.73",
    "call_charm_ask_vol": "85184.72",
    "call_charm_bid_vol": "-241686.87",
    "put_charm_ask_vol": "-59412.37",
    "put_charm_bid_vol": "9045.42",
    "call_vanna_ask_vol": "-537.66",
    "call_vanna_bid_vol": "1525.46",
    "put_vanna_ask_vol": "523.79",
    "put_vanna_bid_vol": "-321.27"
  }
]
```

---

### GEX by Strike & Expiry (WebSocket)
**Channel:** `gex_strike_expiry:TICKER`
**Ingestion:** Stream: Real-time
**Priority:** Medium

**Description:**
Streams live GEX updates at strike AND expiry granularity. Most detailed GEX feed. Use for precise hedging flow analysis by specific contract expirations.

**Connection:**
```json
{"channel":"gex_strike_expiry:SPY","msg_type":"join"}
```

**Payload Schema:**
```json
[
  "gex_strike_expiry:SPY",
  {
    "ticker": "SPY",
    "expiry": "2025-01-24",
    "timestamp": 1726670426000,
    "call_gamma_oi": "174792.59",
    "put_gamma_oi": "-1172037.66",
    "call_charm_oi": "85658181.72",
    "put_charm_oi": "-315259003.37",
    "call_vanna_oi": "-6103.51",
    "put_vanna_oi": "1337727.64",
    "call_gamma_vol": "15596.81",
    "put_gamma_vol": "-236.69",
    "call_charm_vol": "-326871.58",
    "put_charm_vol": "-68457.78",
    "call_vanna_vol": "2063.13",
    "put_vanna_vol": "845.06",
    "strike": "290",
    "price": "562.96",
    "call_gamma_ask_vol": "-4064.62",
    "call_gamma_bid_vol": "11532.18",
    "put_gamma_ask_vol": "-140.95",
    "put_gamma_bid_vol": "95.73"
  }
]
```

---

### News (WebSocket)
**Channel:** `news`
**Ingestion:** Stream: Real-time
**Priority:** Medium

**Description:**
Streams live headline news with timestamp, source, and associated tickers. Use for event-driven trading and market-moving news alerts.

**Connection:**
```json
{"channel":"news","msg_type":"join"}
```

**Payload Schema:**
```json
[
  "news",
  {
    "headline": "US Energy Secretary foresees many more LNG export deals signed",
    "timestamp": "2025-06-11T21:40:56Z",
    "source": "social-media",
    "tickers": [],
    "is_trump_ts": false
  }
]
```

---

### Option Trades - All Tickers (WebSocket)
**Channel:** `option_trades`
**Ingestion:** Stream: Real-time
**Priority:** High

**Description:**
Streams ALL option trades across entire market (~6-10M records/day). Full trade details including Greeks, volume breakdown, premium, tags, flags. Use for market-wide flow analysis and pattern detection.

**Connection:**
```json
{"channel":"option_trades","msg_type":"join"}
```

**Payload Schema:**
```json
{
  "id": "a4dc6020-0611-4c23-b0bc-99944c7348ab",
  "underlying_symbol": "UVIX",
  "executed_at": 1726670167412,
  "nbbo_bid": "0.01",
  "nbbo_ask": "0.09",
  "size": 1,
  "price": "0.01",
  "option_symbol": "UVIX240920C00025000",
  "created_at": 1726670167461,
  "report_flags": [],
  "tags": [
    "bid_side",
    "bearish",
    "etf"
  ],
  "expiry": "2024-09-20",
  "option_type": "call",
  "open_interest": 410,
  "strike": "25.0000000000",
  "premium": "1.00",
  "volume": 105,
  "underlying_price": "4.9261",
  "ewma_nbbo_ask": "0.09",
  "ewma_nbbo_bid": "0.01",
  "implied_volatility": "8.46381958089369",
  "delta": "0.01132315610146539",
  "theta": "-0.02291485773244166",
  "gamma": "0.00962272181839715",
  "vega": "0.0001082948756510385",
  "rho": "0.000002508438316242667",
  "theo": "0.01",
  "trade_code": "slan",
  "exchange": "XCBO",
  "ask_vol": 10,
  "bid_vol": 95,
  "no_side_vol": 0,
  "mid_vol": 0,
  "multi_vol": 0,
  "stock_multi_vol": 0
}
```

---

### Option Trades - By Ticker (WebSocket)
**Channel:** `option_trades:TICKER`
**Ingestion:** Stream: Real-time
**Priority:** High

**Description:**
Streams option trades for a specific ticker only. Same payload as `option_trades` but filtered. Use for focused single-ticker flow monitoring.

**Connection:**
```json
{"channel":"option_trades:TSLA","msg_type":"join"}
```

**Payload Schema:**
Same as `option_trades` channel (see above)

---

### Price Updates (WebSocket)
**Channel:** `price:TICKER`
**Ingestion:** Stream: Real-time
**Priority:** High

**Description:**
Streams live price updates for a specific ticker with close price, volume, and timestamp. Use for real-time price tracking and triggering price-based logic.

**Connection:**
```json
{"channel":"price:SPY","msg_type":"join"}
```

**Payload Schema:**
```json
["price:SPY", {"close": "562.82", "time": 1726670327692, "vol": 6015555}]
```

---

### Lit Trades (WebSocket)
**Channel:** `lit_trades`
**Ingestion:** Stream: Real-time
**Priority:** Medium

**Description:**
Streams live exchange-based (lit) equity trades throughout the trading session. Use for tracking on-exchange execution flow and volume.

**Connection:**
```json
{"channel":"lit_trades","msg_type":"join"}
```

---

### Off-Lit Trades (WebSocket)
**Channel:** `off_lit_trades`
**Ingestion:** Stream: Real-time
**Priority:** Medium

**Description:**
Streams live dark pool (off-lit) equity trades throughout the trading session. Use for tracking dark pool activity and institutional flow.

**Connection:**
```json
{"channel":"off_lit_trades","msg_type":"join"}
```

---

## Historic Data Access

For downloading historic option trades data, use the Full Tape endpoint:
**Endpoint:** `/api/option-trades/full-tape`
**Documentation:** https://api.unusualwhales.com/docs#/operations/PublicApi.OptionTradeController.full_tape
