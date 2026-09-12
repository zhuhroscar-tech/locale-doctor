from locale_doctor.core import (
    ISSUE_LOCALE_LIST_UNAVAILABLE,
    ISSUE_MISMATCHED_CHARMAP,
    ISSUE_NONE_FOUND,
    ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE,
    ISSUE_UNSET_LOCALE_REQUESTED,
    charmap_is_utf8,
    diagnose,
    diagnose_host,
    find_included_sshd_files,
    find_missing_locales,
    get_active_charmap,
    get_installed_locales,
    get_locale_env,
    locale_is_installed,
    sshd_accepts_locale,
)


INSTALLED_SAMPLE = [
    "C", "C.UTF-8", "en_US.utf8", "en_GB.utf8", "POSIX",
]


def test_get_locale_env_filters_and_drops_empty():
    env = {"LANG": "en_US.UTF-8", "LC_ALL": "", "PATH": "/usr/bin", "LC_TIME": "de_DE.UTF-8"}
    result = get_locale_env(environ=env)
    assert result == {"LANG": "en_US.UTF-8", "LC_TIME": "de_DE.UTF-8"}


def test_locale_is_installed_case_and_dash_insensitive():
    assert locale_is_installed("en_US.UTF-8", INSTALLED_SAMPLE) is True
    assert locale_is_installed("EN_US.utf-8", INSTALLED_SAMPLE) is True


def test_locale_is_installed_false_when_missing():
    assert locale_is_installed("de_DE.UTF-8", INSTALLED_SAMPLE) is False


def test_locale_is_installed_true_for_empty_request():
    assert locale_is_installed("", INSTALLED_SAMPLE) is True


def test_find_missing_locales():
    env = {"LANG": "en_US.UTF-8", "LC_TIME": "de_DE.UTF-8"}
    missing = find_missing_locales(env, INSTALLED_SAMPLE)
    assert missing == {"LC_TIME": "de_DE.UTF-8"}


def test_find_missing_locales_handles_language_colon_list():
    env = {"LANGUAGE": "de_DE:en_US:en"}
    missing = find_missing_locales(env, INSTALLED_SAMPLE)
    assert "LANGUAGE" in missing


def test_find_missing_locales_none_missing():
    env = {"LANG": "en_US.UTF-8"}
    assert find_missing_locales(env, INSTALLED_SAMPLE) == {}


def test_get_installed_locales_uses_runner():
    def fake_runner(cmd, timeout=15):
        assert cmd == ["locale", "-a"]
        return "C\nC.UTF-8\nen_US.utf8\n"

    result = get_installed_locales(runner=fake_runner)
    assert result == ["C", "C.UTF-8", "en_US.utf8"]


def test_get_active_charmap_parses_output():
    def fake_runner(cmd, timeout=15):
        return 'charmap="UTF-8"\n'

    assert get_active_charmap(runner=fake_runner) == "UTF-8"


def test_get_active_charmap_none_when_unparseable():
    def fake_runner(cmd, timeout=15):
        return "garbage"

    assert get_active_charmap(runner=fake_runner) is None


def test_charmap_is_utf8_true_cases():
    assert charmap_is_utf8("UTF-8") is True
    assert charmap_is_utf8("utf8") is True


def test_charmap_is_utf8_false_case():
    assert charmap_is_utf8("ISO-8859-15") is False


def test_charmap_is_utf8_true_when_unknown():
    assert charmap_is_utf8(None) is True


def test_sshd_accepts_locale_true():
    config = "AcceptEnv LANG LC_*\nX11Forwarding yes\n"
    assert sshd_accepts_locale(config) is True


def test_sshd_accepts_locale_false_when_absent():
    config = "X11Forwarding yes\nPermitRootLogin no\n"
    assert sshd_accepts_locale(config) is False


def test_diagnose_prioritizes_missing_locale():
    report = diagnose(
        locale_env={"LC_TIME": "de_DE.UTF-8"},
        installed_locales=INSTALLED_SAMPLE,
        active_charmap="ISO-8859-15",
        sshd_config_text="AcceptEnv LANG LC_*\n",
    )
    assert report.issue == ISSUE_UNSET_LOCALE_REQUESTED


def test_diagnose_falls_back_to_charmap():
    report = diagnose(
        locale_env={"LANG": "en_US.UTF-8"},
        installed_locales=INSTALLED_SAMPLE,
        active_charmap="ISO-8859-15",
        sshd_config_text="AcceptEnv LANG LC_*\n",
    )
    assert report.issue == ISSUE_MISMATCHED_CHARMAP


def test_diagnose_falls_back_to_sshd():
    report = diagnose(
        locale_env={"LANG": "en_US.UTF-8"},
        installed_locales=INSTALLED_SAMPLE,
        active_charmap="UTF-8",
        sshd_config_text="AcceptEnv LANG LC_*\n",
    )
    assert report.issue == ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE


def test_diagnose_none_found():
    report = diagnose(
        locale_env={"LANG": "en_US.UTF-8"},
        installed_locales=INSTALLED_SAMPLE,
        active_charmap="UTF-8",
        sshd_config_text="X11Forwarding yes\n",
    )
    assert report.issue == ISSUE_NONE_FOUND


