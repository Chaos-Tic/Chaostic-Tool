<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="docs/media/banner.png">
    <img src="docs/media/banner-dark.png" alt="ChaosticTool — Security reconnaissance, orchestrated." width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Chaos-Tic/Chaostic-Tool/actions/workflows/ci.yml"><img src="https://github.com/Chaos-Tic/Chaostic-Tool/actions/workflows/ci.yml/badge.svg?branch=main" alt="Build and test status"></a>
  <a href="https://github.com/Chaos-Tic/Chaostic-Tool/releases"><img src="https://img.shields.io/badge/version-2.1.0-38bdf8.svg" alt="Version 2.1.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg" alt="GPL-3.0-or-later license"></a>
</p>

# ChaosticTool

**One reconnaissance pipeline. Terminal precision or liquid glass control.**

> *Why ChaosticTool?* In chaos theory, deterministic chaos demonstrates that
> intricate, unpredictable behaviors emerge from simple, interconnected rules.
> Fitting for a security tool by [Chaos-Tic](https://github.com/Chaos-Tic):
> orchestrating dozens of disjointed offensive primitives into structured,
> deterministic intelligence where chaotic attack surfaces resolve into clarity.

<p align="center">
  <picture><source media="(prefers-color-scheme: light)" srcset="docs/media/hero.gif"><img src="docs/media/hero-dark.gif" alt="ChaosticTool reconnaissance pipeline: target selection, offensive tool catalog, automated flow execution, real-time PTY terminal stream, and mission intelligence report" width="100%"></picture>
</p>

ChaosticTool bridges the gap between raw command-line auditing and graphical operations.
Whether you are auditing an external perimeter from an SSH bastion or leading an internal
Active Directory assessment from your workstation, ChaosticTool delivers the same unified
engine through two complementary interfaces:

- **Terminal Precision (`chaostictool`)**: Fullscreen Rich TUI navigator. Direct argument vectors, a real controlling pseudo-terminal (`pty`) for interactive tools — a typed Ctrl-C reaches the tool, not the TUI — and target-isolated local output.
- **Liquid Glass Desktop (`chaostictool-desktop`)**: Frosted-glass application with hardware-accelerated translucent surfaces (Light Pastel & Dark Neon palettes). Visual flow sequencing, live VT100 terminal monitor, and mission history management.

Everything runs strictly on your machine. No accounts, no telemetry, no cloud dependencies.
The only network request the application makes on its own is an anonymous, at most once-a-day
check for a newer GitHub release; switch it off in Desktop **Settings → About**, in the CLI
`u` menu, with `--no-update-check` or with `CHAOSTIC_UPDATE_CHECK=0`. Everything else that
touches the network — tool downloads, package installs, the tools themselves — runs only when
you ask for it. See [update behavior and privacy](docs/UPDATES.md).

**Version 2.1.0 is published.** Each tagged release builds the unified `.deb`, `.rpm`
and AppImage packages for Linux x64 and ARM64, the Windows installers (x64 and ARM64) and
the macOS disk images (Intel and Apple Silicon), attaches them with SHA-256 checksums to the
GitHub Release, and refreshes the AUR, Fedora COPR, the signed Chaos-Tic apt repository and
the Launchpad PPA. The winget manifests follow each release once the package is accepted in
`microsoft/winget-pkgs`.

[Project website](https://tool.chaostic.cloud/cybersecurite.html) · [Install](#install) · [Uninstall](#uninstall) · [How it works](#how-it-works) · [Phases and profiles](#phases-and-profiles) · [Architecture](docs/ARCHITECTURE.md) · [User guide](docs/USER_GUIDE.md) · [Compatibility](docs/COMPATIBILITY.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Verifying](docs/VERIFYING.md)

---

## How it works

<table>
<tr>
<td width="50%"><picture><source media="(prefers-color-scheme: light)" srcset="docs/media/liquid-glass-accueil.png"><img src="docs/media/liquid-glass-accueil-dark.png" alt="Target selector and reconnaissance dashboard"></picture></td>
<td width="50%"><picture><source media="(prefers-color-scheme: light)" srcset="docs/media/liquid-glass-execution.png"><img src="docs/media/liquid-glass-execution-dark.png" alt="Real-time PTY terminal execution with ANSI color output"></picture></td>
</tr>
<tr>
<td><b>1. Scope & Target.</b> Define domains, IPv4/IPv6 addresses, CIDR blocks, or URLs. Targets are validated and isolated in private local storage without launching unwanted connections.</td>
<td><b>2. Orchestrated Execution.</b> Launch individual profiles or chained flows. Interactive tools run in dedicated pseudo-terminals with real-time output and instant cancellation.</td>
</tr>
<tr>
<td width="50%"><picture><source media="(prefers-color-scheme: light)" srcset="docs/media/liquid-glass-arsenal.png"><img src="docs/media/liquid-glass-arsenal-dark.png" alt="The shared security tool catalog classified across ten structured phases"></picture></td>
<td width="50%"><picture><source media="(prefers-color-scheme: light)" srcset="docs/media/liquid-glass-historique.png"><img src="docs/media/liquid-glass-historique-dark.png" alt="Mission report and structured run logs"></picture></td>
</tr>
<tr>
<td><b>3. Shared tool arsenal.</b> Forty-six CLI tools and 137 launch profiles are categorized across ten phases; Desktop adds four built-in utilities and platform adapters.</td>
<td><b>4. Intelligence & Audit.</b> Review parsed findings, inspect raw chunk logs, or export structured JSON reports. Atomic history clearing prevents symlink directory traversal.</td>
</tr>
</table>

---

## Two Interfaces, One Shared Core

ChaosticTool is converging both interfaces on one registry, one phase list derived from
the tool catalog, one release model and one UI-independent process runner. Cross-adapter
tests prove matching success, failure, literal argv, large-output, cancellation, timeout
and streamed-redaction behaviour. Attack flows (the three built-in chains plus custom
flows) exist on both sides; Tor/proxychains routing and the VPN guard remain CLI-only.

| Capability | Terminal Precision CLI / TUI (`chaostictool`) | Liquid Glass Desktop GUI (`chaostictool-desktop`) |
| --- | --- | --- |
| **Primary Environment** | Headless servers, SSH sessions, minimal containers, Linux terminals | Graphical workstations (Linux X11/Wayland & Windows; a macOS disk image is built but unsigned and not notarized) |
| **Interface Style** | Rich terminal TUI dashboard & direct shell commands | Frosted glass with light pastel & dark neon themes |
| **Execution Sandboxing** | A real controlling POSIX `pty` per interactive tool: Ctrl-C is delivered to the tool, terminal settings are restored, zero orphan processes | Integrated VT100 terminal widget with ANSI color emulation |
| **Routing Controls** | Persistent HUD: Direct, Tor (with auto-rotation), and VPN guard | Not exposed yet; GUI routing controls are tracked work |
| **Automation & CI** | Interactive TUI; machine-readable profile execution is tracked work | Visual chained flow designer with step dependencies |
| **Windows Support** | Linux CLI through WSL2 | Native installer with automated WSL2 Kali Linux backend |

---

### Terminal Precision CLI (`chaostictool`)

A high-density terminal control surface built with Rich and prompt_toolkit for keyboard-first security operators and headless environments:

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="docs/media/cli-light.png">
    <img src="docs/media/cli-dark.png" alt="ChaosticTool Terminal Precision CLI: interactive Rich TUI dashboard with live telemetry, kill-chain phases, and action dock" width="800">
  </picture>
</p>

- **Live Workspace HUD**: Always-visible status header tracking active target, routing interface (`DIRECT`, `TOR via proxychains`, `VPN`), and target-isolated output directories.
- **Kill-Chain Methodology**: 10 offensive categories organized into structured phases (OSINT, Network Scan, Web Enumeration, Vulnerability Scan, Exploitation, Post-Exploit, Password Cracking, Windows / Active Directory, Wireless, Network & MITM).
- **Direct Action Dock**: Short keys for target configuration (`[0]`), tool catalog search (`[/]`), the results & session browser (`[11]`), guided attack flows (`[12]`), Proxy/VPN/Tor routing controls (`[p]`), wordlists (`[w]`), API keys (`[k]`) and application updates (`[u]`).
- **Terminal-first operation**: Launch the interactive TUI without a graphical session and use the maintenance checks independently:
  ```bash
  # Launch the interactive terminal control surface
  sudo chaostictool

  # Check the installed runtime without network access or root
  chaostictool --check-installation

  # Check for updates from GitHub releases, or propose the package update
  chaostictool --check-updates
  chaostictool --update

  # Print the installed version
  chaostictool --version
  ```

---

### Liquid Glass Desktop (`chaostictool-desktop`)

A fluid desktop application crafted with the Chaos-Tic frosted-glass aesthetic for graphical Linux workstations and Windows (a macOS disk image is also built; it is unsigned and not notarized, see [Compatibility](docs/COMPATIBILITY.md)):

<p align="center">
  <img src="docs/media/liquid-glass-dark.png" alt="ChaosticTool Liquid Glass Desktop dashboard in its primary dark cybersecurity theme" width="800">
</p>

- **Frosted-Glass Visual Language**: Translucent layered cards, inner reflections, and dual palettes (Light Pastel & Dark Neon) with high-contrast sans-serif typography and reduced-transparency accessibility.
- **Visual Flow Orchestration**: Sequence multi-tool recon and audit workflows with automatic parameter propagation and dependency checks.
- **Integrated VT100 Terminal Monitor**: Watch live tool execution in an embedded terminal emulator with full ANSI styling, elapsed timers, and clean cancellation.
- **Cross-Platform Distribution**: One unified `chaostictool` package is built for Debian/Ubuntu and Fedora (x64 and ARM64), alongside the Arch recipe, AppImages, Windows installers (x64 and ARM64) and macOS disk images. See the dated compatibility table for what CI actually verifies and the installation guide for channel availability.

---

## Phases and Profiles

ChaosticTool shares one ordered set of ten phases across both interfaces:

| Phase | Core Objective | Integrated Profiles |
| --- | --- | --- |
| **01. OSINT** | Passive discovery and public records | `whois`, `dig`, `subfinder`, `amass`, `dnsrecon`, `theHarvester`, `shodan` |
| **02. Network scan** | Host, port and service discovery | `nmap`, `rustscan`, `masscan`, `naabu` |
| **03. Web enumeration** | HTTP probing, crawling and content discovery | `gobuster`, `ffuf`, `httpx`, `wafw00f`, `whatweb`, `katana`, `gau`, `waybackurls` |
| **04. Vulnerabilities** | Web, TLS and template-based checks | `nikto`, `nuclei`, `wpscan`, `testssl.sh`, `sslscan` |
| **05. Exploitation** | Explicitly selected exploitation workflows | `sqlmap`, `xsstrike`, `dalfox`, `msfconsole`, `msfvenom` |
| **06. Post-exploitation** | Credential dumping and remote execution | Impacket `secretsdump.py` and `psexec.py`, `NetExec` (`nxc`, ex-CrackMapExec) |
| **07. Passwords** | Offline and online password auditing | `hashcat`, `john`, `hydra` |
| **08. Windows / AD** | Kerberoasting and Active Directory graph collection | Impacket `GetUserSPNs.py`, `bloodhound-python` |
| **09. Wi-Fi** | Wireless discovery and authorized auditing | Aircrack-ng tools, `reaver`, `wifite` |
| **10. Network & MITM** | Packet capture and authorized local-network testing | `bettercap`, `ettercap`, `tcpdump`, `responder` |

---

## Install

ChaosticTool 2.x is published to the channels below — pick the one for your system.
Each tagged release updates them automatically; upgrades then flow through `yay -Syu`,
`dnf upgrade` or `apt upgrade` on the configured channel. Every channel installs the same
unified `chaostictool` package: the `chaostictool` CLI, `chaostictool-desktop` and the
`chaostictool-uninstall` command (see [Uninstall](#uninstall)). The application itself
installs none of the external security tools; the CLI offers to install the missing ones
on first use and records what it adds.

### Arch Linux (AUR)
```bash
# Unified CLI + Desktop package
yay -S chaostictool
```

### Fedora / Red Hat (COPR)
```bash
sudo dnf copr enable chaostic/chaostictool
sudo dnf install chaostictool
```

### Debian / Ubuntu
Download the native `.deb` from [Releases](https://github.com/Chaos-Tic/Chaostic-Tool/releases):
```bash
sudo apt install ./chaostictool_2.1.0_amd64.deb
```
Or, recommended, via the Chaos-Tic signed APT repository (auto-updating):
```bash
sudo curl -fsSLo /usr/share/keyrings/chaos-tic.gpg https://chaos-tic.github.io/apt/chaos-tic-apt.gpg
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/chaos-tic.gpg] https://chaos-tic.github.io/apt stable main' | sudo tee /etc/apt/sources.list.d/chaos-tic.list
sudo apt update && sudo apt install chaostictool
```

### Ubuntu (Launchpad PPA)
```bash
sudo add-apt-repository ppa:chaos-tic/chaostictool
sudo apt update && sudo apt install chaostictool
```

### Universal Linux (AppImage)
```bash
chmod +x ChaosticTool-2.1.0-linux-x64.AppImage
./ChaosticTool-2.1.0-linux-x64.AppImage
```
An `-linux-arm64` AppImage is published for 64-bit ARM. Without FUSE, run it with
`APPIMAGE_EXTRACT_AND_RUN=1`.

### Windows 10 & 11
Download `ChaosticTool-Setup-2.1.0-windows-x64.exe`
from [Releases](https://github.com/Chaos-Tic/Chaostic-Tool/releases) (a `-windows-arm64`
installer is published for Windows 11 on ARM). The installer sets up the desktop launcher
and offers an automated Kali Linux WSL2 integration for running Linux-native security
utilities. The installer carries no Windows publisher signature, so SmartScreen may warn;
compare the SHA-256 from the release page instead of lowering your protections. Full
walkthrough: [Windows guide](README_WINDOWS.md).

Once the package is accepted in `microsoft/winget-pkgs`, the Windows Package Manager
installs and updates it too:
```powershell
winget install ChaosTic.ChaosticTool
winget upgrade ChaosTic.ChaosticTool
```

### macOS 13+ (Intel and Apple Silicon)
Download the `.dmg` for your processor from [Releases](https://github.com/Chaos-Tic/Chaostic-Tool/releases)
and drag ChaosticTool into Applications. The disk image is built and smoke-tested in CI but is
not signed or notarized, so Gatekeeper may block the first launch; macOS is not a verified
platform yet. Details: [cross-system Desktop guide](docs/DESKTOP.md).

### Build from Source
```bash
git clone https://github.com/Chaos-Tic/Chaostic-Tool.git
cd Chaostic-Tool

# Install Python dependencies
pip install -r requirements.txt -r requirements-desktop.txt

# Run the interactive CLI directly
sudo python chaostictool.py

# Run Desktop directly
python chaostic_desktop.py

# Install the CLI runtime system-wide and (optionally) the external tools;
# everything it adds is recorded in /var/lib/chaostictool/manifest
sudo ./install.sh                    # fast profile: official distro packages only
sudo ./install.sh --profile full     # also Go/Cargo/pipx/pip/gem/source tools and Tor routing

# Or stage the whole tree with CMake (binaries, launcher, icons, licence, uninstaller)
cmake -B build -DCMAKE_INSTALL_PREFIX=/usr
sudo cmake --install build
DESTDIR="$PWD/staging" cmake --install build   # package-style staging, host untouched

# Or build the native packages (.deb, .rpm)
cpack --config build/CPackConfig.cmake -G "DEB;RPM" -B release
```
See the [native installation guide](docs/INSTALLATION.md) for dependencies and channel status.

---

## Uninstall

Removing ChaosticTool is a two-level operation, because the application and the external
security tools it can install for you are different things.

**1. Remove what ChaosticTool installed on the host.** Every native package ships the
`chaostictool-uninstall` command (a source checkout has the same script as
`./uninstall.sh`). It reverses *exactly* what ChaosticTool recorded in
`/var/lib/chaostictool/manifest` — distro packages, Go/Cargo/pipx/pip/gem installs,
wrapper files and symlinks, extra package sources, Tor/proxychains edits — and nothing else.
A tool that was already on the system before ChaosticTool touched it is never recorded,
so it is never removed, and a path that exists but is not in the manifest is left alone.

```bash
sudo chaostictool-uninstall --dry-run           # print the full plan, change nothing
sudo chaostictool-uninstall                     # interactive: confirm each group
sudo chaostictool-uninstall --yes               # no prompts for the recorded removals
sudo chaostictool-uninstall --remove-packages   # also remove the distro packages it added
                                                # (pacman -Rns / apt purge --autoremove / dnf remove)
sudo chaostictool-uninstall --force-detect      # no manifest (pre-1.3.2 install): heuristic mode
```

Run it **before** removing the package, since the command is shipped by the package.
Without `--remove-packages` the distro packages stay installed and the manifest is kept,
reduced to those entries, so a later `--remove-packages` still knows what to offer.
`--yes` never turns on the heuristic detection mode; `--force-detect` is the only way to
remove anything without a manifest, and `--dry-run` is a true no-op in every mode.

**2. Remove the application.** Use your package manager as usual:

```bash
sudo pacman -Rns chaostictool      # Arch
sudo dnf remove chaostictool       # Fedora
sudo apt remove chaostictool       # Debian / Ubuntu
```

Package removal never deletes the external tools: if the manifest still lists items, the
`prerm`/`%preun`/`pre_remove` scriptlet prints a notice naming them and pointing back to
step 1 (reinstall and run `chaostictool-uninstall`, or run `sudo ./uninstall.sh` from a
checkout). User data — targets, results, settings — lives in the user data directory and
is kept by both steps. Windows: *Settings → Apps → ChaosticTool Desktop → Uninstall*;
macOS: drag the application out of Applications.

---

## Security & Privacy Discipline

ChaosticTool adheres to the privacy and security principles of the [Chaos-Tic](https://github.com/Chaos-Tic) ecosystem:

- **Local-First Execution**: Findings, credentials, and targets are never uploaded to any cloud service.
- **Sensitive-data boundaries**: Desktop and CLI mask configured secret fields in command
  previews and streamed values before persistence, including values split across output
  chunks. Operators must still treat all local logs as sensitive.
- **Safe Directory Operations**: The storage manager enforces strict filesystem boundaries, rejecting symbolic link traversal or directory junctions during log deletion (`CVE-resistant cleanup`).
- **No Shell Interpolation**: Subprocesses are spawned directly using explicit argument arrays, preventing command-injection attacks through untrusted target names.
- **Reversible installation**: Every tool, package, file or system edit ChaosticTool adds is recorded in a root-owned manifest and can be reviewed (`--dry-run`) and reversed with `chaostictool-uninstall`; pre-existing tools are never touched.

---

## Documentation

- **[Native installation](docs/INSTALLATION.md)**: Package dependencies, CMake source installation, repository channels and winget.
- **[Windows guide](README_WINDOWS.md)**, **[Linux CLI](README_LINUX.md)** and **[Linux Desktop](README_DESKTOP_LINUX.md)**: Platform walkthroughs.
- **[Cross-system Desktop guide](docs/DESKTOP.md)**: Windows, Linux and macOS downloads, Linux backends (local, WSL, SSH) and data locations.
- **[Architecture & Internals](docs/ARCHITECTURE.md)**: Process model, PTY backend, install manifest, and source map.
- **[User Guide](docs/USER_GUIDE.md)**: Command reference, flags, desktop walkthrough, API keys and theme controls.
- **[Compatibility Matrix](docs/COMPATIBILITY.md)**: Dated CI evidence per platform, catalogue coverage, and package channels.
- **[GitHub updates](docs/UPDATES.md)**: What the once-a-day release check sends, how to disable it, how updates are applied.
- **[Testing & CI](docs/TESTING.md)**: Unit tests, headless X11 visual contracts, and clean container validation.
- **[Troubleshooting](docs/TROUBLESHOOTING.md)**: Resolutions for common environment, permission, and terminal issues.
- **[Verifying Checksums](docs/VERIFYING.md)**: SHA-256 checksum verification for every release asset (checksums are not a publisher signature).

---

## License

Copyright (c) 2026 Chaos-Tic. This source tree is licensed under
**GPL-3.0-or-later** ([LICENSE](LICENSE)). Releases published before this change remain
available under the license that accompanied them; the change is not retroactive.
The project name and logo are governed separately by the
[trademark policy](TRADEMARKS.md).
