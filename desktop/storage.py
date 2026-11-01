"""Local, per-user state. Never writes into the application installation."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import uuid
import unicodedata
import shutil
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
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
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


def retarget(target, host):
    """A copy of ``target`` pointed at another in-scope host, same scheme/port."""
    parsed = urlsplit(target.get("url", ""))
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    url = urlunsplit((parsed.scheme or "http", netloc, parsed.path or "/", parsed.query, ""))
    return dict(target, host=host, url=url)


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

    def update_target(self, identifier, value, label=""):
        target = next((t for t in self.targets if t["id"] == identifier), None)
        if target is None:
            return None
        updated = parse_target(value, label)
        updated["id"] = target["id"]
        updated["created"] = target.get("created", updated["created"])
        if updated["host"] == target.get("host"):
            # Same host: keep the cached subdomain scope; a host change drops it.
            for key in ("subdomains", "include_subdomains", "excluded"):
                if key in target:
                    updated[key] = target[key]
        target.clear()
        target.update(updated)
        self.save()
        return target

    def set_target_scope(self, identifier, include=None, subdomains=None, excluded=None):
        """Store subdomain scope on a target: cached list, on/off flag, exclusions."""
        from core import subdomains as sd
        target = next((t for t in self.targets if t["id"] == identifier), None)
        if target is None:
            return
        host = target.get("host", "")
        if subdomains is not None:
            target["subdomains"] = sorted({
                s.strip().lower().rstrip(".") for s in subdomains
                if isinstance(s, str) and s.strip()
                and sd.within_domain(s, host) and s.strip().lower().rstrip(".") != host.lower()})
            # Drop exclusions that no longer refer to a discovered subdomain.
            allowed = set(target["subdomains"])
            target["excluded"] = [s for s in target.get("excluded", []) if s in allowed]
        if excluded is not None:
            allowed = set(target.get("subdomains", []))
            target["excluded"] = sorted({s.strip().lower().rstrip(".") for s in excluded
                                         if isinstance(s, str) and s.strip().lower().rstrip(".") in allowed})
        if not target.get("subdomains"):
            target["include_subdomains"] = False
        elif include is not None:
            target["include_subdomains"] = bool(include)
        self.save()
        return target

    def scope_hosts(self, target, limit="default"):
        """Hosts a target expands to: base first, then subdomains when enabled.

        Exclusions are always applied; ``limit`` caps the count (base first), the
        default being the shared hard cap so a run never fans out silently to an
        unbounded number of hosts. Pass an integer to run only the first K, or
        ``None`` to disable the cap.
        """
        from core import subdomains as sd
        if not target:
            return []
        cap = sd.MAX_FANOUT if limit == "default" else limit
        return sd.scope_hosts(target.get("host", ""), target.get("subdomains", []),
                              target.get("include_subdomains", False),
                              limit=cap, excluded=target.get("excluded", []))

    def fanout_count(self, target):
        """How many hosts a target would expand to, uncapped (base plus subs)."""
        from core import subdomains as sd
        if not target:
            return 0
        return sd.fanout_count(target.get("host", ""), target.get("subdomains", []),
                               target.get("include_subdomains", False),
                               excluded=target.get("excluded", []))

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

    def _check_history_tree(self, path):
        expected=self.root.resolve()/path.relative_to(self.root)
        current=self.root
        for part in path.relative_to(self.root).parts:
            current=current/part
            is_junc = getattr(current, 'is_junction', None)
            if current.is_symlink() or (callable(is_junc) and is_junc()):
                raise ValueError('Un dossier de résultats est un lien ; suppression refusée.')
        if not path.exists():return
        if path.resolve()!=expected or not path.is_dir():
            raise ValueError('Le dossier des résultats est invalide.')
        for current,dirs,files in os.walk(path,followlinks=False):
            for name in dirs+files:
                child=Path(current)/name
                child_junc = getattr(child, 'is_junction', None)
                if child.is_symlink() or (callable(child_junc) and child_junc()) or not child.resolve().is_relative_to(expected):
                    raise ValueError('Un résultat contient un lien. Retirez ce lien avant de supprimer les résultats.')

    def clear_history(self):
        """Clear operation and flow histories, preserving custom flow definitions."""
        paths=[self.root/'runs',self.root/'flows/history']
        for path in paths:self._check_history_tree(path)
        if any(run.get('status')=='running' for run in self.history()):
            raise ValueError('Terminez ou arrêtez l’opération en cours avant de vider l’historique.')
        for path in paths:
            if path.exists():shutil.rmtree(path)

    def delete_run(self, identifier):
        if not isinstance(identifier,str) or Path(identifier).name!=identifier or identifier in ('.','..') or '/' in identifier or '\\' in identifier:
            raise ValueError('Identifiant de résultat invalide.')
        folder=self.root/'runs'/identifier
        self._check_history_tree(folder)
        self._check_history_tree(self.root/'flows/history')
        run=next((r for r in self.history() if r['id']==identifier),None)
        if run is None:raise ValueError('Ce résultat n’existe plus.')
        if run.get('status')=='running':raise ValueError('Une opération en cours ne peut pas être supprimée.')
        shutil.rmtree(folder)
        for path in (self.root/'flows/history').glob('*.json'):
            try:record=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):continue
            if not isinstance(record,dict) or not isinstance(record.get('steps'),list):continue
            changed=False
            for step in record.get('steps',[]):
                if not isinstance(step,dict):continue
                if step.get('run_id')==identifier:
                    step.pop('run_id');step['status']='deleted';changed=True
            if changed:
                record['status']='active';write_json(path,record)

    def new_run(self, tool, preset, target, command):
        def slug(value,limit):
            value=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower()
            return re.sub(r'[^a-z0-9]+','-',value).strip('-')[:limit].rstrip('-') or 'local'
        host=(target or {}).get('host') or 'local'
        identifier = (datetime.now().strftime("%Y%m%d-%H%M%S") + '__' + slug(host,30) + '__' +
                      slug(tool,20) + '__' + slug(preset,28) + '__' + uuid.uuid4().hex[:8])
        directory = self.root / "runs" / identifier
        directory.mkdir(parents=True)
        record = dict(id=identifier, tool=tool, preset=preset, target=target,
                      command=command, started=now(), status="running")
        write_json(directory / "run.json", record)
        return directory, record
