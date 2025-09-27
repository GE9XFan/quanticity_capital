"""Ensure pinned dependencies stay in sync between pyproject.toml and requirements.txt."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if sys.version_info < (3, 11):  # pragma: no cover - environment guard
    pytest.skip("Dependency sync check requires Python 3.11+", allow_module_level=True)

import tomllib


def test_requirements_matches_pyproject() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    pyproject_data = tomllib.loads((repo_root / "pyproject.toml").read_text())
    project_section = pyproject_data.get("project", {})

    pyproject_requirements = set(project_section.get("dependencies", []))
    dev_dependencies = set(
        project_section.get("optional-dependencies", {}).get("dev", [])
    )

    expected_requirements = pyproject_requirements | dev_dependencies

    requirements_lines = {
        line.strip()
        for line in (repo_root / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert requirements_lines == expected_requirements, (
        "requirements.txt is out of sync with pyproject.toml dependencies. "
        "Update both files together to maintain a stable tooling baseline."
    )
