# Mise en ligne de Cauri Charts (Django) sur Vercel

Architecture, tout en offre gratuite :

| Élément | Service | Rôle |
|---|---|---|
| Site (pages, admin, images de partage) | **Vercel** | `api/index.py` (Django) ; `public/assets` servi directement |
| Base de données | **Neon** (PostgreSQL) | mêmes tables que le site PHP |
| Fichiers générés (vignettes, logos, posts, captures) | **Vercel Blob** | le disque de Vercel est en lecture seule |
| Chaîne quotidienne (imports, vues, calcul du lundi, posts) | **GitHub Actions** | `.github/workflows/daily.yml`, chaque nuit à 3 h 30 |

Le site PHP reste en place en local tant que la version Django n'est pas en ligne et vérifiée.

## 1. Base Neon

1. Créer un compte sur neon.tech, projet « cauricharts », région Europe (Francfort).
2. Copier la chaîne de connexion **pooled**, de la forme
   `postgresql://…@…-pooler….neon.tech/neondb?sslmode=require`.
3. Copier les données du site actuel (depuis ce PC, MariaDB XAMPP allumé) :

   ```
   cd django
   set DATABASE_URL=postgresql://…?sslmode=require
   .venv\Scripts\python tools\migrate_data.py
   .venv\Scripts\python tools\migrate_data.py --check
   ```
   Le script recrée le schéma (`sql/schema.pg.sql`) puis copie chaque table ; `--check` doit afficher « identique ».

## 2. Projet Vercel

1. Envoyer le dépôt sur GitHub (compte ashbornarise), puis sur vercel.com : *Add New > Project*, importer le dépôt.
   Laisser le dossier racine du dépôt ; `vercel.json` règle le reste.
2. *Storage > Create > Blob* : créer un espace « cauri-media » et le relier au projet (ajoute `BLOB_READ_WRITE_TOKEN`).
   Noter son adresse publique (`https://xxxx.public.blob.vercel-storage.com`).
3. *Settings > Environment Variables* :

   | Variable | Valeur |
   |---|---|
   | `DATABASE_URL` | chaîne Neon pooled |
   | `DJANGO_SECRET_KEY` | 50 caractères aléatoires (générer : `python -c "import secrets; print(secrets.token_urlsafe(50))"`) |
   | `APP_URL` | `https://cauricharts.com` |
   | `APP_ENV` | `production` |
   | `APP_DEBUG` | `false` |
   | `BLOB_PUBLIC_URL` | facultatif : déduite de `BLOB_READ_WRITE_TOKEN` si absente |
   | `APP_KEY` | même valeur que dans le `.env` actuel (empreintes des adresses IP) |

   Les clés d'API (YouTube, Gemini, Spotify) ne sont pas utiles au site : elles servent à la chaîne quotidienne (GitHub).
4. Déployer, puis tester l'adresse `https://…vercel.app` : accueil, un classement, une fiche artiste, `/admin/connexion`.
5. Envoyer les vignettes et logos existants dans le Blob (une fois) :

   ```
   cd django
   set BLOB_READ_WRITE_TOKEN=…
   .venv\Scripts\python -c "import os,django; os.environ['DJANGO_SETTINGS_MODULE']='cauri.settings'; django.setup(); from core import storage; [storage.publish_media_files(d, os.listdir(storage.MEDIA/d)) for d in ('news','partners','social') if (storage.MEDIA/d).is_dir()]"
   ```

## 3. Chaîne quotidienne sur GitHub Actions

Dans le dépôt GitHub : *Settings > Secrets and variables > Actions*, créer :
`DATABASE_URL`, `DJANGO_SECRET_KEY`, `APP_URL`, `YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `SPOTIFY_CLIENT_ID`,
`SPOTIFY_CLIENT_SECRET`, `BLOB_READ_WRITE_TOKEN` (valeurs du fichier de secrets actuel).

Tester tout de suite : onglet *Actions > Chaîne quotidienne > Run workflow*. Le journal de chaque étape s'affiche ;
les fichiers de `storage/logs` sont joints à l'exécution.

Posts avec les clips officiels : les clips sont sur ce PC (dossier Clips). Pour la version avec clips et la copie
dans `Documents\Cauri Charts - Posts`, lancer en local (avec `DATABASE_URL` de Neon) :
`.venv\Scripts\python manage.py generate_posts --all`.

## 4. Nom de domaine (LWS)

Une fois le site vérifié sur l'adresse `…vercel.app` :
1. Vercel : *Settings > Domains* : ajouter `cauricharts.com` et `www.cauricharts.com`.
2. LWS, zone DNS de cauricharts.com :
   - enregistrement **A** `@` → `76.76.21.21`
   - enregistrement **CNAME** `www` → `cname.vercel-dns.com`
   (Vercel affiche les valeurs exactes à reporter si elles diffèrent.) Ne pas toucher aux enregistrements MX : les e-mails restent chez LWS.
3. Le certificat HTTPS est créé automatiquement par Vercel (quelques minutes après la propagation DNS).

## Commandes utiles (dossier `django/`)

| Commande | Rôle |
|---|---|
| `python manage.py daily [--weekly] [--posts]` | chaîne quotidienne complète |
| `python manage.py import_charts --source=apple_music --country=CI` | un import précis |
| `python manage.py compute_weekly --week=2026-W40` | calcul d'une semaine (brouillon) |
| `python manage.py collect` | relevé des vues |
| `python manage.py classify_artists --limit=200` | pays des artistes en attente |
| `python manage.py catalog_tasks news\|discover\|enrich\|watch\|channels` | tâches du catalogue |
| `python manage.py generate_posts --theme=artiste` | posts |
| `python manage.py create_admin email "Nom" [--totp]` | compte d'administration |
| `python manage.py purge [--dry-run]` | durées de conservation (RGPD) |
| `python -m pytest tests` | 72 tests |

## Contrôles de parité (PHP ↔ Django)

`tools/parity.py` (pages publiques), `tools/admin_parity.py` et `tools/admin_actions.py` (admin, sur des copies de base),
`tools/tie_check.py` (classements en direct), `tools/compare_tables.py` (données calculées).
Les seuls écarts restants viennent d'égalités parfaites que MariaDB départage dans un ordre arbitraire
(requêtes sans ORDER BY complet) : Django les départage de façon stable.
