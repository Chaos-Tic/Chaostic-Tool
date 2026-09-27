"""Local, per-user state. Never writes into the application installation."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_root() -> Path:
    if custom := os.environ.get("CHAOSTIC_DESKTOP_HOME"):
        return Path(custom).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "ChaosticTool" / "Desktop"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def parse_target(value: str, label: str = "") -> dict:
    value = value.strip()
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Indiquez un domaine, une adresse IP ou une URL sans espaces.")
    try:
        ip = ipaddress.ip_address(value)
        value = f"[{ip}]" if ip.version == 6 else str(ip)
    except ValueError:
        pass
    try:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        port = parsed.port
        host = parsed.hostname or ""
    except ValueError as exc:
        raise ValueError("Adresse ou port invalide.") from exc
    if parsed.scheme not in ("http", "https") or parsed.username is not None or parsed.password is not None:
        raise ValueError("Utilisez une adresse HTTP(S) sans identifiants intégrés.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii").rstrip(".")
        except UnicodeError as exc:
            raise ValueError("Nom de domaine invalide.") from exc
        if len(host) > 253 or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", p) for p in host.split(".")):
            raise ValueError("Utilisez une seule cible : domaine, IPv4 ou IPv6.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Le port doit être compris entre 1 et 65535.")
    netloc = f"[{host}]" if ":" in host else host
    if port:
        netloc += f":{port}"
    return {
        "id": uuid.uuid4().hex,
        "label": label.strip()[:100] or host,
        "host": host,
        "port": port or (443 if parsed.scheme == "https" else 80),
        "url": urlunsplit((parsed.scheme, netloc, parsed.path or "/", parsed.query, "")),
        "created": now(),
    }


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or data_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "settings.json"
        self.warning = ""
        self.settings = {"targets": [], "active_target": "", "executables": {}}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict) or not isinstance(loaded.get("targets", []), list) or not isinstance(loaded.get("executables", {}), dict):
                    raise ValueError("Format invalide")
                for target in loaded.get("targets", []):
                    if not isinstance(target, dict) or not all(k in target for k in ("id", "label", "host", "port", "url")):
                        raise ValueError("Cible invalide")
                self.settings.update(loaded)
            except (ValueError, OSError):
                backup = self.path.with_name(f"settings-unreadable-{uuid.uuid4().hex[:8]}.json")
                self.path.replace(backup)
                self.warning = f"Les paramètres illisibles ont été conservés dans {backup.name}."
        self.recover_runs()

    def save(self):
        write_json(self.path, self.settings)

    @property
    def targets(self):
        return self.settings["targets"]

    @property
    def active_target(self):
        return next((t for t in self.targets if t["id"] == self.settings["active_target"]), None)

    def add_target(self, value, label=""):
        target = parse_target(value, label)
        for existing in self.targets:
            if existing["url"] == target["url"]:
                self.settings["active_target"] = existing["id"]
                self.save()
                return existing
        self.targets.append(target)
        self.settings["active_target"] = target["id"]
        self.save()
        return target

    def remove_target(self, identifier):
        self.settings["targets"] = [t for t in self.targets if t["id"] != identifier]
        if self.settings["active_target"] == identifier:
            self.settings["active_target"] = self.targets[0]["id"] if self.targets else ""
        self.save()

    def history(self):
        records = []
        for path in (self.root / "runs").glob("*/run.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(record, dict) and record.get("id") == path.parent.name:
                    record["directory"] = str(path.parent)
                    records.append(record)
            except (ValueError, OSError):
                continue
        return sorted(records, key=lambda r: r.get("started", ""), reverse=True)

    def recover_runs(self):
        for run in self.history():
            if run.get("status") == "running":
                run.update(status="interrupted", finished=now(), detail="Application fermée avant la fin de l’opération.")
                directory = run.pop("directory")
                write_json(Path(directory) / "run.json", run)

    def new_run(self, tool, preset, target, command):
        identifier = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        directory = self.root / "runs" / identifier
        directory.mkdir(parents=True)
        record = dict(id=identifier, tool=tool, preset=preset, target=target,
                      command=command, started=now(), status="running")
        write_json(directory / "run.json", record)
        return directory, record
