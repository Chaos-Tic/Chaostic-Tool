from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QLinearGradient, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from desktop import VERSION
from desktop.icons import icon as nav_icon
from desktop.catalog import availability, build_arguments, catalog, find_executable
from desktop.process import Runner
from desktop.packages import PORTABLE_PACK, PYTHON_PACK, MANIFEST, find_python, installed, installation_error

STATUS = {"running": "En cours", "success": "Terminé", "failed": "Échec", "cancelled": "Arrêté", "interrupted": "Interrompu"}


def label(text, kind="", wrap=False):
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(wrap)
    if kind:
        result.setObjectName(kind)
    return result


def button(text, callback=None, kind=""):
    result = QPushButton(text)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        result.clicked.connect(callback)
    if kind:
        result.setObjectName(kind)
    return result


def card():
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return frame, layout


def table(headers):
    result = QTableWidget(0, len(headers))
    result.setHorizontalHeaderLabels(headers)
    result.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    result.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    result.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    result.verticalHeader().hide()
    result.verticalHeader().setDefaultSectionSize(51)
    result.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    result.setShowGrid(False)
    result.setAlternatingRowColors(True)
    return result


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            if value in ("Inclus", "Détecté", "Prêt", "Terminé", "Active"):
                item.setForeground(QColor("#73deb0"))
            elif value in ("Échec", "Arrêté", "Interrompu"):
                item.setForeground(QColor("#ff9aa8"))
            widget.setItem(r, c, item)


