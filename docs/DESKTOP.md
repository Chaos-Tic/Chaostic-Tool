# ChaosticTool Desktop — Windows preview 0.2.0

Une application graphique en français, avec installation par utilisateur. La CLI
Linux reste indépendante et utilise ses points d’entrée habituels.

## Installation et utilisation

1. Lancez `ChaosticTool-Setup-0.2.0-windows-x64.exe`.
2. Ouvrez **ChaosticTool Desktop** dans le menu Démarrer.
3. Essayez **Diagnostic local**, qui ne contacte aucun hôte.
4. Ajoutez une cible (domaine, IPv4, IPv6 ou URL HTTP/HTTPS).
5. Dans **Boîte à outils**, cliquez sur **Installer le pack Windows**, ou installez un outil individuellement.
6. Choisissez un outil prêt, son profil et ses paramètres, puis lancez-le.
7. Consultez le journal dans **Exécution**, puis dans **Historique**.

L’application embarque son interpréteur Python et ses bibliothèques. Python, WSL
et un terminal ne sont pas nécessaires pour utiliser les diagnostics inclus.
Cette version est destinée à Windows 10 1809 ou ultérieur, x64. Elle a été testée
sur le poste Windows de développement ; les autres versions restent à valider.
L’installateur de développement n’est pas signé.

## Périmètre de cette version

| Fonction | État |
| --- | --- |
| Interface graphique, navigation au clavier et recherche | Inclus |
| Cibles persistantes, sélection et retrait | Inclus |
| Diagnostic local | Inclus, sans accès réseau |
| Résolution DNS IPv4/IPv6 | Inclus, résolveur système |
| En-têtes HTTP | Inclus, requête HEAD, sans suivi des redirections |
| Certificat TLS | Inclus, vérification de la chaîne et du nom d’hôte |
| Nmap | Exécutable externe, profils TCP connect sans SYN |
| Subfinder, httpx, ffuf, Gobuster, Nuclei, Katana, gau, waybackurls, Dalfox, Naabu | Pack de 10 outils Windows, installation intégrée |
| WAFW00F, SQLmap | Installation Python isolée ; protection Windows susceptible de bloquer certains outils |
| Amass 5 | Binaire installable ; moteur de collecte externe non intégré, lancement désactivé |
| Historique, export du journal et ouverture des résultats | Inclus |
| Arrêt d’une opération et de ses enfants | Windows Job Object, résultats partiels conservés |
| Outils Linux non portés | Visibles avec l’état « À porter », exécution désactivée |
| WSL, consoles interactives, flows, Tor/VPN, Wi-Fi | Non intégrés dans cette version |
| Téléchargement des outils | Bouton individuel ou pack, versions fixées, SHA-256 pour les archives Windows |
| Mises à jour des outils | Versions du manifeste ; aucune mise à jour silencieuse vers une version non validée |

Le catalogue contient les 48 outils d’origine et les quatre diagnostics inclus.
Les outils non portés restent visibles avec leur état explicite. « Prêt » signifie
que le binaire est disponible ; les installations gérées passent aussi une
vérification de lancement avant d’être enregistrées. Les dépendances et services
propres à une opération peuvent toujours nécessiter une configuration.

Les dix outils du pack Windows ne nécessitent pas Python installé. WAFW00F et
SQLmap nécessitent Python 3.10 ou ultérieur, choisi dans les paramètres ou détecté
sur le PATH. Ils utilisent chacun un environnement virtuel isolé et un paquet
PyPI à version fixée ; les dépendances transitives sont résolues par pip et ne
sont pas toutes verrouillées. Le bouton « Vérifier l’installation » relance le
contrôle du binaire sans le retélécharger s’il correspond à la version attendue.
Nuclei télécharge ses modèles au premier usage. Naabu utilise le mode TCP connect,
testé sans Npcap sur ce poste. Amass 5 reste « Service requis » et n’entre pas dans
le compteur des outils prêts.

Sur le poste de validation, Microsoft Defender a bloqué SQLmap lors de son
installation. Cet outil n’est donc pas déclaré prêt ; aucune exclusion antivirus
n’est créée par l’application. Consultez le journal pour connaître un éventuel
échec d’installation. Les autres outils peuvent continuer à être installés.

Les profils utilisent des listes d’arguments sans shell. Les fichiers de mots,
ports personnalisés, filtres de taille et profondeurs sont saisis dans les
dialogues ; les champs numériques et plages de ports sont validés avant le lancement.

