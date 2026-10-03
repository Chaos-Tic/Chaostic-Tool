"""Check the packaged app with a disposable user profile."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
if sys.platform == 'win32': executable = root/'dist/ChaosticTool/ChaosticTool.exe'
elif sys.platform == 'darwin': executable = root/'dist/ChaosticTool.app/Contents/MacOS/ChaosticTool'
else: executable = root/'dist/ChaosticTool/ChaosticTool'
if sys.platform == 'win32':
    # Inspect the real PE resources, not only the icon files in the source tree.
    import struct
    import pefile
    ico = (root/'desktop/assets/icon.ico').read_bytes()
    expected = set()
    for index in range(struct.unpack_from('<H', ico, 4)[0]):
        length, offset = struct.unpack_from('<II', ico, 6 + index*16 + 8)
        expected.add(ico[offset:offset+length])
    installers = list((root/'release').glob('ChaosticTool-Setup-*.exe'))
    from desktop import VERSION
    installers = [path for path in installers if f'-{VERSION}-' in path.name]
    assert installers, 'Current installer is missing from release/'
    for binary in [executable, *installers]:
        with pefile.PE(str(binary)) as pe:
            icons = {pe.get_data(language.data.struct.OffsetToData, language.data.struct.Size)
                     for kind in pe.DIRECTORY_ENTRY_RESOURCE.entries if kind.id == 3
                     for entry in kind.directory.entries for language in entry.directory.entries}
        assert expected <= icons, f'Stale or missing Red Ops icon in {binary.name}'

with tempfile.TemporaryDirectory() as directory:
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', CHAOSTIC_DESKTOP_HOME=directory)
    subprocess.run([str(executable), '--smoke-test'], env=env, timeout=90, check=True)
    from PySide6.QtGui import QImage
    expected_icon = QImage(str(root/'desktop/assets/icon.png')).convertToFormat(QImage.Format.Format_ARGB32)
    actual_icon = QImage(str(Path(directory)/'smoke-icon.png')).convertToFormat(QImage.Format.Format_ARGB32)
    assert not actual_icon.isNull() and actual_icon == expected_icon, 'Window icon differs from packaged branding'
    initial=json.loads((Path(directory)/'smoke-initial-state.json').read_text(encoding='utf-8'))
    assert initial=={'history':0,'targets':0,'configured_linux':False},initial
    assert len(list((Path(directory)/'runs').glob('*/run.json')))==1, 'Unexpected seeded run history'
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
