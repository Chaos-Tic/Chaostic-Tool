# Build on Windows: python -m PyInstaller packaging/windows/ChaosticTool.spec
from pathlib import Path
import importlib.metadata
import sys

root = Path(SPECPATH).resolve().parents[1]
license_files = []
for name in ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6", "psutil", "pyinstaller"):
    distribution = importlib.metadata.distribution(name)
    for entry in distribution.files or []:
        if "licenses" in entry.parts or entry.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
            path = distribution.locate_file(entry)
            if path.is_file():
                license_files.append((str(path), "licenses/" + name))
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.exists():
    license_files.append((str(python_license), "licenses/Python"))
a = Analysis(
    [str(root / "chaostic_desktop.py")], pathex=[str(root)],
    binaries=[], datas=[(str(root / "desktop/assets"), "desktop/assets"),
                         (str(root / "desktop/packages.json"), "desktop"),
                         (str(root / "LICENSE"), "."),
                         (str(root / "docs/DESKTOP.md"), "docs"),
                         (str(root / "docs/THIRD_PARTY.md"), "docs"),
                         (str(root / "docs/licenses"), "licenses/Qt"), *license_files],
    hiddenimports=[], hookspath=[], runtime_hooks=[],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick"],
    noarchive=False,
)
# QtGui's generic hook discovers optional plugins that this widget-only app never
# loads. Exclude PDF/virtual-keyboard plugins and their QML/Quick dependencies.
unused_dlls = {"qt6pdf.dll", "qt6virtualkeyboard.dll", "qpdf.dll"}
a.binaries = [item for item in a.binaries
              if "platforminputcontexts" not in item[0].lower().replace("\\", "/")
              and Path(item[0]).name.lower() not in unused_dlls
              and not Path(item[0]).name.lower().startswith(("qt6qml", "qt6quick"))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ChaosticTool",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / "desktop/assets/icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ChaosticTool")
