# Dashboard Frontend Scaffold

React + TypeScript (Vite) UI described in `docs/specs/dashboard_frontend.md`.

## Setup Plan
- Initialize with `npm create vite@latest dashboard -- --template react-ts` (inside this directory).
- Use TanStack Query for REST/WebSocket data, Zustand for local UI state, and Tailwind or Chakra for styling.
- Mirror backend routes (`/health`, `/analytics/{symbol}`, `/signals/active`, etc.).
- Implement WebSocket client for `/ws/stream` supporting channel subscription.
- Provide `.env.example` for `VITE_API_BASE_URL` and `VITE_API_TOKEN`.

Keep this directory isolated from Python tooling; use `package.json` scripts for build/test.
