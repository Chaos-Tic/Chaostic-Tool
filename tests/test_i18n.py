"""Regression tests for translated validation and desktop file dialogs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop.catalog import build_arguments
from desktop.i18n import language, set_language
from desktop.profiles import redact, validate_field
from desktop.storage import Store


class DesktopTranslationTests(unittest.TestCase):
    def setUp(self):
        self.previous_language = language()

    def tearDown(self):
        set_language(self.previous_language)

    def test_validation_errors_use_active_language_and_preserve_values(self):
        cases = [
            ('passwd', '', 'native',
             'Mot de passe : valeur requise, sans caractère de contrôle.',
             'Password: a value is required, without control characters.'),
            ('domain', '-option', 'native',
             'Une valeur ne peut pas commencer par une option (-).',
             'A value cannot start with an option (-).'),
            ('hashfile', 'relative.txt', 'ssh',
             'Indiquez un chemin Linux absolu sur la machine SSH.',
             'Provide an absolute Linux path on the SSH machine.'),
            ('outfile', '../result.bin', 'native',
             'Choisissez un simple nom de fichier ; la sortie sera dans le dossier de cette opération.',
             'Choose a plain filename; output will be saved in this operation’s folder.'),
            ('user', 'bad user', 'native',
             'Utilisateur : caractères non autorisés.', 'User: invalid characters.'),
            ('lport', '65536', 'native',
             'Port de retour : valeur numérique invalide.', 'Callback port: invalid numeric value.'),
            ('bssid', '00:bad', 'native', 'BSSID invalide.', 'Invalid BSSID.'),
            ('target', 'bad-ip', 'native', 'Adresse IP invalide : bad-ip', 'Invalid IP address: bad-ip'),
        ]
        for lang in ('fr', 'en'):
            set_language(lang)
            for name, value, backend, french, english in cases:
                with self.subTest(language=lang, field=name), self.assertRaises(ValueError) as error:
                    validate_field(name, value, backend)
                self.assertEqual(str(error.exception), french if lang == 'fr' else english)
            with tempfile.TemporaryDirectory() as temp:
                missing = str(Path(temp) / 'fichier inexistant.txt')
                with self.assertRaises(ValueError) as error:
                    validate_field('hashfile', missing)
                prefix = 'Fichier introuvable : ' if lang == 'fr' else 'File not found: '
                self.assertEqual(str(error.exception), prefix + missing)
            self.assertEqual(validate_field('passwd', ' secret '), ' secret ')
            self.assertEqual(redact('token=secret', ['secret']), 'token=[redacted]')

    def test_catalog_validation_uses_active_language(self):
        tool = {'key': 'fixture'}
        cases = [
            ({'needs_target': True, 'args': []}, None, {},
             'Choisissez une cible.', 'Choose a target.'),
            ({'needs_target': True, 'domain_only': True, 'args': []}, {'host': '127.0.0.1'}, {},
             'Ce profil attend un nom de domaine, pas une adresse IP.',
             'This profile requires a domain name, not an IP address.'),
            ({'needs_target': False, 'args': [], 'fields': {'ports': ('Ports', '')}}, None, {'ports': 'bad'},
             'Liste de ports invalide.', 'Invalid port list.'),
            ({'needs_target': False, 'args': [], 'fields': {'ports': ('Ports', '')}}, None, {'ports': '80-22'},
             'Plage de ports invalide.', 'Invalid port range.'),
        ]
        for lang in ('fr', 'en'):
            set_language(lang)
            for preset, target, fields, french, english in cases:
                with self.subTest(language=lang, error=english), self.assertRaises(ValueError) as error:
                    build_arguments(tool, 0, target, fields=fields, preset=preset)
                self.assertEqual(str(error.exception), french if lang == 'fr' else english)

    def test_launch_preview_field_labels_and_cancel_are_translated(self):
        from desktop_harness import APP
        from PySide6.QtWidgets import QDialogButtonBox
        from desktop.launch_dialog import LaunchDialog
        tool = dict(key='fixture', name='DNS avancé', desc='', mode='builtin', category='osint',
                    presets=[dict(label='Profil', needs_target=False, args=['{domain}'],
                                  fields={'domain': ('Domaine', '')})])
        for lang in ('fr', 'en'):
            with self.subTest(language=lang), tempfile.TemporaryDirectory() as temp:
                set_language(lang)
                dialog = LaunchDialog(tool, Store(Path(temp)))
                try:
                    self.assertEqual(dialog.windowTitle(), 'Configurer DNS avancé' if lang == 'fr' else 'Configure Advanced DNS')
                    self.assertEqual(dialog.extra_form.labelForField(dialog.extra_fields['domain']).text(),
                                     'Domaine' if lang == 'fr' else 'Domain')
                    self.assertEqual(dialog.preview.text(),
                                     'Domaine : valeur requise, sans caractère de contrôle.' if lang == 'fr'
                                     else 'Domain: a value is required, without control characters.')
                    actions = dialog.findChild(QDialogButtonBox)
                    self.assertEqual(actions.button(QDialogButtonBox.StandardButton.Cancel).text(),
                                     'Annuler' if lang == 'fr' else 'Cancel')
                    dialog.extra_fields['domain'].setText('example.test')
                    self.assertIn('example.test', dialog.preview.text())
                finally:
                    dialog.close()
                    dialog.deleteLater()
                    APP.processEvents()

    def test_real_catalog_profile_and_optional_field_are_translated(self):
        from desktop_harness import APP
        from desktop.catalog import catalog
        from desktop.launch_dialog import LaunchDialog
        tool = next(item for item in catalog() if item['key'] == 'dig')
        for lang in ('fr', 'en'):
            with self.subTest(language=lang), tempfile.TemporaryDirectory() as temp:
                set_language(lang)
                store = Store(Path(temp))
                store.add_target('https://example.test')
                dialog = LaunchDialog(tool, store)
                try:
                    dialog.backend.setCurrentIndex(dialog.backend.findData('builtin'))
                    self.assertEqual(dialog.profiles.itemText(0),
                                     'Enregistrements A' if lang == 'fr' else 'A records')
                    self.assertEqual(dialog.extra_form.labelForField(dialog.extra_fields['nameserver']).text(),
                                     'Serveur DNS (facultatif)' if lang == 'fr' else 'DNS server (optional)')
                    self.assertEqual(dialog.preview.text(), 'dig')
                finally:
                    dialog.close()
                    dialog.deleteLater()
                    APP.processEvents()

    def test_window_file_dialogs_and_installation_errors_are_translated(self):
        from desktop_harness import APP
        from desktop.packages import MANIFEST
        from desktop.window import Window
        package = next(key for key, spec in MANIFEST.items() if spec['kind'] != 'installer')
        for lang in ('fr', 'en'):
            with self.subTest(language=lang), tempfile.TemporaryDirectory() as temp:
                store = Store(Path(temp))
                store.settings.update(language=lang, animations=False, check_updates=False)
                window = Window(store)
                try:
                    tool = dict(key='fixture', name='DNS avancé', mode='native')
                    with patch.object(window, 'selected_tool', return_value=tool), \
                         patch('desktop.window.QFileDialog.getOpenFileName', return_value=('/missing', '')) as choose, \
                         patch('desktop.window.find_executable', return_value=None), \
                         patch('desktop.window.QMessageBox.warning') as warning:
                        window.configure_executable()
                        self.assertEqual(choose.call_args.args[1],
                                         'Sélectionner DNS avancé' if lang == 'fr' else 'Select Advanced DNS')
                        self.assertEqual(choose.call_args.args[3],
                                         'Programmes et scripts (*)' if lang == 'fr' else 'Programs and scripts (*)')
                        self.assertEqual(warning.call_args.args[1:],
                                         ('Fichier invalide', 'Choisissez un programme ou script Python existant pour cet ordinateur.') if lang == 'fr'
                                         else ('Invalid file', 'Choose an existing program or Python script for this computer.'))
                    with patch('desktop.window.QFileDialog.getOpenFileName', return_value=('', '')) as choose:
                        window.configure_python()
                        self.assertEqual(choose.call_args.args[1],
                                         'Sélectionner Python 3.14 ou ultérieur' if lang == 'fr' else 'Select Python 3.14 or later')
                    with patch('desktop.window.find_python', return_value=None), \
                         patch.object(window.runner, 'start', side_effect=RuntimeError('fixture failure')), \
                         patch('desktop.window.QMessageBox.warning') as warning:
                        window.install_tools([package])
                        self.assertEqual(warning.call_args.args[1:],
                                         ('Installation impossible' if lang == 'fr' else 'Installation failed', 'fixture failure'))
                finally:
                    window.close()
                    window.deleteLater()
                    APP.processEvents()
