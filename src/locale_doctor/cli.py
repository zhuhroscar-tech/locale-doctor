"""locale-doctor CLI."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import diagnose_host, ISSUE_NONE_FOUND
from .style import print_fields, resolve_style, status_headline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="locale-doctor",
        description=(
            "Diagnose Linux locale misconfiguration: requested locales not "
            "installed, non-UTF-8 charmap causing mojibake, and sshd "
            "accepting locale env vars it can't satisfy. Strictly "
            "read-only: never runs locale-gen or modifies any config."
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--no-sshd-check", action="store_true",
        help="Skip reading /etc/ssh/sshd_config (e.g. if unreadable without root).",
    )
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    return p


def _print_text(report, style) -> None:
    level = "ok" if report.issue == ISSUE_NONE_FOUND else "fail"
    print(status_headline(style, level, report.issue))
    print(report.explanation)
    if report.locale_env:
        print("\nCurrent locale environment variables:")
        rows = []
        for k, v in sorted(report.locale_env.items()):
            flag = " <-- requests an uninstalled locale" if k in report.missing_locales else ""
            rows.append((k, f"{v}{flag}"))
        print_fields(rows)
    if report.active_charmap:
        print(f"\nActive charmap: {report.active_charmap}")
    if report.sshd_accepts_locale_vars:
        print("\nsshd_config AcceptEnv includes locale variables (LANG/LC_*).")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    report = diagnose_host(check_sshd_config=not args.no_sshd_check)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        style = resolve_style(no_color_flag=args.no_color)
        _print_text(report, style)

    if report.issue == ISSUE_NONE_FOUND:
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
