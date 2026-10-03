"""Linux desktop execution without privileged commands or external targets."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop.backends import execution_plan, save_config
from desktop.catalog import availability, catalog, native_command
from desktop.storage import Store


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux desktop execution')
class LinuxDesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))

    def test_native_local_bridge_does_not_use_configured_ssh(self):
        save_config({'backend': 'ssh', 'host': 'remote.test', 'user': 'alice'}, self.store.root)
        argv = [sys.executable, '-c', "print('local')"]
        command, request = execution_plan(argv, {'requires_root': True}, self.store.root,
                                          self.store.root, local=True)
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(request['argv'], argv)
        self.assertEqual(request['cwd'], str(self.store.root))
        self.assertTrue(request['elevate'])

    def test_native_interactive_process_receives_a_real_terminal(self):
        from test_desktop import wait_run
        from desktop.process import Runner
        save_config({'backend': 'ssh', 'host': 'remote.test', 'user': 'alice'}, self.store.root)
        runner = Runner(self.store)
        result = wait_run(runner, lambda: runner.start(
            'Local helper', 'Terminal', None,
            command=[sys.executable, '-c', "import os; print('TTY='+str(os.isatty(0)))"],
            bridge=True, local_bridge=True))
        self.assertEqual(result['status'], 'success', result)
        output = (Path(result['directory']) / 'output.txt').read_text()
        self.assertIn('TTY=True', output)

    def test_native_profiles_route_privileges_and_interaction_locally(self):
        from test_desktop import APP
        from desktop.window import Window
        window = Window(self.store)
        try:
            for interactive, privileged in ((True, False), (False, True), (False, False)):
                with self.subTest(interactive=interactive, privileged=privileged):
                    tool = dict(key='local-helper', name='Local helper', mode='native',
                                binary=sys.executable, category='local', desc='Local diagnostic',
                                linux_presets=[], presets=[dict(label='Local', args=['-c', 'pass'],
                                needs_target=False, interactive=interactive, requires_root=privileged)])
                    with patch.object(window.runner, 'start') as start:
                        self.assertTrue(window.launch('local-helper', show_dialog=False, tool_override=tool))
                    kwargs = start.call_args.kwargs
                    self.assertEqual(kwargs.get('bridge', False), interactive or privileged)
                    self.assertEqual(kwargs.get('local_bridge', False), interactive or privileged)
                    self.assertEqual(kwargs.get('elevate', False), privileged)
        finally:
            window.close()
            window.deleteLater()
            APP.processEvents()

    def test_imported_native_profiles_preserve_root_requirements(self):
        from core.tools import TOOLS
        for tool in catalog():
            if tool['mode'] != 'native':
                continue
            for preset in tool['presets']:
                if preset.get('cli_index') is not None:
                    original = TOOLS[tool['key']]['presets'][preset['cli_index']]
                    with self.subTest(tool=tool['key'], profile=preset['label']):
                        self.assertEqual(bool(preset.get('requires_root')),
                                         bool(original.get('requires_root', TOOLS[tool['key']].get('requires_root'))))

    def test_winpeas_cannot_run_as_a_local_linux_tool(self):
        tool = next(t for t in catalog() if t['key'] == 'winpeas')
        self.assertEqual(availability(tool, {}, self.store.root), ('Windows uniquement', False))
        self.assertIsNone(native_command(tool, configured=sys.executable, root=self.store.root))
