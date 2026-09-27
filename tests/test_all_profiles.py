import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from core.tools import TOOLS
from desktop.catalog import catalog,build_arguments
from desktop.profiles import StreamRedactor,redact,secrets_for
from desktop.backends import bridge_command,save_config,linux_status,install_plan
from desktop.storage import Store,parse_target,write_json

class AllProfilesTests(unittest.TestCase):
    def test_every_original_tool_has_an_executable_profile(self):
        items={t['key']:t for t in catalog()}
        self.assertTrue(set(TOOLS)<=set(items))
        self.assertEqual(len(items),52)
        for key in TOOLS:
            with self.subTest(key=key):
                self.assertNotEqual(items[key]['mode'],'unavailable')
                self.assertTrue(items[key]['presets'])
                for p in items[key]['presets']+items[key].get('linux_presets',[]):
                    self.assertTrue(p.get('worker') or 'args' in p)

    def test_all_forms_build_argument_vectors(self):
        with tempfile.TemporaryDirectory() as temp:
            input_file=Path(temp)/'entrée avec espaces.txt'; input_file.write_text('test')
            defaults={'domain':'EXAMPLE','user':'alice','passwd':'p@ss secret','cookie':'session=secret','api_key':'apikey','size':'123','depth':'2','ports':'22,80','hashfile':str(input_file),'userfile':str(input_file),'capfile':str(input_file),'wordlist':str(input_file),'mask':'?l?l?d','fmt':'raw-md5','iface':'eth0','bssid':'00:11:22:33:44:55','channel':'6','lhost':'127.0.0.1','lport':'4444','outfile':'result.bin','pcap':'capture.pcap','pfilter':'80','target':'127.0.0.1','target1':'127.0.0.1','target2':'127.0.0.2','form':'/login:u=^USER^&p=^PASS^:F=wrong','callback':'https://example.test/callback','sources':'crtsh','engine':'http://127.0.0.1:4000','nameserver':'127.0.0.1'}
            for tool in catalog():
                for p in tool['presets']+tool.get('linux_presets',[]):
                    with self.subTest(tool=tool['key'],profile=p['label']):
                        fields={k:defaults.get(k,default or 'test') for k,(_,default) in p.get('fields',{}).items()}
                        args=build_arguments(tool,0,parse_target('https://example.test:8443/path'),str(input_file),fields,preset=p)
                        self.assertTrue(all(isinstance(a,str) for a in args))
                        self.assertNotIn('{host}',args)
                        text=redact(' '.join(args),secrets_for(p,fields))
                        for secret in secrets_for(p,fields): self.assertNotIn(secret,text)

    def test_secrets_split_across_output_chunks(self):
        secret='super-secret-value'
        for split in range(len(secret)+1):
            r=StreamRedactor([secret])
            output=r.feed(('before '+secret[:split]).encode())+r.feed((secret[split:]+' after').encode())+r.feed(b'',final=True)
            self.assertEqual(output,b'before [masque] after')

    def test_changed_linux_config_invalidates_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); save_config({'backend':'ssh','host':'old','user':'alice'},root)
            config=json.loads((root/'linux.json').read_text())
            write_json(root/'linux-status.json',{'config':config,'tools':{'nmap':'/usr/bin/nmap'}})
            self.assertIn('nmap',linux_status(root)['tools'])
            save_config({'backend':'ssh','host':'new','user':'alice'},root)
            self.assertEqual(linux_status(root),{})

    def test_ssh_option_injection_is_rejected(self):
        for host in ['-oProxyCommand=bad','host;touch /tmp/pwn','host\nInjected']:
            with self.assertRaises(ValueError): bridge_command({'backend':'ssh','host':host,'user':'alice'})

    def test_sensitive_command_not_saved(self):
        from test_desktop import wait_run
        from desktop.process import Runner
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)); runner=Runner(store); secret='unique-private-secret'
            command=[sys.executable,'-u','-c',"import sys,time; s=sys.argv[1]; print(s[:6],end='',flush=True); time.sleep(.1); print(s[6:],flush=True)",secret]
            result=wait_run(runner,lambda:runner.start('Secret','Test',None,command=command,redactions=[secret]))
            self.assertEqual(result['status'],'success')
            for name in ['run.json','output.txt']:
                self.assertNotIn(secret,(Path(result['directory'])/name).read_text(encoding='utf-8'))

    def test_local_profile_does_not_require_network_target(self):
        tool=next(t for t in catalog() if t['key']=='hashcat')
        self.assertFalse(tool['presets'][0]['needs_target'])

    def test_linux_install_plan_uses_fixed_package_names(self):
        with self.assertRaises(ValueError): install_plan(['evil;command'])
        command=install_plan(['nmap','tcpdump'])
        self.assertEqual(command[-2:],['nmap','tcpdump'])
