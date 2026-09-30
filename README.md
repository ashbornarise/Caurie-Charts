# Cauri Charts : dossier de lancement

Anciennement "Nova Board". Version 1.1, 29 septembre 2026. Ce document rassemble le cadrage, l'identité, les cinq pays de départ, la famille de classements, les instructions pour développer le site en local, le prompt pour l'agent de développement, le prompt du logo et l'ordre des étapes. La méthodologie détaillée est dans le fichier METHODOLOGIE.md.

## 1. Cadrage

**Projet.** Cauri Charts publie des classements musicaux hebdomadaires, mensuels et annuels pour l'Afrique de l'Ouest. Il démarre au Togo et s'étend à quatre autres pays.

**Le nom.** Le cauri est le coquillage qui servait de monnaie en Afrique de l'Ouest : ce qui compte, ce qui a de la valeur. Le nom est retenu, sous réserve des vérifications de la section 5.

**Domaines.** Vérification GoDaddy du 29 septembre 2026 :

| Domaine | Statut |
|---|---|
| cauricharts.com | Libre |
| cauricharts.africa | Libre |
| cauri.africa | Libre |
| cauricharts.music | Libre |
| cauri.music | Libre |
| cauri-charts.com | Libre |
| cauri.charts | Pris |
| cauricharts.tg | Pris |

Rien n'est encore acheté. Sélection conseillée : cauricharts.com (principal), cauricharts.africa (identité) et cauri.africa (protège le nom seul). O2switch ne gère pas forcément toutes les extensions : si besoin, acheter chez un autre registrar et pointer les DNS vers O2switch.

**Point de vigilance.** Un DJ, Da Le (Havana), a publié en juillet 2024 un "Cauri Chart" sur Beatport (sélection Afro House et Organic House). Ce n'est pas un média, mais le nom est très proche dans le même secteur. Il faut le vérifier dans les registres de marques avant de dépenser sur le logo et la publicité. Si une vérification échoue, la piste de repli est "Harmattan Charts".

**Le nom "Billboard".** C'est une marque déposée : il ne doit apparaître nulle part (nom, visuels, code, noms de classements). Les termes "Hot 100", "Billboard 200" et "Artist 100" sont aussi exclus.

**Hébergement.** O2switch (mutualisé : PHP, MySQL, tâches cron, SSL). Pas de serveur Node.js permanent, donc le site est conçu en PHP.

**Rattachement.** Cauri Charts est un média distinct de Nova Luz Music, sous la future structure Novaluz Group. Les entités ne sont pas encore constituées juridiquement : la holding vient après la validation du projet.

**Neutralité.** Tout artiste signé chez Nova Luz porte un badge visible, et la page Méthodologie explique le lien entre les deux entités. Sans cela, la crédibilité du classement ne tient pas.

**Règle des pays.** Un artiste est classé dans le pays où il soumet sa musique. Le pays où il est le plus écouté s'affiche à part, comme statistique sur sa fiche. Cette répartition vient des captures fournies par l'artiste, car les plateformes ne la donnent qu'à l'artiste lui-même.

**Positionnement face à Billboard.** Billboard Africa existe depuis juin 2025 (partenariat avec Global Venture Partners), mais son onglet classements africains affichait "Coming soon" lors de la dernière vérification. Cauri Charts se lance sous sa propre marque. Un contact avec Billboard Africa se prépare plus tard, avec des chiffres à montrer, pour proposer un partenariat de complémentarité sur l'Afrique francophone de l'Ouest.

## 2. Identité visuelle

**Couleur.** Le violet du logo actuel, #8B52FF, sert d'accent unique. Le texte posé sur le violet reste noir. Le reste du site est en noir, blanc et gris.

**Typographie.** Serif à fort contraste pour les titres et les rangs, sans-serif pour le reste (noms de titres, chiffres, navigation).

**Le logo actuel doit être refait.** Le monogramme "NB" désignait Nova Board. Avec le nom Cauri Charts, il faut un nouveau monogramme (par exemple "C" seul, ou "CC"). On garde la direction : serif éditorial, violet et noir, fond transparent.

Corrections à appliquer au nouveau monogramme, tirées des versions actuelles :
- La lettre doit se lire tout de suite : pas de superposition qui mange les formes (le B se lisait comme un D).
- Épaissir les traits fins, qui disparaissent en petit. Test : réduire à 32 pixels, la lettre doit rester lisible.
- Le texte "Cauri Charts" se place sous le monogramme ou à sa droite, jamais au milieu.
- Prévoir une version aplat sans dégradé (impression, tampon, une couleur).
- Fournir en SVG à fond transparent, pas en JPG sur fond gris.

