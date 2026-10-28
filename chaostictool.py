#!/usr/bin/env python3
import argparse
import atexit
import os
import sys
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core import ui
    from core import target as tgt
    from core import session
    from core import proxy
    from core import flows
    from core import executor
except ImportError as e:
    print(f"\n[!] Missing dependency: {e}")
    print("    Install with: pip3 install -r requirements.txt\n")
    sys.exit(1)


def load_module(filename):
    return importlib.import_module(f"modules.{filename}")


MODULES = {
    "1":  "01_osint",
    "2":  "02_recon",
    "3":  "03_web_enum",
    "4":  "04_vulnscan",
    "5":  "05_exploitation",
    "6":  "06_postexploit",
    "7":  "07_passwords",
    "8":  "08_windows",
    "9":  "09_wireless",
    "10": "10_network",
}


def configure_target():
    ui.header("Configure target")
    if tgt.is_defined():
        ui.console.print(f"[brand.muted]Current target:[/brand.muted] [brand.ok]{tgt.summary()}[/brand.ok]\n")
    host = ui.ask("Host / domain / IP", tgt.TARGET["host"] or None)
    url = ui.ask("URL (optional, otherwise derived from host)", tgt.TARGET["url"] or None)
    port = ui.ask("Port", tgt.TARGET["port"])
    d = tgt.set_target(host=host, url=url, port=port)
    ui.console.print(f"\n[brand.ok][+] Target set:[/brand.ok] [brand.white]{tgt.summary()}[/brand.white]")
    if d:
        ui.console.print(f"[brand.ok][+] Directory:[/brand.ok] [brand.command]{d}[/brand.command]")
    _configure_subdomain_scope()
    ui.pause()


def _configure_subdomain_scope():
    """Offer subdomain scope for a domain target: enumerate once, toggle on/off."""
    from core import subdomains as sd
    host = tgt.TARGET["host"]
    if not sd.is_domain(host):
        return
    cached = tgt.SCOPE["subdomains"]
    state = "on" if tgt.SCOPE["include_subdomains"] else "off"
    ui.console.print(f"\n[brand.muted]Subdomain scope: {state}"
                     + (f", {len(cached)} subdomains cached" if cached else "") + ".[/brand.muted]")
    options = "[brand.accent]e[/brand.accent] enumerate now"
    if cached:
        options += "    [brand.accent]t[/brand.accent] turn " + ("off" if state == "on" else "on")
    options += "    [brand.accent]Enter[/brand.accent] skip"
    ui.console.print(options)
    choice = ui.console.input("[brand.white]▸[/brand.white] ").strip().lower()
    if choice == "e":
        _enumerate_subdomains()
    elif choice == "t" and cached:
        tgt.set_scope_enabled(state == "off")
        ui.console.print(f"[brand.ok][+] Subdomain scope {'enabled' if tgt.SCOPE['include_subdomains'] else 'disabled'}.[/brand.ok]")


def _enumerate_subdomains():
    from core import subdomains as sd
    host = tgt.TARGET["host"]
    env = executor._build_env()
    if not sd.available_enumerators(env.get("PATH")):
        ui.console.print("[bright_red][!] Install subfinder (recommended) or amass to enumerate subdomains.[/bright_red]")
        return
    ui.console.print(f"[brand.muted][*] Enumerating subdomains of {host}… this can take a while.[/brand.muted]")
    subs, sources, error = sd.enumerate_subdomains(host, env=env)
    if error:
        ui.console.print(f"[bright_red][!] {error}[/bright_red]")
        return
    tgt.set_subdomains(subs)
    if not subs:
        ui.console.print("[bright_yellow][!] No subdomains found.[/bright_yellow]")
        return
    tgt.set_scope_enabled(True)
    ui.console.print(f"[brand.ok][+] {len(subs)} subdomains found via {', '.join(sources)}. "
                     f"Subdomain scope enabled — host-targeted tools will run on all of them.[/brand.ok]")


