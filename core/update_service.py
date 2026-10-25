"""Anonymous GitHub release checks and verified downloads for both editions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

API = "https://api.github.com/repos/Chaos-Tic/Chaostic-Tool/releases/latest"
REPOSITORY = "https://github.com/Chaos-Tic/Chaostic-Tool"
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MARKER = re.compile(r"<!-- chaostictool-versions: (.*?) -->")
DAY = 24 * 60 * 60


def _open(request):
    context = ssl.create_default_context()
    if not context.get_ca_certs():
        for filename in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/cert.pem"):
            if Path(filename).is_file():
                context.load_verify_locations(cafile=filename)
                break
    return urlopen(request, timeout=8, context=context)


def version_tuple(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError("Invalid release version")
    return tuple(map(int, value.split(".")))


def _release_metadata(payload: dict) -> tuple[dict[str, str], dict[str, str]]:
    if payload.get("draft") or payload.get("prerelease"):
        raise ValueError("A stable public release is required")
    versions: dict[str, str] = {}
    tags: dict[str, str] = {}
    marker = MARKER.search(payload.get("body") or "")
    if marker:
        versions = json.loads(marker.group(1))
        if not isinstance(versions, dict):
            raise ValueError("Invalid edition metadata")
        versions = {key: value for key, value in versions.items() if key in ("cli", "desktop")}
        for value in versions.values():
            version_tuple(value)
        tags = {
            edition: ("desktop-v" if edition == "desktop" else "v") + version
            for edition, version in versions.items()
        }
    tag = payload.get("tag_name", "")
    if tag.startswith("desktop-v") and VERSION.fullmatch(tag[len("desktop-v"):]):
        versions["desktop"] = tag[len("desktop-v"):]
        tags["desktop"] = tag
    elif tag.startswith("v") and VERSION.fullmatch(tag[1:]):
        versions["cli"] = tag[1:]
        versions.setdefault("desktop", tag[1:])
        tags["cli"] = tag
        tags["desktop"] = tag
    return versions, tags


def release_versions(payload: dict) -> dict[str, str]:
    return _release_metadata(payload)[0]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".updates-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def check(edition: str, current: str, cache: Path, *, force: bool = False) -> dict:
    """At most one automatic request per day, including after a network error."""
    if edition not in ("cli", "desktop"):
        raise ValueError("Unknown edition")
    version_tuple(current)
    timestamp = time.time()
    data = {}
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        fresh = isinstance(data, dict) and 0 <= timestamp - float(data["checked_at"]) < DAY
        if fresh:
            for value in data.get("versions", {}).values():
                version_tuple(value)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        fresh = False
    if force or not fresh:
        data = {"checked_at": timestamp, "versions": {}, "tags": {}, "error": ""}
        try:
            request = Request(API, headers={"User-Agent": "ChaosticTool", "Accept": "application/vnd.github+json"})
            with _open(request) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Release metadata is too large")
            data["versions"], data["tags"] = _release_metadata(json.loads(raw))
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            data["error"] = str(exc)
        try:
            _write_json(cache, data)
        except OSError:
            pass  # Read-only user storage must not prevent launching the application.
    version = data.get("versions", {}).get(edition, "")
    tags = data.get("tags", {})
    tag = tags.get(edition, "") if isinstance(tags, dict) else ""
    if version and not tag:
        tag = ("desktop-v" if edition == "desktop" else "v") + version
    return {"version": version, "available": bool(version and version_tuple(version) > version_tuple(current)),
            "tag": tag, "url": f"{REPOSITORY}/releases/tag/{tag}" if tag else f"{REPOSITORY}/releases",
            "error": data.get("error", "") or ("No release metadata for this edition" if not version else "")}


def external_environment() -> dict[str, str]:
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        for key in ("LD_LIBRARY_PATH", "LIBPATH", "DYLD_LIBRARY_PATH"):
            previous = env.pop(key + "_ORIG", None)
            if previous:
                env[key] = previous
            else:
                env.pop(key, None)
        bundled = str(getattr(sys, "_MEIPASS", ""))
        for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
            if bundled and bundled in env.get(key, ""):
                env.pop(key, None)
    return env


def native_commands(package: str, application: Path) -> list[list[str]]:
    """Only use a package manager for an actual system-managed installation."""
    if package not in ("chaostictool", "chaostictool-desktop"):
        raise ValueError("Unknown package")
    path = str(application.resolve())
    locations = (f"/usr/share/{package}/", f"/usr/lib/{package}/", f"/usr/lib64/{package}/", f"/usr/libexec/{package}/")
    if not path.startswith(locations):
        return []
    candidates = (("dpkg-query", ["-W", "-f=${Status}", package]), ("rpm", ["-q", package]), ("pacman", ["-Q", package]))
    for program, args in candidates:
        if not shutil.which(program):
            continue
        try:
            result = subprocess.run([program, *args], capture_output=True, text=True, timeout=5, env=external_environment())
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode or (program == "dpkg-query" and result.stdout != "install ok installed"):
            continue
        if program == "dpkg-query":
            return [["apt-get", "update"], ["apt-get", "install", "--only-upgrade", package]]
        if program == "rpm":
            if shutil.which("dnf"):
                return [["dnf", "upgrade", "--refresh", package]]
            if shutil.which("zypper"):
                return [["zypper", "refresh"], ["zypper", "update", package]]
            return []
        helper = next((name for name in ("yay", "paru") if shutil.which(name)), None)
        return [[helper, "-Syu", package]] if helper else []
    return []


def installed_version(package: str, manager: str) -> str:
    if package not in ("chaostictool", "chaostictool-desktop"):
        raise ValueError("Unknown package")
    queries = {"apt-get": ["dpkg-query", "-W", "-f=${Version}", package],
               "dnf": ["rpm", "-q", "--qf", "%{VERSION}", package],
               "zypper": ["rpm", "-q", "--qf", "%{VERSION}", package],
               "yay": ["pacman", "-Q", package], "paru": ["pacman", "-Q", package]}
    try:
        result = subprocess.run(queries[manager], capture_output=True, text=True, timeout=5, env=external_environment())
        if result.returncode:
            return ""
        match = re.search(r"(?<![0-9.])([0-9]+\.[0-9]+\.[0-9]+)(?![0-9.])", result.stdout)
        return match[1] if match else ""
    except (KeyError, OSError, subprocess.TimeoutExpired):
        return ""


def replace_appimage(downloaded: Path, original: Path) -> Path:
    """Atomically replace a user-owned AppImage and retain its previous inode."""
    import uuid
    original = original.resolve(strict=True)
    if downloaded.suffix != ".AppImage" or original.stat().st_uid != os.geteuid():
        raise ValueError("Only an AppImage owned by the current user can be replaced")
    backup = original.with_name(original.name + ".previous-" + uuid.uuid4().hex[:8])
    descriptor, temporary = tempfile.mkstemp(prefix=".chaostic-update-", dir=original.parent)
    try:
        with os.fdopen(descriptor, "wb") as output, downloaded.open("rb") as source:
            shutil.copyfileobj(source, output)
        os.chmod(temporary, original.stat().st_mode & 0o777 | 0o100)
        os.link(original, backup)
        try:
            os.replace(temporary, original)
        except OSError:
            backup.unlink(missing_ok=True)
            raise
        return backup
    finally:
        Path(temporary).unlink(missing_ok=True)


def download_verified(tag: str, filename: str, destination: Path, *, cancelled=None) -> Path:
    """Download only this repository's named asset and require its SHA-256 file."""
    prefix = "desktop-v" if tag.startswith("desktop-v") else "v"
    version_tuple(tag[len(prefix):] if tag.startswith(prefix) else "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
        raise ValueError("Invalid artifact name")
    base = f"{REPOSITORY}/releases/download/{tag}/{filename}"
    with _open(Request(base + ".sha256", headers={"User-Agent": "ChaosticTool"})) as response:
        checksum = response.read(4097).decode("ascii").strip()
    match = re.fullmatch(r"([a-fA-F0-9]{64})[ \t]+\*?" + re.escape(filename), checksum)
    if not match:
        raise ValueError("The published checksum does not match the requested artifact")
    destination.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".download-", dir=destination)
    digest = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(descriptor, "wb") as stream, _open(Request(base, headers={"User-Agent": "ChaosticTool"})) as response:
            while chunk := response.read(1024 * 1024):
                if cancelled and cancelled():
                    raise InterruptedError("Download cancelled")
                size += len(chunk)
                if size > 2 * 1024**3:
                    raise ValueError("Artifact exceeds the download limit")
                digest.update(chunk)
                stream.write(chunk)
        if cancelled and cancelled():
            raise InterruptedError("Download cancelled")
        if digest.hexdigest() != match.group(1).lower():
            raise ValueError("SHA-256 verification failed; the installer was discarded")
        target = destination / filename
        os.replace(temporary, target)
        if os.name == "nt":
            # Preserve Windows' normal Internet-download security checks.
            Path(str(target) + ":Zone.Identifier").write_text(f"[ZoneTransfer]\nZoneId=3\nHostUrl={base}\n", encoding="utf-8")
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)
