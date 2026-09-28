"""OS-independent execution plans and explicit Linux prerequisites."""
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from desktop.storage import data_root,write_json,now

BRIDGE=Path(__file__).parent/'linux_bridge.py'
NO_WINDOW=0x08000000 if os.name=='nt' else 0
KALI_PACKAGES={
 'whois':'whois','dig':'dnsutils','subfinder':'subfinder','amass':'amass','dnsrecon':'dnsrecon','theharvester':'theharvester','shodan':'python3-shodan',
 'nmap':'nmap','rustscan':'rustscan','masscan':'masscan','naabu':'naabu','gobuster':'gobuster','ffuf':'ffuf','httpx':'httpx-toolkit','wafw00f':'wafw00f','whatweb':'whatweb',
 'katana':'katana','gau':'getallurls','waybackurls':'waybackurls','nikto':'nikto','nuclei':'nuclei','wpscan':'wpscan','testssl.sh':'testssl.sh','sslscan':'sslscan',
 'sqlmap':'sqlmap','xsstrike':'xsstrike','dalfox':'dalfox','msfconsole':'metasploit-framework','msfvenom':'metasploit-framework','linpeas.sh':'peass',
 'secretsdump.py':'impacket-scripts','psexec.py':'impacket-scripts','GetUserSPNs.py':'impacket-scripts','crackmapexec':'netexec','bloodhound-python':'bloodhound.py',
 'hashcat':'hashcat','john':'john','hydra':'hydra','airmon-ng':'aircrack-ng','airodump-ng':'aircrack-ng','aircrack-ng':'aircrack-ng','reaver':'reaver','wifite':'wifite',
 'bettercap':'bettercap','ettercap':'ettercap-text-only','tcpdump':'tcpdump','responder':'responder',
}

def get_config(root=None):
    try: return json.loads((Path(root or data_root())/'linux.json').read_text(encoding='utf-8'))
    except (OSError,ValueError): return {}

def save_config(config,root=None):
    # No password or API key belongs in backend settings.
    allowed={'backend','distro','host','user','port','identity','known_hosts','paths','wsl_user'}
    write_json(Path(root or data_root())/'linux.json',{k:v for k,v in config.items() if k in allowed})

def linux_status(root=None):
    try:
        record=json.loads((Path(root or data_root())/'linux-status.json').read_text(encoding='utf-8'))
        return record if record.get('config')==get_config(root) else {}
    except (OSError,ValueError): return {}

def decode_wsl(data):
    return data.decode('utf-16-le' if b'\0' in data else 'utf-8',errors='replace').strip('\ufeff\r\n ')

def distributions():
    if os.name!='nt': return []
    result=subprocess.run(['wsl.exe','--list','--quiet'],capture_output=True,timeout=20,creationflags=NO_WINDOW)
    if result.returncode: raise RuntimeError(decode_wsl(result.stderr or result.stdout))
    return [line.strip() for line in decode_wsl(result.stdout).splitlines() if line.strip()]

def linux_path(value,config):
    if config.get('backend')!='wsl': return value
    result=subprocess.run(['wsl.exe','--distribution',config['distro'],'--exec','wslpath','-a',str(value)],capture_output=True,timeout=15,creationflags=NO_WINDOW)
    if result.returncode: raise ValueError('Chemin inaccessible dans WSL : '+str(value))
    return result.stdout.decode('utf-8',errors='replace').strip()

