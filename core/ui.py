import os
import shlex
import shutil
import socket
import subprocess

from rich import box
from rich.console import Group
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from core import executor, tui
from core import target as tgt
from core.proxy import PROXY_STATE, route_status, should_proxy_tool, wrap_command
from core.redaction import redact, secrets_for
from core.terminal import console
from core.theme import EYEBROW, EYEBROW_COMPACT
from core.version import VERSION

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
        f"[brand.faint]{label}[/brand.faint]\n"
        f"[{style}]{escape(str(value))}[/{style}]"
    )


def _badge(text, style="brand.badge.ok"):
    return f"[{style}] {text} [/{style}]"


def _title_row():
    """The window chrome row, like the mockup's 'chaostictool · linux-cli' bar."""
    host = tgt.TARGET["host"] or tgt.TARGET["url"]
    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(justify="right")
    row.add_row(
        Text.assemble(("chaostictool", "brand.white"), (" · linux-cli", "brand.faint")),
        Text.assemble(
            (f"root@{host}  " if host else "no target  ", "brand.faint"),
            ("● ", "brand.ok"),
            ("LIVE", "brand.ok"),
        ),
    )
    return row


def _status_strip():
    target, target_style = _target_state()
    proxy, proxy_style = _proxy_state()
    route = route_status()
    cells = Table.grid(expand=True, padding=(0, 2, 0, 0))
    for _ in range(4):
        cells.add_column(ratio=1)
    cells.add_row(
        _metric("TARGET", target, target_style),
        _metric("ROUTE", route, "brand.info" if route != "DIRECT" else "brand.ok"),
        _metric("PROXY", proxy, proxy_style),
        _metric("VERSION", f"v{VERSION}", "brand.accent"),
    )
    return cells


def _page_head(title, home=False):
    """Shared brand eyebrow, page title and a quiet accent rule."""
    eyebrow = EYEBROW if console.width >= 72 else EYEBROW_COMPACT
    rule_width = 14 if not home else min(max(console.width - 24, 14), 40)
    rule_row = Table.grid(expand=True)
    rule_row.add_column()
    rule_row.add_column(justify="right")
    rule_row.add_row(Text("─" * rule_width, style="brand.accent"), Text("", style="brand.accent"))
    if home:
        title_line = Text.assemble(("CHAOSTIC ", "brand.title"), ("TOOL", "brand.accent"))
    else:
        title_line = Text(str(title), style="bold brand.title")
    return [Text(eyebrow, style="brand.faint"), title_line, rule_row]


def _frame(body, breadcrumb=None, home=False):
    """Render the whole screen as ONE bordered terminal window: a title
    bar, a divider, the eyebrow/title/rule header, then the caller's
    content. Every screen shares this single-frame shape, like the
    desktop app's control-surface layout."""
    clear()
    parts = [_title_row(), Rule(style="brand.dim")]
    parts += _page_head(breadcrumb or "Main menu", home=home)
    if home:
        parts.append(Padding(_status_strip(), (1, 0, 0, 0)))
    parts.extend(body)
    console.print(Panel(Group(*parts), box=box.ROUNDED, border_style="brand.dim", padding=(1, 2)))


def banner():
    """Kept for backward compatibility: prints the home frame on its own."""
    _frame([], home=True)


def header(title):
    """Compact window chrome for a sub-screen: title bar + eyebrow/title head."""
    if tui.available():
        console.begin_screen(title)
        return
    _frame([], breadcrumb=title)


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
    if tui.available():
        console.pause()
        return
    console.input("\n[brand.muted]Press Enter to continue[/brand.muted] [brand.accent]▸[/brand.accent] ")


def ask(prompt, default=None):
    suffix = f" [brand.muted]({escape(str(default))})[/brand.muted]" if default else ""
    val = console.input(f"[brand.accent]{escape(prompt)}{suffix}[/brand.accent] [brand.white]▸[/brand.white] ").strip()
    return val or (default or "")


