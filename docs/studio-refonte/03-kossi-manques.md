# Cauri Studio : ce qu'il sait faire, ce qui lui manque

*Kossi, chercheur de manques. 27/11/2026. Lecture seule du code (rien modifié, ni la base ni git).*

But du fondateur : un éditeur complet façon CapCut sur téléphone (ses images, toutes les possibilités, de A à Z), et
la récupération de médias sur Instagram, TikTok, YouTube, Facebook et X grâce à son téléphone Android (Termux).

---

## 1. Inventaire réel

### Ce que le Studio est vraiment
- **Une appli web installable (PWA)** sur une adresse secrète `/studio/<STUDIO_CHEMIN>`, verrouillée par empreinte
  (passkey WebAuthn, nouveau verrou après 5 min d'inactivité). Code : `django/core/studio.py` (1 580 lignes, ~60 routes)
  et `django/templates/studio2.html` (1 700 lignes, JavaScript sans framework). L'ancien écran reste sur `?classique=1`
  (`studio.html`).
- **Le téléphone ne monte rien.** Il remplit des formulaires et envoie des fichiers. Tout le rendu se fait sur un
  serveur avec ffmpeg et PIL : GitHub Actions (`studio.yml`), ou **le PC** quand une plateforme bloque les serveurs.
- **L'aperçu n'est qu'une image fixe** : une image clé avec le texte posé dessus (`apercu_job`, calculé sur Vercel),
  les vignettes des débuts et des fins (`sequences_apercu`). On ne voit la vraie vidéo qu'une fois fabriquée (de 3 à 10 min).
- **Le modèle de données** se limite à une table `studio_jobs` (un lien et un bloc JSON `params` par tâche). Il n'y a ni
  projet, ni timeline, ni médiathèque : un brouillon par utilisateur (`studio_brouillons`, l'état des formulaires,
  200 Ko maximum) et des « outils maison » (`studio_outils`, des recettes de réglages).

### Les outils, un par un

| Outil (écran) | Ce qu'il prend | Ce qu'il produit | Où il tourne | Limites |
|---|---|---|---|---|
| **Vidéo de clip** (`studio_montage.traite`) | 1 lien (yt-dlp), début/fin, extrait, refrain auto ou résumé des temps forts | Vidéo habillée : logo, accroche animée mot à mot, 10 débuts, 10 fins, 3 couvertures, signature sonore ; texte écrit par Gemini, qui regarde 4 images ; formats origine, 9:16, 4:5, 1:1 ; recadrage sur les visages (« plein ») | GitHub Actions ; **le PC** si le lien est YouTube | 90 s au plus ; un seul plan ; texte aux places fixées par l'habillage ; aucun réglage de position, de taille ou de durée du texte |
| **Montage** « façon CapCut » (`studio_edit.traite`) | Jusqu'à 30 éléments (photos de la banque, fichiers du téléphone envoyés par morceaux de 3,5 Mo, liens), 1 chanson (lien, fichier ou son des vidéos, départ au refrain auto) | Vidéo 9:16, 4:5 ou 1:1, **sans texte**, fondu de 0,4 s ou coupe, zoom doux sur les photos, son normalisé à −14 LUFS | GitHub Actions ; **le PC** si un lien est YouTube | Une seule piste, en file ; pas de texte, de calque, de vitesse ni de volume par plan ; pas de recadrage manuel (vidéo coupée au centre) ; une seule transition ; 90 s au plus |
| **Collage** (`studio_edit.collage`) | 2 à 6 photos | 1 image (grille, côte à côte, mosaïque), cases cadrées sur le visage | Vercel, tout de suite | 3 dispositions, aucun texte |
| **Photos / Photo + titre / Annonce** (`studio_photos`) | Lien de post (gallery-dl, puis Playwright, puis og:image), photos du téléphone (4,3 Mo au plus), profil Instagram (par le relais) | Tri des photos, banque de l'artiste (`artist_photos`), carrousel avec la couverture Cauri, détourage et netteté | GitHub Actions ; relais (profils) | Profils : **Instagram seulement, et seulement les posts photo** (les reels sont ignorés) |
| **Mettre en valeur** (`vedette`) | Artiste + photos de la banque + textes tirés de nos données | Visuels selon des modèles ; un modèle se crée depuis une image d'exemple (Gemini) | GitHub Actions | Modèles d'image fixe seulement |
| **Vidéo paroles** (`studio_paroles`) | Son (lien ou fichier), photos, captures d'écran | Vidéo 4:5 où les paroles s'allument au rythme de la voix (LRCLIB, Musixmatch, Spotify, Groq Whisper), copie muette, copie TikTok | **Le PC seulement** (iZotope RX, `av.py`) | Bloqué depuis la perte du PC (voir § 4) |
| **Cauri raconte** (`studio_raconte`, `raconte_v3/v4`) | Un artiste + un angle | Documentaire : récit IA tiré de vrais chiffres, voix Henri (edge-tts), sous-titres mot à mot, clips, cartes de verre | **Le PC seulement** (Remotion `CauriRaconte`, `av.py`) | Bloqué depuis la perte du PC |
| **Idées du jour** (`souvenirs`) | Rien | Propositions toutes prêtes (clips les plus vus il y a 5 ou 10 ans…), qui partent en tâches « clip » | Vercel, puis GitHub ou le PC | Ce sont des liens YouTube : ils partent **au PC** |
| **Live TikTok** (`core/live.py`) | Classement, clips, commentaires | Régie du live (écran piloté) | Vercel | Hors édition |
| **Envoi** (`envoyer`, `photos_publier`, `vedette_publier`) | Légende FR et EN, mode de légende, réseaux cochés, réglages TikTok | Post dans `social_posts`, puis Buffer, Meta en direct (quand Buffer est en 429), API TikTok (brouillon ou privé tant que l'audit n'est pas passé), Telegram | Vercel | **Toujours « dans 2 minutes »** : on ne choisit ni le jour ni l'heure ; aucune statistique des posts dans le Studio |
| **Calendrier** (`calendrier`) | Rien | Liste des posts d'hier à J+7 (programmé, parti, annulé) | Vercel | Lecture seule : on ne déplace rien, on n'annule rien |
| **Notifications** (Web Push) | Rien | Alerte « à valider » ou « prêt » sur le téléphone | Vercel | Fonctionne |

### Le relais téléphone (Termux) aujourd'hui
- `outils/installer_relais.sh` installe Python et Chromium, écrit le jeton (`~/.cauri-relais`, dérivé de `CRON_SECRET`)
  et démarre au boot (Termux:Boot et wake-lock).
- `outils/relais_telephone.py`, toutes les 5 minutes : `GET /api/relais/profils`, ouverture de chaque profil Instagram
  avec Chromium `--dump-dom` (sans défilement), relevé des liens `/p/` (24 au plus), puis `POST`. **C'est tout.**
- `core/views_relais.py` ne connaît que les marqueurs `relais/profils/`. Les **tâches vidéo** en attente
  (`relais/studio/job-N.json`, posées pour YouTube, les paroles, Cauri raconte et les montages avec un lien YouTube)
  ne sont lues que par `manage.py relais_profils`, la tâche Windows de l'ancien PC, qui **n'existe plus**.

### Le partage Android
Le manifeste déclare déjà un `share_target` : « Partager → Cauri Studio » depuis Instagram, TikTok ou YouTube ouvre le
Studio avec le lien prérempli (`studio2.html`, ligne ~707). Ce point de départ est bon.

---

## 2. Comparaison avec un éditeur complet

Légende : **Oui** = existe, **Partiel** = en partie, **Non** = absent.

| Famille | Fonction | État dans le Studio |
|---|---|---|
| Médias | Importer photos et vidéos du téléphone | Partiel (envoi par morceaux pour le montage ; 4 Mo par photo ; aucune médiathèque où les retrouver) |
| | Depuis un lien Instagram, TikTok, YouTube, X, Facebook | Partiel (yt-dlp et gallery-dl sur le serveur ; YouTube bloqué sans le PC ; Facebook souvent refusé ; ni stories ni profils TikTok, X ou YouTube) |
| | Banque d'images des artistes | Oui (`artist_photos`, dossiers, score) |
| | Recherche de médias (clips, photos d'un artiste) | Partiel (Cauri raconte v3 va chercher les clips officiels et Wikimedia, mais aucun écran « chercher un média ») |
| | Détourage | Partiel (photos : rembg u2net ; vidéo : non) |
| | Amélioration | Partiel (photos : Real-ESRGAN, `ameliore.py` ; vidéo : non) |
| Montage | Timeline multi-pistes | Non (une liste en file, une piste) |
| | Découpe | Partiel (début et fin en secondes, tapés à la main ; pas de découpe visuelle, pas de coupe au milieu d'un plan) |
| | Vitesse, ralenti, marche arrière | Non |
| | Calques, incrustation (image dans l'image) | Non |
| | Recadrage auto par réseau | Partiel (cadrage « plein » sur les visages pour le clip ; un seul format par rendu) |
| | Keyframes (mouvement, zoom, opacité) | Non (seulement le zoom doux automatique des photos) |
| | Annuler / refaire | Non |
| Texte et son | Textes animés libres | Non (l'accroche de l'habillage seulement, à sa place fixe) |
| | Sous-titres automatiques de la parole | Partiel (le moteur existe dans Paroles et dans Raconte, mais n'est pas proposé sur un montage ou un clip) |
| | Voix off (enregistrée) | Non |
| | Voix off (synthèse) | Partiel (edge-tts dans Raconte seulement) |
| | Musique | Partiel (un lien ou un fichier, départ au refrain ; pas de bibliothèque) |
| | Bruitages | Non (seulement les « signatures » de l'habillage) |
| | Réduction de bruit | Non (iZotope RX était sur le PC perdu) |
| | Niveau du son | Partiel (loudnorm global ; pas de volume par plan ni d'atténuation de la musique sous la voix) |
| Habillage | Modèles de la marque | Oui pour clip et image (10 débuts, 10 fins, 3 couvertures, modèles vedette) ; Non pour le Montage |
| | Transitions | Partiel (fondu ou coupe) |
| | Effets, filtres | Non |
| | Autocollants, emojis | Non |
| | Logo | Oui (clip) ; Non (montage) |
| Sortie | Aperçu en direct | Non (image fixe seulement) |
| | Brouillons, projets rouvrables | Partiel (formulaires et historique des tâches ; pas de projet modifiable puis refabriqué) |
| | Export par format | Partiel (un format par tâche ; copies TikTok et Telegram automatiques) |
| | Export dans la galerie du téléphone | Partiel (le lecteur `<video>` le permet, rien de prévu) |
| | Publication programmée multi-réseaux | Partiel (multi-réseaux oui ; programmée non : toujours dans 2 min) |
| | Statistiques | Non dans le Studio (`stats_reseaux.py` et `stats_instagram.py` existent ailleurs) |

---

## 3. Manques propres à Cauri Charts

- **Des cartes « classement » dans un montage** : rang, évolution, pays, chiffres réels du chart, posés en calque sur
  une vidéo. Les données existent (`officiel.py`, `top_titres.py`) mais le Montage n'a aucun texte.
- **La fiche artiste, source d'un projet** : partir d'un artiste et voir sa banque, ses clips officiels, ses chiffres,
  ses comptes (Instagram et TikTok sont déjà en base), puis glisser ces éléments dans la timeline.
- **Cauri raconte en mode éditable** : aujourd'hui, on relit le récit, puis on attend le rendu Remotion. Il manque
  l'ouverture du documentaire fini dans la timeline pour changer un plan, une carte ou une musique.
- **Après le live TikTok** : récupérer la rediffusion du live et en tirer des extraits courts.
- **Crédit et droits suivis par média** : la case « droits » et le crédit existent par tâche, pas par média importé.
  Avec un montage de plusieurs sources, il faut connaître la source de chaque plan.
- **Sources sûres** : rester sur la règle du code (aucun miroir, aucune accélération, aucun filigrane retiré pour
  tromper la détection des droits). Les effets « miroir » et « vitesse » d'un éditeur sont à réserver aux médias
  du fondateur.

---

## 4. Ce qui a été perdu avec l'ancien PC

`C:\Users\agbal\Studio-AV` **n'existe plus** (vérifié : dossier absent sur ce PC). Il contenait :
- le **projet Remotion `CauriRaconte`** (chemin écrit en dur dans `studio_raconte.py`, ligne 24, et `raconte_v4.py`,
  ligne 33 ; aussi `facebook_live.py`, ligne 15) ;
- **`av.py`**, le mastering (pedalboard, VST3, FabFilter Pro-L 2, iZotope RX), utilisé par `studio_paroles.py`
  (lignes 26-27, 497) et `studio_raconte.py` (lignes 25-26, 540) ;
- la **tâche Windows `relais_profils`**, qui fabriquait tout ce qui passe en `attente_pc`.

**Conséquence directe, aujourd'hui :** toute tâche qui contient un lien YouTube (clips, idées du jour, Top officiel
avec `officiel.py`, montages avec un lien YouTube), toute vidéo paroles et tout Cauri raconte passe en `attente_pc` et
**n'avance plus jamais**. Je n'ai vu aucun délai d'expiration ni aucun repli. L'appli affiche « En attente du PC
(5 min max) ». La note de mémoire « tout tourne dans le cloud » est donc **fausse pour ces outils**.

---

## 5. Tableau des manques

Effort : S = moins d'une journée, M = 2 à 4 jours, L = 1 à 2 semaines, XL = plus de 2 semaines.

| # | Manque | Pourquoi c'est utile | Utilité | Effort | Où le brancher |
|---|---|---|---|---|---|
| 1 | **Relais téléphone pour les vidéos** : le téléphone prend aussi les tâches `relais/studio/`, télécharge la source (yt-dlp et gallery-dl dans Termux), la renvoie au Blob par morceaux, puis le rendu part sur GitHub | Remet en marche YouTube, les idées du jour et le Top officiel sans PC ; le téléphone a une connexion de particulier | Haute | M | `views_relais.py` (nouvelle route `/api/relais/studio` : GET les tâches, POST les morceaux, comme `montage_morceau`) ; `relais_telephone.py` ; `installer_relais.sh` (`pkg install ffmpeg`, `pip install yt-dlp gallery-dl`) ; `studio_montage.telecharge()` (accepter « source déjà dans le Blob ») ; `studio._lance()` |
| 2 | **Délai et repli pour `attente_pc`** : après 15 min, alerte dans le Studio et proposition « Envoyer au téléphone » ou « Essayer sur GitHub » | Plus aucune tâche bloquée sans le savoir | Haute | S | `studio._lance()`, `historique()`, cron `/cron/nuit` (`views_cron.py`), `studio2.html` (écran projet) |
| 3 | **Récupération de médias sur tous les réseaux par le téléphone** : posts, reels, vidéos TikTok, posts X, vidéos Facebook, Shorts, et profils (Instagram avec reels, TikTok, X, chaîne YouTube) ; défilement de la grille | La demande du fondateur : prendre ses médias partout depuis son téléphone | Haute | L | `relais_telephone.py` (remplacer `--dump-dom` par yt-dlp/gallery-dl et défiler la page) ; `views_relais.py` ; `studio.est_profil()` (élargir au-delà d'Instagram) ; `studio_photos.traite_profil` |
| 4 | **Médiathèque « Mes médias »** : tout ce qui est importé (téléphone, liens, relais) gardé et rangé, avec source, crédit, droits, durée et vignette, réutilisable dans chaque projet | Base de tout éditeur : on ne renvoie pas 3 fois le même fichier de 40 Mo | Haute | M | Nouvelle table `studio_medias` dans `studio.creer_tables()` ; `studio_edit.importe_morceau` ; `studio_photos` ; onglet dans `studio2.html` à côté de `v-banque` |
| 5 | **Projet = timeline JSON** (pistes vidéo, texte, son ; plans avec entrée/sortie, vitesse, position, échelle, opacité, keyframes), enregistré, rouvrable, refabricable, avec annuler/refaire | Passer de « formulaire puis rendu » à un vrai éditeur ; sans ça aucun des points suivants ne tient | Haute | L | Nouvelle table `studio_projets` ; `studio.montage_nouveau()` devient « enregistrer le projet » ; `studio_edit.traite()` lit la timeline |
| 6 | **Moteur de rendu de timeline** sur GitHub Actions : la timeline JSON traduite en graphe ffmpeg (overlay, scale, crop, setpts, xfade, amix, volume), ou Remotion installé dans le dépôt | Rend les calques, textes, vitesses et pistes son ; Remotion dans le dépôt réglerait aussi la perte de `CauriRaconte` | Haute | XL | `studio_edit.py` (remplacer `_assemble`) ou nouveau dossier `remotion/` dans le dépôt + étape `npx remotion render` dans `studio.yml` |
| 7 | **Éditeur sur le téléphone** : timeline tactile (glisser, couper, étirer), aperçu en direct en `<canvas>` (vidéos `<video>` et textes dessinés), sans attendre le serveur | C'est le cœur de « CapCut » : voir ce qu'on fait | Haute | XL | Nouvel écran `v-editeur` dans `studio2.html`, ou un fichier JS à part sous `public/assets/studio/` (la CSP autorise `script-src 'self'`) ; vidéos du Blob déjà permises par `media-src` |
| 8 | **Textes libres et animés** (plusieurs, position, police Montserrat, couleurs de la marque, animations d'entrée/sortie reprises de `studio_habillage` et `studio_sequences`) | Le Montage est aujourd'hui « sans texte » : impossible d'y mettre un titre ou un chiffre | Haute | M | Piste texte de la timeline (n° 5) ; rendu PIL image par image en FFV1 transparent, comme `studio_habillage._encode` |
| 9 | **Sous-titres automatiques de la parole** sur n'importe quelle vidéo (Groq Whisper, mot à mot, style Cauri, corrigeables) | Les vidéos se regardent sans le son ; Facebook et TikTok les mettent en avant | Haute | M | Réutiliser `studio_paroles._groq` et `studio_raconte._sous_titres` ; piste texte de la timeline |
| 10 | **Programmer le jour et l'heure** depuis le Studio, et déplacer ou annuler un post dans le calendrier | Aujourd'hui tout part « dans 2 minutes », ce qui ne permet pas de tenir une ligne éditoriale | Haute | S | `studio._envoyer()` (`due` choisi au lieu de `maintenant + 2 min`) ; `calendrier()` (POST déplacer/annuler) ; fenêtre `demandeReseaux` dans `studio2.html` |
| 11 | **Reconstruire le mastering et Remotion sans le PC** : `av.py` remplacé par les filtres ffmpeg (`afftdn`/`arnndn` contre le bruit, `loudnorm`, `alimiter`) ; projet Remotion `CauriRaconte` remis dans le dépôt et rendu sur GitHub | Vidéo paroles et Cauri raconte redeviennent possibles | Haute | L | `studio_paroles.py` (`AV`, `_isole_voix`) ; `studio_raconte.py` (`REMOTION`, `rendu()`) ; `raconte_v4.py` ; `studio.yml` (Node est déjà installé) ; retirer `paroles\|raconte` du renvoi au PC dans `studio._lance()` |
| 12 | **Export multi-format en une fois** : un projet donne 9:16, 4:5 et 1:1, chaque format recadré sur les visages | Un montage pour TikTok, le fil Instagram et Facebook sans tout refaire | Moyenne | M | `studio_edit.traite()` (boucle sur les formats) ; `couverture2026.cadrer` ; `studio_montage.cadrage_plein` |
| 13 | **Voix off** : enregistrée au téléphone (MediaRecorder) ou synthétisée (edge-tts, voix Henri), avec atténuation automatique de la musique | Narration de ses propres montages, façon Cauri raconte | Moyenne | M | `studio2.html` (micro) ; envoi par `montage_morceau` ; `studio_raconte._tts` ; filtre `sidechaincompress` dans le rendu |
| 14 | **Vitesse et découpe visuelle** : couper un plan en deux, ralenti ou accéléré (sur ses propres médias), poignées d'entrée et de sortie sur une bande d'images | Les gestes de base de tout monteur | Moyenne | M | Timeline (n° 5 et 7) ; rendu `setpts` et `atempo` ; bande d'images extraite par ffmpeg (`images_cles`) |
| 15 | **Calques et incrustation** : image dans l'image, logo, photo détourée de l'artiste sur une vidéo, cadre aux couleurs du pays | Fait les visuels « réaction », « classement » et « nouveau son » | Moyenne | M | Rendu `overlay` ; détourage `rembg` déjà présent (`plans.py`, `visages.py`) |
| 16 | **Cartes « classement » et « chiffre »** insérables (rang, évolution, pays, vues, écoutes) depuis nos données | Propre à Cauri : ce que personne d'autre ne peut faire | Moyenne | M | `studio_sequences` (nouveaux modèles), `officiel.py`, `top_titres.py`, `facts.py` |
| 17 | **Filtres et réglages couleur** (luminosité, contraste, saturation, quelques LUT de la marque) | Harmoniser des sources de qualités différentes | Moyenne | S | Rendu `eq` / `lut3d` ; aperçu CSS `filter` dans le canvas |
| 18 | **Transitions supplémentaires** (glissé, zoom, flash, balayage) choisies par plan | Variété du rythme | Basse | S | `studio_edit._assemble` : `xfade=transition=` en offre plus de 40 |
| 19 | **Bibliothèque de musiques et bruitages** autorisés (signatures Cauri, whoosh, impacts), et la piste « son officiel ajouté dans l'appli » | Évite de chercher un son à chaque montage | Moyenne | S | `studio_montage.SIGNATURES`, `public/assets/studio/` ; mode « muette » déjà prévu à l'envoi |
| 20 | **Statistiques dans le Studio** : vues, likes et partages par post publié, sur la carte du projet | Savoir quels formats marchent, sans quitter l'appli | Moyenne | S | `stats_reseaux.py`, `stats_instagram.py` ; `calendrier()` et la carte projet de `studio2.html` |
| 21 | **État du relais visible** : dernier passage du téléphone, version, batterie, file d'attente ; alerte s'il se tait depuis plus de 30 min | Termux est coupé par Android (économie de batterie) sans prévenir | Moyenne | S | `views_relais.py` (battement de cœur dans le Blob) ; carte dans `v-reglages` ; `installer_relais.sh` (rappel de désactiver l'optimisation de batterie) |
| 22 | **Modèles de la marque pour le Montage** (début, fin, logo, couverture des clips appliqués à un montage) | Les débuts, fins et couvertures existent mais pas pour l'outil Montage | Moyenne | S | Brancher `_habillage` et `_couverture` de `studio_montage` dans `studio_edit.traite` |
| 23 | **Envoi de gros fichiers plus fiable** : reprise après coupure, progression, compression au téléphone avant l'envoi | Les vidéos du téléphone font souvent plus de 100 Mo, sur réseau mobile | Moyenne | M | `studio2.html` (envoi par morceaux) ; `montage_morceau` (vérifier les morceaux reçus) |
| 24 | **Détourage et amélioration vidéo** (fond retiré image par image, agrandissement) | Effet « artiste sur fond de classement » ; anciennes vidéos floues | Basse | L | rembg/ESRGAN image par image sur GitHub Actions (long et lourd ; la limite de 30 min de `studio.yml` est à revoir) |
| 25 | **Extraits du live TikTok** (rediffusion vers les meilleurs moments) | Recycler le live en vidéos courtes | Basse | M | `live.py` + `studio_montage.moments_forts` |
| 26 | **Crédit et droits par média**, cumulés dans la légende du post | Un montage multi-sources doit citer chaque source | Moyenne | S | `studio_medias` (n° 4) ; `studio._envoyer()` (ligne « Source : ») |

---

## 6. Les 10 manques à combler en premier, dans l'ordre

1. **Délai et repli pour `attente_pc`** (n° 2, S). Aujourd'hui des tâches restent bloquées sans le dire. C'est le
   plus rapide à faire et le plus urgent.
2. **Relais téléphone pour les vidéos** (n° 1, M). Le téléphone remplace le PC perdu pour YouTube : clips, idées du
   jour et Top officiel repartent.
3. **Récupération sur tous les réseaux par le téléphone** (n° 3, L). C'est la demande du fondateur, sur la base du n° 2.
4. **Médiathèque « Mes médias »** (n° 4, M). Tout ce que le relais et le téléphone récupèrent y arrive, avec crédit
   et droits (n° 26 compris).
5. **Programmer le jour et l'heure, calendrier modifiable** (n° 10, S). Petit effort, gros gain au quotidien.
6. **Reconstruire mastering et Remotion sans le PC** (n° 11, L). Vidéo paroles et Cauri raconte redeviennent possibles,
   sur GitHub.
7. **Projet = timeline JSON** (n° 5, L). C'est la fondation de l'éditeur.
8. **Moteur de rendu de timeline** (n° 6, XL). Le même effort sert le n° 11 si l'on choisit Remotion dans le dépôt.
9. **Textes animés et sous-titres automatiques** (n° 8 et 9, M + M). Ce que les créateurs utilisent le plus dans
   CapCut ; les briques existent déjà (habillage, Groq).
10. **Éditeur tactile avec aperçu en direct** (n° 7, XL). Il vient en dernier parce qu'il a besoin des n° 5, 6 et 8
    pour avoir quelque chose à montrer et à fabriquer.

Juste après : modèles de la marque dans le Montage (n° 22), export multi-format (n° 12), état du relais (n° 21),
statistiques (n° 20).

### Deux remarques de monteur
- **L'aperçu en direct au téléphone et le rendu final doivent suivre les mêmes règles.** Une seule description
  (la timeline JSON) lue par le canvas du téléphone et par le moteur de GitHub. Sinon, ce qu'on voit n'est pas ce qui
  part.
- **Le téléphone peut télécharger, pas monter.** Termux sait faire tourner ffmpeg, mais un rendu de 60 s en 1080 × 1920
  avec calques y serait lent et vider la batterie. Je garde le partage des rôles : le téléphone va chercher les
  médias, GitHub Actions fabrique.
