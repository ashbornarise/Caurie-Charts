# Déploiement sur O2switch

Hébergement mutualisé : PHP, MySQL/MariaDB, tâches cron et SSL Let's Encrypt depuis le cPanel. Aucun service Node.js n'est nécessaire.

À faire seulement après les vérifications de marque et l'achat du domaine (README.md, sections 5 et 9).

## 1. Préparer le domaine

1. Dans le cPanel, **Domaines** : ajouter le domaine (ou le pointer vers O2switch si acheté ailleurs, avec les serveurs DNS indiqués par O2switch).
2. Régler la **racine du document** sur le dossier `public` du projet, par exemple `/home/UTILISATEUR/cauricharts/public`. Tout le reste (`src`, `config`, `.env`, `storage`) reste ainsi hors d'atteinte du web.
3. **Sélecteur de version PHP** : choisir PHP 8.2 ou plus, et vérifier que `pdo_mysql`, `mbstring`, `gd`, `fileinfo`, `curl` et `intl` sont cochés.

## 2. Envoyer le code

Par Git (recommandé), depuis le **Terminal** du cPanel :

```bash
cd ~
git clone https://github.com/COMPTE/cauricharts.git
```

Ou par **Git Version Control** dans le cPanel. Ne jamais envoyer le fichier `.env` local ni `storage/uploads`.

## 3. Base de données

1. **Bases de données MySQL** : créer la base (ex. `UTILISATEUR_cauri`), un utilisateur avec un mot de passe fort, et lui donner tous les privilèges sur cette base.
2. Créer le fichier de configuration :

```bash
cd ~/cauricharts
cp .env.example .env
chmod 600 .env
nano .env
```

Valeurs de production :

```ini
APP_NAME="Cauri Charts"
APP_URL=https://cauricharts.com
APP_ENV=production
APP_DEBUG=false
APP_KEY=   # php -r "echo bin2hex(random_bytes(32));"
DB_HOST=localhost
DB_NAME=UTILISATEUR_cauri
DB_USER=UTILISATEUR_cauri
DB_PASS=...
YOUTUBE_API_KEY=...
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

3. Installer le schéma sans les données d'exemple :

```bash
php bin/install.php
php bin/create-admin.php toi@exemple.com "Ton Nom" --totp
```

`--totp` affiche le secret à ajouter dans une application d'authentification (Aegis, Google Authenticator...). Garder le mot de passe affiché dans un gestionnaire de mots de passe.

4. `install.php` importe `database/reference.sql` : les cinq pays, les types de classements et les versions de la formule. Aucune donnée fictive n'est installée (`--demo` est réservé au développement et refusé en production). Le catalogue se remplit avec `bin/import-charts.php` et les actualités avec `bin/import-news.php`.

Base déjà installée avant le 30/09/2026 : lancer une fois `database/migrations/2026-09-30-actualites-partenaires.sql` (phpMyAdmin, onglet Importer).

Ajuster ensuite dans l'admin (Catalogue) les plateformes actives de chaque pays, une fois leur audience réelle vérifiée.

## 4. Droits des dossiers

```bash
chmod -R 775 storage
```

`storage/logs`, `storage/cache/share`, `storage/uploads` et `storage/backups` doivent être inscriptibles par PHP.

## 5. SSL

cPanel, **Let's Encrypt SSL** (ou **AutoSSL**) : générer le certificat pour le domaine et `www`. Le fichier `public/.htaccess` redirige ensuite tout le trafic en HTTPS, et l'application envoie l'en-tête HSTS.

## 6. Tâches cron

cPanel, **Tâches Cron**. Le serveur est à l'heure de Paris : Lomé est à UTC+0, soit 1 h de moins que Paris en hiver et 2 h de moins en été. Les horaires ci-dessous visent la fin de journée à Lomé.

```cron
# Chaîne quotidienne complète, dans l'ordre (voir bin/daily.php) :
# classements des plateformes → liste de suivi et découverte d'artistes → profils → pays des artistes →
# clips YouTube → relevé des vues → popularité Deezer et vues YouTube des artistes suivis → actualités →
# le lundi : classement officiel (brouillon, publication dans l'admin le mardi) →
# lundi, mercredi, vendredi : posts réseaux sociaux → ménage (cache, fichiers orphelins).
# Vers 1 h à Lomé ; dure 15 à 30 minutes.
0 2 * * * cd ~/cauricharts && /usr/local/bin/php bin/daily.php >> storage/logs/cron-stdout.log 2>&1

