from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QListWidget,QListWidgetItem,QDialog,QDialogButtonBox,QLineEdit,QFileDialog,QMessageBox
from core.tools import TOOLS
from desktop.catalog import availability
from desktop.flows import load_flows,save_custom,import_flows,validate_flow,step_tool,FlowSession
from desktop import effects

class FlowEditor(QDialog):
    def __init__(self,parent,flow=None):
        super().__init__(parent); self.setWindowTitle('Éditeur de flow'); self.resize(720,620)
        self.steps=[list(s) for s in (flow or {}).get('steps',[])]
        layout=QVBoxLayout(self)
        self.name=QLineEdit((flow or {}).get('name','')); self.name.setPlaceholderText('Nom du flow')
        self.desc=QLineEdit((flow or {}).get('desc','')); self.desc.setPlaceholderText('Description')
        layout.addWidget(self.name); layout.addWidget(self.desc)
        pick=QHBoxLayout(); self.tools=QComboBox(); self.profiles=QComboBox()
        for key,t in TOOLS.items(): self.tools.addItem(t['name'],key)
        def profiles():
            self.profiles.clear(); self.profiles.addItems([p['label'] for p in TOOLS[self.tools.currentData()]['presets']])
        self.tools.currentIndexChanged.connect(profiles); profiles()
        pick.addWidget(self.tools); pick.addWidget(self.profiles,1)
        add=QPushButton('Ajouter'); add.clicked.connect(self.add); pick.addWidget(add); layout.addLayout(pick)
        self.list=QListWidget(); layout.addWidget(self.list,1)
        actions=QHBoxLayout()
        for label,fn in [('Monter',lambda:self.move(-1)),('Descendre',lambda:self.move(1)),('Retirer',self.remove)]:
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        layout.addLayout(actions)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons); self.refresh()
    def refresh(self):
        self.list.clear()
        for k,i in self.steps: self.list.addItem(TOOLS[k]['name']+' — '+TOOLS[k]['presets'][i]['label'])
    def add(self): self.steps.append([self.tools.currentData(),self.profiles.currentIndex()]); self.refresh()
    def move(self,offset):
        i=self.list.currentRow(); j=i+offset
        if 0<=i<len(self.steps) and 0<=j<len(self.steps): self.steps[i],self.steps[j]=self.steps[j],self.steps[i]; self.refresh(); self.list.setCurrentRow(j)
    def remove(self):
        i=self.list.currentRow()
        if i>=0: self.steps.pop(i); self.refresh()
    def value(self): return validate_flow(dict(name=self.name.text(),desc=self.desc.text(),steps=self.steps))
    def accept(self):
        try: self.value()
        except ValueError as exc: QMessageBox.warning(self,'Flow invalide',str(exc)); return
        super().accept()

