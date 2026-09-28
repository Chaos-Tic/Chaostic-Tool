# ChaosticTool — prévisualisation de l'interface jeu

**Prototype graphique Godot 4.7.2, distinct de Desktop 0.8.**

Double-cliquez sur **ChaosticTool Game Preview.exe** après extraction complète de
l'archive. Le moteur est fourni dans le dossier `runtime` : aucune installation
de Godot, de Python ou de Git n'est nécessaire pour essayer ce paquet Windows x64.

## Ce qui fonctionne

- Scène 3D avec caméra, géométrie, éclairage, profondeur, brouillard et anticrénelage.
- Plein écran sans bordure au premier lancement, fenêtre alternative avec F11.
- Navigation souris et clavier, transitions de panneaux et déplacements de caméra.
- Sons de survol/confirmation/retour et ambiance originale en boucle.
- Volumes général, interface et ambiance indépendants, sourdine, réglages persistants.
- Limite 30/60/120 images/s et désactivation des mouvements décoratifs.
- Consultation et recherche dans le catalogue réel de 52 outils, descriptions et
  nombres de profils natifs/Linux issus de Desktop.
- Bouton pour ouvrir Desktop installé sur le même compte Windows.

## Périmètre et limites

Ce prototype **ne lance pas les outils**. Les cibles, flows, exécutions, historique,
installations et préparation WSL doivent encore être raccordés à l'interface jeu.
Il ne remplace pas l'application Desktop installée et ne modifie pas son historique.
Le bouton Desktop ouvre l'application existante pour les opérations.

Le décor est une première scène procédurale destinée à valider l'expérience d'un
vrai moteur, pas une direction artistique AAA achevée. Le paquet utilise le binaire
officiel Godot pour exécuter le projet ; la distribution finale devra utiliser les
templates d'export et son propre installateur après migration des fonctions.

Windows 10/11 x64 est la cible de cette prévisualisation. Le rendu Compatibility
demande un pilote OpenGL 3.3 adapté. Test effectué sur Windows avec une NVIDIA RTX
4060 Laptop, pilote 616.92. ARM64/Linux/macOS ne sont pas empaquetés ni validés ici.
Ne pas confondre ces limites avec la matrice multi-systèmes de Desktop 0.8.

## Commandes et réglages

**F11** bascule plein écran/fenêtre. **Échap** revient à l'accueil ; depuis l'accueil,
il quitte le plein écran. Les flèches/Tab déplacent le focus, Entrée active un bouton.
Quitter ferme la prévisualisation.

Préférences séparées : `%APPDATA%/ChaosticToolGamePreview/settings.cfg`.
Les tests automatiques utilisent un dossier isolé. Les sons sont à volume modéré
au premier lancement et peuvent être coupés entièrement dans Image & son.

## Sources et validation

Ouvrir `project.godot` avec Godot 4.7.2 ; importer les ressources puis exécuter le projet.
Le rendu utilise `gl_compatibility`. Un mode de test interne `-- --qa-dir=CHEMIN`
prend des captures dans un dossier existant, vérifie les paramètres et quitte.
Ce mode coupe l'audio audible et utilise des réglages séparés.

Le catalogue est une photographie de celui de Desktop 0.8 ; sa synchronisation
automatique avec le moteur métier fait partie de la migration restante.

Godot : [site officiel](https://godotengine.org), licence MIT dans `GODOT-LICENSE.txt`,
licences tierces dans `GODOT-COPYRIGHT.txt`. Polices : licences OFL dans `assets`.
Code et sons procéduraux de ChaosticTool sous la licence du dépôt.
