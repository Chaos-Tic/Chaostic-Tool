import shutil

from rich import box
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from core import ui
from core import target as tgt

console = ui.console


def view_results():
    while True:
        ui.header("Results & Session")

        if not tgt.is_defined():
            console.print("[bright_red][!] No target defined.[/bright_red]")
            ui.pause()
            return

        d = tgt.target_dir()
        if d is None or not d.exists():
            console.print("[bright_red][!] No results directory.[/bright_red]")
            ui.pause()
            return

        summary = Table.grid(expand=True)
        summary.add_column(ratio=1)
        summary.add_column(ratio=1)
        summary.add_row(
            f"[brand.muted]TARGET[/brand.muted]\n[brand.ok]{escape(tgt.summary())}[/brand.ok]",
            f"[brand.muted]RESULT ROOT[/brand.muted]\n[brand.command]{escape(str(d))}[/brand.command]",
        )
        console.print(
            Panel(
                summary,
                title="[brand.red] SESSION [/brand.red]",
                border_style="brand.red",
                box=box.HEAVY,
                padding=(1, 2),
            )
        )

        tree = Tree(f"[brand.red]{escape(str(d))}[/brand.red]")
        files = []
        for cat in sorted(d.iterdir()):
            if not cat.is_dir():
                continue
            cat_files = sorted([f for f in cat.glob("*") if f.is_file()])
            branch = tree.add(f"[brand.ok]{escape(cat.name)}/[/brand.ok] [brand.muted]({len(cat_files)})[/brand.muted]")
            for f in cat_files:
                files.append(f)
                branch.add(f"[brand.red]{len(files)}[/brand.red] [brand.white]{escape(f.name)}[/brand.white]")
        console.print(tree)

        console.print(
            Panel(
                "[brand.red]N[/brand.red] display    "
                "[brand.red]pN[/brand.red] print path    "
                "[bright_red]c[/bright_red] clean    "
                "[brand.red]r / 0[/brand.red] back",
                border_style="brand.dim",
                box=box.SQUARE,
            )
        )
        choice = console.input("\n[brand.red]╰─[/brand.red][brand.white]RESULTS[/brand.white][brand.red]▶[/brand.red] ").strip().lower()
        if choice in ui.BACK_KEYS or not choice:
            return
        if choice == "c":
            _clean_target_results(d)
            continue
        if not files:
            console.print("\n[brand.muted]No results saved yet.[/brand.muted]")
            ui.pause()
            continue
        if choice.startswith("p") and choice[1:].isdigit() and 1 <= int(choice[1:]) <= len(files):
            console.print(f"[brand.command]{escape(str(files[int(choice[1:]) - 1]))}[/brand.command]")
            ui.pause()
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            f = files[int(choice) - 1]
            console.print(
                Panel(
                    f"[brand.command]{escape(str(f))}[/brand.command]",
                    title="[brand.red] FILE VIEW [/brand.red]",
                    border_style="brand.red",
                    box=box.HEAVY,
                )
            )
            try:
                if _looks_binary(f):
                    console.print("[bright_yellow][!] Binary file, not displayed as text.[/bright_yellow]")
                    console.print(f"[brand.command]{escape(str(f))}[/brand.command]")
                else:
                    console.print(f.read_text(errors="replace"))
            except Exception as e:
                console.print(f"[bright_red]Read error: {e}[/bright_red]")
            ui.pause()


def _looks_binary(path):
    try:
        sample = path.read_bytes()[:2048]
    except Exception:
        return False
    return b"\0" in sample


def _clean_target_results(target_dir):
    target_name = target_dir.name
    console.print(
        Panel(
            f"[brand.warn]This will delete all files for target:[/brand.warn] "
            f"[brand.white]{escape(target_name)}[/brand.white]\n"
            f"[brand.command]{escape(str(target_dir))}[/brand.command]",
            title="[bright_red] DESTRUCTIVE ACTION [/bright_red]",
            border_style="bright_red",
            box=box.HEAVY,
        )
    )
    rep = console.input("[bright_red]Type CLEAN to confirm[/bright_red] [brand.white]›[/brand.white] ").strip()
    if rep != "CLEAN":
        console.print("[brand.muted]Cleanup cancelled.[/brand.muted]")
        ui.pause()
        return

    removed = 0
    for item in target_dir.iterdir():
        if item.name == ".gitkeep":
            continue
        try:
            if item.is_dir():
                for child in item.rglob("*"):
                    if child.is_file():
                        removed += 1
                shutil.rmtree(item)
            else:
                item.unlink()
                removed += 1
        except Exception as e:
            console.print(f"[bright_red][!] Could not remove {item}: {e}[/bright_red]")

    for cat in tgt.CATEGORIES:
        (target_dir / cat).mkdir(parents=True, exist_ok=True)
    try:
        tgt._chown_tree(target_dir)
    except Exception:
        pass

    console.print(f"[brand.ok][+] Target results cleaned. Removed {removed} file(s).[/brand.ok]")
    ui.pause()
