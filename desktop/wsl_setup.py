"""Resumable WSL provisioning. Commands are fixed vectors, never user shell input."""
import os
import subprocess
import sys
from pathlib import Path
from desktop.backends import NO_WINDOW, decode_wsl, distributions, save_config, get_config, inspect_backend
from desktop.storage import write_json, now

DISTRO = 'kali-linux'
USER = 'chaostic-tool'

def command(args, timeout=1800):
    result = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    output = decode_wsl(result.stdout + result.stderr)
    if output:
        print(output, flush=True)
    if result.returncode in (3010,1641):
        raise RuntimeError('Windows demande un redémarrage. Redémarrez manuellement, puis relancez ChaosticTool pour reprendre.')
    if result.returncode:
        raise RuntimeError(f'Commande interrompue (code {result.returncode}). Consultez le journal, puis reprenez la préparation.')
    return output

def linux(args, root=False):
    return ['wsl.exe', '--distribution', DISTRO, '--user', 'root' if root else USER, '--exec', *args]

def prepare(request):
    if sys.platform != 'win32':
        raise ValueError('Cette préparation nécessite Windows.')
    if sys.getwindowsversion().build < 19041:
        raise ValueError('La préparation automatique nécessite Windows 10 version 2004 (build 19041) ou Windows 11.')
    root = Path(request['root'])
    state_path = root / 'wsl-setup.json'
    def state(stage, error=None):
        write_json(state_path, {'stage': stage, 'checked': now(), 'error': error})
        print(stage, flush=True)
    try:
        state('Détection de WSL')
        try:
            installed = distributions()
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            installed = None
        if installed is None:
            state('Activation de WSL — validation administrateur Windows')
            # Only machine features are elevated. Distro registration stays in
            # the original Windows account, even with alternate UAC credentials.
            script = "$ErrorActionPreference='Stop'; $p=Start-Process -FilePath ($env:SystemRoot+'\\System32\\wsl.exe') -ArgumentList '--install','--no-distribution','--web-download' -Verb RunAs -WindowStyle Hidden -PassThru -Wait; exit $p.ExitCode"
            command(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script])
            try:
                installed = distributions()
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                raise RuntimeError('WSL ne répond pas encore. Redémarrez Windows, puis relancez ChaosticTool pour reprendre. Vérifiez aussi la virtualisation si Windows le demande.')
        if DISTRO.casefold() not in [name.casefold() for name in installed]:
            state('Téléchargement de Kali Linux')
            command(['wsl.exe', '--install', '--distribution', DISTRO, '--no-launch', '--web-download'])
        state('Préparation de Python et du compte Linux')
        command(linux(['true'], root=True), timeout=60)
        command(linux(['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'update'], root=True))
        command(linux(['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', 'python3', 'ca-certificates'], root=True))
        # A locked-password account: no shared secret and no passwordless sudo.
        command(linux(['sh', '-c', 'id -u chaostic-tool >/dev/null 2>&1 || useradd --create-home --shell /bin/bash chaostic-tool'], root=True))
        uid = command(linux(['id', '-u']), timeout=30).strip()
        if not uid.isdigit() or uid == '0':
            raise RuntimeError('Le compte Linux applicatif doit être un compte non administrateur.')
        if request.get('tools'):
            state('Installation de Nmap, RustScan et des utilitaires réseau')
            command(linux(['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', 'nmap', 'rustscan', 'dnsutils', 'whois'], root=True))
        state('Connexion et inventaire')
        previous = get_config(root)
        save_config({'backend': 'wsl', 'distro': DISTRO, 'wsl_user': USER}, root)
        try:
            inspect_backend({'root': str(root)})
        except Exception:
            save_config(previous, root)
            raise
        state('ready')
        print('Environnement prêt. Le catalogue indique les outils réellement disponibles.', flush=True)
    except Exception as exc:
        state('À reprendre', str(exc))
        raise

def offer(window):
    """One consent covering downloads, OS activation and distro provisioning."""
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox
    dialog = QDialog(window)
    dialog.setWindowTitle('Préparer mon environnement Linux')
    dialog.setMinimumWidth(540)
    box = QVBoxLayout(dialog)
    text = QLabel('ChaosticTool va installer WSL si nécessaire, télécharger Kali Linux, préparer Python et connecter le catalogue automatiquement.\n\nUne connexion Internet, plusieurs Go libres et parfois un redémarrage sont nécessaires. Windows peut afficher une demande administrateur.\n\nSi Kali est déjà présent, Python et les paquets choisis pourront être mis à jour et un compte applicatif non administrateur sera ajouté. Les autres distributions et la distribution par défaut restent inchangées. WSL et Kali seront conservés si vous désinstallez ChaosticTool.')
    text.setWordWrap(True)
    box.addWidget(text)
    tools = QCheckBox('Installer aussi Nmap, RustScan, DNS et Whois')
    tools.setChecked(True)
    box.addWidget(tools)
    actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    actions.button(QDialogButtonBox.StandardButton.Ok).setText('Préparer automatiquement')
    actions.button(QDialogButtonBox.StandardButton.Cancel).setText('Plus tard')
    actions.accepted.connect(dialog.accept); actions.rejected.connect(dialog.reject)
    box.addWidget(actions)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        window.console.clear(); window.terminal_screen=None; window.input_row.hide()
        window.run_title.setText('Préparation automatique de Linux')
        window.runner.start('Linux', 'Préparation WSL', {'root':str(window.store.root), 'tools':tools.isChecked(), 'label':'Cet ordinateur'}, worker='wsl-setup', timeout_ms=3_600_000)
        window.navigate(3)