# Actualités plus fréquentes dans la journée (la chaîne quotidienne les importe aussi)
15 */3 * * * cd ~/cauricharts && /usr/local/bin/php bin/import-news.php >> storage/logs/cron-stdout.log 2>&1

# Sauvegarde quotidienne de la base
0 4 * * * cd ~/cauricharts && /usr/local/bin/php bin/backup.php >> storage/logs/cron-stdout.log 2>&1

# Durées de conservation des données personnelles (politique de confidentialité)
30 4 * * * cd ~/cauricharts && /usr/local/bin/php bin/purge.php >> storage/logs/cron-stdout.log 2>&1
```

## 6 bis. Pages juridiques, cookies et campagne Meta

- Compléter dans `.env` les variables `LEGAL_*`, `PRIVACY_EMAIL` et `HOST_ADDRESS` (coordonnées exactes d'o2switch, à recopier depuis leur site). Tant qu'une valeur manque, les pages affichent « [à compléter] » en surbrillance.
- Faire relire les pages Mentions légales, Confidentialité, Cookies et Conditions par un juriste avant le lancement, et fixer le droit applicable (Togo ou France) avec la structure juridique.
- Google Analytics : renseigner `GA_MEASUREMENT_ID` (format `G-XXXXXXXXXX`). Meta Pixel (campagne de 100 €, étape 10 du README) : renseigner `META_PIXEL_ID`. Dès qu'un des deux est rempli, le bandeau de consentement apparaît et ces outils ne se chargent qu'après accord. Laisser vide tant qu'ils ne servent pas : pas de bandeau, pas de cookie.

Vérifier le chemin de PHP avec `which php` dans le Terminal (il dépend de la version choisie). Pour recevoir un e-mail en cas d'erreur, renseigner l'adresse en haut de la page Tâches Cron.

## 7. Clés API

- **YouTube Data API v3** : Google Cloud Console, créer un projet, activer l'API, créer une clé API restreinte à cette API (et, si possible, à l'adresse IP du serveur). Quota par défaut : 10 000 unités par jour ; `videos.list` coûte 1 unité par lot de 50 vidéos.
- **Spotify** : developer.spotify.com, créer une application, récupérer l'identifiant et le secret. Métadonnées seulement.
- **Audiomack** : demander l'accès API. En attendant, relevés manuels dans l'admin.

Les clés vont uniquement dans `.env`, jamais dans le dépôt. Relire les conditions d'utilisation de chaque plateforme avant d'activer la collecte (voir les commentaires en tête de `src/Services/Platforms/*Client.php`).

## 8. Vérifications après mise en ligne

- `https://domaine/` affiche la page d'accueil (vide tant qu'aucun classement n'est publié).
- `https://domaine/admin` demande la connexion, puis le code 2FA.
- `https://domaine/robots.txt` autorise l'indexation (APP_ENV=production) et `sitemap.xml` liste les pages.
- `php bin/collect.php` à la main : YouTube doit répondre `ok`.
- Après une semaine de relevés : `php bin/compute-weekly.php`, contrôle dans l'admin, publication.
- Tester l'image de partage d'un classement publié (`/partage/ID-square`) : elle doit être en PNG. Si les polices système manquent, déposer des polices TTF libres (DejaVu, ou Playfair Display et Inter, licence OFL) dans `resources/fonts/` sous les noms `serif-bold.ttf`, `sans.ttf` et `sans-bold.ttf`, ou renseigner `SHARE_FONT_SERIF` et `SHARE_FONT_SANS`.

## 9. Mises à jour

```bash
cd ~/cauricharts
php bin/backup.php
git pull
```

Pas d'étape de compilation : le CSS et le JavaScript sont des fichiers statiques. Vider `storage/cache/share` si la mise en page des images de partage a changé.

## 10. Sauvegardes

`bin/backup.php` garde les 30 dernières sauvegardes dans `storage/backups`. O2switch fait aussi des sauvegardes (JetBackup dans le cPanel). Télécharger régulièrement une copie hors du serveur.
