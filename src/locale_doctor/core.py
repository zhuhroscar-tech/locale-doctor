"""Core logic for locale-doctor.

The problem: a decade-old, still-recurring Linux failure mode --
`perl: warning: Setting locale failed`, `locale: Cannot set LC_ALL to
default locale`, mojibake ('??????' or garbled characters) over SSH --
happens because the *client's* locale environment variables (LANG,
LC_ALL, LC_*) get forwarded over SSH (via `SendEnv`/`AcceptEnv`) to a
*server* that doesn't have that locale installed/generated. Every
existing answer (AskUbuntu, Stack Exchange, r/openbsd, r/ProxmoxQA) is
the same multi-step manual diagnostic: read the current `locale` output,
check `locale -a` for what's actually installed, check
`/etc/ssh/ssh_config`'s `SendEnv` and `/etc/ssh/sshd_config`'s
`AcceptEnv`, and reconcile them by hand. No tool automates this
reconciliation into one command.

This tool performs exactly that: it inspects the current process'
locale environment variables, cross-references them against the locales
actually available on this host (`locale -a`), and separately reports
whether SSH client/server config would forward locale variables that
this host cannot satisfy -- giving a single, clear verdict instead of a
multi-file manual investigation.

Strictly read-only: it never calls `locale-gen`, `dpkg-reconfigure
locales`, or modifies any SSH config file.
"""
from __future__ import annotations

import glob as glob_module
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional


ISSUE_UNSET_LOCALE_REQUESTED = "requested_locale_not_installed"
ISSUE_MISMATCHED_CHARMAP = "mismatched_charmap"
ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE = "ssh_forwards_uninstalled_locale_vars"
ISSUE_SSH_CLIENT_FORWARDS_LOCALE = "ssh_client_forwards_locale_vars"
ISSUE_LOCALE_LIST_UNAVAILABLE = "installed_locale_list_unavailable"
ISSUE_NONE_FOUND = "no_locale_issue_found"

ISSUE_EXPLANATIONS = {
    ISSUE_LOCALE_LIST_UNAVAILABLE: (
        "`locale -a` returned no locales at all, which real systems never do "
        "(even a minimal host reports at least 'C' and 'POSIX'). This means "
        "the installed-locale list could not actually be determined -- "
        "likely because the `locale` binary is missing, unusable, or the "
        "command failed in this environment. Any 'requested locale not "
        "installed' verdict would be a false positive in this state, so no "
        "such verdict is reported; re-run where `locale -a` works to get a "
        "real diagnosis."
    ),
    ISSUE_UNSET_LOCALE_REQUESTED: (
        "One or more locale environment variables (LANG/LC_ALL/LC_*) request "
        "a locale that is not present in this host's installed locale list "
        "(`locale -a`). Programs that call setlocale() with this value will "
        "fail or silently fall back to the 'C' locale, which is the direct "
        "cause of 'Setting locale failed' warnings from perl, Python, and "
        "other programs."
    ),
    ISSUE_MISMATCHED_CHARMAP: (
        "The active locale's charmap does not appear to be UTF-8. If your "
        "terminal emulator or SSH client is emitting UTF-8-encoded "
        "characters while the remote locale expects a different charmap "
        "(or vice versa), this is the classic cause of mojibake / '??????' "
        "output for accented or non-ASCII characters."
    ),
    ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE: (
        "This host's sshd_config accepts (AcceptEnv) locale-related "
        "environment variables that a connecting SSH client may forward "
        "(via SendEnv) with a locale this host does not have installed. "
        "This is the most common root cause of 'Setting locale failed' "
        "warnings appearing only over SSH and not in a local terminal."
    ),
    ISSUE_SSH_CLIENT_FORWARDS_LOCALE: (
        "This host's own ssh_config (client side) is configured to send "
        "(SendEnv) locale-related environment variables to every remote "
        "server it connects to, via a value this host's *current* locale "
        "environment requests. If a remote server does not have that "
        "locale installed and its sshd_config accepts the variable "
        "(AcceptEnv), the remote session will show 'Setting locale "
        "failed'/mojibake even though this host's own locale setup is "
        "fine. This is a latent risk to remote sessions, not a proven "
        "failure on this host -- inspect the remote's installed locales "
        "and AcceptEnv policy, or stop forwarding locale variables you "
        "don't need remotely."
    ),
    ISSUE_NONE_FOUND: (
        "No locale misconfiguration was detected: every requested locale "
        "environment variable corresponds to an installed locale, the "
        "active charmap is UTF-8, and (if inspected) sshd_config does not "
        "accept locale variables beyond what this host supports."
    ),
}


