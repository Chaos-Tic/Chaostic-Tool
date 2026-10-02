"""Capture English UI screenshots for the docs, offscreen and deterministic.

Run from the repo root:
    QT_QPA_PLATFORM=offscreen PYTHONUTF8=1 python scripts/capture-screens.py [outdir]

Seeds an isolated data home with a couple of targets and sample history so the
home and history screens are populated, forces the dark (and light) theme and
the English language, then grabs each page to docs/images/windows/desktop-1.1-*.
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
        "theme": theme, "language": "en", "animations": False, "animation_fps": 60,
    }), encoding="utf-8")


def grab(window, name):
    from PySide6.QtWidgets import QApplication
    for _ in range(6):
        QApplication.processEvents()
    window.grab().save(str(OUT / name))
    print("saved", name)


def main():
    from PySide6.QtWidgets import QApplication
    from desktop.storage import Store
    from desktop import theme as thememod
    from desktop.window import Window, TargetDialog

    app = QApplication.instance() or QApplication(sys.argv)

    home = Path(tempfile.mkdtemp(prefix="chaostic-shots-"))
    seed(home)

    # Red Ops default theme, English.
    build_settings(home, "dark")
    thememod.apply_theme(app, "dark")
    store = Store(home)
    win = Window(store)
    win.resize(*SIZE)
    win.show()
    QApplication.processEvents()

    win.navigate(0); grab(win, "desktop-1.1-accueil.png")
    win.navigate(2); grab(win, "desktop-1.1-arsenal.png")
    # A real local diagnostic illustrates execution without contacting a target.
    from PySide6.QtTest import QTest
    import time
    win.launch("desktop-diagnostic", show_dialog=False)
    deadline=time.monotonic()+15
    while win.runner.active and time.monotonic()<deadline: QTest.qWait(30)
    if win.runner.active: raise RuntimeError("Diagnostic capture timed out")
    win.navigate(3); grab(win, "desktop-1.1-execution.png")
    win.navigate(4); grab(win, "desktop-1.1-historique.png")
    win.navigate(5); grab(win, "desktop-1.1-linux.png")
    win.navigate(6); grab(win, "desktop-1.1-flows.png")

    dlg = TargetDialog(win); dlg.resize(520, 300); dlg.show()
    QApplication.processEvents()
    dlg.grab().save(str(OUT / "desktop-1.1-formulaire.png")); print("saved formulaire")
    dlg.close()

    win.navigate(0); win.resize(900,600); grab(win, "desktop-1.1-compact.png")
    win.close()

    # Light theme home.
    build_settings(home, "light")
    thememod.apply_theme(app, "light")
    store2 = Store(home)
    win2 = Window(store2)
    win2.resize(*SIZE)
    win2.show()
    win2.navigate(0); grab(win2, "desktop-1.1-clair.png")
    win2.close()

    print("DONE")


if __name__ == "__main__":
    main()
