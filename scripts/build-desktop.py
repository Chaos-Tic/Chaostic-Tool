"""Build a self-contained desktop bundle on its destination OS."""
from pathlib import Path
import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop import VERSION

def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iscc', default=os.environ.get('ISCC_PATH', ''))
    parser.add_argument('--skip-tests', action='store_true')
    args = parser.parse_args()
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    if not args.skip_tests:
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v')
    run(sys.executable, 'scripts/make-icon.py')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', 'packaging/ChaosticTool.spec')
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    arch = {'amd64':'x64', 'x86_64':'x64', 'aarch64':'arm64', 'arm64':'arm64'}[platform.machine().lower()]
    system = platform.system().lower()
    if system == 'windows':
        compiler = args.iscc or shutil.which('ISCC.exe')
        if not compiler:
            raise SystemExit('Application built in dist. Pass --iscc with an Inno Setup 6 compiler to build the installer.')
        run(compiler, '/DAppVersion=' + VERSION, '/DAppArch=' + arch, 'packaging/windows/installer.iss')
        artifact = release / f'ChaosticTool-Setup-{VERSION}-windows-{arch}.exe'
    elif system == 'darwin':
        staging = ROOT / 'build/dmg'
        staging.mkdir(parents=True, exist_ok=True)
        app = staging / 'ChaosticTool.app'
        if app.exists(): shutil.rmtree(app)
        shutil.copytree(ROOT / 'dist/ChaosticTool.app', app, symlinks=True)
        link = staging / 'Applications'
        if not link.exists(): link.symlink_to('/Applications', target_is_directory=True)
        artifact = release / f'ChaosticTool-{VERSION}-macos-{arch}.dmg'
        for attempt in range(3):
            try:
                run('hdiutil', 'create', '-volname', 'ChaosticTool', '-srcfolder', staging, '-ov', '-format', 'UDZO', artifact)
                break
            except subprocess.CalledProcessError:
                if attempt==2: raise
                time.sleep(5)
    elif system == 'linux':
        bundle = ROOT / 'dist/ChaosticTool'
        for name in ('install.sh', 'uninstall.sh'):
            shutil.copy2(ROOT / 'packaging/linux' / name, bundle / name)
            (bundle / name).chmod(0o755)
        artifact = release / f'ChaosticTool-{VERSION}-linux-{arch}.tar.gz'
        with tarfile.open(artifact, 'w:gz') as archive:
            archive.add(bundle, arcname='ChaosticTool')
    else:
        raise SystemExit('Supported build hosts: Windows, Linux, macOS.')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (release / (artifact.name + '.sha256')).write_text(f'{digest}  {artifact.name}\n', encoding='ascii')
    print(artifact)

if __name__ == '__main__': main()
