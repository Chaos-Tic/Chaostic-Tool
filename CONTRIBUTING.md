# Contributing

## Three maintained branches

| Change | Pull request target |
|---|---|
| Terminal CLI, root installer and CLI guide | `linux-cli` (default branch) |
| Windows graphical application | `desktop/windows-app` |
| Linux graphical application and distro support | `desktop/linux-app` |

The homepage is maintained in the README of each edition. It does not need a
permanent documentation branch. Use short-lived branches for changes and remove
them after their pull requests are merged.

Keep common fixes synchronized with focused commits. The Desktop editions share
code, but their platform-specific changes should be reviewed on the matching
branch. Never commit targets, run logs, personal configuration, virtual
environments, builds or downloaded binaries. Use isolated demo profiles for
screenshots.

## Validation

CLI changes run on Python 3.11 and 3.14 and require the aggregate `cli-tests` gate.
Desktop changes require six platform checks: `windows-x64`, `windows-arm64`,
`linux-x64`, `linux-arm64`, `macos-x64` and `macos-arm64`.

Run the commands in the edition's README. For Desktop, install
`requirements-build.txt`, set `QT_QPA_PLATFORM=offscreen`, run
`python -m unittest discover -s tests -v`, then `python scripts/check-docs.py`.
Build with `python scripts/build-desktop.py` and check the packaged application
with `python scripts/smoke-desktop.py`. POSIX tests skipped on Windows must run
on Linux. Unit tests do not certify every external tool or hardware device.

## Pull requests and protection

The three maintained branches require pull requests, passing checks, an up-to-date
branch and resolved review discussions. Deletion and force pushes are blocked.
No bypass actors or external review approvals are required. Keep the names of
required checks aligned with the workflows when editing them.

Release publication is tag-only and is not a required PR check. Already-public
release assets must remain unchanged; failed draft publication can be resumed.
GitHub repository rules are separate from these files: a workflow rename may also
require a ruleset update.
