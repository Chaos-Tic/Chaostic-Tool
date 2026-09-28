# ChaosticTool Desktop 0.6

**Sous Windows : [présentation, téléchargement et captures de l’interface](../README_WINDOWS.md).**

Application graphique pour Windows, Linux et macOS. Le catalogue contient les
48 outils du registre CLI et 4 diagnostics supplémentaires. Tous ont des profils
exécutables avec formulaires ; leur disponibilité dépend des outils installés,
du système choisi et des prérequis propres à chaque outil.

## Télécharger et installer

Les téléchargements publics sont dans les [Releases GitHub](https://github.com/Chaos-Tic/Chaostic-Tool/releases).
Choisir une version **Desktop** et le fichier correspondant à votre système et processeur.
Les sommes SHA-256 sont fournies à côté des fichiers. Les artifacts Actions sont
des builds de développement temporaires et peuvent nécessiter un compte GitHub.

| Système | Processeurs | Distribution |
|---|---|---|
| Windows 10 1809+ / Windows 11 | x64 ; ARM64 sous Windows 11 | Setup `.exe`, raccourcis et désinstallation Windows |
| Linux de bureau avec glibc | x64 (glibc 2.35+) ; ARM64 (glibc 2.39+) | Archive `.tar.gz`, application portable, installateur utilisateur |
| macOS 13+ | Intel x64 ; Apple Silicon ARM64 | Image `.dmg`, application à glisser dans Applications |

La matrice de compilation teste Windows Server 2022/Windows 11 ARM, Ubuntu 22.04
x64/24.04 ARM et macOS 15 sur les deux architectures. Les versions minimales
ci-dessus sont des exigences de dépendances, pas une liste de machines toutes testées.
Windows 32 bits, Windows 7/8, Alpine/musl, Android, iOS et les anciens macOS ne sont
pas des cibles de cette version. Une distribution Linux différente peut demander
ses bibliothèques graphiques OpenGL/EGL, XKB et XCB. Sous Debian/Ubuntu :
`sudo apt install libegl1 libopengl0 libxkbcommon0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0`.

**Windows :** ouvrir le Setup téléchargé. Installation par utilisateur, sans installer
Python ni Git. Les mises à jour remplacent l'application et conservent les données.
Désinstaller depuis Paramètres → Applications → ChaosticTool Desktop.

**Linux :** extraire l'archive puis ouvrir `ChaosticTool` dans le dossier extrait.
Pour ajouter l'application au menu, exécuter le `install.sh` fourni, sans sudo.
Le script copie l'application dans `$XDG_DATA_HOME/ChaosticTool/application`
(par défaut `~/.local/share/ChaosticTool/application`). Son `uninstall.sh` retire
l'application et l'entrée de menu, tout en conservant vos données.

**macOS :** ouvrir le DMG et glisser ChaosticTool vers Applications. Pour désinstaller,
retirer ChaosticTool.app d'Applications. Les données personnelles restent conservées.
Les builds actuels n'ont pas de signature d'éditeur Windows ni de notarisation Apple :
les contrôles de réputation du système peuvent donc afficher un avertissement ou
bloquer l'ouverture. Une diffusion sans cet obstacle demande des certificats d'éditeur.

## Préparer les outils

Les six diagnostics/résolveurs intégrés fonctionnent dès l'installation. Depuis
**Outils**, installer le pack portable ou Python, ou un outil individuellement.
L'application choisit l'archive publiée pour votre OS et architecture. Si Python
3.14 est absent, elle télécharge un runtime isolé dont l'empreinte est vérifiée.
Aucun chemin du développeur, compte personnel ou serveur prédéfini n'est requis.

Les outils externes sont téléchargés séparément depuis leurs distributions officielles.
Une connexion Internet est nécessaire pour leur installation. Les clés API, moteurs
tiers (notamment Amass), pilotes et données de travail restent à configurer par l'utilisateur.
Une protection antivirus peut bloquer certains outils : l'application signale l'échec
et ne modifie pas les protections. Un outil n'est pas compté prêt simplement parce
que sa fiche figure au catalogue.

## Outils nécessitant Linux

Dans **Paramètres → Environnement Linux**, choisir :

- **Linux local** sur un poste Linux ;
- **WSL** sur Windows, avec une distribution Kali de préférence ;
- **SSH** vers votre propre machine ou VM Linux, sur les trois systèmes.

Le bouton de préparation WSL lance l'installation Windows officielle ; l'activation
de la virtualisation peut demander des droits administrateur et un redémarrage.
Terminer l'initialisation de la distribution et de son compte utilisateur, puis
sélectionner sa distribution dans l'application et vérifier la connexion.
La machine Linux doit disposer de Python 3. Le mode SSH utilise le client OpenSSH,
une clé déjà autorisée et une clé d'hôte déjà approuvée dans `known_hosts` ; aucune
acceptation aveugle de l'identité du serveur n'est effectuée.

Le bouton **Installer le pack Linux** utilise apt sur Kali/Debian/Ubuntu et affiche
explicitement les paquets absents des dépôts. Il n'ajoute aucun dépôt Kali à Ubuntu.
Sur Arch ou une autre distribution, installer les outils avec son gestionnaire de
paquets puis relancer la détection ; un chemin personnalisé peut être renseigné.
Le compte doit avoir les droits sudo lorsque le paquet ou le profil les nécessite.

Les commandes interactives utilisent un vrai pseudo-terminal Linux, avec saisie
intégrée, masquage des secrets, Ctrl+C, arrêt et limite de durée. En WSL les chemins
de fichiers locaux sont traduits. En SSH les fichiers d'entrée doivent déjà exister
sur Linux et les fichiers produits restent sur cette machine ; les journaux restent
disponibles dans Desktop. Le transfert automatique de fichiers SSH n'est pas fourni.

Les opérations Wi-Fi exigent une interface compatible et des pilotes adaptés,
réellement visibles dans Linux. Le routage et les interfaces utilisés sont ceux
de l'environnement d'exécution, pas nécessairement ceux de l'ordinateur graphique.
Desktop reprend les trois attack flows CLI et permet de créer, modifier, importer et exporter des flows personnalisés. Tor/proxychains et VPN guard restent propres à la CLI.

## Données et mises à jour

- Windows : `%LOCALAPPDATA%/ChaosticTool/Desktop`.
- Linux : `$XDG_DATA_HOME/ChaosticTool/Desktop`, par défaut `~/.local/share/ChaosticTool/Desktop`.
- macOS : `~/Library/Application Support/ChaosticTool/Desktop`.

Les résultats, cibles, outils téléchargés et paramètres y restent après désinstallation.
La variable `CHAOSTIC_DESKTOP_HOME` permet un profil séparé. Les secrets saisis dans
les formulaires sont masqués dans l'historique et le flux de sortie ; les fichiers
produits par les outils eux-mêmes peuvent contenir des données sensibles.

## Construire et vérifier

Installer Python 3.14 pour le développement, puis `pip install -r requirements-build.txt`.
Lancer `python scripts/build-desktop.py` sur le système cible ; sous Windows ajouter
`--iscc CHEMIN/ISCC.exe` avec Inno Setup 6. Les fichiers apparaissent dans `release/`.
`python scripts/smoke-desktop.py` vérifie le binaire construit avec un profil jetable.
Le workflow GitHub compile et teste séparément les six couples OS/architecture.
Un tag `desktop-v*` prépare une Release brouillon avec tous les paquets vérifiés ;
sa publication rend les fichiers accessibles sans installation d'outils de développement.

## Nouveautés 0.4

Exécuter et arrêter depuis la même page ; classement selon les dix phases CLI ; noms de dossiers avec cible, outil et profil ; historique recherchable ; trois attack flows, éditeur et import/export JSON. RustScan dispose d’une installation native sur les plateformes publiées en amont, et Nmap de son assistant officiel sous Windows x64. Les 48 outils et tous leurs profils CLI sont contrôlés par les tests de correspondance. Voir le guide Windows pour le fonctionnement des flows et les limites de chaque moteur.
