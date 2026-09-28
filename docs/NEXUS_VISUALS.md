# NEXUS 0.7 — rendu et interactions

## Objectif

Faire évoluer le tableau de bord vers un cockpit animé tout en conservant les
formulaires, le clavier, les journaux lisibles et le démarrage sur Windows 10/11.
L'habillage est décoratif ; les statistiques et états viennent des données réelles.

## Composants

| Composant | Animation | Limites |
|---|---|---|
| Fond commun | Grille en perspective, rubans lumineux, particules et lumières latérales | Couleurs peu contrastées derrière les panneaux |
| Hologramme | Sphère triangulée, rotation 3D, projection perspective, faces triées en profondeur, orbites, particules | Masqué si la largeur du panneau est ≤ 790 px |
| Panneaux | Repères d'angle, segment lumineux mobile, survol accentué | Dessin limité aux bordures, contenu inchangé |
| Rail d'en-tête | Segments et déplacement lumineux | Décoration, sans fausse mesure d'activité |
| Boutons | Survol 170 ms, onde de clic 450 ms | Pas d'animation nouvelle en mode statique |
| Pages | Fondu 180 ms | Effet libéré à la fin ; navigation et focus immédiats |
| Exécution | Lumière mobile au bord du journal | Seulement pendant une opération ; jamais au-dessus du texte |

La palette conserve violet électrique, cyan, fonds bleu nuit et texte clair.
Orbitron sert aux titres, Exo 2 complète la police du système, Share Tech Mono
sert aux sorties. Les polices et leurs licences sont incluses.

## Choix technique

Le rendu distribué utilise **QPainter/PySide6**. Le module `desktop/reactor.py`
calcule la rotation, la projection et le tri des faces, puis les dessine avec Qt.
Il ne s'agit pas d'un moteur de jeu ni d'une scène accélérée par GPU.

Un prototype QOpenGLWidget a été exécuté sur le poste Windows de validation.
Le contexte était valide mais des artefacts apparaissaient dans le framebuffer
et la capture du widget, y compris avec profondeur, stencil et multisampling.
Ce prototype n'est pas inclus dans la release : il reste à isoler la cause avant
de retenir OpenGL. Ajouter Unity/Godot imposerait une seconde pile d'interface et
une intégration du cycle de vie sans bénéfice démontré à ce stade.

## Cadence et ressources

Une horloge partagée utilise le temps monotone. Elle demande une mise à jour
toutes les 16 ms (mode fluide) ou 33 ms (mode économe). Le déplacement dépend du
temps écoulé, borné après une pause, et non du nombre d'images reçues.

Les widgets masqués ne sont pas animés. La fenêtre réduite suspend l'horloge.
Le choix 30/60 et le mode statique sont conservés dans les paramètres de
l'utilisateur. Ces valeurs sont des cibles et non des FPS mesurés garantis.
Les contrôles natifs restent accessibles avec le clavier, y compris en mode statique.

## Vérification

Tests de navigation et actions, libération des transitions, suspension des
panneaux masqués, cadence persistée, suspension à la réduction, images successives
différentes en mouvement et identiques en mode statique. Captures Qt à 1440×920
et 900×600. Le GIF de documentation assemble des images du vrai widget, sans
maquette ni animation ajoutée après capture.

La CI vérifie le fonctionnement sans écran sur les six combinaisons OS/architecture.
Cela ne remplace pas des mesures sur chaque écran, GPU ou session distante.
