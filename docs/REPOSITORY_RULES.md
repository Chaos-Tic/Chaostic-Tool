# Protection de main et contributions

Vérifié le 28 septembre 2026. Le ruleset [Protect main](https://github.com/Chaos-Tic/Chaostic-Tool/rules/24086485) est actif et cible uniquement `refs/heads/main`.

## Règles appliquées

- Suppression de `main` interdite.
- Push forcé / réécriture non fast-forward interdits.
- Modifications introduites par pull request.
- Discussions de review résolues avant fusion.
- Branche à jour avec `main` avant fusion, selon la politique stricte des contrôles requis.
- Six contrôles GitHub Actions requis : `windows-x64`, `windows-arm64`, `linux-x64`, `linux-arm64`, `macos-x64` et `macos-arm64`.
- Les contrôles sont liés à l'application GitHub Actions (identifiant 15368).
- Aucun acteur configuré pour contourner ce ruleset.

Aucune approbation d'un autre contributeur n'est obligatoire : le nombre de reviews requises est zéro. Cela permet au propriétaire de fusionner sa propre PR lorsque les conditions sont satisfaites. Les reviews restent possibles. Les administrateurs gardent la capacité de modifier la configuration du ruleset ; cela est distinct d'un contournement autorisé lors d'une fusion.

## Parcours de contribution

1. Créer ou utiliser une branche de travail.
2. Y enregistrer les changements et ouvrir une PR vers `main`.
3. Attendre les six contrôles ; en cas d'échec, examiner les logs et corriger ou relancer si la cause est transitoire.
4. Si `main` a avancé, mettre à jour la branche et laisser les contrôles s'exécuter sur le nouvel état.
5. Résoudre les discussions éventuelles, sortir la PR du brouillon lorsqu'elle est prête et la fusionner.

Le job `release` n'est pas requis pour une PR : il prépare les assets lors d'un tag `desktop-v*`. Exiger ce job sur une PR bloquerait un chemin qui ne publie pas de Release.

Les protections ne fusionnent aucune PR et ne changent pas le contenu de `main`. Le workflow Desktop est actuellement apporté par la PR Desktop ; après son intégration dans `main`, il sera disponible pour les nouvelles contributions fondées sur cette branche. Une PR issue de l'ancien `main` sans ce workflow ne produira pas les six contrôles attendus.

## Maintenir les règles

Si un contrôle est renommé dans le [workflow](../.github/workflows/desktop.yml), mettre aussi à jour son nom dans le ruleset. Ne pas désactiver une plateforme uniquement pour rendre une fusion verte sans analyser la régression.

Les règles s'appliquent à `main`, pas aux branches de travail ni aux tags. Il n'y a pas de protection des tags ajoutée par ce ruleset.

Références : [règles effectivement configurées](https://github.com/Chaos-Tic/Chaostic-Tool/rules/24086485), [documentation GitHub des rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