def run(cmd: list, timeout: int = 15) -> str:
    """Run a read-only subprocess command, returning stdout (empty on error)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return result.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


LOCALE_ENV_VARS = [
    "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_NUMERIC", "LC_TIME",
    "LC_COLLATE", "LC_MONETARY", "LC_MESSAGES", "LC_PAPER", "LC_NAME",
    "LC_ADDRESS", "LC_TELEPHONE", "LC_MEASUREMENT", "LC_IDENTIFICATION",
]


def get_locale_env(environ: Optional[dict] = None) -> dict:
    """Return the subset of os.environ that are locale-related variables."""
    environ = environ if environ is not None else dict(os.environ)
    return {k: v for k, v in environ.items() if k in LOCALE_ENV_VARS and v}


def get_installed_locales(runner=run) -> list:
    """Return every locale name reported by `locale -a`."""
    out = runner(["locale", "-a"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def _normalize_locale_name(name: str) -> str:
    """Normalize for comparison: case-insensitive, treat 'utf8'/'UTF-8' the
    same, and ignore a trailing '@modifier'."""
    name = name.split("@", 1)[0]
    return name.lower().replace("-", "").replace("_", "")


def locale_is_installed(requested: str, installed: list) -> bool:
    if not requested:
        return True
    normalized_requested = _normalize_locale_name(requested)
    return any(_normalize_locale_name(inst) == normalized_requested for inst in installed)


def find_missing_locales(locale_env: dict, installed: list) -> dict:
    """Return {var_name: requested_value} for every locale env var whose
    value names a locale not present in `installed`."""
    missing = {}
    for var, value in locale_env.items():
        # LANGUAGE can be a colon-separated fallback list; check each entry.
        candidates = value.split(":") if var == "LANGUAGE" else [value]
        for candidate in candidates:
            candidate = candidate.strip()
            if candidate and not locale_is_installed(candidate, installed):
                missing[var] = value
                break
    return missing


def get_active_charmap(runner=run) -> Optional[str]:
    out = runner(["locale", "-k", "charmap"])
    m = re.search(r'charmap\s*=\s*"?([^"\n]+)"?', out)
    return m.group(1).strip() if m else None


def charmap_is_utf8(charmap: Optional[str]) -> bool:
    if not charmap:
        return True  # unknown -- don't flag
    return "utf-8" in charmap.lower() or "utf8" in charmap.lower()


_SENDENV_LOCALE_RE = re.compile(r"^\s*SendEnv\s+(.+)$", re.IGNORECASE | re.MULTILINE)
_ACCEPTENV_LOCALE_RE = re.compile(r"^\s*AcceptEnv\s+(.+)$", re.IGNORECASE | re.MULTILINE)


def _config_forwards_locale_vars(config_text: str, directive_re: re.Pattern) -> bool:
    for m in directive_re.finditer(config_text):
        tokens = m.group(1).split()
        for token in tokens:
            if token in ("LANG", "LANGUAGE") or token.startswith("LC_"):
                return True
    return False


def ssh_client_sends_locale(ssh_config_text: str) -> bool:
    return _config_forwards_locale_vars(ssh_config_text, _SENDENV_LOCALE_RE)


def sshd_accepts_locale(sshd_config_text: str) -> bool:
    return _config_forwards_locale_vars(sshd_config_text, _ACCEPTENV_LOCALE_RE)


def read_file_if_exists(path: str, runner=run) -> str:
    return runner(["cat", path])


_INCLUDE_RE = re.compile(r"^\s*Include\s+(.+)$", re.IGNORECASE | re.MULTILINE)


def find_included_sshd_files(config_text: str, base_dir: str = "/etc/ssh", glob_fn=glob_module.glob) -> list:
    """Resolve every path matched by an sshd_config `Include` directive.

    Every mainstream OpenSSH-shipped sshd_config since OpenSSH 8.2 (the
    default on Ubuntu 20.04+, Debian 11+, RHEL 8+, and most distro
    packaging) starts with `Include /etc/ssh/sshd_config.d/*.conf`, and
    hardening/config-management tooling (cloud-init, Ansible, Puppet)
    commonly drops `AcceptEnv` overrides into that directory rather than
    editing the main file. A relative Include pattern is resolved against
    `base_dir` (sshd_config's own directory), matching sshd's own
    behavior. Glob matches are sorted for deterministic, reproducible
    results.
    """
    paths: list = []
    for m in _INCLUDE_RE.finditer(config_text):
        for token in m.group(1).split():
            pattern = token.strip()
            if not pattern.startswith("/"):
                pattern = f"{base_dir.rstrip('/')}/{pattern}"
            paths.extend(sorted(glob_fn(pattern)))
    return paths


@dataclass
class LocaleDoctorReport:
    issue: str
    explanation: str
    locale_env: dict = field(default_factory=dict)
    missing_locales: dict = field(default_factory=dict)
    active_charmap: Optional[str] = None
    sshd_accepts_locale_vars: Optional[bool] = None
    ssh_client_sends_locale_vars: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "issue": self.issue,
            "explanation": self.explanation,
            "locale_env": dict(self.locale_env),
            "missing_locales": dict(self.missing_locales),
            "active_charmap": self.active_charmap,
            "sshd_accepts_locale_vars": self.sshd_accepts_locale_vars,
            "ssh_client_sends_locale_vars": self.ssh_client_sends_locale_vars,
        }


def diagnose(
    locale_env: dict,
    installed_locales: list,
    active_charmap: Optional[str],
    sshd_config_text: Optional[str] = None,
    ssh_client_config_text: Optional[str] = None,
) -> LocaleDoctorReport:
    """Classify locale misconfiguration, in priority order: an unavailable
    installed-locale list (means the check itself is broken -- must not be
    silently treated as "everything requested is missing"); then a
    currently unsatisfiable requested locale (most directly explains a
    failure the user is already seeing); then a non-UTF-8 charmap (explains
    mojibake); then sshd accepting locale vars it can't guarantee (a latent
    risk rather than a proven failure) -- server-side risk is checked before
    client-side because a host actually receiving a bad forwarded locale
    over inbound SSH is a more directly actionable finding than this host's
    own outbound ssh_config merely being capable of forwarding one; then
    this host's own ssh_config sending locale vars outward (a latent risk
    to remote sessions, not a proven failure here); else none found."""
    sshd_accepts = sshd_accepts_locale(sshd_config_text) if sshd_config_text is not None else None
    ssh_client_sends = (
        ssh_client_sends_locale(ssh_client_config_text)
        if ssh_client_config_text is not None
        else None
    )

    if not installed_locales:
        return LocaleDoctorReport(
            issue=ISSUE_LOCALE_LIST_UNAVAILABLE,
            explanation=ISSUE_EXPLANATIONS[ISSUE_LOCALE_LIST_UNAVAILABLE],
            locale_env=locale_env,
            missing_locales={},
            active_charmap=active_charmap,
            sshd_accepts_locale_vars=sshd_accepts,
            ssh_client_sends_locale_vars=ssh_client_sends,
        )

    missing = find_missing_locales(locale_env, installed_locales)

    if missing:
        return LocaleDoctorReport(
            issue=ISSUE_UNSET_LOCALE_REQUESTED,
            explanation=ISSUE_EXPLANATIONS[ISSUE_UNSET_LOCALE_REQUESTED],
            locale_env=locale_env,
            missing_locales=missing,
            active_charmap=active_charmap,
            sshd_accepts_locale_vars=sshd_accepts,
            ssh_client_sends_locale_vars=ssh_client_sends,
        )

    if not charmap_is_utf8(active_charmap):
        return LocaleDoctorReport(
            issue=ISSUE_MISMATCHED_CHARMAP,
            explanation=ISSUE_EXPLANATIONS[ISSUE_MISMATCHED_CHARMAP],
            locale_env=locale_env,
            missing_locales=missing,
            active_charmap=active_charmap,
            sshd_accepts_locale_vars=sshd_accepts,
            ssh_client_sends_locale_vars=ssh_client_sends,
        )

    if sshd_accepts:
        return LocaleDoctorReport(
            issue=ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE,
            explanation=ISSUE_EXPLANATIONS[ISSUE_SSH_FORWARDS_UNKNOWN_LOCALE],
            locale_env=locale_env,
            missing_locales=missing,
            active_charmap=active_charmap,
            sshd_accepts_locale_vars=sshd_accepts,
            ssh_client_sends_locale_vars=ssh_client_sends,
        )

    if ssh_client_sends:
        return LocaleDoctorReport(
            issue=ISSUE_SSH_CLIENT_FORWARDS_LOCALE,
            explanation=ISSUE_EXPLANATIONS[ISSUE_SSH_CLIENT_FORWARDS_LOCALE],
            locale_env=locale_env,
            missing_locales=missing,
            active_charmap=active_charmap,
            sshd_accepts_locale_vars=sshd_accepts,
            ssh_client_sends_locale_vars=ssh_client_sends,
        )

    return LocaleDoctorReport(
        issue=ISSUE_NONE_FOUND,
        explanation=ISSUE_EXPLANATIONS[ISSUE_NONE_FOUND],
        locale_env=locale_env,
        missing_locales=missing,
        active_charmap=active_charmap,
        sshd_accepts_locale_vars=sshd_accepts,
        ssh_client_sends_locale_vars=ssh_client_sends,
    )


def diagnose_host(check_sshd_config: bool = True, runner=run) -> LocaleDoctorReport:
    locale_env = get_locale_env()
    installed = get_installed_locales(runner=runner)
    charmap = get_active_charmap(runner=runner)

    sshd_config_text = None
    ssh_client_config_text = None
    if check_sshd_config:
        for candidate in ("/etc/ssh/sshd_config",):
            text = read_file_if_exists(candidate, runner=runner)
            if text:
                sshd_config_text = text
                included = find_included_sshd_files(text)
                for inc_path in included:
                    inc_text = read_file_if_exists(inc_path, runner=runner)
                    if inc_text:
                        sshd_config_text += "\n" + inc_text
                break
        if sshd_config_text is None:
            sshd_config_text = ""

        ssh_client_config_text = read_file_if_exists("/etc/ssh/ssh_config", runner=runner)

    return diagnose(
        locale_env,
        installed,
        charmap,
        sshd_config_text=sshd_config_text,
        ssh_client_config_text=ssh_client_config_text,
    )
