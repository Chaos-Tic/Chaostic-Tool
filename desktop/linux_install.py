"""Kali/Debian package installation, launched inside the Linux PTY as root."""
import os
import re
import shutil
import subprocess
import sys

def main():
    if not shutil.which('apt-get'): raise RuntimeError('Installation automatique disponible pour Kali/Debian/Ubuntu. Installez les outils avec le gestionnaire de cette distribution, puis actualisez l’inventaire.')
    packages=sys.argv[1:]
    if not packages or any(not re.fullmatch(r'[a-z0-9.+-]+',p) for p in packages): raise ValueError('Invalid package list')
    env=dict(os.environ,DEBIAN_FRONTEND='noninteractive')
    subprocess.run(['apt-get','update'],check=True,env=env)
    available=[]; missing=[]
    for package in packages:
        check=subprocess.run(['apt-cache','show',package],capture_output=True)
        (available if check.returncode==0 and b'Package:' in check.stdout else missing).append(package)
    if available: subprocess.run(['apt-get','install','-y',*available],check=True,env=env)
    if missing:
        print('Paquets absents des dépôts de cette distribution : '+', '.join(missing),flush=True)
        return 2
    print('Installation Linux terminée. Actualisez l’inventaire des outils.',flush=True)
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except Exception as exc:
        print(str(exc),flush=True)
        sys.exit(1)
