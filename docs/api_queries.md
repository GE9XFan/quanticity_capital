# Unusual Whales API Reference

This document captures the exact REST requests and WebSocket payloads we exercised during Phase 1. Replace `<YOUR_API_TOKEN>` with your token from `.env` before running any snippet.

* Sample REST responses are stored under `docs/api_samples/`.
* Canonical WebSocket payloads (used in unit tests) live in `tests/data/uw/ws/`.

---
## REST Requests
All examples use Python's `http.client` with explicit query strings/parameters exactly as captured from the live API.

### Dark Pool Prints
```
GET https://api.unusualwhales.com/api/darkpool/{ticker}
```
```python
import http.client

conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/darkpool/SPY", headers=headers)
print(conn.getresponse().read().decode())
```

### ETF Exposure
```
GET https://api.unusualwhales.com/api/etfs/{ticker}/exposure
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/etfs/SPY/exposure", headers=headers)
print(conn.getresponse().read().decode())
```

### ETF In/Outflow
```
GET https://api.unusualwhales.com/api/etfs/{ticker}/in-outflow
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/etfs/SPY/in-outflow", headers=headers)
print(conn.getresponse().read().decode())
```

### Economic Calendar
```
GET https://api.unusualwhales.com/api/market/economic-calendar
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/market/economic-calendar", headers=headers)
print(conn.getresponse().read().decode())
```

### Market Tide
```
GET https://api.unusualwhales.com/api/market/market-tide
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/market/market-tide", headers=headers)
print(conn.getresponse().read().decode())
```

### Market OI Change
```
GET https://api.unusualwhales.com/api/market/oi-change
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/market/oi-change", headers=headers)
print(conn.getresponse().read().decode())
```

### Market Top Net Impact
```
GET https://api.unusualwhales.com/api/market/top-net-impact
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/market/top-net-impact", headers=headers)
print(conn.getresponse().read().decode())
```

### Market Total Options Volume
```
GET https://api.unusualwhales.com/api/market/total-options-volume?limit=100
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/market/total-options-volume?limit=100", headers=headers)
print(conn.getresponse().read().decode())
```

### Net Flow by Expiry
```
GET https://api.unusualwhales.com/api/net-flow/expiry
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/net-flow/expiry", headers=headers)
print(conn.getresponse().read().decode())
```

### ETF Tide
```
GET https://api.unusualwhales.com/api/market/{ticker}/etf-tide
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/market/SPY/etf-tide", headers=headers)
print(conn.getresponse().read().decode())
```

### Flow Alerts Mirror
```
GET https://api.unusualwhales.com/api/stock/{ticker}/flow-alerts?limit=100
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/flow-alerts?limit=100", headers=headers)
print(conn.getresponse().read().decode())
```

### Flow per Expiry
```
GET https://api.unusualwhales.com/api/stock/{ticker}/flow-per-expiry
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/flow-per-expiry", headers=headers)
print(conn.getresponse().read().decode())
```

### Greek Exposure (Spot)
```
GET https://api.unusualwhales.com/api/stock/{ticker}/greek-exposure
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/greek-exposure", headers=headers)
print(conn.getresponse().read().decode())
```

### Greek Exposure (by Expiry)
```
GET https://api.unusualwhales.com/api/stock/{ticker}/greek-exposure/expiry
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/greek-exposure/expiry", headers=headers)
print(conn.getresponse().read().decode())
```

### Greek Exposure (by Strike)
```
GET https://api.unusualwhales.com/api/stock/{ticker}/greek-exposure/strike
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/greek-exposure/strike", headers=headers)
print(conn.getresponse().read().decode())
```

### Greek Flow
```
GET https://api/unusualwhales.com/api/stock/{ticker}/greek-flow
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/greek-flow", headers=headers)
print(conn.getresponse().read().decode())
```

### Interpolated IV
```
GET https://api.unusualwhales.com/api/stock/{ticker}/interpolated-iv
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/interpolated-iv", headers=headers)
print(conn.getresponse().read().decode())
```

### IV Rank
```
GET https://api.unusualwhales.com/api/stock/{ticker}/iv-rank
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/iv-rank", headers=headers)
print(conn.getresponse().read().decode())
```

### Max Pain
```
GET https://api.unusualwhales.com/api/stock/{ticker}/max-pain
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/max-pain", headers=headers)
print(conn.getresponse().read().decode())
```

### Net Premium Ticks
```
GET https://api.unusualwhales.com/api/stock/{ticker}/net-prem-ticks
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/net-prem-ticks", headers=headers)
print(conn.getresponse().read().decode())
```

### NOPE
```
GET https://api.unusualwhales.com/api/stock/{ticker}/nope
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/nope", headers=headers)
print(conn.getresponse().read().decode())
```

### OHLC (1m)
```
GET https://api.unusualwhales.com/api/stock/{ticker}/ohlc/1m?limit=500
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/ohlc/1m?limit=500", headers=headers)
print(conn.getresponse().read().decode())
```

### OI Change (Ticker)
```
GET https://api.unusualwhales.com/api/stock/{ticker}/oi-change
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/oi-change", headers=headers)
print(conn.getresponse().read().decode())
```

### Option Chains
```
GET https://api.unusualwhales.com/api/stock/{ticker}/option-chains
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/option-chains", headers=headers)
print(conn.getresponse().read().decode())
```

