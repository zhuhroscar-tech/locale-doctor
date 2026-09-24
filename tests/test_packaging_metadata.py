"""Regression tests for modern Python package license metadata."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def _pyproject_text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def test_project_uses_spdx_license_string() -> None:
    text = _pyproject_text()

    assert 'license = "MIT"' in text
    assert "license = {" not in text
    assert "license-files" in text


def test_deprecated_license_classifier_does_not_return() -> None:
    text = _pyproject_text()

    assert "License :: OSI Approved :: MIT License" not in text


def test_setuptools_floor_supports_spdx_license_metadata() -> None:
    text = _pyproject_text()
    match = re.search(r'setuptools>=([0-9]+)', text)

    assert match, "pyproject.toml should pin a minimum setuptools version"
    assert int(match.group(1)) >= 77
