<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="cauri-charts-logos/02-horizontal-blanc-transparent/cauri-charts-horizontal-blanc.svg">
    <img src="cauri-charts-logos/01-horizontal-noir-transparent/cauri-charts-horizontal-noir.svg" alt="Cauri Charts" width="360">
  </picture>
</p>

<p align="center">
  <strong>Les classements musicaux de l'Afrique de l'Ouest.</strong><br>
  Togo · Bénin · Ghana · Côte d'Ivoire · Sénégal<br>
  <a href="https://cauricharts.com">cauricharts.com</a>
</p>

---

Cauri Charts est un média qui publie chaque vendredi les classements musicaux de cinq pays d'Afrique de l'Ouest, et un classement régional qui les réunit. Les chiffres viennent des plateformes publiques (YouTube, Apple Music, Deezer, Shazam, Spotify, Audiomack, Boomplay), la méthode est publique, et aucune position ne se modifie à la main.

Autour des classements, le projet produit aussi des contenus : posts automatiques, magazine PDF, documentaires vidéo « Cauri raconte », lives TikTok et un Studio de publication sur téléphone.

## Ce que publie le site

| Rubrique | Contenu |
|---|---|
| **Classements par pays** | Prime Chart (le classement principal), Buzz Chart (les plus fortes progressions), Fresh Chart (les nouveautés), Icon Chart (les artistes), Legend Chart (le cumul depuis le lancement), et le classement complet de tous les titres mesurés |
| **Afrique de l'Ouest** | Le classement régional des cinq pays, chaque pays étant pondéré par la racine de sa population et la fiabilité de ses données |
| **Fiches** | Une page par artiste et par titre : historique des positions, meilleures places, liens vers les plateformes |
| **Méthodologie** | La formule, les sources et les règles anti-fraude, en français et en anglais |
| **Actualités** | Cauri Matin, Cauri Hebdo, Cauri Monde, l'actualité des artistes, et les plus écoutés dans le monde |
| **Documents** | Le magazine de la semaine et les dossiers, à feuilleter et à télécharger en PDF |
| **Pour les artistes et partenaires** | Formulaire de déclaration, revendication de fiche, widget à intégrer, espaces partenaires, newsletter |

Le classement de la semaine couvre la période du vendredi au jeudi (heure de Lomé). Il est calculé et contrôlé le vendredi, puis publié le vendredi à 19 h UTC.

## Comment on calcule

Le détail est dans [METHODOLOGIE.md](METHODOLOGIE.md) et sur la page Méthodologie du site. La formule en vigueur est la **v7 (méthodologie 1.7, depuis la semaine 48)** :

- la place d'un titre dans le classement d'une plateforme est convertie en part d'écoute estimée (loi de Zipf-Mandelbrot), et un titre absent compte comme classé juste après le dernier ;
- les vues YouTube sont compressées et pondérées selon le pays ; Deezer, Shazam et le Spotify du pays entrent dans le score ;
- les sources sont combinées par moyenne géométrique, et un titre doit être présent sur plusieurs sources pour atteindre le haut du classement ;
- le score s'affiche en **indice Cauri de 0 à 100** (le N°1 vaut 100) ;
- un contrôle statistique bloque les hausses suspectes. Une exclusion est toujours motivée et inscrite au journal.

Règle des pays : un artiste est classé dans le pays où il soumet sa musique, pas selon sa nationalité.

## Architecture

Tout tourne dans le cloud. Un ordinateur ne sert qu'à développer et à piloter.

| Élément | Service | Rôle |
|---|---|---|
| Site, admin, Studio, API | **Vercel** (région Francfort) | Django servi par [api/index.py](api/index.py) ; les fichiers de `public/assets` sont servis directement |
| Base de données | **Neon** (PostgreSQL) | Classements, relevés, artistes, titres, journal d'audit |
| Fichiers générés | **Vercel Blob** | Visuels, posts, vidéos du Studio, documents |
| Tâches planifiées | **Vercel Cron** + **GitHub Actions** | Vercel réveille la chaîne de nuit (`/cron/nuit`) ; GitHub Actions fait le travail lourd |
| Publication | API **Meta** (Instagram, Facebook), **Buffer**, **TikTok**, **Telegram** | Posts et vidéos sur les réseaux |
| Rédaction et vérification | DeepSeek, Gemini, Groq, OpenRouter | Pays des artistes, relecture des textes, comité de rédaction |

### Le calendrier automatique

