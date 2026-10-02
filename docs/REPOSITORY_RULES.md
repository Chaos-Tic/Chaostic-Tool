# Repository rules and branch maintenance

See [CONTRIBUTING](../CONTRIBUTING.md) for branch targets, validation and the
current mismatch between CLI protection and Desktop build checks.

As verified on 2026-10-02, `linux-cli` is the default branch. `main` no longer
exists remotely. The active ruleset prevents deletion and force pushes, requires
pull requests and resolved discussions, and currently requires six Desktop jobs.
No bypass actors are configured and no external approval is required.

The Desktop branches are independent editions; contributions should target the
matching branch. The old Desktop PR #1 targets `linux-cli` and is an integration
proposal, not the normal route for Desktop maintenance.

The `release` job is tag-only and must not be a required PR check. A release
workflow rerun must preserve already-published assets. Draft assets may be
replaced when resuming a failed build publication.

[Live ruleset](https://github.com/Chaos-Tic/Chaostic-Tool/rules/24086485).
