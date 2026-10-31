"""Traductions FR→EN des dialogues et du panneau des attack flows.
Fusionné dans le dictionnaire principal de i18n.
"""

UI = {
    # --- Dialogue de lancement ---
    "Configurer ": "Configure ",
    "Moteur intégré": "Bundled engine",
    "Natif · ": "Native · ",
    "Environnement Linux configuré": "Configured Linux environment",
    "Profil": "Profile",
    "Cible (selon le profil)": "Target (per profile)",
    "COMMANDE": "COMMAND",
    "Copier": "Copy",
    "Copié": "Copied",
    "Liste de mots": "Wordlist",
    "Parcourir…": "Browse…",
    "Fichier d’entrée": "Input file",
    "Opération locale à l’environnement choisi ; aucune cible réseau enregistrée nécessaire.":
        "Local operation to the chosen environment; no saved network target required.",
    "Session interactive dans l’onglet Exécution.": "Interactive session in the Execution tab.",
    "Ce profil nécessite Npcap et peut nécessiter des droits administrateur.":
        "This profile requires Npcap and may need administrator rights.",
    "Ce profil nécessite les droits administrateur ; sudo peut demander son mot de passe sous Linux.":
        "This profile requires administrator rights; sudo may ask for its password on Linux.",
    "Fichiers d’entrée et fichiers de résultats sur la machine SSH.":
        "Input files and result files on the SSH machine.",
    "Interface Wi-Fi Linux et pilotes compatibles requis pour la capture et le mode moniteur.":
        "Linux Wi-Fi interface and compatible drivers required for capture and monitor mode.",

    # --- Validation des profils ---
    "{field} : valeur requise, sans caractère de contrôle.": "{field}: a value is required, without control characters.",
    "Une valeur ne peut pas commencer par une option (-).": "A value cannot start with an option (-).",
    "Indiquez un chemin Linux absolu sur la machine SSH.": "Provide an absolute Linux path on the SSH machine.",
    "Fichier introuvable : {path}": "File not found: {path}",
    "Choisissez un simple nom de fichier ; la sortie sera dans le dossier de cette opération.": "Choose a plain filename; output will be saved in this operation’s folder.",
    "{field} : caractères non autorisés.": "{field}: invalid characters.",
    "{field} : valeur numérique invalide.": "{field}: invalid numeric value.",
    "BSSID invalide.": "Invalid BSSID.",
    "Adresse IP invalide : {value}": "Invalid IP address: {value}",
    "Choisissez une cible.": "Choose a target.",
    "Ce profil attend un nom de domaine, pas une adresse IP.": "This profile requires a domain name, not an IP address.",
    "Liste de ports invalide.": "Invalid port list.",
    "Plage de ports invalide.": "Invalid port range.",

    # --- Panneau des attack flows ---
    "Éditeur de flow": "Flow editor",
    "Nom du flow": "Flow name",
    "Description": "Description",
    "Ajouter": "Add",
    "Monter": "Up",
    "Descendre": "Down",
    "Retirer": "Remove",
    "Flow invalide": "Invalid flow",
    "Créer": "Create",
    "Modifier / copier": "Edit / copy",
    "Cible du flow": "Flow target",
    "Ajouter une cible…": "Add a target…",
    "Importer CLI…": "Import CLI…",
    "Exporter…": "Export…",
    "Supprimer": "Delete",
    "Résultats du flow": "Flow results",
    "Chaque étape reste configurable avant lancement. Une étape indisponible n’est jamais exécutée silencieusement.":
        "Each step stays configurable before launch. An unavailable step is never run silently.",
    "Configurer et exécuter l’étape": "Configure and run the step",
    "Exécuter tout le flow": "Run the whole flow",
    "Passer cette étape": "Skip this step",
    "Nouvelle session": "New session",
    "Préparer le flow": "Prepare the flow",
    "Renseignez une fois les champs requis. Les étapes disponibles s’enchaînent ensuite automatiquement.":
        "Fill in the required fields once. Available steps then chain automatically.",
    "Confirmer chaque étape (pas-à-pas)": "Confirm each step (step by step)",
    "Exécuter le flow": "Run the flow",
    "Commande complétée au lancement.": "Command completed at launch.",
    "Flow {name} — étape {i}/{n}": "Flow {name} — step {i}/{n}",
    "hôte {k}/{n}": "host {k}/{n}",
    "Étape %v/%m": "Step %v/%m",
    "Étape terminée. Lancement de la suivante…": "Step done. Launching the next one…",
    "Flow terminé : toutes les étapes ont réussi.": "Flow complete: every step succeeded.",
    "Toutes les étapes sont déjà terminées.": "All steps are already complete.",
    "Champs enregistrés. Lancez chaque étape avec « Configurer et exécuter l’étape ».":
        "Fields saved. Launch each step with “Configure and run the step”.",
    "Enchaînement interrompu : ": "Chaining interrupted: ",
    "Flows personnalisés non chargés : ": "Custom flows not loaded: ",
    "\nCible : ": "\nTarget: ",
    "Ajoutez une cible pour ce flow": "Add a target for this flow",
    "À faire": "To do",
    "Échec — relançable": "Failed — retryable",
    "Arrêté — relançable": "Stopped — retryable",
    "Passé": "Skipped",
    "Résultat supprimé — relançable": "Result deleted — retryable",
    "Changer la cible du flow": "Change the flow target",
    "Créer une nouvelle session pour cette cible ? Les résultats de la précédente session sont conservés.":
        "Create a new session for this target? The previous session's results are kept.",
    "Ajoutez et sélectionnez une cible dans la liste Cible du flow.":
        "Add and select a target in the Flow target list.",
    "Étape non lancée": "Step not started",
    "Cible requise": "Target required",
    "Étape terminée. Consultez les résultats puis choisissez la suivante.":
        "Step done. Review the results then choose the next one.",
    "Étape arrêtée ou en échec. Relancez-la, passez-la ou ouvrez son journal.":
        "Step stopped or failed. Re-run it, skip it or open its log.",
    "Flow non enregistré": "Flow not saved",
    "Importer custom_flows.json": "Import custom_flows.json",
    "Import impossible": "Import failed",
    "Exporter un flow": "Export a flow",
    "Export impossible": "Export failed",
    "Flow fourni": "Bundled flow",
    "Les flows fournis sont conservés. Vous pouvez les dupliquer puis modifier leur copie.":
        "Bundled flows are kept. You can duplicate them then edit the copy.",
    "Supprimer ce flow": "Delete this flow",
    "Supprimer ce flow personnalisé ? Ses journaux seront conservés.":
        "Delete this custom flow? Its logs are kept.",
    "Suppression impossible": "Delete failed",
}
