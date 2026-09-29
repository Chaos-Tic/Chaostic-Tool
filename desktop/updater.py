"""Vérification de mise à jour : compare la version locale aux releases Desktop.

Interroge l'API GitHub (releases publiques), ne retient que les tags Desktop
stables (`desktop-vX.Y.Z`, ni brouillon ni préversion), et signale s'il en existe
une plus récente. Ne télécharge ni n'installe rien : propose d'ouvrir la page.
Réseau exécuté dans un thread pour ne pas bloquer l'interface.
"""
from __future__ import annotations

import json
import re
import urllib.request

from PySide6.QtCore import QObject, Signal, QThread

from desktop import VERSION

RELEASES_API = "https://api.github.com/repos/Chaos-Tic/Chaostic-Tool/releases"
RELEASES_PAGE = "https://github.com/Chaos-Tic/Chaostic-Tool/releases"
_TAG = re.compile(r"^desktop-v(\d+)\.(\d+)\.(\d+)$")


def _version_tuple(text: str):
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


class _Worker(QObject):
    done = Signal(bool, str, str)  # (mise_a_jour_disponible, version, url)

    def run(self):
        try:
            request = urllib.request.Request(
                RELEASES_API,
                headers={"User-Agent": "ChaosticTool-Desktop",
                         "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(request, timeout=8) as response:
                releases = json.load(response)
            best = (0, 0, 0)
            best_url = RELEASES_PAGE
            for release in releases:
                if release.get("draft") or release.get("prerelease"):
                    continue
                if not _TAG.match(release.get("tag_name", "")):
                    continue
                version = _version_tuple(release["tag_name"])
                if version > best:
                    best = version
                    best_url = release.get("html_url", RELEASES_PAGE)
            current = _version_tuple(VERSION)
            newer = best > current
            label = ".".join(str(n) for n in best) if best != (0, 0, 0) else ""
            self.done.emit(newer, label, best_url)
        except Exception:
            self.done.emit(False, "", "")


class UpdateChecker(QObject):
    """Lance une vérification en arrière-plan et émet un résultat unique."""
    result = Signal(bool, str, str, bool)  # (dispo, version, url, manuel)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None

    def check(self, manual: bool = False):
        if self._thread is not None:
            return
        self._manual = manual
        self._thread = QThread(self)
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._thread.start()

    def _on_done(self, available, version, url):
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is not None:
            thread.quit()
            thread.wait(3000)
        self.result.emit(available, version, url, getattr(self, "_manual", False))
