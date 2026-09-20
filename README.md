# locale-doctor

[![English](https://img.shields.io/badge/English-555555?style=flat)](README.md) [![简体中文](https://img.shields.io/badge/%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555555?style=flat)](README.zh-CN.md)

Diagnose locale warnings and likely encoding mismatches in the current shell or SSH session. locale-doctor compares requested locales with the host's installed list, checks the active charmap and looks for SSH locale-forwarding risk—all read-only.

![locale-doctor example output](docs/images/example-output.png)

[Demo video](docs/demo.mp4)

## Requirements and installation

Python 3.9+ and a POSIX `locale` command. Linux is the primary target; environment and charmap checks can also run on macOS/BSD. No Python runtime dependencies.

```bash
git clone https://github.com/zhuhroscar-tech/locale-doctor.git
cd locale-doctor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Quick start

```bash
locale-doctor
locale-doctor --json
locale-doctor --no-sshd-check
```

Run it **inside the session showing the problem**: it reads that process's environment, not another user's login settings. It checks `LANG`, `LANGUAGE`, `LC_ALL` and known `LC_*` variables against `locale -a`, then examines the active charmap and optionally `/etc/ssh/sshd_config` (server-side `AcceptEnv`) and `/etc/ssh/ssh_config` (client-side `SendEnv`) -- both resolved together with any files they pull in via `Include` (e.g. the `/etc/ssh/sshd_config.d/*.conf` / `/etc/ssh/ssh_config.d/*.conf` drop-in layout that Debian/Ubuntu ship by default since OpenSSH 8.2).

Exit `0` means no issue was found by the performed checks. Exit `2` includes missing locales, non-UTF-8 charmap, forwarding risk (server `AcceptEnv` or client `SendEnv`) and an unavailable locale list. An `AcceptEnv`/`SendEnv` warning is a potential risk, not proof that a client sent (or a server received) an invalid locale.

For a no-install option, download `locale-doctor.pyz` from [releases](https://github.com/zhuhroscar-tech/locale-doctor/releases), verify the same release's `SHA256SUMS.txt`, then run `python3 locale-doctor.pyz`.

## Interpreting findings

For a missing locale, generate it using your distribution's tools or stop forwarding the unsupported value. For an encoding mismatch, select an installed UTF-8 locale. Review client `SendEnv` and server `AcceptEnv` together before changing SSH policy.

The tool never runs `locale-gen`, edits configuration, writes persistent state or makes network requests. An unreadable SSH config is skipped; unknown charmap data is not flagged. The SSH check is a text scan, not evaluation of effective `sshd` policy or all nested includes/conditional blocks. A clean result therefore does not prove every locale or SSH setting is correct. Review output before sharing it: it includes locale environment values.

## Development and removal

```bash
python -m pytest -q
python -m pip uninstall locale-doctor
```

[Releases](https://github.com/zhuhroscar-tech/locale-doctor/releases) · [MIT license](LICENSE)
