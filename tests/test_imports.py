"""Smoke checks for the repository skeleton."""

from __future__ import annotations

from importlib import import_module


def test_package_imports() -> None:
    module = import_module("quanticity_capital")
    assert hasattr(module, "bootstrap_logging")


def test_cli_main_returns_zero() -> None:
    from quanticity_capital.main import main

    exit_code = main(["--log-level", "DEBUG"])
    assert exit_code == 0
