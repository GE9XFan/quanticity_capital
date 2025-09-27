"""Query helper demonstration stub.

TODO (Michael Merrick):
- Leverage storage/query_helpers.py to fetch sample time series data.
- Print summary stats for sanity checks.
- Provide command-line options for symbol, metric, start/end.
"""

import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sample Redis TimeSeries queries")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--metric", default="option_chain")
    parser.add_argument("--start", default="-1h")
    parser.add_argument("--end", default="now")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("TODO: execute query helper with:", vars(args))
    print("Expected output: last value + count + basic stats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
