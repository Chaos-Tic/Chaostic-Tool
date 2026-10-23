import os
import shutil
import signal
import subprocess
import time

from core.theme import THEME

from core.terminal import console

# Global proxy state
PROXY_STATE = {
    "enabled": False,
    "mode": None,       # "tor" | "vpn"
    "interface": None,
    "tor_started_by_us": False,
    "tor_exit_ip": None,
    "tor_exit_ip_changed": None,
    "tor_auto_rotate": False,
}


def is_tor_running():
    return subprocess.run(["pgrep", "-x", "tor"], capture_output=True).returncode == 0


def proxychains_binary():
    return shutil.which("proxychains4") or shutil.which("proxychains")


def get_vpn_interfaces():
    """Returns list of tun/wg interfaces (OpenVPN/WireGuard)."""
    result = subprocess.run(["ip", "link", "show"], capture_output=True, text=True)
    ifaces = []
    for line in result.stdout.splitlines():
        if ": tun" in line or ": wg" in line or ": ppp" in line:
            name = line.split(":")[1].strip().split("@")[0]
            ifaces.append(name)
    return ifaces


def get_default_interface():
    """Returns the interface used by the current default route, if any."""
    result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        parts = line.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    return None


def proxy_menu(ui_module):
    """Interactive menu to configure proxy/VPN/Tor routing."""
    while True:
        status = "[brand.badge.ok] ACTIVE [/brand.badge.ok]" if PROXY_STATE["enabled"] else "[brand.badge.bad] DISABLED [/brand.badge.bad]"
        mode = PROXY_STATE["mode"] or "none"
        default_iface = get_default_interface()

        entries = [
            ("1", "Enable Tor routing", "brand.accent", "route supported tool traffic through proxychains", "[brand.badge.ok] TOR [/brand.badge.ok]"),
            ("2", "Enable VPN guard", "brand.info", "warn if the default route is not the selected VPN", "[brand.badge.info] VPN [/brand.badge.info]"),
            ("3", "Disable proxy", "brand.danger", "restore direct connection", "[brand.badge.bad] DIRECT [/brand.badge.bad]"),
            ("4", "Check Tor status", "brand.warn", "verify Tor is running", "[brand.badge.warn] CHECK [/brand.badge.warn]"),
            ("5", "Show Tor exit IP", "brand.warn", "query current Tor public IP", "[brand.badge.warn] IP [/brand.badge.warn]"),
            ("6", "Rotate Tor identity", "brand.warn", "ask Tor for a new circuit / exit IP", "[brand.badge.warn] ROTATE [/brand.badge.warn]"),
            ("7", "Toggle Tor auto-rotate", "brand.warn", "rotate before every Tor-routed tool", "[brand.badge.warn] AUTO [/brand.badge.warn]"),
        ]
        footer = [
            f"[brand.faint]status[/brand.faint] {status} [brand.muted]mode: {mode}[/brand.muted]",
            f"[brand.faint]default route[/brand.faint] [brand.command]{default_iface or 'unknown'}[/brand.command]",
            f"[brand.faint]tor exit ip[/brand.faint] {_format_tor_ip_state()}",
            f"[brand.faint]tor auto-rotate[/brand.faint] {'ON' if PROXY_STATE['tor_auto_rotate'] else 'OFF'}",
            "[brand.muted]Proxy routing is only applied to tools where it makes operational sense.[/brand.muted]",
        ]
        choice = ui_module.menu("Routing control", entries, footer_extra=footer,
                                routing_rows=routing_snapshot())

        if choice in ui_module.BACK_KEYS:
            return

        if choice == "1":
            if not proxychains_binary():
                console.print("[bright_red][!] proxychains / proxychains4 not found.[/bright_red]")
                console.print("[brand.muted]    Install: sudo pacman -S proxychains-ng  or  sudo apt install proxychains4[/brand.muted]")
            elif not is_tor_running():
                console.print("[brand.warn][!] Tor is not running.[/brand.warn]")
                rep = console.input("[brand.warn]Start Tor now? [Y/n][/brand.warn] [brand.white]›[/brand.white] ").strip().lower()
                if rep in ("", "y", "yes", "o", "oui"):
                    if start_tor():
                        console.print("[brand.ok][+] Tor started by ChaosticTool.[/brand.ok]")
                    else:
                        console.print("[bright_red][!] Could not start Tor automatically.[/bright_red]")
                    if is_tor_running():
                        update_tor_exit_ip()
                        PROXY_STATE.update({"enabled": True, "mode": "tor", "interface": None})
                        console.print("[brand.ok][+] Tor routing enabled.[/brand.ok]")
                    else:
                        console.print("[bright_red][!] Tor is still not running — routing NOT enabled to prevent IP leak.[/bright_red]")
            else:
                PROXY_STATE.update({"enabled": True, "mode": "tor", "interface": None})
                console.print("[brand.ok][+] Tor routing enabled. Tools will be wrapped with proxychains.[/brand.ok]")
                update_tor_exit_ip()

        elif choice == "2":
            ifaces = get_vpn_interfaces()
            if not ifaces:
                console.print("[bright_yellow][!] No VPN interface detected (tun*, wg*, ppp*).[/bright_yellow]")
                console.print("[brand.muted]    Connect to your VPN first, then come back.[/brand.muted]")
            else:
                console.print("  Detected VPN interfaces:")
                for i, iface in enumerate(ifaces, 1):
                    console.print(f"  [brand.ok][{i}][/brand.ok] [brand.command]{iface}[/brand.command]")
                sel = console.input("[brand.red]Select interface[/brand.red] [brand.white]›[/brand.white] ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(ifaces):
                    chosen = ifaces[int(sel) - 1]
                    default_iface = get_default_interface()
                    if default_iface != chosen:
                        console.print(
                            f"[bright_yellow][!] {chosen} is active, but the default route is {default_iface or 'unknown'}.[/bright_yellow]"
                        )
                        console.print("[brand.muted]    Tools will only use the VPN if your system route sends traffic through it.[/brand.muted]")
                    PROXY_STATE.update({"enabled": True, "mode": "vpn", "interface": chosen})
                    console.print(f"[brand.ok][+] VPN guard enabled for {chosen}.[/brand.ok]")

        elif choice == "3":
            PROXY_STATE.update({"enabled": False, "mode": None, "interface": None})
            console.print("[brand.ok][+] Direct connection restored.[/brand.ok]")

        elif choice == "4":
            running = is_tor_running()
            if running:
                console.print("[brand.ok][+] Tor is running.[/brand.ok]")
            else:
                console.print("[bright_red][-] Tor is not running.[/bright_red]")

        elif choice == "5":
            ip = update_tor_exit_ip()
            if ip:
                changed = PROXY_STATE.get("tor_exit_ip_changed")
                suffix = "changed" if changed else "unchanged"
                console.print(f"[brand.ok][+] Tor exit IP: {ip} ({suffix})[/brand.ok]")
            else:
                console.print("[bright_red][!] Could not query Tor exit IP.[/bright_red]")

        elif choice == "6":
            old_ip = PROXY_STATE.get("tor_exit_ip")
            if rotate_tor_identity():
                console.print("[brand.ok][+] Tor identity rotation requested.[/brand.ok]")
                time.sleep(4)
                new_ip = update_tor_exit_ip()
                if new_ip:
                    if old_ip and new_ip != old_ip:
                        console.print(f"[brand.ok][+] Tor exit IP changed: {old_ip} -> {new_ip}[/brand.ok]")
                    else:
                        console.print(f"[bright_yellow][!] Tor exit IP did not change yet: {new_ip}[/bright_yellow]")
            else:
                console.print("[bright_red][!] Could not rotate Tor identity.[/bright_red]")

        elif choice == "7":
            PROXY_STATE["tor_auto_rotate"] = not PROXY_STATE["tor_auto_rotate"]
            state = "enabled" if PROXY_STATE["tor_auto_rotate"] else "disabled"
            console.print(f"[brand.ok][+] Tor auto-rotate {state}.[/brand.ok]")

        ui_module.pause()


def wrap_command(cmd):
    """Prepend proxychains to cmd if Tor mode is active."""
    if not PROXY_STATE["enabled"]:
        return cmd
    if PROXY_STATE["mode"] == "tor":
        pc = proxychains_binary()
        if pc:
            if PROXY_STATE.get("tor_auto_rotate"):
                old_ip = PROXY_STATE.get("tor_exit_ip")
                rotate_tor_identity()
                time.sleep(4)
                new_ip = update_tor_exit_ip()
                if new_ip and old_ip and new_ip != old_ip:
                    console.print(f"[brand.ok][+] Tor exit IP changed: {old_ip} -> {new_ip}[/brand.ok]")
                elif new_ip:
                    console.print(f"[bright_yellow][!] Tor exit IP unchanged: {new_ip}[/bright_yellow]")
            return [pc, "-q"] + cmd
    if PROXY_STATE["mode"] == "vpn":
        chosen = PROXY_STATE.get("interface")
        default_iface = get_default_interface()
        if chosen and default_iface != chosen:
            console.print(
                f"[bright_yellow][!] VPN guard: default route is {default_iface or 'unknown'}, not {chosen}.[/bright_yellow]"
            )
            console.print("[brand.muted]    Command is still launched; connect/reroute your VPN if this is not intended.[/brand.muted]")
    return cmd


def route_status(tool=None):
    if not PROXY_STATE["enabled"]:
        return "DIRECT"
    mode = (PROXY_STATE.get("mode") or "direct").upper()
    if tool is not None and not should_proxy_tool(tool):
        return f"DIRECT ({mode} skipped)"
    if PROXY_STATE.get("mode") == "vpn":
        iface = PROXY_STATE.get("interface") or "unknown"
        default_iface = get_default_interface() or "unknown"
        if default_iface == iface:
            return f"VPN {iface}"
        return f"VPN guard {iface} (default: {default_iface})"
    if PROXY_STATE.get("mode") == "tor":
        return "TOR via proxychains"
    return mode


def start_tor():
    was_running = is_tor_running()
    commands = [
        ["systemctl", "start", "tor"],
        ["service", "tor", "start"],
    ]
    for cmd in commands:
        if shutil.which(cmd[0]):
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and is_tor_running():
                PROXY_STATE["tor_started_by_us"] = not was_running
                return True
    return is_tor_running()


def cleanup_proxy():
    if PROXY_STATE.get("tor_started_by_us") and is_tor_running():
        console.print("\n[brand.muted]Stopping Tor service started by ChaosticTool...[/brand.muted]")
        for cmd in (["systemctl", "stop", "tor"], ["service", "tor", "stop"]):
            if shutil.which(cmd[0]):
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    break
    PROXY_STATE.update({"enabled": False, "mode": None, "interface": None, "tor_started_by_us": False})


def update_tor_exit_ip():
    if not is_tor_running() or not proxychains_binary():
        return None
    old_ip = PROXY_STATE.get("tor_exit_ip")
    ip = _query_tor_exit_ip()
    if not ip:
        return None
    PROXY_STATE["tor_exit_ip"] = ip
    PROXY_STATE["tor_exit_ip_changed"] = old_ip is not None and old_ip != ip
    return ip


def rotate_tor_identity():
    if not is_tor_running():
        return False
    for cmd in (["systemctl", "reload", "tor"], ["service", "tor", "reload"]):
        if shutil.which(cmd[0]):
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
    try:
        result = subprocess.run(["pgrep", "tor"], capture_output=True, text=True)
        for pid in result.stdout.split():
            os.kill(int(pid), signal.SIGHUP)
        return bool(result.stdout.strip())
    except Exception:
        return False


def _query_tor_exit_ip():
    pc = proxychains_binary()
    client = _http_client_command()
    if not pc or not client:
        return None
    urls = ["https://api.ipify.org", "https://icanhazip.com"]
    for url in urls:
        cmd = [pc, "-q"] + client + [url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        except Exception:
            continue
        if result.returncode == 0:
            ip = (result.stdout.strip().splitlines() or [""])[-1].strip()
            if ip:
                return ip
    return None


def _http_client_command():
    curl = shutil.which("curl")
    if curl:
        return [curl, "-fsS", "--max-time", "15"]
    wget = shutil.which("wget")
    if wget:
        return [wget, "-qO-", "--timeout=15"]
    return None


def _format_tor_ip_state():
    ip = PROXY_STATE.get("tor_exit_ip")
    if not ip:
        return "unknown"
    changed = PROXY_STATE.get("tor_exit_ip_changed")
    if changed is True:
        return f"{ip} [green](changed)[/green]"
    if changed is False:
        return f"{ip} [brand.muted](unchanged)[/brand.muted]"
    return ip


def should_proxy_tool(tool):
    if tool.get("proxy") is False:
        return False
    if PROXY_STATE.get("mode") == "vpn":
        return tool.get("category") not in ("wireless", "passwords")
    if tool.get("proxy") is True:
        return True
    tor_safe = {
        # whois excluded: sends native UDP DNS queries that proxychains cannot intercept
        "shodan", "httpx", "wafw00f", "whatweb", "katana",
        "gau", "waybackurls", "nikto", "nuclei", "wpscan",
        "testssl", "sslscan", "sqlmap", "xsstrike", "dalfox",
    }
    if PROXY_STATE.get("mode") == "tor":
        binaries = {tool.get("binary")} | set(tool.get("binary_alternatives", []))
        return bool(tor_safe & binaries)
    return True


def routing_snapshot():
    """Describe observed routing state without claiming untested protection."""
    enabled = PROXY_STATE["enabled"]
    mode = PROXY_STATE.get("mode")
    binary = proxychains_binary()
    running = is_tor_running()
    interface = PROXY_STATE.get("interface")
    default = get_default_interface() or "unknown"
    tor_state = "ACTIVE" if enabled and mode == "tor" and running and binary else "OFF"
    if enabled and mode == "tor" and (not running or not binary):
        tor_state = "UNAVAILABLE"
    guard = "OFF"
    if enabled and mode == "vpn":
        guard = "MATCH" if interface and interface == default else "MISMATCH"
    exit_ip = PROXY_STATE.get("tor_exit_ip") or "not checked"
    return [
        ("TOR", f"{binary or 'proxychains missing'} / exit {exit_ip}", tor_state),
        ("VPN GUARD", f"selected {interface or 'none'} / default {default} / warning only", guard),
        ("PROXY", "uses the installed proxychains configuration", "AVAILABLE" if binary else "MISSING"),
        ("DNS LEAK", "no DNS leak verification implemented", "NOT VERIFIED"),
    ]
