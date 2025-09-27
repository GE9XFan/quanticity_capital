"""IBKR streaming smoke test stub.

TODO (Michael Merrick):
- Initiate IBKR client session and subscribe to quote/tick streams.
- Output normalized DTOs and verify schema compliance.
- Allow configurable duration and symbol.
"""

import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream IBKR market data")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--duration", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"TODO: stream IBKR data for {args.symbol} during {args.duration}s")
    print("Expected output: normalized quotes, ticks, and depth events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
