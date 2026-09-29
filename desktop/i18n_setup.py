"""Traductions FR→EN des dialogues d'environnement Linux (backend_dialog.py)
et de la préparation WSL (wsl_setup.py). Fusionné dans i18n.
"""

SETUP = {
    # --- Dialogue Environnement Linux ---
    "Linux local, WSL ou une machine Linux SSH : aucune machine personnelle n’est préconfigurée. SSH utilise votre clé et vérifie la clé d’hôte connue. Python 3 doit être disponible côté Linux.":
        "Local Linux, WSL or an SSH Linux machine: no personal machine is preconfigured. SSH uses your key and verifies the known host key. Python 3 must be available on the Linux side.",
    "Linux sur cet ordinateur": "Linux on this computer",
    "Distribution WSL": "WSL distribution",
    "Machine ou VM Linux en SSH": "Linux machine or VM over SSH",
    "Hôte SSH": "SSH host",
    "Utilisateur SSH": "SSH user",
    "Port SSH": "SSH port",
    "Clé privée SSH (facultative)": "SSH private key (optional)",
    "Fichier known_hosts (facultatif)": "known_hosts file (optional)",
    "Les fichiers d’entrée SSH doivent déjà exister sur la machine Linux : indiquez leur chemin absolu dans le formulaire du profil. Les résultats fichiers restent dans ~/.local/share/ChaosticTool/runs sur cette machine ; le journal est conservé dans l’application.":
        "SSH input files must already exist on the Linux machine: give their absolute path in the profile form. File results stay in ~/.local/share/ChaosticTool/runs on that machine; the log is kept in the application.",

    # --- Préparation WSL : messages et étapes ---
    "Redémarrage Windows requis. Enregistrez votre travail, redémarrez manuellement le PC, puis relancez ChaosticTool et reprenez la préparation. Kali sera installée avant sa configuration.":
        "Windows restart required. Save your work, restart the PC manually, then relaunch ChaosticTool and resume the setup. Kali will be installed before it is configured.",
    "Commande interrompue (code {code}). Consultez le journal, puis reprenez la préparation.":
        "Command interrupted (code {code}). Check the log, then resume the setup.",
    "Cette préparation nécessite Windows.": "This setup requires Windows.",
    "La préparation automatique nécessite Windows 10 version 2004 (build 19041) ou Windows 11.":
        "Automatic setup requires Windows 10 version 2004 (build 19041) or Windows 11.",
    "Détection de WSL": "Detecting WSL",
    "Activation de WSL — validation administrateur Windows":
        "Enabling WSL — Windows administrator approval",
    "WSL ne répond pas encore. Redémarrez Windows, puis relancez ChaosticTool pour reprendre. Vérifiez aussi la virtualisation si Windows le demande.":
        "WSL is not responding yet. Restart Windows, then relaunch ChaosticTool to resume. Also check virtualization if Windows asks for it.",
    "Téléchargement de Kali Linux": "Downloading Kali Linux",
    "WSL ne permet pas encore de vérifier Kali. Si Windows demande un redémarrage, redémarrez puis reprenez la préparation. Aucun paquet Linux n’a été lancé.":
        "WSL cannot verify Kali yet. If Windows asks for a restart, restart then resume the setup. No Linux package was started.",
    "Kali n’est pas encore enregistrée dans WSL. Si Windows a demandé un redémarrage, redémarrez puis reprenez la préparation ; sinon consultez le journal d’installation. Aucun paquet Linux n’a été lancé.":
        "Kali is not registered in WSL yet. If Windows asked for a restart, restart then resume the setup; otherwise check the installation log. No Linux package was started.",
    "Préparation de Python et du compte Linux": "Preparing Python and the Linux account",
    "Le compte Linux applicatif doit être un compte non administrateur.":
        "The application Linux account must be a non-administrator account.",
    "Installation de Nmap, RustScan et des utilitaires réseau":
        "Installing Nmap, RustScan and network utilities",
    "Connexion et inventaire": "Connection and inventory",
    "Environnement prêt. Le catalogue indique les outils réellement disponibles.":
        "Environment ready. The catalog shows the tools actually available.",
    "À reprendre": "To resume",

    # --- Dialogue de consentement ---
    "Redémarrage Windows requis": "Windows restart required",
    "Préparer mon environnement Linux": "Prepare my Linux environment",
    "ChaosticTool va installer WSL si nécessaire, télécharger Kali Linux, préparer Python et connecter le catalogue automatiquement.\n\nUne connexion Internet, plusieurs Go libres et parfois un redémarrage sont nécessaires. Windows peut afficher une demande administrateur.\n\nSi Kali est déjà présent, Python et les paquets choisis pourront être mis à jour et un compte applicatif non administrateur sera ajouté. Les autres distributions et la distribution par défaut restent inchangées. WSL et Kali seront conservés si vous désinstallez ChaosticTool.":
        "ChaosticTool will install WSL if needed, download Kali Linux, prepare Python and connect the catalog automatically.\n\nAn internet connection, several free GB and sometimes a restart are required. Windows may show an administrator prompt.\n\nIf Kali is already present, Python and the chosen packages can be updated and a non-administrator application account will be added. Other distributions and the default distribution stay unchanged. WSL and Kali are kept if you uninstall ChaosticTool.",
    "Installer aussi Nmap, RustScan, DNS et Whois": "Also install Nmap, RustScan, DNS and Whois",
    "Préparer automatiquement": "Prepare automatically",
    "Plus tard": "Later",
    "Préparation automatique de Linux": "Automatic Linux setup",
    "Préparation WSL": "WSL setup",
    "Cet ordinateur": "This computer",

    # --- Point d'entrée (chaostic_desktop.py) ---
    "L’application est déjà ouverte pour cet espace de travail.":
        "The application is already open for this workspace.",
    "Erreur": "Error",
    "{error}\n\nLes détails sont conservés dans desktop-errors.log.":
        "{error}\n\nDetails are kept in desktop-errors.log.",

    # --- Backend Linux (backends.py) ---
    "Inventaire Linux invalide.": "Invalid Linux inventory.",
    "Connexion vérifiée. {count} outils Linux détectés.":
        "Connection verified. {count} Linux tools detected.",
    "Interfaces : ": "Interfaces: ",
}
