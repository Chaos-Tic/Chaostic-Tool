# NEXUS — système visuel Desktop 0.5

Interface native PySide6, sans moteur web ni connexion requise pour le rendu.

| Rôle | Couleur |
|---|---|
| Fond | `#080b19` |
| Accent principal | `#9b75ff` |
| Accent secondaire | `#56d9ee` |
| Texte | `#edf2ff` |
| Succès | `#63e6b5` |
| Prérequis | `#f2bf78` |
| Erreur / arrêt | `#ff7c97` |

Les polices Orbitron, Exo 2 et Share Tech Mono sont embarquées avec leurs licences OFL. Les titres utilisent Orbitron ; les paragraphes privilégient la police du système pour préserver la lecture. Les polices de remplacement sont prévues dans le thème.

`desktop/hud.py` dessine les éléments procéduraux : noyau orbital, particules, grille et indicateur d’exécution. Une horloge commune de 33 ms actualise uniquement les panneaux visibles et actifs. Elle s’arrête si aucun panneau visible n’en a besoin, si la fenêtre est minimisée ou si l’utilisateur désactive les effets. Le compteur n’ajoute aucune information métier simulée.

`desktop/effects.py` gère les survols, les compteurs et les transitions. Chaque bouton réutilise son animation. Les animations finies de transition et de compteur sont supprimées. Les badges gardent une hauteur de 27 pixels logiques et un texte accessible.

Le profil utilisateur conserve `animations: true/false`. Les opérations, l’historique et les processus fonctionnent de la même façon lorsque les effets sont désactivés. Les contrôles restent des widgets Qt utilisables au clavier. Ctrl+K ouvre la recherche et F6 l’exécution.

Vérifications : cinq tests dédiés aux animations et interactions s’ajoutent aux quarante tests existants. Ils vérifient les panneaux masqués, la persistance du mode statique, la libération des transitions, les quatre quadrants de l’icône, les actions de l’accueil et l’état réel d’exécution. Le rendu est également inspecté sur une fenêtre de 900 × 600 et sur grand écran.
