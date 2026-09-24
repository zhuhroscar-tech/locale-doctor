"""Repository completeness contracts for locale-doctor."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
CI = ROOT / ".github" / "workflows" / "ci.yml"
CODEQL = ROOT / ".github" / "workflows" / "codeql.yml"


def _version() -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "pyproject.toml should declare the project version"
    return match.group(1)


def test_required_repository_files_exist() -> None:
    for relative in [
        "LICENSE",
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        ".github/workflows/codeql.yml",
    ]:
        assert (ROOT / relative).is_file(), f"missing required repository file: {relative}"


def test_readmes_link_release_history_license_and_download_artifacts() -> None:
    for path in [README, README_ZH]:
        text = path.read_text(encoding="utf-8")
        assert "CHANGELOG.md" in text
        assert "releases" in text
        assert "LICENSE" in text
        assert "locale-doctor.pyz" in text
        assert "SHA256SUMS.txt" in text


def test_changelog_documents_current_version() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert f"## v{_version()}" in text
    assert "v0.1.9" in text
    assert "v0.1.0" in text


def test_ci_builds_release_artifacts_and_runs_codeql() -> None:
    ci_text = CI.read_text(encoding="utf-8")
    codeql_text = CODEQL.read_text(encoding="utf-8")

    assert "python -m build" in ci_text
    assert "locale-doctor.pyz" in ci_text
    assert "SHA256SUMS.txt" in ci_text
    assert "actions/upload-artifact" in ci_text
    assert "github/codeql-action" in codeql_text
