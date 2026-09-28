from __future__ import annotations

import re
import os
import math
import platform
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QSize, QTimer
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QLinearGradient, QConicalGradient, QRadialGradient, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSplitter,
    QInputDialog, QScrollArea, QMenu, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.phases import PHASES
from desktop.flow_panel import FlowPanel
from desktop import VERSION
from desktop.icons import icon as nav_icon
from desktop import effects
from desktop import theme
from desktop.catalog import availability, build_arguments, catalog, find_executable, native_command
from desktop.process import Runner
from desktop.backends import get_config,save_config,linux_status,install_plan
from desktop.profiles import secrets_for,INPUT_FILES
from desktop.backend_dialog import BackendDialog
from desktop.packages import PORTABLE_PACK, PYTHON_PACK, MANIFEST, find_python, installed, installation_error, can_install

STATUS = {"running": "En cours", "success": "Terminé", "failed": "Échec", "cancelled": "Arrêté", "interrupted": "Interrompu"}


def label(text, kind="", wrap=False):
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(wrap)
    if kind:
        result.setObjectName(kind)
    return result


def button(text, callback=None, kind=""):
    result = effects.GamingButton(text)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        result.clicked.connect(callback)
    if kind:
        result.setObjectName(kind)
    if kind == "primary":
        effects.glow(result, "#9b75ff", blur=20, alpha=120)
    return result


def status_badge(text, color):
    """Small header pill with a drawn glowing dot (no Unicode bullet)."""
    holder = QWidget()
    holder.setObjectName("hbadge")
    box = QHBoxLayout(holder)
    box.setContentsMargins(13, 6, 14, 6)
    box.setSpacing(9)
    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
    effects.glow(dot, color, blur=10, alpha=210)
    caption = QLabel(text)
    caption.setStyleSheet(f"color: {color}; font-family: '{theme.DISPLAY}'; font-size: 10px; font-weight: 700; letter-spacing: 1px; background: transparent;")
    box.addWidget(dot)
    box.addWidget(caption)
    tint = QColor(color)
    holder.setStyleSheet(f"QWidget#hbadge {{ background: rgba({tint.red()},{tint.green()},{tint.blue()},0.10); border: 1px solid rgba({tint.red()},{tint.green()},{tint.blue()},0.40); border-radius: 12px; }}")
    return holder


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


def _pill_cell(text):
    holder = QWidget()
    box = QHBoxLayout(holder)
    box.setContentsMargins(10, 6, 10, 6)
    box.setSpacing(0)
    box.addWidget(effects.status_pill(str(text)),0,Qt.AlignmentFlag.AlignVCenter)
    box.addStretch()
    holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return holder


def fill_table(widget, rows, pill_cols=()):
    widget.setRowCount(len(rows))
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            if c in pill_cols:
                accessible_item=QTableWidgetItem('');accessible_item.setData(Qt.ItemDataRole.AccessibleTextRole,str(value));accessible_item.setToolTip(str(value))
                widget.setItem(r,c,accessible_item)
                if str(value) not in ("", "—"):
                    widget.setCellWidget(r, c, _pill_cell(value))
                else:
                    widget.setCellWidget(r, c, None)
                continue
            widget.setCellWidget(r, c, None)
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            widget.setItem(r, c, item)


from desktop.hud import Hero,GridBackground,ScanOverlay,clock


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


from desktop.launch_dialog import LaunchDialog


