import os
import shlex
import shutil
import socket
import subprocess
import time

from rich import box
from rich.align import Align
from rich.cells import cell_len
from rich.console import Console
from rich.console import Group
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.theme import Theme

from core import target as tgt
from core import executor
from core.version import VERSION
from core.proxy import PROXY_STATE, route_status, should_proxy_tool, wrap_command

THEME = Theme(
    {
        "brand.logo": "bold #ff3131",
        "brand.title": "bold #fff2f2",
        "brand.red": "bold #ff3131",
        "brand.red_soft": "#ff6b6b",
        "brand.dark": "#17090b",
        "brand.dim": "#7f5f64",
        "brand.muted": "#a98c91",
        "brand.warn": "bold #ffb84d",
        "brand.ok": "bold #31ff83",
        "brand.info": "bold #67e8f9",
        "brand.white": "bold #f8fafc",
        "brand.command": "#ffb4b4",
    }
)

console = Console(theme=THEME)
_BINARY_VALIDATION_CACHE = {}

SUPPORT_TOOLS = {
    "proxychains4": {
        "name": "proxychains",
        "binary": "proxychains4",
        "binary_alternatives": ["proxychains"],
        "desc": "required for Tor routing",
    },
    "tor": {
        "name": "Tor service",
        "binary": "tor",
        "desc": "required when using Tor routing",
    },
    "curl": {
        "name": "curl",
        "binary": "curl",
        "desc": "used to query Tor exit IP",
    },
}

BANNER = r"""
 ██████╗██╗  ██╗ █████╗  ██████╗ ███████╗████████╗██╗ ██████╗
██╔════╝██║  ██║██╔══██╗██╔═══██╗██╔════╝╚══██╔══╝██║██╔════╝
██║     ███████║███████║██║   ██║███████╗   ██║   ██║██║
██║     ██╔══██║██╔══██║██║   ██║╚════██║   ██║   ██║██║
╚██████╗██║  ██║██║  ██║╚██████╔╝███████║   ██║   ██║╚██████╗
 ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝ ╚═════╝
          ████████╗ ██████╗  ██████╗ ██╗
          ╚══██╔══╝██╔═══██╗██╔═══██╗██║
             ██║   ██║   ██║██║   ██║██║
             ██║   ██║   ██║██║   ██║██║
             ██║   ╚██████╔╝╚██████╔╝███████╗
             ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝
"""
COMPACT_BANNER = "C H A O S T I C   T O O L"
HUD_TAGLINE = "RED OPS CONTROL SURFACE // PENTEST CLI FRAMEWORK"

WORDLISTS = [
    ("/usr/share/wordlists/dirb/common.txt",                              "small — fast"),
    ("/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",     "medium"),
    ("/usr/share/wordlists/dirbuster/directory-list-2.3-big.txt",        "large — slow"),
    ("/usr/share/wordlists/rockyou.txt",                                  "passwords — rockyou"),
    ("/usr/share/seclists/Discovery/Web-Content/raft-large-words.txt",   "SecLists raft-large"),
    ("/usr/share/seclists/Passwords/rockyou.txt",                        "SecLists rockyou"),
]

BACK_KEYS = {"r", "0", "b", "retour", "back", "q"}


def clear():
    console.clear()


def _target_state():
    if tgt.is_defined():
        return tgt.summary(), "brand.ok"
    return "not configured", "brand.warn"


def _proxy_state():
    if PROXY_STATE["enabled"]:
        mode = PROXY_STATE["mode"]
        iface = PROXY_STATE.get("interface") or ""
        label = f"{mode.upper()}{' / ' + iface if iface else ''}"
        return label, "brand.warn" if mode == "tor" else "brand.info"
    return "direct", "brand.ok"


def _metric(label, value, style):
    return (
        f"[brand.muted]{label}[/brand.muted]\n"
        f"[{style}]{escape(str(value))}[/{style}]"
    )


