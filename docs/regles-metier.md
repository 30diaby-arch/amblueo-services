# Règles métier

Les montants sont stockés en décimal avec deux positions. À la saisie, XOF
exige un montant entier et EUR accepte deux décimales. Le logiciel refuse les
montants qui dépassent la précision admise. Les soldes sont des sommes et
différences exactes. La devise est fixée lors de la création de l'entreprise.
Les charges d'une tâche sont des heures décimales.

## Budget

Un budget en brouillon est modifiable. Le montant approuvé est verrouillé dans
le pilote. Une dépense passe par brouillon, soumission puis approbation ou rejet.
L'approbation nécessite un budget approuvé et peut constater un dépassement.
Les demandes soumises alimentent l'alerte de risque avant approbation.

- Engagement ouvert = montant approuvé de la dépense moins son réalisé.
- Disponible = budget approuvé moins coûts réalisés et engagements ouverts.
- Disponible prévisionnel = disponible moins dépenses soumises.
- Le paiement ne modifie pas le budget.

Avec 1 000 000 XOF en budget et 300 000 XOF approuvés, le disponible est
700 000 XOF. En réalisant 120 000 XOF, l'engagement ouvert passe à 180 000 XOF.
Le disponible reste 700 000 XOF.

## Trésorerie et corrections

Le solde d'ouverture est le solde avant les règlements du jour de référence.
Le solde courant additionne les encaissements et soustrait les décaissements
enregistrés depuis cette date, date de référence comprise. Chaque écriture
porte sa date effective. Les dates futures sont réservées aux échéances.

La prévision à 30 jours ajoute les recettes approuvées en attente et déduit les
dépenses approuvées encore sans règlement à cet horizon. Elle inclut la partie
encore engagée d'une dépense à partir de son échéance. Les impayés échus
figurent à part et sont inclus dans la projection. Leur montant exigible
correspond au réalisé non payé pour une dépense et au montant approuvé non
encaissé pour une recette.

Les règlements d'une dépense sont plafonnés par le coût réalisé restant.
Une annulation d'écriture exige un motif et conserve la ligne d'origine.
Une réalisation ne peut être annulée que si le montant réalisé corrigé
couvre les règlements actifs. Une opération approuvée peut ensuite être
annulée une fois toutes ses écritures actives annulées. Pour corriger le montant
d'une opération approuvée, annuler et ressaisir avec le bon montant.

Les lignes de budget du CSV sont cumulées au moment de l'export. Le filtre
de date s'applique à l'échéance des lignes d'opération.
