"""AlphaVantage streaming smoke test stub.

TODO (Michael Merrick):
- Connect to AlphaVantage client and stream normalized events for given symbol.
- Validate events against `option_chain` contract and print sample output.
- Support --duration argument to limit runtime.
"""

import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream AlphaVantage data")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--duration", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"TODO: stream AlphaVantage data for {args.symbol} during {args.duration}s")
    print("Expected output: normalized OptionQuote samples written to stdout or log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
