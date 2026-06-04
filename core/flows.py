import json
from pathlib import Path

from core import target as tgt
from core import ui
from core.tools import get_tool

CUSTOM_FLOWS_PATH = Path(__file__).parent.parent / "custom_flows.json"
CUSTOM_FLOWS: dict = {}

FLOWS = {
    "1": {
        "name": "Basic attack flow",
        "desc": "low-noise first pass: DNS, quick ports, web fingerprint, default nuclei",
        "steps": [
            ("dig", 0),
            ("subfinder", 0),
            ("nmap", 0),
            ("httpx", 1),
            ("whatweb", 0),
            ("nuclei", 0),
        ],
    },
    "2": {
        "name": "Intermediate attack flow",
        "desc": "broader recon with crawling and URL history",
        "steps": [
            ("dig", 0),
            ("subfinder", 1),
            ("nmap", 1),
            ("naabu", 0),
            ("httpx", 1),
            ("katana", 1),
            ("gau", 1),
            ("waybackurls", 0),
            ("nuclei", 2),
            ("sslscan", 0),
        ],
    },
    "3": {
        "name": "Advanced attack flow",
        "desc": "deeper scans; louder and slower, confirm each step",
        "steps": [
            ("amass", 0),
            ("subfinder", 1),
            ("nmap", 1),
            ("rustscan", 2),
            ("ffuf", 0),
            ("gobuster", 0),
            ("katana", 2),
            ("nuclei", 1),
            ("nuclei", 2),
            ("testssl.sh", 0),
            ("nikto", 0),
        ],
    },
}


def _next_custom_key() -> str:
    existing = [int(k[3:]) for k in CUSTOM_FLOWS if k.startswith("cf-") and k[3:].isdigit()]
    n = max(existing, default=0) + 1
    return f"cf-{n}"


