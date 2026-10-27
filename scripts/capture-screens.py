"""Capture English UI screenshots for the docs, offscreen and deterministic.

Run from the repo root:
    QT_QPA_PLATFORM=offscreen PYTHONUTF8=1 python scripts/capture-screens.py [outdir]

Seeds isolated demo targets and history; captures light first, then dark.
No tool, diagnostic process or network request is started. English is the default
(CHAOSTIC_CAPTURE_LANGUAGE=fr for French).
"""
import os, sys, tempfile, json
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONUTF8", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ("docs/images/linux" if sys.platform.startswith("linux") else "docs/images/windows")
OUT.mkdir(parents=True, exist_ok=True)
SIZE = (1360, 860)


def seed(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    runs = home / "runs"
    runs.mkdir(exist_ok=True)
    samples = [
        ("nmap", "Nmap", "Top 100 common TCP ports", "success",
         {"id": "t1", "label": "Staging web", "host": "staging.example.com", "url": "https://staging.example.com", "port": 443},
         "2026-09-20T09:12:00+00:00"),
        ("httpx", "httpx", "Read the headers (HEAD)", "success",
         {"id": "t1", "label": "Staging web", "host": "staging.example.com", "url": "https://staging.example.com", "port": 443},
         "2026-09-21T14:03:00+00:00"),
        ("subfinder", "Subfinder", "Include subdomains", "failed",
         {"id": "t2", "label": "Lab host", "host": "10.0.0.5", "url": "10.0.0.5", "port": 0},
         "2026-09-22T18:41:00+00:00"),
    ]
    for i, (key, tool, preset, status, target, started) in enumerate(samples):
        d = runs / f"2026092{i}-000000__{key}__{i:08x}"
        d.mkdir(exist_ok=True)
        (d / "output.txt").write_text(f"{tool} {preset}\nSample output for documentation.\n", encoding="utf-8")
        (d / "run.json").write_text(json.dumps({
            "id": d.name, "tool": tool, "preset": preset, "status": status,
            "started": started, "finished": started, "directory": str(d),
            "command": ["sample"], "target": target, "exit_code": 0 if status == "success" else 2,
            "detail": "",
        }), encoding="utf-8")


def build_settings(home: Path, theme: str):
    (home / "settings.json").write_text(json.dumps({
        "targets": [
            {"id": "t1", "label": "Staging web", "host": "staging.example.com", "url": "https://staging.example.com", "port": 443},
            {"id": "t2", "label": "Lab host", "host": "10.0.0.5", "url": "10.0.0.5", "port": 0},
        ],
        "active_target": "t1", "executables": {},
        "theme": theme, "language": os.environ.get("CHAOSTIC_CAPTURE_LANGUAGE", "en"), "animations": False, "animation_fps": 60,
    }), encoding="utf-8")


def grab(window, name):
    from PySide6.QtWidgets import QApplication
    for _ in range(6):
        QApplication.processEvents()
    window.grab().save(str(OUT / name))
    print("saved", name)


def capture_set(app, home, theme, suffix):
    """Capture the full documentation screen set for one theme.

    `suffix` is appended before the extension (e.g. "-dark") so the light and
    dark passes write side-by-side files without overwriting each other.
    """
    from PySide6.QtWidgets import QApplication
    from desktop.storage import Store
    from desktop import theme as thememod
    from desktop.window import Window, TargetDialog

    build_settings(home, theme)
    thememod.apply_theme(app, theme)
    store = Store(home)
    win = Window(store)
    win.resize(*SIZE)
    win.show()
    QApplication.processEvents()

    win.navigate(0); grab(win, f"liquid-glass-accueil{suffix}.png")
    win.navigate(2); grab(win, f"liquid-glass-arsenal{suffix}.png")
    # Synthetic output: no process or network request is started for captures.
    win.console.setPlainText("Documentation demo\n\nPreparing an operation for staging.example.com\nChoose a tool and profile to begin.\n\nNo operation has been started.")
    win.navigate(3); grab(win, f"liquid-glass-execution{suffix}.png")
    win.navigate(4); grab(win, f"liquid-glass-historique{suffix}.png")
    win.navigate(5); grab(win, f"liquid-glass-linux{suffix}.png")
    win.navigate(6); grab(win, f"liquid-glass-flows{suffix}.png")

    dlg = TargetDialog(win); dlg.resize(520, 300); dlg.show()
    QApplication.processEvents()
    dlg.grab().save(str(OUT / f"liquid-glass-formulaire{suffix}.png")); print(f"saved formulaire{suffix}")
    dlg.close()

    win.navigate(0); win.resize(900, 600); grab(win, f"liquid-glass-compact{suffix}.png")
    win.close()


def main():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory(prefix="chaostic-shots-") as directory:
        home = Path(directory)
        seed(home)

        # Light is the primary documentation theme.
        capture_set(app, home, "light", "")

        # Complementary dark theme: same full set with a -dark suffix.
        capture_set(app, home, "dark", "-dark")

        # Keep the historical accueil-only dark alias for existing references.
        import shutil
        shutil.copyfile(OUT / "liquid-glass-accueil-dark.png", OUT / "liquid-glass-dark.png")
        print("saved liquid-glass-dark.png (alias)")
    print("DONE")


if __name__ == "__main__":
    main()
