# Amblueo Services

Pilote de gestion des projets, des budgets et de la trésorerie pour les TPE et PME.
L'application Django utilise PostgreSQL et se déploie avec Docker Compose sur
Debian 12.

## Lancer la démonstration avec Docker

Il faut Docker Engine, le plugin Compose (2.24.4 ou ultérieur) et les ports locaux disponibles.

```bash
cp .env.example .env
chmod 600 .env
./ops/compose.sh up -d --wait db
./ops/compose.sh build web
./ops/compose.sh run --rm web python manage.py migrate
./ops/compose.sh run --rm web python manage.py collectstatic --noinput
./ops/compose.sh run --rm web python manage.py seed_demo
./ops/compose.sh up -d --wait
```

Ouvrir http://localhost:8080. Les comptes locaux `demo_dirigeant`,
`demo_projet`, `demo_finance`, `demo_collab` et `demo_second` utilisent
le mot de passe fictif `Amblueo-demo-local-42!`. Le dernier compte appartient
à une entreprise différente pour la recette d'isolation.

## Lancer les tests

```bash
./ops/compose.sh run --rm web python manage.py test
./ops/compose.sh run --rm web python manage.py makemigrations --check --dry-run
```

Pour une vérification rapide sans Docker, utiliser Python 3.12 et SQLite.
Le test de règlements concurrents est réservé à PostgreSQL.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python manage.py test
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python manage.py migrate
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python manage.py seed_demo
AMBLUEO_INFRA_SQLITE=1 .venv/bin/python manage.py runserver
```

## Documentation

- [Architecture et droits](docs/architecture.md)
- [Règles métier](docs/regles-metier.md)
- [Déploiement et exploitation](docs/exploitation.md)
- [Guide utilisateur](docs/guide-utilisateur.md)
- [Recette et vérifications](docs/recette.md)
- [Historique des versions](CHANGELOG.md)
# amblueo-services
