"""Inspect a stored Unusual Whales JSON file and print a short summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a raw JSON file saved by the REST fetcher")
    parser.add_argument("path", help="Path to the JSON file (e.g. data/unusual_whales/raw/flow_alerts/SPY_*.json)")
    args = parser.parse_args()

    file_path = Path(args.path)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    with file_path.open() as handle:
        payload = json.load(handle)

    metadata = payload.get("metadata", {})
    data = payload.get("data")

    print("FILE SUMMARY")
    print("============")
    print(f"Path: {file_path}")
    if metadata:
        print("Metadata:")
        for key in sorted(metadata):
            print(f"  {key}: {metadata[key]}")
    else:
        print("Metadata: <missing>")

    print("\nData snippet:")
    describe_payload(data)


def describe_payload(data: Any, indent: str = "  ", depth: int = 0) -> None:
    max_depth = 2
    if depth > max_depth:
        print(f"{indent}... (truncated)")
        return

    if isinstance(data, dict):
        keys = list(data.keys())
        print(f"{indent}dict with {len(keys)} keys")
        for key in keys[:5]:
            value = data[key]
            print(f"{indent}- {key}: {type_name(value)}")
            if isinstance(value, (dict, list)):
                describe_payload(value, indent + "  ", depth + 1)
            else:
                print(f"{indent}  value: {value}")
        if len(keys) > 5:
            print(f"{indent}... ({len(keys) - 5} more keys)")
    elif isinstance(data, list):
        print(f"{indent}list with {len(data)} items")
        for item in data[:3]:
            print(f"{indent}- item type: {type_name(item)}")
            if isinstance(item, (dict, list)):
                describe_payload(item, indent + "  ", depth + 1)
            else:
                print(f"{indent}  value: {item}")
        if len(data) > 3:
            print(f"{indent}... ({len(data) - 3} more items)")
    else:
        print(f"{indent}{type_name(data)}: {data}")


def type_name(value: Any) -> str:
    return type(value).__name__


if __name__ == "__main__":
    main()
