"""Explicit desktop adapters; the original CLI registry remains unchanged."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from core.tools import TOOLS
from desktop.packages import MANIFEST, managed_command, installation_error

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
    "nmap": dict(desc="Identifiez les ports TCP ouverts sur une cible.", url="https://nmap.org/download.html", note="Installez Nmap pour Windows. Les profils utilisent une connexion TCP, sans scan SYN.", presets=[
        dict(label="100 ports TCP courants", args=["-sT", "-Pn", "-n", "--top-ports", "100", "{host}"]),
        dict(label="Port de la cible", args=["-sT", "-Pn", "-n", "-p", "{port}", "{host}"]),
        dict(label="Ports personnalisés", args=["-sT", "-Pn", "-n", "-p", "{ports}", "{host}"], fields={'ports': ('Ports TCP', '22,80,443,8000-8100')}),
    ]),
    "subfinder": dict(desc="Recherchez des sous-domaines à partir de sources publiques.", url="https://github.com/projectdiscovery/subfinder/releases", note="Sélectionnez la version Windows de Subfinder.", presets=[dict(label="Sous-domaines publics", args=["-d", "{host}", "-silent"], domain_only=True)]),
    "httpx": dict(desc="Relevez le statut HTTP, le titre et les technologies d’un site.", url="https://github.com/projectdiscovery/httpx/releases", note="Utilisez httpx de ProjectDiscovery, pas la bibliothèque Python du même nom.", presets=[dict(label="Statut, titre et technologies", args=["-u", "{url}", "-status-code", "-title", "-tech-detect", "-no-color"])]),
    "ffuf": dict(desc="Explorez les chemins d’un site à partir d’une liste de mots.", url="https://github.com/ffuf/ffuf/releases", note="Sélectionnez ffuf.exe et une liste de mots pour ce profil.", presets=[dict(label="Répertoires web", args=["-u", "{base_url}FUZZ", "-w", "{wordlist}", "-noninteractive", "-maxtime", "300"], wordlist=True)]),
    "gobuster": dict(desc="Recherchez des répertoires et des ressources web.", url="https://github.com/OJ/gobuster/releases", note="Sélectionnez gobuster.exe et une liste de mots pour ce profil.", presets=[dict(label="Répertoires web", args=["dir", "-u", "{url}", "-w", "{wordlist}", "--no-progress"], wordlist=True)]),
}

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
for _key, _adapter in ADAPTERS.items():
    if _key in MANIFEST:
        _spec = MANIFEST[_key]
        _adapter['package'] = _key
        _adapter.setdefault('url', _spec['url'])
        _adapter['note'] = ('Installation depuis l’application · Version ' + _spec['version'] +
                            (' · Python 3.10 ou ultérieur requis.' if _spec['kind'] == 'pip' else ' · Archive Windows vérifiée par SHA-256.'))
ADAPTERS['nuclei']['note'] += ' Les modèles sont téléchargés au premier lancement ; une connexion Internet est nécessaire.'
ADAPTERS['naabu']['note'] += ' Npcap peut être nécessaire selon la configuration Windows.'
ADAPTERS['amass']['note'] += ' Amass 5 exige un moteur de collecte externe. Son intégration Desktop reste à compléter ; l’installation du binaire seule ne suffit pas.'
ADAPTERS['ffuf']['presets'].append(dict(label='Répertoires avec filtre de taille', args=['-u','{base_url}FUZZ','-w','{wordlist}','-fs','{size}','-noninteractive','-maxtime','300'], wordlist=True, fields={'size': ('Taille de réponse à ignorer', '0')}))
ADAPTERS['katana']['presets'].append(dict(label='Profondeur personnalisée', args=['-u','{url}','-d','{depth}','-silent','-nc'], fields={'depth': ('Profondeur (1 à 10)', '2')}))


def catalog():
    entries = []
    for key, definition in {**BUILTINS, **TOOLS}.items():
        item = dict(definition, key=key, group=CATEGORIES.get(definition["category"], definition["category"]))
        if key in BUILTINS:
            item.update(mode="builtin", note="Inclus dans l’application. Aucune installation supplémentaire.")
        elif key in ADAPTERS:
            item.update(ADAPTERS[key], mode="native")
        else:
            item.update(mode="unavailable", presets=[], note="Cet outil du catalogue Linux n’a pas encore d’intégration Desktop. Il reste disponible dans la version CLI Linux.")
        entries.append(item)
    return entries


def find_executable(tool, configured=None, root=None):
    if tool["mode"] != "native":
        return None
    candidates = []
    if configured:
        candidates.append(str(Path(configured).expanduser()))
    else:
        if tool.get('package') and (command := managed_command(tool['package'], root=root)):
            return command[0]
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
        if path.is_file() and (os.name != "nt" or path.suffix.lower() == ".exe"):
            return str(path.resolve())
    return None


def availability(tool, settings, root=None):
    if tool["mode"] == "builtin":
        return "Inclus", True
    if tool["mode"] == "unavailable":
        return "À porter", False
    if tool['key'] == 'amass':
        return 'Service requis', False
    executable = find_executable(tool, settings.get(tool["key"]), root)
    if executable:
        return 'Prêt', True
    if tool.get('package') and installation_error(tool['package'], root):
        return 'Échec installation', False
    return 'À installer', False


def build_arguments(tool, preset_index, target, wordlist="", fields=None):
    preset = tool["presets"][preset_index]
    if not target:
        raise ValueError('Choisissez une cible.')
    if preset.get("domain_only"):
        import ipaddress
        try:
            ipaddress.ip_address(target["host"])
        except ValueError:
            pass
        else:
            raise ValueError("Ce profil attend un nom de domaine, pas une adresse IP.")
    if preset.get("wordlist") and not Path(wordlist).is_file():
        raise ValueError("Sélectionnez un fichier de mots existant.")
    from urllib.parse import urlsplit, urlunsplit
    parsed = urlsplit(target["url"])
    base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", ""))
    values = {**target, "wordlist": str(Path(wordlist).resolve()) if wordlist else "", "base_url": base_url}
    import re
    for name, (caption, default) in preset.get('fields', {}).items():
        value = (fields or {}).get(name, default).strip()
        if name == 'ports':
            if not re.fullmatch(r'[0-9,-]+', value):
                raise ValueError('Indiquez des ports séparés par des virgules, ou des plages comme 8000-8100.')
            for part in value.split(','):
                limits = part.split('-')
                if len(limits) > 2 or any(not p or not 1 <= int(p) <= 65535 for p in limits) or int(limits[0]) > int(limits[-1]):
                    raise ValueError('Les ports doivent être compris entre 1 et 65535, dans un ordre de plage valide.')
        elif not value.isascii() or not value.isdigit() or not (1 if name == 'depth' else 0) <= int(value) <= (10 if name == 'depth' else 1_000_000_000):
            raise ValueError(f'{caption} : valeur numérique invalide.')
        values[name] = value
    args = [arg.format_map(values) for arg in preset["args"]]
    if tool["key"] == "nmap" and ":" in target["host"]:
        args.insert(0, "-6")
    return args
