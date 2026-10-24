# Compatibility

[Back to the README](../README.md)

Only verified configurations are listed, with the test date and execution context.
"Disposable container" means a freshly provisioned container without persistent volume mounts
or pre-installed developer tools.

## Operating Systems

| Platform | Interface | Checked | Result | Date |
| --- | --- | --- | --- | --- |
| Debian 13 (Trixie), x86_64 | CLI & GUI | Native source package check, native package install, zero pip | pass | 2026-10-24 |
| Ubuntu 24.04 LTS, x86_64 | CLI & GUI | Full unittest suite (130 tests), headless X11, native package install | pass | 2026-10-24 |
| Ubuntu 22.04 LTS, x86_64 | CLI & GUI | Universal AppImage & CLI install via `./install.sh` | pass | 2026-10-24 |
| Arch Linux (rolling) | CLI & GUI | Native installation via `PKGBUILD` | pass | 2026-10-24 |
| Fedora 40 / 41 / Rawhide | CLI & GUI | RPM package install & smoke check in container | pass | 2026-10-24 |
| Windows 10 & 11 (x64) | CLI & GUI | Inno Setup installer & WSL2 Kali Linux backend | pass | 2026-10-24 |
| macOS 14 / 15 (Apple Silicon & Intel) | CLI | Terminal PTY and core unit tests | pass | 2026-10-24 |

## Offensive Profile Categories

| Phase | Core Tools Tested | Status |
| --- | --- | --- |
| **1. Discovery** | `nmap`, `rustscan`, `arp-scan`, `netdiscover` | Verified |
| **2. Web Surface** | `httpx`, `katana`, `feroxbuster`, `ffuf`, `gobuster` | Verified |
| **3. Exposure & Secrets** | `subfinder`, `amass`, `trufflehog`, `gitleaks` | Verified |
| **4. Active Directory** | `bloodhound-python`, `netexec` (nxc), `ldapdomaindump` | Verified |
| **5. Reporting & Intelligence** | Native JSON synthesis, markdown summaries, HTML audits | Verified |

## Package Formats

| Format | Channel | Target Distributions |
| --- | --- | --- |
| `.deb` | GitHub Releases & Chaos-Tic APT | Debian 12+, Ubuntu 22.04+ |
| `.rpm` | GitHub Releases & Fedora COPR | Fedora 39+, RHEL 9+, openSUSE |
| `PKGBUILD` | Arch User Repository (AUR) | Arch Linux, Manjaro, EndeavourOS |
| `.AppImage` | GitHub Releases | Universal Linux (GLIBC >= 2.35) |
| `.exe` (Inno Setup) | GitHub Releases | Windows 10 & 11 |
