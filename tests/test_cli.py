import json

import pytest

from locale_doctor.cli import main
from locale_doctor.core import (
    LocaleDoctorReport,
    ISSUE_NONE_FOUND,
    ISSUE_SSH_CLIENT_FORWARDS_LOCALE,
    ISSUE_UNSET_LOCALE_REQUESTED,
)


def _fake_report(issue=ISSUE_UNSET_LOCALE_REQUESTED):
    return LocaleDoctorReport(
        issue=issue, explanation="example explanation",
        locale_env={"LANG": "en_US.UTF-8", "LC_TIME": "de_DE.UTF-8"},
        missing_locales={"LC_TIME": "de_DE.UTF-8"},
        active_charmap="UTF-8",
        sshd_accepts_locale_vars=True,
    )


def test_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert "locale-doctor" in capsys.readouterr().out


def test_text_output(monkeypatch, capsys):
    monkeypatch.setattr("locale_doctor.cli.diagnose_host", lambda check_sshd_config: _fake_report())
    rc = main([])
    out = capsys.readouterr().out
    assert "requested_locale_not_installed" in out
    assert "LC_TIME" in out
    assert "de_DE.UTF-8" in out
    assert "uninstalled locale" in out
    assert rc == 2


def test_json_output(monkeypatch, capsys):
    monkeypatch.setattr("locale_doctor.cli.diagnose_host", lambda check_sshd_config: _fake_report())
    rc = main(["--json"])
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["issue"] == ISSUE_UNSET_LOCALE_REQUESTED
    assert rc == 2


def test_none_found_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(
        "locale_doctor.cli.diagnose_host",
        lambda check_sshd_config: LocaleDoctorReport(issue=ISSUE_NONE_FOUND, explanation="fine"),
    )
    rc = main([])
    assert rc == 0


def test_no_sshd_check_flag_passed_through(monkeypatch):
    captured = {}

    def fake_diagnose(check_sshd_config):
        captured["check_sshd_config"] = check_sshd_config
        return LocaleDoctorReport(issue=ISSUE_NONE_FOUND, explanation="fine")

    monkeypatch.setattr("locale_doctor.cli.diagnose_host", fake_diagnose)
    main(["--no-sshd-check"])
    assert captured["check_sshd_config"] is False


def test_text_output_shows_ssh_client_sendenv_line(monkeypatch, capsys):
    """cli.py must surface ssh_client_sends_locale_vars, the client-side
    SendEnv risk newly wired up in core.py's diagnose_host()."""
    report = LocaleDoctorReport(
        issue=ISSUE_SSH_CLIENT_FORWARDS_LOCALE,
        explanation="client forwards locale vars",
        locale_env={"LANG": "en_US.UTF-8"},
        active_charmap="UTF-8",
        sshd_accepts_locale_vars=False,
        ssh_client_sends_locale_vars=True,
    )
    monkeypatch.setattr("locale_doctor.cli.diagnose_host", lambda check_sshd_config: report)
    rc = main([])
    out = capsys.readouterr().out
    assert "ssh_config (client) SendEnv includes locale variables" in out
    assert rc == 2
