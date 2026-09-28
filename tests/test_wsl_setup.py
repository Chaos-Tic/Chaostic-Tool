import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from desktop import wsl_setup
from desktop.backends import get_config,save_config,execution_plan

class WslSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def run_setup(self,installed=None,side_effect=None):
        with patch.object(wsl_setup.sys,'platform','win32'), patch.object(wsl_setup.sys,'getwindowsversion',return_value=SimpleNamespace(build=22631),create=True), patch.object(wsl_setup,'distributions',side_effect=[installed if installed is not None else ['kali-linux'],['kali-linux']]), patch.object(wsl_setup,'command',side_effect=side_effect or (lambda args,**kwargs:'1001' if args[-2:]==['id','-u'] else '')) as calls, patch.object(wsl_setup,'inspect_backend') as inventory:
            wsl_setup.prepare({'root':str(self.root),'tools':True})
            return calls,inventory
    def test_existing_kali_is_reused_and_nonroot_backend_saved(self):
        calls,inventory=self.run_setup()
        self.assertEqual(get_config(self.root)['wsl_user'],'chaostic-tool')
        self.assertFalse(any('--install' in c.args[0] for c in calls.call_args_list))
        self.assertFalse(any('--set-default' in c.args[0] for c in calls.call_args_list))
        inventory.assert_called_once()
        self.assertEqual(json.loads((self.root/'wsl-setup.json').read_text())['stage'],'ready')
    def test_other_distro_does_not_get_modified(self):
        calls,_=self.run_setup(['Ubuntu'])
        self.assertTrue(any('--install' in c.args[0] for c in calls.call_args_list))
        self.assertTrue(all('Ubuntu' not in c.args[0] for c in calls.call_args_list))
    def test_failure_is_resumable_without_overwriting_backend(self):
        save_config({'backend':'ssh','host':'my-host'},self.root)
        with self.assertRaises(RuntimeError):self.run_setup(side_effect=RuntimeError('download unavailable'))
        self.assertEqual(get_config(self.root)['host'],'my-host')
        self.assertEqual(json.loads((self.root/'wsl-setup.json').read_text())['stage'],'À reprendre')
    def test_failed_inventory_restores_previous_configuration(self):
        save_config({'backend':'ssh','host':'my-host'},self.root)
        with patch.object(wsl_setup.sys,'platform','win32'),patch.object(wsl_setup.sys,'getwindowsversion',return_value=SimpleNamespace(build=22631),create=True),patch.object(wsl_setup,'distributions',return_value=['kali-linux']),patch.object(wsl_setup,'command',return_value='1001'),patch.object(wsl_setup,'inspect_backend',side_effect=RuntimeError('inventory failed')):
            with self.assertRaises(RuntimeError):wsl_setup.prepare({'root':str(self.root)})
        self.assertEqual(get_config(self.root)['host'],'my-host')
    def test_managed_root_is_only_used_for_explicit_privileged_profile(self):
        save_config({'backend':'wsl','distro':'kali-linux','wsl_user':'chaostic-tool'},self.root)
        with patch('desktop.backends.linux_path',return_value='/tmp/run'):
            normal,_=execution_plan(['nmap'],{},self.root,self.root)
            elevated,_=execution_plan(['nmap'],{'requires_root':True},self.root,self.root)
        self.assertEqual(normal[normal.index('--user')+1],'chaostic-tool')
        self.assertEqual(elevated[elevated.index('--user')+1],'root')

    def test_french_success_output_still_requires_restart(self):
        output='L’opération demandée est réussie. Les modifications ne seront pas effectives avant que le système n’ait été réamorcé.'
        with patch.object(wsl_setup.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=output.encode('utf-16-le'),stderr=b'')):
            with self.assertRaises(wsl_setup.SetupPending):
                wsl_setup.command(['wsl.exe','--install','--distribution','kali-linux'])

    def test_restart_output_and_exit_codes(self):
        for code,output in [(0,'Changes will not be effective until the system is rebooted.'),(3010,''),(1641,'')]:
            with self.subTest(code=code),patch.object(wsl_setup.subprocess,'run',return_value=SimpleNamespace(returncode=code,stdout=output.encode(),stderr=b'')):
                with self.assertRaises(wsl_setup.SetupPending):wsl_setup.command(['wsl.exe','--install'])
        self.assertFalse(wsl_setup.needs_restart('No restart required.'))

    def test_missing_distro_after_success_never_runs_linux_commands(self):
        with patch.object(wsl_setup.sys,'platform','win32'),patch.object(wsl_setup.sys,'getwindowsversion',return_value=SimpleNamespace(build=22631),create=True),patch.object(wsl_setup,'distributions',return_value=[]),patch.object(wsl_setup,'command') as calls:
            with self.assertRaises(wsl_setup.SetupPending):wsl_setup.prepare({'root':str(self.root)})
        self.assertEqual(len(calls.call_args_list),1)
        self.assertNotIn('--exec',calls.call_args.args[0])
        self.assertEqual(json.loads((self.root/'wsl-setup.json').read_text(encoding='utf-8'))['stage'],'distribution_pending')

    def test_restart_state_blocks_retry_only_until_next_boot(self):
        with patch.object(wsl_setup.sys,'platform','win32'),patch.object(wsl_setup.sys,'getwindowsversion',return_value=SimpleNamespace(build=22631),create=True),patch.object(wsl_setup,'distributions',return_value=[]),patch.object(wsl_setup,'command',side_effect=wsl_setup.SetupPending(wsl_setup.RESTART_MESSAGE)) as calls:
            with self.assertRaises(wsl_setup.SetupPending):wsl_setup.prepare({'root':str(self.root)})
            calls.reset_mock()
            with self.assertRaises(wsl_setup.SetupPending):wsl_setup.prepare({'root':str(self.root)})
            calls.assert_not_called()
        self.assertTrue(wsl_setup.waiting_for_restart(self.root))
        with patch.object(wsl_setup.psutil,'boot_time',return_value=wsl_setup.psutil.boot_time()+3600):
            self.assertFalse(wsl_setup.waiting_for_restart(self.root))