Les profils externes doivent être validés avec les versions effectivement
installées. Les tests automatiques couvrent leur construction de commandes,
mais ne lancent pas de scans distants. Une seule opération s’exécute à la fois.
Les diagnostics intégrés sont limités à 30 secondes et les opérations externes
à 20 minutes ; l’installation d’un pack est limitée à 30 minutes. L’arrêt termine les processus et conserve les sorties déjà écrites.
Le routage est celui de Windows ; l’application n’affirme pas activer Tor ou un VPN.

## Données, mise à niveau et désinstallation

- Programme : `%LOCALAPPDATA%\Programs\ChaosticTool` par défaut.
- Données : `%LOCALAPPDATA%\ChaosticTool\Desktop`.
- `settings.json` : cibles, sélection active, chemins des exécutables tiers et de Python.
- `tools/` : versions téléchargées, environnements Python isolés, manifestes et derniers échecs. Une installation interrompue peut y laisser des fichiers partiels non utilisés.
- Les outils tiers peuvent aussi créer leurs propres caches ou configurations dans le profil utilisateur.
- `runs/<identifiant>/run.json` : cible, profil, dates, statut et code de sortie.
- `runs/<identifiant>/output.txt` : journal intégral UTF-8 pour les diagnostics ;
  les octets des sorties tierces sont conservés et affichés avec remplacement des
  séquences invalides. Le journal de l’interface est borné en mémoire.

L’installateur garde le même AppId lors d’une mise à niveau et préserve les
données. Désinstallez via **Paramètres Windows → Applications → ChaosticTool
Desktop**. L’application et ses raccourcis sont retirés. Les cibles, résultats et
outils installés séparément sont conservés. Si vous souhaitez effacer vos données,
ouvrez le dossier depuis les paramètres de l’application avant de la désinstaller,
puis supprimez ce dossier vous-même. Le désinstalleur n’effectue aucune suppression
récursive sur un chemin de données configurable.

## Développement

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe chaostic_desktop.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Le projet Desktop n’importe que le registre déclaratif `core.tools` de la CLI.
Les adaptateurs Windows sont dans `desktop/catalog.py`. `desktop/storage.py`
gère les données, `desktop/process.py` les processus et `desktop/workers.py` les
diagnostics ; `desktop/packages.py` gère les téléchargements, vérifications et environnements isolés à partir du manifeste `desktop/packages.json`. L’interface utilise les widgets PySide6 avec les styles partagés de
`desktop/theme.py`. Cette première version utilise Qt Widgets, qui permet de
réutiliser les contrôles clavier et dialogues natifs sans moteur QML supplémentaire.

Pour isoler les données des tests, définissez `CHAOSTIC_DESKTOP_HOME`. Un verrou
d’instance empêche deux fenêtres de modifier le même espace simultanément.

## Fabrication de l’application et de l’installateur

Installez les dépendances de `requirements-build.txt` et Inno Setup 6.7 ou supérieur.
Depuis PowerShell, à la racine du dépôt :

```powershell
.\scripts\build-desktop.ps1 -Python .\.venv\Scripts\python.exe -Iscc 'C:\chemin\vers\ISCC.exe'
```

Le script teste le code, génère l’icône, construit l’application avec PyInstaller,
puis compile l’installateur. Résultats : `dist/ChaosticTool/ChaosticTool.exe` et
`release/ChaosticTool-Setup-0.2.0-windows-x64.exe`. La compilation Windows doit
être réalisée sur Windows. Aucun des binaires générés n’est ajouté à Git.

La distribution conserve Qt en bibliothèques partagées et inclut les notices
livrées avec les dépendances. Voir `docs/THIRD_PARTY.md`.

## Validation

Les tests couvrent les adresses invalides, IPv6 et IDN, les chemins contenant des
espaces et des accents, la persistance, les paramètres endommagés, la récupération
des opérations interrompues, les commandes sans shell, les fonctions locales,
un serveur HTTP sur `127.0.0.1`, un exécutable absent, l’arrêt d’un arbre de processus,
les délais et la navigation graphique. Le mode `--smoke-test` lance le diagnostic
local puis ferme l’application ; utilisez un dossier de données isolé.

Les tests de dépendances couvrent les empreintes incorrectes, traversées de
répertoires et liens d’archives, installations interrompues, binaires absents,
champs invalides et worker d’installation. Les essais d’intégration Windows
utilisent uniquement des services HTTP/TCP de test sur 127.0.0.1. Ils ne prouvent
pas la disponibilité de toutes les sources OSINT externes.

L’installateur peut être compilé avec une identité de test distincte via
`/DAppIdentity=ChaosticTool-Validation-020`, pour vérifier installation,
réinstallation et désinstallation sans toucher à une installation utilisateur.
Cette option n’est pas employée pour l’installateur livré.
