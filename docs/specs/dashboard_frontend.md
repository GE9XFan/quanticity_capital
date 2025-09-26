# Dashboard Frontend (React)

## Purpose
Provide a MacBook-friendly web interface to monitor system health, market analytics, signals, trades, social activity, and watchdog status in near real-time.

## Stack
- React + TypeScript (Vite build).
- Component library: lightweight custom components with Tailwind CSS or Chakra UI (choose minimal dependency).
- State management: TanStack Query for API data, Zustand for local UI state.
- WebSocket integration for live updates via API backend.

## Core Views
1. **Overview**
   - Module health grid (heartbeats, last update).
   - Scheduler status, rate-limit usage, error counters.
2. **Market Analytics**
   - Symbol selector, display dealer exposures, volatility regime, liquidity stress, risk summary.
   - Charts: implied vol smile, risk reversal ladder, VPIN trend.
3. **Signals**
   - Pending/active signals with strategy tags, sizing model, approvals.
   - Actions for manual approve/reject (if enabled).
4. **Trades**
   - Live trades with PnL, stops/targets, timeline of fills.
   - Historical trades table with filters.
5. **Social Pipeline**
   - Queue of messages, approval status, send history.
6. **Watchdog**
   - Recent analyses, risk flags, autopilot status toggle.
7. **Macro & Futures**
   - Macro overlay charts, futures basis vs. spot.

## UI Considerations
- Responsive layout but optimized for desktop.
- Dark mode toggle.
- Data freshness indicators (color-coded by TTL status).
- Link out to raw payload inspector (launch CLI command suggestions).

## Configuration
- `.env` file for API base URL, auth token.
- Build scripts via `npm run dev`, `npm run build`.
- Optional integration with system notification for alerts (future scope).

## Testing
- Use Playwright or Cypress for smoke tests (focus on data rendering).
- Mock WebSocket server in dev mode; actual integration validated manually with live backend.
