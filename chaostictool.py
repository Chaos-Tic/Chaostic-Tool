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
    _warn_if_unresolved()
    _configure_subdomain_scope()
    ui.pause()


def _warn_if_unresolved():
    """Flag a domain target that has no A/AAAA record, so it is not mistaken for a bug."""
    from core import subdomains as sd
    warning = sd.resolution_warning(tgt.TARGET["host"])
    if warning:
        ui.console.print(f"[bright_yellow][!] {warning}[/bright_yellow]")


def _configure_subdomain_scope():
    """Offer subdomain scope for a domain target: enumerate, toggle, exclude."""
    from core import subdomains as sd
    host = tgt.TARGET["host"]
    if not sd.is_domain(host):
        return
    while True:
        cached = tgt.SCOPE["subdomains"]
        excluded = set(tgt.SCOPE["excluded"])
        state = "on" if tgt.SCOPE["include_subdomains"] else "off"
        status = f"\n[brand.muted]Subdomain scope: {state}"
        if cached:
            active = len([s for s in cached if s not in excluded])
            status += f", {len(cached)} cached"
            if excluded:
                status += f", {len(excluded)} excluded ({active} in scope)"
        status += ".[/brand.muted]"
        ui.console.print(status)
        options = "[brand.accent]e[/brand.accent] enumerate now"
        if cached:
            options += "    [brand.accent]t[/brand.accent] turn " + ("off" if state == "on" else "on")
            options += "    [brand.accent]x[/brand.accent] exclude / include subdomains"
        options += "    [brand.accent]Enter[/brand.accent] done"
        ui.console.print(options)
        choice = ui.console.input("[brand.white]▸[/brand.white] ").strip().lower()
        if choice == "e":
            _enumerate_subdomains()
        elif choice == "t" and cached:
            tgt.set_scope_enabled(state == "off")
            ui.console.print(f"[brand.ok][+] Subdomain scope {'enabled' if tgt.SCOPE['include_subdomains'] else 'disabled'}.[/brand.ok]")
        elif choice == "x" and cached:
            _manage_subdomain_exclusions()
        else:
            return


def _manage_subdomain_exclusions():
    """List discovered subdomains and toggle which are excluded from the fan-out."""
    cached = tgt.SCOPE["subdomains"]
    if not cached:
        return
    while True:
        excluded = set(tgt.SCOPE["excluded"])
        ui.console.print("\n[brand.muted]Discovered subdomains (✗ excluded from scope):[/brand.muted]")
        for index, sub in enumerate(cached, start=1):
            mark = "[bright_red]✗[/bright_red]" if sub in excluded else "[brand.ok]•[/brand.ok]"
            ui.console.print(f"  {mark} [brand.accent]{index}[/brand.accent] {sub}")
        ui.console.print("[brand.muted]Number toggles exclusion    [brand.accent]a[/brand.accent] include all"
                         "    [brand.accent]n[/brand.accent] exclude all    [brand.accent]Enter[/brand.accent] back[/brand.muted]")
        choice = ui.console.input("[brand.white]▸[/brand.white] ").strip().lower()
        if not choice:
            return
        if choice == "a":
            tgt.set_excluded([])
            ui.console.print("[brand.ok][+] All subdomains included in scope.[/brand.ok]")
        elif choice == "n":
            tgt.set_excluded(list(cached))
            ui.console.print("[bright_yellow][+] All subdomains excluded from scope.[/bright_yellow]")
        elif choice.isdigit() and 1 <= int(choice) <= len(cached):
            sub = cached[int(choice) - 1]
            now_excluded = tgt.toggle_excluded(sub)
            ui.console.print(f"[brand.ok][+] {sub} {'excluded from' if now_excluded else 'included in'} scope.[/brand.ok]")
        else:
            ui.console.print("[bright_red]Invalid choice.[/bright_red]")


def _enumerate_subdomains():
    """Enumerate via the shared path (subfinder primary + amass best-effort)."""
    from core import subdomains as sd
    host = tgt.TARGET["host"]
    env = executor._build_env()
    tools = sd.available_enumerators(env.get("PATH"))
    if not tools:
        ui.console.print("[bright_red][!] Install subfinder (recommended) or amass to enumerate subdomains.[/bright_red]")
        return
    running = ", ".join(f"{name} (best-effort)" if name == "amass" else name for name in tools)
    ui.console.print(f"[brand.muted][*] Enumerating subdomains with {running}…[/brand.muted]")
    try:
        with ui.console.status(f"[brand.accent]Running {running}…[/brand.accent]", spinner="dots"):
            subs, counts, error = sd.enumerate_subdomains(host, env=env, budget=600)
    except Exception as exc:
        ui.console.print(f"[bright_red][!] Subdomain enumeration failed: {exc}[/bright_red]")
        return
    # Keep a plain copy of the discovered hosts in the OSINT folder for reference.
    cat = tgt.category_dir("osint")
    if cat is not None and subs:
        try:
            output_path = executor.target_path(cat, "subdomains", tgt.target_name())
            output_path.write_text("\n".join(subs) + "\n", encoding="utf-8")
        except OSError:
            pass
    tgt.set_subdomains(subs)
    if subs:
        tgt.set_scope_enabled(True)
        ui.console.print(f"[brand.ok][+] {sd.enumeration_summary(len(subs), counts)} "
                         f"Subdomain scope enabled — host-targeted tools will run on all of them.[/brand.ok]")
    elif error:
        ui.console.print(f"[bright_yellow][!] {error}[/bright_yellow]")
    else:
        ui.console.print("[bright_yellow][!] No subdomains found.[/bright_yellow]")
    _warn_if_unresolved()


