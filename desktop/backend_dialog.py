import sys
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QDialogButtonBox,QLabel,QFileDialog,QPushButton
from desktop.backends import get_config,save_config

class BackendDialog(QDialog):
    def __init__(self,root,parent=None):
        super().__init__(parent)
        self.root=root
        self.config=get_config(root)
        self.setWindowTitle('Environnement Linux')
        self.setMinimumWidth(620)
        layout=QVBoxLayout(self)
        explanation=QLabel('Linux local, WSL ou une machine Linux SSH : aucune machine personnelle n’est préconfigurée. SSH utilise votre clé et vérifie la clé d’hôte connue. Python 3 doit être disponible côté Linux.')
        explanation.setWordWrap(True); layout.addWidget(explanation)
        form=QFormLayout(); layout.addLayout(form)
        self.backend=QComboBox()
        if sys.platform.startswith('linux'): self.backend.addItem('Linux sur cet ordinateur','local')
        if sys.platform=='win32': self.backend.addItem('Distribution WSL','wsl')
        self.backend.addItem('Machine ou VM Linux en SSH','ssh')
        default=self.config.get('backend','local' if sys.platform.startswith('linux') else 'wsl' if sys.platform=='win32' else 'ssh')
        self.backend.setCurrentIndex(max(0,self.backend.findData(default)))
        form.addRow('Exécution',self.backend)
        self.fields={}
        for key,caption,default in [('distro','Distribution WSL','kali-linux'),('host','Hôte SSH',''),('user','Utilisateur SSH',''),('port','Port SSH','22'),('identity','Clé privée SSH (facultative)',''),('known_hosts','Fichier known_hosts (facultatif)','')]:
            edit=QLineEdit(str(self.config.get(key,default)))
            self.fields[key]=edit; form.addRow(caption,edit)
        note=QLabel('Les fichiers d’entrée SSH doivent déjà exister sur la machine Linux : indiquez leur chemin absolu dans le formulaire du profil. Les résultats fichiers restent dans ~/.local/share/ChaosticTool/runs sur cette machine ; le journal est conservé dans l’application.')
        note.setWordWrap(True); layout.addWidget(note)
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self.accept); actions.rejected.connect(self.reject); layout.addWidget(actions)
        def update():
            for key,edit in self.fields.items(): edit.setEnabled(self.backend.currentData()==('wsl' if key=='distro' else 'ssh'))
        self.backend.currentIndexChanged.connect(update); update()
    def save(self):
        config={**self.config,'backend':self.backend.currentData()}
        config.update({k:v.text().strip() for k,v in self.fields.items()})
        save_config(config,self.root)
