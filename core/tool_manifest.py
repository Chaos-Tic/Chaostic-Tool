"""Canonical installation contract for every tool in the shared catalog.

This first A4 layer is declarative: existing installers keep their behaviour while
tests enforce one normalized record per catalog tool and platform.  Artifact and
distribution data are projected from the current verified sources until A3 makes
this module their only input.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from core.tools import TOOLS

# Canonical distribution-package names. The standalone Linux bridge keeps a
# generated-compatible copy until A3 makes it consume generated data directly.
PACKAGE_NAMES = MappingProxyType({
    "apt": MappingProxyType({
        "whois": "whois", "dig": "dnsutils", "subfinder": "subfinder",
        "amass": "amass", "dnsrecon": "dnsrecon", "theharvester": "theharvester",
        "shodan": "python3-shodan", "nmap": "nmap", "rustscan": "rustscan",
        "masscan": "masscan", "naabu": "naabu", "gobuster": "gobuster",
        "ffuf": "ffuf", "httpx": "httpx-toolkit", "wafw00f": "wafw00f",
        "whatweb": "whatweb", "katana": "katana", "gau": "getallurls",
        "waybackurls": "waybackurls", "nikto": "nikto", "nuclei": "nuclei",
        "wpscan": "wpscan", "testssl.sh": "testssl.sh", "sslscan": "sslscan",
        "sqlmap": "sqlmap", "xsstrike": "xsstrike", "dalfox": "dalfox",
        "msfconsole": "metasploit-framework", "msfvenom": "metasploit-framework",
        "secretsdump.py": "impacket-scripts",
        "psexec.py": "impacket-scripts", "GetUserSPNs.py": "impacket-scripts",
        "crackmapexec": "netexec", "bloodhound-python": "bloodhound.py",
        "hashcat": "hashcat", "john": "john", "hydra": "hydra",
        "airmon-ng": "aircrack-ng", "airodump-ng": "aircrack-ng",
        "aircrack-ng": "aircrack-ng", "reaver": "reaver", "wifite": "wifite",
        "bettercap": "bettercap", "ettercap": "ettercap-text-only",
        "tcpdump": "tcpdump", "responder": "responder",
    }),
    "pacman": MappingProxyType({
        "whois": "whois", "dig": "bind", "shodan": "python-shodan",
        "nmap": "nmap", "rustscan": "rustscan", "masscan": "masscan",
        "gobuster": "gobuster", "wafw00f": "wafw00f", "nikto": "nikto",
        "wpscan": "wpscan", "testssl.sh": "testssl.sh", "sslscan": "sslscan",
        "sqlmap": "sqlmap", "msfconsole": "metasploit", "msfvenom": "metasploit",
        "secretsdump.py": "python-impacket", "psexec.py": "python-impacket",
        "GetUserSPNs.py": "python-impacket", "hashcat": "hashcat",
        "john": "john", "hydra": "hydra", "airmon-ng": "aircrack-ng",
        "airodump-ng": "aircrack-ng", "aircrack-ng": "aircrack-ng",
        "reaver": "reaver", "wifite": "wifite", "bettercap": "bettercap",
        "ettercap": "ettercap", "tcpdump": "tcpdump",
    }),
    "dnf": MappingProxyType({
        "whois": "whois", "dig": "bind-utils", "nmap": "nmap",
        "masscan": "masscan", "nikto": "nikto", "sslscan": "sslscan",
        "sqlmap": "sqlmap", "hashcat": "hashcat", "john": "john",
        "hydra": "hydra", "airmon-ng": "aircrack-ng",
        "airodump-ng": "aircrack-ng", "aircrack-ng": "aircrack-ng",
        "ettercap": "ettercap", "tcpdump": "tcpdump",
    }),
})

PLATFORMS = (
    "linux-x86_64",
    "linux-aarch64",
    "windows-x86_64",
    "windows-aarch64",
    "darwin-x86_64",
    "darwin-aarch64",
)

# Helpers are intentionally outside the 46-tool product catalog.
TECHNICAL_COMPONENTS = frozenset({"7zip", "python-runtime"})

# Several catalog commands are installed by one upstream distribution.
TOOL_PACKAGE_ALIASES = MappingProxyType({
    "secretsdump.py": "impacket",
    "psexec.py": "impacket",
    "GetUserSPNs.py": "impacket",
})

_PACKAGE_DATA = Path(__file__).resolve().parents[1] / "desktop" / "packages.json"


def _package_specs() -> dict[str, dict[str, Any]]:
    return json.loads(_PACKAGE_DATA.read_text(encoding="utf-8"))


def _artifact_binary(spec: dict[str, Any], platform: str) -> str:
    """Binary name as it ships on ``platform``'s OS.

    Mirrors the runtime resolution in ``desktop/packages.py``: a per-OS override
    in ``binary_by_os`` wins; otherwise the ``.exe`` suffix is stripped for every
    non-Windows target. Without this the Linux records inherited the Windows
    default (e.g. hashcat's ``hashcat.exe`` instead of ``hashcat.bin``).
    """
    os_name = platform.split("-", 1)[0]
    by_os = spec.get("binary_by_os") or {}
    if os_name in by_os:
        return by_os[os_name]
    binary = spec["binary"]
    return binary if os_name == "windows" else binary.removesuffix(".exe")


def _portable_record(tool: str, platform: str,
                     specs: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    package = TOOL_PACKAGE_ALIASES.get(tool, tool)
    if package not in specs or package in TECHNICAL_COMPONENTS:
        return None
    spec = dict(specs[package])
    artifacts = spec.get("artifacts")
    if artifacts is not None:
        artifact = artifacts.get(platform)
        if artifact is None:
            return None
        spec.update(artifact)
    elif spec.get("platforms") and platform not in spec["platforms"]:
        return None

    record: dict[str, Any] = {
        "status": "automatic",
        "method": spec["kind"],
        "version": spec["version"],
        "package": package,
    }
    if spec["kind"] in {"release", "file", "installer", "pip-source"}:
        record["artifact"] = {
            "url": spec["url"],
            "sha256": spec["sha256"],
            "binary": _artifact_binary(spec, platform),
        }
    elif spec["kind"] == "pip":
        record["python_package"] = spec["package"]
    else:
        raise ValueError(f"Unsupported package method for {package}: {spec['kind']}")
    return record


def _linux_package_record(tool: str) -> dict[str, Any] | None:
    packages = {manager: mapping[tool] for manager, mapping in PACKAGE_NAMES.items()
                if tool in mapping}
    if not packages:
        return None
    commands = {
        "apt": f"sudo apt install {packages['apt']}" if "apt" in packages else None,
        "pacman": (f"sudo pacman -S {packages['pacman']}"
                   if "pacman" in packages else None),
        "dnf": f"sudo dnf install {packages['dnf']}" if "dnf" in packages else None,
    }
    return {
        "status": "automatic",
        "method": "system-package",
        "version": "distribution-managed",
        "packages": packages,
        "instructions": {manager: command for manager, command in commands.items()
                         if command is not None},
    }


def _unsupported_record(tool: str, platform: str) -> dict[str, str]:
    apt_package = PACKAGE_NAMES["apt"].get(tool)
    if platform.startswith("windows-"):
        environment = "the configured WSL2 Kali backend"
    elif platform.startswith("darwin-"):
        environment = "a supported Linux backend"
    else:
        environment = "a supported distribution repository"
    instruction = (f"Use {environment} and run `sudo apt install {apt_package}`."
                   if apt_package else
                   "Install the tool manually from its upstream documentation, then refresh inventory.")
    return {
        "status": "unsupported",
        "method": "manual",
        "reason": f"No pinned automatic source is recorded for {tool} on {platform}.",
        "instruction": instruction,
    }


def build_manifest() -> dict[str, dict[str, Any]]:
    """Return the complete normalized installation contract."""
    specs = _package_specs()
    manifest: dict[str, dict[str, Any]] = {}
    for tool in TOOLS:
        platforms: dict[str, dict[str, Any]] = {}
        for platform in PLATFORMS:
            record = _portable_record(tool, platform, specs)
            if record is None and platform.startswith("linux-"):
                record = _linux_package_record(tool)
            platforms[platform] = record or _unsupported_record(tool, platform)
        manifest[tool] = {
            "tool": tool,
            "package_alias": TOOL_PACKAGE_ALIASES.get(tool, tool),
            "platforms": platforms,
        }
    return manifest


TOOL_MANIFEST = build_manifest()
