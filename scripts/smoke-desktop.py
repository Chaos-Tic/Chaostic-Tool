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
