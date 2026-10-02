"""Explicit desktop adapters; the original CLI registry remains unchanged."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from core.tools import TOOLS
from core.phases import PHASES
from desktop.packages import MANIFEST, managed_command, installation_error, can_install, find_python, installed
from desktop.profiles import normalized, validate_field, placeholders
from desktop.backends import linux_status, get_config

CATEGORIES = {
    "local": "Diagnostic", "osint": "OSINT", "recon": "Réseau",
    "web_enum": "Web", "vulnscan": "Vulnérabilités", "exploitation": "Exploitation",
    "postexploit": "Post-exploitation", "passwords": "Mots de passe",
    "wireless": "Wi-Fi", "network": "Réseau avancé",
}

BUILTINS = {
    "desktop-diagnostic": dict(name="Diagnostic local", category="local", desc="Vérifiez l’environnement de l’application, sans connexion réseau.", presets=[dict(label="Vérifier cet ordinateur", worker="diagnostic")]),
    "desktop-dns": dict(name="Résolution DNS", category="osint", desc="Résolvez les adresses IPv4 et IPv6 d’une cible avec le résolveur système.", presets=[dict(label="Adresses IPv4 et IPv6", worker="dns")]),
    "desktop-http": dict(name="En-têtes HTTP", category="web_enum", desc="Consultez le statut HTTP et les en-têtes renvoyés par un site.", presets=[dict(label="Lire les en-têtes (HEAD)", worker="http")]),
    "desktop-tls": dict(name="Certificat TLS", category="web_enum", desc="Vérifiez le certificat, sa validité et la connexion TLS d’un service.", presets=[dict(label="Vérifier le certificat", worker="tls")]),
}

ADAPTERS = {
    "nmap": dict(desc="Identifiez les ports TCP ouverts sur une cible.", url="https://nmap.org/download.html", note="Installez Nmap pour votre système. Les profils utilisent une connexion TCP, sans scan SYN.", presets=[
        dict(label="100 ports TCP courants", args=["-sT", "-Pn", "-n", "--top-ports", "100", "{host}"]),
        dict(label="Port de la cible", args=["-sT", "-Pn", "-n", "-p", "{port}", "{host}"]),
        dict(label="Ports personnalisés", args=["-sT", "-Pn", "-n", "-p", "{ports}", "{host}"], fields={'ports': ('Ports TCP', '22,80,443,8000-8100')}),
    ]),
    "subfinder": dict(desc="Recherchez des sous-domaines à partir de sources publiques.", url="https://github.com/projectdiscovery/subfinder/releases", note="Sélectionnez la version de Subfinder adaptée à votre système.", presets=[dict(label="Sous-domaines publics", args=["-d", "{host}", "-silent"], domain_only=True)]),
    "httpx": dict(desc="Relevez le statut HTTP, le titre et les technologies d’un site.", url="https://github.com/projectdiscovery/httpx/releases", note="Utilisez httpx de ProjectDiscovery, pas la bibliothèque Python du même nom.", presets=[dict(label="Statut, titre et technologies", args=["-u", "{url}", "-status-code", "-title", "-tech-detect", "-no-color"])]),
    "ffuf": dict(desc="Explorez les chemins d’un site à partir d’une liste de mots.", url="https://github.com/ffuf/ffuf/releases", note="Sélectionnez ffuf et une liste de mots pour ce profil.", presets=[dict(label="Répertoires web", args=["-u", "{base_url}FUZZ", "-w", "{wordlist}", "-noninteractive", "-maxtime", "300"], wordlist=True)]),
    "gobuster": dict(desc="Recherchez des répertoires et des ressources web.", url="https://github.com/OJ/gobuster/releases", note="Sélectionnez gobuster et une liste de mots pour ce profil.", presets=[dict(label="Répertoires web", args=["dir", "-u", "{url}", "-w", "{wordlist}", "--no-progress"], wordlist=True)]),
}

ADAPTERS['rustscan']=dict(desc='Repérez les ports TCP puis transmettez les résultats à Nmap.',
    presets=[dict(label='Port de la cible, sans Nmap',args=['-a','{host}','-p','{port}','--scripts','none','--no-config'])],
    note='Scanner natif. Les profils CLI avec détection de services nécessitent aussi Nmap. Le profil autonome fonctionne sans Nmap.')
ADAPTERS['nmap']['note']='Installez Nmap avec son assistant officiel. Npcap et les droits administrateur sont requis pour certains profils SYN, UDP et système. Les profils TCP connect fonctionnent sans capture brute.'

# Profiles are explicit argument vectors: no shell and no terminal interaction.
ADAPTERS.update({
    'nuclei': dict(desc='Vérifiez un site avec les modèles Nuclei.', presets=[
        dict(label='Vulnérabilités critiques et élevées', args=['-u', '{url}', '-severity', 'critical,high', '-rl', '10', '-nc']),
        dict(label='Détection des technologies', args=['-u', '{url}', '-tags', 'tech', '-rl', '10', '-nc']),
    ]),
    'katana': dict(desc='Explorez les liens et ressources d’un site.', presets=[
        dict(label='Exploration courte (profondeur 1)', args=['-u', '{url}', '-d', '1', '-silent', '-nc']),
        dict(label='Exploration approfondie (profondeur 3)', args=['-u', '{url}', '-d', '3', '-silent', '-nc']),
    ]),
    'gau': dict(desc='Retrouvez les URL connues d’un domaine dans les archives publiques.', presets=[
        dict(label='URL archivées', args=['{host}'], domain_only=True),
        dict(label='Inclure les sous-domaines', args=['--subs', '{host}'], domain_only=True),
    ]),
    'waybackurls': dict(desc='Retrouvez les URL archivées par la Wayback Machine.', presets=[
        dict(label='URL du domaine', args=['-no-subs', '{host}'], domain_only=True),
        dict(label='Domaine et sous-domaines', args=['{host}'], domain_only=True),
    ]),
    'dalfox': dict(desc='Analysez les paramètres d’une URL pour rechercher des failles XSS.', presets=[
        dict(label='Analyse de l’URL', args=['--no-color', 'scan', '{url}']),
    ]),
    'amass': dict(desc='Cartographiez les sous-domaines et les informations DNS.', presets=[
        dict(label='Énumération du domaine', args=['enum', '-d', '{host}'], domain_only=True),
    ]),
    'naabu': dict(desc='Repérez les ports TCP accessibles.', presets=[
        dict(label='100 ports courants (TCP connect)', args=['-host', '{host}', '-top-ports', '100', '-s', 'c', '-nc']),
        dict(label='Port de la cible (TCP connect)', args=['-host', '{host}', '-p', '{port}', '-s', 'c', '-nc']),
    ]),
    'wafw00f': dict(desc='Identifiez le pare-feu applicatif d’un site.', presets=[
        dict(label='Identifier le WAF', args=['{url}']),
        dict(label='Essayer toutes les signatures', args=['-a', '{url}']),
    ]),
    'sqlmap': dict(desc='Analysez les paramètres d’une URL pour rechercher des injections SQL.', presets=[
        dict(label='Détection standard', args=['-u', '{url}', '--batch', '--level=1', '--risk=1', '--disable-coloring']),
    ]),
})

# The original registry is preserved, including interactive and local-only profiles.
for _key in ['dnsrecon','theharvester','shodan','xsstrike','secretsdump.py','psexec.py','GetUserSPNs.py','bloodhound-python','hashcat','john','sslscan','aircrack-ng']:
    ADAPTERS[_key] = dict(presets=[dict(p) for p in TOOLS[_key]['presets']], note='Profils natifs. Une distribution Linux peut également être sélectionnée.', url='https://github.com/Chaos-Tic/Chaostic-Tool')
    if _key in MANIFEST: ADAPTERS[_key]['package']=_key
    elif _key in ('secretsdump.py','psexec.py','GetUserSPNs.py'): ADAPTERS[_key]['package']='impacket'
ADAPTERS['shodan']['presets'].append(dict(label='Configurer la clé API Shodan',args=['init','{api_key}'],fields={'api_key':('Clé API','')}))
ADAPTERS['theharvester']['presets']=[dict(label='Sources publiques crtsh',args=['-d','{host}','-b','crtsh']),dict(label='Sources personnalisées',args=['-d','{host}','-b','{sources}'],fields={'sources':('Sources séparées par des virgules','crtsh')})]
ADAPTERS['winpeas']=dict(package='winpeas',url='https://github.com/peass-ng/PEASS-ng/releases',note='Exécution sur cet ordinateur Windows. Les résultats décrivent ce PC, pas une cible distante.',presets=[dict(label='Informations système de ce PC',args=['systeminfo','notcolor']),dict(label='Énumération complète de ce PC',args=['notcolor'])])
ADAPTERS['amass']['presets']=[dict(label='Énumération avec moteur Amass',args=['enum','-d','{host}','-engine','{engine}'],fields={'engine':('URL du moteur de collecte','http://127.0.0.1:4000')},domain_only=True)]
for _key in ['subfinder','httpx','gobuster','ffuf','sqlmap','nuclei']:
    for _p in TOOLS[_key]['presets']:
        _p=dict(_p)
        if _key=='nuclei' and '-t' in _p['cmd']:
            _p['cmd']=list(_p['cmd']); _idx=_p['cmd'].index('-t'); _p['cmd'][_idx]='-tags'; _p['cmd'][_idx+1]={'exposures':'exposure','network':'network'}[_p['cmd'][_idx+1]]
        ADAPTERS[_key]['presets'].append(_p)
ADAPTERS['ffuf']['presets'].append(dict(label='Répertoires avec filtre de taille',args=['-u','{base_url}FUZZ','-w','{wordlist}','-fs','{size}','-noninteractive','-maxtime','300'],wordlist=True,fields={'size':('Taille à ignorer','0')}))
ADAPTERS['katana']['presets'].append(dict(label='Profondeur personnalisée',args=['-u','{url}','-d','{depth}','-silent','-nc'],fields={'depth':('Profondeur (1 à 10)','2')}))
for _key,_adapter in ADAPTERS.items():
    _package=_adapter.get('package',_key)
    if _package in MANIFEST:
        _adapter['package']=_package
        _spec=MANIFEST[_package]
        _adapter.setdefault('url',_spec.get('url','https://github.com/Chaos-Tic/Chaostic-Tool'))
        _adapter['note']=_adapter.get('note','')+' Installation intégrée, version '+_spec['version']+'.'
    _adapter.setdefault('note','Choisissez un exécutable compatible avec votre système.')
    _adapter.setdefault('url','https://github.com/Chaos-Tic/Chaostic-Tool')
    _adapter['presets']=[normalized(p) for p in _adapter['presets']]
    for _p in _adapter['presets']:
        _p['interactive']=bool(TOOLS[_key].get('interactive'))
ADAPTERS['nuclei']['note']+=' Les modèles sont téléchargés lors du premier usage.'
ADAPTERS['amass']['note']+=' Un moteur de collecte Amass configuré doit être accessible à l’URL indiquée.'
ADAPTERS['hashcat']['note']+=' Un pilote GPU/OpenCL compatible est requis.'

BUILTINS['whois']=dict(name='Whois',category='osint',desc='Consultez les informations d’enregistrement auprès du serveur Whois.',presets=[dict(label='Requête Whois',worker='whois',needs_target=True)])
BUILTINS['dig']=dict(name='DNS avancé',category='osint',desc='Interrogez les enregistrements DNS ; le moteur dnspython est intégré.',presets=[dict(label='Enregistrements '+r,worker='dig',rrtype=r,needs_target=True,fields={'nameserver':('Serveur DNS (facultatif)','')}) for r in ['A','AAAA','MX','TXT','NS','SOA','CAA','ANY','AXFR']])

def linux_presets(key):
    result=[]
    for original in TOOLS[key]['presets']:
        p=normalized(original,'linux')
        p['requires_root']=bool(original.get('requires_root',TOOLS[key].get('requires_root')))
        p['interactive']=bool(TOOLS[key].get('interactive'))
        if key=='rustscan': p['args']=rustscan_arguments(p['args'])
        if key=='hashcat' and '-m' in p['args'] and '22000' in p['args']: p['fields']['hashfile']=('Capture de hachages au format 22000','')
        if key=='amass':
            p['args']=['enum','-d','{host}','-engine','{engine}']; p['fields']['engine']=('Moteur de collecte Amass 5','http://127.0.0.1:4000')
        p['cli_index']=len(result)
        result.append(p)
    return result


def rustscan_arguments(args):
    args=['-b' if x=='--rate' else x for x in args]
    # RustScan expects ranges via -r; -p accepts comma-separated individual ports.
    for i,arg in enumerate(args[:-1]):
        if arg=='-p' and '-' in args[i+1]: args[i]='-r'
    return args


def cli_native_profile(key,index):
    original=TOOLS[key]['presets'][index]
    p=normalized(original)
    p['cli_index']=index
    p['interactive']=bool(TOOLS[key].get('interactive'))
    p['requires_root']=bool(original.get('requires_root',TOOLS[key].get('requires_root')))
    if key=='amass': p=dict(ADAPTERS[key]['presets'][0],cli_index=index)
    if key=='theharvester':
        p['args']=['-d','{host}','-b','{sources}']
        p['fields']['sources']=('Sources OSINT disponibles','crtsh')
        p['label']=original['label']+' · sources configurables'
    if key=='rustscan': p['args']=rustscan_arguments(p['args'])
    if key=='dalfox': p['args']=['scan' if a=='url' else a for a in p['args']]
    if key=='nuclei' and '-t' in p['args']:
        at=p['args'].index('-t'); p['args'][at]='-tags'
        p['args'][at+1]={'exposures':'exposure'}.get(p['args'][at+1],p['args'][at+1])
    return p


def catalog():
    entries=[]
    for key,definition in {**TOOLS,**BUILTINS}.items():
        item=dict(definition,key=key,group=CATEGORIES.get(definition['category'],definition['category']))
        item['linux_presets']=linux_presets(key) if key in TOOLS and key!='winpeas' else []
        if key in BUILTINS:
            item.update(BUILTINS[key],mode='builtin',note='Inclus dans l’application. Aucune installation supplémentaire.')
            item['presets']=[dict(p,backend='builtin',needs_target=p.get('needs_target',key!='desktop-diagnostic')) for p in item['presets']]
        elif key in ADAPTERS:
            item.update(ADAPTERS[key],mode='native')
            item['presets']=[dict(p) for p in item['presets']]
            for index,original in enumerate(TOOLS[key]['presets']):
                existing=next((p for p in item['presets'] if p['label']==original['label']),None)
                if existing is not None:
                    existing['cli_index']=index
                    existing['requires_root']=bool(original.get('requires_root',TOOLS[key].get('requires_root')))
                    existing['interactive']=bool(TOOLS[key].get('interactive'))
                else: item['presets'].append(cli_native_profile(key,index))
        else:
            item.update(mode='linux',presets=item['linux_presets'],note='Exécution Linux intégrée. Configurez et vérifiez Linux local, WSL ou SSH dans les paramètres.')
        phases=[p for p in PHASES if key in p['tools']]
        item['phases']=[p['id'] for p in phases]
        if phases: item['group']=phases[0]['id'][:2]+' · '+phases[0]['name']
        entries.append(item)
    order={key:i for i,key in enumerate(dict.fromkeys(key for phase in PHASES for key in phase['tools']))}
    return sorted(entries,key=lambda t:order.get(t['key'],100))


def native_command(tool,configured=None,root=None):
    if tool['key']=='winpeas' and os.name!='nt': return None
    if tool.get('package') and not configured and can_install(tool['package']):
        try:
            binary=tool['binary'] if tool['key'] in ('secretsdump.py','psexec.py','GetUserSPNs.py') else None
            command=managed_command(tool['package'],binary,root)
            if command: return command
        except (KeyError,ValueError): pass
    path=find_executable(tool,configured,root)
    if not path: return None
    if Path(path).suffix=='.py':
        python=find_python()
        if not python and (runtime := installed('python-runtime',root)):
            candidate=runtime['path']/runtime['executable']
            if candidate.is_file(): python=str(candidate)
        return [python,path] if python else None
    return [path]


def find_executable(tool, configured=None, root=None):
    if tool['key']=='winpeas' and os.name!='nt': return None
    if tool["mode"] != "native":
        return None
    candidates = []
    if configured:
        candidates.append(str(Path(configured).expanduser()))
    else:
        if tool.get('package') and can_install(tool['package']) and (command := managed_command(tool['package'], binary=tool['binary'] if tool['key'].endswith('.py') else None, root=root)):
            return command[-1]
        binary = tool["binary"]
        found = shutil.which(binary)
        if found:
            candidates.append(found)
        if tool["key"] == "nmap" and os.name == "nt":
            for env in ("ProgramFiles", "ProgramFiles(x86)"):
                if base := os.environ.get(env):
                    candidates.append(str(Path(base) / "Nmap" / "nmap.exe"))
    for value in candidates:
        path = Path(value)
        if path.is_file() and (os.name != "nt" or path.suffix.lower() in (".exe", ".py")):
            return str(path.resolve())
    return None


def availability(tool,settings,root=None):
    if tool['key']=='winpeas' and os.name!='nt': return 'Windows uniquement',False
    if tool['mode']=='builtin': return 'Inclus',True
    if tool['mode']=='native' and native_command(tool,settings.get(tool['key']),root):
        return ('Service requis',False) if tool['key']=='amass' else ('Prêt',True)
    status=linux_status(root)
    if tool['key'] in status.get('tools',{}): return ('Service requis',False) if tool['key']=='amass' else ('Prêt · Linux',True)
    if tool.get('package') and installation_error(tool['package'],root): return 'Échec installation',False
    if tool['mode']=='native': return 'À installer',False
    return ('À installer · Linux',False) if status.get('tools') else ('Linux à configurer',False)


def build_arguments(tool,preset_index,target,wordlist='',fields=None,preset=None,backend='native'):
    preset=preset or tool['presets'][preset_index]
    fields=fields or {}
    if preset.get('needs_target',True) and not target: raise ValueError('Choisissez une cible.')
    target=target or {}
    if preset.get('domain_only'):
        import ipaddress
        try: ipaddress.ip_address(target['host'])
        except ValueError: pass
        else: raise ValueError('Ce profil attend un nom de domaine, pas une adresse IP.')
    from urllib.parse import urlsplit,urlunsplit
    parsed=urlsplit(target.get('url',''))
    base_url=urlunsplit((parsed.scheme,parsed.netloc,parsed.path.rstrip('/')+'/','',''))
    values={**target,'base_url':base_url}
    if preset.get('wordlist'): values['wordlist']=validate_field('wordlist',wordlist,backend)
    for name,(caption,default) in preset.get('fields',{}).items():
        value=fields.get(name,default)
        if name=='ports':
            if not re.fullmatch(r'[0-9,-]+',value): raise ValueError('Liste de ports invalide.')
            for part in value.split(','):
                limits=part.split('-')
                if len(limits)>2 or any(not p or not 1<=int(p)<=65535 for p in limits) or int(limits[0])>int(limits[-1]): raise ValueError('Plage de ports invalide.')
            values[name]=value
        elif name=='engine':
            from desktop.storage import parse_target
            values[name]=parse_target(value)['url'].rstrip('/')
        elif name=='nameserver' and not value: values[name]=''
        else: values[name]=validate_field(name,value,backend)
    args=[arg.format_map(values) for arg in preset.get('args',[])]
    if tool['key']=='nmap' and ':' in target.get('host','') and '-6' not in args: args.insert(0,'-6')
    return args
