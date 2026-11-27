# Cauri Studio 2027 : le plan

27 novembre 2026. Synthèse des rapports de Kossi (manques), Afi (pourquoi), Séna (veille web) et Yao (tests),
rangés dans ce dossier.

## L'idée qui guide tout

> **Je donne l'idée, le Studio fait le reste.**
> Créer sans beaucoup travailler, sans savoir monter.

Le Studio n'est donc pas un CapCut de plus, avec une timeline qu'il faut maîtriser. C'est un **monteur
automatique** : on lui donne un lien, un artiste, une photo ou une idée. Il propose **trois versions finies**,
aux couleurs de Cauri, avec les sous-titres, la musique et le texte. On choisit, on ajuste d'un geste si on veut,
puis ça part.

La timeline existera, mais cachée derrière un bouton « Ajuster ». On ne l'ouvre que si on en a envie.

## Décisions du fondateur (27/11/2026)

1. **Équipe** : le fondateur seul. Remotion reste donc gratuit.
2. **YouTube et Instagram** : on continue comme depuis le début (téléphone ou PC comme relais), en connaissant le
   risque. On reste raisonnable sur les volumes.
3. **TikTok** : publication par Buffer, comme avant, sans audit propre.
4. **Suppressions** : autorisées quand c'est utile.
5. **Recentrage** : le Studio crée automatiquement, mais il devient surtout **le pont des médias**. Il récupère les
   médias sur les réseaux, les range dans des **dossiers** (par artiste ou par projet) que le fondateur crée lui-même,
   et **chaque média se télécharge directement** sur le téléphone (un appui = enregistré dans la galerie ; pour plusieurs,
   « Enregistrer sur le téléphone » via le menu de partage d'Android, **jamais d'archive ZIP**). Tout ce qui est créé ou
   déposé dans le Studio est téléchargeable de la même façon, pour monter dans CapCut, Premiere… Créer soi-même évite le « déjà vu ». **L'éditeur dans la page (timeline, étape 2) est abandonné** :
   l'aperçu animé reste utile pour les créations automatiques.

## Le parcours cible : trois gestes

1. **Donner** : coller un lien, partager depuis Instagram, TikTok ou YouTube, choisir un artiste, ou écrire une phrase
   (« le portrait de Sethlo », « annonce son concert du 12 »).
2. **Choisir** : le Studio montre trois propositions prêtes (aperçu animé dans la page, pas une image fixe).
   Sous chacune, des boutons simples : *autre musique*, *autre photo*, *texte plus court*, *plus long*, *plus calme*,
   *plus énergique*.
3. **Envoyer** : maintenant, ou à une date et une heure choisies dans le calendrier. Instagram, Facebook, TikTok,
   YouTube et Telegram en une fois.

## Qui fait quoi

| Qui | Son rôle | Ce qu'il ne fait plus |
|---|---|---|
| **Toi** | L'idée, le choix entre trois versions, le feu vert | Monter, recadrer, chercher la musique, écrire les sous-titres |
| **Ton téléphone** | Prendre et partager : photos, vidéos, liens envoyés au Studio d'un geste (« Partager → Cauri Studio ») | Pas de boucle automatique qui aspire les réseaux (contraire à leurs conditions, et Android la coupe) |
| **Le Studio (Vercel)** | L'écran : propositions, aperçu animé (Remotion Player), calendrier, médiathèque « Mes médias » | Aucun rendu lourd |
| **GitHub Actions** | La fabrique : rendu final (Remotion + FFmpeg), mixage du son, sous-titres, publication | Plus rien n'attend un PC allumé |
| **Les IA du projet** | DeepSeek écrit les textes et les récits, Gemini regarde les images et choisit les plans, Groq (Whisper) fait les sous-titres, OpenRouter prend le relais en cas de panne | Aucune décision de publication |
| **L'équipe d'agents** | Koffi réalise « Cauri raconte », Awa juge chaque visuel avant envoi, Yao teste chaque changement, Afi challenge chaque nouvelle fonction, Kossi liste les manques, Séna fait la veille | Rien ne part sans ton accord |

## Les étapes

### Étape 0 : débloquer (cette semaine)
Depuis la perte du PC, toutes les tâches « sur le PC » attendent sans fin : liens YouTube, paroles, Cauri raconte,
idées du jour.
- **Délai et alerte** : une tâche bloquée plus de 30 minutes passe en erreur claire, avec une notification, au lieu
  d'attendre en silence.
- **Remettre la fabrique dans le cloud** : recréer le projet Remotion « Cauri raconte » **dans le dépôt** (il n'y était
  jamais, c'est pour ça qu'il est perdu), et remplacer le mixage iZotope/FabFilter (plugins Windows payants) par un
  mastering FFmpeg (−14 LUFS). Cauri raconte et les paroles se fabriquent alors sur GitHub.
