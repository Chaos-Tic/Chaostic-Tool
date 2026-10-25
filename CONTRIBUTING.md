# Contributing

## Branches

`main` is the single public product branch for the CLI and Desktop application.
Use a short-lived branch for each focused change and remove it after merge.

During the shared-core refactor, focused branches target `refactor/shared-core`.
That integration branch targets `main` only after the CLI/Desktop and Linux/Windows
parity checks pass. Platform-specific code stays in explicit platform modules; the
catalog and core are shared. Never commit targets, run logs, personal configuration, virtual
environments, builds or downloaded binaries. Use isolated demo profiles for
screenshots.

## Validation

The full suite runs on Python 3.11, 3.12 and 3.14. Distributable builds cover
`windows-x64`, `windows-arm64`, `linux-x64`, `linux-arm64`, `macos-x64` and
`macos-arm64`; platform-specific behavior still requires the matching runner.

Run the commands in the edition's README. For Desktop, install
`requirements-build.txt`, set `QT_QPA_PLATFORM=offscreen`, run
`python -m unittest discover -s tests -v`, then `python scripts/check-docs.py`.
Build with `python scripts/build-desktop.py` and check the packaged application
with `python scripts/smoke-desktop.py`. POSIX tests skipped on Windows must run
on Linux. Unit tests do not certify every external tool or hardware device.

## Pull requests and protection

Protected public branches require pull requests, passing checks, an up-to-date branch
and resolved review discussions. Deletion and force pushes are blocked.
No bypass actors or external review approvals are required. Keep the names of
required checks aligned with the workflows when editing them.

Release publication is tag-only and is not a required PR check. Already-public
release assets must remain unchanged; a failed draft upload can be resumed and is
published only after all assets and checksums are present.
GitHub repository rules are separate from these files: a workflow rename may also
require a ruleset update.
