import json
import shlex
from pathlib import Path

from core import target as tgt
from core import ui
from core.paths import data_home, ensure_directory
from core.tools import get_tool
from core.flow_definitions import FLOWS

CUSTOM_FLOWS_PATH = data_home() / "custom_flows.json"
LEGACY_FLOWS_PATH = Path(__file__).resolve().parent.parent / "custom_flows.json"
CUSTOM_FLOWS: dict = {}



def _next_custom_key() -> str:
    existing = [int(k[3:]) for k in CUSTOM_FLOWS if k.startswith("cf-") and k[3:].isdigit()]
    n = max(existing, default=0) + 1
    return f"cf-{n}"


def _valid_flow(flow) -> bool:
    """Drop entries that are not flow objects so a corrupt file cannot poison the menu."""
    return isinstance(flow, dict)


def load_custom_flows() -> None:
    global CUSTOM_FLOWS
    path = CUSTOM_FLOWS_PATH if CUSTOM_FLOWS_PATH.exists() else LEGACY_FLOWS_PATH
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            CUSTOM_FLOWS.update({k: v for k, v in data.items() if _valid_flow(v)})
    except Exception as exc:
        try:
            from core import ui as _ui
            _ui.console.print(f"[bright_yellow][!] Could not load custom_flows.json: {exc}[/bright_yellow]")
        except Exception:
            pass