## 3. Les cinq pays de départ

| Pays | Code | Langue du site | Rôle |
|---|---|---|---|
| Togo | TG | Français | Pays pilote, Top 20 |
| Bénin | BJ | Français | Top 10 au départ |
| Ghana | GH | Anglais (sous-titres FR) | Top 10 au départ |
| Côte d'Ivoire | CI | Français | Top 10 au départ |
| Sénégal | SN | Français | Top 10 au départ |

Le Nigeria est laissé de côté volontairement : le marché est déjà couvert par des classements établis, et il écraserait les autres pays en volume. Il peut devenir le sixième pays plus tard.

**Règles de départ, à ajuster avec les vraies données.**
- Le Togo publie un Top 20. Les autres pays publient un Top 10, et passent à 20 quand assez de titres ont des données fiables (seuil à fixer après quatre semaines de collecte).
- Chaque pays a sa propre liste de plateformes actives. Avant de brancher quoi que ce soit, vérifier pour chaque pays quelles plateformes ont réellement de l'audience (YouTube, Audiomack, Boomplay, Spotify, Apple Music, Deezer).

## 4. Famille de classements

Noms proposés, à confirmer. Le détail (contenu, périodes, règles) est dans METHODOLOGIE.md.

| Classement | Rôle |
|---|---|
| Prime Chart | Classement principal par pays (l'équivalent du "Hot 100") |
| Buzz Chart | Les plus fortes progressions |
| Fresh Chart | Nouveautés et artistes émergents |
| Icon Chart | Classement des artistes |
| Legend Chart | Cumul depuis le lancement ("tout temps") |
| Vintage Chart | Bilan de l'année |
| Prime Chart Afrique de l'Ouest | Classement total des cinq pays, affiché en page d'accueil |

Lancement : Prime Chart, Buzz Chart, Fresh Chart et Icon Chart. Le reste vient après six à huit semaines de régularité.

## 5. Vérifications avant d'investir

À faire avant d'acheter le domaine principal en série, de payer le logo ou de lancer la publicité :

1. **Marques.** Chercher "Cauri" dans la base gratuite de l'OMPI (Global Brand Database), dans TMview (EUIPO), et à l'OAPI (qui couvre le Togo et seize autres pays). Classes à regarder : 9 (enregistrements numériques), 35 (publicité et médias), 41 (divertissement, musique) et 42 (logiciels en ligne).
2. **Réseaux sociaux.** Vérifier que @cauricharts est libre sur Instagram, TikTok, X et YouTube.
3. **Recherche générale.** Chercher "Cauri Charts" sur Google et sur Beatport pour voir ce qui existe déjà.
4. **Décision.** Si un obstacle sérieux apparaît, basculer sur "Harmattan Charts" ou une autre piste, et refaire les vérifications.

Un domaine libre ne veut pas dire un nom libre : le contrôle de marque est la vraie vérification.

## 6. Développement en local

Tu construis le site sur ton ordinateur avant tout achat. Rien de ce qui suit ne dépend du domaine ni de l'hébergement.

**Outils nécessaires.** PHP 8.2 ou plus, Composer, MariaDB ou MySQL, Git. Sous Windows, Laragon installe PHP, MySQL et Composer en une fois. Sous Mac, Homebrew (php, composer, mariadb). Sous Linux, les paquets de la distribution.

**Structure de dossiers proposée.**

```text
cauricharts/
  public/            point d'entrée web (index.php, CSS, images)
  src/               code de l'application (contrôleurs, modèles, services)
  templates/         pages HTML
  lang/              traductions (fr.php, en.php)
  bin/               scripts en ligne de commande (collecte, calcul)
  database/          schema.sql, seed.sql
  tests/             tests du calcul de classement
  .env.example       modèle de configuration
  .gitignore
```

**Démarrage.**

1. Créer le dossier et initialiser Git. Ajouter `.env` au fichier `.gitignore` avant le premier commit.
2. Copier `.env.example` vers `.env` et y mettre les accès de la base locale.
3. Créer la base `cauricharts`, puis importer `database/schema.sql` et `database/seed.sql` (données d'exemple).
4. Lancer le serveur intégré de PHP depuis le dossier du projet : `php -S localhost:8000 -t public`
5. Ouvrir http://localhost:8000.

**Règles en local.**
- Tout fonctionne d'abord sur les données d'exemple, sans aucune clé API. La clé YouTube n'entre en jeu qu'à l'étape de collecte réelle, et reste dans `.env`, jamais dans le dépôt.
- Les tâches planifiées (cron) sont lancées à la main : `php bin/collect.php` pour le relevé quotidien, `php bin/compute-weekly.php` pour le calcul hebdomadaire. Les noms de scripts sont une proposition.
- Ne jamais copier de vraies données personnelles d'artistes dans la base de test.
- Le nom du domaine et l'adresse du site sont des variables de configuration, pas du texte écrit en dur : le changement de nom éventuel ne coûtera rien.

**Ordre de construction conseillé.** 1) schéma de base et données d'exemple, 2) page d'accueil et classement complet (reproduire la maquette), 3) calcul du classement avec tests, 4) fiches artiste et titre, 5) page Méthodologie, 6) formulaire de déclaration d'artistes, 7) administration, 8) collecte YouTube.

