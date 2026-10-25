# Compatibility

[Back to the README](../README.md)

Evidence reviewed on **2026-10-25**: [successful CI run for `e0709eb`](https://github.com/Chaos-Tic/Chaostic-Tool/actions/runs/40133873560)
and the [workflow](../.github/workflows/ci.yml). The table describes automated checks
at that revision. It does not establish that every external tool, desktop session,
or published package repository works on each operating system. Changes after that
revision need their own passing checks.

## Automated coverage

| Execution context | Checks in CI | Scope and limits |
| --- | --- | --- |
| Ubuntu 24.04 runner, x64; Python 3.11, 3.12 and 3.14 | Unit/integration suite; isolated X11 UI checks; documentation links | Source tests with Qt offscreen or Xvfb; no KDE/GNOME/Wayland session coverage |
| Debian Trixie container, x64 | Build source packages with distro dependencies, install, Desktop diagnostic smoke test, remove | No pip dependencies in this check; no complete CLI/GUI functional parity claim |
| Ubuntu 22.04 x64 and Ubuntu 24.04 ARM64 runners; Python 3.14 | Tests, frozen application build/smoke test, user-local installation/removal, AppImage extraction and smoke test, DEB/RPM generation | Headless diagnostic checks; AppImage tested without FUSE |
| Debian Trixie, Ubuntu 24.04, Fedora 43 and Fedora 44 containers, x64 | Install the generated DEB/RPM, run Desktop diagnostic smoke test, remove | Packages downloaded from the build job; no installation from APT/PPA/COPR repositories |
| Windows Server 2022 x64 and Windows 11 ARM64 runners; Python 3.14 | Applicable tests, frozen application and installer build, diagnostic smoke test, installer/shortcut identity and removal checks | No Windows 10 validation; WSL/Kali setup and real Linux tool execution are not exercised end to end |
| macOS 15 Intel and Apple Silicon runners; Python 3.14 | Applicable tests, application/DMG build, packaged diagnostic smoke test | No interactive DMG installation, signing/notarization or macOS 14 validation |

Platform-specific tests can be skipped: Linux PTY tests run on Linux, and POSIX CLI
regression tests do not run on Windows. The native CLI requires a POSIX environment;
Windows Desktop uses native tools where supported and a configured Linux backend
(WSL or SSH) for Linux profiles. Native Windows CLI parity is not established.

Containers are disposable and mount the checkout or package directory read-only.
They verify package and process behaviour, not a complete desktop or real hardware.
Arch/AUR, openSUSE, other distributions and desktop sessions need separate installation
and runtime evidence before being marked verified.

## Catalogue coverage

The shared registry contains **48 CLI tools and 137 CLI profiles**, organized in the
same **ten phases** used by Desktop. Desktop adds four built-in utilities, for
**52 catalogue entries**. Native adapters may add or adapt forms; catalogue presence
is not proof that a tool is installed or operational on a platform.

| Phase | Shared category |
| --- | --- |
| 01 | OSINT & passive reconnaissance |
| 02 | Network scan |
| 03 | Web enumeration |
| 04 | Vulnerabilities |
| 05 | Exploitation |
| 06 | Post-exploitation & privileges |
| 07 | Passwords |
| 08 | Windows / Active Directory |
| 09 | Wi-Fi |
| 10 | Network & MITM |

Tests select graphical profiles and construct their argument vectors. They do not
run every offensive operation against targets, install every tool, or verify live
Active Directory, Wi-Fi capture, GPU cracking, Tor/VPN routing or remote SSH setups.
See the [Desktop catalogue](WINDOWS_PORT.md) for per-tool forms and requirements.

## Distribution formats

| Format | CI evidence | Remaining validation |
| --- | --- | --- |
| `.deb` | Generated for x64/ARM64; x64 installation smoke tests on Debian Trixie and Ubuntu 24.04 | Other Debian/Ubuntu releases, ARM64 package installation, published APT/PPA channels |
| `.rpm` | Generated for x64/ARM64; x64 installation smoke tests on Fedora 43/44 | Other Fedora releases, RHEL, openSUSE, ARM64 installation, published COPR channel |
| `.tar.gz`, `.AppImage` | Linux x64/ARM64 bundle install/remove and extracted AppImage smoke checks | Other distributions, FUSE launch, desktop session integration |
| `.exe` | x64/ARM64 installer and shortcut checks on the Windows runners above | Consumer Windows 10/x64 Windows 11 and real WSL/Kali workflows |
| `.dmg` | Intel/Apple Silicon build and application smoke checks on macOS 15 | Interactive installation, signing and notarization |
| `PKGBUILD` | Arch packaging recipes are present | Clean Arch build/install/remove and published AUR installation |

A release upload or a successful publication job alone does not verify installation
from a distribution repository. External tools retain their own platform, service,
privilege and hardware requirements.