def save_custom_flows() -> None:
    persistent = {k: v for k, v in CUSTOM_FLOWS.items() if v.get("persistent")}
    try:
        ensure_directory(CUSTOM_FLOWS_PATH.parent)
        CUSTOM_FLOWS_PATH.write_text(
            json.dumps(persistent, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tgt._chown_path(CUSTOM_FLOWS_PATH)
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


def _resolve_steps(flow):
    """Resolve a flow's ``(tool_key, preset_index)`` pairs into run-ready records.

    Pure and side-effect free (no prompts, no process launch) so it is safe to
    build for the preview. Each record carries the resolved tool/preset objects
    (``None`` when the registry entry or the preset index is missing), an
    availability flag (is the binary installed), an ``enabled`` toggle the
    preview flips, and a live ``status`` the progress board reads.
    """
    records = []
    for tool_key, preset_idx in flow["steps"]:
        tool = get_tool(tool_key)
        preset = None
        problem = None
        if tool is None:
            problem = "missing registry entry"
        elif preset_idx >= len(tool.get("presets", [])):
            problem = f"missing preset #{preset_idx + 1}"
        else:
            preset = tool["presets"][preset_idx]
        records.append({
            "tool_key": tool_key, "preset_idx": preset_idx,
            "tool": tool, "preset": preset, "problem": problem,
            "available": bool(tool and preset and ui.tool_available(tool)),
            "enabled": problem is None,
            "status": "pending",
        })
    return records


def _preview_command(tool, preset):
    """Display argv for a step: the target host/url/port filled in, wordlist and
    prompted values left as literal placeholders (they are only asked at run
    time). Reuses the same ``ui._format_value`` substitution as a real launch."""
    fill = {"host": tgt.TARGET["host"], "url": tgt.TARGET["url"], "port": tgt.TARGET["port"]}
    return [ui._format_value(part, fill) for part in preset["cmd"]]


def _render_preview(records):
    """List resolved steps with an on/off marker, label and previewed command
    (same tool/preset resolution as ``_render_steps``, plus the toggle state)."""
    for i, r in enumerate(records, 1):
        tool = r["tool"]
        tname = tool["name"] if tool else r["tool_key"]
        mark = "[brand.ok][on ][/brand.ok]" if r["enabled"] else "[brand.muted][off][/brand.muted]"
        if r["problem"]:
            ui.console.print(f"  {mark} [brand.red]{i}.[/brand.red] [brand.white]{tname}[/brand.white] "
                             f"[bright_red]— {r['problem']}[/bright_red]")
            continue
        avail = "" if r["available"] else " [bright_red](not installed)[/bright_red]"
        ui.console.print(f"  {mark} [brand.red]{i}.[/brand.red] [brand.white]{tname}[/brand.white] "
                         f"[brand.muted]— {r['preset']['label']}[/brand.muted]{avail}")
        ui.console.print(f"        [brand.command]{shlex.join(_preview_command(tool, r['preset']))}[/brand.command]")


def _preview_flow(flow, records):
    """Show the resolved steps and let the user enable/disable any before launch.

    Mutates ``records[*]['enabled']``. Returns True to launch, False to cancel.
    """
    while True:
        ui.header(f"Flow preview — {flow['name']}")
        ui.console.print(
            f"[brand.muted]{flow['desc']}[/brand.muted]\n"
            f"[brand.red]Target[/brand.red] [brand.ok]{tgt.summary()}[/brand.ok]\n"
        )
        _render_preview(records)
        ui.console.print(
            "\n[brand.muted]Commands:[/brand.muted]  "
            "[brand.red]<n>[/brand.red] toggle step  "
            "[brand.red]a[/brand.red] all on  "
            "[brand.red]none[/brand.red] all off  "
            "[brand.red]go[/brand.red] launch  "
            "[brand.red]r[/brand.red] cancel\n"
        )
        raw = ui.console.input("[brand.red]>[/brand.red] ").strip().lower()

        if raw == "go":
            if not any(r["enabled"] for r in records):
                ui.console.print("[bright_yellow][!] No step enabled — nothing to run.[/bright_yellow]")
                continue
            return True
        if raw in ui.BACK_KEYS:
            return False
        if raw == "a":
            for r in records:
                if r["problem"] is None:
                    r["enabled"] = True
        elif raw == "none":
            for r in records:
                r["enabled"] = False
        elif raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(records) and records[idx]["problem"] is None:
                records[idx]["enabled"] = not records[idx]["enabled"]


def _ask_mode():
    """Ask the run mode once per launch. Returns 'auto' (chain every step, stop
    only on failure or Ctrl-C) or 'step' (confirm/pause between steps)."""
    ui.console.print(
        "\n[brand.warn]Run mode:[/brand.warn]  "
        "[brand.red]1[/brand.red] Step by step [brand.muted](confirm/pause each step)[/brand.muted]   "
        "[brand.red]2[/brand.red] Run all [brand.muted](auto-chain, stop on failure or Ctrl+C)[/brand.muted]"
    )
    rep = ui.console.input("[brand.red]>[/brand.red] ").strip().lower()
    return "auto" if rep in ("2", "all", "auto") else "step"


_PROGRESS_GLYPH = {"done": ("✓", "brand.ok"), "failed": ("✗", "brand.danger"),
                   "aborted": ("✗", "brand.warn"), "skipped": ("»", "brand.muted")}


def _progress_recap(active, current_index):
    """One row per enabled step — done / running / upcoming — drawn before each
    step so the chain's progress stays visible between runs."""
    total = len(active)
    ui.console.print(f"[brand.faint]── progress · {min(current_index, total)}/{total} ──[/brand.faint]")
    for idx, r in enumerate(active):
        name = r["tool"]["name"] if r["tool"] else r["tool_key"]
        if idx == current_index:
            glyph, style, word = "▶", "brand.accent", "now"
        elif idx < current_index:
            glyph, style = _PROGRESS_GLYPH.get(r["status"], ("·", "brand.faint"))
            word = r["status"]
        else:
            glyph, style, word = "·", "brand.faint", "queued"
        ui.console.print(f"  [{style}]{glyph}[/{style}] [brand.faint]{idx + 1}/{total}[/brand.faint] "
                         f"[brand.white]{name}[/brand.white] [brand.muted]{word}[/brand.muted]")


def run_flow(flow):
    if not tgt.is_defined():
        ui.console.print("\n[bright_red][!] Set a target first (option 0 in the main menu).[/bright_red]")
        ui.pause()
        return

    records = _resolve_steps(flow)

    # Preview every resolved step (built-in and custom flows alike) and let the
    # operator switch steps on/off before anything runs.
    if not _preview_flow(flow, records):
        return

    active = [r for r in records if r["enabled"]]
    if not active:
        return

    # One mode decision for the whole chain — never one confirmation per step.
    mode = _ask_mode()
    total = len(active)

    i = 0
    while i < len(active):
        r = active[i]
        step_no = i + 1
        tool, preset = r["tool"], r["preset"]

        ui.header(flow["name"])
        _progress_recap(active, i)
        ui.console.print(
            f"\n[brand.red][{step_no}/{total}][/brand.red] "
            f"[brand.white]{tool['name']}[/brand.white] "
            f"[brand.muted]- {preset['label']}[/brand.muted]"
        )

        if not r["available"]:
            ui.console.print(f"[bright_red]    skipped: {tool['binary']} is not installed[/bright_red]")
            r["status"] = "skipped"
            i += 1
            continue

        if mode == "step":
            try:
                rep = ui.console.input(
                    "[brand.warn]Run step? [Y]es · [s]kip · [r]eplay previous · [q]uit[/brand.warn] "
                    "[brand.white]›[/brand.white] "
                ).strip().lower()
            except (KeyboardInterrupt, EOFError):
                rep = "q"
            if rep in ("q", "quit"):
                ui.console.print("[brand.muted]Flow stopped.[/brand.muted]")
                ui.pause()
                return
            if rep in ("s", "skip"):
                ui.console.print("[brand.muted]Skipped.[/brand.muted]")
                r["status"] = "skipped"
                i += 1
                continue
            if rep in ("r", "replay"):
                if i > 0:
                    i -= 1
                    active[i]["status"] = "pending"
                else:
                    ui.console.print("[brand.muted]Nothing to replay yet.[/brand.muted]")
                continue

        flow_ctx = {"name": flow["name"], "index": step_no, "total": total}
        r["status"] = "running"
        try:
            rc = ui.run_preset(tool, preset, pause_after=(mode == "step"), flow_context=flow_ctx)
        except KeyboardInterrupt:
            ui.console.print("\n[bright_yellow][!] Flow interrupted with Ctrl+C.[/bright_yellow]")
            r["status"] = "aborted"
            ui.pause()
            return

        if rc == 130:  # aborted mid-run — leave the chain
            ui.console.print("\n[bright_yellow][!] Flow stopped (step aborted).[/bright_yellow]")
            r["status"] = "aborted"
            ui.pause()
            return
        if mode == "auto" and rc == 127:  # tool could not launch — stop the auto chain
            ui.console.print(f"\n[bright_red][!] {tool['name']} could not run — stopping run-all.[/bright_red]")
            r["status"] = "failed"
            ui.pause()
            return

        r["status"] = "done"
        i += 1

    ui.header(flow["name"])
    _progress_recap(active, len(active))
    ui.console.print("\n[brand.ok][+] Flow complete.[/brand.ok]")
    ui.pause()
