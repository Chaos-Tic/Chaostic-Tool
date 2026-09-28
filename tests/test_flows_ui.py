import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_desktop import APP,wait_run
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QDialog
from PySide6.QtTest import QTest
from desktop.window import Window
from desktop.storage import Store,write_json
from desktop.catalog import catalog
from desktop.flows import validate_flow,load_flows,save_custom,import_flows,step_tool,FlowSession
from core.tools import TOOLS
from core.phases import PHASES
from core.flow_definitions import FLOWS

class FlowsUiTests(unittest.TestCase):
    def test_every_cli_profile_resolves_by_identity(self):
        items={t['key']:t for t in catalog()}
        self.assertEqual(set(TOOLS),{k for phase in PHASES for k in phase['tools']})
        for key,tool in TOOLS.items():
            for index in range(len(tool['presets'])):
                with self.subTest(key=key,index=index):
                    resolved=step_tool(items[key],index)
                    self.assertTrue(resolved['presets'])
                    if items[key]['mode']!='builtin': self.assertEqual(resolved['presets'][0]['cli_index'],index)

    def test_custom_flow_import_is_atomic_and_invalid_values_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); flow=next(iter(FLOWS.values())); key=save_custom(root,flow)
            self.assertIn(key,load_flows(root))
            before=(root/'flows/custom.json').read_bytes()
            path=root/'import.json'; write_json(path,{'valid':flow,'bad':{'name':'Bad','steps':[['nmap',999]]}})
            with self.assertRaises(ValueError): import_flows(root,path)
            self.assertEqual(before,(root/'flows/custom.json').read_bytes())
            for bad in [{'name':[], 'steps':[['nmap',0]]},{'name':'A','steps':[[[],0]]},{'name':'A','steps':[['nmap',True]]}]:
                with self.assertRaises(ValueError): validate_flow(bad)
            write_json(path,{'example':flow}); self.assertEqual(len(import_flows(root,path)),1)

    def test_descriptive_run_folders_preserve_legacy_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp));target=store.add_target('https://example.test/path?token=private')
            folder,run=store.new_run('Nmap','Ports TCP : 80/443',target,[])
            self.assertIn('__example-test__nmap__ports-tcp-80-443__',folder.name)
            self.assertNotIn('private',folder.name)
            legacy=store.root/'runs/20200101-abcd'; write_json(legacy/'run.json',dict(id=legacy.name,tool='Old',preset='Old',status='success',started='2020'))
            self.assertEqual(len(store.history()),2)

    def test_execution_button_and_actual_stop_from_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            window=Window(Store(Path(tmp))); window.show();window.navigate(3); APP.processEvents()
            self.assertFalse(window.stop_button.isVisible());self.assertTrue(window.execute_button.isVisible())
            window.execution_tool.setCurrentIndex(window.execution_tool.findData('desktop-diagnostic'))
            def accept_dialog():
                dialog=APP.activeModalWidget()
                self.assertIsNotNone(dialog);dialog.accept()
            def start():
                QTimer.singleShot(50,accept_dialog);QTest.mouseClick(window.execute_button,Qt.MouseButton.LeftButton)
            result=wait_run(window.runner,start)
            self.assertEqual(result['status'],'success')
            def sleeper():
                window.runner.start('UI test','Sleep',None,command=[sys.executable,'-u','-c','import time; print("started",flush=True); time.sleep(30)'])
                self.assertTrue(window.stop_button.isEnabled());self.assertFalse(window.execute_button.isEnabled())
                QTimer.singleShot(300,lambda:QTest.mouseClick(window.stop_button,Qt.MouseButton.LeftButton))
            result=wait_run(window.runner,sleeper)
            self.assertEqual(result['status'],'cancelled');self.assertFalse(window.stop_button.isVisible());self.assertTrue(window.execute_button.isEnabled())
            window.close()

    def test_flow_success_moves_selection_without_automatic_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)); store.add_target('localhost');window=Window(store)
            panel=window.flow_panel;panel.ensure_session()
            with patch.object(window,'launch',return_value=True) as launch:
                panel.start_step();self.assertEqual(panel.session.record['steps'][0]['status'],'running')
                run={'flow_id':panel.session.record['id'],'flow_step':0,'status':'success','id':'test-run'}
                panel.completed(run);self.assertEqual(panel.list.currentRow(),1);self.assertEqual(launch.call_count,1)
                run.update(flow_step=1,status='failed');panel.completed(run);self.assertEqual(panel.list.currentRow(),1)
            window.close()

    def test_phase_filter_includes_active_directory_and_small_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            window=Window(Store(Path(tmp))); window.resize(900,600);window.show();window.navigate(2);APP.processEvents()
            window.category.setCurrentIndex(window.category.findData('08_windows'))
            self.assertEqual({t['key'] for t in window.filtered_tools},set(PHASES[7]['tools']))
            self.assertEqual(window.size().width(),900)
            self.assertEqual(window.tools_split.orientation(),Qt.Orientation.Vertical)
            window.close()
