from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QListWidget,QListWidgetItem,QDialog,QDialogButtonBox,QLineEdit,QFileDialog,QMessageBox,QScrollArea,QFrame,QFormLayout,QCheckBox
from core.tools import TOOLS
from desktop.catalog import availability
from desktop.flows import load_flows,save_custom,import_flows,validate_flow,step_tool,FlowSession
from desktop.launch_dialog import LaunchDialog,command_preview
from desktop import effects
from desktop.i18n import T

def _tool_ready(window,key):
    """Availability label for a tool key, or None when it cannot be resolved."""
    tool=window.tool_by_key.get(key) if window else None
    if not tool: return None
    return availability(tool,window.store.settings['executables'],window.store.root)[0]

class FlowEditor(QDialog):
    def __init__(self,parent,flow=None,window=None):
        super().__init__(parent); self.setWindowTitle(T('Éditeur de flow')); self.resize(720,620)
        self.window=window
        self.steps=[list(s) for s in (flow or {}).get('steps',[])]
        layout=QVBoxLayout(self)
        self.name=QLineEdit((flow or {}).get('name','')); self.name.setPlaceholderText(T('Nom du flow'))
        self.desc=QLineEdit((flow or {}).get('desc','')); self.desc.setPlaceholderText(T('Description'))
        layout.addWidget(self.name); layout.addWidget(self.desc)
        pick=QHBoxLayout(); self.tools=QComboBox(); self.profiles=QComboBox()
        for key,t in TOOLS.items():
            ready=_tool_ready(window,key)
            self.tools.addItem(T(t['name'])+(' · '+T(ready) if ready else ''),key)
        def profiles():
            self.profiles.clear(); self.profiles.addItems([T(p['label']) for p in TOOLS[self.tools.currentData()]['presets']])
        self.tools.currentIndexChanged.connect(profiles); profiles()
        pick.addWidget(self.tools); pick.addWidget(self.profiles,1)
        add=QPushButton(T('Ajouter')); add.clicked.connect(self.add); pick.addWidget(add); layout.addLayout(pick)
        self.list=QListWidget(); layout.addWidget(self.list,1)
        actions=QHBoxLayout()
        for label,fn in [(T('Monter'),lambda:self.move(-1)),(T('Descendre'),lambda:self.move(1)),(T('Retirer'),self.remove)]:
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        layout.addLayout(actions)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons); self.refresh()
    def refresh(self):
        self.list.clear()
        for k,i in self.steps: self.list.addItem(T(TOOLS[k]['name'])+' — '+T(TOOLS[k]['presets'][i]['label']))
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
        except ValueError as exc: QMessageBox.warning(self,T('Flow invalide'),str(exc)); return
        super().accept()