## 7. Prompt : site et API

À donner tel quel à un agent de développement (Claude Code ou équivalent). Il vise d'abord le développement en local, puis O2switch.

```text
Tu es un développeur full-stack senior. Construis le site Cauri Charts,
un média de classements musicaux pour l'Afrique de l'Ouest. Le nom de
domaine n'est pas encore fixé : l'adresse du site et le nom de marque
sont des variables de configuration, jamais du texte en dur.

CONTEXTE
Cauri Charts publie des classements de titres par pays (Togo, Bénin,
Ghana, Côte d'Ivoire, Sénégal) avec trois périodes : semaine, mois,
année. Le Togo publie un Top 20, les autres pays un Top 10 (taille
configurable par pays). Le site doit inspirer confiance : la méthodologie
est publique et chaque classement est reproductible à partir des données
stockées. Le fichier METHODOLOGIE.md fait référence pour la formule, les
classements et les règles anti-fraude.

RÈGLE DES PAYS
Un artiste est classé dans le pays où il soumet sa musique (pays de
soumission, pas de nationalité). Le pays où il est le plus écouté est
une statistique affichée sur sa fiche, alimentée par les captures
d'écran que fournit l'artiste, sans effet sur son classement.

PHASE 1 : DÉVELOPPEMENT LOCAL
- Le projet doit démarrer sur un ordinateur avec PHP 8.2, Composer et
  MariaDB/MySQL, et se lancer avec : php -S localhost:8000 -t public
- Fournir .env.example, schema.sql, seed.sql (données d'exemple
  réalistes mais fictives, reproduisant la maquette), et un README de
  démarrage local en quelques commandes.
- Aucune clé API nécessaire pour faire tourner le site sur les données
  d'exemple. Les intégrations API sont écrites derrière des interfaces
  et testables avec de fausses réponses.
- Les scripts cron sont des commandes exécutables à la main :
  bin/collect.php (relevé quotidien) et bin/compute-weekly.php (calcul
  hebdomadaire).

PHASE 2 : DÉPLOIEMENT O2SWITCH (plus tard)
Hébergement mutualisé : PHP 8.2, MySQL/MariaDB, cron, SSL Let's Encrypt.
Aucun service Node.js permanent. Prévoir la documentation de déploiement
pas à pas (base, cron, SSL, variables d'environnement).

CONTRAINTES TECHNIQUES
- Architecture MVC simple en PHP (micro-framework type Slim ou code
  maison propre). Pas de framework lourd.
- Front mobile-first, CSS compilé en fichier statique, JavaScript
  minimal. Chargement rapide sur connexion 3G/4G moyenne.
- Interface en français, structure prête pour l'anglais (fichiers de
  traduction, pas de texte en dur).
- Secrets (clés API, mots de passe base) dans .env hors du dossier
  public et listé dans .gitignore.

DIRECTION VISUELLE
Fond blanc et noir, un seul accent violet #8B52FF (texte noir posé sur
le violet). Titres et rangs en serif à fort contraste, le reste en
sans-serif. Le classement est le héros de la page. Pas de dégradés, pas
d'effets décoratifs. Référence : la maquette d'accueil fournie (en-tête
avec logo, titre "Togo Top 20", sélecteur Semaine/Mois/Année, liste de
titres avec rang, pochette, titre, artiste, évolution, badge du label,
bloc méthodologie, sélecteur de pays, pied de page). Le logo est un
fichier remplaçable (SVG) : prévoir un emplacement provisoire.

PAGES PUBLIQUES
1. Accueil : classement vedette du pays pilote, sélecteur de période.
2. Classement complet par pays et par période, avec historique.
3. Fiche artiste : titres classés, meilleures positions, évolution,
   pays d'écoute principal (si déclaré).
4. Fiche titre : courbe de position, liens vers les plateformes.
5. Méthodologie : sources, formule, règles anti-fraude, transparence
   sur le lien avec Nova Luz.
6. À propos et contact.
Chaque page a ses balises SEO, ses données Open Graph, et une image de
partage générée pour chaque classement (format carré et format story)
pour se partager facilement sur Instagram et TikTok.

CLASSEMENTS (noms provisoires, dans un fichier de configuration)
Prime Chart, Buzz Chart, Fresh Chart, Icon Chart au lancement. Legend
Chart (cumul depuis le début) dès le premier jour, vide au départ.
Vintage Chart et Prime Chart Afrique de l'Ouest en phase 2 : prévoir la
structure de données sans les afficher. N'utilise jamais les termes
"Hot 100", "Billboard 200", "Artist 100" ni le mot "Billboard".

MODÈLE DE DONNÉES (MySQL)
countries, artists (avec submission_country et label_owner pour repérer
les artistes Nova Luz), tracks, track_platform_ids (identifiant du titre
sur chaque plateforme), snapshots (relevé quotidien des compteurs
cumulés par titre et par plateforme), submissions (déclarations
d'artistes avec capture d'écran et répartition par pays), chart_types,
chart_runs (une exécution de calcul par classement, pays et période),
chart_entries (position, score, position précédente, flags), users
(rôles admin et éditeur), audit_log.

CYCLE DE DONNÉES
- Les compteurs des plateformes sont cumulatifs. Le système enregistre
  un relevé par jour et calcule la variation sur la période (compteur de
  fin moins compteur de début).
- Un script quotidien collecte les relevés. Un script hebdomadaire
  (lundi) calcule le classement de la semaine précédente (lundi à
  dimanche). Les classements mensuels et annuels sont cumulés à partir
  des relevés.
- Chaque calcul est stocké avec la version de la formule utilisée, pour
  pouvoir l'expliquer et le rejouer.

FORMULE DE SCORE (configurable, fichier de config et admin)
score_titre = somme sur les sources de (variation x poids_source).
Poids initiaux, à valider après quatre semaines de vraies données :
streams audio 1.0, vues YouTube officielles 0.5, déclarations validées
1.0 seulement si recoupées par une donnée publique. Les poids peuvent
varier par pays. Règle de diversité : pour entrer dans le Top 5 d'un
pays, un titre doit avoir des données sur au moins deux sources, sinon
il est plafonné à la sixième place.

ANTI-FRAUDE
- Variation hebdomadaire supérieure à 5 fois la médiane des quatre
  dernières semaines : marqué "à vérifier", non publié tant qu'un admin
  n'a pas validé ou exclu.
- Déclaration d'artiste écartée de plus de 30 % des données publiques :
  "à vérifier".
- Ratio anormal entre vues et mentions "j'aime" sur YouTube : flag.
- Aucune position ne peut être modifiée à la main. Une exclusion
  s'écrit dans audit_log avec l'utilisateur et la raison.

INTÉGRATIONS API (chacune isolée dans une classe avec la même
interface : fetchTrackStats(trackId) et searchTrack(query))
1. YouTube Data API v3 : videos.list, champ statistics. Clé dans .env.
   Gérer le quota journalier avec un compteur et une file d'attente
   (appels groupés jusqu'à 50 identifiants).
2. Spotify Web API : métadonnées uniquement (identifiants, pochettes,
   noms d'artistes, indice de popularité). Pas de streams par titre :
   ne pas les utiliser dans le score.
3. Audiomack : vérifier si l'accès API est ouvert au projet, sinon
   saisie manuelle ou déclaration d'artiste.
4. Boomplay : pas d'API publique connue. Saisie manuelle et déclarations
   d'artistes, en attendant un partenariat.
5. Module de déclaration : formulaire public pour artistes et labels
   (capture d'écran de Spotify for Artists, Audiomack, Boomplay, période
   concernée, répartition par pays), file de validation dans l'admin.
Lire et respecter les conditions d'utilisation actuelles de chaque
plateforme avant d'automatiser, et documenter dans le code ce qui est
autorisé.

ADMIN
Connexion sécurisée (mot de passe fort, limitation des tentatives, 2FA
si possible). Écrans : validation des relevés et déclarations, gestion
des flags, poids de la formule, publication d'un classement (brouillon
puis publié), gestion des pays, artistes et titres, journal d'audit.

SÉCURITÉ ET QUALITÉ
Requêtes préparées partout, protection CSRF, échappement des sorties,
en-têtes de sécurité, sauvegarde de la base, journalisation des erreurs
de cron. Tests automatisés sur le calcul du classement (variations,
égalités, flags, règle de diversité).

LIVRABLES
Code source structuré, README de démarrage local, schema.sql,
seed.sql, tests, et la documentation de déploiement O2switch.
```

