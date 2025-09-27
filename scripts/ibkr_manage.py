"""IBKR session management stub.

TODO (Michael Merrick):
- Provide commands for connect, disconnect, reconnect, and status checks.
- Integrate with IBKR client wrapper and configuration.
- Return exit codes based on success/failure.
"""

import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage IBKR ingestion session")
    sub = parser.add_subparsers(dest="command", required=True)
    reconnect = sub.add_parser("reconnect")
    reconnect.add_argument("--env", default="dev")
    status = sub.add_parser("status")
    status.add_argument("--env", default="dev")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print(f"TODO: IBKR manage command={args.command} env={args.env}")
    print("Expected output: connection result + metrics snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
