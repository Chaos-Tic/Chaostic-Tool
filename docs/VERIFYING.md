# Verifying Releases

[Back to the README](../README.md)

Every release published by [Chaos-Tic](https://github.com/Chaos-Tic/Chaostic-Tool) includes
SHA-256 checksums to verify file integrity against the manifest downloaded from the
same release. A checksum is not a publisher signature and does not independently prove
who produced the file.

## SHA-256 Checksums

Each release contains a `SHA256SUMS` file covering all installer packages:
- Linux packages (`.deb`, `.rpm`, `.AppImage`, `.tar.gz`)
- Windows installers (`.exe`, `.zip`)
- macOS bundles (`.dmg`, `.tar.gz`)

### Verifying on Linux / macOS:
```bash
# Download the release asset and SHA256SUMS
curl -fsSL -O https://github.com/Chaos-Tic/Chaostic-Tool/releases/download/v2.0.0/SHA256SUMS
curl -fsSL -O https://github.com/Chaos-Tic/Chaostic-Tool/releases/download/v2.0.0/ChaosticTool-2.0.0-linux-x64.AppImage

# Verify the file against the checksum manifest
sha256sum --check --ignore-missing SHA256SUMS
```

### Verifying on Windows (PowerShell):
```powershell
Get-FileHash .\ChaosticTool-Setup-2.0.0-windows-x64.exe -Algorithm SHA256
```

Compare the computed hash against the value published in `SHA256SUMS`.
