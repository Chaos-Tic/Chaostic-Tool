# ADR — interface jeu Godot

**Statut : prototype accepté pour évaluation, migration métier non terminée.**
**Date : 28 septembre 2026.**

## Contexte

L'utilisateur demande une expérience de jeu Cyberpunk : véritable moteur graphique,
plein écran, scène vivante, transitions et sons réglables. Les itérations de thème
Qt ont conservé une présentation de logiciel utilitaire, et leurs barres animées
permanentes étaient trop distrayantes. Un essai QOpenGLWidget avait aussi montré
des artefacts sur le poste local.

## Décision

Prototyper dans `game_ui/` avec **Godot 4.7.2**, rendu Compatibility OpenGL 3.3,
scène 3D originale et couche de menus. Les effets sont liés aux actions et à une
ambiance lente. Fenêtre toujours fenêtrée, audio par bus, volumes séparés,
sourdine, cadence maximale et mouvements réduits sont de vraies préférences.

Le prototype est séparé de Desktop 0.8 et ne doit pas être publié sous un numéro
de release Desktop ni remplacer son installateur avant raccordement fonctionnel.
Le binaire officiel du moteur est embarqué dans le paquet d'évaluation, vérifié
par SHA-256. Un build final utilisera les templates d'export.

## Options considérées

| Option | Avantage | Limite dans ce contexte |
|---|---|---|
| Qt Widgets | Fonctionnel et déjà distribué | Ne satisfait pas la demande d'expérience de jeu |
| Qt Quick / scène GPU | Bonne intégration au backend existant | Nouvelle couche UI, ne fournit pas directement tout le cadre de jeu demandé |
| Godot | Scène, caméra, rendu, entrées, audio et menus dans un moteur libre | Recréation des écrans et liaison métier nécessaires |
| Unity / Unreal | Moteurs de jeu complets | Pile et distribution plus lourdes pour ce périmètre |

## État vérifié

- Rendu natif sur NVIDIA RTX 4060 Laptop avec OpenGL 3.3, pilote 616.92.
- Fenêtrage permanent, sauvegarde des réglages, mute, démarrage du lecteur audio
  et catalogue de 52 outils vérifiés par le mode QA.
- Paquet portable testé par son lanceur Windows sans terminal.
- Réglages dans un profil Godot distinct ; aucun historique Desktop embarqué.
- Sources des sons procéduraux et licences Godot/polices fournies.

## Direction artistique — état

Après une première itération « poste d'opérateur » jugée trop marquée jeu vidéo,
la direction retenue sur le parcours accueil → arsenal → fiche est **sobre** :
matières mates, lumière douce de studio, une seule teinte d'accent acier,
typographie en casse normale. Un objet mat (sphère et fin anneau d'acier) sur un
socle, sous un projecteur doux, tient lieu d'unique point d'intérêt — aucun néon,
aucun hologramme lumineux, aucun effet qui balaye. Caméra calme, courts
déplacements par section, panneaux opaques et lisibles. La fenêtre reste
**toujours fenêtrée** (le plein écran et F11 sont retirés). La fiche outil
(ex. Nmap) est dédiée : description, note, comptes de profils et liste consultable.
L'exécution reste non raccordée — le bouton ouvre Desktop 0.8. Les autres écrans
suivront ce cadre une fois ce parcours validé en mouvement.

## Migration restante

1. Étendre cette direction sobre (matières mates, lumière de studio, caméra calme)
   à tous les écrans, après validation du parcours accueil → arsenal → fiche.
2. Extraire un service métier local de Desktop avec contrat IPC explicite : aucune
   commande shell libre ne doit provenir de l'interface. Garder validation des
   profils, confidentialité des secrets et suivi/arrêt des processus existants.
3. Raccorder cibles, formulaires de tous les profils, résultats, filtres, flows,
   installations et préparation WSL ; réutiliser les données existantes.
4. Vérifier la parité fonctionnelle, les déconnexions, l'arrêt de processus et
   l'absence d'exposition réseau du service avant de remplacer l'interface Qt.
5. Construire et tester les exports x64/ARM64, puis Linux/macOS, et les installateurs.

Le catalogue du prototype est une photographie de Desktop 0.8 et reste en lecture
seule. Le bouton Desktop ouvre l'application opérationnelle séparément. Il ne
constitue pas un raccordement des outils à Godot.

## Releases GitHub

Quatre releases restent publiques : Desktop actuelle et précédente, Linux CLI
stable et précédente. Les six anciennes préversions Desktop passent en brouillon,
avec conservation des tags et assets. Le propriétaire peut toujours les retrouver.
Les essais graphiques ne créent plus de release publique supplémentaire tant que
leur périmètre n'est pas celui d'une application distribuable complète.

Références : [Godot Windows](https://godotengine.org/download/windows/),
[DisplayServer](https://docs.godotengine.org/en/stable/classes/class_displayserver.html).
