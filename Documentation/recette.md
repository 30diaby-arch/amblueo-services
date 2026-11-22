# Recette du pilote

Utiliser le jeu fictif du README et repartir d'une base dédiée aux tests.

| Scénario | Actions | Attendu |
|---|---|---|
| Invitation | Créer un lien de collaborateur, l'accepter, le rouvrir et désactiver le membre | Une seule activation, accès retiré après désactivation |
| Projet | Créer un projet avec une tâche de 8 h affectée au collaborateur | Le collaborateur met sa charge réelle à 7 h et termine la tâche |
| Isolation | Depuis Studio Latitude, tenter d'ouvrir les URL d'un projet, d'un document et d'un export d'Atelier Horizon | Réponse 404 et aucune modification |
| Permissions | Préparer le budget avec le chef de projet, tenter de l'approuver, puis changer pour le financier | Le chef reçoit 403 et le financier approuve |
| Engagement | Approuver 300 000 XOF sur 1 000 000 XOF, puis réaliser 120 000 XOF | Réalisé 120 000, ouvert 180 000, disponible 700 000 |
| Paiement | Ouvrir la trésorerie à 500 000 XOF, puis régler 50 000 XOF le jour de référence | Exigible 70 000, courant 450 000, disponible 700 000 |
| Export | Exporter le projet après ce paiement | Les colonnes Réalisé, Engagé ouvert, Disponible et Restant exigible correspondent au tableau |
| Correction | Annuler le règlement avec le motif « Saisie en doublon constatée » | Écriture conservée, motif dans l'historique, trésorerie courante à 500 000 |
| Concurrence | Lancer deux paiements de 75 sur une recette de 100 sous PostgreSQL | Un seul paiement est accepté, solde de 25 |
| Restauration | Restaurer le dump et les pièces sur une cible séparée | Recalcul cohérent, justificatif lisible et migrations présentes |

La recette du déploiement inclut la construction des images, les contrôles
d'état Compose, HTTPS, SMTP, une sauvegarde hors hôte et la restauration via
les scripts d'exploitation sur l'environnement cible.

## Vérifications effectuées

Les quatre tests Django ont réussi avec PostgreSQL 16.2, y compris deux
règlements simultanés. Le dump PostgreSQL et un justificatif ont été
restaurés vers une autre base et un autre dossier. Les agrégats 120 000,
180 000 et 700 000 XOF et le contenu du fichier ont été recontrôlés.

Le test de restauration local utilise les utilitaires PostgreSQL et tar.
Il reste à exécuter les scripts de bout en bout avec Docker Compose,
PostgreSQL 17, et le service de sauvegarde de l'hôte Debian 12. Vérifier
aussi les ports, les certificats et l'envoi SMTP sur cet hôte.