def load_custom_flows() -> None:
    global CUSTOM_FLOWS
    if not CUSTOM_FLOWS_PATH.exists():
        return
    try:
        data = json.loads(CUSTOM_FLOWS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            CUSTOM_FLOWS.update(data)
    except Exception as exc:
        try:
            from core import ui as _ui
            _ui.console.print(f"[bright_yellow][!] Could not load custom_flows.json: {exc}[/bright_yellow]")
        except Exception:
            pass


def save_custom_flows() -> None:
    persistent = {k: v for k, v in CUSTOM_FLOWS.items() if v.get("persistent")}
    try:
        CUSTOM_FLOWS_PATH.write_text(
            json.dumps(persistent, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        try:
            from core import ui as _ui
            _ui.console.print(f"[bright_red][!] Could not save custom_flows.json: {exc}[/bright_red]")
        except Exception:
            pass


def _pick_step():
    """Interactive picker: category → tool → preset. Returns [tool_key, preset_idx] or None."""
    from core.tools import TOOLS

    categories: dict = {}
    for key, tool in TOOLS.items():
        cat = tool.get("category", "other")
        categories.setdefault(cat, []).append((key, tool))

    cats_sorted = sorted(categories)
    cat_entries = [
        (str(i + 1), cat, "brand.ok", f"{len(categories[cat])} tools", "")
        for i, cat in enumerate(cats_sorted)
    ]
    choice = ui.menu("Pick a category", cat_entries)
    if choice in ui.BACK_KEYS:
        return None
    if not choice.isdigit() or not (1 <= int(choice) <= len(cats_sorted)):
        return None
    selected_cat = cats_sorted[int(choice) - 1]
    tools_in_cat = categories[selected_cat]

    tool_entries = [
        (str(i + 1), t["name"], "brand.ok", t.get("desc", ""), "")
        for i, (k, t) in enumerate(tools_in_cat)
    ]
    choice = ui.menu(f"Pick a tool ({selected_cat})", tool_entries)
    if choice in ui.BACK_KEYS:
        return None
    if not choice.isdigit() or not (1 <= int(choice) <= len(tools_in_cat)):
        return None
    tool_key, tool = tools_in_cat[int(choice) - 1]

    presets = tool.get("presets", [])
    if not presets:
        ui.console.print("[bright_red]This tool has no presets.[/bright_red]")
        ui.pause()
        return None
    preset_entries = [
        (str(i + 1), p["label"], "brand.ok", "", "")
        for i, p in enumerate(presets)
    ]
    choice = ui.menu(f"Pick a preset ({tool['name']})", preset_entries)
    if choice in ui.BACK_KEYS:
        return None
    if not choice.isdigit() or not (1 <= int(choice) <= len(presets)):
        return None
    return [tool_key, int(choice) - 1]


def _render_steps(steps: list) -> None:
    from core.tools import get_tool
    if not steps:
        ui.console.print("  [brand.muted](no steps yet)[/brand.muted]")
        return
    for i, (tk, pi) in enumerate(steps):
        tool = get_tool(tk)
        tname = tool["name"] if tool else tk
        plabel = (
            tool["presets"][pi]["label"]
            if tool and pi < len(tool.get("presets", []))
            else f"preset {pi}"
        )
        ui.console.print(
            f"  [brand.red]{i + 1}.[/brand.red] "
            f"[brand.white]{tname}[/brand.white] "
            f"[brand.muted]— {plabel}[/brand.muted]"
        )


def custom_flow_builder(existing_key: str | None = None) -> None:
    """Create or edit a custom flow. Pass existing_key to edit an existing one."""
    if existing_key and existing_key in CUSTOM_FLOWS:
        flow = CUSTOM_FLOWS[existing_key]
        name: str = flow["name"]
        desc: str = flow["desc"]
        steps: list = [list(s) for s in flow["steps"]]
    else:
        existing_key = None
        name = ""
        desc = ""
        steps = []

    ui.header("Custom flow builder")
    name = ui.ask("Flow name", name or None) or ""
    if not name:
        ui.console.print("[bright_red]Name required.[/bright_red]")
        ui.pause()
        return
    desc = ui.ask("Short description", desc or None) or ""

    while True:
        ui.header(f"Flow: {name}")
        _render_steps(steps)
        ui.console.print(
            "\n[brand.muted]Commands:[/brand.muted]  "
            "[brand.red]a[/brand.red] add  "
            "[brand.red]d <n>[/brand.red] delete  "
            "[brand.red]u <n>[/brand.red] move up  "
            "[brand.red]dn <n>[/brand.red] move down  "
            "[brand.red]ok[/brand.red] finish  "
            "[brand.red]r[/brand.red] cancel\n"
        )
        raw = ui.console.input("[brand.red]>[/brand.red] ").strip().lower()

        if raw in ui.BACK_KEYS:
            return
        elif raw == "ok":
            break
        elif raw == "a":
            step = _pick_step()
            if step:
                steps.append(step)
        elif raw.startswith("d ") and raw[2:].isdigit():
            idx = int(raw[2:]) - 1
            if 0 <= idx < len(steps):
                steps.pop(idx)
        elif raw.startswith("u ") and raw[2:].isdigit():
            idx = int(raw[2:]) - 1
            if 0 < idx < len(steps):
                steps[idx - 1], steps[idx] = steps[idx], steps[idx - 1]
            elif 0 <= idx < len(steps):
                ui.console.print("[brand.muted]Already at the top.[/brand.muted]")
        elif raw.startswith("dn ") and raw[3:].isdigit():
            idx = int(raw[3:]) - 1
            if 0 <= idx < len(steps) - 1:
                steps[idx], steps[idx + 1] = steps[idx + 1], steps[idx]
            elif 0 < idx < len(steps):
                ui.console.print("[brand.muted]Already at the bottom.[/brand.muted]")

    if not steps:
        ui.console.print("[bright_yellow][!] Flow has no steps — cancelled.[/bright_yellow]")
        ui.pause()
        return

    ui.console.print("\n[brand.warn]Save as:[/brand.warn]  [S]ession only  /  [P]ersistent (saved to disk)")
    choice = ui.console.input("[brand.red]>[/brand.red] ").strip().lower()
    persistent = choice.startswith("p")

    key = existing_key or _next_custom_key()
    CUSTOM_FLOWS[key] = {"name": name, "desc": desc, "steps": steps, "persistent": persistent}

    if persistent:
        save_custom_flows()
        ui.console.print(f"[brand.ok][+] Flow '[brand.white]{name}[/brand.white]' saved to disk.[/brand.ok]")
    else:
        ui.console.print(f"[brand.ok][+] Flow '[brand.white]{name}[/brand.white]' active for this session.[/brand.ok]")
    ui.pause()


def flow_menu() -> None:
    while True:
        entries = []
        # Built-in flows
        for key, flow in FLOWS.items():
            entries.append((
                key,
                flow["name"],
                "brand.info",
                flow["desc"],
                f"[brand.info]{len(flow['steps'])} STEPS[/brand.info]",
            ))
        # Custom flows
        for key, flow in CUSTOM_FLOWS.items():
            badge = "[brand.warn]CUSTOM[/brand.warn]"
            entries.append((
                key,
                flow["name"],
                "brand.warn",
                flow["desc"],
                f"[brand.warn]{len(flow['steps'])} STEPS[/brand.warn]  {badge}",
            ))
        # Actions
        entries.append(("n", "Créer un flow custom", "brand.muted", "builder interactif", ""))

        choice = ui.menu("Attack flows", entries, footer_extra=ui.context_footer())

        if choice in ui.BACK_KEYS:
            return

        if choice == "n":
            custom_flow_builder()
            continue

        if choice in FLOWS:
            run_flow(FLOWS[choice])
            continue

        if choice in CUSTOM_FLOWS:
            flow = CUSTOM_FLOWS[choice]
            ui.console.print(
                f"\n[brand.muted]Flow:[/brand.muted] [brand.white]{flow['name']}[/brand.white]   "
                "[brand.red]e[/brand.red] edit  [brand.red]del[/brand.red] delete  "
                "[brand.red]r[/brand.red] run  [brand.red]b[/brand.red] back"
            )
            action = ui.console.input("[brand.red]>[/brand.red] ").strip().lower()
            if action == "r":
                run_flow(flow)
            elif action == "e":
                custom_flow_builder(existing_key=choice)
            elif action == "del":
                confirm = ui.console.input(
                    f"[brand.warn]Delete '{flow['name']}'? [y/N][/brand.warn] "
                    "[brand.red]>[/brand.red] "
                ).strip().lower()
                if confirm in ("y", "yes", "o", "oui"):
                    del CUSTOM_FLOWS[choice]
                    if flow.get("persistent"):
                        save_custom_flows()
                    ui.console.print("[brand.ok][+] Flow deleted.[/brand.ok]")
                    ui.pause()
            continue

        ui.console.print("[bright_red]Invalid choice.[/bright_red]")
        ui.pause()


def run_flow(flow):
    if not tgt.is_defined():
        ui.console.print("\n[bright_red][!] Set a target first (option 0 in the main menu).[/bright_red]")
        ui.pause()
        return

    ui.header(flow["name"])
    ui.console.print(
        f"[brand.muted]{flow['desc']}[/brand.muted]\n"
        f"[brand.red]Target[/brand.red] [brand.ok]{tgt.summary()}[/brand.ok]    "
        f"[brand.red]Steps[/brand.red] [brand.info]{len(flow['steps'])}[/brand.info]\n"
    )
    for idx, (tool_key, preset_idx) in enumerate(flow["steps"], 1):
        tool = get_tool(tool_key)
        if not tool:
            ui.console.print(f"[bright_red][-] Missing registry entry: {tool_key}[/bright_red]")
            continue
        presets = tool.get("presets", [])
        if preset_idx >= len(presets):
            ui.console.print(f"[bright_red][-] Missing preset #{preset_idx + 1}: {tool['name']}[/bright_red]")
            continue
        preset = presets[preset_idx]

        ui.console.print(
            f"\n[brand.red][{idx}/{len(flow['steps'])}][/brand.red] "
            f"[brand.white]{tool['name']}[/brand.white] "
            f"[brand.muted]- {preset['label']}[/brand.muted]"
        )
        if not ui.tool_available(tool):
            ui.console.print(f"[bright_red]    skipped: {tool['binary']} is not installed[/bright_red]")
            continue

        rep = ui.console.input("[brand.warn]Run this step? [Y/n/q][/brand.warn] [brand.white]›[/brand.white] ").strip().lower()
        if rep == "q":
            ui.console.print("[brand.muted]Flow stopped.[/brand.muted]")
            ui.pause()
            return
        if rep == "n":
            ui.console.print("[brand.muted]Skipped.[/brand.muted]")
            continue

        try:
            ui.run_preset(tool, preset, pause_after=False)
        except KeyboardInterrupt:
            ui.console.print("\n[bright_yellow][!] Flow interrupted with Ctrl+C.[/bright_yellow]")
            ui.pause()
            return
