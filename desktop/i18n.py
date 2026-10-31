"""Traduction légère FR→EN pour l'interface, sans dépendance à Qt Linguist.

L'app est écrite avec des libellés français comme source. `T(fr)` renvoie la
traduction anglaise (langue par défaut) ou la chaîne française si la langue
active est le français, avec repli sur le français si une clé manque.

La langue s'applique en recréant la fenêtre principale : les libellés passent
tous par `T()` (directement, ou via les helpers `label()`/`button()`).
"""
from __future__ import annotations

_LANG = "en"  # anglais par défaut

# Dictionnaire FR -> EN. Toute chaîne d'interface enveloppée par T() doit y figurer
# (sinon repli sur le français). Regroupé par zone pour la maintenance.
FR_EN = {
    "Remplacer cette AppImage par la version vérifiée ? L’ancienne version sera conservée.": "Replace this AppImage with the verified version? The previous version will be kept.",
    "AppImage mise à jour. Fermez puis relancez l’application.": "AppImage updated. Close and restart the application.",
    " Utilisez le bouton Mettre à jour pour continuer.": " Use Update to continue.",
    "Terminez l’opération en cours avant de mettre à jour l’application.": "Finish the current operation before updating the application.",
    "Ouvrir un terminal pour exécuter la mise à jour ?": "Open a terminal to run the package update?",
    "Exécutez cette commande dans votre terminal, puis redémarrez l’application :": "Run this command in your terminal, then restart the application:",
    "Télécharger, vérifier puis ouvrir l’installateur depuis GitHub ?": "Download, verify and open the installer from GitHub?",
    "Téléchargement et vérification de l’installateur…": "Downloading and verifying the installer…",
    "La mise à jour n’a pas été installée.": "The update was not installed.",
    "Installateur vérifié. Suivez les étapes d’installation, puis redémarrez l’application.": "Installer verified. Follow the installation steps, then restart the application.",
    "Ouvrez l’installateur vérifié :": "Open the verified installer:",
    "Vérifier automatiquement les mises à jour": "Automatically check for updates",
    "Une requête anonyme par jour vers GitHub. GitHub voit votre adresse IP. Aucun téléchargement sans votre accord.": "One anonymous request per day to GitHub. GitHub sees your IP address. No download without your consent.",
    "Mettre à jour…": "Update…",
    "VOTRE ESPACE DE TRAVAIL": "YOUR WORKSPACE",
    "Votre prochaine opération,\nbien préparée.": "Your next operation,\nthoughtfully prepared.",
    "Cibles, outils et résultats, réunis dans un espace clair.": "Targets, tools and results, together in one clear workspace.",
    "ESPACES DE TRAVAIL": "WORKSPACES",
    "Réduire la transparence": "Reduce transparency",
    "Sous-domaines": "Subdomains",
    "Pour une cible de type domaine, énumérez les sous-domaines (subfinder/amass) : les outils visant un hôte s’exécuteront sur la cible et sur chaque sous-domaine.": "For a domain target, enumerate its subdomains (subfinder/amass): host-targeted tools will run against the target and each subdomain.",
    "Inclure les sous-domaines dans les analyses": "Include subdomains in scans",
    "Énumérer les sous-domaines": "Enumerate subdomains",
    "Définissez une cible active.": "Set an active target.",
    "La cible active n’est pas un domaine ; les sous-domaines ne s’appliquent pas.": "The active target is not a domain; subdomains do not apply.",
    "Énumération en cours…": "Enumeration in progress…",
    "{n} sous-domaines en cache.": "{n} subdomains cached.",
    "Aucun sous-domaine en cache — lancez l’énumération.": "No subdomains cached — run the enumeration.",
    "Installez subfinder (recommandé) ou amass pour énumérer les sous-domaines.": "Install subfinder (recommended) or amass to enumerate subdomains.",
    "{n} sous-domaines trouvés via {s}.": "{n} subdomains found via {s}.",
    "Aucun sous-domaine trouvé.": "No subdomains found.",
    "Clés API": "API keys",
    "Certains outils embarqués utilisent une clé API. Enregistrez-la ici une fois : elle est conservée dans le coffre de clés sécurisé du système d’exploitation (chiffrée au repos), jamais en clair sur le disque.": "Some bundled tools use an API key. Save it here once: it is kept in the operating system's secure key store (encrypted at rest), never in clear text on disk.",
    "Aucun coffre de clés sécurisé n’est disponible sur ce système : les clés ne seront gardées que pour cette session.": "No secure key store is available on this system: keys will only be kept for this session.",
    "Clé ou jeton": "Key or token",
    "Afficher les clés": "Show the keys",
    "Enregistrer les clés": "Save the keys",
    "Clés API enregistrées.": "API keys saved.",
    "Clés gardées pour cette session (aucun coffre sécurisé).": "Keys kept for this session (no secure store).",
    "Recherche passive Shodan (sans scan — nécessite la clé API Shodan)": "Shodan passive lookup (no scan — needs Shodan API key)",
    "Ce profil nécessite la clé API {name}. Enregistrez-la dans Paramètres → Clés API.": "This profile needs the {name} API key. Save it in Settings → API keys.",
    "VOTRE CIBLE. VOS OUTILS. VOTRE SESSION.":"YOUR TARGET. YOUR TOOLS. YOUR SESSION.",
    "ÉTAT LOCAL":"LOCAL STATE",
    "// ESPACES DE TRAVAIL":"// WORKSPACES",
    "SORTIE DE L’OPÉRATION":"OPERATION OUTPUT",
    "OPÉRATION": "OPERATION",
    "Votre cible. Vos outils. Votre session.": "Your target. Your tools. Your session.",
    "RECONNAISSANCE / EXÉCUTION / RÉSULTATS": "RECON / EXECUTION / EVIDENCE",

    # --- Fenêtre, entête, navigation ---
    "ChaosticTool Desktop": "ChaosticTool Desktop",
    "CHAOSTICTOOL  ·  DESKTOP": "CHAOSTICTOOL  ·  DESKTOP",
    "OPERATOR / LOCAL": "OPERATOR / LOCAL",
    "Centre de contrôle": "Control center",
    "Cibles": "Targets",
    "Arsenal d’outils": "Tool arsenal",
    "Exécution": "Execution",
    "Historique": "History",
    "Paramètres": "Settings",
    "Attack flows": "Attack flows",
    "  Centre de contrôle": "  Control center",
    "  Cibles": "  Targets",
    "  Arsenal d’outils": "  Tool arsenal",
    "  Historique": "  History",
    "  Paramètres": "  Settings",
    "  Attack flows": "  Attack flows",
    "Vos cibles": "Your targets",
    "Vos données restent sur cet ordinateur": "Your data stays on this computer",
    "+  Ajouter une cible": "+  Add a target",
    "Ajouter une cible": "Add a target",
    "  Mode sombre": "  Dark mode",
    "  Mode clair": "  Light mode",
    "Ouvrir mes fichiers": "Open my files",
    "DECK  /  ": "DECK  /  ",
    " DESKTOP": " DESKTOP",

    # --- Accueil / hero / missions ---
    "ChaosticTool": "ChaosticTool",
    "Préparez votre\nprochaine opération.": "Prepare your\nnext operation.",
    "Votre cible, votre arsenal, vos décisions —\ntoutes vos opérations au même endroit.":
        "Your target, your arsenal, your decisions —\nall your operations in one place.",
    "Ouvrir l’arsenal": "Open the arsenal",
    "01  /  CIBLES\nPRÉPARER": "01  /  TARGETS\nPREPARE",
    "02  /  ARSENAL\nSÉLECTIONNER": "02  /  ARSENAL\nSELECT",
    "03  /  HISTORIQUE\nCONSULTER": "03  /  HISTORY\nREVIEW",
    "CIBLES": "TARGETS",
    "Environnements enregistrés": "Saved environments",
    "ARSENAL PRÊT": "ARSENAL READY",
    "Outils inclus ou détectés": "Bundled or detected tools",
    "OPÉRATIONS": "OPERATIONS",
    "Journaux conservés localement": "Logs kept locally",
    "Aucune cible": "No target",
    "Ajoutez votre premier environnement.": "Add your first environment.",
    "CIBLE ACTIVE / PROCHAINE OPÉRATION": "ACTIVE TARGET / NEXT OPERATION",

    # --- Boutons / actions génériques ---
    "Actualiser": "Refresh",
    "Installer des outils": "Install tools",
    "Attack flows  »": "Attack flows  »",
    "Rechercher un outil, une fonction…": "Search a tool or function…",
    "Rechercher un outil": "Search a tool",
    "Toutes les phases": "All phases",
    "Utilitaires intégrés": "Built-in utilities",
    "Prêts uniquement": "Ready only",
    "Choisissez un outil": "Choose a tool",
    "Configurer et lancer": "Configure and run",
    "Configurer et exécuter": "Configure and run",
    "Installer cet outil": "Install this tool",
    "Choisir l’exécutable…": "Choose the executable…",
    "Ouvrir la page de téléchargement": "Open the download page",
    "Installer côté Linux": "Install on Linux",
    "Chemin Linux personnalisé…": "Custom Linux path…",
    "Annuler": "Cancel",
    "Lancer": "Run",
    "Fermer": "Close",

    # --- En-têtes de colonnes / tableaux ---
    "OUTIL": "TOOL",
    "CATÉGORIE": "CATEGORY",
    "DISPONIBILITÉ": "AVAILABILITY",
    "OUTIL / FLOW": "TOOL / FLOW",
    "PROFIL": "PROFILE",
    "CIBLE": "TARGET",
    "ÉTAT": "STATUS",
    "DATE": "DATE",

    # --- Disponibilité (pastilles) ---
    "Inclus": "Bundled",
    "Prêt": "Ready",
    "Prêt · Linux": "Ready · Linux",
    "Service requis": "Service required",
    "Clé requise": "Key required",
    "Échec installation": "Install failed",
    "À installer": "To install",
    "À installer · Linux": "To install · Linux",
    "Linux à configurer": "Configure Linux",
    "Active": "Active",

    # --- Réglages ---
    "Apparence": "Appearance",
    "Animations immersives": "Immersive animations",
    "Environnement Linux": "Linux environment",
    "Configurer Linux / WSL / SSH…": "Configure Linux / WSL / SSH…",
    "Vérifier la connexion et les outils": "Check the connection and tools",
    "Installer WSL et Kali Linux…": "Install WSL and Kali Linux…",
    "Actualiser la détection des outils": "Refresh tool detection",
    "Choisir Python…": "Choose Python…",
    "À propos de cette version": "About this version",
    "Rechercher les mises à jour": "Check for updates",
    "Ouvrir le dépôt GitHub  »": "Open the GitHub repo  »",
    "Ouvrir le dossier de données": "Open the data folder",
    "Langue": "Language",
    "Français": "French",
    "Anglais": "English",

    # --- Exécution ---
    "Prêt pour votre prochaine opération": "Ready for your next operation",
    "Les sorties des outils apparaîtront ici en temps réel.":
        "Tool output will appear here in real time.",
    "Ouvrir les résultats": "Open the results",
    "Arrêter": "Stop",
    "Journal enregistré\nautomatiquement": "Log saved\nautomatically",

    # --- Mises à jour ---
    "Vérification…": "Checking…",
    "Mise à jour disponible": "Update available",
    "À jour": "Up to date",
    "Mise à jour": "Update",

    # --- Statut / barre du bas ---
    "PRÊT  /  Ctrl+K : arsenal  /  F6 : exécution  /  Résultats enregistrés localement":
        "READY  /  Ctrl+K: arsenal  /  F6: execution  /  Results saved locally",

    # --- Historique : filtres et états ---
    "Toutes les cibles": "All targets",
    "Tous les états": "All statuses",
    "Tous les outils": "All tools",
    "Toutes les dates": "All dates",
    "Dernières 24 h": "Last 24 h",
    "7 derniers jours": "Last 7 days",
    "30 derniers jours": "Last 30 days",
    "En cours": "Running",
    "Terminé": "Done",
    "Échec": "Failed",
    "Arrêté": "Stopped",
    "Interrompu": "Interrupted",
    "Sélectionnez une opération pour lire son journal.": "Select an operation to read its log.",

    # --- Exécution : placeholders et états ---
    "Saisie pour la session interactive…": "Input for the interactive session…",
    "Aucune opération lancée.\n\nChoisissez un outil dans la boîte à outils pour commencer.":
        "No operation started.\n\nChoose a tool from the toolbox to begin.",
    "Rechercher un outil, un profil, une cible ou un flow…":
        "Search a tool, profile, target or flow…",
    "Installation des outils": "Installing tools",
    "Téléchargement, vérification et installation · En cours":
        "Downloading, verifying and installing · In progress",
    "Arrêt en cours…": "Stopping…",
    "  Exécution · en cours": "  Execution · running",
    "  Exécution": "  Execution",
    "Aucun outil correspondant": "No matching tool",
    "Vérifier l’installation": "Check the installation",
    "Python : ": "Python: ",

    # --- Cadence / animations ---
    "Fluide · cible 60 images/s": "Smooth · target 60 fps",
    "Économe · cible 30 images/s": "Economical · target 30 fps",

    # --- Phases (catégories) ---
    "OSINT & reconnaissance passive": "OSINT & passive recon",
    "Scan réseau": "Network scan",
    "Énumération Web": "Web enumeration",
    "Vulnérabilités": "Vulnerabilities",
    "Exploitation": "Exploitation",
    "Post-exploitation & privilèges": "Post-exploitation & privileges",
    "Mots de passe": "Passwords",
    "Windows / Active Directory": "Windows / Active Directory",
    "Wi-Fi": "Wi-Fi",
    "Réseau & MITM": "Network & MITM",

    # --- Dialogue Ajouter une cible ---
    "Ex. Mon environnement de test": "e.g. My test environment",
    "https://example.com ou 127.0.0.1": "https://example.com or 127.0.0.1",
    "Ajouter la cible": "Add the target",
    "Cible enregistrée et sélectionnée.": "Target saved and selected.",

    # --- Divers réglages / statuts ---
    "Terminez l’opération en cours avant de changer de langue.":
        "Finish the current operation before changing language.",
    "Non vérifié": "Not checked",
    "\nVersion installée : ": "\nInstalled version: ",
    "outil(s) affiché(s) · états issus des exécutables natifs et de l’inventaire Linux":
        "tool(s) shown · statuses from native executables and the Linux inventory",
    "Les animations accompagnent vos actions. Les tableaux et journaux restent stables.":
        "Animations accompany your actions. Tables and logs stay stable.",
    "Ambiance lumineuse lente sur l’accueil, transitions et réactions aux interactions. Aucun balayage permanent. Désactivez les effets pour une interface statique.":
        "Slow ambient light on the home screen, transitions and reactions to interactions. No constant sweeping. Disable effects for a static interface.",
}


try:
    from desktop.i18n_catalog import CATALOG as _CATALOG
    FR_EN.update(_CATALOG)
except Exception:
    pass
try:
    from desktop.i18n_ui import UI as _UI
    FR_EN.update(_UI)
except Exception:
    pass
try:
    from desktop.i18n_win import WIN as _WIN
    FR_EN.update(_WIN)
except Exception:
    pass
try:
    from desktop.i18n_setup import SETUP as _SETUP
    FR_EN.update(_SETUP)
except Exception:
    pass


def set_language(lang: str) -> str:
    global _LANG
    _LANG = "fr" if str(lang).lower().startswith("fr") else "en"
    return _LANG


def language() -> str:
    return _LANG


def T(fr: str) -> str:
    """Traduit une chaîne source française vers la langue active."""
    if _LANG == "fr":
        return fr
    return FR_EN.get(fr, fr)