class FlowPrepareDialog(QDialog):
    """Collect every step's required fields once, with per-step command preview.

    Replaces the one-modal-per-step launch: the whole flow is reviewed and its
    typed fields entered here, then the steps chain automatically.
    """
    def __init__(self,parent,window,flow,target,steps):
        super().__init__(parent); self.window=window; self.target=target
        self.setWindowTitle(T('Préparer le flow')); self.resize(760,680)
        self.editors={}  # {step_index: {field_name: QLineEdit}}
        layout=QVBoxLayout(self)
        intro=QLabel(T('Renseignez une fois les champs requis. Les étapes disponibles s’enchaînent ensuite automatiquement.'))
        intro.setWordWrap(True); layout.addWidget(intro)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); body=QWidget(); col=QVBoxLayout(body)
        for i,(key,index) in enumerate(steps):
            col.addWidget(self._step_group(i,key,index))
        col.addStretch(); scroll.setWidget(body); layout.addWidget(scroll,1)
        self.confirm_each=QCheckBox(T('Confirmer chaque étape (pas-à-pas)')); layout.addWidget(self.confirm_each)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(T('Exécuter le flow'))
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def _step_group(self,i,key,index):
        group=QFrame(); group.setObjectName('cmdcard'); gl=QVBoxLayout(group)
        tool=self.window.tool_by_key[key]
        ready=availability(tool,self.window.store.settings['executables'],self.window.store.root)[0]
        title=QLabel(f"{i+1:02d} · {T(tool['name'])} — {T(TOOLS[key]['presets'][index]['label'])}")
        title.setStyleSheet('font-weight:600; background:transparent;'); title.setWordWrap(True); gl.addWidget(title)
        pills=QHBoxLayout(); pills.addWidget(effects.status_pill(ready)); pills.addStretch(); gl.addLayout(pills)
        self.editors[i]={}
        try:
            resolved=step_tool(tool,index)
        except ValueError as exc:
            note=QLabel(T(str(exc))); note.setObjectName('muted'); note.setWordWrap(True); gl.addWidget(note); return group
        # A hidden launch dialog resolves the exact backend/preset/fields this
        # step will use, so the collected fields match what actually runs.
        probe=LaunchDialog(resolved,self.window.store,self)
        if self.target: probe.target_override=self.target
        preset=probe.preset()
        if probe.extra_fields:
            form=QFormLayout()
            for name,edit in probe.extra_fields.items():
                mirror=QLineEdit(edit.text())
                if edit.echoMode()==QLineEdit.EchoMode.Password: mirror.setEchoMode(QLineEdit.EchoMode.Password)
                lbl=probe.extra_form.labelForField(edit)
                form.addRow(lbl.text() if lbl else T(name),mirror)
                self.editors[i][name]=mirror
            gl.addLayout(form)
        preview=QLabel(); preview.setObjectName('cmdlabel'); preview.setWordWrap(True); preview.setTextFormat(Qt.TextFormat.PlainText)
        try:
            preview.setText(command_preview(resolved,preset,(self.target if preset.get('needs_target',True) else None),
                                             probe.wordlist.text(),probe.field_values(),probe.effective_backend()))
        except (ValueError,KeyError,TypeError):
            preview.setText(T('Commande complétée au lancement.'))
        gl.addWidget(preview); probe.deleteLater()
        return group

    def values(self):
        return {i:{name:e.text() for name,e in editors.items()} for i,editors in self.editors.items() if editors}