class Hero(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(192)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(label("CHAOSTICTOOL  /  DESKTOP", "eyebrow"))
        title = label("Vos outils. Vos cibles.\nUn seul espace de travail.")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addWidget(label("Configurez une cible, lancez une opération, retrouvez ses résultats.", "muted"))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#202332"))
        gradient.setColorAt(0.65, QColor("#231b2a"))
        gradient.setColorAt(1, QColor("#331b29"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#493041"), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 13, 13)
        center_x, center_y = self.width() - 82, self.height() // 2
        painter.setPen(QPen(QColor("#653143"), 1))
        for radius in (38, 72, 106, 140):
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawLine(center_x - 170, center_y, self.width() - 8, center_y)
        painter.drawLine(center_x, 10, center_x, self.height() - 10)
        painter.setBrush(QColor("#ff4d64"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center_x - 5, center_y - 5, 10, 10)
        painter.drawEllipse(center_x - 62, center_y - 49, 6, 6)


class TargetDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Ajouter une cible")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(18)
        layout.addWidget(label("Nouvelle cible", "sectionTitle"))
        layout.addWidget(label("Un domaine, une adresse IP ou une URL complète.\nL’ajout n’effectue aucune connexion réseau.", "muted", True))
        form = QFormLayout()
        form.setSpacing(14)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex. Mon environnement de test")
        self.address = QLineEdit()
        self.address.setPlaceholderText("https://example.com ou 127.0.0.1")
        self.address.setObjectName("targetAddress")
        form.addRow("Nom (facultatif)", self.name)
        form.addRow("Adresse", self.address)
        layout.addLayout(form)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        actions.button(QDialogButtonBox.StandardButton.Ok).setText("Ajouter la cible")
        actions.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        actions.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)


class LaunchDialog(QDialog):
    def __init__(self, tool, store, parent):
        super().__init__(parent)
        self.tool, self.store = tool, store
        self.setWindowTitle(f"Lancer {tool['name']}")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(17)
        layout.addWidget(label(tool["name"], "sectionTitle"))
        layout.addWidget(label(tool["desc"], "muted", True))
        form = QFormLayout()
        form.setSpacing(16)
        self.targets = QComboBox()
        for target in store.targets:
            self.targets.addItem(f"{target['label']} — {target['host']}", target["id"])
        if store.active_target:
            self.targets.setCurrentIndex(self.targets.findData(store.active_target["id"]))
        self.profiles = QComboBox()
        self.profiles.addItems([p["label"] for p in tool["presets"]])
        form.addRow("Profil", self.profiles)
        if tool["key"] != "desktop-diagnostic":
            form.addRow("Cible", self.targets)
        self.wordlist = QLineEdit()
        self.wordlist.setPlaceholderText("Choisissez une liste de mots…")
        self.file_row = QWidget()
        files = QHBoxLayout(self.file_row)
        files.setContentsMargins(0, 0, 0, 0)
        files.addWidget(self.wordlist)
        files.addWidget(button("Parcourir", self.browse))
        if any(p.get("wordlist") for p in tool["presets"]):
            form.addRow("Liste de mots", self.file_row)
        layout.addLayout(form)
        self.extra_form = QFormLayout()
        self.extra_fields = {}
        layout.addLayout(self.extra_form)
        self.preview = label("", "muted", True)
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.preview)
        self.targets.currentIndexChanged.connect(self.update_preview)
        self.profiles.currentIndexChanged.connect(self.profile_changed)
        self.wordlist.textChanged.connect(self.update_preview)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        actions.button(QDialogButtonBox.StandardButton.Ok).setText("Lancer l’opération")
        actions.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        actions.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)
        self.profile_changed()

    def profile_changed(self):
        while self.extra_form.rowCount():
            self.extra_form.removeRow(0)
        self.extra_fields = {}
        preset = self.tool['presets'][self.profiles.currentIndex()]
        self.file_row.setVisible(bool(preset.get('wordlist')))
        for name, (caption, default) in preset.get('fields', {}).items():
            edit = QLineEdit(default)
            self.extra_form.addRow(caption, edit)
            self.extra_fields[name] = edit
            edit.textChanged.connect(self.update_preview)
        self.update_preview()

    def field_values(self):
        return {name: edit.text() for name, edit in self.extra_fields.items()}

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir une liste de mots", "", "Textes (*.txt);;Tous les fichiers (*)")
        if path:
            self.wordlist.setText(path)

    def target(self):
        return next((t for t in self.store.targets if t["id"] == self.targets.currentData()), None)

    def update_preview(self):
        if self.tool["mode"] == "builtin":
            text = "Diagnostic local, sans connexion réseau." if self.tool["key"] == "desktop-diagnostic" else "Connexion directe depuis cet ordinateur. Le VPN et Tor ne sont pas gérés par cette version."
        else:
            try:
                args = build_arguments(self.tool, self.profiles.currentIndex(), self.target(), self.wordlist.text(), self.field_values())
                import subprocess
                text = subprocess.list2cmdline([self.tool["binary"], *args])
            except (ValueError, TypeError):
                text = "Choisissez une cible et les fichiers nécessaires au profil."
        self.preview.setText(text)


class Window(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.tools = catalog()
        self.tool_by_key = {t["key"]: t for t in self.tools}
        self.runner = Runner(store, self)
        self.runner.output.connect(self.append_output)
        self.runner.completed.connect(self.run_completed)
        self.runner.activeChanged.connect(self.active_changed)
        self.setWindowTitle("ChaosticTool Desktop")
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "assets/icon.svg")))
        self.resize(1440, 920)
        self.setMinimumSize(1120, 740)
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(222)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 28, 18, 22)
        brand = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(self.windowIcon().pixmap(36, 36))
        brand.addWidget(icon)
        text = label("CHAOSTIC\nTOOL")
        text.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        brand.addWidget(text)
        brand.addStretch()
        side.addLayout(brand)
        side.addSpacing(24)
        side.addWidget(label("WORKSPACE", "eyebrow"))
        side.addSpacing(8)
        self.nav = []
        names = ["Vue d’ensemble", "Cibles", "Boîte à outils", "Exécution", "Historique", "Paramètres"]
        symbols = ["overview", "target", "tools", "run", "history", "settings"]
        for index, name in enumerate(names):
            item = button(f"  {name}", lambda checked=False, n=index: self.navigate(n), "nav")
            item.setIcon(nav_icon(symbols[index]))
            item.setIconSize(QSize(18, 18))
            item.setCheckable(True)
            self.nav.append(item)
            side.addWidget(item)
        side.addStretch()
        side.addWidget(label("WINDOWS DESKTOP", "eyebrow"))
        side.addWidget(label(f"Version {VERSION} · Aperçu", "muted"))
        side.addSpacing(8)
        side.addWidget(button("Ouvrir mes fichiers", self.open_data))
        outer.addWidget(sidebar)
        body = QWidget()
        main = QVBoxLayout(body)
        main.setContentsMargins(30, 26, 30, 20)
        main.setSpacing(23)
        heading = QHBoxLayout()
        title_area = QVBoxLayout()
        title_area.setSpacing(6)
        title_area.addWidget(label("CHAOSTICTOOL   /   ESPACE LOCAL", "eyebrow"))
        self.page_title = label("", "pageTitle")
        title_area.addWidget(self.page_title)
        heading.addLayout(title_area)
        heading.addStretch()
        heading.addWidget(label("●  Windows natif", "badge"))
        heading.addSpacing(14)
        heading.addWidget(button("+  Ajouter une cible", self.add_target, "primary"))
        main.addLayout(heading)
        self.stack = QStackedWidget()
        main.addWidget(self.stack, 1)
        outer.addWidget(body, 1)
        self.build_home()
        self.build_targets()
        self.build_tools()
        self.build_execution()
        self.build_history()
        self.build_settings()
        self.statusBar().showMessage("Prêt · Les résultats sont enregistrés sur cet ordinateur")
        self.refresh()
        self.navigate(0)
        if store.warning:
            self.statusBar().showMessage(store.warning)

    def page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        self.stack.addWidget(widget)
        return layout

    def build_home(self):
        layout = self.page()
        layout.addWidget(Hero())
        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.stats = []
        for caption, detail in (("CIBLES", "Vos environnements enregistrés"), ("OUTILS PRÊTS", "Inclus ou détectés sur ce PC"), ("OPÉRATIONS", "Un historique conservé localement")):
            frame, content = card()
            content.addWidget(label(caption, "eyebrow"))
            value = label("0", "number")
            self.stats.append(value)
            content.addWidget(value)
            content.addWidget(label(detail, "muted"))
            stats.addWidget(frame)
        layout.addLayout(stats)
        quick = QHBoxLayout()
        frame, content = card()
        content.addWidget(label("Commencer en quelques clics", "sectionTitle"))
        content.addWidget(label("Vérifiez l’application ou découvrez les outils disponibles.", "muted", True))
        buttons = QHBoxLayout()
        buttons.addWidget(button("Diagnostic local", lambda: self.launch("desktop-diagnostic"), "primary"))
        buttons.addWidget(button("Explorer les outils  →", lambda: self.navigate(2)))
        buttons.addStretch()
        content.addLayout(buttons)
        quick.addWidget(frame, 3)
        frame, content = card()
        content.addWidget(label("CIBLE ACTIVE", "eyebrow"))
        self.active_name = label("Aucune cible", "sectionTitle")
        self.active_host = label("Ajoutez votre premier environnement.", "muted", True)
        content.addWidget(self.active_name)
        content.addWidget(self.active_host)
        quick.addWidget(frame, 2)
        layout.addLayout(quick)
        top = QHBoxLayout()
        top.addWidget(label("Activité récente", "sectionTitle"))
        top.addStretch()
        top.addWidget(button("Tout voir  →", lambda: self.navigate(4)))
        layout.addLayout(top)
        self.recent = table(["OPÉRATION", "CIBLE", "ÉTAT", "DATE"])
        self.recent.cellDoubleClicked.connect(lambda *_: self.navigate(4))
        self.recent_empty = label("Aucune opération pour le moment. Lancez le diagnostic local pour essayer.", "muted", True)
        layout.addWidget(self.recent_empty)
        layout.addWidget(self.recent, 1)

    def build_targets(self):
        layout = self.page()
        layout.addWidget(label("Retrouvez vos environnements et choisissez la cible utilisée par défaut.", "muted"))
        self.target_table = table(["NOM", "ADRESSE", "PORT", "SÉLECTION"])
        self.target_table.cellDoubleClicked.connect(lambda *_: self.activate_target())
        layout.addWidget(self.target_table, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("Définir comme cible active", self.activate_target))
        actions.addWidget(button("Retirer la cible", self.remove_target))
        actions.addStretch()
        actions.addWidget(label("Les résultats restent dans l’historique.", "muted"))
        layout.addLayout(actions)

    def build_tools(self):
        layout = self.page()
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un outil, une fonction…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Rechercher un outil")
        self.search.textChanged.connect(self.filter_tools)
        toolbar.addWidget(self.search, 1)
        self.category = QComboBox()
        self.category.addItem("Toutes les catégories")
        self.category.addItems(sorted({t["group"] for t in self.tools}))
        self.category.currentIndexChanged.connect(self.filter_tools)
        toolbar.addWidget(self.category)
        self.only_ready = QCheckBox("Prêts uniquement")
        self.only_ready.toggled.connect(self.filter_tools)
        toolbar.addWidget(self.only_ready)
        layout.addLayout(toolbar)
        installs = QHBoxLayout()
        self.pack_button = button("Installer le pack Windows", lambda: self.install_tools(PORTABLE_PACK), "primary")
        self.python_pack_button = button("Installer les outils Python", lambda: self.install_tools(PYTHON_PACK))
        installs.addWidget(self.pack_button)
        installs.addWidget(self.python_pack_button)
        installs.addStretch()
        installs.addWidget(button("Actualiser", self.refresh))
        layout.addLayout(installs)
        split = QSplitter()
        self.tool_table = table(["OUTIL", "CATÉGORIE", "DISPONIBILITÉ"])
        self.tool_table.itemSelectionChanged.connect(self.show_tool)
        self.tool_table.cellDoubleClicked.connect(lambda *_: self.launch_selected())
        split.addWidget(self.tool_table)
        detail, content = card()
        detail.setMinimumWidth(290)
        self.tool_name = label("Choisissez un outil", "sectionTitle", True)
        self.tool_status = label("", "eyebrow")
        self.tool_desc = label("", "muted", True)
        self.tool_note = label("", "muted", True)
        self.tool_path = label("", "muted", True)
        self.tool_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self.tool_status)
        content.addWidget(self.tool_name)
        content.addWidget(self.tool_desc)
        content.addSpacing(10)
        content.addWidget(self.tool_note)
        content.addWidget(self.tool_path)
        content.addStretch()
        self.launch_button = button("Configurer et lancer", self.launch_selected, "primary")
        self.configure_button = button("Choisir l’exécutable…", self.configure_executable)
        self.download_button = button("Téléchargement officiel ↗", self.open_download)
        self.install_button = button("Installer cet outil", self.install_selected)
        content.addWidget(self.install_button)
        content.addWidget(self.launch_button)
        content.addWidget(self.configure_button)
        content.addWidget(self.download_button)
        split.addWidget(detail)
        split.setSizes([640, 330])
        layout.addWidget(split, 1)
        self.tool_count = label("", "muted")
        layout.addWidget(self.tool_count)

    def build_execution(self):
        layout = self.page()
        self.run_title = label("Prêt pour votre prochaine opération", "sectionTitle")
        self.run_info = label("Les sorties des outils apparaîtront ici en temps réel.", "muted", True)
        layout.addWidget(self.run_title)
        layout.addWidget(self.run_info)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setAccessibleName("Journal de l’opération")
        self.console.document().setMaximumBlockCount(5000)
        self.console.setPlaceholderText("Aucune opération lancée.\n\nChoisissez un outil dans la boîte à outils pour commencer.")
        layout.addWidget(self.console, 1)
        actions = QHBoxLayout()
        self.stop_button = button("■  Arrêter l’opération", self.runner.stop, "danger")
        # clicked(bool) must not replace Runner.stop's cancellation flag.
        self.stop_button.clicked.disconnect()
        self.stop_button.clicked.connect(lambda: self.runner.stop())
        self.stop_button.setEnabled(False)
        actions.addWidget(self.stop_button)
        self.run_folder = button("Ouvrir les résultats", self.open_run_folder)
        self.run_folder.setEnabled(False)
        actions.addWidget(self.run_folder)
        actions.addStretch()
        actions.addWidget(label("Journal complet enregistré automatiquement", "muted"))
        layout.addLayout(actions)

    def build_history(self):
        layout = self.page()
        layout.addWidget(label("Chaque opération conserve sa cible, son état et son journal complet.", "muted"))
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.history_table = table(["OUTIL", "CIBLE", "ÉTAT", "DATE"])
        self.history_table.itemSelectionChanged.connect(self.show_history)
        splitter.addWidget(self.history_table)
        self.history_log = QPlainTextEdit()
        self.history_log.setReadOnly(True)
        self.history_log.setPlaceholderText("Sélectionnez une opération pour lire son journal.")
        splitter.addWidget(self.history_log)
        splitter.setSizes([310, 240])
        layout.addWidget(splitter, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("Ouvrir le dossier", self.open_history_folder))
        actions.addWidget(button("Exporter le journal…", self.export_history))
        actions.addStretch()
        layout.addLayout(actions)

    def build_settings(self):
        layout = self.page()
        frame, content = card()
        content.addWidget(label("Vos données restent sur cet ordinateur", "sectionTitle"))
        content.addWidget(label("Cibles, paramètres et journaux sont enregistrés séparément du programme. Une mise à niveau conserve ces données.", "muted", True))
        path = label(str(self.store.root), "muted", True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(path)
        content.addWidget(button("Ouvrir le dossier de données", self.open_data))
        layout.addWidget(frame)
        frame, content = card()
        content.addWidget(label("Outils externes", "sectionTitle"))
        content.addWidget(label("Installez le pack Windows depuis la boîte à outils, ou choisissez chaque outil séparément. Les versions sont conservées dans votre dossier de données. Les archives portables sont vérifiées par SHA-256. Les outils Python utilisent chacun un environnement isolé ; leur installation nécessite Python 3.10 ou ultérieur.", "muted", True))
        self.python_path = label("Python : " + (find_python(self.store.settings.get("python")) or "non détecté"), "muted", True)
        content.addWidget(self.python_path)
        content.addWidget(button("Choisir Python…", self.configure_python))
        content.addWidget(button("Actualiser la détection des outils", self.refresh))
        layout.addWidget(frame)
        frame, content = card()
        content.addWidget(label("À propos de cette version", "sectionTitle"))
        content.addWidget(label(f"ChaosticTool Desktop {VERSION}\nInterface native PySide6 · Application en français\n\nLes fonctions CLI Linux restent dans le dépôt. Les consoles interactives, les workflows en chaîne, le Wi-Fi et le pilotage Tor/VPN ne sont pas encore intégrés à Desktop. Le routage des opérations est celui de Windows.", "muted", True))
        content.addWidget(button("Ouvrir le dépôt GitHub ↗", lambda: QDesktopServices.openUrl(QUrl("https://github.com/Chaos-Tic/Chaostic-Tool"))))
        layout.addWidget(frame)
        layout.addStretch()

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        self.page_title.setText(["Vue d’ensemble", "Vos cibles", "Boîte à outils", "Exécution", "Historique", "Paramètres"][index])
        for i, item in enumerate(self.nav):
            item.setChecked(i == index)

    def refresh(self):
        self.history_rows = self.store.history()
        for value, count in zip(self.stats, (len(self.store.targets), sum(availability(t, self.store.settings["executables"], self.store.root)[1] for t in self.tools), len(self.history_rows))):
            value.setText(str(count))
        target = self.store.active_target
        self.active_name.setText(target["label"] if target else "Aucune cible")
        self.active_host.setText(target["url"] if target else "Ajoutez votre premier environnement.")
        fill_table(self.target_table, [(t["label"], t["url"], t["port"], "Active" if target and t["id"] == target["id"] else "—") for t in self.store.targets])
        rows = [(r["tool"], (r.get("target") or {}).get("label", "Cet ordinateur"), STATUS.get(r["status"], r["status"]), r["started"].replace("T", " ")[:16] + " UTC") for r in self.history_rows]
        fill_table(self.recent, rows[:3])
        self.recent_empty.setVisible(not rows)
        fill_table(self.history_table, rows)
        self.filter_tools()

    def add_target(self):
        dialog = TargetDialog(self)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.store.add_target(dialog.address.text(), dialog.name.text())
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Cible non enregistrée", str(exc))
                continue
            self.refresh()
            self.statusBar().showMessage("Cible enregistrée et sélectionnée.")
            break

    def activate_target(self):
        row = self.target_table.currentRow()
        if 0 <= row < len(self.store.targets):
            self.store.settings["active_target"] = self.store.targets[row]["id"]
            self.store.save()
            self.refresh()

    def remove_target(self):
        row = self.target_table.currentRow()
        if 0 <= row < len(self.store.targets):
            target = self.store.targets[row]
            if QMessageBox.question(self, "Retirer la cible", f"Retirer « {target['label']} » ? Les résultats seront conservés.") == QMessageBox.StandardButton.Yes:
                self.store.remove_target(target["id"])
                self.refresh()

    def filter_tools(self):
        selected = self.selected_tool()
        selected_key = selected["key"] if selected else ""
        query = self.search.text().casefold()
        category = self.category.currentText()
        self.filtered_tools = [t for t in self.tools if (not query or query in (t["name"] + " " + t["desc"]).casefold())
                               and (self.category.currentIndex() == 0 or t["group"] == category)
                               and (not self.only_ready.isChecked() or availability(t, self.store.settings["executables"], self.store.root)[1])]
        self.tool_table.blockSignals(True)
        fill_table(self.tool_table, [(t["name"], t["group"], availability(t, self.store.settings["executables"], self.store.root)[0]) for t in self.filtered_tools])
        self.tool_table.blockSignals(False)
        self.tool_count.setText(f"{len(self.filtered_tools)} outil(s) affiché(s) · « À porter » : disponible uniquement dans la CLI Linux pour le moment")
        if self.filtered_tools:
            row = next((i for i, t in enumerate(self.filtered_tools) if t["key"] == selected_key), 0)
            self.tool_table.selectRow(row)
        self.show_tool()

    def selected_tool(self):
        row = self.tool_table.currentRow()
        tools = getattr(self, "filtered_tools", [])
        return tools[row] if 0 <= row < len(tools) else None

    def show_tool(self):
        tool = self.selected_tool()
        if not tool:
            self.tool_name.setText("Aucun outil correspondant")
            self.tool_status.clear()
            self.tool_desc.clear()
            self.tool_note.clear()
            self.tool_path.clear()
            for item in (self.launch_button, self.configure_button, self.download_button, self.install_button):
                item.setEnabled(False)
            return
        status, ready = availability(tool, self.store.settings["executables"], self.store.root)
        self.tool_name.setText(tool["name"])
        self.tool_status.setText(f"{tool['group'].upper()}  /  {status.upper()}")
        self.tool_desc.setText(tool["desc"])
        self.tool_note.setText(tool["note"])
        package = tool.get("package")
        record = installed(package, self.store.root) if package else None
        self.install_button.setVisible(bool(package))
        self.install_button.setEnabled(bool(package) and not self.runner.active)
        self.install_button.setText("Vérifier l’installation" if record else "Installer cet outil")
        if record:
            self.tool_note.setText(tool["note"] + "\nVersion installée : " + record["version"])
        elif package and (error := installation_error(package, self.store.root)):
            self.tool_note.setText(tool['note'] + '\nDernier échec : ' + error[-600:])

        self.tool_path.setText(find_executable(tool, self.store.settings["executables"].get(tool["key"]), self.store.root) or "")
        self.launch_button.setEnabled(ready and not self.runner.active)
        self.configure_button.setVisible(tool["mode"] == "native")
        self.download_button.setVisible(tool["mode"] == "native")
        self.configure_button.setEnabled(True)
        self.download_button.setEnabled(True)

    def configure_executable(self):
        tool = self.selected_tool()
        if not tool or tool["mode"] != "native":
            return
        path, _ = QFileDialog.getOpenFileName(self, f"Sélectionner {tool['name']}", "", "Exécutables Windows (*.exe)")
        if path:
            if not find_executable(tool, path):
                QMessageBox.warning(self, "Fichier invalide", "Choisissez un exécutable Windows existant.")
                return
            self.store.settings["executables"][tool["key"]] = path
            self.store.save()
            self.refresh()

    def open_download(self):
        tool = self.selected_tool()
        if tool and tool.get("url"):
            QDesktopServices.openUrl(QUrl(tool["url"]))

    def configure_python(self):
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner Python 3.10 ou ultérieur", "", "Python (python.exe)")
        if path:
            self.store.settings["python"] = path
            self.store.save()
            self.python_path.setText("Python : " + path)

    def install_selected(self):
        tool = self.selected_tool()
        if tool and tool.get("package"):
            self.install_tools([tool["package"]])

    def install_tools(self, packages):
        if self.runner.active:
            self.navigate(3)
            return
        python = find_python(self.store.settings.get("python"))
        if any(MANIFEST[p]["kind"] == "pip" for p in packages) and not python:
            QMessageBox.information(self, "Python requis", "Sélectionnez Python 3.10 ou ultérieur dans les paramètres, puis relancez l’installation.")
            self.navigate(5)
            return
        request = {"label": "Cet ordinateur", "packages": list(packages), "root": str(self.store.root), "python": python}
        self.console.clear()
        self.run_title.setText("Installation des outils")
        self.run_info.setText("Téléchargement, vérification et installation · En cours")
        try:
            self.runner.start("Dépendances Windows", ", ".join(packages), request, worker="install", timeout_ms=1_800_000)
            self.run_folder.setEnabled(True)
            self.navigate(3)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Installation impossible", str(exc))

    def launch_selected(self):
        if tool := self.selected_tool():
            self.launch(tool["key"])

    def launch(self, key, show_dialog=True):
        if self.runner.active:
            self.navigate(3)
            self.statusBar().showMessage("Une opération est déjà en cours. Arrêtez-la avant d’en lancer une autre.")
            return
        tool = self.tool_by_key[key]
        if not availability(tool, self.store.settings["executables"], self.store.root)[1]:
            return
        if key != "desktop-diagnostic" and not self.store.targets:
            self.add_target()
            if not self.store.targets:
                return
        dialog = LaunchDialog(tool, self.store, self)
        if show_dialog and dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target = dialog.target() if key != "desktop-diagnostic" else None
        index = dialog.profiles.currentIndex()
        preset = tool["presets"][index]
        try:
            kwargs = {"worker": preset["worker"], "timeout_ms": 30_000} if tool["mode"] == "builtin" else {
                "command": [find_executable(tool, self.store.settings["executables"].get(key), self.store.root), *build_arguments(tool, index, target, dialog.wordlist.text(), dialog.field_values())]}
            if not kwargs.get("worker") and not kwargs["command"][0]:
                raise ValueError("L’exécutable n’est plus disponible. Actualisez sa configuration.")
            self.console.clear()
            self.run_title.setText(f"{tool['name']} · {preset['label']}")
            self.run_info.setText(f"Cible : {(target or {}).get('url', 'cet ordinateur')}   ·   En cours")
            self.runner.start(tool["name"], preset["label"], target, **kwargs)
            self.run_folder.setEnabled(True)
            self.navigate(3)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Lancement impossible", str(exc))

    def append_output(self, text):
        # Strip ANSI terminal controls; cap even a single huge line in the GUI.
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text).replace("\x00", "")
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text[-262144:])
        if self.console.document().characterCount() > 1_000_000:
            self.console.setPlainText(self.console.toPlainText()[-500_000:])
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def active_changed(self, active):
        self.pack_button.setEnabled(not active)
        self.python_pack_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        self.progress.setRange(0, 0 if active else 1)
        self.progress.setValue(0 if active else 1)
        self.nav[3].setText("  Exécution · en cours" if active else "  Exécution")
        self.show_tool()

    def run_completed(self, result):
        state = STATUS[result["status"]]
        self.run_info.setText(f"{state} · Code de sortie : {result['exit_code']} · Résultats conservés")
        if result.get("detail"):
            self.append_output("\n" + result["detail"] + "\n")
        self.statusBar().showMessage(f"{result['tool']} : {state.lower()}.")
        self.refresh()

    def selected_history(self):
        row = self.history_table.currentRow()
        return self.history_rows[row] if 0 <= row < len(self.history_rows) else None

    def show_history(self):
        run = self.selected_history()
        if not run:
            self.history_log.clear()
            return
        path = Path(run["directory"]) / "output.txt"
        try:
            with path.open("rb") as stream:
                data = stream.read(512_001)
            text = data[:512_000].decode("utf-8", errors="replace")
            if len(data) > 512_000:
                text += "\n\n[Aperçu limité. Exportez le journal pour lire le fichier complet.]"
            if run.get("detail"):
                text += "\n" + run["detail"]
            self.history_log.setPlainText(text)
        except OSError as exc:
            self.history_log.setPlainText(f"Journal indisponible : {exc}")

    def open_data(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root)))

    def open_run_folder(self):
        if self.runner.directory:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.runner.directory)))

    def open_history_folder(self):
        if run := self.selected_history():
            QDesktopServices.openUrl(QUrl.fromLocalFile(run["directory"]))

    def export_history(self):
        run = self.selected_history()
        if not run:
            return
        destination, _ = QFileDialog.getSaveFileName(self, "Exporter le journal", f"chaostic-{run['id']}.txt", "Texte (*.txt)")
        if destination:
            import shutil
            try:
                source = Path(run["directory"]) / "output.txt"
                if source.resolve() != Path(destination).resolve():
                    shutil.copyfile(source, destination)
                self.statusBar().showMessage("Journal exporté.")
            except OSError as exc:
                QMessageBox.warning(self, "Export impossible", str(exc))

    def closeEvent(self, event):
        if self.runner.active:
            answer = QMessageBox.question(self, "Opération en cours", "Arrêter l’opération et fermer l’application ? Les résultats partiels seront conservés.",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.runner.shutdown()
        event.accept()