def _hud_grid():
    target, target_style = _target_state()
    proxy, proxy_style = _proxy_state()
    route = route_status()
    if console.width < 60 and not tgt.is_defined():
        target = "unset"
    grid = Table.grid(expand=True)
    for _ in range(4):
        grid.add_column(ratio=1)
    grid.add_row(
        _metric("TARGET", target, target_style),
        _metric("ROUTE", route, "brand.info" if route != "DIRECT" else "brand.ok"),
        _metric("PROXY", proxy, proxy_style),
        _metric("VERSION", f"v{VERSION}", "brand.red"),
    )
    return grid


def _logo_text():
    content_width = max(console.width - 8, 20)
    lines = BANNER.strip("\n").splitlines()
    logo_width = max(cell_len(line) for line in lines)
    if logo_width > content_width:
        return Text(COMPACT_BANNER, style="brand.logo", justify="center", no_wrap=True, overflow="crop")

    rendered = "\n".join(line.ljust(logo_width) for line in lines)
    return Text(rendered, style="brand.logo", no_wrap=True, overflow="crop")


def banner():
    clear()
    tagline = HUD_TAGLINE if console.width >= 72 else "RED OPS // PENTEST CLI"
    title = Text.assemble(
        ("ChaosticTool", "brand.title"),
        ("  ", "brand.muted"),
        (tagline, "brand.muted"),
    )
    console.print(
        Panel(
            Group(
                Align.center(_logo_text()),
                Align.center(title),
                Padding(_hud_grid(), (1, 0, 0, 0)),
            ),
            box=box.DOUBLE,
            border_style="brand.red",
            padding=(1, 2),
        )
    )


def header(title):
    banner()
    console.print(
        Panel(
            Align.center(Text(str(title).upper(), style="brand.white")),
            box=box.HEAVY,
            border_style="brand.red_soft",
            padding=(0, 2),
        )
    )


def tool_available(tool):
    for binary in _candidate_binaries(tool):
        if _binary_matches_tool(tool, binary):
            return True
    return False


def resolve_tool_binary(tool):
    for binary in _candidate_binaries(tool):
        if _binary_matches_tool(tool, binary):
            return binary
    return tool["binary"]


def _candidate_binaries(tool):
    binaries = [tool["binary"]] + list(tool.get("binary_alternatives", []))
    candidates = []
    for binary in binaries:
        path = shutil.which(binary)
        if path:
            candidates.append(path)

    sudo_user = os.environ.get("SUDO_USER", "")
    extra_dirs = []
    if sudo_user:
        extra_dirs += [
            f"/home/{sudo_user}/go/bin",
            f"/home/{sudo_user}/.local/share/go/bin",
            f"/home/{sudo_user}/.cargo/bin",
            f"/home/{sudo_user}/.local/bin",
        ]
    extra_dirs += [
        os.path.expanduser("~/go/bin"),
        os.path.expanduser("~/.local/share/go/bin"),
        os.path.expanduser("~/.cargo/bin"),
        os.path.expanduser("~/.local/bin"),
    ]
    # Scan all home dirs so go/cargo tools resolve even without SUDO_USER
    try:
        for entry in os.scandir("/home"):
            if entry.is_dir() and entry.name != sudo_user:
                base = entry.path
                for sub in ("go/bin", ".local/share/go/bin", ".cargo/bin", ".local/bin"):
                    d = os.path.join(base, sub)
                    if d not in extra_dirs:
                        extra_dirs.append(d)
    except PermissionError:
        pass
    for d in extra_dirs:
        for binary in binaries:
            path = os.path.join(d, binary)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                candidates.append(path)

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _binary_matches_tool(tool, binary):
    needles = tool.get("help_contains_any")
    if not needles:
        return True
    cache_key = (binary, tuple(needles))
    if cache_key in _BINARY_VALIDATION_CACHE:
        return _BINARY_VALIDATION_CACHE[cache_key]
    try:
        result = subprocess.run([binary, "-h"], capture_output=True, text=True, timeout=4)
        help_text = (result.stdout + "\n" + result.stderr).lower()
        ok = any(needle.lower() in help_text for needle in needles)
    except Exception:
        ok = False
    _BINARY_VALIDATION_CACHE[cache_key] = ok
    return ok


