import platform,subprocess
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QLabel,QWidget,QHBoxLayout,QPushButton,QFileDialog,QScrollArea,QDialogButtonBox
from desktop.catalog import build_arguments,native_command
from desktop.backends import get_config,linux_status
from desktop.profiles import SECRETS,INPUT_FILES,OUTPUT_FILES,secrets_for,redact

class LaunchDialog(QDialog):
    def __init__(self,tool,store,parent=None):
        super().__init__(parent)
        self.tool,self.store=tool,store
        self.setWindowTitle('Configurer '+tool['name'])
        self.resize(680,640)
        layout=QVBoxLayout(self)
        title=QLabel(tool['name']); title.setObjectName('sectionTitle'); layout.addWidget(title)
        description=QLabel(tool['desc']); description.setWordWrap(True); layout.addWidget(description)
        form=QFormLayout(); form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows); layout.addLayout(form)
        self.backend=QComboBox()
        if tool['mode']=='builtin': self.backend.addItem('Moteur intégré','builtin')
        elif tool['mode']=='native': self.backend.addItem('Natif · '+platform.system(),'native')
        if tool.get('linux_presets'): self.backend.addItem('Environnement Linux configuré','linux')
        if tool['mode']=='linux': self.backend.setCurrentIndex(self.backend.findData('linux'))
        elif tool['mode']=='native' and tool['key'] in linux_status(store.root).get('tools',{}) and not native_command(tool,store.settings['executables'].get(tool['key']),store.root):
            self.backend.setCurrentIndex(self.backend.findData('linux'))
        form.addRow('Exécution',self.backend)
        self.profiles=QComboBox(); form.addRow('Profil',self.profiles)
        self.targets=QComboBox()
        for target in store.targets: self.targets.addItem(target['label']+' — '+target['host'],target['id'])
        if store.active_target: self.targets.setCurrentIndex(self.targets.findData(store.active_target['id']))
        form.addRow('Cible (selon le profil)',self.targets)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True)
        self.field_widget=QWidget(); self.extra_form=QFormLayout(self.field_widget); self.extra_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.scroll.setWidget(self.field_widget); layout.addWidget(self.scroll,1)
        self.extra_fields={}; self.wordlist=QLineEdit()
        self.preview=QLabel(); self.preview.setWordWrap(True); self.preview.setTextFormat(Qt.TextFormat.PlainText)
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); layout.addWidget(self.preview)
        self.context=QLabel(); self.context.setWordWrap(True); layout.addWidget(self.context)
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        actions.button(QDialogButtonBox.StandardButton.Ok).setText('Lancer')
        actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); layout.addWidget(actions)
        self.backend.currentIndexChanged.connect(self.backend_changed)
        self.profiles.currentIndexChanged.connect(self.profile_changed)
        self.targets.currentIndexChanged.connect(self.update_preview)
        self.backend_changed()

    def backend_changed(self):
        self.current_presets=self.tool.get('linux_presets',[]) if self.backend.currentData()=='linux' else self.tool['presets']
        self.profiles.blockSignals(True); self.profiles.clear()
        self.profiles.addItems([p['label'] for p in self.current_presets]); self.profiles.blockSignals(False)
        self.profile_changed()

    def preset(self): return self.current_presets[max(0,self.profiles.currentIndex())]
    def target(self): return getattr(self,'target_override',None) or next((t for t in self.store.targets if t['id']==self.targets.currentData()),None)
    def field_values(self): return {k:v.text() for k,v in self.extra_fields.items()}
    def effective_backend(self):
        return get_config(self.store.root).get('backend','local') if self.backend.currentData()=='linux' else 'native'
    def profile_changed(self):
        while self.extra_form.rowCount(): self.extra_form.removeRow(0)
        self.extra_fields={}
        preset=self.preset()
        self.targets.setEnabled(preset.get('needs_target',True) and not getattr(self,'target_override',None))
        fields=dict(preset.get('fields',{}))
        if preset.get('wordlist'): fields={'wordlist':('Liste de mots',''),**fields}
        self.wordlist=QLineEdit()
        for name,(caption,default) in fields.items():
            if name in OUTPUT_FILES and not default: default='capture.pcap' if name=='pcap' else 'resultat.bin'
            edit=QLineEdit(default)
            if name in SECRETS: edit.setEchoMode(QLineEdit.EchoMode.Password)
            if name in INPUT_FILES and self.effective_backend()!='ssh':
                row=QWidget(); buttons=QHBoxLayout(row); buttons.setContentsMargins(0,0,0,0); buttons.addWidget(edit)
                browse=QPushButton('Parcourir…'); buttons.addWidget(browse)
                def choose(checked=False,field=edit):
                    filename,_=QFileDialog.getOpenFileName(self,'Fichier d’entrée')
                    if filename: field.setText(filename)
                browse.clicked.connect(choose); self.extra_form.addRow(caption,row)
            else: self.extra_form.addRow(caption,edit)
            self.extra_fields[name]=edit
            if name=='wordlist': self.wordlist=edit
            edit.textChanged.connect(self.update_preview)
        context=[]
        if not preset.get('needs_target',True): context.append('Opération locale à l’environnement choisi ; aucune cible réseau enregistrée nécessaire.')
        if preset.get('interactive'): context.append('Session interactive dans l’onglet Exécution.')
        if preset.get('requires_root'):
            context.append('Ce profil nécessite Npcap et peut nécessiter des droits administrateur.' if self.effective_backend()=='native' and platform.system()=='Windows' else 'Ce profil nécessite les droits administrateur ; sudo peut demander son mot de passe sous Linux.')
        if self.effective_backend()=='ssh': context.append('Fichiers d’entrée et fichiers de résultats sur la machine SSH.')
        if self.tool['category']=='wireless': context.append('Interface Wi-Fi Linux et pilotes compatibles requis pour la capture et le mode moniteur.')
        self.context.setText('\n'.join(context)); self.update_preview()

    def update_preview(self):
        if not getattr(self,'current_presets',None): return
        preset=self.preset()
        try:
            args=build_arguments(self.tool,0,self.target(),self.wordlist.text(),self.field_values(),preset=preset,backend=self.effective_backend())
            text=subprocess.list2cmdline([self.tool.get('binary',preset.get('worker','diagnostic')),*args])
            self.preview.setText(redact(text,secrets_for(preset,self.field_values())))
        except (ValueError,KeyError,TypeError) as exc: self.preview.setText(str(exc))
