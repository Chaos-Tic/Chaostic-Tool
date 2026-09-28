import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import tarfile

from desktop.packages import extract_archive, download, installed, managed_command, install_package, MANIFEST, package_spec
from desktop.catalog import catalog, availability, build_arguments
from desktop.storage import parse_target

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_zip_and_tar_reject_traversal(self):
        for name in ['../escape.exe', '/absolute.exe', 'C:/escape.exe', '..\\escape.exe']:
            with self.subTest(name=name):
                archive = self.root / 'bad.zip'
                with zipfile.ZipFile(archive,'w') as z: z.writestr(name,b'unsafe')
                with self.assertRaises(ValueError): extract_archive(archive,self.root/'out')
        archive = self.root / 'bad.tar.gz'
        with tarfile.open(archive,'w:gz') as t:
            item = tarfile.TarInfo('link'); item.type = tarfile.SYMTYPE; item.linkname = '../escape'
            t.addfile(item)
        with self.assertRaises(ValueError): extract_archive(archive,self.root/'out')

    def test_download_rejects_hash_mismatch(self):
        response = io.BytesIO(b'changed release')
        response.geturl = lambda: 'https://example.test/file.zip'
        with patch('urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'SHA-256'): download('https://example.test/file.zip', self.root/'archive', '0'*64)

    def test_failed_install_never_registers_package(self):
        with patch('desktop.packages.download', side_effect=ValueError('checksum')):
            with self.assertRaises(ValueError): install_package('ffuf', self.root, log=lambda *_:None)
        self.assertIsNone(installed('ffuf', self.root))
        self.assertIsNone(managed_command('ffuf', root=self.root))

    def test_successful_install_and_broken_binary_detection(self):
        def fake_download(url,path,*_):
            with zipfile.ZipFile(path,'w') as z: z.writestr('nested/'+package_spec('ffuf')['binary'], b'fixture')
            return 'a'*64
        with patch('desktop.packages.download',side_effect=fake_download), patch('desktop.packages.probe',return_value='ffuf test'):
            record = install_package('ffuf',self.root,log=lambda *_:None)
        command = managed_command('ffuf',root=self.root)
        self.assertTrue(Path(command[0]).is_file())
        Path(command[0]).unlink()
        self.assertIsNone(managed_command('ffuf',root=self.root))

    def test_no_service_is_counted_ready_for_amass(self):
        tool = next(t for t in catalog() if t['key']=='amass')
        self.assertFalse(availability(tool,{},self.root)[1])
        with patch('desktop.catalog.native_command',return_value=['amass']):
            self.assertEqual(availability(tool,{},self.root), ('Service requis',False))

    def test_all_portable_archives_have_pinned_hashes(self):
        for spec in MANIFEST.values():
            if spec['kind'] in ('release','file','installer'):
                for artifact in spec.get('artifacts',{'default':spec}).values():
                    self.assertRegex(artifact['sha256'],r'^[0-9a-f]{64}$')
                    self.assertTrue(artifact['url'].startswith('https://'))
                    self.assertNotIn('/latest/',artifact['url'])

    def test_custom_fields_reject_options_and_invalid_ranges(self):
        tools = {t['key']:t for t in catalog()}
        target = parse_target('127.0.0.1')
        for bad in ['-oN stolen', '0', '65536', '80-22', '80,,443', '22;calc']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_arguments(tools['nmap'],2,target,fields={'ports':bad})
        args = build_arguments(tools['nmap'],2,target,fields={'ports':'22,80,8000-8100'})
        self.assertIn('22,80,8000-8100',args)
        with self.assertRaises(ValueError): build_arguments(tools['katana'],2,target,fields={'depth':'11'})

    def test_install_worker_reports_failure_without_blocking_gui(self):
        from test_desktop import APP, wait_run
        from desktop.process import Runner
        from desktop.storage import Store
        store = Store(self.root / 'worker')
        runner = Runner(store)
        result = wait_run(runner, lambda: runner.start('Install','invalid',{'packages':['unknown'],'root':str(store.root)},worker='install'))
        self.assertEqual(result['status'],'failed')
        self.assertIn('Liste d’outils invalide', (Path(result['directory'])/'output.txt').read_text(encoding='utf-8'))