def pause():
    console.input("\n[brand.muted]Press Enter to continue[/brand.muted] [brand.red]›[/brand.red] ")


def ask(prompt, default=None):
    suffix = f" [brand.muted]({escape(str(default))})[/brand.muted]" if default else ""
    val = console.input(f"[brand.red]{escape(prompt)}{suffix}[/brand.red] [brand.white]›[/brand.white] ").strip()
    return val or (default or "")


def context_footer():
    target, target_style = _target_state()
    proxy, proxy_style = _proxy_state()
    route = route_status()
    return [
        f"[brand.red]Target:[/brand.red] [{target_style}]{escape(target)}[/{target_style}]",
        f"[brand.red]Route:[/brand.red] [brand.info]{escape(route)}[/brand.info]",
        f"[brand.red]Proxy:[/brand.red] [{proxy_style}]{escape(proxy)}[/{proxy_style}]",
    ]


def _footer_panel(lines):
    return Panel(
        Group(*(line for line in lines)),
        box=box.SQUARE,
        border_style="brand.dim",
        padding=(0, 1),
    )


def _input_prompt():
    return console.input("\n[brand.red]╰─[/brand.red][brand.white]COMMAND[/brand.white][brand.red]▶[/brand.red] ").strip().lower()


def menu(title, entries, footer_extra=None, show_back=True):
    """entries: list of (key, label, style[, desc]). Returns the key typed."""
    header(title)
    show_status = any(len(item) > 4 for item in entries)
    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="brand.red",
        expand=True,
        pad_edge=True,
        show_lines=False,
    )
    table.add_column("KEY", style="brand.red", justify="center", no_wrap=True, width=7)
    table.add_column("MODULE", style="brand.white", no_wrap=True)
    table.add_column("CAPABILITY", style="brand.muted", ratio=1)
    if show_status:
        table.add_column("STATUS", justify="right", no_wrap=True)

    for item in entries:
        key, label, style = item[0], item[1], item[2]
        desc = item[3] if len(item) > 3 else None
        status = item[4] if len(item) > 4 else ""
        key_text = Text(f" {key} ", style=style)
        label_text = Text(str(label), style="brand.white" if "red" not in style else "bright_red")
        desc_text = desc or ""
        if show_status:
            table.add_row(key_text, label_text, desc_text, status)
        else:
            table.add_row(key_text, label_text, desc_text)

    console.print(Padding(table, (1, 0, 0, 0)))
    footer_lines = list(footer_extra or [])
    controls = (
        "[brand.red]r / 0[/brand.red] back"
        if show_back
        else "[brand.red]99[/brand.red] quit"
    )
    footer_lines.extend(
        [
            controls,
            "[brand.muted]Ctrl+C interrupts the current tool[/brand.muted]",
        ]
    )
    console.print(_footer_panel(footer_lines))
    return _input_prompt()