class Window(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.tools = catalog()
        self.tool_by_key = {t["key"]: t for t in self.tools}
        self.runner = Runner(store, self)
        clock().set_enabled(store.settings.get("animations",True))
        self.runner.output.connect(self.append_output)
        self.runner.completed.connect(self.run_completed)
        self.runner.activeChanged.connect(self.active_changed)
        self.setWindowTitle("ChaosticTool Desktop")
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "assets/icon.svg")))
        self.setMinimumSize(900, 600)
        screen=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440,screen.width()),min(920,screen.height()))
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 18, 12, 16)
        brand = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(self.windowIcon().pixmap(36, 36))
        brand.addWidget(icon)
        text = label("CHAOSTIC\nTOOL")
        brand_font = QFont(theme.DISPLAY, 12)
        brand_font.setWeight(QFont.Weight.Black)
        brand_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
        text.setFont(brand_font)
        text.setStyleSheet("color: #c2aaff;")
        brand.addWidget(text)
        brand.addStretch()
        side.addLayout(brand)
        side.addSpacing(24)
        side.addWidget(label("OPERATOR / LOCAL", "eyebrow"))
        side.addSpacing(8)
        names = ["Centre de contrôle", "Cibles", "Arsenal d’outils", "Exécution", "Historique", "Paramètres", "Attack flows"]
        symbols = ["overview", "target", "tools", "run", "history", "settings", "flow"]
        # self.nav stays ordered by stack index (nav[i] -> page i); only the on-screen
        # order is customised so Attack flows sits next to Exécution.
        self.nav = [None] * len(names)
        for index, name in enumerate(names):
            item = button(f"  {name}", lambda checked=False, n=index: self.navigate(n), "nav")
            item.setIcon(nav_icon(symbols[index]))
            item.setIconSize(QSize(18, 18))
            item.setCheckable(True)
            self.nav[index] = item
        for stack_index in (0, 1, 2, 3, 6, 4, 5):
            side.addWidget(self.nav[stack_index])
        side.addStretch()
        side.addWidget(label(platform.system().upper()+" DESKTOP", "eyebrow"))
        side.addWidget(label(f"NEXUS  /  {VERSION}", "muted"))
        side.addSpacing(8)
        side.addWidget(button("Ouvrir mes fichiers", self.open_data))
        outer.addWidget(sidebar)
        body = GridBackground()
        main = QVBoxLayout(body)
        main.setContentsMargins(20, 18, 20, 16)
        main.setSpacing(14)
        heading = QHBoxLayout()
        title_area = QVBoxLayout()
        title_area.setSpacing(6)
        title_area.addWidget(label("NEXUS  /  CENTRE DE CONTRÔLE", "eyebrow"))
        self.page_title = label("", "pageTitle")
        title_area.addWidget(self.page_title)
        heading.addLayout(title_area)
        heading.addStretch()
        heading.addWidget(status_badge(platform.system(), "#73deb0"))
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
        self.flow_panel=FlowPanel(self)
        self.stack.addWidget(self.flow_panel)
        from PySide6.QtGui import QShortcut,QKeySequence
        self.search_shortcut=QShortcut(QKeySequence('Ctrl+K'),self)
        self.search_shortcut.activated.connect(self.focus_search)
        self.execution_shortcut=QShortcut(QKeySequence('F6'),self)
        self.execution_shortcut.activated.connect(lambda:self.navigate(3))
        self.statusBar().showMessage("PRÊT  /  Ctrl+K : arsenal  /  F6 : exécution  /  Résultats enregistrés localement")
        self.refresh()
        self.navigate(0)
        if store.warning:
            self.statusBar().showMessage(store.warning)

    def focus_search(self):
        self.navigate(2);self.search.setFocus();self.search.selectAll()

    def page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(widget); self.stack.addWidget(scroll)
        return layout

    def build_home(self):
        layout = self.page()
        self.hero = Hero(on_tools=lambda:self.navigate(2),on_flows=lambda:self.navigate(6))
        hero=self.hero
        effects.glow(hero, "#9b75ff", blur=34, alpha=70)
        layout.addWidget(hero)
        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.stats = []
        for (caption, detail), tint in zip((("01 / CIBLES", "Environnements enregistrés"), ("02 / ARSENAL PRÊT", "Outils inclus ou détectés"), ("03 / OPÉRATIONS", "Journaux conservés localement")), (effects.LINUX, effects.READY, effects.RUNNING)):
            frame, content = card()
            content.addWidget(label(caption, "eyebrow"))
            value = label("0", "number")
            value.setStyleSheet(f"color: {tint};")
            effects.glow(value, tint, blur=24, alpha=140)
            self.stats.append(value)
            content.addWidget(value)
            content.addWidget(label(detail, "muted", True))
            stats.addWidget(frame)
        layout.addLayout(stats)
        target_bar=QFrame();target_bar.setObjectName('card')
        target_layout=QHBoxLayout(target_bar);target_layout.setContentsMargins(20,14,20,14)
        target_text=QVBoxLayout();target_text.setSpacing(5)
        target_text.addWidget(label("CIBLE ACTIVE / PROCHAINE OPÉRATION","eyebrow"))
        self.active_name=label("Aucune cible","sectionTitle",True)
        self.active_host=label("Ajoutez votre premier environnement.","muted",True)
        target_text.addWidget(self.active_name);target_text.addWidget(self.active_host)
        target_layout.addLayout(target_text,1)
        target_layout.addWidget(button("Diagnostic local",lambda:self.launch("desktop-diagnostic")))
        layout.addWidget(target_bar)
        top = QHBoxLayout()
        top.addWidget(label("JOURNAL DES OPÉRATIONS", "sectionTitle"))
        top.addStretch()
        top.addWidget(button("Tout voir  »", lambda: self.navigate(4)))
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
        self.category.addItem("Toutes les phases",None)
        for i,phase in enumerate(PHASES): self.category.addItem(f"{i+1:02d} · {phase['name']}",phase['id'])
        self.category.addItem("Utilitaires intégrés","builtin")
        self.category.setMaximumWidth(285)
        self.category.setMinimumWidth(240)
        self.category.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.category.currentIndexChanged.connect(self.filter_tools)
        toolbar.addWidget(self.category)
        self.only_ready = QCheckBox("Prêts uniquement")
        self.only_ready.toggled.connect(self.filter_tools)
        toolbar.addWidget(self.only_ready)
        layout.addLayout(toolbar)
        installs = QHBoxLayout()
        menu=QMenu(self)
        self.pack_button=menu.addAction("Installer le pack natif",lambda:self.install_tools([p for p in PORTABLE_PACK if can_install(p)]))
        self.python_pack_button=menu.addAction("Installer les outils Python",lambda:self.install_tools(PYTHON_PACK))
        self.linux_pack_button=menu.addAction("Installer le pack Linux",lambda:self.install_linux(list(self.tool_by_key)))
        install_menu=button("Installer des outils",kind="primary"); install_menu.setMenu(menu)
        installs.addWidget(install_menu)
        installs.addWidget(button("Attack flows  »",lambda:self.navigate(6)))
        installs.addStretch(); installs.addWidget(button("Actualiser",self.refresh))
        layout.addLayout(installs)
        split = QSplitter(); self.tools_split=split
        self.tool_table = table(["OUTIL", "CATÉGORIE", "DISPONIBILITÉ"])
        self.tool_table.itemSelectionChanged.connect(self.show_tool)
        self.tool_table.cellDoubleClicked.connect(lambda *_: self.launch_selected())
        split.addWidget(self.tool_table)
        detail, content = card()
        detail.setMinimumWidth(250)
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
        # Primary action first, on its own.
        self.launch_button = button("Configurer et lancer", self.launch_selected, "primary")
        content.addWidget(self.launch_button)
        # Secondary block: install / configure, visually separated.
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #26314a; margin-top: 8px; margin-bottom: 2px;")
        content.addWidget(divider)
        content.addWidget(label("INSTALLATION & CONFIGURATION", "eyebrow"))
        self.install_button = button("Installer cet outil", self.install_selected)
        self.linux_install_button = button("Installer côté Linux", self.install_selected_linux)
        self.linux_path_button = button("Chemin Linux personnalisé…", self.configure_linux_path)
        self.configure_button = button("Choisir l’exécutable…", self.configure_executable)
        self.download_button = button("Téléchargement officiel  »", self.open_download)
        for widget in (self.install_button, self.linux_install_button, self.linux_path_button, self.configure_button, self.download_button):
            content.addWidget(widget)
        detail_scroll=QScrollArea(); detail_scroll.setWidgetResizable(True); detail_scroll.setWidget(detail)
        detail_scroll.setMinimumWidth(265); split.addWidget(detail_scroll)
        split.setSizes([640, 330])
        layout.addWidget(split, 1)
        self.tool_count = label("", "muted")
        layout.addWidget(self.tool_count)

    def build_execution(self):
        layout = self.page()
        pick=QHBoxLayout(); self.execution_tool=QComboBox()
        for tool in self.tools: self.execution_tool.addItem(tool['name'],tool['key'])
        self.execution_tool.setAccessibleName("Outil à exécuter")
        self.execution_tool.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.execute_button=button("Configurer et exécuter",lambda:self.launch(self.execution_tool.currentData()),"primary")
        pick.addWidget(self.execution_tool,1); pick.addWidget(self.execute_button); layout.addLayout(pick)
        self.flow_return=button("Retour au flow  »",lambda:self.navigate(6)); self.flow_return.hide(); layout.addWidget(self.flow_return)
        self.run_title = label("Prêt pour votre prochaine opération", "sectionTitle", True)
        self.run_info = label("Les sorties des outils apparaîtront ici en temps réel.", "muted", True)
        layout.addWidget(self.run_title)
        layout.addWidget(self.run_info)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.progress.hide()
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setAccessibleName("Journal de l’opération")
        self.console.document().setMaximumBlockCount(5000)
        self.console.setPlaceholderText("Aucune opération lancée.\n\nChoisissez un outil dans la boîte à outils pour commencer.")
        console_wrap = QWidget()
        console_grid = QGridLayout(console_wrap)
        console_grid.setContentsMargins(0, 0, 0, 0)
        console_grid.addWidget(self.console, 0, 0)
        self.scan = ScanOverlay(console_wrap)
        console_grid.addWidget(self.scan, 0, 0)
        layout.addWidget(console_wrap, 1)
        self.input_row=QWidget(); entry=QHBoxLayout(self.input_row); entry.setContentsMargins(0,0,0,0)
        self.terminal_input=QLineEdit(); self.terminal_input.setPlaceholderText("Saisie pour la session interactive…")
        self.secret_input=QCheckBox("Masquer"); self.secret_input.setChecked(True)
        self.terminal_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_input.toggled.connect(lambda yes:self.terminal_input.setEchoMode(QLineEdit.EchoMode.Password if yes else QLineEdit.EchoMode.Normal))
        entry.addWidget(self.terminal_input,1); entry.addWidget(self.secret_input)
        entry.addWidget(button("Envoyer",self.send_terminal_input)); entry.addWidget(button("Ctrl+C",self.runner.interrupt))
        self.terminal_input.returnPressed.connect(self.send_terminal_input)
        layout.addWidget(self.input_row); self.input_row.hide()
        self.terminal_screen=None

        actions = QHBoxLayout()
        self.stop_button = button("Arrêter l’opération", self.runner.stop, "danger")
        # clicked(bool) must not replace Runner.stop's cancellation flag.
        self.stop_button.clicked.disconnect()
        self.stop_button.clicked.connect(self.stop_current)
        self.stop_button.setEnabled(False)
        self.stop_button.hide()
        effects.pulse(self.stop_button, "#9b75ff", low=8, high=28, ms=900)
        actions.addWidget(self.stop_button)
        self.run_folder = button("Ouvrir les résultats", self.open_run_folder)
        self.run_folder.setEnabled(False)
        actions.addWidget(self.run_folder)
        actions.addStretch()
        actions.addWidget(label("Journal enregistré automatiquement", "muted", True))
        layout.addLayout(actions)

    def build_history(self):
        layout = self.page()
        layout.addWidget(label("Chaque opération conserve sa cible, son état et son journal complet.", "muted"))
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.history_search=QLineEdit(); self.history_search.setPlaceholderText("Rechercher un outil, un profil, une cible ou un flow…")
        self.history_search.textChanged.connect(self.filter_history); layout.addWidget(self.history_search)
        self.history_table = table(["OUTIL / FLOW", "PROFIL", "CIBLE", "ÉTAT", "DATE"])
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
        outer=self.page()
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        panel=QWidget(); layout=QVBoxLayout(panel)
        scroll.setWidget(panel); outer.addWidget(scroll)
        appearance,appearance_box=card()
        appearance_box.addWidget(label("NEXUS / Apparence", "sectionTitle"))
        self.motion_toggle=QCheckBox("Animations immersives")
        self.motion_toggle.setChecked(self.store.settings.get('animations',True))
        self.motion_toggle.toggled.connect(self.set_motion)
        appearance_box.addWidget(self.motion_toggle)
        appearance_box.addWidget(label("Orbite, particules, transitions et survols. Désactivez les effets pour une interface statique ; les opérations continuent normalement.","muted",True))
        layout.addWidget(appearance)
        frame,content=card()
        content.addWidget(label("Environnement Linux", "sectionTitle"))
        self.backend_status=label("Non vérifié", "muted", True)
        content.addWidget(self.backend_status)
        content.addWidget(button("Configurer Linux / WSL / SSH…",self.configure_backend))
        content.addWidget(button("Vérifier la connexion et les outils",self.check_backend))
        if os.name=='nt': content.addWidget(button("Installer WSL et Kali Linux…",self.setup_wsl))
        content.addWidget(label("Linux local utilise ce PC. WSL utilise la distribution sélectionnée. SSH utilise votre propre machine ou VM ; aucun serveur n’est imposé. Les pilotes Wi-Fi et interfaces doivent exister dans cet environnement.","muted",True))
        layout.addWidget(frame)
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
        content.addWidget(label("Installez le pack natif depuis la boîte à outils, ou choisissez chaque outil séparément. Les versions sont conservées dans votre dossier de données. Les archives portables sont vérifiées par SHA-256. Les outils Python utilisent chacun un environnement isolé. Si nécessaire, un Python compatible est téléchargé et vérifié automatiquement.", "muted", True))
        self.python_path = label("Python : " + (find_python(self.store.settings.get("python")) or "non détecté"), "muted", True)
        content.addWidget(self.python_path)
        content.addWidget(button("Choisir Python…", self.configure_python))
        content.addWidget(button("Actualiser la détection des outils", self.refresh))
        layout.addWidget(frame)
        frame, content = card()
        content.addWidget(label("À propos de cette version", "sectionTitle"))
        content.addWidget(label(f"ChaosticTool Desktop {VERSION}\nInterface native PySide6 · Application en français\n\nLes profils du catalogue sont intégrés avec exécution native ou Linux. Les sessions interactives disposent d’une saisie dans Exécution. Les prérequis pilotes, matériels et services restent propres à chaque outil. Les attack flows proposent des étapes guidées et configurables. Le pilotage Tor/VPN reste séparé. Le routage est celui de l’environnement choisi.", "muted", True))
        content.addWidget(button("Ouvrir le dépôt GitHub  »", lambda: QDesktopServices.openUrl(QUrl("https://github.com/Chaos-Tic/Chaostic-Tool"))))
        layout.addWidget(frame)
        layout.addStretch()

    def set_motion(self,enabled):
        self.store.settings['animations']=bool(enabled);self.store.save();clock().set_enabled(enabled)

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        effects.fade_in(self.stack.currentWidget())
        if index==6: self.flow_panel.refresh()
        self.page_title.setText(["Centre de contrôle", "Vos cibles", "Arsenal d’outils", "Exécution", "Historique", "Paramètres", "Attack flows"][index])
        for i, item in enumerate(self.nav):
            item.setChecked(i == index)
        self.nav[index].setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh(self):
        if hasattr(self,'backend_status'):
            status=linux_status(self.store.root)
            self.backend_status.setText(status.get('error') or (str(len(status.get('tools',{})))+' outils détectés · '+status.get('checked','Connexion non vérifiée')))
        self.history_rows = self.store.history()
        for value, count in zip(self.stats, (len(self.store.targets), sum(availability(t, self.store.settings["executables"], self.store.root)[1] for t in self.tools), len(self.history_rows))):
            effects.count_up(value, count)
        target = self.store.active_target
        self.active_name.setText(target["label"] if target else "Aucune cible")
        self.active_host.setText(target["url"] if target else "Ajoutez votre premier environnement.")
        fill_table(self.target_table, [(t["label"], t["url"], t["port"], "Active" if target and t["id"] == target["id"] else "—") for t in self.store.targets], pill_cols=(3,))
        rows = [(r["tool"], (r.get("target") or {}).get("label", "Cet ordinateur"), STATUS.get(r["status"], r["status"]), r["started"].replace("T", " ")[:16] + " UTC") for r in self.history_rows]
        fill_table(self.recent, rows[:3], pill_cols=(2,))
        self.recent_empty.setVisible(not rows)
        self.filter_history()
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
        category = self.category.currentData()
        members=next((p["tools"] for p in PHASES if p["id"]==category),[])
        self.filtered_tools = [t for t in self.tools if (not query or query in (t["name"] + " " + t["desc"]).casefold())
                               and (category is None or t["key"] in members or (category=="builtin" and t["key"].startswith("desktop-")))
                               and (not self.only_ready.isChecked() or availability(t, self.store.settings["executables"], self.store.root)[1])]
        self.tool_table.blockSignals(True)
        fill_table(self.tool_table, [(t["name"], t["group"], availability(t, self.store.settings["executables"], self.store.root)[0]) for t in self.filtered_tools], pill_cols=(2,))
        self.tool_table.blockSignals(False)
        self.tool_count.setText(f"{len(self.filtered_tools)} outil(s) affiché(s) · états issus des exécutables natifs et de l’inventaire Linux")
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
            for item in (self.launch_button, self.configure_button, self.download_button, self.install_button, self.linux_install_button, self.linux_path_button):
                item.setEnabled(False)
            return
        status, ready = availability(tool, self.store.settings["executables"], self.store.root)
        self.tool_name.setText(tool["name"])
        self.tool_status.setText(f"{tool['group'].upper()}  /  {status.upper()}")
        self.tool_desc.setText(tool["desc"])
        self.tool_note.setText(tool["note"])
        package = tool.get("package")
        record = installed(package, self.store.root) if package else None
        self.install_button.setVisible(bool(package) and can_install(package))
        self.install_button.setEnabled(bool(package) and not self.runner.active)
        self.install_button.setText("Vérifier l’installation" if record else "Installer cet outil")
        if record:
            self.tool_note.setText(tool["note"] + "\nVersion installée : " + record["version"])
        elif package and (error := installation_error(package, self.store.root)):
            self.tool_note.setText(tool['note'] + '\nDernier échec : ' + error[-600:])

        self.tool_path.setText(find_executable(tool, self.store.settings["executables"].get(tool["key"]), self.store.root) or "")
        self.launch_button.setEnabled(bool(tool['presets']) and not self.runner.active)
        self.linux_install_button.setVisible(bool(tool.get('linux_presets')))
        self.linux_install_button.setEnabled(not self.runner.active)
        self.linux_path_button.setVisible(bool(tool.get('linux_presets')))
        self.configure_button.setVisible(tool["mode"] == "native")
        self.download_button.setVisible(tool["mode"] == "native")
        self.configure_button.setEnabled(True)
        self.download_button.setEnabled(True)

    def configure_executable(self):
        tool = self.selected_tool()
        if not tool or tool["mode"] != "native":
            return
        path, _ = QFileDialog.getOpenFileName(self, f"Sélectionner {tool['name']}", "", "Programmes et scripts (*)")
        if path:
            if not find_executable(tool, path):
                QMessageBox.warning(self, "Fichier invalide", "Choisissez un programme ou script Python existant pour cet ordinateur.")
                return
            self.store.settings["executables"][tool["key"]] = path
            self.store.save()
            self.refresh()

    def open_download(self):
        tool = self.selected_tool()
        if tool and tool.get("url"):
            QDesktopServices.openUrl(QUrl(tool["url"]))

    def configure_python(self):
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner Python 3.14 ou ultérieur", "", "Programmes Python (*)")
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
        request = {"label": "Cet ordinateur", "packages": list(packages), "root": str(self.store.root), "python": python}
        self.pending_installers=[p for p in packages if MANIFEST[p]['kind']=='installer']
        self.console.clear()
        self.terminal_screen=None
        self.input_row.hide()
        self.run_title.setText("Installation des outils")
        self.run_info.setText("Téléchargement, vérification et installation · En cours")
        try:
            self.runner.start("Dépendances natives", ", ".join(packages), request, worker="install", timeout_ms=1_800_000)
            self.run_folder.setEnabled(True)
            self.navigate(3)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Installation impossible", str(exc))

    def launch_selected(self):
        if tool := self.selected_tool():
            self.launch(tool["key"])

    def launch(self,key,show_dialog=True,tool_override=None,metadata=None,target_override=None):
        if self.runner.active:
            self.navigate(3); return False
        tool=tool_override or self.tool_by_key[key]
        dialog=LaunchDialog(tool,self.store,self)
        if target_override:
            dialog.target_override=target_override
            dialog.targets.setCurrentIndex(dialog.targets.findData(target_override['id']))
            dialog.targets.setEnabled(False)
            dialog.update_preview()
        while True:
            if show_dialog and dialog.exec()!=QDialog.DialogCode.Accepted: return False
            preset=dialog.preset(); backend=dialog.backend.currentData()
            target=(target_override or dialog.target()) if preset.get('needs_target',True) else None
            fields=dialog.field_values()
            try:
                args=build_arguments(tool,0,target,dialog.wordlist.text(),fields,preset=preset,backend=dialog.effective_backend())
                secret_values=secrets_for(preset,fields)
                if backend=='builtin':
                    request={**(target or {}),'fields':fields,'rrtype':preset.get('rrtype','A')}
                    kwargs={'worker':preset['worker'],'timeout_ms':30_000}
                else:
                    request=target
                    if backend=='linux':
                        executable=linux_status(self.store.root).get('tools',{}).get(key)
                        if not executable: raise ValueError('Outil Linux non détecté. Configurez Linux et actualisez son inventaire dans les paramètres.')
                        kwargs={'command':[executable,*args],'bridge':True,'fields':{**fields,'wordlist':dialog.wordlist.text()},'elevate':preset.get('requires_root',False)}
                    else:
                        command=native_command(tool,self.store.settings['executables'].get(key),self.store.root)
                        if not command: raise ValueError('Outil natif non installé pour ce système. Utilisez Installer cet outil, sélectionnez son programme ou choisissez Linux.')
                        kwargs={'command':[*command,*args]}
                        if key=='rustscan' and preset.get('cli_index') is not None:
                            nmap=native_command(self.tool_by_key['nmap'],self.store.settings['executables'].get('nmap'),self.store.root)
                            if not nmap: raise ValueError('Ce profil RustScan appelle Nmap. Installez Nmap depuis la boîte à outils, ou choisissez le profil « Port de la cible, sans Nmap ».')
                            kwargs['environment_extra']={'PATH':str(Path(nmap[0]).parent)+os.pathsep+os.environ.get('PATH','')}
                    kwargs['redactions']=secret_values
                self.console.clear(); self.terminal_screen=None
                interactive=preset.get('interactive',False) or kwargs.get('elevate',False)
                if interactive:
                    import pyte
                    self.terminal_screen=pyte.Screen(120,30); self.terminal_stream=pyte.Stream(self.terminal_screen)
                self.input_row.setVisible(interactive)
                self.run_title.setText(tool['name']+' · '+preset['label'])
                self.run_info.setText(('Cible : '+target['url'] if target else 'Environnement local sélectionné')+' · En cours')
                self.flow_return.setVisible(bool(metadata))
                self.execution_tool.setCurrentIndex(self.execution_tool.findData(key))
                self.runner.start(tool['name'],preset['label'],request,metadata=metadata,**kwargs)
                self.run_folder.setEnabled(True); self.navigate(3)
                return True
            except (ValueError,RuntimeError,OSError) as exc:
                if not show_dialog: raise
                QMessageBox.warning(self,'Lancement impossible',str(exc))

    def configure_backend(self):
        dialog=BackendDialog(self.store.root,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            dialog.save(); self.check_backend()

    def check_backend(self):
        if self.runner.active: self.navigate(3); return
        self.console.clear(); self.terminal_screen=None; self.input_row.hide()
        self.run_title.setText('Vérification de l’environnement Linux')
        self.runner.start('Linux','Inventaire',{'root':str(self.store.root),'label':'Environnement Linux'},worker='linux-check',timeout_ms=60_000)
        self.navigate(3)

    def setup_wsl(self):
        if self.runner.active: self.navigate(3); return
        self.console.clear(); self.terminal_screen=None; self.input_row.hide()
        self.run_title.setText('Installation WSL / Kali Linux')
        self.runner.start('Linux','Installation WSL',{'label':'Cet ordinateur'},worker='wsl-setup',timeout_ms=1_800_000)
        self.navigate(3)

    def configure_linux_path(self):
        tool=self.selected_tool()
        if not tool: return
        value,ok=QInputDialog.getText(self,'Programme Linux','Chemin absolu du programme dans Linux :')
        if ok and value:
            if not value.startswith('/') or any(ord(c)<32 for c in value):
                QMessageBox.warning(self,'Chemin invalide','Indiquez un chemin Linux absolu.'); return
            config=get_config(self.store.root)
            config.setdefault('paths',{})[tool['key']]=value
            save_config(config,self.store.root); self.check_backend()

    def install_selected_linux(self):
        tool=self.selected_tool()
        if tool: self.install_linux([tool['key']])

    def install_linux(self,keys):
        if self.runner.active: self.navigate(3); return
        try:
            self.console.clear(); self.terminal_screen=None; self.input_row.show()
            self.run_title.setText('Installation des paquets Linux')
            self.runner.start('Dépendances Linux','Paquets Kali/Debian',{'label':'Environnement Linux'},command=install_plan(keys),bridge=True,elevate=True,timeout_ms=3_600_000)
            self.navigate(3)
        except (ValueError,RuntimeError,OSError) as exc: QMessageBox.warning(self,'Installation Linux',str(exc))

    def send_terminal_input(self):
        value=self.terminal_input.text()
        self.runner.send_input(value+'\n',secret=self.secret_input.isChecked())
        self.terminal_input.clear()

    def append_output(self, text):
        if self.terminal_screen is not None:
            self.terminal_stream.feed(text)
            self.console.setPlainText('\n'.join(self.terminal_screen.display))
            return
        # Strip ANSI terminal controls; cap even a single huge line in the GUI.
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text).replace("\x00", "")
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text[-262144:])
        if self.console.document().characterCount() > 1_000_000:
            self.console.setPlainText(self.console.toPlainText()[-500_000:])
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def active_changed(self, active):
        self.scan.set_active(active)
        self.linux_pack_button.setEnabled(not active)
        self.terminal_input.setEnabled(active)
        self.pack_button.setEnabled(not active)
        self.python_pack_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        self.stop_button.setVisible(active)
        self.stop_button.setText("Arrêter")
        self.execute_button.setEnabled(not active)
        self.execution_tool.setEnabled(not active)
        self.progress.setVisible(active)
        self.progress.setRange(0, 0 if active else 1)
        self.progress.setValue(0 if active else 1)
        self.nav[3].setText("  Exécution · en cours" if active else "  Exécution")
        self.show_tool()

    def stop_current(self):
        if not self.runner.active: return
        self.stop_button.setEnabled(False)
        self.stop_button.setText("Arrêt en cours…")
        self.runner.stop()

    def filter_history(self):
        query=self.history_search.text().casefold()
        self.visible_history=[r for r in self.history_rows if not query or query in
            (r['tool']+' '+r.get('preset','')+' '+r.get('flow_name','')+' '+str(r.get('target') or {})).casefold()]
        fill_table(self.history_table,[(r['tool']+(' / '+r['flow_name'] if r.get('flow_name') else ''),r.get('preset',''),
            (r.get('target') or {}).get('label','Cet ordinateur'),STATUS.get(r['status'],r['status']),r['started'].replace('T',' ')[:16]+' UTC') for r in self.visible_history],pill_cols=(3,))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'tools_split'):
            orientation=Qt.Orientation.Vertical if self.width()<1100 else Qt.Orientation.Horizontal
            if self.tools_split.orientation()!=orientation:
                self.tools_split.setOrientation(orientation)
                self.tools_split.setSizes([300,260] if self.width()<1100 else [640,330])

    def run_completed(self, result):
        state = STATUS[result["status"]]
        self.run_info.setText(f"{state} · Code de sortie : {result['exit_code']} · Résultats conservés")
        if result.get("detail"):
            self.append_output("\n" + result["detail"] + "\n")
        self.statusBar().showMessage(f"{result['tool']} : {state.lower()}.")
        self.refresh()
        if result['tool']=='Dépendances natives':
            pending=getattr(self,'pending_installers',[]); self.pending_installers=[]
            if result['status']=='success' and os.name=='nt':
                for package in pending:
                    spec=MANIFEST[package]
                    path=self.store.root/'tools/installers'/f"{package}-{spec['version']}-setup.exe"
                    try:
                        import hashlib
                        if hashlib.sha256(path.read_bytes()).hexdigest()!=spec['sha256']: raise ValueError('Empreinte de l’installateur invalide.')
                        os.startfile(str(path))
                        self.run_info.setText('Assistant officiel ouvert. Terminez l’installation puis cliquez sur Actualiser dans la boîte à outils.')
                    except (OSError,ValueError) as exc: QMessageBox.warning(self,'Installateur',str(exc))
        if result['tool']=='Dépendances Linux':
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0,self.check_backend)

    def selected_history(self):
        row = self.history_table.currentRow()
        return self.visible_history[row] if 0 <= row < len(self.visible_history) else None

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