def test_report_to_dict_roundtrip():
    report = diagnose(
        locale_env={"LC_TIME": "de_DE.UTF-8"},
        installed_locales=INSTALLED_SAMPLE,
        active_charmap="UTF-8",
        sshd_config_text="",
    )
    d = report.to_dict()
    assert d["issue"] == ISSUE_UNSET_LOCALE_REQUESTED
    assert d["missing_locales"] == {"LC_TIME": "de_DE.UTF-8"}


def test_diagnose_host_integration(monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("LC_ALL", raising=False)

    def fake_runner(cmd, timeout=15):
        if cmd == ["locale", "-a"]:
            return "C\nC.UTF-8\nen_US.utf8\n"
        if cmd[0] == "locale" and "charmap" in cmd:
            return 'charmap="UTF-8"\n'
        if cmd[0] == "cat":
            return "X11Forwarding yes\n"
        return ""

    report = diagnose_host(runner=fake_runner)
    assert report.issue == ISSUE_NONE_FOUND


def test_diagnose_reports_locale_list_unavailable_not_all_missing():
    """When `locale -a` yields nothing (broken/unavailable tool), diagnose()
    must not silently treat every requested locale as 'not installed' --
    that would be a false positive masking a diagnostic-tool failure. Real
    hosts always report at least C/POSIX from `locale -a`, so an empty list
    means the check itself is broken, not that nothing is installed."""
    report = diagnose(
        locale_env={"LANG": "en_US.UTF-8"},
        installed_locales=[],
        active_charmap="UTF-8",
        sshd_config_text="X11Forwarding yes\n",
    )
    assert report.issue == ISSUE_LOCALE_LIST_UNAVAILABLE
    assert report.missing_locales == {}


def test_diagnose_host_integration_locale_a_unavailable(monkeypatch):
    """Integration-level proof: if the `locale -a` runner call fails/returns
    nothing, diagnose_host() surfaces the unavailable-list issue instead of
    falsely flagging LANG as an uninstalled locale."""
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("LC_ALL", raising=False)

    def fake_runner(cmd, timeout=15):
        if cmd == ["locale", "-a"]:
            return ""  # locale binary missing/broken in this environment
        if cmd[0] == "locale" and "charmap" in cmd:
            return 'charmap="UTF-8"\n'
        if cmd[0] == "cat":
            return "X11Forwarding yes\n"
        return ""

    report = diagnose_host(runner=fake_runner)
    assert report.issue == ISSUE_LOCALE_LIST_UNAVAILABLE


def test_find_included_sshd_files_resolves_absolute_glob():
    """Ubuntu 20.04+/Debian 11+/RHEL 8+ ship `Include /etc/ssh/sshd_config.d/*.conf`
    at the top of the default sshd_config; hardening tools (cloud-init,
    Ansible) commonly drop AcceptEnv overrides there instead of editing the
    main file."""
    config = "Include /etc/ssh/sshd_config.d/*.conf\nX11Forwarding yes\n"

    def fake_glob(pattern):
        assert pattern == "/etc/ssh/sshd_config.d/*.conf"
        return ["/etc/ssh/sshd_config.d/50-cloud-init.conf", "/etc/ssh/sshd_config.d/10-hardening.conf"]

    result = find_included_sshd_files(config, glob_fn=fake_glob)
    # sorted deterministically
    assert result == ["/etc/ssh/sshd_config.d/10-hardening.conf", "/etc/ssh/sshd_config.d/50-cloud-init.conf"]


def test_find_included_sshd_files_resolves_relative_pattern():
    config = "Include sshd_config.d/*.conf\n"

    def fake_glob(pattern):
        assert pattern == "/etc/ssh/sshd_config.d/*.conf"
        return []

    result = find_included_sshd_files(config, base_dir="/etc/ssh", glob_fn=fake_glob)
    assert result == []


def test_find_included_sshd_files_none_when_no_include_directive():
    config = "X11Forwarding yes\nAcceptEnv LANG LC_*\n"
    assert find_included_sshd_files(config, glob_fn=lambda p: ["should-not-be-called"]) == []


def test_diagnose_host_detects_accept_env_only_in_included_dropin(monkeypatch, tmp_path):
    """Regression for the real gap: the main sshd_config has no AcceptEnv
    line (as on a hardened/default host using the standard `Include
    /etc/ssh/sshd_config.d/*.conf` layout), but a drop-in file included
    from it does grant AcceptEnv LANG LC_*. Before this fix, diagnose_host
    only ever read the literal /etc/ssh/sshd_config file and never
    resolved Include directives, so this real-world case was silently
    reported as 'no locale issue found' -- a false all-clear."""
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("LC_ALL", raising=False)

    dropin_dir = tmp_path / "sshd_config.d"
    dropin_dir.mkdir()
    dropin_file = dropin_dir / "50-cloud-init.conf"
    dropin_file.write_text("AcceptEnv LANG LC_*\n")

    def fake_runner(cmd, timeout=15):
        if cmd == ["locale", "-a"]:
            return "C\nC.UTF-8\nen_US.utf8\n"
        if cmd[0] == "locale" and "charmap" in cmd:
            return 'charmap="UTF-8"\n'
        if cmd[0] == "cat" and cmd[1] == "/etc/ssh/sshd_config":
            return f"Include {dropin_dir}/*.conf\nX11Forwarding yes\n"
        if cmd[0] == "cat" and cmd[1] == str(dropin_file):
            return dropin_file.read_text()
        return ""

    report = diagnose_host(runner=fake_runner)
    assert report.issue == ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE
    assert report.sshd_accepts_locale_vars is True
