# Protection de linux-cli et contributions

Vérifié le 28 septembre 2026. Le ruleset [Protect linux-cli](https://github.com/Chaos-Tic/Chaostic-Tool/rules/24086485) est actif et cible uniquement `refs/heads/linux-cli`.

## Règles appliquées

- Suppression de `linux-cli` interdite.
- Push forcé / réécriture non fast-forward interdits.
- Modifications introduites par pull request.
- Discussions de review résolues avant fusion.
- Branche à jour avec `linux-cli` avant fusion, selon la politique stricte des contrôles requis.
- Six contrôles GitHub Actions requis : `windows-x64`, `windows-arm64`, `linux-x64`, `linux-arm64`, `macos-x64` et `macos-arm64`.
- Les contrôles sont liés à l'application GitHub Actions (identifiant 15368).
- Aucun acteur configuré pour contourner ce ruleset.

Aucune approbation d'un autre contributeur n'est obligatoire : le nombre de reviews requises est zéro. Cela permet au propriétaire de fusionner sa propre PR lorsque les conditions sont satisfaites. Les reviews restent possibles. Les administrateurs gardent la capacité de modifier la configuration du ruleset ; cela est distinct d'un contournement autorisé lors d'une fusion.

## Parcours de contribution

1. Créer ou utiliser une branche de travail.
2. Y enregistrer les changements et ouvrir une PR vers `linux-cli`.
3. Attendre les six contrôles ; en cas d'échec, examiner les logs et corriger ou relancer si la cause est transitoire.
4. Si `linux-cli` a avancé, mettre à jour la branche et laisser les contrôles s'exécuter sur le nouvel état.
5. Résoudre les discussions éventuelles, sortir la PR du brouillon lorsqu'elle est prête et la fusionner.

Le job `release` n'est pas requis pour une PR : il prépare les assets lors d'un tag `desktop-v*`. Exiger ce job sur une PR bloquerait un chemin qui ne publie pas de Release.

Les protections ne fusionnent aucune PR et ne changent pas le contenu de `linux-cli`. Le workflow Desktop est actuellement apporté par la PR Desktop ; après son intégration dans `linux-cli`, il sera disponible pour les nouvelles contributions fondées sur cette branche. Une PR issue de l'ancien `linux-cli` sans ce workflow ne produira pas les six contrôles attendus.

## Maintenir les règles

Si un contrôle est renommé dans le [workflow](../.github/workflows/desktop.yml), mettre aussi à jour son nom dans le ruleset. Ne pas désactiver une plateforme uniquement pour rendre une fusion verte sans analyser la régression.

Les règles s'appliquent à `linux-cli`, pas aux branches de travail ni aux tags. Il n'y a pas de protection des tags ajoutée par ce ruleset.

Références : [règles effectivement configurées](https://github.com/Chaos-Tic/Chaostic-Tool/rules/24086485), [documentation GitHub des rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).

## Renommage du 28 septembre 2026

La branche `main` a été renommée **`linux-cli`** pour identifier la version Linux
en terminal. Elle reste la branche par défaut. La branche graphique reste
`desktop/windows-app`. GitHub a redirigé la PR Desktop existante vers `linux-cli` ;
elle reste en brouillon. Le ruleset a été renommé et sa cible mise à jour, avec
les mêmes six contrôles, l'interdiction de suppression et de push forcé.

Pour actualiser un clone dont la branche locale s'appelle encore `main` :

```sh
git branch -m main linux-cli
git fetch origin
git branch -u origin/linux-cli linux-cli
git remote set-head origin -a
```

Ne lancez la première commande que si vous avez effectivement une branche locale
`main` à renommer. Le renommage ne fusionne pas les deux éditions.