- **Les sources YouTube** : c'est le seul cas où un serveur est refusé. Voir la décision n°2.
- **Les bugs bloquants de Yao** (rapport 01) :
  - un post photo publié ou en échec n'apparaît nulle part dans l'Historique ;
  - les fichiers de plus de 4,5 Mo (son des paroles, modèle de « Mettre en valeur ») sont refusés par Vercel. Il faut
    les envoyer en morceaux ;
  - les doubles lancements sont possibles (un montage déjà publié peut repartir). Il faut un verrou côté serveur et
    `concurrency` dans `studio.yml` ;
  - « publier les clips prêts » lancé avec le champ vide publie tout ce qui est prêt ;
  - les tests doivent être protégés contre la base de production.
- **Filet de sécurité** : Yao relance les 272 tests et rejoue ses sondes après chaque changement.

### Étape 1 : créer en trois gestes (2 semaines)
- **« Mes médias »** : une médiathèque. Tout ce que tu partages depuis le téléphone y arrive directement (envoi direct
  vers le stockage, plus de découpage en morceaux de 4 Mo), avec la source et le crédit de chaque média.
- **Écran Créer simplifié** : un seul champ « Qu'est-ce qu'on fait ? » à la place des neuf tuiles d'outils. Le Studio
  devine l'outil (il sait déjà le faire pour les liens).
- **Trois propositions par demande**, chacune passée par Awa avant de t'être montrée.
- **Programmer** le jour et l'heure, et un calendrier où l'on peut déplacer une publication.
- **Sous-titres automatiques** sur toutes les vidéos (Groq Whisper, déjà branché).

### Étape 2 : l'aperçu en direct et « Ajuster » (3 à 4 semaines)
- Chaque création devient un **projet décrit en JSON**, lu à la fois par l'aperçu sur le téléphone et par le rendu
  final : ce qu'on voit est exactement ce qui part.
- **Aperçu animé** dans la page (Remotion Player), et les boutons « autre musique, autre photo, plus court… »
  modifient le projet en direct.
- **« Ajuster »** ouvre une timeline simple : changer l'ordre, couper un plan, changer un texte. Elle est optionnelle.

### Étape 3 : inventer (ensuite)
- **Le Studio propose tout seul** chaque matin : « Sethlo vient de passer N°2, voici trois posts prêts ». Ces
  propositions partent des données des classements, ce qu'aucun outil grand public ne sait faire.
- **Médias officiels des artistes** par l'API Instagram Business Discovery (autorisée) au lieu de lire les pages.
- **« Cauri raconte » en un geste** : choisir un artiste, Koffi écrit, Awa vérifie, la vidéo arrive. Épisode pilote :
  **le portrait de Sethlo**, une fois son profil nettoyé.

### À enlever (moins de choses = plus simple)
L'ancien Studio (`studio.html`, sauf sa connexion par empreinte), les recettes « Créer mon propre outil », les moteurs
Cauri raconte v2 et v3, le workflow `studio-clip.yml` (refusé par YouTube), les dix débuts, dix fins et trois voix
proposés à chaque vidéo (le Studio choisit, tu peux changer).

## Les décisions qui te reviennent

1. **Remotion** : gratuit tant que l'équipe compte 3 personnes au plus. Au-delà, un éditeur fait avec revient à
   100 $ par mois minimum. Combien de personnes compte Cauri Charts ?
2. **Les vidéos YouTube** : les télécharger (depuis le téléphone ou un PC) va contre les conditions de YouTube, comme
   la boucle Instagram actuelle va contre celles d'Instagram. Trois options :
   - (a) on continue en connaissant le risque ;
   - (b) on n'utilise que les fichiers envoyés par les artistes et les labels, et les médias partagés à la main ;
   - (c) un mélange, avec seulement des extraits courts et le crédit.
   Recommandation : **(b) pour tout ce qui est automatique, (c) au cas par cas.**
3. **TikTok** : tant que l'appli n'a pas passé l'audit de TikTok, ce qu'on publie reste privé. On lance l'audit ?
4. **Ce qu'on supprime** : d'accord pour retirer la liste « À enlever » ci-dessus ?

## Ce que ça change pour le guide Termux
Le guide (Téléchargements, *Guide-Termux-Cauri-Studio.pdf*) reste valable pour installer Termux et partager un lien
à la main. Mais, d'après la veille de Séna, son chapitre 8 (« relais pour tous les réseaux ») et la boucle Instagram
automatique sont à revoir selon ta décision n°2. Une version 2 du guide suivra.