def select_wordlist():
    header("Wordlist selection")
    available = [(p, d) for p, d in WORDLISTS if os.path.exists(p)]
    idx = 1
    mapping = {}
    current = tgt.TARGET["wordlist"]
    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="brand.red",
        expand=True,
        pad_edge=True,
    )
    table.add_column("KEY", justify="center", no_wrap=True, width=7)
    table.add_column("WORDLIST", style="brand.white", ratio=1)
    table.add_column("PROFILE", style="brand.muted", no_wrap=True)
    table.add_column("STATE", justify="right", no_wrap=True)
    for path, desc in available:
        state = "[brand.info]ACTIVE[/brand.info]" if path == current else "[brand.ok]READY[/brand.ok]"
        table.add_row(
            Text(f" {idx} ", style="bold brand.ok"),
            escape(path),
            desc,
            state,
        )
        mapping[str(idx)] = path
        idx += 1
    for path, desc in WORDLISTS:
        if not os.path.exists(path):
            table.add_row(
                Text(" - ", style="bold bright_red"),
                f"[bright_red]{escape(path)}[/bright_red]",
                desc,
                "[bright_red]MISSING[/bright_red]",
            )
    table.add_row(
        Text(f" {idx} ", style="bold brand.warn"),
        "[brand.warn]Custom path[/brand.warn]",
        "manual override",
        "[brand.warn]INPUT[/brand.warn]",
    )
    console.print(Padding(table, (1, 0, 0, 0)))
    custom_key = str(idx)

    has_missing = any(not os.path.exists(p) for p, _ in WORDLISTS)
    footer_hints = ["[brand.red]r / 0[/brand.red] cancel and keep current"]
    if has_missing:
        footer_hints.append("[brand.red]d[/brand.red] download missing wordlists")
    console.print(_footer_panel(footer_hints))
    default = tgt.TARGET["wordlist"]
    choice = console.input(
        f"\n[brand.red]WORDLIST[/brand.red] [brand.muted]default: {escape(default)}[/brand.muted] "
        "[brand.white]›[/brand.white] "
    ).strip()
    if not choice:
        return default
    if choice.lower() in BACK_KEYS:
        return default
    if choice.lower() == "d":
        from core import wordlists as _wl
        _wl.wordlist_menu()
        return select_wordlist()
    if choice == custom_key:
        path = ask("Wordlist path")
        return path or default
    return mapping.get(choice, default)


def _format_value(piece, fill):
    out = piece
    for k, v in fill.items():
        out = out.replace("{" + k + "}", str(v) if v is not None else "")
    return out


def _launch_panel(tool, preset, cmd, route, output_path):
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(
        f"[brand.muted]TOOL[/brand.muted]\n[brand.white]{escape(tool['name'])}[/brand.white]",
        f"[brand.muted]PRESET[/brand.muted]\n[brand.red]{escape(preset['label'])}[/brand.red]",
    )
    grid.add_row(
        f"[brand.muted]ROUTE[/brand.muted]\n[brand.info]{escape(route)}[/brand.info]",
        f"[brand.muted]OUTPUT[/brand.muted]\n[brand.command]{escape(output_path or 'not saved')}[/brand.command]",
    )
    command = Text(shlex.join(cmd), style="brand.command", overflow="fold")
    return Panel(
        Group(
            grid,
            Padding(Text("COMMAND", style="brand.muted"), (1, 0, 0, 0)),
            command,
        ),
        title="[brand.red] LAUNCH MATRIX [/brand.red]",
        box=box.HEAVY,
        border_style="brand.red",
        padding=(1, 2),
    )


def run_preset(tool, preset, pause_after=True):
    fill = {
        "host": tgt.TARGET["host"],
        "url":  tgt.TARGET["url"],
        "port": tgt.TARGET["port"],
    }

    if tool.get("requires_ip"):
        host = fill["host"]
        try:
            socket.inet_pton(socket.AF_INET, host)
        except OSError:
            try:
                socket.inet_pton(socket.AF_INET6, host)
            except OSError:
                try:
                    resolved = socket.gethostbyname(host)
                    console.print(f"[brand.muted][*] {tool['name']} requires an IP — resolved {escape(host)} → {escape(resolved)}[/brand.muted]")
                    fill["host"] = resolved
                except socket.gaierror:
                    console.print(f"[bright_red][!] Could not resolve '{escape(host)}' to an IP address. {escape(tool['name'])} requires an IP.[/bright_red]")
                    return

    if preset.get("wordlist"):
        fill["wordlist"] = select_wordlist()
        tgt.TARGET["wordlist"] = fill["wordlist"]

    has_prompts = bool(preset.get("prompt"))
    for var, label in (preset.get("prompt") or {}).items():
        val = ask(label)
        if not val:
            console.print(f"[bright_yellow][!] '{label}' left empty — the command may fail.[/bright_yellow]")
        fill[var] = val

    cmd = [_format_value(p, fill) for p in preset["cmd"]]
    if cmd and cmd[0] == tool["binary"]:
        cmd[0] = resolve_tool_binary(tool)

    # UX-005 : confirmation avant lancement quand des paramètres ont été saisis
    if has_prompts:
        console.print(Panel(Text(shlex.join(cmd), style="brand.command"), border_style="brand.warn", box=box.SQUARE))
        rep = console.input("[brand.warn]Run? [Y/n][/brand.warn] [brand.white]›[/brand.white] ").strip().lower()
        if rep not in ("", "y", "yes", "o", "oui"):
            console.print("[brand.muted]Cancelled.[/brand.muted]")
            return

    output_path = None
    out_base = preset.get("output")
    if out_base:
        cat = tgt.category_dir(tool["output_dir"])
        if cat is not None:
            output_path = str(executor.target_path(cat, out_base, tgt.target_name()))
        else:
            console.print("[brand.warn][!] No target defined - results will not be saved.[/brand.warn]")

    interactive = tool.get("interactive", False)
    route = "LOCAL / direct" if tool.get("category") == "passwords" else route_status(tool)
    if should_proxy_tool(tool):
        cmd = wrap_command(cmd)
    elif PROXY_STATE["enabled"]:
        console.print("[brand.muted]Proxy/VPN skipped for this local or network-interface tool.[/brand.muted]")
    console.print(_launch_panel(tool, preset, cmd, route, output_path))
    executor.run_tool(cmd, output_path=output_path, interactive=interactive)
    if pause_after:
        pause()


