"""User consent and per-user settings around the common update service."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox
from desktop_harness import APP
from desktop.storage import Store
from desktop.window import Window


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name))
        self.window = Window(self.store)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.directory.cleanup()

    def test_automatic_checks_can_be_disabled_and_stay_disabled(self):
        self.window.update_checks_toggle.setChecked(False)
        self.assertFalse(Store(self.store.root).settings['check_updates'])
        with patch.object(self.window.update_checker, 'check') as check:
            self.window.check_updates(manual=False)
            check.assert_not_called()
            self.window.check_updates(manual=True)
            check.assert_called_once_with(manual=True)

    def test_declining_native_update_never_opens_a_terminal(self):
        self.window._on_update_result(True, '9.0.0', 'v9.0.0', 'https://github.com/Chaos-Tic/Chaostic-Tool/releases/tag/v9.0.0', False)
        with patch('core.update_service.native_commands', return_value=[['apt-get','install','--only-upgrade','chaostictool']]), patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No), patch('subprocess.Popen') as start:
            self.window.install_app_update()
            start.assert_not_called()

    def test_failed_download_is_never_opened(self):
        with patch.object(QMessageBox, 'warning') as warning, patch('desktop.window.QDesktopServices.openUrl') as open_url:
            self.window._on_installer_downloaded('', 'SHA-256 verification failed')
            warning.assert_called_once()
            open_url.assert_not_called()

    def test_declining_installer_download_has_no_side_effect(self):
        import sys
        self.window._on_update_result(True, '9.0.0', 'v9.0.0', 'https://github.com/Chaos-Tic/Chaostic-Tool/releases/tag/v9.0.0', False)
        with patch.object(sys, 'platform', 'win32'), patch.object(sys, 'frozen', True, create=True), patch('platform.machine', return_value='AMD64'), patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No), patch.object(self.window.update_download, 'start') as download:
            self.window.install_app_update()
            download.assert_not_called()

    def test_unified_release_tag_is_used_for_installer_download(self):
        import sys
        self.window._on_update_result(
            True,
            '9.0.0',
            'v9.0.0',
            'https://github.com/Chaos-Tic/Chaostic-Tool/releases/tag/v9.0.0',
            False,
        )
        with patch.object(sys, 'platform', 'win32'), patch.object(
            sys, 'frozen', True, create=True
        ), patch('platform.machine', return_value='AMD64'), patch.object(
            QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes
        ), patch.object(self.window.update_download, 'start') as download:
            self.window.install_app_update()
            download.assert_called_once_with(
                'v9.0.0', 'ChaosticTool-Setup-9.0.0-windows-x64.exe'
            )