def context_footer():
    target, target_style = _target_state()
    proxy, proxy_style = _proxy_state()
    route = route_status()
    from core.cli_updates import notice
    updates = [f"[brand.info]{notice()}[/brand.info]"] if notice() else []
    return updates + [
        f"[brand.faint]target:[/brand.faint] [{target_style}]{escape(target)}[/{target_style}]",
        f"[brand.faint]route:[/brand.faint] [brand.info]{escape(route)}[/brand.info]",
        f"[brand.faint]proxy:[/brand.faint] [{proxy_style}]{escape(proxy)}[/{proxy_style}]",
    ]


def _footer_panel(lines):
    return Panel(
        Group(*(line for line in lines)),
        box=box.ROUNDED,
        border_style="brand.dim",
        padding=(0, 1),
    )


def _input_prompt():
    return console.input("\n[brand.accent]▸[/brand.accent] ").strip().lower()


def _entries_grid(entries):
    """Two-column '[01] Label' grid, like the mockup's main-menu phase list."""
    grid = Table.grid(expand=True, padding=(0, 2, 0, 0))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    cells = [
        Text.assemble((f"[{item[0]}] ", item[2]), (str(item[1]), "brand.white"))
        for item in entries
    ]
    for i in range(0, len(cells), 2):
        pair = cells[i:i + 2]
        if len(pair) == 1:
            grid.add_row(pair[0], "")
        else:
            grid.add_row(pair[0], pair[1])
    return grid


def _entries_list(entries):
    """Borderless KEY / MODULE / CAPABILITY / STATUS rows for sub-menus,
    sitting inside the single outer window instead of their own box."""
    show_status = any(len(item) > 4 for item in entries)
    table = Table(box=None, expand=True, show_header=False, show_edge=False, pad_edge=False)
    table.add_column("KEY", no_wrap=True, width=6)
    table.add_column("MODULE", no_wrap=True)
    table.add_column("CAPABILITY", style="brand.muted", ratio=1)
    if show_status:
        table.add_column("STATUS", justify="right", no_wrap=True)
    for item in entries:
        key, label, style = item[0], item[1], item[2]
        desc = item[3] if len(item) > 3 else None
        status = item[4] if len(item) > 4 else ""
        row = [Text(f"[{key}]", style=style), Text(str(label), style="brand.white"), desc or ""]
        if show_status:
            row.append(status)
        table.add_row(*row)
    return table


def menu(title, entries, footer_extra=None, show_back=True, home=False, routing_rows=None):
    """entries: list of (key, label, style[, desc[, status]]). Returns the key typed."""
    if tui.available():
        console.begin_screen(title)
        return tui.menu(
            title, entries, footer_extra=footer_extra, show_back=show_back,
            home=home, metrics=screen_metrics() if home else None,
            routing_rows=routing_rows,
        )
    body = []
    if home:
        body.append(Padding(Text("// ASSESSMENT PHASES", style="brand.faint"), (1, 0, 0, 0)))
        body.append(_entries_grid(entries))
    else:
        body.append(Padding(_entries_list(entries), (1, 0, 0, 0)))

    controls = "[brand.accent]r/0[/brand.accent] back" if show_back else "[brand.accent]99[/brand.accent] quit"
    status_bits = (
        ["[brand.ok]READY[/brand.ok]"]
        + list(footer_extra or [])
        + [controls, "[brand.faint]ctrl+c interrupt[/brand.faint]"]
    )
    footer_line = " [brand.faint]/[/brand.faint] ".join(status_bits)
    body.append(Rule(style="brand.dim"))
    body.append(footer_line)

    _frame(body, breadcrumb=title, home=home)
    return _input_prompt()


