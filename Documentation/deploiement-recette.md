# Déployer la recette sur services.amblueo.com

La recette publique utilise Django en mode production avec des comptes de test et une base dédiée. Nginx sert l’application en HTTPS sur le port 443. Sur le port 80, il redirige vers HTTPS avec un statut 308 et sert le défi ACME nécessaire au renouvellement du certificat. Gunicorn et PostgreSQL communiquent sur les réseaux privés de Compose.

## Récupérer le code sur le VPS

Sur un premier déploiement, utiliser un compte de déploiement disposant d’un accès SSH GitHub en lecture et vérifier l’empreinte de l’hôte SSH. Exécuter les commandes depuis le répertoire parent du futur dépôt.

```bash
git clone --branch main git@github.com:30diaby-arch/amblueo-services.git
cd amblueo-services
git rev-parse --short HEAD
```

Sur une installation existante, exécuter ces commandes depuis le dépôt du serveur après avoir vérifié que le répertoire de travail est propre.

```bash
git status --short
git switch main
git pull --ff-only origin main
git rev-parse --short HEAD
```

Récupérer une révision qui contient cette procédure et la cible Compose `recette`.

## Configurer la cible et le certificat

Lors de la première installation, créer le fichier d’environnement avec des permissions restreintes.

```bash
test -f Operations/.env || install -m 600 Operations/.env.example Operations/.env
chmod 600 Operations/.env
```

Renseigner les valeurs suivantes dans `Operations/.env`, ainsi que les secrets PostgreSQL et Django et les paramètres SMTP de recette. Pour une instance en service, conserver le nom de projet Compose et les paramètres PostgreSQL existants afin de retrouver les mêmes volumes. Sur un VPS dédié à une nouvelle recette, on peut choisir `COMPOSE_PROJECT_NAME=amblueo-recette-services` dès le premier lancement et le conserver ensuite.

```dotenv
AMBLUEO_INFRA_MODE=production
AMBLUEO_INFRA_DOMAINE=services.amblueo.com
AMBLUEO_INFRA_HOTES=services.amblueo.com
```

Si une ancienne installation avait son fichier `.env` à la racine, reprendre ses valeurs sur le VPS dans `Operations/.env`. Utiliser l’ancienne configuration Compose pour effectuer la sauvegarde préalable si le passage à la nouvelle arborescence n’a pas encore eu lieu.

Vérifier que les enregistrements DNS publics pointent vers le VPS, que les ports 80 et 443 sont accessibles et que le certificat possède le nom attendu.

```bash
sudo install -d -m 755 /var/www/amblueo-acme
sudo certbot certificates
sudo test -r /etc/letsencrypt/live/services.amblueo.com/fullchain.pem
sudo test -r /etc/letsencrypt/live/services.amblueo.com/privkey.pem
```

Réutiliser le certificat existant s’il couvre le domaine et correspond à ces chemins. Sur un hôte neuf, si le certificat manque et que le port 80 est libre, le créer avant de lancer le proxy.

```bash
sudo certbot certonly --standalone --cert-name services.amblueo.com -d services.amblueo.com
```

## Lancer ou mettre à jour la plateforme

Avant une mise à jour d’une instance en service, vérifier qu’une sauvegarde récente de la base et des justificatifs est disponible. Les commandes suivantes s’exécutent depuis la racine du dépôt. Réserver une fenêtre de maintenance pour l’arrêt du proxy et de Django.

```bash
export AMBLUEO_INFRA_CIBLE=recette
./Operations/compose.sh config --quiet
./Operations/compose.sh build web
./Operations/compose.sh up -d --wait db
./Operations/compose.sh stop proxy web
./Operations/compose.sh run --rm --no-deps web python manage.py migrate --noinput
./Operations/compose.sh run --rm --no-deps web python manage.py collectstatic --noinput
./Operations/compose.sh up -d --wait
./Operations/compose.sh exec -T proxy nginx -t
./Operations/compose.sh ps
```

Pour une base neuve, créer le premier compte avec `./Operations/compose.sh run --rm web python manage.py createsuperuser`, puis se connecter et créer une entreprise de test.

Depuis un poste extérieur au serveur, vérifier la redirection et le certificat sans désactiver la vérification TLS.

```bash
curl -sSI http://services.amblueo.com/connexion/
curl -fsS https://services.amblueo.com/health/
curl -fsSI https://services.amblueo.com/connexion/
curl -fsSI https://services.amblueo.com/static/pilot/app.css
```

Attendus : statut 308 avec une destination HTTPS pour la requête HTTP, réponse `ok` sur `/health/`, puis statut 200 pour la connexion et le CSS. Compléter la vérification par une connexion de recette et un e-mail de réinitialisation.

## Renouveler le certificat

Une fois Nginx en service, faire renouveler le certificat via le webroot `/var/www/amblueo-acme`. Si le certificat a été obtenu en mode standalone, adapter sa configuration avec la procédure correspondant à la version installée de Certbot. Tester ensuite le renouvellement avec `sudo certbot renew --dry-run`. [Guide Certbot sur la modification des paramètres de renouvellement](https://eff-certbot.readthedocs.io/en/stable/using.html#modifying-the-renewal-configuration-of-existing-certificates)

Dans le hook de déploiement Certbot, utiliser le chemin absolu du dépôt sur le VPS pour recharger le proxy après un renouvellement réussi.

```bash
AMBLUEO_INFRA_CIBLE=recette /chemin/du/depot/Operations/compose.sh exec -T proxy nginx -s reload
```

Voir le [guide d’exploitation](exploitation.md) pour les sauvegardes, la restauration isolée et le retour arrière.
