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

## API key storage

API keys (Shodan, WPScan, GitHub) are stored, in order of preference, in the
operating system's secret store through `keyring` (encrypted at rest by the OS),
or, only after the user accepts, in a `0600` file under the application data
directory. That file is encrypted with a user passphrase (PBKDF2-HMAC-SHA256 →
Fernet) when the optional `cryptography` library is installed; otherwise it is
base64-encoded but **not encrypted** and the interfaces say so. Without either,
keys stay in memory for the current session. Keys are injected into tool
environments only; a variable already set in the shell wins. See
[User guide §4](docs/USER_GUIDE.md#4-api-keys).
