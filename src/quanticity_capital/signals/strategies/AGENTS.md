# Strategy Definitions

Holds rule implementations for each configured strategy (`0dte`, `1dte`, `14dte`, `moc_imbalance`).

Each strategy module should expose functions like `evaluate(symbol, analytics_bundle, sizing_settings) -> SignalDecision`.

Reference `docs/specs/signal_engine.md` for triggers and sizing toggles.
