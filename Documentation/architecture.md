# Architecture

Nginx expose l'interface et les assets publics. Gunicorn exécute Django sur
le réseau frontal de Compose. Seul le service Django rejoint le réseau de
données avec PostgreSQL. L'application est un monolithe dont les écrans,
les modèles et les règles financières sont séparés dans `pilot/`.

| Donnée | Rattachement | Rôle |
|---|---|---|
| Compte et adhésion | L'adhésion associe un compte à une entreprise | Rôle et état d'accès |
| Invitation | Entreprise, courriel, rôle, empreinte et expiration | Un lien à usage unique ouvre l'adhésion |
| Projet et tâche | Projet lié à l'entreprise, tâche liée au projet | Organisation du travail |
| Budget | Un montant par projet | Seul un budget approuvé alimente le disponible |
| Opération | Projet et auteur | Dépense ou recette dont la validation est suivie |
| Écriture | Opération et auteur | Réalisation ou règlement, avec clé de répétition |
| Ouverture de trésorerie | Une par entreprise | Solde de référence consolidé |
| Audit | Entreprise et auteur | Décisions, corrections et motifs |

L'appartenance active est contrôlée au début de chaque vue d'entreprise.
Les recherches d'objets et les choix de formulaires appliquent le même
périmètre. Les justificatifs résident dans un volume privé et passent par
une vue authentifiée. Le chemin du fichier est opaque.

| Action | Dirigeant | Chef de projet | Financier | Collaborateur |
|---|---|---|---|---|
| Inviter ou désactiver un membre | Oui | | | |
| Voir les projets et tâches de l'entreprise | Oui | Oui | Oui | Oui |
| Planifier les projets et affecter leurs tâches | Oui | Oui | | |
| Mettre à jour statut et charge réelle de sa tâche | Oui | Oui | Oui | Oui |
| Préparer un budget et une dépense | Oui | Oui | Oui | |
| Approuver budget et opérations | Oui | | Oui | |
| Saisir recettes, réalisations, règlements et corrections | Oui | | Oui | |
| Consulter budget, opérations, pièces et exports | Oui | Oui | Oui | |
| Gérer le solde d'ouverture, voir la trésorerie et l'audit | Oui | | Oui | |

Tout compte connecté peut ouvrir sa propre entreprise. Le pilote permet
au dirigeant d'approuver ses propres opérations. Le dirigeant ne peut
désactiver un autre dirigeant depuis l'interface. Les utilisateurs qui
doivent appartenir à plusieurs entreprises acceptent l'invitation avec
leur compte existant.

PostgreSQL est la référence pour la concurrence. Les mutations d'écritures
verrouillent leur opération. Les clés UUID de formulaire empêchent de rejouer
deux fois la même écriture. Un utilisateur doit présenter une adhésion active
au début de la requête. Une désactivation s'applique aux requêtes suivantes.
