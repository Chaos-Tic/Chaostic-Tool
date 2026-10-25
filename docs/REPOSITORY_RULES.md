# Repository rules and branch maintenance

`main` is the protected release branch. `refactor/shared-core` is the temporary
integration branch for the 2.x convergence work; feature and fix branches target it
until the shared runner, packages and parity scenarios are ready to merge into `main`.
There are no longer separate maintained branches for each interface or operating system.

See [CONTRIBUTING](../CONTRIBUTING.md) for branch targets and local validation.

## Required checks

The workflow exercises source tests on Python 3.11, 3.12 and 3.14, native UI
contracts, source packaging, six Desktop OS/architecture builds and Linux package
installation. Branch protection should require the current aggregate checks on both
`main` and the active integration branch; exact check names must match the live rules.

The rules require pull requests, passing checks on an up-to-date branch and
resolved discussions. Deletion and force pushes are blocked. No bypass actors
or external review approvals are required.

The `release` job is tag-only and must not be a required PR check. A workflow
rerun preserves published assets and can replace assets in an existing draft.

The tag-only release and publication jobs are not pull-request gates. A release is
published only after its verified assets have been uploaded; reruns may replace assets
in an existing draft before publication.

[Live repository rules](https://github.com/Chaos-Tic/Chaostic-Tool/rules).