def bridge_command(config):
    backend=config.get('backend','local' if sys.platform.startswith('linux') else '')
    if backend=='wsl':
        distro=config.get('distro','')
        if not distro or any(ord(c)<32 for c in distro): raise ValueError('Sélectionnez une distribution WSL.')
        return ['wsl.exe','--distribution',distro,*(['--user',config['wsl_user']] if config.get('wsl_user') else []),'--exec','python3','-u','-c',BRIDGE.read_text(encoding='utf-8')]
    if backend=='ssh':
        host=config.get('host',''); user=config.get('user','')
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+',host) or host.startswith('-') or not re.fullmatch(r'[A-Za-z0-9_.-]+',user) or user.startswith('-'): raise ValueError('Hôte ou utilisateur SSH invalide.')
        port=int(config.get('port',22))
        if not 1<=port<=65535: raise ValueError('Port SSH invalide.')
        command=[shutil.which('ssh') or 'ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','-p',str(port)]
        if config.get('identity'): command+=['-i',str(Path(config['identity']).expanduser())]
        if config.get('known_hosts'): command+=['-o','UserKnownHostsFile='+str(Path(config['known_hosts']).expanduser())]
        return [*command,user+'@'+host,shlex.join(['python3','-u','-c',BRIDGE.read_text(encoding='utf-8')])]
    if backend=='local' and os.name!='nt':
        if getattr(sys,'frozen',False): return [sys.executable,'--linux-bridge']
        return [sys.executable,'-u',str(BRIDGE)]
    raise ValueError('Configurez un environnement Linux dans les paramètres : WSL sous Windows, Linux local ou une machine SSH.')

def inspect_backend(request):
    from core.tools import TOOLS
    root=Path(request['root'])
    config=get_config(root)
    choices={key:[*([config.get('paths',{}).get(key)] if config.get('paths',{}).get(key) else []),t['binary'],*t.get('binary_alternatives',[])] for key,t in TOOLS.items() if key!='winpeas'}
    choices['linpeas.sh']+=['/usr/share/peass/linpeas/linpeas.sh','/usr/share/peass/linpeas.sh']
    try:
        markers={key:t['help_contains_any'] for key,t in TOOLS.items() if t.get('help_contains_any')}
        result=subprocess.run(bridge_command(config),input=(json.dumps({'op':'inventory','tools':choices,'markers':markers})+'\n').encode(),capture_output=True,timeout=45,creationflags=NO_WINDOW)
        if result.returncode: raise RuntimeError(result.stderr.decode('utf-8',errors='replace') or result.stdout.decode('utf-8',errors='replace'))
        status=json.loads(result.stdout)
        if not isinstance(status.get('tools'),dict): raise ValueError('Inventaire Linux invalide.')
        status.update(config=config,checked=now())
        write_json(root/'linux-status.json',status)
        print('Connexion vérifiée. '+str(len(status['tools']))+' outils Linux détectés.',flush=True)
        print('Interfaces : '+', '.join(status.get('interfaces',[])),flush=True)
    except Exception as exc:
        write_json(root/'linux-status.json',{'config':config,'error':str(exc),'checked':now(),'tools':{}})
        raise

def execution_plan(argv,preset,root,directory,fields=None):
    config=get_config(root)
    backend=config.get('backend','local' if sys.platform.startswith('linux') else '')
    # Managed WSL has no shared sudo password. Elevate only explicitly privileged
    # profiles using the Windows account's existing WSL root authority.
    if backend=='wsl' and config.get('wsl_user')=='chaostic-tool' and preset.get('requires_root'):
        config={**config,'wsl_user':'root'}
    command=bridge_command(config)
    cwd=None if backend=='ssh' else linux_path(str(directory),config)
    mapped=[]
    from desktop.profiles import INPUT_FILES
    replacements={str(v):linux_path(str(v),config) for k,v in (fields or {}).items() if k in INPUT_FILES and v and backend=='wsl'}
    for arg in argv:
        for source,target in replacements.items(): arg=arg.replace(source,target)
        mapped.append(arg)
    return command,{'op':'run','argv':mapped,'cwd':cwd,'elevate':bool(preset.get('requires_root')),'timeout':1200}

def install_plan(keys):
    packages=sorted({KALI_PACKAGES[k] for k in keys if k in KALI_PACKAGES})
    if not packages: raise ValueError('Aucun paquet Linux pour cette sélection.')
    # apt is not a shell: package names come exclusively from this fixed map.
    return ['python3','-u','-c',(Path(__file__).parent/'linux_install.py').read_text(encoding='utf-8'),*packages]