## 8. Prompt : logo

À utiliser dans un générateur d'images (Ideogram, Midjourney ou autre). Générer plusieurs variantes, puis faire redessiner la meilleure en vectoriel. À lancer seulement après les vérifications de marque de la section 5.

```text
Logo vectoriel plat pour "Cauri Charts", un média de classements
musicaux d'Afrique de l'Ouest. Le nom se lit "Cauri Charts".

Concept : un monogramme "C" en serif à fort contraste (style éditorial,
comme un magazine), dont la forme évoque de façon abstraite un
coquillage cauri vu de profil : ovale allongé avec une fente centrale.
La fente peut être suggérée par une fine ligne verticale ou par trois
petites barres de hauteurs croissantes (un classement qui monte).

Style : minimaliste, géométrique, formes nettes, aucun dégradé, aucune
ombre, aucun effet 3D. Traits épais, lisible réduit à 32 pixels
(favicon) et en noir et blanc.

Couleurs : violet #8B52FF et noir #111111 sur fond transparent. Le noir
pour la lettre, le violet en aplat de fond ou pour un seul élément.

Typographie du mot "Cauri Charts" : serif contrasté, espacement légèrement
large, "Cauri" en graisse forte et "Charts" en graisse normale.

Compositions : (1) monogramme seul, carré, pour icône et favicon ;
(2) logo horizontal, monogramme à gauche et texte à droite ;
(3) version tout noir sur fond blanc ; (4) version tout blanc sur fond
noir ; (5) monogramme dans un cercle violet pour photo de profil.

À éviter : le mot "Billboard", un cadre rectangulaire rappelant le logo
Billboard, une note de musique clichée, un globe, une carte d'Afrique
cliché, du clipart, un texte illisible ou mal orthographié, un fond
décoré, une lettre superposée à une autre qui la rend illisible.
```

