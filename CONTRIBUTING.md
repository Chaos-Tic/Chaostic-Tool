# Contributing

## Choose the correct base branch

| Change | Pull request target |
|---|---|
| Terminal CLI, root installer and CLI guide | `linux-cli` |
| Windows graphical application | `desktop/windows-app` |
| Linux graphical application and distro support | `desktop/linux-app` |

`docs/homepage-two-editions` is a documentation proposal for the CLI homepage,
not a separate edition. Its original Desktop 1.0.0 link is obsolete; the updated
CLI homepage includes the three maintained editions.

Keep common fixes synchronized with focused commits. Do not merge the entire
Desktop application into the CLI merely to satisfy unrelated build checks.
Never commit targets, run logs, personal configuration, virtual environments,
builds or downloaded binaries. Use isolated demo profiles for screenshots.

## Validation

Run the commands in the branch's README. Desktop changes also require
`python -m unittest discover -s tests -v` with `QT_QPA_PLATFORM=offscreen`,
then `python scripts/check-docs.py`. Build and smoke-test on each target OS
before publishing. POSIX tests skipped on Windows must run on Linux.

## Current GitHub protection mismatch

Verified on 2026-10-02: the `Protect linux-cli` ruleset still requires the six
Desktop build jobs, although the CLI branch has no Desktop application. The
homepage PR #2 therefore has no checks and is blocked. The CLI workflow in this
change introduces `cli-tests`; a maintainer must replace the six Desktop checks
with that gate for `linux-cli` before merging CLI-only contributions.

Keep the existing pull-request requirement, resolved discussions, strict
up-to-date policy, deletion protection and force-push protection. Desktop PRs
should use the six-platform workflow on their own base branches. Repository
settings are separate from files: adding this document does not change a ruleset.