class FlowPanel(QWidget):
    def __init__(self,window):
        super().__init__(); self.window=window; self.session=None
        self.auto_run=False; self.confirm_each=False; self.prepared={}
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        head=QHBoxLayout(); self.select=QComboBox(); head.addWidget(self.select,1)
        self.edit_buttons=[]
        for title,callback in [(T('Créer'),self.create),(T('Modifier / copier'),self.edit)]:
            b=QPushButton(title); b.clicked.connect(callback); head.addWidget(b); self.edit_buttons.append(b)
        layout.addLayout(head)
        target_row=QHBoxLayout();target_row.addWidget(QLabel(T('Cible du flow')))
        self.target_select=QComboBox();target_row.addWidget(self.target_select,1)
        self.target_select.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.target_select.setMinimumContentsLength(15)
        self.add_target_button=QPushButton(T('Ajouter une cible…'));self.add_target_button.clicked.connect(self.add_flow_target);target_row.addWidget(self.add_target_button)
        layout.addLayout(target_row)
        self.target_select.currentIndexChanged.connect(self.change_target)
        files=QHBoxLayout()
        for title,callback in [(T('Importer CLI…'),self.import_cli),(T('Exporter…'),self.export_cli),(T('Supprimer'),self.delete),(T('Résultats du flow'),self.results)]:
            b=QPushButton(title); b.clicked.connect(callback); files.addWidget(b); self.edit_buttons.append(b)
        layout.addLayout(files)
        self.info=QLabel(); self.info.setWordWrap(True); self.info.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.info)
        self.list=QListWidget(); self.list.setWordWrap(True); self.list.setSpacing(8); layout.addWidget(self.list,1)
        self.feedback=QLabel(T('Chaque étape reste configurable avant lancement. Une étape indisponible n’est jamais exécutée silencieusement.')); self.feedback.setWordWrap(True); layout.addWidget(self.feedback)
        actions=QHBoxLayout()
        self.run_all_button=QPushButton(T('Exécuter tout le flow')); self.run_all_button.setObjectName('primary'); self.run_all_button.clicked.connect(self.run_all)
        self.launch=QPushButton(T('Configurer et exécuter l’étape')); self.launch.clicked.connect(self.start_step)
        self.skip=QPushButton(T('Passer cette étape')); self.skip.clicked.connect(self.skip_step)
        self.restart=QPushButton(T('Nouvelle session')); self.restart.clicked.connect(self.reset)
        actions.addWidget(self.run_all_button); actions.addWidget(self.launch); actions.addWidget(self.skip); actions.addWidget(self.restart); layout.addLayout(actions)
        self.select.currentIndexChanged.connect(self.reset)
        window.runner.completed.connect(self.completed); window.runner.activeChanged.connect(self.activity)
        self.reload()
    def reload(self,key=None):
        self.select.blockSignals(True); self.select.clear()
        try: self.flows=load_flows(self.window.store.root)
        except (ValueError,OSError) as exc:
            from core.flow_definitions import FLOWS
            self.flows=FLOWS; self.feedback.setText(T('Flows personnalisés non chargés : ')+str(exc))
        for k,flow in self.flows.items(): self.select.addItem(T(flow['name']),k)
        if key: self.select.setCurrentIndex(max(0,self.select.findData(key)))
        self.select.blockSignals(False); self.reset()
    def reset(self): self.session=None; self.auto_run=False; self.confirm_each=False; self.prepared={}; self.refresh(); self.list.setCurrentRow(0)
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
            if self.window.runner.active or QMessageBox.question(self,T('Changer la cible du flow'),T('Créer une nouvelle session pour cette cible ? Les résultats de la précédente session sont conservés.'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:
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
        self.info.setText(T(flow['desc'])+T('\nCible : ')+target.get('url',T('Ajoutez une cible pour ce flow')))
        states={'pending':T('À faire'),'success':T('Terminé'),'failed':T('Échec — relançable'),'cancelled':T('Arrêté — relançable'),'skipped':T('Passé'),'running':T('En cours'),'deleted':T('Résultat supprimé — relançable')}
        for index,(key,preset) in enumerate(flow['steps']):
            state=self.session.record['steps'][index]['status'] if self.session else 'pending'
            tool=self.window.tool_by_key[key]; ready=availability(tool,self.window.store.settings['executables'],self.window.store.root)[0]
            item=QListWidgetItem(); item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{index+1} {tool['name']} {states.get(state,state)}"); self.list.addItem(item)
            self.list.setItemWidget(item,self._step_widget(index,tool['name'],TOOLS[key]['presets'][preset]['label'],states.get(state,state),ready,self._step_command(key,preset,target)))
            item.setSizeHint(QSize(0,118))
        self.list.setCurrentRow(max(0,current))
    def _step_command(self,key,index,target):
        """Previewed command line for a flow step, or '' when not composable yet."""
        try:
            resolved=step_tool(self.window.tool_by_key[key],index); preset=resolved['presets'][0]
            backend='builtin' if resolved['mode']=='builtin' else 'native'
            return command_preview(resolved,preset,(target or None) if preset.get('needs_target',True) else None,'',{},backend)
        except (ValueError,KeyError,TypeError,IndexError):
            return ''
    def _step_widget(self,index,tool_name,preset_label,state_text,ready_text,command=''):
        holder=QWidget(); holder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
        box=QVBoxLayout(holder); box.setContentsMargins(6,4,6,4); box.setSpacing(5)
        title=QLabel(f"{index+1:02d} · {T(tool_name)} — {T(preset_label)}")
        title.setStyleSheet('font-weight:600; background:transparent;'); title.setWordWrap(True); title.setTextFormat(Qt.TextFormat.PlainText)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
        box.addWidget(title)
        pills=QHBoxLayout(); pills.setContentsMargins(0,0,0,0); pills.setSpacing(8)
        pills.addWidget(effects.status_pill(state_text)); pills.addWidget(effects.status_pill(ready_text)); pills.addStretch()
        box.addLayout(pills)
        if command:
            cmd=QLabel(command); cmd.setObjectName('cmdlabel'); cmd.setWordWrap(True); cmd.setTextFormat(Qt.TextFormat.PlainText)
            cmd.setStyleSheet('background:transparent;'); cmd.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
            box.addWidget(cmd)
        return holder
    def ensure_session(self):
        if not self.selected_target() and not self.session:
            raise ValueError(T('Ajoutez et sélectionnez une cible dans la liste Cible du flow.'))
        if not self.session: self.session=FlowSession(self.window.store.root,self.flows[self.select.currentData()],self.selected_target())
    def _context(self,i):
        return {'flow_id':self.session.record['id'],'flow_name':self.session.record['name'],'flow_step':i,
                'flow_total':len(self.session.flow['steps']),'flow_target':self.session.record.get('target')}
    def _next_runnable(self,after):
        if not self.session: return None
        return next((j for j in range(after+1,len(self.session.flow['steps']))
                     if self.session.record['steps'][j]['status'] not in ('success','skipped')),None)
    def _launch_step(self,i,show_dialog=False):
        """Start step ``i`` reusing the plumbing fan-out runs already use.

        ``show_dialog=False`` feeds the values collected in the preparation
        screen, so no per-step modal appears. Returns whether a run started;
        a composition error stops the chain cleanly and is surfaced.
        """
        if i is None or i<0 or i>=len(self.session.flow['steps']) or self.window.runner.active: return False
        key,index=self.session.flow['steps'][i]
        overrides=self.prepared.get(i) or None
        try:
            tool=step_tool(self.window.tool_by_key[key],index)
            started=self.window.launch(key,show_dialog=show_dialog,tool_override=tool,metadata=self._context(i),
                                       target_override=self.session.record.get('target'),field_overrides=overrides,
                                       wordlist_override=(overrides or {}).get('wordlist'))
        except (ValueError,OSError,RuntimeError) as exc:
            self.auto_run=False; self.feedback.setText(T('Enchaînement interrompu : ')+str(exc))
            QMessageBox.warning(self,T('Étape non lancée'),str(exc)); return False
        if started: self.session.update(i,'running'); self.refresh()
        return started
    def run_all(self):
        if self.window.runner.active: self.window.navigate(3); return
        try: self.ensure_session()
        except ValueError as exc: QMessageBox.warning(self,T('Cible requise'),str(exc)); return
        dialog=FlowPrepareDialog(self,self.window,self.session.flow,self.session.record.get('target'),self.session.flow['steps'])
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        self.prepared=dialog.values(); self.confirm_each=dialog.confirm_each.isChecked(); self.auto_run=True
        start=self._next_runnable(-1)
        if start is None: self.auto_run=False; self.feedback.setText(T('Toutes les étapes sont déjà terminées.')); return
        self.list.setCurrentRow(start)
        if self.confirm_each:
            self.feedback.setText(T('Champs enregistrés. Lancez chaque étape avec « Configurer et exécuter l’étape ».'))
        else:
            self._launch_step(start)
    def start_step(self):
        if self.window.runner.active: self.window.navigate(3); return
        i=self.list.currentRow()
        if i<0: return
        if self.auto_run:
            # Prepared pas-à-pas: run the selected step with the values collected once.
            self._launch_step(i); return
        try:
            self.ensure_session(); key,index=self.session.flow['steps'][i]
            tool=step_tool(self.window.tool_by_key[key],index)
            started=self.window.launch(key,tool_override=tool,metadata=self._context(i),target_override=self.session.record.get('target'))
            if started: self.session.update(i,'running'); self.refresh()
        except (ValueError,OSError) as exc: QMessageBox.warning(self,T('Étape non lancée'),str(exc))
    def skip_step(self):
        i=self.list.currentRow()
        if i<0 or self.window.runner.active: return
        try: self.ensure_session()
        except ValueError as exc: QMessageBox.warning(self,T('Cible requise'),str(exc)); return
        self.session.update(i,'skipped'); self.refresh(); self.list.setCurrentRow(min(i+1,self.list.count()-1))
    def completed(self,run):
        if not self.session or run.get('flow_id')!=self.session.record['id']: return
        i=run['flow_step']; status=run['status']
        # A subdomain fan-out keeps the same step across every host. Only the last
        # host (or an abort) finalises the step, so it is never marked done before
        # the final host has actually run.
        if not run.get('flow_last',True) and status!='cancelled':
            self.refresh(); return
        self.session.update(i,status,run); self.refresh()
        if status=='success':
            self.list.setCurrentRow(min(i+1,self.list.count()-1))
            if self.auto_run and not self.confirm_each:
                nxt=self._next_runnable(i)
                if nxt is not None:
                    self.feedback.setText(T('Étape terminée. Lancement de la suivante…')); self._launch_step(nxt); return
                self.auto_run=False; self.feedback.setText(T('Flow terminé : toutes les étapes ont réussi.')); return
            self.feedback.setText(T('Étape terminée. Consultez les résultats puis choisissez la suivante.'))
        else:
            # Pure auto-run stops on failure/abort; prepared pas-à-pas keeps its
            # collected values so the user can relaunch or skip the step.
            if self.auto_run and not self.confirm_each: self.auto_run=False
            self.feedback.setText(T('Étape arrêtée ou en échec. Relancez-la, passez-la ou ouvrez son journal.'))
    def activity(self,active):
        for widget in (self.select,self.target_select,self.add_target_button,self.run_all_button,self.launch,self.skip,self.restart,*self.edit_buttons): widget.setEnabled(not active)
    def create(self): self.editor()
    def edit(self): self.editor(self.flows[self.select.currentData()],self.select.currentData())
    def editor(self,flow=None,key=None):
        dialog=FlowEditor(self,flow,self.window)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try: self.reload(save_custom(self.window.store.root,dialog.value(),key if key and key.startswith('custom-') else None))
            except (ValueError,OSError) as exc: QMessageBox.warning(self,T('Flow non enregistré'),str(exc))
    def import_cli(self):
        path,_=QFileDialog.getOpenFileName(self,T('Importer custom_flows.json'),'','JSON (*.json)')
        if path:
            try: self.reload(import_flows(self.window.store.root,path)[0])
            except (ValueError,OSError) as exc: QMessageBox.warning(self,T('Import impossible'),str(exc))
    def export_cli(self):
        from desktop.storage import write_json
        from pathlib import Path
        path,_=QFileDialog.getSaveFileName(self,T('Exporter un flow'),'custom_flows.json','JSON (*.json)')
        if path:
            try: write_json(Path(path),{self.select.currentData():self.flows[self.select.currentData()]})
            except OSError as exc: QMessageBox.warning(self,T('Export impossible'),str(exc))
    def delete(self):
        from desktop.storage import write_json
        key=self.select.currentData()
        if not key.startswith('custom-'):
            QMessageBox.information(self,T('Flow fourni'),T('Les flows fournis sont conservés. Vous pouvez les dupliquer puis modifier leur copie.')); return
        if QMessageBox.question(self,T('Supprimer ce flow'),T('Supprimer ce flow personnalisé ? Ses journaux seront conservés.'))!=QMessageBox.StandardButton.Yes: return
        try:
            flows=load_flows(self.window.store.root)
            write_json(self.window.store.root/'flows/custom.json',{k:v for k,v in flows.items() if k.startswith('custom-') and k!=key})
            self.reload()
        except (ValueError,OSError) as exc: QMessageBox.warning(self,T('Suppression impossible'),str(exc))
    def results(self):
        self.window.reset_history_filters()
        target=self.session.record.get('target') if self.session else self.selected_target()
        index=self.window.history_target.findData(self.window.history_target_key(target))
        if index>=0:self.window.history_target.setCurrentIndex(index)
        self.window.history_search.setText(self.flows[self.select.currentData()]['name'])
        self.window.navigate(4)
