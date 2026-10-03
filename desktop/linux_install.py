"""Explicit distro packages; standalone source sent to the Linux bridge.

Use only the standard library: SSH targets and frozen apps cannot import the
project here. Unmapped tools require manual installation, without extra repos.
"""
import os
import re
import shutil
import subprocess
import sys

KALI_PACKAGES = {
    'whois': 'whois', 'dig': 'dnsutils', 'subfinder': 'subfinder',
    'amass': 'amass', 'dnsrecon': 'dnsrecon', 'theharvester': 'theharvester',
    'shodan': 'python3-shodan', 'nmap': 'nmap', 'rustscan': 'rustscan',
    'masscan': 'masscan', 'naabu': 'naabu', 'gobuster': 'gobuster',
    'ffuf': 'ffuf', 'httpx': 'httpx-toolkit', 'wafw00f': 'wafw00f',
    'whatweb': 'whatweb', 'katana': 'katana', 'gau': 'getallurls',
    'waybackurls': 'waybackurls', 'nikto': 'nikto', 'nuclei': 'nuclei',
    'wpscan': 'wpscan', 'testssl.sh': 'testssl.sh', 'sslscan': 'sslscan',
    'sqlmap': 'sqlmap', 'xsstrike': 'xsstrike', 'dalfox': 'dalfox',
    'msfconsole': 'metasploit-framework', 'msfvenom': 'metasploit-framework',
    'linpeas.sh': 'peass', 'secretsdump.py': 'impacket-scripts',
    'psexec.py': 'impacket-scripts', 'GetUserSPNs.py': 'impacket-scripts',
    'crackmapexec': 'netexec', 'bloodhound-python': 'bloodhound.py',
    'hashcat': 'hashcat', 'john': 'john', 'hydra': 'hydra',
    'airmon-ng': 'aircrack-ng', 'airodump-ng': 'aircrack-ng',
    'aircrack-ng': 'aircrack-ng', 'reaver': 'reaver', 'wifite': 'wifite',
    'bettercap': 'bettercap', 'ettercap': 'ettercap-text-only',
    'tcpdump': 'tcpdump', 'responder': 'responder',
}

# Official-package names mirrored from core/installer.py, without importing it.
PACMAN_PACKAGES = {
    'whois': 'whois', 'dig': 'bind', 'shodan': 'python-shodan',
    'nmap': 'nmap', 'rustscan': 'rustscan', 'masscan': 'masscan',
    'gobuster': 'gobuster', 'wafw00f': 'wafw00f', 'nikto': 'nikto',
    'wpscan': 'wpscan', 'testssl.sh': 'testssl.sh', 'sslscan': 'sslscan',
    'sqlmap': 'sqlmap', 'msfconsole': 'metasploit', 'msfvenom': 'metasploit',
    'secretsdump.py': 'python-impacket', 'psexec.py': 'python-impacket',
    'GetUserSPNs.py': 'python-impacket', 'hashcat': 'hashcat',
    'john': 'john', 'hydra': 'hydra', 'airmon-ng': 'aircrack-ng',
    'airodump-ng': 'aircrack-ng', 'aircrack-ng': 'aircrack-ng',
    'reaver': 'reaver', 'wifite': 'wifite', 'bettercap': 'bettercap',
    'ettercap': 'ettercap', 'tcpdump': 'tcpdump',
}
DNF_PACKAGES = {
    'whois': 'whois', 'dig': 'bind-utils', 'nmap': 'nmap',
    'masscan': 'masscan', 'nikto': 'nikto', 'sslscan': 'sslscan',
    'sqlmap': 'sqlmap', 'hashcat': 'hashcat', 'john': 'john',
    'hydra': 'hydra', 'airmon-ng': 'aircrack-ng',
    'airodump-ng': 'aircrack-ng', 'aircrack-ng': 'aircrack-ng',
    'ettercap': 'ettercap', 'tcpdump': 'tcpdump',
}
PACKAGE_NAMES = {'apt': KALI_PACKAGES, 'pacman': PACMAN_PACKAGES, 'dnf': DNF_PACKAGES}