### Option Stock Price Levels
```
GET https://api.unusualwhales.com/api/stock/{ticker}/option/stock-price-levels
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/option/stock-price-levels", headers=headers)
print(conn.getresponse().read().decode())
```

### Options Volume
```
GET https://api.unusualwhales.com/api/stock/{ticker}/options-volume
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/options-volume", headers=headers)
print(conn.getresponse().read().decode())
```

### Spot Exposures (Spot + Strike)
```
GET https://api.unusualwhales.com/api/stock/{ticker}/spot-exposures
GET https://api.unusualwhales.com/api/stock/{ticker}/spot-exposures/strike
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/spot-exposures", headers=headers)
print(conn.getresponse().read().decode())
conn.request("GET", "/api/stock/SPY/spot-exposures/strike", headers=headers)
print(conn.getresponse().read().decode())
```

### Stock State
```
GET https://api.unusualwhales.com/api/stock/{ticker}/stock-state
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/stock-state", headers=headers)
print(conn.getresponse().read().decode())
```

### Stock Volume Price Levels
```
GET https://api.unusualwhales.com/api/stock/{ticker}/stock-volume-price-levels
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/stock-volume-price-levels", headers=headers)
print(conn.getresponse().read().decode())
```

### Volatility Term Structure
```
GET https://api.unusualwhales.com/api/stock/{ticker}/volatility/term-structure
```
```python
conn = http.client.HTTPSConnection("api.unusualwhales.com")
headers = {
    "Accept": "application/json, text/plain",
    "Authorization": "Bearer <YOUR_API_TOKEN>",
}
conn.request("GET", "/api/stock/SPY/volatility/term-structure", headers=headers)
print(conn.getresponse().read().decode())
```

---
## WebSocket Payloads
Connect to:
```
wss://api.unusualwhales.com/socket?token=<YOUR_API_TOKEN>
```
and send `{ "channel": "<name>", "msg_type": "join" }`.

### Flow Alerts (`flow-alerts`)
```
[
  "flow-alerts",
  {
    "rule_id": "5ce5ec11-087c-4c00-b164-08106b015856",
    "rule_name": "RepeatedHitsDescendingFill",
    "ticker": "DIA",
    "option_chain": "DIA241018C00415000",
    "total_premium": 36466,
    "trade_ids": ["417f0cd6-…", "4af4c646-…", "74ddcd55-…"],
    "executed_at": 1726670212748
  }
]
```

### GEX (`gex:<ticker>`)
```
[
  "gex:SPY",
  {
    "ticker": "SPY",
    "timestamp": 1726670396000,
    "gamma_per_one_percent_move_oi": "-262444980.31",
    "price": "562.86",
    "vanna_per_one_percent_move_vol": "128814703.59"
  }
]
```

### GEX Strike (`gex_strike:<ticker>`)
```
[
  "gex_strike:SPY",
  {
    "ticker": "SPY",
    "timestamp": 1726670426000,
    "strike": "290",
    "call_gamma_oi": "174792.59",
    "put_gamma_oi": "-1172037.66"
  }
]
```

### GEX Strike + Expiry (`gex_strike_expiry:<ticker>`)
```
[
  "gex_strike_expiry:SPY",
  {
    "ticker": "SPY",
    "expiry": "2025-01-24",
    "timestamp": 1726670426000,
    "strike": "290"
  }
]
```

### News (`news`)
```
[
  "news",
  {
    "headline": "US Energy Secretary foresees many more LNG export deals signed",
    "timestamp": "2025-06-11T21:40:56Z",
    "source": "social-media",
    "tickers": []
  }
]
```

### Option Trades (`option_trades` / `option_trades:<ticker>`)
```
{
  "id": "a4dc6020-0611-4c23-b0bc-99944c7348ab",
  "underlying_symbol": "UVIX",
  "executed_at": 1726670167412,
  "option_symbol": "UVIX240920C00025000",
  "size": 1,
  "price": "0.01",
  "tags": ["bid_side", "bearish", "etf"],
  "exchange": "XCBO"
}
```

### Price (`price:<ticker>`)
```
[
  "price:SPY",
  {
    "ticker": "SPY",
    "close": "562.82",
    "time": 1726670327692,
    "vol": 6015555
  }
]
```

### Multi-channel Example
```
websocat "wss://api.unusualwhales.com/socket?token=<YOUR_API_TOKEN>"
{"channel":"option_trades","msg_type":"join"}
["option_trades",{"response":{},"status":"ok"}]
{"channel":"option_trades:TSLA","msg_type":"join"}
["option_trades:TSLA",{"response":{},"status":"ok"}]
```

### Python Client Snippet
```python
import websocket
import json
import rel

def on_message(ws, msg):
    channel, payload = json.loads(msg)
    print(f"Got {channel}: {payload}")

ws = websocket.WebSocketApp(
    "wss://api.unusualwhales.com/socket?token=<YOUR_API_TOKEN>",
    on_message=on_message,
)
ws.run_forever(dispatcher=rel, reconnect=5)
```

---
## Historic Data
Bulk option tape downloads: <https://api.unusualwhales.com/docs#/operations/PublicApi.OptionTradeController.full_tape>.