def configure_api_keys():
    from core import api_keys as ak

    def masked(value):
        if not value:
            return "[brand.muted]not set[/brand.muted]"
        tail = value[-4:] if len(value) > 4 else value
        return f"[brand.ok]set[/brand.ok] [brand.muted](…{tail})[/brand.muted]"

    def storage_line():
        status = ak.storage_status()
        if status.kind == "keyring":
            return "[brand.muted]Storage: the operating system's secure key store (encrypted at rest by the OS).[/brand.muted]"
        if status.kind == "file-encrypted":
            state = " [bright_yellow]— locked (enter the passphrase to use the keys)[/bright_yellow]" if status.locked else ""
            return (f"[brand.muted]Storage: encrypted file (PBKDF2-HMAC-SHA256 + Fernet, passphrase asked once per "
                    f"session) at {status.path}[/brand.muted]{state}")
        if status.kind == "file-plain":
            return (f"[bright_yellow]Storage: file readable by your account only (mode 0600) at {status.path}. "
                    "Values are base64-encoded, NOT encrypted — file permissions are the only protection.[/bright_yellow]")
        return ("[bright_yellow][!] No secure key store on this system — keys are kept for this session only. "
                "Saving a key offers a persistent file instead; exporting the variable (e.g. SHODAN_API_KEY) also works.[/bright_yellow]")

    def unlock():
        """Ask for the passphrase of an encrypted file store; True when usable."""
        for _ in range(3):
            passphrase = ui.ask("Key file passphrase", password=True)
            if not passphrase:
                return False
            if ak.unlock_file_store(passphrase):
                return True
            ui.console.print("[bright_red]Wrong passphrase.[/bright_red]")
        return False

    def offer_file_store():
        """Propose the on-disk fallback once; the choice is remembered by the file itself."""
        status = ak.storage_status()
        ui.console.print(f"\n[bright_yellow][!] No secure key store. Keys can be saved to {status.path} "
                         "(directory 0700, file 0600, atomic writes) so they survive relaunches.[/bright_yellow]")
        if status.can_encrypt:
            ui.console.print("[brand.muted]The file will be encrypted with a passphrase (PBKDF2-HMAC-SHA256 → Fernet) "
                             "that you enter once per session.[/brand.muted]")
        else:
            ui.console.print("[bright_yellow]The `cryptography` library is not installed: the file would be "
                             "base64-encoded but NOT encrypted; only its 0600 permissions protect it.[/bright_yellow]")
        if ui.ask("Save keys to this file? [y/N]").lower() not in ("y", "yes", "o", "oui"):
            return
        passphrase = None
        if status.can_encrypt:
            passphrase = ui.ask("Passphrase (leave blank for an unencrypted 0600 file)", password=True)
            if passphrase and ui.ask("Confirm passphrase", password=True) != passphrase:
                ui.console.print("[bright_red]Passphrases differ — keys kept for this session only.[/bright_red]")
                return
        mode = ak.enable_file_store(passphrase or None)
        ui.console.print("[brand.ok][+] Encrypted key file created.[/brand.ok]" if mode == "fernet"
                         else "[bright_yellow][+] Unencrypted 0600 key file created.[/bright_yellow]")

    ak.set_passphrase_prompt(lambda reason: ui.ask("Key file passphrase", password=True) or None)
    while True:
        ui.header("API keys")
        ui.console.print("[brand.muted]Set once and reused on every launch. Each key is passed to the tools that "
                         "read it from the environment; a variable already exported in your shell wins.[/brand.muted]")
        ui.console.print(storage_line())
        ui.console.print("")
        if ak.storage_status().locked and not unlock():
            return
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
        ui.console.print("[brand.muted]Leave blank to remove the stored key. Input is hidden.[/brand.muted]")
        value = ui.ask("Key / token", password=True)
        if value.strip() and ak.file_store_offerable():
            offer_file_store()
        persisted = ak.set_key(spec["id"], value)
        kind = ak.storage_status().kind
        if not value.strip():
            ui.console.print("[brand.ok][+] Removed.[/brand.ok]")
        elif not persisted:
            ui.console.print("[bright_yellow][+] Kept for this session only (no persistent key store).[/bright_yellow]")
        elif kind == "keyring":
            ui.console.print("[brand.ok][+] Saved to the system key store.[/brand.ok]")
        elif kind == "file-encrypted":
            ui.console.print("[brand.ok][+] Saved to the encrypted key file.[/brand.ok]")
        else:
            ui.console.print("[bright_yellow][+] Saved to the 0600 key file (not encrypted).[/bright_yellow]")
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
    from core import logging_setup
    logging_setup.setup_logging()
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