def configure_api_keys():
    from core import api_keys as ak

    def masked(value):
        if not value:
            return "[brand.muted]not set[/brand.muted]"
        tail = value[-4:] if len(value) > 4 else value
        return f"[brand.ok]set[/brand.ok] [brand.muted](…{tail})[/brand.muted]"

    while True:
        ui.header("API keys")
        ui.console.print("[brand.muted]Stored in the operating system's secure key store and reused on every "
                         "launch. Each key is passed to the tools that read it from the environment.[/brand.muted]")
        if not ak.secure_storage_available():
            ui.console.print("[bright_yellow][!] No secure key store on this system — keys are kept for this "
                             "session only. Export the environment variable to persist, e.g. SHODAN_API_KEY.[/bright_yellow]")
        ui.console.print("")
        stored = ak.load()
        entries = []
        for index, spec in enumerate(ak.KEY_SPECS, start=1):
            entries.append((str(index), spec["label"], "brand.ok",
                            f"{spec['env']} · {spec['tools']}", masked(stored.get(spec["id"]))))
        choice = ui.menu("API keys", entries, footer_extra=["[brand.faint]number[/brand.faint] edit a key"])
        if choice in ui.BACK_KEYS or not choice:
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(ak.KEY_SPECS)):
            ui.console.print("[bright_red]Invalid choice.[/bright_red]")
            ui.pause()
            continue
        spec = ak.KEY_SPECS[int(choice) - 1]
        ui.console.print(f"\n[brand.white]{spec['label']}[/brand.white] [brand.muted]({spec['env']})[/brand.muted]")
        ui.console.print(f"[brand.muted]{spec['help']}[/brand.muted]")
        ui.console.print("[brand.muted]Leave blank to remove the stored key.[/brand.muted]")
        value = ui.ask("Key / token")
        persisted = ak.set_key(spec["id"], value)
        if not value.strip():
            ui.console.print("[brand.ok][+] Removed.[/brand.ok]")
        elif persisted:
            ui.console.print("[brand.ok][+] Saved to the system key store.[/brand.ok]")
        else:
            ui.console.print("[bright_yellow][+] Kept for this session only (no secure key store).[/bright_yellow]")
        ui.pause()


MAIN_ENTRIES = [
    ("0",  "Configure target",               "brand.red",  "sets host/URL/port and creates the results folder", "[brand.red]SETUP[/brand.red]"),
    ("1",  "OSINT & Passive Recon",          "brand.ok",   "whois, dig, subfinder, amass, dnsrecon, theHarvester, shodan", "[brand.ok]PHASE 01[/brand.ok]"),
    ("2",  "Network Scan",                   "brand.ok",   "nmap, rustscan, masscan, naabu", "[brand.ok]PHASE 02[/brand.ok]"),
    ("3",  "Web Enumeration",                "brand.ok",   "gobuster, ffuf, httpx, wafw00f, whatweb, katana, gau, waybackurls", "[brand.ok]PHASE 03[/brand.ok]"),
    ("4",  "Vulnerability Scan",             "brand.ok",   "nikto, nuclei, wpscan, testssl, sslscan", "[brand.ok]PHASE 04[/brand.ok]"),
    ("5",  "Exploitation",                   "brand.ok",   "sqlmap, xsstrike, dalfox, metasploit, msfvenom", "[brand.ok]PHASE 05[/brand.ok]"),
    ("6",  "Post-Exploitation & Privesc",    "brand.ok",   "impacket, netexec, bloodhound", "[brand.ok]PHASE 06[/brand.ok]"),
    ("7",  "Password Cracking",              "brand.ok",   "hashcat, john, hydra", "[brand.ok]PHASE 07[/brand.ok]"),
    ("8",  "Windows / Active Directory",     "brand.ok",   "secretsdump, psexec, kerberoasting, nxc, bloodhound", "[brand.ok]AD[/brand.ok]"),
    ("9",  "Wireless Security",              "brand.ok",   "airmon-ng, airodump-ng, aircrack-ng, reaver, wifite", "[brand.ok]RF[/brand.ok]"),
    ("10", "Network & MITM",                 "brand.ok",   "bettercap, ettercap, tcpdump, responder", "[brand.ok]LAN[/brand.ok]"),
    ("11", "Results & Session",              "brand.info", "browse files in the target folder", "[brand.info]FILES[/brand.info]"),
    ("12", "Attack flows",                   "brand.info", "guided basic/intermediate/advanced attack chains", "[brand.info]FLOW[/brand.info]"),
    ("p",  "Proxy / VPN / Tor",              "brand.warn", "route traffic through Tor or guard a VPN interface", "[brand.warn]ROUTE[/brand.warn]"),
    ("w",  "Wordlists",                       "brand.info", "download missing wordlists (SecLists, rockyou, dirb)", "[brand.info]WORDS[/brand.info]"),
    ("k",  "API keys",                        "brand.info", "store Shodan, WPScan and GitHub keys for the embedded tools", "[brand.info]KEYS[/brand.info]"),
    ("u",  "Application updates", "brand.info", "GitHub release checks and package updates", "[brand.info]UPDATE[/brand.info]"),
    ("99", "Quit",                           "bright_red", "", "[bright_red]EXIT[/bright_red]"),
]


