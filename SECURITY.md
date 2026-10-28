# Security policy

## Supported versions

Security fixes target the latest published release. Older releases may not receive fixes; update to the latest version before reporting when possible.

## Reporting a vulnerability

Please report security issues privately using [GitHub security advisories](https://github.com/Chaos-Tic/Chaostic-Tool/security/advisories/new). Avoid public issues for undisclosed vulnerabilities. Include the affected version, platform, impact, and the minimum information needed to reproduce the issue. Do not include real credentials or sensitive assessment data. Response times depend on maintainer availability.

## Update privacy and verification

See [GitHub updates](docs/UPDATES.md) for the request, cache, opt-out controls and
installation behavior. The automatic request is anonymous, contains no assessment
data and runs at most once per day. GitHub sees the request IP address.

No download or installation starts without user confirmation. Downloaded installers
must match the exact release's SHA-256; failed or cancelled downloads are discarded.
Linux packages use their existing system channel. AppImage replacement keeps a
backup and is atomic. Source checkouts are never reset by the updater.

Checksums protect file integrity and do not replace OS publisher signatures.
