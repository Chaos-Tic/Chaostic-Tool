"""Wrap an already tested Linux bundle in an AppImage with a pinned runtime."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "tool", "runtime", "output"):
        parser.add_argument("--"+name, required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--arch", choices=("x64", "arm64"), required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.version):
        parser.error("version must be X.Y.Z")
    bundle, tool, runtime = (path.resolve() for path in (args.bundle, args.tool, args.runtime))
    if not (bundle/"ChaosticTool").is_file():
        parser.error("bundle must contain the tested ChaosticTool executable")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifact = output/f"ChaosticTool-{args.version}-linux-{args.arch}.AppImage"
    with tempfile.TemporaryDirectory(prefix="chaostic-appimage-") as directory:
        work = Path(directory)
        appdir = work/"ChaosticTool.AppDir"
        shutil.copytree(bundle, appdir/"usr/lib/chaostictool", symlinks=True)
        shutil.copyfile(bundle/"_internal/desktop/assets/icon.svg", appdir/"chaostictool.svg")
        (appdir/".DirIcon").symlink_to("chaostictool.svg")
        (appdir/"chaostictool.desktop").write_text("[Desktop Entry]\nType=Application\nName=ChaosticTool Desktop\nExec=AppRun\nIcon=chaostictool\nTerminal=false\nCategories=Network;Utility;\n")
        (appdir/"AppRun").write_text('#!/bin/sh\nroot="${APPDIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}"\nexec "$root/usr/lib/chaostictool/ChaosticTool" "$@"\n')
        (appdir/"AppRun").chmod(0o755)
        subprocess.run([str(tool), "--appimage-extract"], cwd=work, stdout=subprocess.DEVNULL, check=True)
        environment = dict(os.environ, ARCH="x86_64" if args.arch=="x64" else "aarch64", VERSION=args.version)
        subprocess.run([str(work/"squashfs-root/AppRun"), "--no-appstream", "--runtime-file", str(runtime), str(appdir), str(artifact)], env=environment, check=True)
    with artifact.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    artifact.with_name(artifact.name+".sha256").write_text(f"{digest}  {artifact.name}\n")
    print(artifact)


if __name__ == "__main__":
    main()
