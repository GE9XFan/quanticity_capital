# Unusual Whales WebSocket Scope (Plain-English Plan)

We are not coding the WebSocket consumers yet. This page simply says **which pipes we care about**, **why they matter**, and **how they will sit next to the REST fetcher** when the time comes.

## Channels we will listen to first

| Channel | What it streams | How it helps |
|---------|-----------------|--------------|
| `flow-alerts` | Real-time whale flow alerts | Keeps us up-to-the-second between REST pulls of `flow_alerts` |
| `option_trades` / `option_trades:<ticker>` | Individual option trades | Fills the gaps between REST `options_volume` snapshots; lets us build custom tape metrics |
| `price:<ticker>` | Live underlying price ticks | Gives us true intraday pricing instead of relying on 1‑minute REST bars |
| `gex:<ticker>` | Aggregate gamma exposure | Keeps `greek_exposure` style data current without waiting for the next REST pass |
| `gex_strike:<ticker>` / `gex_strike_expiry:<ticker>` | Strike + expiry level gamma | Lets analytics see the latest strike map without re-polling heavy REST endpoints |
| `news` | Breaking headlines | Feeds the distribution layer and AI commentator with instant alerts |

## How these streams complement the REST API

- REST gives us **snapshots**. WebSockets give us **the in-between moments**.
- For channels we already fetch via REST (e.g. `flow_alerts`, `gex`), the live feed means we can react instantly and still keep the REST pull as a safety net / hourly sanity check.
- For streams like `price:<ticker>`, the WebSocket becomes the main source for intraday analytics while the REST OHLC endpoint stays as a fallback.

## Implementation sketch (for later)

When we are ready to build the consumer, we will:

1. Open one async WebSocket connection per channel family (flow, trades, prices, gex, news).
2. For each message:
   - Write the raw event into a **Redis stream** with a sensible cap (e.g. maxlen 5,000) so we can replay recent history.
   - Update the same Redis hash keys that REST uses (`uw:rest:<endpoint>[:<symbol>]`) so “latest snapshot” stays consistent across REST and WS.
3. Log every reconnect attempt and message type so we can debug easily.
4. Reuse the settings pattern we already have (token, tickers, rate limits) so the CLI stays familiar.

## Open questions to answer before coding

- Exact retention: how many events do we keep per stream? (Start with 1 trading day worth.)
- Ordering/deduplication: do we get duplicate trade IDs? (Need to inspect live feed when we build it.)
- Back-pressure: what happens if Redis is slow? (Probably drop to disk queue as a fallback—decide later.)

For now, this page is our north star. Once the REST pipeline runs on autopilot, we will come back here and turn these notes into code.

### How to try it (when ready)

1. Set `ENABLE_WEBSOCKET=true` in `.env` (and make sure `STORE_TO_REDIS`/`ENABLE_HISTORY_STREAMS` are set if you want snapshots/streams).
2. Start the consumer: `python -m src.cli.uw_websocket` or `make uw-websocket`.
3. Watch logs: `tail -f "$(ls -t logs/uw_websocket_*.log | head -n 1)"`.
4. Inspect streams: `redis-cli XREVRANGE uw:ws:flow-alerts:SPY + - COUNT 5`.
