# Amblueo Services

Pilote Django de gestion de projets, de budgets et de trésorerie pour les entreprises de services. Django rend les pages HTML côté serveur et utilise PostgreSQL dans Docker Compose.

## Où intervenir

Accède aux dossiers de navigation [Backend](Backend/README.md), [Frontend](Frontend/README.md), [Operations](Operations/README.md) et [Documentation](Documentation/README.md).

| Sujet | Point d’entrée |
| --- | --- |
| Routes et paramètres Django | [config/urls.py](Backend/config/urls.py), [config/settings.py](Backend/config/settings.py) |
| Entreprises, invitations et membres | [pilot/views/companies.py](Backend/pilot/views/companies.py), [contrôles partagés](Backend/pilot/views/common.py) |
| Projets et tâches | [pilot/views/projects.py](Backend/pilot/views/projects.py) |
| Budgets, opérations, écritures et trésorerie | [pilot/views/financial.py](Backend/pilot/views/financial.py), [calculs et écritures atomiques](Backend/pilot/finance.py) |
| Export CSV | [pilot/views/exports.py](Backend/pilot/views/exports.py) |
| Schéma et formulaires | [pilot/models.py](Backend/pilot/models.py), [pilot/migrations/](Backend/pilot/migrations/), [pilot/forms.py](Backend/pilot/forms.py) |
| Interface | [Templates Django](Frontend/templates/), [mise en page](Frontend/templates/pilot/base.html), [CSS](Frontend/static/pilot/app.css) |
| Déploiement, proxy et sauvegardes | [Dockerfile](Operations/Dockerfile), [Compose local](Operations/compose.yaml), [surcharge de production](Operations/compose.prod.yaml), [scripts](Operations/), [guide d’exploitation](Documentation/exploitation.md) |
| Tests et démonstration | [pilot/tests.py](Backend/pilot/tests.py), [seed_demo.py](Backend/pilot/management/commands/seed_demo.py), [scénarios de recette](Documentation/recette.md) |

Pour comprendre un écran, pars de sa route, puis suis la vue, le formulaire et le template. Pour les règles métier, lis [règles métier](Documentation/regles-metier.md). Le [README](README.md) donne les commandes de démarrage. [L’architecture](Documentation/architecture.md) décrit les composants et [le dossier de référence](Documentation/RESSOURCES-DOCUMENTAIRES/) conserve les documents historiques.

## Contrats à préserver

- Vérifie l’adhésion active et les rôles. Filtre par entreprise les objets lus ou modifiés, les choix de formulaires, les exports et les justificatifs privés.
- Utilise les calculs de `Backend/pilot/finance.py` pour les soldes, budgets et prévisions. Préserve les montants `Decimal`, les contraintes par devise, les transactions, les verrous de ligne et l’idempotence des écritures.
- Lors d’un déplacement de code, conserve les noms et arguments des routes, les contrats des formulaires et les clés de contexte des templates.
- Rédige les textes de l’interface et la documentation du projet en français. Pour les variables, constantes et paramètres internes ajoutés, suis la convention `AMBLUEO_<MODULE>_<NOM>`. Respecte les interfaces Django, Python et Docker existantes.

## Vérifier les changements

Depuis un environnement de développement configuré selon le README, lance les vérifications pertinentes.

```bash
./Operations/compose.sh run --rm web python manage.py check
./Operations/compose.sh run --rm web python manage.py test
./Operations/compose.sh run --rm web python manage.py makemigrations --check --dry-run
```

SQLite permet une vérification rapide avec `AMBLUEO_INFRA_SQLITE=1` et le mode debug local. Le test de concurrence des écritures nécessite PostgreSQL. Pour un changement de droits ou de finances, vérifie aussi les accès entre entreprises, les calculs attendus et les effets sur les données. Indique les vérifications effectuées et celles qui restent à faire.
