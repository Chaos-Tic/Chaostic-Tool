import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from desktop.storage import Store,write_json
from desktop.release_audit import assert_clean_bundle
from test_desktop import APP
from desktop.window import Window
from PySide6.QtWidgets import QMessageBox

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
