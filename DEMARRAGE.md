# Cauri Charts : démarrage local

Le site tourne entièrement sur des données d'exemple fictives, sans aucune clé API. Le cadrage du projet est dans [README.md](README.md) et les règles de calcul dans [METHODOLOGIE.md](METHODOLOGIE.md).

## Prérequis

PHP 8.1 ou plus (8.2 visé en production), extensions `pdo_mysql`, `mbstring`, `fileinfo`, et `gd` pour les images de partage en PNG (sans GD, elles sont servies en SVG). MariaDB ou MySQL. Composer n'est pas nécessaire : le projet n'a aucune dépendance et charge ses classes tout seul.

Sous Windows, XAMPP ou Laragon fournissent tout. Avec XAMPP, PHP est dans `C:\xampp\php\php.exe` et GD s'active en retirant le `;` devant `extension=gd` dans `C:\xampp\php\php.ini` (ou en ajoutant `-d extension=gd` aux commandes).

## Démarrage en cinq commandes

```bash
cp .env.example .env                     # puis mettre les accès de la base et une APP_KEY aléatoire
php bin/install.php --fresh              # crée la base, importe schema.sql + reference.sql (données réelles uniquement)
php bin/create-admin.php toi@example.com "Ton Nom"   # affiche un mot de passe généré
php bin/daily.php --posts                # chaîne complète : classements, découverte d'artistes, vues, actualités, posts
php -S localhost:8000 -t public          # serveur de développement
```

Puis ouvrir http://localhost:8000 (site) et http://localhost:8000/admin (administration).

`php -S localhost:8000 -t public public/index.php` fait la même chose et sert en plus `robots.txt` et `sitemap.xml`, que le serveur intégré refuse sans script routeur. En production, Apache s'en charge via `public/.htaccess`.

## La chaîne quotidienne (bin/daily.php)

Une seule commande enchaîne tout, dans l'ordre, chaque nuit :

| Étape | Ce qu'elle fait |
|---|---|
| 1. Classements des plateformes | Apple Music, Deezer, Shazam, tendances YouTube, nouveaux clips YouTube (Togo, Bénin) : positions et nouveaux artistes |
| 2. Suivi et découverte | Liste de suivi (config/watchlist.php), Wikidata et réseau Deezer, filtrés par fanbase (config/discovery.php) |
| 3. Profils et pays | Photo et fans Deezer ; pays vérifié par MusicBrainz, Wikidata, indices de scène, IA gratuite (Gemini) ; les cas incertains vont dans /admin/import |
| 4. Données de chaque titre | Deezer : titres des classements retrouvés (popularité, pochette). YouTube : chaîne de chaque artiste trouvée une fois (100 unités), puis toutes ses vidéos rattachées à ses titres (clip, audio, lyrics, live) pour 1 à 2 unités ; recherche titre par titre pour le reste ; enfin relevé quotidien des vues et des likes |
| 5. Sources calculées | Popularité Deezer et vues YouTube des artistes suivis : rendent visibles les pays sans classement de plateforme |
| 6. Actualités | RFI Musique, NotJustOk, AmeyawDebrah |
| 7. Lundi | Classement officiel de la semaine en brouillon (publication dans l'admin) |
| 8. Lundi, mercredi, vendredi | Posts réseaux sociaux, rangés dans Documents\Cauri Charts - Posts |
| 9. Ménage | Cache des classements en direct, fichiers de posts abandonnés |

Le quota YouTube (10 000 unités par jour) est partagé par tous les modules, avec une réserve pour le relevé des vues.

## Ce que contiennent les données d'exemple

Neuf semaines de relevés quotidiens (du 26 juillet au 28 septembre 2026) pour 86 titres et 48 artistes fictifs dans les cinq pays. Plusieurs cas sont prévus pour tester le système :

- au Togo, un titre présent sur YouTube seulement mais très écouté, plafonné à la 6e place par la règle de diversité ;
- au Togo, deux titres en forte progression hors Top 20, qui alimentent le Buzz Chart ;
- au Bénin, semaine du 21 septembre : un pic suspect sur Audiomack et un ratio vues / « j'aime » anormal sur YouTube. La semaine reste en brouillon : il faut valider ou exclure ces titres dans l'admin avant de publier ;
- une déclaration validée (Spotify for Artists, comptée car recoupée) et une déclaration en attente.

Les autres semaines sont publiées automatiquement par `--demo` (option refusée quand `APP_ENV=production`).

## Tâches planifiées, lancées à la main

| Commande | Rôle | Fréquence en production |
|---|---|---|
| `php bin/import-charts.php` | Import des classements des plateformes (Apple Music), création des nouveaux titres, recherche des clips YouTube | tous les jours, avant `collect.php` |
| `php bin/collect.php` | Relevé des compteurs (YouTube, métadonnées Spotify) | tous les jours vers 23 h 30, heure de Lomé |
| `php bin/compute-weekly.php` | Calcul de la semaine écoulée, en brouillon | le lundi matin |
| `php bin/backup.php` | Sauvegarde de la base | tous les jours |
| `php bin/purge.php` | Applique les durées de conservation des données personnelles (`--dry-run` pour simuler) | tous les jours |

Options utiles de `compute-weekly.php` : `--country=TG`, `--week=2026-W39`, `--from=2026-07-27 --to=2026-09-27` (rattrapage), `--correction="raison"` pour recalculer une semaine déjà publiée (la correction est affichée sur la page du classement).

Sans clé dans `.env`, `collect.php` ignore les plateformes et le dit. Les erreurs des tâches sont écrites dans `storage/logs/cron-AAAA-MM.log`.

## Tests

```bash
php tests/run.php            # tous les tests
php tests/run.php diversité  # filtre par nom
```

Ils couvrent le calcul (variations, poids, déclarations, égalités, règle de diversité, Buzz, Fresh, Icon, classement régional), l'anti-fraude (pic, ratio YouTube, déclaration contredite), les clients API avec de fausses réponses (lots de 50, quota épuisé) et la sécurité (TOTP, mots de passe, échappement).

## Organisation du code

```text
public/        point d'entrée (index.php), CSS, JS, logo provisoire
src/Core/      routeur, requêtes, vues, session, CSRF, traduction, base de données
src/Services/Charts/      ScoreCalculator et ChartRanker (purs, testés), ChartService (base), Period
src/Services/Platforms/   YouTube, Spotify, plateformes manuelles, collecte, quota
src/Services/Security/    connexion, limitation des tentatives, TOTP
src/Controllers/          pages publiques et admin
templates/     gabarits HTML (layout, pages, admin)
lang/          fr.php, en.php
config/        app.php, charts.php (noms des classements), formula.php (poids de départ)
bin/           install, collect, compute-weekly, create-admin, backup, generate-seed
database/      schema.sql, seed.sql
tests/         lanceur autonome et tests
docs/          déploiement O2switch
```

## Règles à garder en tête

- Le nom de marque et l'adresse du site viennent de `.env` (`APP_NAME`, `APP_URL`) : un changement de nom ne demande aucune modification de code.
- Le logo est `public/assets/img/logo.svg`, provisoire : le remplacer par le monogramme définitif.
- Les noms des classements sont dans `config/charts.php`.
- Aucune position ne se modifie à la main : l'admin valide ou exclut un titre signalé (avec une raison écrite au journal d'audit), puis le classement est recalculé.
- Les captures d'écran des déclarations sont rangées dans `storage/uploads`, hors du dossier public.
- `seed.sql` se régénère avec `php bin/generate-seed.php`. Ne jamais y mettre de vraies données d'artistes.