class FlowPanel(QWidget):
    def __init__(self,window):
        super().__init__(); self.window=window; self.session=None
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        head=QHBoxLayout(); self.select=QComboBox(); head.addWidget(self.select,1)
        self.edit_buttons=[]
        for title,callback in [('Créer',self.create),('Modifier / copier',self.edit)]:
            b=QPushButton(title); b.clicked.connect(callback); head.addWidget(b); self.edit_buttons.append(b)
        layout.addLayout(head)
        target_row=QHBoxLayout();target_row.addWidget(QLabel('Cible du flow'))
        self.target_select=QComboBox();target_row.addWidget(self.target_select,1)
        self.target_select.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.target_select.setMinimumContentsLength(15)
        self.add_target_button=QPushButton('Ajouter une cible…');self.add_target_button.clicked.connect(self.add_flow_target);target_row.addWidget(self.add_target_button)
        layout.addLayout(target_row)
        self.target_select.currentIndexChanged.connect(self.change_target)
        files=QHBoxLayout()
        for title,callback in [('Importer CLI…',self.import_cli),('Exporter…',self.export_cli),('Supprimer',self.delete),('Résultats du flow',self.results)]:
            b=QPushButton(title); b.clicked.connect(callback); files.addWidget(b); self.edit_buttons.append(b)
        layout.addLayout(files)
        self.info=QLabel(); self.info.setWordWrap(True); self.info.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.info)
        self.list=QListWidget(); self.list.setWordWrap(True); self.list.setSpacing(8); layout.addWidget(self.list,1)
        self.feedback=QLabel('Chaque étape reste configurable avant lancement. Une étape indisponible n’est jamais exécutée silencieusement.'); self.feedback.setWordWrap(True); layout.addWidget(self.feedback)
        actions=QHBoxLayout(); self.launch=QPushButton('Configurer et exécuter l’étape'); self.launch.setObjectName('primary'); self.launch.clicked.connect(self.start_step)
        self.skip=QPushButton('Passer cette étape'); self.skip.clicked.connect(self.skip_step)
        self.restart=QPushButton('Nouvelle session'); self.restart.clicked.connect(self.reset)
        actions.addWidget(self.launch); actions.addWidget(self.skip); actions.addWidget(self.restart); layout.addLayout(actions)
        self.select.currentIndexChanged.connect(self.reset)
        window.runner.completed.connect(self.completed); window.runner.activeChanged.connect(self.activity)
        self.reload()
    def reload(self,key=None):
        self.select.blockSignals(True); self.select.clear()
        try: self.flows=load_flows(self.window.store.root)
        except (ValueError,OSError) as exc:
            from core.flow_definitions import FLOWS
            self.flows=FLOWS; self.feedback.setText('Flows personnalisés non chargés : '+str(exc))
        for k,flow in self.flows.items(): self.select.addItem(flow['name'],k)
        if key: self.select.setCurrentIndex(max(0,self.select.findData(key)))
        self.select.blockSignals(False); self.reset()
    def reset(self): self.session=None; self.refresh(); self.list.setCurrentRow(0)
    def refresh_targets(self):
        chosen=(self.session.record.get('target') or {}).get('id') if self.session else self.target_select.currentData()
        if not chosen:chosen=(self.window.store.active_target or {}).get('id')
        targets=list(self.window.store.targets)
        if self.session and not any(t['id']==chosen for t in targets):targets.append(self.session.record['target'])
        self.target_select.blockSignals(True);self.target_select.clear()
        for target in targets:self.target_select.addItem(target['label']+' — '+target['url'],target['id'])
        self.target_select.setCurrentIndex(max(0,self.target_select.findData(chosen)));self.target_select.blockSignals(False)
    def selected_target(self):
        return next((t for t in self.window.store.targets if t['id']==self.target_select.currentData()),None)
    def change_target(self):
        if self.session:
            previous=self.session.record['target']['id']
            if self.target_select.currentData()==previous:return
            if self.window.runner.active or QMessageBox.question(self,'Changer la cible du flow','Créer une nouvelle session pour cette cible ? Les résultats de la précédente session sont conservés.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:
                self.target_select.blockSignals(True);self.target_select.setCurrentIndex(self.target_select.findData(previous));self.target_select.blockSignals(False);return
            self.session=None;self.list.setCurrentRow(0)
        self.refresh()
    def add_flow_target(self):
        before=(self.window.store.active_target or {}).get('id')
        self.window.add_target();self.refresh_targets()
        active=(self.window.store.active_target or {}).get('id')
        if active and active!=before:self.target_select.setCurrentIndex(self.target_select.findData(active))
    def refresh(self):
        self.refresh_targets()
        current=self.list.currentRow(); self.list.clear(); flow=self.flows[self.select.currentData()]
        target=(self.session.record.get('target') if self.session else self.selected_target()) or {}
        self.info.setText(flow['desc']+'\nCible : '+target.get('url','Ajoutez une cible pour ce flow'))
        states={'pending':'À faire','success':'Terminé','failed':'Échec — relançable','cancelled':'Arrêté — relançable','skipped':'Passé','running':'En cours','deleted':'Résultat supprimé — relançable'}
        for index,(key,preset) in enumerate(flow['steps']):
            state=self.session.record['steps'][index]['status'] if self.session else 'pending'
            tool=self.window.tool_by_key[key]; ready=availability(tool,self.window.store.settings['executables'],self.window.store.root)[0]
            item=QListWidgetItem(); item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{index+1} {tool['name']} {states.get(state,state)}"); self.list.addItem(item)
            self.list.setItemWidget(item,self._step_widget(index,tool['name'],TOOLS[key]['presets'][preset]['label'],states.get(state,state),ready))
            item.setSizeHint(QSize(0,96))
        self.list.setCurrentRow(max(0,current))
    def _step_widget(self,index,tool_name,preset_label,state_text,ready_text):
        holder=QWidget(); holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
        box=QVBoxLayout(holder); box.setContentsMargins(6,4,6,4); box.setSpacing(5)
        title=QLabel(f"{index+1:02d} · {tool_name} — {preset_label}")
        title.setStyleSheet('font-weight:600; background:transparent;'); title.setWordWrap(True); title.setTextFormat(Qt.TextFormat.PlainText)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
        box.addWidget(title)
        pills=QHBoxLayout(); pills.setContentsMargins(0,0,0,0); pills.setSpacing(8)
        pills.addWidget(effects.status_pill(state_text)); pills.addWidget(effects.status_pill(ready_text)); pills.addStretch()
        box.addLayout(pills)
        return holder
    def ensure_session(self):
        if not self.selected_target() and not self.session:
            raise ValueError('Ajoutez et sélectionnez une cible dans la liste Cible du flow.')
        if not self.session: self.session=FlowSession(self.window.store.root,self.flows[self.select.currentData()],self.selected_target())
    def start_step(self):
        if self.window.runner.active: self.window.navigate(3); return
        i=self.list.currentRow()
        if i<0: return
        try:
            self.ensure_session(); key,index=self.session.flow['steps'][i]
            tool=step_tool(self.window.tool_by_key[key],index)
            context={'flow_id':self.session.record['id'],'flow_name':self.session.record['name'],'flow_step':i,'flow_target':self.session.record.get('target')}
            started=self.window.launch(key,tool_override=tool,metadata=context,target_override=self.session.record.get('target'))
            if started: self.session.update(i,'running'); self.refresh()
        except (ValueError,OSError) as exc: QMessageBox.warning(self,'Étape non lancée',str(exc))
    def skip_step(self):
        i=self.list.currentRow()
        if i<0 or self.window.runner.active: return
        try: self.ensure_session()
        except ValueError as exc: QMessageBox.warning(self,'Cible requise',str(exc)); return
        self.session.update(i,'skipped'); self.refresh(); self.list.setCurrentRow(min(i+1,self.list.count()-1))
    def completed(self,run):
        if not self.session or run.get('flow_id')!=self.session.record['id']: return
        i=run['flow_step']; self.session.update(i,run['status'],run); self.refresh()
        if run['status']=='success': self.list.setCurrentRow(min(i+1,self.list.count()-1))
        self.feedback.setText('Étape terminée. Consultez les résultats puis choisissez la suivante.' if run['status']=='success' else 'Étape arrêtée ou en échec. Relancez-la, passez-la ou ouvrez son journal.')
    def activity(self,active):
        for widget in (self.select,self.target_select,self.add_target_button,self.launch,self.skip,self.restart,*self.edit_buttons): widget.setEnabled(not active)
    def create(self): self.editor()
    def edit(self): self.editor(self.flows[self.select.currentData()],self.select.currentData())
    def editor(self,flow=None,key=None):
        dialog=FlowEditor(self,flow)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try: self.reload(save_custom(self.window.store.root,dialog.value(),key if key and key.startswith('custom-') else None))
            except (ValueError,OSError) as exc: QMessageBox.warning(self,'Flow non enregistré',str(exc))
    def import_cli(self):
        path,_=QFileDialog.getOpenFileName(self,'Importer custom_flows.json','','JSON (*.json)')
        if path:
            try: self.reload(import_flows(self.window.store.root,path)[0])
            except (ValueError,OSError) as exc: QMessageBox.warning(self,'Import impossible',str(exc))
    def export_cli(self):
        from desktop.storage import write_json
        from pathlib import Path
        path,_=QFileDialog.getSaveFileName(self,'Exporter un flow','custom_flows.json','JSON (*.json)')
        if path:
            try: write_json(Path(path),{self.select.currentData():self.flows[self.select.currentData()]})
            except OSError as exc: QMessageBox.warning(self,'Export impossible',str(exc))
    def delete(self):
        from desktop.storage import write_json
        key=self.select.currentData()
        if not key.startswith('custom-'):
            QMessageBox.information(self,'Flow fourni','Les flows fournis sont conservés. Vous pouvez les dupliquer puis modifier leur copie.'); return
        if QMessageBox.question(self,'Supprimer ce flow','Supprimer ce flow personnalisé ? Ses journaux seront conservés.')!=QMessageBox.StandardButton.Yes: return
        try:
            flows=load_flows(self.window.store.root)
            write_json(self.window.store.root/'flows/custom.json',{k:v for k,v in flows.items() if k.startswith('custom-') and k!=key})
            self.reload()
        except (ValueError,OSError) as exc: QMessageBox.warning(self,'Suppression impossible',str(exc))
    def results(self):
        self.window.reset_history_filters()
        target=self.session.record.get('target') if self.session else self.selected_target()
        index=self.window.history_target.findData(self.window.history_target_key(target))
        if index>=0:self.window.history_target.setCurrentIndex(index)
        self.window.history_search.setText(self.flows[self.select.currentData()]['name'])
        self.window.navigate(4)
