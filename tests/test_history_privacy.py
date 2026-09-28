import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from desktop.storage import Store,write_json
from desktop.release_audit import assert_clean_bundle
from test_desktop import APP
from desktop.window import Window
from PySide6.QtWidgets import QMessageBox
from desktop.flows import FlowSession
from core.flow_definitions import FLOWS

class HistoryPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'profile')
    def tearDown(self):self.temp.cleanup()
    def add_run(self):
        folder,record=self.store.new_run('DNS','Local',{},['builtin','dns'])
        record['status']='success';write_json(folder/'run.json',record)
        (folder/'output.txt').write_text('private result',encoding='utf-8')
        return folder
    def test_clear_removes_artifacts_but_preserves_settings_and_tools(self):
        self.store.add_target('localhost');self.add_run()
        for name in ['linux.json','wsl-setup.json','tools/installed.json']:
            write_json(self.store.root/name,{'keep':True})
        before=self.store.path.read_bytes()
        self.store.clear_history()
        self.assertEqual(self.store.history(),[]);self.assertFalse((self.store.root/'runs').exists())
        self.assertEqual(self.store.path.read_bytes(),before)
        for name in ['linux.json','wsl-setup.json','tools/installed.json']:self.assertTrue((self.store.root/name).exists())
        self.add_run();self.assertEqual(len(self.store.history()),1)
    def test_active_record_blocks_deletion(self):
        folder,_=self.store.new_run('DNS','Local',{},[])
        with self.assertRaises(ValueError):self.store.clear_history()
        self.assertTrue(folder.exists())
    def test_external_link_is_never_deleted(self):
        folder=self.add_run();outside=self.root/'outside';outside.mkdir();marker=outside/'keep.txt';marker.write_text('keep')
        link=folder/'external'
        try:link.symlink_to(outside,target_is_directory=True)
        except OSError:self.skipTest('Symlink creation unavailable')
        with self.assertRaises(ValueError):self.store.clear_history()
        self.assertEqual(marker.read_text(),'keep');link.unlink()
    def test_ui_cancel_and_confirm_refresh_views(self):
        self.add_run();w=Window(self.store)
        try:
            with patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Cancel):w.clear_history()
            self.assertEqual(len(self.store.history()),1)
            w.history_search.setText('no visible match')
            with patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Yes):w.clear_history()
            self.assertEqual(self.store.history(),[]);self.assertEqual(w.history_table.rowCount(),0)
            self.assertEqual(w.console.toPlainText(),'');self.assertFalse(w.run_folder.isEnabled())
            w.active_changed(True);self.assertFalse(w.clear_history_button.isEnabled())
            w.active_changed(False);self.assertTrue(w.clear_history_button.isEnabled())
        finally:w.close();w.deleteLater();APP.processEvents()
    def test_clean_bundle_audit_rejects_nested_user_data(self):
        bundle=self.root/'bundle';bundle.mkdir();(bundle/'application.exe').write_bytes(b'app')
        assert_clean_bundle(bundle)
        state=bundle/'_internal'/'accidental-profile';state.mkdir(parents=True)
        for name in ['settings.json','run.json','wsl-setup.json']:
            path=state/name;path.write_text('{}')
            with self.assertRaises(ValueError):assert_clean_bundle(bundle)
            path.unlink()
    def test_new_profile_never_inherits_another_profiles_history(self):
        self.store.add_target('localhost');self.add_run()
        clean=Store(self.root/'new-user')
        self.assertEqual(clean.history(),[]);self.assertEqual(clean.targets,[])

    def test_delete_one_result_updates_flow_references_and_keeps_others(self):
        folder=self.add_run();other=self.add_run()
        session=FlowSession(self.store.root,next(iter(FLOWS.values())),{'id':'target'})
        session.update(0,'success',{'id':folder.name})
        self.store.delete_run(folder.name)
        self.assertFalse(folder.exists());self.assertTrue(other.exists())
        import json
        saved=json.loads(session.path.read_text(encoding='utf-8'))
        self.assertEqual(saved['steps'][0]['status'],'deleted');self.assertNotIn('run_id',saved['steps'][0])
        for bad in ['../outside','..','a/b','a\\b']:
            with self.assertRaises(ValueError):self.store.delete_run(bad)

    def test_clear_also_removes_flow_sessions_not_custom_definitions(self):
        self.add_run();session=FlowSession(self.store.root,next(iter(FLOWS.values())),{'id':'target'})
        custom=self.store.root/'flows/custom.json';write_json(custom,{'keep':True})
        self.store.clear_history()
        self.assertFalse(session.path.exists());self.assertTrue(custom.exists())

    def test_combined_filters_and_single_result_ui_deletion(self):
        a=self.store.add_target('localhost','Alpha');b=self.store.add_target('127.0.0.1','Beta')
        for target,status,tool,date in [(a,'success','DNS','2020-01-01T00:00:00+00:00'),(b,'failed','Nmap',None),(a,'success','Nmap',None)]:
            path,record=self.store.new_run(tool,'Profile',target,[]);record['status']=status
            if tool=='DNS':record['flow_target']=target;record['target']=None
            if date:record['started']=date
            write_json(path/'run.json',record);(path/'output.txt').write_text('log')
        w=Window(self.store)
        try:
            w.history_target.setCurrentIndex(w.history_target.findData(a['id']))
            self.assertEqual(len(w.visible_history),2)
            w.history_tool.setCurrentIndex(w.history_tool.findData('Nmap'))
            w.history_state.setCurrentIndex(w.history_state.findData('success'))
            w.history_period.setCurrentIndex(1)
            self.assertEqual(len(w.visible_history),1)
            w.history_table.selectRow(0)
            with patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Yes):w.delete_history_result()
            self.assertEqual(len(self.store.history()),2);self.assertEqual(len(w.visible_history),0)
            w.reset_history_filters();self.assertEqual(len(w.visible_history),2)
        finally:w.close();w.deleteLater();APP.processEvents()

    def test_flow_target_is_explicit_and_session_change_requires_confirmation(self):
        a=self.store.add_target('localhost','Alpha');b=self.store.add_target('127.0.0.1','Beta')
        w=Window(self.store);panel=w.flow_panel
        try:
            panel.target_select.setCurrentIndex(panel.target_select.findData(a['id']))
            with patch.object(w,'launch',return_value=True) as launch:
                panel.start_step()
                self.assertEqual(launch.call_args.kwargs['target_override']['id'],a['id'])
            original=panel.session.record['id']
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Cancel):
                panel.target_select.setCurrentIndex(panel.target_select.findData(b['id']))
            self.assertEqual(panel.session.record['id'],original)
            self.assertEqual(panel.target_select.currentData(),a['id'])
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
                panel.target_select.setCurrentIndex(panel.target_select.findData(b['id']))
            panel.ensure_session()
            self.assertNotEqual(panel.session.record['id'],original)
            self.assertEqual(panel.session.record['target']['id'],b['id'])
            self.assertTrue((self.store.root/'flows/history'/(original+'.json')).exists())
            panel.activity(True);self.assertFalse(panel.target_select.isEnabled())
            panel.activity(False)
        finally:w.close();w.deleteLater();APP.processEvents()