def run_tool_menu(tool, _key=None):
    """Tool preset sub-menu. Returns cleanly via 'r'."""
    if not tool_available(tool):
        console.print(
            Panel(
                Group(
                    f"[bright_red]{escape(tool['name'])} is not installed on this system.[/bright_red]",
                    f"[brand.muted]Binary searched: {escape(tool['binary'])}[/brand.muted]",
                ),
                title="[bright_red] TOOL OFFLINE [/bright_red]",
                border_style="bright_red",
                box=box.HEAVY,
            )
        )
        pause()
        return

    requires_target = tool["category"] not in ("passwords", "wireless", "network")
    if requires_target and not tgt.is_defined():
        console.print(
            Panel(
                "[bright_red]Set a target first with option 0 in the main menu.[/bright_red]",
                title="[bright_red] TARGET REQUIRED [/bright_red]",
                border_style="bright_red",
                box=box.HEAVY,
            )
        )
        pause()
        return

    presets = tool.get("presets", [])
    if not presets:
        note = tool.get("note", "No preset available for this tool.")
        console.print(
            Panel(
                f"[brand.info]{escape(note)}[/brand.info]",
                title="[brand.info] NOTE [/brand.info]",
                border_style="brand.info",
                box=box.SQUARE,
            )
        )
        pause()
        return

    if len(presets) == 1:
        try:
            run_preset(tool, presets[0])
        except KeyboardInterrupt:
            console.print("\n[bright_yellow][!] Interrupted with Ctrl+C.[/bright_yellow]")
            pause()
        except Exception as e:
            console.print(f"\n[bright_red][!] Error: {e}[/bright_red]")
            pause()
        return

    while True:
        entries = [
            (str(i + 1), p["label"], "brand.ok", "ready-to-run command preset", "[brand.ok]READY[/brand.ok]")
            for i, p in enumerate(presets)
        ]
        tool_footer = context_footer()
        tool_footer.append(f"[brand.red]Binary[/brand.red] [brand.command]{escape(resolve_tool_binary(tool))}[/brand.command]")
        choice = menu(
            f"{tool['name']} - {tool.get('desc', '')}",
            entries,
            footer_extra=tool_footer,
        )

        if choice in BACK_KEYS:
            return

        if choice.isdigit() and 1 <= int(choice) <= len(presets):
            try:
                run_preset(tool, presets[int(choice) - 1])
            except KeyboardInterrupt:
                console.print("\n[bright_yellow][!] Interrupted with Ctrl+C.[/bright_yellow]")
                pause()
            except Exception as e:
                console.print(f"\n[bright_red][!] Error: {e}[/bright_red]")
                pause()
        else:
            console.print("[bright_red]Invalid choice.[/bright_red]")
            pause()