def select_wordlist():
    header("Wordlist selection")
    available = [(p, d) for p, d in WORDLISTS if os.path.exists(p)]
    idx = 1
    mapping = {}
    current = tgt.TARGET["wordlist"]
    table = Table(
        box=box.ROUNDED,
        border_style="brand.dim",
        expand=True,
        pad_edge=True,
        header_style="brand.faint",
    )
    table.add_column("KEY", justify="center", no_wrap=True, width=7)
    table.add_column("WORDLIST", style="brand.white", ratio=1)
    table.add_column("PROFILE", style="brand.muted", no_wrap=True)
    table.add_column("STATE", justify="right", no_wrap=True)
    for path, desc in available:
        state = _badge("ACTIVE", "brand.badge.info") if path == current else _badge("READY", "brand.badge.ok")
        table.add_row(
            Text(f"[{idx}]", style="brand.ok"),
            escape(path),
            desc,
            state,
        )
        mapping[str(idx)] = path
        idx += 1
    for path, desc in WORDLISTS:
        if not os.path.exists(path):
            table.add_row(
                Text("[-]", style="brand.danger"),
                f"[bright_red]{escape(path)}[/bright_red]",
                desc,
                _badge("MISSING", "brand.badge.bad"),
            )
    table.add_row(
        Text(f"[{idx}]", style="brand.warn"),
        "[brand.warn]Custom path[/brand.warn]",
        "manual override",
        _badge("INPUT", "brand.badge.warn"),
    )
    console.print(Padding(table, (1, 0, 0, 0)))
    custom_key = str(idx)

    has_missing = any(not os.path.exists(p) for p, _ in WORDLISTS)
    footer_hints = ["[brand.accent]r / 0[/brand.accent] cancel and keep current"]
    if has_missing:
        footer_hints.append("[brand.accent]d[/brand.accent] download missing wordlists")
    console.print(_footer_panel(footer_hints))
    default = tgt.TARGET["wordlist"]
    choice = console.input(
        f"\n[brand.accent]wordlist[/brand.accent] [brand.muted]default: {escape(default)}[/brand.muted] "
        "[brand.white]▸[/brand.white] "
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
        f"[brand.faint]TOOL[/brand.faint]\n[brand.white]{escape(tool['name'])}[/brand.white]",
        f"[brand.faint]PRESET[/brand.faint]\n[brand.accent]{escape(preset['label'])}[/brand.accent]",
    )
    grid.add_row(
        f"[brand.faint]ROUTE[/brand.faint]\n[brand.info]{escape(route)}[/brand.info]",
        f"[brand.faint]OUTPUT[/brand.faint]\n[brand.command]{escape(output_path or 'not saved')}[/brand.command]",
    )
    command = Text(shlex.join(cmd), style="brand.command", overflow="fold")
    return Panel(
        Group(
            grid,
            Padding(Text("COMMAND", style="brand.faint"), (1, 0, 0, 0)),
            command,
        ),
        title="[brand.accent] LAUNCH [/brand.accent]",
        box=box.ROUNDED,
        border_style="brand.dim",
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

    key_value = None
    needed = preset.get("needs_key")
    if needed:
        from core import api_keys
        key_value = api_keys.get(needed)
        if not key_value:
            spec = api_keys.SPEC_BY_ID.get(needed, {})
            console.print(f"[bright_red][!] This profile needs the {spec.get('label', needed)} API key. "
                          f"Set it from the main menu (k · API keys).[/bright_red]")
            return
        fill[f"{needed}_key"] = key_value

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
    redactions = secrets_for(fill, (preset.get("prompt") or {}).keys())
    if key_value:
        redactions = list(redactions) + [key_value]
    display_cmd = [redact(argument, redactions) for argument in cmd]

    # UX-005 : confirmation avant lancement quand des paramètres ont été saisis
    if has_prompts:
        console.print(Panel(Text(shlex.join(display_cmd), style="brand.command"), border_style="brand.warn", box=box.ROUNDED))
        rep = console.input("[brand.warn]Run? [Y/n][/brand.warn] [brand.white]▸[/brand.white] ").strip().lower()
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
    display_cmd = [redact(argument, redactions) for argument in cmd]
    fullscreen = tui.available()
    if not fullscreen:
        console.print(_launch_panel(tool, preset, display_cmd, route, output_path))
    executor.run_tool(
        cmd, output_path=output_path, interactive=interactive,
        context={"tool": tool["name"], "preset": preset["label"],
                 "category": tool["category"], "route": route, "wait": pause_after},
        timeout=preset.get("timeout"), redactions=redactions,
    )
    if pause_after and not fullscreen:
        pause()


def run_tool_menu(tool, _key=None, *, choose_preset=False):
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
                box=box.ROUNDED,
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
                box=box.ROUNDED,
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
                box=box.ROUNDED,
            )
        )
        pause()
        return

    if len(presets) == 1 and not choose_preset:
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
            (str(i + 1), p["label"], "brand.ok", "ready-to-run command preset", _badge("READY", "brand.badge.ok"))
            for i, p in enumerate(presets)
        ]
        tool_footer = context_footer()
        tool_footer.append(f"[brand.faint]binary[/brand.faint] [brand.command]{escape(resolve_tool_binary(tool))}[/brand.command]")
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
                entries.append((str(i), tool["name"], "brand.ok", desc, _badge("READY", "brand.badge.ok")))
            else:
                entries.append((str(i), tool["name"], "brand.danger", desc, _badge("MISSING", "brand.badge.bad")))
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
    from core.installer import install_missing
    from core.tools import TOOLS

    header("Arsenal readiness scan")

    present = []
    missing = []
    with console.status("[brand.accent]Mapping local tools...[/brand.accent]", spinner="dots"):
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
        _metric("MISSING", nok_count, "brand.ok" if nok_count == 0 else "brand.danger"),
        _metric("MODE", "root session", "brand.accent"),
    )
    console.print(Padding(Panel(summary, box=box.ROUNDED, border_style="brand.dim", padding=(0, 2)), (1, 0, 1, 0)))

    if nok_count == 0:
        console.print(
            Panel(
                f"[brand.ok]All {total} tools are available.[/brand.ok]",
                border_style="brand.ok",
                box=box.ROUNDED,
            )
        )
        pause()
        return

    table = Table(
        box=box.ROUNDED,
        border_style="brand.dim",
        expand=True,
        pad_edge=True,
        header_style="brand.faint",
    )
    table.add_column("TOOL", style="brand.danger", no_wrap=True)
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
            box=box.ROUNDED,
        )
    )
    rep = console.input(
        "[brand.warn]Install missing tools now? [Y/n][/brand.warn] [brand.white]▸[/brand.white] "
    ).strip().lower()

    if rep in ("", "y", "yes", "o", "oui"):
        install_missing([(k, b) for k, b, _ in missing], assume_yes=True)

    console.print()
    pause()


def screen_metrics():
    """Return actual session values for the home dashboard."""
    from core.proxy import get_default_interface

    guard = "OFF"
    if PROXY_STATE["enabled"] and PROXY_STATE["mode"] == "vpn":
        chosen = PROXY_STATE.get("interface") or "unknown"
        default = get_default_interface() or "unknown"
        guard = f"{chosen} / default {default}"
    return [
        ("TARGET", tgt.TARGET["host"] or tgt.TARGET["url"] or "not configured"),
        ("ROUTE", route_status()),
        ("VPN GUARD", guard),
        ("OUTPUT", str(tgt.target_dir() or "no target")),
    ]


def search_tools():
    """Search the registered tools, then explicitly choose a preset."""
    from core.tools import TOOLS

    entries = [
        (key, tool["name"], "brand.accent", tool.get("desc", ""), tool["category"])
        for key, tool in TOOLS.items()
    ]
    while True:
        selected = tui.menu("Search tools", entries, start_search=True)
        if selected in BACK_KEYS:
            return
        if selected in TOOLS:
            run_tool_menu(TOOLS[selected], selected, choose_preset=True)
