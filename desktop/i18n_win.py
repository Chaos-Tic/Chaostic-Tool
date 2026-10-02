"""Traductions FR→EN des chaînes de la fenêtre principale (window.py) :
messages, boîtes de dialogue, boutons et libellés non couverts par les autres
dictionnaires. Fusionné dans le dictionnaire principal de i18n.
"""

WIN = {
    # --- Accueil / journal ---
    "Aucune opération pour le moment. Lancez le diagnostic local pour essayer.":
        "No operation yet. Run the local diagnostic to give it a try.",
    "JOURNAL DES OPÉRATIONS": "OPERATIONS LOG",
    "Tout voir  »": "See all  »",
    "Journal enregistré automatiquement": "Log saved automatically",

    # --- Cibles ---
    "Retrouvez vos environnements et choisissez la cible utilisée par défaut.":
        "Find your environments and choose the default target.",
    "Définir comme cible active": "Set as active target",
    "Les résultats restent dans l’historique.": "Results stay in the history.",
    "Un domaine, une adresse IP ou une URL complète.\nL’ajout n’effectue aucune connexion réseau.":
        "A domain, an IP address or a full URL.\nAdding it makes no network connection.",
    "Cible non enregistrée": "Target not saved",
    "Retirer « {label} » ? Les résultats seront conservés.":
        "Remove “{label}”? The results will be kept.",
    "Cet ordinateur / opérations locales": "This computer / local operations",
    "Environnement local sélectionné": "Local environment selected",

    # --- Arsenal / exécution ---
    "Téléchargement officiel  »": "Official download  »",
    "Retour au flow  »": "Back to flow  »",
    "Arrêter l’opération": "Stop the operation",
    "Chaque opération conserve sa cible, son état et son journal complet.":
        "Each operation keeps its target, its status and its full log.",
    "Vérification de l’environnement Linux": "Checking the Linux environment",
    "Dépendances Linux": "Linux dependencies",
    "Préparation Linux": "Linux setup",
    "Outil Linux non détecté. Configurez Linux et actualisez son inventaire dans les paramètres.":
        "Linux tool not detected. Configure Linux and refresh its inventory in the settings.",
    "Outil natif non installé pour ce système. Utilisez Installer cet outil, sélectionnez son programme ou choisissez Linux.":
        "Native tool not installed for this system. Use Install this tool, select its program or choose Linux.",
    "Empreinte de l’installateur invalide.": "Invalid installer fingerprint.",
    "Ce profil RustScan appelle Nmap. Installez Nmap depuis la boîte à outils, ou choisissez le profil « Port de la cible, sans Nmap ».":
        "This RustScan profile calls Nmap. Install Nmap from the toolbox, or choose the “Target port, without Nmap” profile.",
    "Assistant officiel ouvert. Terminez l’installation puis cliquez sur Actualiser dans la boîte à outils.":
        "Official installer opened. Finish the installation then click Refresh in the toolbox.",
    "\nDernier échec : ": "\nLast failure: ",

    # --- Historique ---
    "Supprimer ce résultat…": "Delete this result…",
    "Vider l’historique…": "Clear the history…",
    "Réinitialiser filtres": "Reset filters",
    "Supprimer ce résultat": "Delete this result",
    "Supprimer définitivement le résultat de {tool} ({preset}) et ses fichiers locaux ? Les autres résultats, cibles et réglages sont conservés.":
        "Permanently delete the result of {tool} ({preset}) and its local files? Other results, targets and settings are kept.",
    "Suppression incomplète": "Incomplete deletion",
    "Résultat supprimé": "Result deleted",
    "Résultat local supprimé.": "Local result deleted.",
    "Vider tout l’historique": "Clear the whole history",
    "Supprimer définitivement TOUT l’historique local, même les opérations masquées par la recherche, ainsi que leurs journaux et fichiers de résultats ?\n\nLes cibles, paramètres, outils installés et WSL sont conservés. Les exports copiés ailleurs et les résultats stockés sur Linux/SSH ne sont pas supprimés. Cette action est irréversible.":
        "Permanently delete ALL local history, including operations hidden by the search, along with their logs and result files?\n\nTargets, settings, installed tools and WSL are kept. Exports copied elsewhere and results stored on Linux/SSH are not deleted. This action is irreversible.",
    "Historique non vidé": "History not cleared",
    "Aucune opération": "No operation",
    "Historique vidé": "History cleared",
    "Historique local et résultats supprimés. Cibles et paramètres conservés.":
        "Local history and results deleted. Targets and settings kept.",
    "[Aperçu limité. Exportez le journal pour lire le fichier complet.]":
        "[Preview limited. Export the log to read the full file.]",
    "Journal indisponible : {error}": "Log unavailable: {error}",
    "Exporter le journal": "Export the log",
    "Texte (*.txt)": "Text (*.txt)",
    "Journal exporté.": "Log exported.",
    "Export impossible": "Export failed",
    "{shown} résultat(s) affiché(s) sur {total}": "{shown} result(s) shown of {total}",
    "{state} · Code de sortie : {code} · Résultats conservés":
        "{state} · Exit code: {code} · Results kept",

    # --- Fermeture / opération en cours ---
    "Arrêter l’opération et fermer l’application ? Les résultats partiels seront conservés.":
        "Stop the operation and close the application? Partial results will be kept.",
    " Une activation Windows ou une installation Linux déjà lancée peut continuer en arrière-plan ; attendez sa fin avant de reprendre.":
        " A Windows activation or a Linux installation already started may continue in the background; wait for it to finish before resuming.",
    "Opération en cours": "Operation in progress",
    "Interrompre le suivi ? Une activation Windows élevée ou un téléchargement Linux déjà lancé peut continuer en arrière-plan. Attendez sa fin avant de reprendre.":
        "Stop tracking? An elevated Windows activation or a Linux download already started may continue in the background. Wait for it to finish before resuming.",
    "Redémarrage Windows requis — reprenez après redémarrage":
        "Windows restart required — resume after restarting",
    "Préparation en attente — Kali n’est pas encore disponible":
        "Setup pending — Kali is not available yet",

    # --- Installateurs natifs ---
    "Installateur": "Installer",
    "Installation des paquets Linux": "Installing Linux packages",
    "Paquets Kali/Debian": "Kali/Debian packages",
    "Paquets Linux": "Linux packages",
    "Windows uniquement": "Windows only",
    "Installation Linux": "Linux installation",
    "Environnement Linux": "Linux environment",
    "Inventaire": "Inventory",
    "Programme Linux": "Linux program",
    "Chemin absolu du programme dans Linux :": "Absolute path of the program in Linux:",
    "Chemin invalide": "Invalid path",
    "Indiquez un chemin Linux absolu.": "Provide an absolute Linux path.",
    "Lancement impossible": "Launch failed",
    "Cible : ": "Target: ",
    " · En cours": " · In progress",

    # --- Mises à jour ---
    "Mise à jour disponible : Desktop {version}.": "Update available: Desktop {version}.",
    " Ouvrez la page de téléchargement pour l’installer.":
        " Open the download page to install it.",
    "Desktop {version} est disponible (vous avez {current}).":
        "Desktop {version} is available (you have {current}).",
    "Ouvrir la page de téléchargement ?": "Open the download page?",
    "Vous utilisez déjà la dernière version (Desktop {current}).":
        "You are already on the latest version (Desktop {current}).",
    "Impossible de vérifier les mises à jour pour le moment.":
        "Unable to check for updates at the moment.",

    # --- Réglages (paragraphes) ---
    "Linux local utilise ce PC. WSL utilise la distribution sélectionnée. SSH utilise votre propre machine ou VM ; aucun serveur n’est imposé. Les pilotes Wi-Fi et interfaces doivent exister dans cet environnement.":
        "Local Linux uses this PC. WSL uses the selected distribution. SSH uses your own machine or VM; no server is imposed. Wi-Fi drivers and interfaces must exist in that environment.",
    "Cibles, paramètres et journaux sont enregistrés séparément du programme. Une mise à niveau conserve ces données.":
        "Targets, settings and logs are stored separately from the program. An upgrade keeps this data.",
    "Installez le pack natif depuis la boîte à outils, ou choisissez chaque outil séparément. Les versions sont conservées dans votre dossier de données. Les archives portables sont vérifiées par SHA-256. Les outils Python utilisent chacun un environnement isolé. Si nécessaire, un Python compatible est téléchargé et vérifié automatiquement.":
        "Install the native pack from the toolbox, or choose each tool separately. Versions are kept in your data folder. Portable archives are verified by SHA-256. Python tools each use an isolated environment. If needed, a compatible Python is downloaded and verified automatically.",

    # --- Statut backend ---
    " outils détectés · ": " tools detected · ",
    "Connexion non vérifiée": "Connection not verified",

    # --- Dialogue Ajouter une cible ---
    "Nouvelle cible": "New target",
    "Nom (facultatif)": "Name (optional)",
    "Adresse": "Address",

    # --- Chaînes FR sans accent (boutons / titres / groupes) ---
    "Retirer la cible": "Remove the target",
    "Envoyer": "Send",
    "Ouvrir le dossier": "Open the folder",
    "Exporter le journal…": "Export the log…",
    "Outils externes": "External tools",
}