def category_menu(title, tool_keys):
    """Category menu listing the tools with their description."""
    from core.tools import get_tool

    while True:
        entries = []
        idx_map = {}
        for i, k in enumerate(tool_keys, start=1):
            tool = get_tool(k)
            if tool is None:
                continue
            desc = tool.get("desc", "")
            if tool_available(tool):
                entries.append((str(i), tool["name"], "brand.ok", desc, "[brand.ok]READY[/brand.ok]"))
            else:
                entries.append((str(i), tool["name"], "bright_red", desc, "[bright_red]MISSING[/bright_red]"))
            idx_map[str(i)] = k

        choice = menu(title, entries, footer_extra=context_footer())

        if choice in BACK_KEYS:
            return

        if choice in idx_map:
            tool = get_tool(idx_map[choice])
            run_tool_menu(tool, idx_map[choice])
        else:
            console.print("[bright_red]Invalid choice.[/bright_red]")
            pause()


# ---------------------------------------------------------------------------
# Startup check (style airgeddon)
# ---------------------------------------------------------------------------

def startup_check():
    """
    Checks the availability of all tools (airgeddon-style).
    UX-004 : affiche seulement les outils manquants pour ne pas bloquer au démarrage.
    """
    from core.tools import TOOLS
    from core.installer import install_missing

    banner()
    console.print(
        Panel(
            Align.center(Text("ARSENAL READINESS SCAN", style="brand.white")),
            box=box.HEAVY,
            border_style="brand.red",
            padding=(0, 2),
        )
    )

    present = []
    missing = []
    with console.status("[brand.red]Mapping local tools...[/brand.red]", spinner="dots"):
        for key, tool in {**TOOLS, **SUPPORT_TOOLS}.items():
            binary = tool["binary"]
            ok = tool_available(tool)
            (present if ok else missing).append((key, binary, tool))

    ok_count  = len(present)
    nok_count = len(missing)
    total     = ok_count + nok_count
    ratio = f"{ok_count}/{total}"

    summary = Table.grid(expand=True)
    for _ in range(3):
        summary.add_column(ratio=1)
    summary.add_row(
        _metric("READY", ratio, "brand.ok" if nok_count == 0 else "brand.warn"),
        _metric("MISSING", nok_count, "brand.ok" if nok_count == 0 else "bright_red"),
        _metric("MODE", "root session", "brand.red"),
    )
    console.print(Padding(summary, (1, 0, 1, 0)))

    if nok_count == 0:
        console.print(
            Panel(
                f"[brand.ok]All {total} tools are available.[/brand.ok]",
                border_style="brand.ok",
                box=box.HEAVY,
            )
        )
        pause()
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="brand.red",
        expand=True,
        pad_edge=True,
    )
    table.add_column("TOOL", style="bright_red", no_wrap=True)
    table.add_column("BINARY", style="brand.command", no_wrap=True)
    table.add_column("WHY IT MATTERS", style="brand.muted", ratio=1)
    for _, binary, tool in missing:
        name = tool["name"]
        desc = tool.get("desc", "")
        hint = ""
        if binary == "httpx" and shutil.which("httpx"):
            hint = " [brand.muted](system httpx is the Python library, not ProjectDiscovery)[/brand.muted]"
        table.add_row(escape(name), escape(binary), f"{escape(desc)}{hint}")
    console.print(table)

    console.print(
        Panel(
            "[brand.warn]Missing binaries:[/brand.warn] "
            + ", ".join(f"[brand.command]{escape(b)}[/brand.command]" for _, b, _ in missing),
            border_style="brand.warn",
            box=box.SQUARE,
        )
    )
    rep = console.input(
        "[brand.warn]Install missing tools now? [y/N][/brand.warn] [brand.white]›[/brand.white] "
    ).strip().lower()

    if rep in ("y", "yes", "o", "oui"):
        install_missing([(k, b) for k, b, _ in missing], assume_yes=True)

    console.print()
    pause()
