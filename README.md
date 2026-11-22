# Amblueo Services

Pilote de gestion des projets, des budgets et de la trésorerie pour les TPE et PME.
L'application Django utilise PostgreSQL et se déploie avec Docker Compose sur
Debian 12.

## Lancer la démonstration avec Docker

Il faut Docker Engine, le plugin Compose (2.24.4 ou ultérieur) et les ports locaux disponibles.

```bash
cp Operations/.env.example Operations/.env
chmod 600 Operations/.env
./Operations/compose.sh up -d --wait db
./Operations/compose.sh build web
./Operations/compose.sh run --rm web python manage.py migrate
./Operations/compose.sh run --rm web python manage.py collectstatic --noinput
./Operations/compose.sh run --rm web python manage.py seed_demo
./Operations/compose.sh up -d --wait
```

Ouvrir http://localhost:8080. Les comptes locaux `demo_dirigeant`,
`demo_projet`, `demo_finance`, `demo_collab` et `demo_second` utilisent
le mot de passe fictif `Amblueo-demo-local-42!`. Le dernier compte appartient
à une entreprise différente pour la recette d'isolation.

## Lancer les tests

```bash
./Operations/compose.sh run --rm web python manage.py test
./Operations/compose.sh run --rm web python manage.py makemigrations --check --dry-run
```

Pour une vérification rapide sans Docker, utiliser Python 3.12 et SQLite.
Le test de règlements concurrents est réservé à PostgreSQL.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r Backend/requirements.txt
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python Backend/manage.py test
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python Backend/manage.py migrate
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python Backend/manage.py seed_demo
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python Backend/manage.py runserver
```

## Documentation

- [Organisation du dépôt et consignes pour les agents](AGENTS.md)
- [Architecture et droits](Documentation/architecture.md)
- [Règles métier](Documentation/regles-metier.md)
- [Déploiement et exploitation](Documentation/exploitation.md)
- [Déploiement de la recette HTTPS](Documentation/deploiement-recette.md)
- [Feuille de route du MVP](Documentation/roadmap-mvp.md)
- [Guide utilisateur](Documentation/guide-utilisateur.md)
- [Recette et vérifications](Documentation/recette.md)
- [Historique des versions](Documentation/CHANGELOG.md)
# amblueo-services
