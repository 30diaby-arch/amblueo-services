# Guide utilisateur

1. **Dirigeant** — Connectez-vous et ouvrez ou créez une entreprise. « Premiers
   pas » indique les étapes encore ouvertes : projet, budget approuvé et solde
   d’ouverture. Le bloc « À traiter » donne accès aux dépenses à approuver,
   impayés échus, alertes budgétaires et tâches en retard selon votre rôle. Dans
   Équipe, choisissez « Inviter un membre », sélectionnez un rôle, puis
   transmettez le lien à la personne concernée. Le lien expire en 48 heures.
   Une personne déjà inscrite se connecte avant d'accepter. « Désactiver »
   coupe l'accès à cette entreprise.
2. **Chef de projet** — Créez un projet et sélectionnez son responsable.
   Ajoutez les tâches et leurs échéances. Préparez le budget et soumettez
   les dépenses en joignant les justificatifs nécessaires.
3. **Collaborateur** — Ouvrez une tâche qui vous est affectée pour mettre à
   jour son statut et sa charge réelle.
4. **Financier** — Approuvez le budget, puis approuvez ou rejetez les demandes.
   Ouvrez une dépense approuvée pour enregistrer un coût réalisé, puis son
   règlement. Pour une recette, saisissez le montant attendu, soumettez-la,
   approuvez-la et enregistrez l'encaissement.
5. **Trésorerie et export** — Initialisez une fois le solde d'ouverture.
   Consultez la projection et les impayés sur le tableau de bord. Ouvrez
   « Préparer un export », sélectionnez un projet et une période, puis cliquez
   sur « Actualiser l’aperçu ». Vérifiez les montants et la devise avant de
   télécharger le CSV. La période filtre les échéances des opérations. Le
   budget approuvé reste celui de la situation courante.
6. **Correction** — Depuis la fiche opération, sélectionnez « Corriger » sur
   l'écriture, indiquez le motif et enregistrez l'écriture exacte au besoin.
   L'historique récent est visible sur la page de l'entreprise.

La page de connexion propose une réinitialisation du mot de passe. En local,
les messages figurent par défaut dans les journaux de Django. Lorsque le relais
SMTP est configuré, le lien de réinitialisation et le lien d’invitation sont
envoyés par e-mail. Un e-mail est aussi envoyé à la personne qui reçoit une tâche
ou devient responsable d’un projet.

## Reprendre les données d’un tableur

Le dirigeant peut ouvrir **Importer des données** depuis la fiche entreprise et
télécharger le modèle CSV. Les lignes s’identifient avec un identifiant stable
de la source. Le fichier peut réunir des projets, des budgets approuvés, des
créances et des factures restant à payer. Le nom du projet doit correspondre
exactement à un projet unique de l’entreprise ou du fichier. Vérifiez les totaux
et corrigez les erreurs dans le tableur avant de confirmer. Une ligne déjà
importée avec le même identifiant et les mêmes valeurs est ignorée.

## Suivre les échéances clients et fournisseurs

Depuis la fiche entreprise, **Échéancier** affiche le montant restant exigible,
les retards et les totaux à payer et à encaisser pour les filtres sélectionnés.
Ouvrez l’opération pour enregistrer un règlement si votre rôle le permet. Les
montants tiennent compte des règlements partiels et des corrections. Le
dirigeant et le financier peuvent renseigner ou corriger le tiers et la
référence externe dans la fiche opération.
