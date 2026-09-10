from locale_doctor.core import (
    ISSUE_MISMATCHED_CHARMAP,
    ISSUE_NONE_FOUND,
    ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE,
    ISSUE_UNSET_LOCALE_REQUESTED,
    charmap_is_utf8,
    diagnose,
    diagnose_host,
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
