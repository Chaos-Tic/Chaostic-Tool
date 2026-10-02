# Repository rules and branch maintenance

The repository has three maintained branches: `linux-cli` (default),
`desktop/windows-app`, and `desktop/linux-app`. Documentation belongs to the
corresponding edition; other branches are temporary pull-request branches.

See [CONTRIBUTING](../CONTRIBUTING.md) for branch targets and local validation.

## Required checks

- `linux-cli`: `cli-tests`, aggregating the Python 3.11 and 3.14 tests.
- Both Desktop branches: `windows-x64`, `windows-arm64`, `linux-x64`,
  `linux-arm64`, `macos-x64`, and `macos-arm64`.

The rules require pull requests, passing checks on an up-to-date branch and
resolved discussions. Deletion and force pushes are blocked. No bypass actors
or external review approvals are required.

The `release` job is tag-only and must not be a required PR check. A workflow
rerun preserves published assets and can replace assets in an existing draft.

On 2026-10-02 the CLI's obsolete Desktop check requirements were replaced by
its own gate, and matching protection was added to the Desktop branches.
The old homepage proposal was incorporated into the CLI. The historical
Desktop-to-CLI integration PR was retired to keep the editions separate.

[Live repository rules](https://github.com/Chaos-Tic/Chaostic-Tool/rules).