**Conseils.** Les générateurs d'images écrivent souvent mal le texte : générer d'abord le monogramme seul, puis ajouter "Cauri Charts" avec une vraie police dans un éditeur (Figma, Canva, Illustrator). Vérifier que le logo ne ressemble pas à une marque existante avant de le déposer.

## 9. Ordre de mise en place

1. **Faire les vérifications de marque et de comptes** (section 5).
2. **Commencer le site en local** (section 6) avec le prompt de la section 7, sur données d'exemple.
3. **Acheter cauricharts.com** dès que la vérification de marque est passée (et cauricharts.africa, cauri.africa si le budget le permet).
4. **Faire générer le nouveau logo** (section 8), puis mettre à jour la maquette avec lui.
5. **Ouvrir l'hébergement O2switch**, activer le SSL, créer la base de données.
6. **Créer les accès API** : clé YouTube Data API v3 (Google Cloud Console), compte développeur Spotify. Demander l'accès Audiomack. Ne jamais publier ces clés.
7. **Publier la méthodologie** avant le premier classement.
8. **Lancer le premier classement** du Togo, puis les quatre autres pays quand la collecte est stable.
9. **Tenir quatre semaines de régularité** et ajuster les poids de la formule avec les vraies données.
10. **Ouvrir Meta** : compte professionnel et demande de certification (conditions à vérifier selon le pays et le statut), puis une campagne test de 100 euros ciblée Togo, Bénin, Ghana, Côte d'Ivoire, Sénégal et diaspora en France, après la publication du premier classement.
11. **Chercher les partenariats** (plateformes, distributeurs, radios), puis contacter Billboard Africa avec des chiffres réels.
12. **Structurer Novaluz Group** et préparer des awards, avec un jury indépendant.

## 10. Points ouverts

- Le nom "Cauri" passe-t-il les vérifications de marque (OMPI, EUIPO, OAPI) ?
- Les comptes @cauricharts sont-ils libres sur les quatre réseaux ?
- Quelles plateformes ont réellement de l'audience dans chacun des cinq pays ?
- Audiomack accepte-t-il un accès API pour ce projet ?
- Un remix compte-t-il avec l'original ou séparément ? (voir METHODOLOGIE.md)
- Quand fixer le statut juridique de Cauri Charts (association, SARL, filiale) et de Novaluz Group ?
- Qui compose le comité de validation indépendant de la méthodologie ?
- Les noms des classements (Prime, Buzz, Fresh, Icon, Legend, Vintage) sont-ils confirmés ?
