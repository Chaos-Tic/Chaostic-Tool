> Historical design archive. For the current interface, see [Desktop design system](DESIGN.md).

# OPERATION DECK 0.8 — direction visuelle

## Intention

Une présentation inspirée des menus Cyberpunk : grandes entrées, jaune acide,
cyan, rouge signal et panneaux anguleux sur fond noir bleuté. Les graphismes sont
propres au projet ; aucun asset de jeu n'est repris. L'interface reste en français.

## Mouvement

| Zone | Au repos | Interaction / activité |
|---|---|---|
| Fond et en-tête | Fixes, aucune barre mobile | Navigation mise en évidence |
| Accueil | Cycle lumineux lent du décor urbain | Accès aux cibles, arsenal, historique et flows |
| Panneaux | Bordures et repères fixes | Boutons éclairés au survol, onde de clic courte |
| Navigation | Aucun mouvement continu | Fondu 240 ms, focus immédiatement disponible |
| Exécution | Fond stable | Pulsation fixe uniquement pendant une opération |
| Arsenal / historique / paramètres | Horloge d'ambiance arrêtée | Contrôles Qt habituels et transitions |

Les barres traversantes horizontales et verticales de 0.7 ont été retirées.
Le décor urbain est masqué lorsque le panneau d'accueil est trop étroit (≤ 1020 px).
Les compteurs sont réels ; le décor ne représente aucune télémétrie.

## Accessibilité et ressources

Les boutons gardent leur rôle Qt, leur texte accessible, le focus clavier et leurs
actions. Ctrl+K ouvre la recherche, F6 l'exécution. Les états d'échec et les actions
destructives gardent leur propre couleur et leur libellé.

Les animations peuvent être désactivées. La cadence cible 60/30 est conservée ;
elle concerne l'horloge d'ambiance, pas une garantie de FPS. Les panneaux masqués
et la fenêtre réduite sont suspendus. Les vues sans ambiance active n'entretiennent
pas cette horloge. Les transitions de navigation sont finies et libèrent leurs effets.

## Rendu et validation

Qt/PySide6 et QPainter logiciel. Le prototype OpenGL étudié en 0.7 présentait des
artefacts sur le poste Windows de test ; il n'est pas distribué. Aucun moteur de
jeu supplémentaire n'est requis. Le changement n'altère pas les moteurs des outils.

Tests : navigation par les trois grandes entrées, arrêt de l'horloge dans l'arsenal,
réduction de fenêtre, mode statique, libération des transitions et fonctions
existantes. Captures du vrai Qt à 1440×920 et 900×600. Le GIF montre l'application,
avec un profil local de démonstration, jamais inclus dans les installateurs.
