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

## Valider et déployer avec GitHub Actions

Le workflow **Validation et déploiement de recette** vérifie le code à chaque
push et pull request. Il construit l’image, exécute les vérifications Django sur
PostgreSQL et teste la navigation ainsi que le modèle de notification dans Chromium aux
formats bureau et mobile.
Une capture d’écran est jointe au run si une assertion du parcours échoue dans
le navigateur. Le script utilise un projet Compose temporaire et les réglages
de démonstration de `Operations/.env.example`.

Depuis un poste équipé de Docker, lancer `./Operations/verifier.sh`. Pour inclure
le parcours navigateur, préparer un environnement Python local et lancer :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install playwright==1.65.1
.venv/bin/python -m playwright install --with-deps chromium
AMBLUEO_TEST_PYTHON="$PWD/.venv/bin/python" ./Operations/verifier.sh --affichage
```

### Préparer l’accès SSH

- Sur `infra01`, utiliser un compte de déploiement dédié. Ce compte doit pouvoir
  lire et mettre à jour le dépôt de recette, utiliser Docker et récupérer
  `origin/main` sans invite. Configurer pour cette récupération une clé de
  déploiement GitHub en lecture seule.
- Après la fusion du workflow dans `main`, préparer le dépôt du serveur sur
  `main` avec `Operations/deployer-recette.sh` présent. Conserver le
  `Operations/.env` existant, le projet Compose, les volumes et le réseau
  Postfix. La mise à jour du checkout à cette étape ne relance aucun service.
- Créer une **seconde paire de clés**, dédiée au lien Actions vers `infra01`.
  Sur `infra01`, ajouter sa clé publique à `~/.ssh/authorized_keys` du compte de
  déploiement. Remplacer le chemin et la clé dans cet exemple. La commande
  forcée lit le SHA à déployer sur son entrée standard.

```text
restrict,command="/chemin/absolu/amblueo-services/Operations/deployer-recette.sh" ssh-ed25519 AAAA... github-actions-recette
```

Dans GitHub, ouvrir **Settings → Environments → New environment**, nommer
l’environnement `recette` et limiter ses déploiements à la branche `main`.
Configurer les paramètres suivants dans cet environnement.

| Type | Nom | Valeur |
| --- | --- | --- |
| Secret | `RECETTE_SSH_PRIVATE_KEY` | Clé privée dédiée au lien Actions vers `infra01` |
| Variable | `RECETTE_SSH_TARGET` | Compte et nom d’hôte SSH, par exemple `deploiement@infra01.amblueo.com` |
| Variable | `RECETTE_SSH_KNOWN_HOSTS` | Ligne `known_hosts` avec le nom d’hôte et la clé publique de l’hôte, vérifiée sur `infra01` |

Pour préparer la dernière valeur avec une clé d’hôte Ed25519, lire la clé sur
le serveur via une session déjà vérifiée :

```bash
sudo awk '{print "infra01.amblueo.com", $1, $2}' /etc/ssh/ssh_host_ed25519_key.pub
```

La clé utilisée sur le poste pour les pushes Git reste sur le poste. Garder
`Operations/.env` et les clés privées hors de Git.

### Lancer le déploiement

1. Vérifier les checks de la pull request et fusionner dans `main`.
2. Vérifier qu’une sauvegarde récente est disponible et réserver la fenêtre
   d’interruption.
3. Ouvrir **Actions → Validation et déploiement de recette → Run workflow**,
   choisir `main` et lancer le workflow.
4. Ouvrir le job **Déployer sur infra01**. Il démarre après la validation du
   même commit et affiche le SHA déployé, l’état Compose et le résultat du
   contrôle HTTPS. Un verrou empêche deux mises à jour simultanées du
   checkout de recette.

En cas d’échec après l’arrêt de `web` et du proxy, consulter l’étape en erreur et
les logs sur `infra01`. Corriger la cause avant de relancer le déploiement. Pour
les changements de messagerie, confirmer aussi la réception réelle d’une
notification dans une boîte de recette.