| Quand (UTC) | Tâche |
|---|---|
| Chaque nuit, 1 h | Chaîne quotidienne : imports des classements des plateformes, découverte d'artistes, relevé des vues, actualités, posts |
| Chaque matin | Rattrapage si la nuit n'a pas tourné, comité de rédaction, vérification des pays et des comptes officiels |
| Chaque jour, 12 h 30 | Sorties et classements de la mi-journée |
| Chaque jour, 21 h 40 | Écoutes Spotify des titres |
| Jeudi | Genres des titres, relevé Spotify, répétition générale de la publication |
| **Vendredi, 19 h** | **Publication du classement officiel**, puis contrôle à 21 h 15 |
| Lundi, 7 h | Rapport hebdomadaire |
| Dimanche | Sauvegarde complète de la base |

Chaque tâche a son fichier dans [.github/workflows/](.github/workflows/). Les tâches du Studio (montage, clips, publication) partent à la demande.

## Organisation du dépôt

```text
api/index.py         point d'entrée Vercel (Django)
django/
  cauri/             réglages et routes
  core/              pages, admin, Studio, live, publication, calcul des classements
  core/management/   commandes de la chaîne (daily, compute_weekly, publish_chart, monde, studio_job…)
  templates/         gabarits Jinja (site, admin, pages légales)
  lang/              textes du site en français et en anglais
  sql/               schéma PostgreSQL
  tests/             tests automatisés (pytest)
public/assets/       CSS, JS, images, polices servies telles quelles
config/              noms des classements, coûts, recettes
cauri-charts-logos/  logo officiel dans tous ses formats
docs/                déploiement, données, feuille de route, dossier de lancement
.github/workflows/   tâches planifiées et tâches du Studio
src/, bin/, templates/  ancienne version PHP, gardée comme référence
```

## Développer en local

Prérequis : Python 3.12, Node LTS, FFmpeg et Git.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r requirements-pipeline.txt   # seulement pour la chaîne de nuit (visages, détourage, captures)

cd django
..\.venv\Scripts\python manage.py runserver               # site sur http://localhost:8000
..\.venv\Scripts\python -m pytest tests                   # tests
```

Les secrets (base Neon, clés d'API, jetons des réseaux) ne sont **jamais** dans le dépôt. Ils sont rangés dans les variables d'environnement Vercel et dans les secrets GitHub Actions. En local, on les récupère avec `vercel env pull` dans un fichier placé hors du projet (variable `SECRETS_FILE`). Le modèle de configuration est [.env.example](.env.example).

Commandes utiles (dossier `django/`) :

| Commande | Rôle |
|---|---|
| `python manage.py daily` | Chaîne quotidienne complète |
| `python manage.py compute_weekly --week=2026-W48` | Calcul d'une semaine, en brouillon |
| `python manage.py publish_chart` | Publication du classement officiel |
| `python manage.py collect` | Relevé des vues |
| `python manage.py create_admin email "Nom"` | Compte d'administration |
| `python manage.py purge --dry-run` | Durées de conservation des données (RGPD) |

## Documentation

| Fichier | Sujet |
|---|---|
| [METHODOLOGIE.md](METHODOLOGIE.md) | Formule, sources, anti-fraude, texte public de la méthodologie |
| [docs/DEPLOIEMENT-VERCEL.md](docs/DEPLOIEMENT-VERCEL.md) | Mise en ligne : Neon, Vercel, Blob, GitHub Actions, nom de domaine |
| [docs/DONNEES-ET-CLASSEMENTS.md](docs/DONNEES-ET-CLASSEMENTS.md) | D'où viennent les données et comment elles deviennent un classement |
| [docs/FEUILLE-DE-ROUTE.md](docs/FEUILLE-DE-ROUTE.md) | Vision et étapes à venir |
| [docs/DOSSIER-DE-LANCEMENT.md](docs/DOSSIER-DE-LANCEMENT.md) | Le cadrage d'origine (septembre 2026), gardé pour l'historique |
| [DEMARRAGE.md](DEMARRAGE.md) | Démarrage de l'ancienne version PHP |

## Règles du projet

- **Neutralité.** Cauri Charts est un média distinct de Nova Luz Music. Tout artiste signé chez Nova Luz porte un badge visible et suit les mêmes règles que les autres.
- **Aucune position à la main.** L'admin peut seulement exclure un titre suspect, avec une raison écrite au journal d'audit.
- **Le mot « Billboard » n'apparaît nulle part**, pas plus que « Hot 100 », « Billboard 200 » ou « Artist 100 ».
- **Marque et adresse en configuration** (`APP_NAME`, `APP_URL`), jamais écrites en dur dans le code.

---

<p align="center"><sub>Cauri Charts · le cauri, le coquillage qui servait de monnaie en Afrique de l'Ouest : ce qui compte.</sub></p>
