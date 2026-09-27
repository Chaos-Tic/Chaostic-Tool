# ADR-001 : exécution Windows et Linux dans Desktop

**Statut :** accepté pour implémentation, validation des prérequis par poste.
**Date :** 2026-09-27.
**Décision :** garder les adaptateurs natifs et ajouter un backend WSL explicite.

## Contexte

Les 48 outils ne sont pas tous exécutables sous Windows. Les profils interactifs,
chemins de fichiers, privilèges et interfaces réseau demandent une gestion réelle.
Ajouter des lignes au catalogue ne constitue pas un portage fonctionnel.

## Choix

- Les outils natifs restent prioritaires. Le catalogue importe les profils
  d’origine, avec formulaires typés, validation et masquage des secrets.
- L’utilisateur choisit Windows ou une distribution WSL détectée. Un inventaire
  explicite vérifie les binaires Linux ; le compteur ne suppose pas leur présence.
- Un pont Python Linux crée un pseudo-terminal, reçoit les commandes sous forme
  de JSON sur stdin, et redirige les sorties dans l’interface. Aucun champ utilisateur
  n’est concaténé dans une commande shell.
- L’arrêt, la perte de stdin et la fermeture de l’application terminent le groupe
  de processus Linux. Les chemins Windows sont convertis dans la distribution.
- L’installation Linux utilise les paquets Kali/Debian explicitement associés
  aux outils. Les scripts absents restent identifiés, avec sélection de leur chemin.
- Les fonctions Wi-Fi nécessitent une interface Linux compatible réellement visible.
  L’application ne présente pas la carte Wi-Fi Windows comme utilisable en mode moniteur.

## Autres options

Une application uniquement Windows laisse une partie des outils inutilisable.
Une machine SSH imposée rendrait l’application dépendante du serveur personnel.
Un conteneur Linux nécessite aussi une couche de virtualisation et complique
l’accès aux interfaces. WSL est le backend local retenu ; SSH pourra être ajouté
sans changer les formulaires et le registre de profils.

## Conséquences

WSL peut exiger une élévation et un redémarrage Windows. Une disponibilité de binaire
ne garantit ni pilotes, ni clé API, ni moteur tiers configuré. La validation doit
distinguer tests du pont Linux, intégration WSL réelle et fonctionnement des outils.
