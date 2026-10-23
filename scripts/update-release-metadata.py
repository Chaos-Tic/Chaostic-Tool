"""Keep edition versions on the latest GitHub release for one-request update checks."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

REPOSITORY = "Chaos-Tic/Chaostic-Tool"
MARKER = re.compile(r"<!-- chaostictool-versions: .*? -->")


def gh(*arguments):
    return subprocess.check_output(["gh", *arguments], text=True)


def main():
    releases = json.loads(gh("release", "list", "--repo", REPOSITORY, "--exclude-drafts", "--exclude-pre-releases", "--limit", "100", "--json", "tagName"))
    versions = {}
    for item in releases:
        match = re.fullmatch(r"(desktop-v|v)([0-9]+\.[0-9]+\.[0-9]+)", item["tagName"])
        if not match:
            continue
        edition = "desktop" if match[1] == "desktop-v" else "cli"
        value = match[2]
        if edition not in versions or tuple(map(int, value.split("."))) > tuple(map(int, versions[edition].split("."))):
            versions[edition] = value
    latest = json.loads(gh("api", f"repos/{REPOSITORY}/releases/latest"))
    body = MARKER.sub("", latest.get("body") or "").rstrip()
    body += "\n\n<!-- chaostictool-versions: " + json.dumps(versions, sort_keys=True) + " -->\n"
    with tempfile.TemporaryDirectory() as directory:
        notes = Path(directory) / "notes.md"
        notes.write_text(body, encoding="utf-8")
        subprocess.run(["gh", "release", "edit", latest["tag_name"], "--repo", REPOSITORY, "--notes-file", str(notes)], check=True)
    print("Published edition metadata:", versions)


if __name__ == "__main__":
    main()
