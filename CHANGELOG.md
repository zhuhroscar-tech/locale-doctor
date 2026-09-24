# Changelog

## v0.1.10 — 2026-09-24

- Added release-history documentation and repository-contract checks so the project stays complete across future releases.
- Kept the shipped `locale-doctor.pyz`, wheel, sdist, and checksum release workflow documented from the README.

## v0.1.9 — 2026-09-24

- Modernized packaging license metadata to use a SPDX license string and `license-files`.
- Raised the setuptools build floor to a version that supports current license metadata.
- Added regression coverage for package metadata and version consistency.

## v0.1.8 — 2026-09-20

- Shipped release artifacts for the standalone `locale-doctor.pyz`, wheel, sdist, and checksums.
- Kept CI, CodeQL, and Linux smoke coverage for the package and zipapp paths.

## v0.1.7 — 2026-09-19

- Improved locale and SSH configuration diagnostics while preserving read-only behavior.
- Refined tests for the command-line and core analysis paths.

## v0.1.6 — 2026-09-18

- Updated documentation and release artifacts for the locale diagnostics workflow.
- Maintained package and zipapp smoke-test coverage.

## v0.1.5 — 2026-09-13

- Added user-facing documentation and examples for interpreting locale findings.
- Published refreshed release assets.

## v0.1.4 — 2026-09-13

- Improved CLI output consistency and style coverage.
- Published package artifacts for installation and no-install usage.

## v0.1.3 — 2026-09-12

- Expanded tests around locale environment parsing and reporting.
- Refined README guidance for running inside the affected session.

## v0.1.2 — 2026-09-12

- Fixed unavailable locale-list handling so the tool reports an honest unavailable state instead of treating every requested locale as missing.

## v0.1.1 — 2026-09-11

- Added early project polish, tests, and release assets after the initial public release.

## v0.1.0 — 2026-09-10

- Initial public release of `locale-doctor` for read-only locale, charmap, and SSH locale-forwarding diagnostics.
