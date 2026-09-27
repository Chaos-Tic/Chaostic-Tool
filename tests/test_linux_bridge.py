import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path

BRIDGE=Path(__file__).resolve().parents[1]/'desktop/linux_bridge.py'

@unittest.skipIf(os.name=='nt','POSIX bridge is validated on Linux/macOS runners')
class LinuxBridgeTests(unittest.TestCase):
    def start(self,request):
        process=subprocess.Popen([sys.executable,'-u',str(BRIDGE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        process.stdin.write((json.dumps(request)+'\n').encode()); process.stdin.flush()
        self.addCleanup(lambda: self.cleanup(process))
        return process
    def cleanup(self,p):
        if p.poll() is None: p.terminate(); p.wait(timeout=5)
        p.stdin.close(); p.stdout.close()
    def test_inventory(self):
        p=self.start({'op':'inventory','tools':{'python':[sys.executable],'missing':['chaostic-does-not-exist']}})
        result=json.loads(p.stdout.readline())
        self.assertIn('python',result['tools']); self.assertNotIn('missing',result['tools'])
        self.assertEqual(p.wait(timeout=5),0)
    def test_inventory_rejects_wrong_program_with_same_name(self):
        with tempfile.TemporaryDirectory() as temp:
            wrong=Path(temp)/'httpx'
            wrong.write_text('#!/bin/sh\necho "Python HTTP client"\n')
            wrong.chmod(0o755)
            p=self.start({'op':'inventory','tools':{'httpx':[str(wrong)]},'markers':{'httpx':['projectdiscovery','-tech-detect']}})
            self.assertEqual(json.loads(p.stdout.readline())['tools'],{})
            self.assertEqual(p.wait(timeout=5),0)
    def test_interactive_input_and_real_tty(self):
        with tempfile.TemporaryDirectory() as temp:
            code="import os; print('TTY='+str(os.isatty(0)),flush=True); answer=input(); print('ANSWER='+answer,flush=True)"
            p=self.start({'op':'run','argv':[sys.executable,'-u','-c',code],'cwd':temp})
            self.assertIn(b'TTY=True',p.stdout.readline())
            p.stdin.write((json.dumps({'op':'input','text':'hello world\n'})+'\n').encode()); p.stdin.flush()
            p.wait(timeout=10)
            self.assertIn(b'ANSWER=hello world',p.stdout.read())
            self.assertEqual(p.returncode,0)
    def test_disconnect_terminates_linux_group(self):
        with tempfile.TemporaryDirectory() as temp:
            code="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)"
            p=self.start({'op':'run','argv':[sys.executable,'-u','-c',code],'cwd':temp})
            child=int(p.stdout.readline().strip()); p.stdin.close()
            self.assertEqual(p.wait(timeout=10),130)
            import psutil
            deadline=time.monotonic()+3
            while psutil.pid_exists(child) and psutil.Process(child).status()!=psutil.STATUS_ZOMBIE and time.monotonic()<deadline: time.sleep(.05)
            self.assertTrue(not psutil.pid_exists(child) or psutil.Process(child).status()==psutil.STATUS_ZOMBIE)
    def test_shell_metacharacters_remain_literal_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            value='literal; echo NEVER $(touch pwn)'
            p=self.start({'op':'run','argv':[sys.executable,'-u','-c','import sys; print(sys.argv[1],flush=True)',value],'cwd':temp})
            self.assertIn(value.encode(),p.stdout.readline()); self.assertEqual(p.wait(timeout=5),0)
            self.assertFalse((Path(temp)/'pwn').exists())
