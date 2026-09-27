"""Check the packaged app with a disposable user profile."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
if sys.platform == 'win32': executable = root/'dist/ChaosticTool/ChaosticTool.exe'
elif sys.platform == 'darwin': executable = root/'dist/ChaosticTool.app/Contents/MacOS/ChaosticTool'
else: executable = root/'dist/ChaosticTool/ChaosticTool'
with tempfile.TemporaryDirectory() as directory:
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', CHAOSTIC_DESKTOP_HOME=directory)
    subprocess.run([str(executable), '--smoke-test'], env=env, timeout=90, check=True)
    result = json.loads((Path(directory)/'smoke-result.json').read_text(encoding='utf-8'))
    assert result['status'] == 'success', result
    print(result)
    if os.name != 'nt':
        # The frozen entry point must route bridge jobs before loading Qt.
        inventory = subprocess.run([str(executable), '--linux-bridge'],
            input=json.dumps({'op':'inventory','tools':{'python':[sys.executable]}})+'\n',
            capture_output=True, text=True, timeout=20, check=True, env=env)
        assert json.loads(inventory.stdout)['tools']['python'], inventory
        bridge = subprocess.Popen([str(executable), '--linux-bridge'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        request = {'op':'run','argv':[sys.executable,'-u','-c',"import os; print('FROZEN_TTY='+str(os.isatty(0)),flush=True)"], 'cwd':directory}
        bridge.stdin.write((json.dumps(request)+'\n').encode()); bridge.stdin.flush()
        try:
            bridge.wait(timeout=20)
            assert bridge.returncode == 0, bridge.stderr.read()
            assert b'FROZEN_TTY=True' in bridge.stdout.read()
        finally:
            if bridge.poll() is None: bridge.kill(); bridge.wait()
            bridge.stdin.close(); bridge.stdout.close(); bridge.stderr.close()
