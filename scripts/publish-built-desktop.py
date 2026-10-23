"""Recover a draft from tested CI artifacts, allowing only final installer names."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REPO = "Chaos-Tic/Chaostic-Tool"


def gh(*args):
    return subprocess.check_output(["gh", *args, "--repo", REPO], text=True)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def expected_names(version):
    names = set()
    for arch in ("x64", "arm64"):
        for name in (f"ChaosticTool-Setup-{version}-windows-{arch}.exe", f"ChaosticTool-{version}-linux-{arch}.tar.gz", f"ChaosticTool-{version}-macos-{arch}.dmg"):
            names.update((name, name+".sha256"))
        names.add("linux-native-SHA256SUMS-"+arch)
    names.update((f"chaostictool-desktop_{version}_amd64.deb", f"chaostictool-desktop_{version}_arm64.deb",
                  f"chaostictool-desktop-{version}-1.x86_64.rpm", f"chaostictool-desktop-{version}-1.aarch64.rpm"))
    return names


def collect(source, output, version):
    expected = expected_names(version)
    output.mkdir()
    # Ignore CPack's nested staging files even in older oversized artifacts.
    for artifact in source.iterdir():
        if artifact.is_dir():
            for path in artifact.iterdir():
                if path.is_file() and path.name in expected:
                    if (output/path.name).exists():
                        raise ValueError("Duplicate final artifact: "+path.name)
                    shutil.copyfile(path, output/path.name)
    missing = expected - {path.name for path in output.iterdir()}
    if missing:
        raise ValueError("Missing final installers: "+", ".join(sorted(missing)))
    verified = set()
    for checksum in output.iterdir():
        if checksum.name.endswith(".sha256") or checksum.name.startswith("linux-native-SHA256SUMS-"):
            for line in checksum.read_text().splitlines():
                match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?([A-Za-z0-9_.-]+)", line)
                if not match or match[2] not in expected or digest(output/match[2]) != match[1].lower():
                    raise ValueError("Checksum failed: "+checksum.name)
                verified.add(match[2])
    packages = {name for name in expected if name.endswith((".exe", ".dmg", ".tar.gz", ".deb", ".rpm"))}
    if not packages.issubset(verified):
        raise ValueError("Every installer must have a verified checksum")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not args.run.isdigit() or not re.fullmatch(r"desktop-v[0-9]+\.[0-9]+\.[0-9]+", args.tag):
        parser.error("a numeric run and desktop-vX.Y.Z tag are required")
    run = json.loads(gh("run", "view", args.run, "--json", "headSha,headBranch,workflowName,jobs"))
    if run["headBranch"] != args.tag or run["workflowName"] != "Desktop Windows Linux macOS":
        raise ValueError("The artifacts must come from the desktop tag workflow")
    expected = {"Debian source package", "windows-x64", "windows-arm64", "linux-x64", "linux-arm64", "macos-x64", "macos-arm64"}
    passed = {job["name"] for job in run["jobs"] if job["conclusion"] == "success"}
    if not expected.issubset(passed):
        raise ValueError("Every build and installation check must pass before publication")
    ref = json.loads(subprocess.check_output(["gh", "api", f"repos/{REPO}/git/ref/tags/{args.tag}"], text=True))
    if ref["object"]["type"] != "commit" or ref["object"]["sha"] != run["headSha"]:
        raise ValueError("The tag no longer points to the tested commit")
    with tempfile.TemporaryDirectory() as directory:
        source, output = Path(directory)/"artifacts", Path(directory)/"final"
        gh("run", "download", args.run, "--dir", str(source))
        collect(source, output, args.tag.removeprefix("desktop-v"))
        try:
            state = json.loads(gh("release", "view", args.tag, "--json", "isDraft"))
        except subprocess.CalledProcessError:
            state = None
        if state is not None:
            if not state["isDraft"]:
                raise ValueError("A published release is immutable")
            # Only the generated, unpublished draft is replaced; the tag is retained.
            gh("release", "delete", args.tag, "--yes")
        gh("release", "create", args.tag, "--draft", "--verify-tag", "--title", "ChaosticTool Desktop "+args.tag.removeprefix("desktop-v"), "--generate-notes")
        gh("release", "upload", args.tag, *(str(path) for path in sorted(output.iterdir())))
        print("Verified draft contains", len(list(output.iterdir())), "final assets")


if __name__ == "__main__":
    main()
