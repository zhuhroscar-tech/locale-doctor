# locale-doctor

Diagnose Linux locale misconfiguration — instead of manually reconciling
`locale`, `locale -a`, and SSH config files by hand.

## The problem

A decade-old, still-recurring Linux failure mode: `perl: warning:
Setting locale failed`, `locale: Cannot set LC_ALL to default locale`,
or mojibake (`??????` or garbled accented characters) over SSH. It
happens because the *client's* locale environment variables (`LANG`,
`LC_ALL`, `LC_*`) get forwarded over SSH (`SendEnv`/`AcceptEnv`) to a
*server* that doesn't have that locale installed or generated. Every
existing answer (AskUbuntu, Unix & Linux Stack Exchange, r/openbsd,
r/ProxmoxQA) walks the same multi-step manual diagnostic: read `locale`
output, check `locale -a` for what's actually installed, check
`/etc/ssh/ssh_config`'s `SendEnv` and `/etc/ssh/sshd_config`'s
`AcceptEnv`, and reconcile them by hand. No existing tool automates this
reconciliation into one command.

## What this does

```
$ locale-doctor

Issue: requested_locale_not_installed
One or more locale environment variables (LANG/LC_ALL/LC_*) request a
locale that is not present in this host's installed locale list (`locale
-a`). Programs that call setlocale() with this value will fail or
silently fall back to the 'C' locale, which is the direct cause of
'Setting locale failed' warnings from perl, Python, and other programs.

Current locale environment variables:
  LANG=en_US.UTF-8
  LC_TIME=de_DE.UTF-8 <-- requests an uninstalled locale

Active charmap: UTF-8
```

Checks performed, in priority order:

1. **Requested-but-uninstalled locale** — does any `LANG`/`LC_ALL`/`LC_*`
   environment variable name a locale not present in `locale -a`?
2. **Non-UTF-8 active charmap** — is the currently active locale's
   charmap something other than UTF-8 (the classic mojibake trigger)?
3. **sshd forwarding risk** — does `/etc/ssh/sshd_config`'s `AcceptEnv`
   accept `LANG`/`LC_*` from connecting clients at all (a latent risk:
   any client with an uninstalled locale set will trigger this failure)?

**Strictly read-only.** It never runs `locale-gen`, `dpkg-reconfigure
locales`, or modifies any SSH config file — it only reads environment
variables and config/command output.

## Install

Requires Python 3.9+ on Linux (uses `locale -a`; degrades gracefully —
and still works standalone — on macOS/BSD, though the SSH-specific
sshd_config check is Linux-oriented).

```bash
pip install locale-doctor
```

Or run the standalone zipapp with no install:

```bash
curl -LO https://github.com/zhuhroscar-tech/locale-doctor/releases/download/v0.1.0/locale-doctor.pyz
python3 locale-doctor.pyz --version
```

Verify the download against `SHA256SUMS.txt` in the same release before
running it.

## Usage

```bash
locale-doctor                  # diagnose the current shell's locale environment
locale-doctor --json           # machine-readable output
locale-doctor --no-sshd-check  # skip reading /etc/ssh/sshd_config (e.g. if unreadable)
```

Run it inside the actual SSH session where you're seeing the problem —
it inspects the *current process's* environment, which is exactly what
was forwarded (or not) by your SSH client/server.

Exit code `0` = no issue found, `2` = a locale issue was identified.

## If it finds a problem

This tool only diagnoses; it never modifies anything.

- `requested_locale_not_installed` → either generate the missing locale
  on this host (`locale-gen <name>` on Debian/Ubuntu, or
  `localedef`/`dpkg-reconfigure locales`), or stop forwarding it from
  the client: comment out `SendEnv LANG LC_*` in your local
  `/etc/ssh/ssh_config` or `~/.ssh/config`.
- `mismatched_charmap` → set the environment to an explicit `.UTF-8`
  locale that is actually installed (`export LC_ALL=C.UTF-8` or a
  proper `en_US.UTF-8`, etc.) rather than relying on whatever was
  forwarded.
- `ssh_forwards_uninstalled_locale_vars` → either comment out
  `AcceptEnv LANG LC_*` in `/etc/ssh/sshd_config` on the server (so
  clients can't push an unsupported locale), or ensure every locale
  your clients might send is actually generated on this host.

## Uninstall

```bash
pip uninstall locale-doctor
```
No config files, no persistent state — a stateless read-only diagnostic.

## Privacy / permissions

- No network access, no telemetry.
- Reads process environment variables, `locale -a`, `locale -k
  charmap`, and (optionally) `/etc/ssh/sshd_config`. Reading
  `sshd_config` typically requires root on a locked-down host; the tool
  degrades gracefully (`--no-sshd-check` skips it entirely) if
  unreadable.
- Writes nothing to disk.

## Distro / architecture support

Works on any POSIX system with a `locale` command (all mainstream Linux
distros, and macOS/BSD for the non-sshd-specific checks). Pure Python,
no compiled dependencies.

## Reproducible build / test

```bash
git clone https://github.com/zhuhroscar-tech/locale-doctor
cd locale-doctor
python3 -m pip install -e .[dev]
python3 -m pytest -v
```

CI (`.github/workflows/ci.yml`) runs the suite on real Ubuntu runners
across Python 3.9 and 3.12, then smoke-tests both the "no issue" path
and a deliberately-triggered missing-locale detection (`LC_TIME` set to
a nonexistent locale) against real `locale -a` output on the runner,
before building and verifying the wheel/sdist and a standalone `.pyz`.

## License

MIT — see [LICENSE](LICENSE).