def validate_tools(keys: list[str]) -> list[str]:
    """Accept tool identifiers only; package arguments always come from maps."""
    if not keys or any(key not in KALI_PACKAGES for key in keys):
        raise ValueError('Sélection d’outils Linux invalide.')
    return sorted(set(keys))


def detect_manager() -> str:
    for manager, binary in [('pacman', 'pacman'), ('apt', 'apt-get'), ('dnf', 'dnf')]:
        if shutil.which(binary):
            return manager
    raise RuntimeError('Installation automatique disponible avec apt, pacman ou dnf. '
                       'Installez les outils manuellement, puis actualisez l’inventaire.')


def package_installed(manager: str, package: str, env: dict[str, str]) -> bool:
    commands = {
        'apt': ['dpkg-query', '-W', '-f=${db:Status-Status}', package],
        'pacman': ['pacman', '-Q', package],
        'dnf': ['rpm', '-q', package],
    }
    result = subprocess.run(commands[manager], capture_output=True, text=True, env=env)
    return result.returncode == 0 and (manager != 'apt' or result.stdout.strip() == 'installed')


def package_available(manager: str, package: str, env: dict[str, str]) -> bool:
    commands = {
        'apt': ['apt-cache', 'show', package],
        'pacman': ['pacman', '-Si', package],
        'dnf': ['dnf', '-q', 'list', '--available', package],
    }
    result = subprocess.run(commands[manager], capture_output=True, text=True, env=env)
    if result.returncode:
        return False
    if manager == 'apt':
        return bool(re.search(r'^Package: ' + re.escape(package) + r'$', result.stdout, re.M))
    if manager == 'dnf':
        # DNF 5 may return zero with no match. Require an actual package row.
        return bool(re.search(r'^' + re.escape(package) + r'\.[\w]+\s', result.stdout, re.M))
    return True


def install_tools(keys: list[str]) -> int:
    keys = validate_tools(keys)
    manager = detect_manager()
    mapping = PACKAGE_NAMES[manager]
    missing_tools = [key for key in keys if key not in mapping]
    packages = sorted({mapping[key] for key in keys if key in mapping})
    env = dict(os.environ, LC_ALL='C', DEBIAN_FRONTEND='noninteractive')
    pending = [package for package in packages if not package_installed(manager, package, env)]
    refresh = {'apt': ['apt-get', 'update'], 'dnf': ['dnf', 'makecache', '-y']}
    if pending and manager in refresh:
        subprocess.run(refresh[manager], check=True, env=env)
    # Keep pacman's database: -Sy without a full upgrade is unsafe on Arch.
    # Installing selected tools must not upgrade the entire system.
    available = [package for package in pending if package_available(manager, package, env)]
    missing_packages = [package for package in pending if package not in available]
    if available:
        commands = {
            'apt': ['apt-get', 'install', '-y'],
            'pacman': ['pacman', '-S', '--noconfirm', '--needed'],
            'dnf': ['dnf', 'install', '-y'],
        }
        subprocess.run([*commands[manager], *available], check=True, env=env)
        uninstalled = [package for package in available if not package_installed(manager, package, env)]
        if uninstalled:
            raise RuntimeError('Installation non confirmée : ' + ', '.join(uninstalled))
    if missing_tools:
        print('Outils sans paquet prévu pour ' + manager + ' : ' + ', '.join(missing_tools), flush=True)
    if missing_packages:
        print('Paquets absents des dépôts de cette distribution : ' + ', '.join(missing_packages), flush=True)
    if missing_tools or missing_packages:
        print('Installation incomplète. Installez les outils manquants manuellement, '
              'puis actualisez l’inventaire.', flush=True)
        return 2
    print('Installation Linux terminée. Actualisez l’inventaire des outils.', flush=True)
    return 0


def main() -> int:
    try:
        return install_tools(sys.argv[1:])
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
