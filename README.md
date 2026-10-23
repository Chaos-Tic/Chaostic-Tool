<div align="center">

<img src="assets/icon.svg" alt="ChaosticTool circle and lightning icon in pastel glass" width="84" />

# ChaosticTool

### Linux pentest control surface for structured recon, tool orchestration, routing control, and target-based evidence capture

[![Version](https://img.shields.io/badge/version-1.5.0-ff3131?style=for-the-badge)](https://github.com/Chaos-Tic/Chaostic-Tool/releases/tag/v1.5.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-111827?style=for-the-badge&logo=python)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-Rich%20Terminal-ff3131?style=for-the-badge)](https://github.com/Textualize/rich)
[![Platform](https://img.shields.io/badge/platform-Linux-111827?style=for-the-badge&logo=linux)](#supported-systems)
[![License](https://img.shields.io/badge/license-MIT-111827?style=for-the-badge)](LICENSE)

ChaosticTool is a Rich-powered terminal framework for authorized security testing. It centralizes common pentest tools, guided scan flows, target-aware output storage, and Tor/VPN routing controls into one fast interactive CLI.

**[Installation Guide](INSTALLATION.md)** · **[All Releases](https://github.com/Chaos-Tic/Chaostic-Tool/releases)** · **[Desktop Version](https://github.com/Chaos-Tic/Chaostic-Tool/tree/desktop/linux-app)**

</div>

---

## Choose your edition

| Edition | Branch | Start here |
|---|---|---|
| Linux terminal | [`linux-cli`](https://github.com/Chaos-Tic/Chaostic-Tool/tree/linux-cli) | [Installation Guide](INSTALLATION.md) · Python 3.11+ |
| Windows desktop | [`desktop/windows-app`](https://github.com/Chaos-Tic/Chaostic-Tool/tree/desktop/windows-app) | [Desktop 1.3.0, Windows x64 / ARM64](https://github.com/Chaos-Tic/Chaostic-Tool/releases/tag/desktop-v1.3.0) |
| Linux desktop | [`desktop/linux-app`](https://github.com/Chaos-Tic/Chaostic-Tool/tree/desktop/linux-app) | [Desktop 1.3.0 downloads](https://github.com/Chaos-Tic/Chaostic-Tool/releases/tag/desktop-v1.3.0) · [Linux GUI setup](https://github.com/Chaos-Tic/Chaostic-Tool/blob/desktop/linux-app/README_DESKTOP_LINUX.md) |

The CLI and desktop branches have separate entry points and installation paths.
The repository-root `install.sh` installs the **CLI**. The installer inside a
Desktop Linux archive installs the **GUI**. Desktop 1.3.0 also includes macOS
packages for Intel and Apple Silicon, Linux AppImages and native DEB/RPM packages.
The CLI keeps its own version (1.5.0) and terminal experience.

## Terminal Interface

![ChaosticTool CLI terminal interface](docs/images/cli-dark.svg)

## What Is Chaostic Tool?

ChaosticTool is a pentesting framework for authorized assessments: an operator-first CLI built around real security testing workflows and fast iteration. It brings a broad set of reconnaissance, enumeration, scanning, exploitation-support, post-exploitation, password, wireless, and network tools into one structured terminal experience.

The goal is not to hide what the underlying tools do. The goal is to make them faster to launch, easier to organize, safer to route, and cleaner to document during an assessment.

ChaosticTool gives you:

- one target context shared across modules;
- curated presets for common attack and recon steps;
- guided attack flows for repeatable multi-tool chains;
- automatic result storage by target and category;
- Tor/proxy and VPN guard visibility before launching tools;

## Why ChaosticTool

Most security testing sessions become messy fast: repeated commands, scattered outputs, forgotten flags, and unclear routing state. ChaosticTool is built to keep the operator focused by turning a Linux workstation into a structured terminal control surface.

It does not replace the underlying tools. It orchestrates them cleanly.

## Core Features

- Rich-based terminal UI with a persistent HUD for target, route, proxy, and version state.
- Phase-based methodology: OSINT, network scan, web enum, vuln scan, exploitation, post-exploitation, passwords, wireless, and MITM.
- Ready-to-run presets for tools such as `nmap`, `rustscan`, `gobuster`, `ffuf`, `httpx`, `nuclei`, `sqlmap`, `hydra`, `bettercap`, and more.
- Target-aware result storage under `~/.local/share/chaostictool/targets/<target>/`.
- Guided attack flows for basic, intermediate, and advanced recon chains.
- Tor routing through `proxychains` where operationally appropriate.
- VPN guard for `tun*`, `wg*`, and `ppp*` interfaces.
- Live execution feedback, command launch panels, exit summaries, and saved-result indicators.
- Startup tool check with optional installation of missing dependencies.
- Clean interrupt handling: `Ctrl+C` stops the running tool without leaving ChaosticTool child processes behind.

## Supported Systems

ChaosticTool targets Linux distributions commonly used for security work:

| Family | Status | Notes |
| --- | --- | --- |
| Arch / Manjaro | Supported | Uses `pacman`; full profile builds AUR packages directly with `makepkg` after installing `pacman`, `git`, and `base-devel`. |
| Debian / Ubuntu | Supported | Uses `apt`. |
| Kali / Parrot | Supported | Debian-based workflow. |
| Fedora | Supported | Uses `dnf`. |

Several integrated tools require elevated privileges, so ChaosticTool is intended to run with `sudo`.

## Installation

Install ChaosticTool through your distribution's package manager or run it from a git checkout:

| Platform | Channel | Quick install command |
|---|---|---|
| **Debian / Ubuntu / Kali / Parrot** | Signed APT | `sudo apt install chaostictool` |
| **Arch / Manjaro** | AUR | `yay -S chaostictool` |
| **Fedora** | COPR | `sudo dnf copr enable chaostic/chaostictool && sudo dnf install chaostictool` |
| **Any Linux** | Source checkout | `git clone -b linux-cli https://github.com/Chaos-Tic/Chaostic-Tool.git && cd Chaostic-Tool && sudo ./install.sh` |

👉 For repository configuration, signing keys, offline `.deb` / `.rpm` packages, CMake source staging, installer profiles (`minimal`, `standard`, `full`), and uninstallation, see the complete **[Installation Guide](INSTALLATION.md)**.

## Quick Start

1. Launch ChaosticTool:

```bash
sudo chaostictool
```

2. Select `0` to configure a target.

3. Move through the methodology:

```text
1  OSINT & Passive Recon
2  Network Scan
3  Web Enumeration
4  Vulnerability Scan
5  Exploitation
6  Post-Exploitation & Privesc
7  Password Cracking
8  Windows / Active Directory
9  Wireless Security
10 Network & MITM
```

4. Use `11` to browse saved results.

5. Use `12` to run guided attack flows.

6. Use `p` to control Proxy / VPN / Tor routing.

Navigation:

```text
r / 0     back
Ctrl+C    interrupt the running tool
99        quit from main menu
```

## Routing Model

ChaosticTool is explicit about routing. The banner and each tool launch show the active route state:

```text
DIRECT
TOR via proxychains
VPN <interface>
VPN guard <interface> (default: <route>)
```

### Tor Mode

Tor mode wraps compatible internet-facing tools with `proxychains`. ChaosticTool avoids routing local, wireless, packet-capture, cracking, payload-generation, or network-interface tools through Tor when that would be operationally wrong or misleading.

The Tor menu can:

- enable Tor routing;
- check Tor service status;
- show the current Tor exit IP;
- rotate Tor identity;
- enable automatic rotation before every Tor-routed tool.

If ChaosticTool starts Tor itself, it stops that Tor service on exit or interrupt.

### VPN Guard

VPN mode does not force Linux traffic through a specific interface. The kernel routing table still decides. ChaosticTool acts as a guard:

- detects `tun*`, `wg*`, and `ppp*` interfaces;
- shows the selected VPN interface;
- warns when the default route is not using that interface.

## Result Storage

New results are stored outside the installation, in `~/.local/share/chaostictool/targets/` (or the XDG data directory). Legacy checkout results are preserved.

After target configuration, ChaosticTool creates a structured workspace:

```text
targets/
└── example.com/
    ├── osint/
    ├── recon/
    ├── web_enum/
    ├── vulnscan/
    ├── exploitation/
    ├── postexploit/
    ├── passwords/
    ├── wireless/
    └── network/
```

Example outputs:

```text
targets/example.com/osint/dig_a_example.com.txt
targets/example.com/recon/nmap_rapide_example.com.txt
targets/example.com/web_enum/ffuf_dir_example.com.txt
```

## Included Categories

| Category | Example tools |
| --- | --- |
| OSINT & Passive Recon | `whois`, `dig`, `subfinder`, `amass`, `dnsrecon`, `theHarvester`, `shodan` |
| Network Scan | `nmap`, `rustscan`, `masscan`, `naabu` |
| Web Enumeration | `gobuster`, `ffuf`, `httpx`, `wafw00f`, `whatweb`, `katana`, `gau`, `waybackurls` |
| Vulnerability Scan | `nikto`, `nuclei`, `wpscan`, `testssl.sh`, `sslscan` |
| Exploitation | `sqlmap`, `xsstrike`, `dalfox`, `metasploit`, `msfvenom` |
| Post-Exploitation | `linpeas`, `winpeas`, `impacket`, `crackmapexec`, `bloodhound-python` |
| Password Cracking | `hashcat`, `john`, `hydra` |
| Wireless Security | `airmon-ng`, `airodump-ng`, `aircrack-ng`, `reaver`, `wifite` |
| Network & MITM | `bettercap`, `ettercap`, `tcpdump`, `responder` |

## Project Structure

```text
chaostictool.py      # entry point, root check, main navigation
core/tools.py        # tool registry, presets, categories
core/ui.py           # Rich UI, menus, banner, startup checks
core/executor.py     # process execution, progress, output saving
core/proxy.py        # Tor, VPN guard, proxychains routing logic
core/installer.py    # dependency and tool installation resolver
core/target.py       # target normalization and result directories
core/session.py      # result browser and cleanup
core/flows.py        # guided attack flows
modules/             # category entry points
targets/             # empty in Git; local results are ignored
```

## Adding A Tool

Tool definitions live in `core/tools.py`.

```python
"my_tool": {
    "name": "My Tool",
    "binary": "my-tool",
    "desc": "Short description",
    "category": "recon",
    "output_dir": "recon",
    "requires_root": False,
    "presets": [
        {
            "label": "Quick scan",
            "cmd": ["my-tool", "{host}"],
            "output": "mytool_quick",
        },
    ],
}
```

Available placeholders:

```text
{host}
{url}
{port}
{wordlist}
```

Presets can also define custom prompt fields through `"prompt"`.

## Release

Current release: `v1.5.0`.

See releases: https://github.com/Chaos-Tic/Chaostic-Tool/releases

## License

MIT. See [LICENSE](LICENSE).

## Development and verification

Use an isolated Linux environment with Python 3.11 or later:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
bash -n install.sh uninstall.sh
python -m unittest discover -s tests -v
python scripts/check-docs.py
```

The tests import every phase, run local child processes, check captured output
and simulate configuration restoration in temporary folders. They do not install
pentest tools or scan external targets. Package availability, privileged routing,
wireless hardware and full installations require separate distro-specific tests.

See [contribution and branch rules](CONTRIBUTING.md).

## GitHub updater

CLI 1.5.0 checks the latest public release once per day in the background.
The release carries separate CLI and Desktop versions, so the editions do not
mistake one another's tags for an update. The request is anonymous: no target,
result, user identifier or access token is sent. GitHub sees the request IP address.

Use **u → Application updates** to check manually, change automatic checks, or
confirm an update through the package manager that owns this installation.
Nothing is downloaded or installed by the automatic check. Source checkouts link
to the release instructions; local changes are never reset automatically.

```sh
chaostictool --check-updates
chaostictool --update                 # displays commands, then asks for confirmation
chaostictool --no-update-check        # disable automatic checking for this launch
CHAOSTIC_UPDATE_CHECK=0 chaostictool  # environment override
```

The **u** menu saves the automatic-check preference in the user data directory.
The 1.4.0 release predates this updater; upgrade once through your package manager
to obtain it. See [update privacy and verification](SECURITY.md).