def main_menu():
    return ui.menu("Main Menu", MAIN_ENTRIES, footer_extra=ui.context_footer(), show_back=False, home=True)


def main():
    from core.version import VERSION
    parser = argparse.ArgumentParser(description="ChaosticTool Linux terminal interface")
    parser.add_argument("--version", action="version", version=f"ChaosticTool {VERSION}")
    parser.add_argument("--check-installation", action="store_true",
                        help="check runtime imports without root, network or tool installation")
    parser.add_argument("--check-updates", action="store_true", help="check the latest public CLI release")
    parser.add_argument("--update", action="store_true", help="check and propose a package update with confirmation")
    parser.add_argument("--no-update-check", action="store_true", help="disable automatic release checks for this launch")
    args = parser.parse_args()
    if args.check_updates or args.update:
        from core import cli_updates
        if args.check_updates and not args.update:
            result = cli_updates._check(force=True)
            if result['error']:
                print("Could not verify updates.")
                raise SystemExit(1)
            print(f"CLI {VERSION}: " + (f"update {result['version']} available" if result['available'] else "no newer release"))
        else:
            cli_updates.show(install_now=True)
        return
    if args.check_installation:
        for module in MODULES.values():
            load_module(module)
        print(f"ChaosticTool {VERSION}: runtime imports OK")
        print(f"Results directory: {tgt.TARGETS_ROOT}")
        return
    if os.geteuid() != 0:
        print("\n[!] This script requires root privileges.")
        print("    Re-run with: sudo python3 chaostictool.py\n")
        sys.exit(1)

    if not args.no_update_check and sys.stdin.isatty() and sys.stdout.isatty():
        from core import cli_updates
        cli_updates.start_background()
    flows.load_custom_flows()
    ui.startup_check()
    while True:
        choice = main_menu()
        try:
            if choice == "__search__":
                ui.search_tools()
            elif choice == "0":
                configure_target()
            elif choice.lower() == "p":
                proxy.proxy_menu(ui)
            elif choice.lower() == "w":
                from core import wordlists as _wl
                _wl.wordlist_menu()
            elif choice.lower() == "k":
                configure_api_keys()
            elif choice.lower() == "u":
                from core import cli_updates
                if cli_updates.show():
                    return
            elif choice == "11":
                session.view_results()
            elif choice == "12":
                flows.flow_menu()
            elif choice in MODULES:
                try:
                    mod = load_module(MODULES[choice])
                    mod.run()
                except Exception as e:
                    ui.console.print(f"[bright_red][!] Module error: {e}[/bright_red]")
                    ui.pause()
            elif choice == "99":
                ui.console.print("\n[brand.red]ChaosticTool session closed.[/brand.red]\n")
                sys.exit(0)
            else:
                ui.console.print("[bright_red]Invalid choice.[/bright_red]")
                ui.pause()
        except KeyboardInterrupt:
            # Escape cancels a form or returns from a secondary screen.
            continue


def cleanup():
    executor.cleanup_processes()
    proxy.cleanup_proxy()


if __name__ == "__main__":
    atexit.register(cleanup)
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
        cleanup()
        sys.exit(0)
