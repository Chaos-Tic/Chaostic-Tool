"""Explicit desktop adapters; the original CLI registry remains unchanged."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from core.tools import TOOLS, AMASS_STDOUT
from core.phases import PHASES
from desktop.tool_paths import resolve_tool
from desktop.packages import MANIFEST, managed_command, installation_error, can_install, find_python, installed
from desktop.profiles import normalized, validate_field, placeholders
from desktop.backends import linux_status, get_config
from desktop.i18n import T

CATEGORIES = {
    "local": "Diagnostic", "osint": "OSINT", "recon": "Réseau",
    "web_enum": "Web", "vulnscan": "Vulnérabilités", "exploitation": "Exploitation",
    "postexploit": "Post-exploitation", "passwords": "Mots de passe",
    "wireless": "Wi-Fi", "network": "Réseau avancé",
}


def _rewrite_args(args, rules):
    """Apply declarative argv rewrites in order, returning a new list.

    Rule kinds: ``{'map': {old: new}}`` rewrites every matching token;
    ``{'range_flag': flag, 'to': repl}`` renames *flag* to *repl* when the token
    after it is a range (contains ``-``); ``{'rename': flag, 'to': repl,
    'values': {...}}`` renames the first *flag* and remaps the value after it.
    """
    result = list(args)
    for rule in rules:
        if 'map' in rule:
            mapping = rule['map']
            result = [mapping.get(a, a) for a in result]
        elif 'range_flag' in rule:
            flag, repl = rule['range_flag'], rule['to']
            for i, arg in enumerate(result[:-1]):
                if arg == flag and '-' in result[i + 1]: result[i] = repl
        elif 'rename' in rule:
            if rule['rename'] in result:
                i = result.index(rule['rename'])
                result[i] = rule['to']
                if i + 1 < len(result): result[i + 1] = rule['values'].get(result[i + 1], result[i + 1])
    return result


def amass_profile(index):
    """One honest Amass v5 desktop profile for CLI preset *index*.

    Amass v5 enumerates with no collection engine and no ``-passive`` flag
    (passive is the default); discovered names go only to the ``-o`` file, so
    the shared ``AMASS_STDOUT`` points it at stdout (captured by the runner).
    CLI preset 1 is the active mode (``-active``), which adds zone transfers and
    certificate name grabs. The old ``-engine http://127.0.0.1:4000`` was
    misleading — amass does not need a running engine — so it is not emitted.
    """
    active = index == 1
    args = ['enum', '-active', '-d', '{host}', *AMASS_STDOUT] if active else ['enum', '-d', '{host}', *AMASS_STDOUT]
    label = 'Énumération active (transferts de zone et certificats)' if active else 'Énumération passive (sources par défaut)'
    return dict(label=label, args=args, domain_only=True)


# Declarative per-tool desktop transforms, applied generically by linux_presets /
# cli_native_profile (and, for nuclei, by the ADAPTERS loop below). They replace
# the former per-tool ``if key == ...`` branches: a tool's GUI munging is one row
# here, not code in the appliers.
#   backends:   which backends the transform applies to ('native', 'linux').
#   builder:    callable(index) -> full profile spec (amass' passive/active engine variants).
#   set_args/fields/label_suffix: replace the argv, add typed fields, suffix the label.
#   rules:      ordered argv rewrites handed to _rewrite_args.
GUI_TRANSFORMS = {
    'amass': {'backends': ('native', 'linux'), 'builder': amass_profile},
    'theharvester': {'backends': ('native',), 'set_args': ['-d', '{host}', '-b', '{sources}'],
                     'fields': {'sources': ('Sources OSINT disponibles', 'crtsh')},
                     'label_suffix': ' · sources configurables'},
    'rustscan': {'backends': ('native', 'linux'), 'rules': [
        {'map': {'--rate': '-b'}},
        {'range_flag': '-p', 'to': '-r'},
    ]},
    'dalfox': {'backends': ('native',), 'rules': [{'map': {'url': 'scan'}}]},
    'nuclei': {'backends': ('native',), 'rules': [
        {'rename': '-t', 'to': '-tags', 'values': {'exposures': 'exposure', 'network': 'network'}},
    ]},
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
        dict(label="Recherche passive Shodan (sans scan — nécessite la clé API Shodan)", args=["-sn", "-Pn", "-n", "--script", "shodan-api", "--script-args", "shodan-api.apikey={shodan_key}", "{host}"], needs_key="shodan"),
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
ADAPTERS['amass']['presets']=[]  # Amass v5 variants are built per CLI index (passive default / -active) in amass_profile
for _key in ['subfinder','httpx','gobuster','ffuf','sqlmap','nuclei']:
    # Only nuclei carries a native argv rewrite here (-t <dir> -> -tags <tag>);
    # the rest are straight appends of the CLI preset.
    _spec=GUI_TRANSFORMS.get(_key)
    _cmd_rules=_spec['rules'] if _spec and 'native' in _spec['backends'] and 'rules' in _spec else None
    for _p in TOOLS[_key]['presets']:
        _p=dict(_p)
        if _cmd_rules: _p['cmd']=_rewrite_args(_p['cmd'],_cmd_rules)
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
ADAPTERS['amass']['note']+=' Amass v5 énumère sans moteur de collecte ; les noms trouvés sont affichés directement.'
ADAPTERS['hashcat']['note']+=' Un pilote GPU/OpenCL compatible est requis.'

BUILTINS['whois']=dict(name='Whois',category='osint',desc='Consultez les informations d’enregistrement auprès du serveur Whois.',presets=[dict(label='Requête Whois',worker='whois',needs_target=True)])
BUILTINS['dig']=dict(name='DNS avancé',category='osint',desc='Interrogez les enregistrements DNS ; le moteur dnspython est intégré.',presets=[dict(label='Enregistrements '+r,worker='dig',rrtype=r,needs_target=True,fields={'nameserver':('Serveur DNS (facultatif)','')}) for r in ['A','AAAA','MX','TXT','NS','SOA','CAA','ANY','AXFR']])


def _apply_transform(preset, spec, index, backend):
    """Apply a GUI_TRANSFORMS *spec* to a normalized *preset*; return the preset.

    The ``native`` builder path rebuilds the preset from the synthesized spec
    (dropping the CLI ``cmd``/``output`` keys), matching the historic amass
    behaviour; the ``linux`` builder path mutates in place and keeps them.
    """
    if 'builder' in spec:
        synth = spec['builder'](index)
        if backend == 'native':
            return dict(normalized(synth), cli_index=preset['cli_index'],
                        interactive=preset['interactive'], requires_root=preset['requires_root'])
        preset.update(label=synth['label'], args=synth['args'])
        if synth.get('domain_only'): preset['domain_only'] = True
        preset['fields'].update(synth.get('fields', {}))
    elif 'set_args' in spec:
        preset['args'] = list(spec['set_args'])
        preset['fields'].update(spec['fields'])
        preset['label'] = preset['label'] + spec['label_suffix']
    elif 'rules' in spec:
        preset['args'] = _rewrite_args(preset['args'], spec['rules'])
    return preset


def linux_presets(key):
    result=[]
    spec=GUI_TRANSFORMS.get(key)
    spec=spec if spec and 'linux' in spec['backends'] else None
    for original in TOOLS[key]['presets']:
        p=normalized(original,'linux')
        p['requires_root']=bool(original.get('requires_root',TOOLS[key].get('requires_root')))
        p['interactive']=bool(TOOLS[key].get('interactive'))
        if spec: p=_apply_transform(p,spec,len(result),'linux')
        # hashcat keeps a Linux-only field caption for the 22000 capture format;
        # it is not an argv rewrite, so it stays an explicit rule.
        if key=='hashcat' and '-m' in p['args'] and '22000' in p['args']: p['fields']['hashfile']=('Capture de hachages au format 22000','')
        p['cli_index']=len(result)
        result.append(p)
    return result


def cli_native_profile(key,index):
    original=TOOLS[key]['presets'][index]
    p=normalized(original)
    p['cli_index']=index
    p['interactive']=bool(TOOLS[key].get('interactive'))
    p['requires_root']=bool(original.get('requires_root',TOOLS[key].get('requires_root')))
    spec=GUI_TRANSFORMS.get(key)
    if spec and 'native' in spec['backends']: p=_apply_transform(p,spec,index,'native')
    return p


def catalog():
    entries=[]
    for key,definition in {**TOOLS,**BUILTINS}.items():
        item=dict(definition,key=key,group=CATEGORIES.get(definition['category'],definition['category']))
        item.pop('phase',None)  # authoring hint consumed by core.phases; membership is exposed via item['phases'] below
        item['linux_presets']=linux_presets(key) if key in TOOLS else []
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
    if tool.get('package') and not configured and can_install(tool['package']):
        try:
            binary=tool['binary'] if tool['key'] in ('secretsdump.py','psexec.py','GetUserSPNs.py') else None
            command=managed_command(tool['package'],binary,root)
            if command: return command
        except (KeyError,ValueError): pass
    path=find_executable(tool,configured,root)
    if not path: return None
    if Path(path).suffix=='.py' and os.name=='nt':
        python=find_python()
        if not python and (runtime := installed('python-runtime',root)):
            candidate=runtime['path']/runtime['executable']
            if candidate.is_file(): python=str(candidate)
        return [python,path] if python else None
    return [path]


def find_executable(tool, configured=None, root=None):
    if tool["mode"] != "native":
        return None
    candidates = []
    if configured:
        candidates.append(str(Path(configured).expanduser()))
    else:
        if tool.get('package') and can_install(tool['package']) and (command := managed_command(tool['package'], binary=tool['binary'] if tool['key'].endswith('.py') else None, root=root)):
            return command[-1]
        binary = tool["binary"]
        found = resolve_tool([binary,*tool.get('binary_alternatives',[])],tool.get('help_contains_any',[]))
        if found:
            candidates.append(found)
        if tool["key"] == "nmap" and os.name == "nt":
            for env in ("ProgramFiles", "ProgramFiles(x86)"):
                if base := os.environ.get(env):
                    candidates.append(str(Path(base) / "Nmap" / "nmap.exe"))
    for value in candidates:
        path = Path(value)
        if path.is_file() and ((os.name != "nt" and os.access(path,os.X_OK)) or (os.name == "nt" and path.suffix.lower() in (".exe", ".py"))):
            return os.path.abspath(path)
    return None


def availability_state(tool,settings,root=None):
    """Resolve a tool to a shared :class:`core.availability.Availability`.

    The single source of truth both front-ends read. Amass is plain READY once
    installed (v5 needs no engine). Key-gated tools whose key is missing surface
    NEEDS_KEY; a declared install error is BLOCKED; everything unresolved is
    NOT_INSTALLED, with the French label kept so the GUI pill/legend is unchanged.
    """
    from core import availability as av
    key=tool['key']
    def _resolved(label,tone):
        gated=av.KEY_GATED.get(key)
        if gated and not av.key_present(gated):
            return av.Availability(av.NEEDS_KEY,label='Clé requise',tone='warn',
                                   reason=f'{gated} API key')
        return av.Availability(av.READY,label=label,tone=tone)
    if tool['mode']=='builtin': return av.Availability(av.READY,label='Inclus',tone='ok')
    if tool['mode']=='native' and native_command(tool,settings.get(key),root):
        return _resolved('Prêt','ok')
    status=linux_status(root)
    if key in status.get('tools',{}): return _resolved('Prêt · Linux','info')
    if tool.get('package') and installation_error(tool['package'],root):
        return av.Availability(av.BLOCKED,label='Échec installation',tone='bad')
    if tool['mode']=='native': return av.Availability(av.NOT_INSTALLED,label='À installer',tone='bad')
    label='À installer · Linux' if status.get('tools') else 'Linux à configurer'
    return av.Availability(av.NOT_INSTALLED,label=label,tone='bad')


def availability(tool,settings,root=None):
    """Legacy ``(French label, ready)`` tuple over :func:`availability_state`."""
    state=availability_state(tool,settings,root)
    return state.label,state.ready


def build_arguments(tool,preset_index,target,wordlist='',fields=None,preset=None,backend='native'):
    preset=preset or tool['presets'][preset_index]
    fields=fields or {}
    if preset.get('needs_target',True) and not target: raise ValueError(T('Choisissez une cible.'))
    target=target or {}
    if preset.get('domain_only'):
        import ipaddress
        try: ipaddress.ip_address(target['host'])
        except ValueError: pass
        else: raise ValueError(T('Ce profil attend un nom de domaine, pas une adresse IP.'))
    from urllib.parse import urlsplit,urlunsplit
    parsed=urlsplit(target.get('url',''))
    base_url=urlunsplit((parsed.scheme,parsed.netloc,parsed.path.rstrip('/')+'/','',''))
    values={**target,'base_url':base_url}
    if preset.get('wordlist'): values['wordlist']=validate_field('wordlist',wordlist,backend)
    for name,(caption,default) in preset.get('fields',{}).items():
        value=fields.get(name,default)
        if name=='ports':
            if not re.fullmatch(r'[0-9,-]+',value): raise ValueError(T('Liste de ports invalide.'))
            for part in value.split(','):
                limits=part.split('-')
                if len(limits)>2 or any(not p or not 1<=int(p)<=65535 for p in limits) or int(limits[0])>int(limits[-1]): raise ValueError(T('Plage de ports invalide.'))
            values[name]=value
        elif name=='engine':
            from desktop.storage import parse_target
            values[name]=parse_target(value)['url'].rstrip('/')
        elif name=='nameserver' and not value: values[name]=''
        else: values[name]=validate_field(name,value,backend)
    if preset.get('needs_key'):
        values[preset['needs_key']+'_key']=preset_key_value(preset) or ''
    args=[arg.format_map(values) for arg in preset.get('args',[])]
    if tool['key']=='nmap' and ':' in target.get('host','') and '-6' not in args: args.insert(0,'-6')
    return args


def preset_key_value(preset):
    """The stored API key a preset needs (preset['needs_key']), or None.

    Read from the OS secret store at launch; callers add it to the redaction
    set so it never reaches the preview, the live stream or the saved history.
    """
    needed=preset.get('needs_key')
    if not needed: return None
    from core import api_keys
    return api_keys.get(needed)
