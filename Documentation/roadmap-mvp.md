# Feuille de route du MVP commercialisable

**Objectif** — Une TPE ou PME de services reprend ses données existantes, réalise un premier point de gestion et revient traiter ses échéances la semaine suivante.

Le socle livré couvre les projets et tâches, les budgets, la validation des opérations, les paiements partiels, la trésorerie, le tableau « À traiter », les premiers pas et l’export CSV.

| Ordre | Chantier | Périmètre | Critère de validation |
| --- | --- | --- | --- |
| 1 | Recette et exploitation | Publier la recette en HTTPS. Vérifier les rôles, le SMTP, les sauvegardes et le renouvellement TLS. Restaurer une base et ses justificatifs dans un environnement isolé. | Le compte de recette se connecte, reçoit un lien de réinitialisation et retrouve les mêmes soldes et pièces après restauration. |
| 2 | Import initial CSV | Fournir des modèles pour les projets, les budgets courants et les échéances ouvertes. Prévisualiser le fichier, signaler les erreurs par ligne, puis confirmer l’import. Préserver les rôles, les règles financières et la cohérence en cas de répétition. | Un client pilote reprend un tableur représentatif, corrige ses lignes en erreur et retrouve les totaux attendus dans Amblueo. |
| 3 | Échéancier clients et fournisseurs | Associer un tiers et une référence externe à une opération. Présenter les montants restant à payer ou à recevoir, avec des filtres par tiers, projet et échéance. Réutiliser les règles actuelles de règlement. | Un financier retrouve les échéances d’une semaine et voit le reste dû évoluer après un paiement partiel. Les données des autres entreprises restent isolées. |
| 4 | Récapitulatif hebdomadaire interne | Envoyer aux membres concernés leurs validations en attente, les impayés et les alertes budgétaires. Appliquer le périmètre et les droits de chaque destinataire. Prévoir l’activation et la désactivation de l’envoi. | Sur deux rôles de recette, vérifier que chacun reçoit les actions auxquelles il a accès et qu’un membre désactivé cesse de recevoir les messages. |
| 5 | Pilote payant | Préparer la mise en service accompagnée, la facturation manuelle et un canal de support. Mesurer le temps jusqu’au premier point de gestion et le retour la semaine suivante. | Un client pilote importe ses données, réalise un point de gestion sur ses propres chiffres et revient traiter ses échéances. |

La facturation intégrée, la connexion bancaire et le paiement automatique de l’abonnement seront priorisés après les retours du pilote.
