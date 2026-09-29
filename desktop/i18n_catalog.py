"""Traductions FR→EN du contenu du catalogue (noms, groupes, descriptions,
notes, libellés de profils). Fusionné dans le dictionnaire principal de i18n.

Les chaînes déjà en anglais dans le catalogue ne figurent pas ici : `T()` les
renvoie inchangées (repli). On ne traduit donc que le contenu français.
"""

CATALOG = {
    # --- Noms d'outils français ---
    "DNS avancé": "Advanced DNS",
    "En-têtes HTTP": "HTTP headers",
    "Résolution DNS": "DNS resolution",
    "Certificat TLS": "TLS certificate",
    "Diagnostic local": "Local diagnostic",
    "Whois": "Whois",

    # --- Groupes / phases (colonne Catégorie) ---
    "01 · OSINT & reconnaissance passive": "01 · OSINT & passive recon",
    "02 · Scan réseau": "02 · Network scan",
    "03 · Énumération Web": "03 · Web enumeration",
    "04 · Vulnérabilités": "04 · Vulnerabilities",
    "05 · Exploitation": "05 · Exploitation",
    "06 · Post-exploitation & privilèges": "06 · Post-exploitation & privileges",
    "07 · Mots de passe": "07 · Passwords",
    "08 · Windows / Active Directory": "08 · Windows / Active Directory",
    "09 · Wi-Fi": "09 · Wi-Fi",
    "10 · Réseau & MITM": "10 · Network & MITM",
    "Diagnostic": "Diagnostic",
    "OSINT": "OSINT",
    "Web": "Web",

    # --- Descriptions ---
    "Analysez les paramètres d’une URL pour rechercher des failles XSS.":
        "Analyze a URL's parameters to find XSS flaws.",
    "Analysez les paramètres d’une URL pour rechercher des injections SQL.":
        "Analyze a URL's parameters to find SQL injections.",
    "Cartographiez les sous-domaines et les informations DNS.":
        "Map subdomains and DNS information.",
    "Consultez le statut HTTP et les en-têtes renvoyés par un site.":
        "View the HTTP status and headers returned by a site.",
    "Consultez les informations d’enregistrement auprès du serveur Whois.":
        "Look up registration information from the Whois server.",
    "Explorez les chemins d’un site à partir d’une liste de mots.":
        "Explore a site's paths from a wordlist.",
    "Explorez les liens et ressources d’un site.":
        "Crawl a site's links and resources.",
    "Identifiez les ports TCP ouverts sur une cible.":
        "Identify open TCP ports on a target.",
    "Interrogez les enregistrements DNS ; le moteur dnspython est intégré.":
        "Query DNS records; the dnspython engine is bundled.",
    "Recherchez des répertoires et des ressources web.":
        "Search for web directories and resources.",
    "Recherchez des sous-domaines à partir de sources publiques.":
        "Search for subdomains from public sources.",
    "Relevez le statut HTTP, le titre et les technologies d’un site.":
        "Read a site's HTTP status, title and technologies.",
    "Repérez les ports TCP accessibles.":
        "Detect reachable TCP ports.",
    "Repérez les ports TCP puis transmettez les résultats à Nmap.":
        "Detect TCP ports then pass the results to Nmap.",
    "Retrouvez les URL archivées par la Wayback Machine.":
        "Retrieve URLs archived by the Wayback Machine.",
    "Retrouvez les URL connues d’un domaine dans les archives publiques.":
        "Retrieve a domain's known URLs from public archives.",
    "Résolvez les adresses IPv4 et IPv6 d’une cible avec le résolveur système.":
        "Resolve a target's IPv4 and IPv6 addresses with the system resolver.",
    "Vérifiez le certificat, sa validité et la connexion TLS d’un service.":
        "Check a service's certificate, its validity and the TLS connection.",
    "Vérifiez l’environnement de l’application, sans connexion réseau.":
        "Check the application's environment, without a network connection.",
    "Vérifiez un site avec les modèles Nuclei.":
        "Scan a site with Nuclei templates.",

    # --- Notes ---
    " Installation intégrée, version 1.10.9.": " Bundled installation, version 1.10.9.",
    " Installation intégrée, version 2.4.2.": " Bundled installation, version 2.4.2.",
    " Installation intégrée, version v0.1.0.": " Bundled installation, version v0.1.0.",
    " Installation intégrée, version v1.7.0.": " Bundled installation, version v1.7.0.",
    " Installation intégrée, version v2.2.4.": " Bundled installation, version v2.2.4.",
    " Installation intégrée, version v2.6.1.": " Bundled installation, version v2.6.1.",
    " Installation intégrée, version v3.11.1. Les modèles sont téléchargés lors du premier usage.":
        " Bundled installation, version v3.11.1. Templates are downloaded on first use.",
    " Installation intégrée, version v3.2.3.": " Bundled installation, version v3.2.3.",
    " Installation intégrée, version v5.1.1. Un moteur de collecte Amass configuré doit être accessible à l’URL indiquée.":
        " Bundled installation, version v5.1.1. A configured Amass collection engine must be reachable at the given URL.",
    "Exécution Linux intégrée. Configurez et vérifiez Linux local, WSL ou SSH dans les paramètres.":
        "Bundled Linux execution. Configure and verify local Linux, WSL or SSH in the settings.",
    "Exécution sur cet ordinateur Windows. Les résultats décrivent ce PC, pas une cible distante. Installation intégrée, version 20260927-30e48b1d.":
        "Runs on this Windows computer. Results describe this PC, not a remote target. Bundled installation, version 20260927-30e48b1d.",
    "Inclus dans l’application. Aucune installation supplémentaire.":
        "Bundled in the application. No additional installation.",
    "Installez Nmap avec son assistant officiel. Npcap et les droits administrateur sont requis pour certains profils SYN, UDP et système. Les profils TCP connect fonctionnent sans capture brute. Installation intégrée, version 7.991.":
        "Install Nmap with its official installer. Npcap and administrator rights are required for some SYN, UDP and system profiles. TCP connect profiles work without raw capture. Bundled installation, version 7.991.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée.":
        "Native profiles. A Linux distribution can also be selected.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée. Installation intégrée, version 0.13.1.":
        "Native profiles. A Linux distribution can also be selected. Bundled installation, version 0.13.1.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée. Installation intégrée, version 1.31.0.":
        "Native profiles. A Linux distribution can also be selected. Bundled installation, version 1.31.0.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée. Installation intégrée, version 1.9.0.":
        "Native profiles. A Linux distribution can also be selected. Bundled installation, version 1.9.0.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée. Installation intégrée, version 165a3910efcc.":
        "Native profiles. A Linux distribution can also be selected. Bundled installation, version 165a3910efcc.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée. Installation intégrée, version ab27955d3674.":
        "Native profiles. A Linux distribution can also be selected. Bundled installation, version ab27955d3674.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée. Installation intégrée, version dc8c0c07952e.":
        "Native profiles. A Linux distribution can also be selected. Bundled installation, version dc8c0c07952e.",
    "Profils natifs. Une distribution Linux peut également être sélectionnée. Installation intégrée, version v7.1.2. Un pilote GPU/OpenCL compatible est requis.":
        "Native profiles. A Linux distribution can also be selected. Bundled installation, version v7.1.2. A compatible GPU/OpenCL driver is required.",
    "Scanner natif. Les profils CLI avec détection de services nécessitent aussi Nmap. Le profil autonome fonctionne sans Nmap. Installation intégrée, version 2.4.1.":
        "Native scanner. CLI profiles with service detection also require Nmap. The standalone profile works without Nmap. Bundled installation, version 2.4.1.",
    "Sélectionnez ffuf et une liste de mots pour ce profil. Installation intégrée, version v2.3.0.":
        "Select ffuf and a wordlist for this profile. Bundled installation, version v2.3.0.",
    "Sélectionnez gobuster et une liste de mots pour ce profil. Installation intégrée, version v3.8.2.":
        "Select gobuster and a wordlist for this profile. Bundled installation, version v3.8.2.",
    "Sélectionnez la version de Subfinder adaptée à votre système. Installation intégrée, version v2.16.0.":
        "Select the Subfinder build suited to your system. Bundled installation, version v2.16.0.",
    "Utilisez httpx de ProjectDiscovery, pas la bibliothèque Python du même nom. Installation intégrée, version v1.12.0.":
        "Use ProjectDiscovery's httpx, not the Python library of the same name. Bundled installation, version v1.12.0.",

    # --- Libellés de profils (français) ---
    "100 ports TCP courants": "Top 100 common TCP ports",
    "100 ports courants (TCP connect)": "Top 100 common ports (TCP connect)",
    "Configurer la clé API Shodan": "Configure the Shodan API key",
    "Détection des technologies": "Technology detection",
    "Détection standard": "Standard detection",
    "Essayer toutes les signatures": "Try all signatures",
    "Inclure les sous-domaines": "Include subdomains",
    "Informations système de ce PC": "System information of this PC",
    "Lire les en-têtes (HEAD)": "Read the headers (HEAD)",
    "Port de la cible": "Target port",
    "Port de la cible (TCP connect)": "Target port (TCP connect)",
    "Port de la cible, sans Nmap": "Target port, without Nmap",
    "Ports personnalisés": "Custom ports",
    "Profondeur personnalisée": "Custom depth",
    "Requête Whois": "Whois query",
    "Répertoires avec filtre de taille": "Directories with size filter",
    "Répertoires web": "Web directories",
    "Sources personnalisées": "Custom sources",
    "URL archivées": "Archived URLs",
    "URL du domaine": "Domain URLs",
    "Vulnérabilités critiques et élevées": "Critical and high vulnerabilities",
    "Vérifier cet ordinateur": "Check this computer",
    "Vérifier le certificat": "Check the certificate",
    "Énumération avec moteur Amass": "Enumeration with Amass engine",
    "Énumération complète de ce PC": "Full enumeration of this PC",

    # --- Libellés de champs (dialogue de lancement) ---
    "Clé API": "API key",
    "Fichier d’utilisateurs": "Users file",
    "Profondeur (1 à 10)": "Depth (1 to 10)",
    "Sources séparées par des virgules": "Comma-separated sources",
    "Taille à ignorer": "Size to ignore",
}
