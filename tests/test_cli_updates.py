import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from core import cli_updates
from core import ui


@unittest.skipIf(os.name == 'nt', 'CLI updates require POSIX; run on Linux')
class CliUpdateTests(unittest.TestCase):
    def test_declining_updates_does_not_execute_package_commands(self):
        with patch.object(cli_updates.update_service, 'native_commands', return_value=[['apt-get','update'],['apt-get','install','--only-upgrade','chaostictool']]), patch.object(ui.console, 'input', return_value='n'), patch.object(ui.console, 'print'), patch.object(cli_updates.subprocess, 'run') as run:
            self.assertFalse(cli_updates.install({'available': True, 'version': '9.0.0'}))
            run.assert_not_called()

    def test_repository_lag_is_not_reported_as_a_successful_update(self):
        with patch.object(cli_updates.update_service, 'native_commands', return_value=[['apt-get','update']]), patch.object(cli_updates.update_service, 'installed_version', return_value='1.4.0'), patch.object(ui.console, 'input', return_value='y'), patch.object(ui.console, 'print') as output, patch.object(cli_updates.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertFalse(cli_updates.install({'available': True, 'version': '1.5.0'}))
            self.assertIn('repository does not yet offer', output.call_args.args[0])

    def test_saved_automatic_check_preference(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cli_updates, 'data_home', return_value=Path(directory)), patch.dict('os.environ', {'CHAOSTIC_UPDATE_CHECK':'1'}):
            self.assertTrue(cli_updates.enabled())
            (Path(directory)/'cli-settings.json').write_text('{"check_updates":false}')
            self.assertFalse(cli_updates.enabled())
