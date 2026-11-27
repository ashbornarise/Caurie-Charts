# Veille technologique : refonte du Cauri Studio (éditeur façon CapCut + collecte de médias)

*Séna, veilleuse technologique de Cauri Charts, 27/11/2026. Recherche faite sur le web le jour même. Les prix et les
règles changent souvent : chaque ligne a sa source, à revérifier avant de signer ou de payer.*

**Point de départ (lecture du code)** : le Studio actuel est déjà riche, mais tout se fait « par formulaire » puis rendu
sur un serveur. `studio_edit.py` met des photos et vidéos bout à bout dans l'ordre choisi (9:16, 4:5, 1:1, 90 s max, fondu
fixe de 0,4 s). Les fichiers arrivent en morceaux de 3,5 Mo à cause de la limite des requêtes Vercel.
`studio_habillage.py` et `studio_sequences.py` dessinent les débuts et les fins image par image avec PIL, puis les
envoient à FFmpeg. `studio_paroles.py` passe par LRCLIB, Gemini et Groq, avec iZotope sur le PC. `studio_raconte.py`
utilise edge-tts, Remotion en local sur le PC et Gemini. `studio_photos.py` lance gallery-dl sur le serveur, avec og:image
en repli. `outils/relais_telephone.py` ouvre les profils Instagram avec Chromium sans interface sous Termux, toutes les
5 minutes. La publication passe par Buffer, Meta en direct et TikTok en direct. Le manifeste de l'appli déclare déjà un
`share_target` en GET (liens seulement) : voir `django/core/studio.py`, ligne 219.

Ce qui manque pour faire « CapCut » : **une vraie timeline à l'écran** (pistes, calques, rognage au doigt, aperçu
instantané). Aujourd'hui, on choisit sur un formulaire et on découvre le résultat après le rendu.

---

## 1. CE QUI EXISTE

### 1.1 Éditeurs vidéo web open source (timeline, calques)

| Outil | Licence (usage commercial ?) | Popularité / état | Ce qu'il fait | Limites | Effort pour l'intégrer |
|---|---|---|---|---|---|
| [OpenCut](https://github.com/OpenCut-app/OpenCut) | MIT (oui) | ~99,5 k étoiles. **En réécriture complète** (cœur en Rust). La version « classique » tourne sur opencut.app ([opencut-classic](https://github.com/opencut-app/opencut-classic)) | L'« alternative à CapCut » la plus connue | Pas prêt. Contributions extérieures fermées pendant la réécriture. Version mobile seulement prévue | Fort, et la cible bouge : **à surveiller, pas à adopter** |
| [OpenReel Video](https://github.com/Augani/openreel-video) | MIT (« usage personnel et commercial ») | ~6,6 k étoiles, **bêta** | Timeline multipiste (vidéo, son, image, texte), sous-titres karaoké mot à mot, import SRT, tout dans le navigateur (WebCodecs, WebGPU) | Pensé pour ordinateur : 8 Go de RAM recommandés, mobile « prévu ». Se présente comme « une expérience de développement assisté par IA » | Moyen : bonne source d'idées et de code d'interface, risqué comme socle |
| [OpenVideo Editor (designcombo/react-video-editor)](https://github.com/designcombo/react-video-editor) | **Double licence** : gratuit jusqu'à 3 salariés, licence entreprise au-delà | ~1,8 k étoiles | Timeline multipiste, découpe, rognage, aimantation, transitions par shaders, export MP4 **dans le navigateur** (WebCodecs + PixiJS) | Demande des services tiers (R2 ou S3, Deepgram, Pexels) | Moyen. React, alors que le Studio est en Django et HTML |
| [Twick](https://github.com/ncounterspecialist/twick) | « Sustainable Use License » : usage commercial **dans son application** permis, revente comme SDK interdite | ~550 étoiles, v0.15 | Kit de composants : timeline React, canevas Fabric.js, sous-titres IA, export navigateur (Chrome et Edge seulement) **ou serveur** (Puppeteer + FFmpeg) | Jeune (avant la 1.0) | Moyen. C'est un kit pour construire son éditeur, proche de notre besoin |
| [Remotion Editor Starter](https://www.remotion.dev/docs/editor-starter) | Modèle payant, **600 $ une fois** ([comparatif](https://www.remotion.dev/docs/editor-starter/vs-studio)), plus la licence Remotion | Officiel Remotion | Éditeur complet prêt à adapter : timeline, calques, sous-titres Whisper ([captioning](https://www.remotion.dev/docs/editor-starter/captioning)) | Payant. Sous-titres par l'API OpenAI par défaut (25 Mo maximum) | **Faible à moyen**, car le Studio utilise déjà Remotion pour « Cauri raconte » |
| [IMG.LY CE.SDK](https://img.ly/products/video-for-web/) | Commercial, **prix sur devis** ([pricing](https://www.img.ly/pricing)) | Éditeur professionnel web et mobile | Éditeur « clé en main » façon CapCut | Prix inconnu, dépendance à un fournisseur | Faible techniquement, coût probablement élevé |

Autres projets repérés mais non vérifiés en détail : [Omniclip](https://github.com/omni-media/omniclip) (MIT),
[FreeCut](https://github.com/fengmk2/freecut) (MIT, Chromium seulement),
[Timeline Studio](https://github.com/MartinDelophy/ai-video-editor) (MIT).

### 1.2 Moteurs de rendu : Remotion et ses alternatives

- **Remotion** ([licence](https://www.remotion.dev/docs/license/faq)) : **gratuit pour les particuliers et les équipes
  de 3 personnes au plus**, y compris pour un usage commercial. Au-delà, il faut une licence entreprise :
  « Creators » à 25 $ par siège et par mois, ou « Automators » à 0,01 $ par rendu avec un minimum de 100 $ par mois.
  **Important : un éditeur construit avec `<Player>`, ou un outil qui fabrique des vidéos automatiquement, relève de
  « Automators »** (même FAQ). Les aperçus dans le Player ne comptent pas comme des rendus.
  → **À vérifier : combien de personnes compte Cauri Charts ?** À 3 ou moins, on ne paie rien.
- **Rendu Remotion dans le navigateur** : [`renderMediaOnWeb()`](https://www.remotion.dev/docs/web-renderer/render-media-on-web)
  existe, mais la doc le marque « très expérimental » ([miroir de la doc](https://remotion.nodejs.cn/docs/web-renderer/render-media-on-web)).
  Pas encore pour la production sur téléphone.
- **Revideo** ([GitHub](https://github.com/redotvideo/revideo)) : MIT, ~4,2 k étoiles, dérivé de Motion Canvas. Rendu
  sans interface (aussi sur Cloud Run), rendu parallèle, composant `<Player/>`, son. Je n'ai pas pu confirmer qu'il est
  encore activement maintenu en 2026.
- **Motion Canvas** : vraiment open source, mais seulement du canevas et pas de service de rendu sans interface
  ([comparatif Remotion, partial](https://www.remotion.dev/docs/compare/motion-canvas)).
- **Mediabunny** ([GitHub](https://github.com/Vanilagy/mediabunny), [site](https://mediabunny.dev/)) : licence MPL-2.0,
  usage commercial permis, y compris dans un logiciel fermé. Bibliothèque TypeScript qui lit, écrit et convertit les
  médias avec l'accélération matérielle (WebCodecs). C'est la brique qui manque pour **rogner et exporter sur le
  téléphone sans serveur**. Remotion l'utilise ([blog Remotion](https://www.remotion.dev/blog/mediabunny)).
- **FFmpeg.wasm** : plus lent que FFmpeg natif, même en multithread ([doc perf](https://ffmpegwasm.netlify.app/docs/performance)).
  Le multithread demande une page « cross-origin isolated ». **Sur téléphone, le système peut fermer l'onglet sans
  prévenir** quand la mémoire manque ([LinuxFr](https://linuxfr.org/users/videocompressio/journaux/ffmpeg-dans-le-navigateur-webassembly-memoire-et-limites-pratiques.epub)).
  → Bon pour des vignettes ou de petites découpes. **Pas pour le rendu final sur téléphone.** On garde FFmpeg natif sur
  GitHub Actions.
- **Envoi des gros fichiers** : avec les [envois directs de Vercel Blob](https://vercel.com/docs/vercel-blob/client-upload),
  le fichier part du navigateur droit vers le stockage, au-delà de 4,5 Mo, avec un jeton délivré par le serveur après
  vérification de l'utilisateur. Cela remplacerait les morceaux de 3,5 Mo recollés à la main.

### 1.3 Sous-titres automatiques (Whisper et variantes)

| Outil | Licence / prix | Ce qu'il fait | Limites |
|---|---|---|---|
| [Groq whisper-large-v3-turbo](https://console.groq.com/docs/model/whisper-large-v3-turbo) | **0,04 $ par heure** d'audio, minimum facturé 10 s par requête ([guide ASR Groq](https://groq.com/GroqDocs/Groq%20ASR%20Model%20Guide.pdf)) | Horodatage **mot par mot** (`timestamp_granularities`, [doc](https://console.groq.com/docs/speech-to-text)). Déjà utilisé par `studio_paroles.py` | Fichier de 100 Mo au plus. Le chant sur musique reste difficile : il faut d'abord isoler la voix |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT, gratuit | Mots horodatés (`word_timestamps=True`). Rapide sur processeur (int8) : tourne sur GitHub Actions | Calcul à notre charge |
| [WhisperX](https://github.com/m-bain/whisperX) | Licence à vérifier sur le dépôt (BSD-2 selon un miroir) | Calage précis mot par mot (alignement wav2vec2) plus détection de voix ([article](https://arxiv.org/abs/2303.00747)) | Plus lourd, carte graphique préférable |
| [@remotion/whisper-webgpu](https://www.remotion.dev/docs/whisper-webgpu) | Écosystème Remotion | Transcription **dans le navigateur** (WebGPU, Transformers.js), mots horodatés | Le téléphone doit avoir WebGPU. Petits modèles seulement |

**Langues locales** : je n'ai **rien trouvé sur le nouchi ni sur le français ivoirien**. Pour le yoruba, le pidgin
nigérian et l'éwé, les études de 2026 montrent que Whisper « de base » reste faible et qu'il faut des modèles affinés
([Nufo, éwé](https://arxiv.org/pdf/2610.17278), [pidgin](https://proceedings.mlr.press/v302/rufai26a.html),
[WAXAL-NET, 19 langues](https://huggingface.co/papers/2606.02375.md)). → La relecture humaine reste obligatoire.
C'est déjà le cas avec l'étape « à valider ».

### 1.4 Détourage (fond retiré)

- [rembg](https://github.com/danielgatis/rembg) : code MIT. Chaque modèle a sa propre licence.
- [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) : code MIT. Le dépôt ne précise pas à part la licence des poids
  du modèle, donc à vérifier.
- ⚠️ **BRIA RMBG-2.0** : poids en **CC BY-NC 4.0, usage non commercial seulement** ([fiche](https://huggingface.co/briaai/rmbg-2.0)).
  Le modèle `bria-rmbg` de rembg en hérite. **À ne pas utiliser** sans contrat avec BRIA.
- ⚠️ **@imgly/background-removal** (dans le navigateur) : **AGPL** ([npm](https://npmjs.com/package/@imgly/background-removal)).
  Si on le modifie et qu'on le sert en ligne, il faut publier les sources modifiées. Licence commerciale sur demande.

### 1.5 Voix (synthèse vocale)

- **edge-tts** (voix Henri, déjà utilisée) : gratuit, mais c'est le service de Microsoft, propriétaire
  ([comparatif, source secondaire](https://bestllmfor.com/guides/kokoro-tts-guide/)). Je n'ai pas trouvé de conditions
  d'utilisation qui l'autorisent clairement pour un usage commercial. ⚠️ **C'est un risque** : le service peut être coupé
  ou interdit du jour au lendemain.
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) : poids sous **Apache 2.0** (commercial permis). Il existe des
  voix françaises, mais avec moins de 11 h de données d'entraînement en français. La phonétisation française passe par
  espeak-ng, sous licence GPLv3 ([dépôt](https://github.com/hexgrad/kokoro)).
- **Piper** : le développement est passé à [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl), sous GPL-3.0.
  La licence de chaque voix est à vérifier.

### 1.6 Publication sur plusieurs réseaux (API officielles)

| Réseau | Ce que dit la doc officielle | Points d'attention |
|---|---|---|
| **Instagram** ([Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing)) | Photo (JPEG seulement), vidéo, **Reels**, **carrousel jusqu'à 20 éléments**, **Stories**. Compte professionnel relié à une Page | **100 posts par 24 h glissantes** (une autre section de la même page dit 50). Le média doit être sur une adresse publique, ou envoyé par `rupload.facebook.com` |
| **Facebook Reels** ([Reels Publishing](https://developers.facebook.com/docs/video-api/guides/reels-publishing)) | Pages seulement. 3 à 90 s, 9:16, 1080×1920 recommandé, 24 à 60 images/s, H.264, AAC 48 kHz | **30 posts par 24 h**. Les liens fbcdn sont refusés |
| **TikTok** ([Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started)) | Publication directe de vidéos et maintenant de **photos** (via `PULL_FROM_URL` sur un domaine vérifié) | ⚠️ **Tant que l'appli n'a pas passé l'audit TikTok, tout ce qu'elle publie reste en privé** |
| **YouTube** ([videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)) | Par défaut, **100 envois par jour** et par projet ([quotas](https://developers.google.com/youtube/v3/determine_quota_cost)) | Les sources se contredisent : la page officielle lue aujourd'hui dit que les envois d'un projet non vérifié **ne sont plus** limités au privé, d'autres sources disent l'inverse. → **Faire un envoi d'essai** ([audits](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits)) |
| **Buffer** ([limites](https://developers.buffer.com/guides/api-limits.html)) | API ouverte à toutes les formules. Limites par 15 min, 24 h et 30 jours, **partagées entre toutes les clés** | Créer une deuxième clé ne donne pas plus de requêtes : c'est l'origine des 429 du 26/11 |
| **Alternatives** | [Postiz](https://github.com/gitroomhq/postiz-app) : AGPL-3.0, auto-hébergeable, 20 réseaux ou plus, mais il faut obtenir soi-même les accès de chaque réseau. [Upload-Post](https://www.upload-post.com/pricing.md) et [Ayrshare](https://www.ayrshare.com/compare/upload-post-api-alternative.md) : API unifiées payantes (comparatifs écrits par les vendeurs) | Aucune ne lève l'audit TikTok à notre place : elles passent par **leur** appli auditée |

---

## 2. RÉCUPÉRER DES MÉDIAS DEPUIS UN TÉLÉPHONE ANDROID / TERMUX

### 2.1 Ce que disent les conditions des réseaux (l'essentiel)

- **TikTok** ([conditions](https://www.tiktok.com/legal/page/row/terms-of-service/en)) : interdit d'« utiliser des
  scripts automatisés pour collecter des informations » et de « contourner les mesures » de protection. Le contenu ne
  peut pas être téléchargé ni redistribué, et il est accessible « pour un usage personnel, non commercial ».
  **Aucun droit n'est accordé sur les enregistrements sonores.**
- **YouTube** ([conditions](https://www.youtube.com/static?template=terms)) : interdit de télécharger ou de reproduire
  sans permission explicite, et d'accéder au service « par des procédés automatisés (robots, scrapers) ».
- **X** : « le scraping sous quelque forme que ce soit, sans notre consentement écrit, est expressément interdit »
  ([citation dans X c. Bright Data](https://s3.documentcloud.org/documents/24658681/x-v-bright-data.pdf)). Les conditions
  prévoient **15 000 $ de dommages forfaitaires par million de posts** consultés en 24 h
  ([Knight Institute](https://knightcolumbia.org/content/knight-institute-says-xs-new-terms-of-service-will-stifle-independent-research)).
  La page de X ne s'est pas ouverte pour moi (erreur 402) : le texte actuel est à revérifier.
- **Instagram et Facebook** : les conditions interdisent de collecter des données de façon automatisée sans permission
  expresse ([copie déposée au tribunal](https://www.lb7.uscourts.gov/documents/19-1861URL1Termsofuse.pdf)). La page
  officielle ne s'est pas ouverte dans mon outil, donc la formulation actuelle est à vérifier sur instagram.com/legal.
- **Droit d'auteur** : même avec un outil autorisé, **la photo appartient à son auteur** (photographe, label). Le Studio
  crédite déjà le compte d'origine, ce qui est bien, mais **créditer ne vaut pas autorisation**.

### 2.2 Ce qui marche sous Termux, et ce qui est risqué

| Outil | Marche sous Termux ? | Réseaux | Risque |
|---|---|---|---|
| **yt-dlp** ([installation](https://github.com/yt-dlp/yt-dlp/wiki/Installation)) | Oui : `pkg install python ffmpeg`, puis `pip install -U "yt-dlp[default]"` | YouTube, TikTok, Facebook, X, Instagram… | ⚠️ Pour YouTube, il faut un moteur JavaScript (Deno recommandé) depuis la version 2025.11.12, et parfois des « PO tokens » ([page de manuel](https://man.archlinux.org/man/extra/yt-dlp/yt-dlp.1.en)). **Contraire aux conditions de YouTube et TikTok** dès qu'on l'automatise |
| **gallery-dl** ([dépôt](https://github.com/mikf/gallery-dl)) | Par pip, probablement (pas de doc spécifique à Termux) | Instagram, X… (déjà utilisé par `studio_photos.py`) | Licence GPLv3. Pour Instagram, il demande souvent des **cookies de connexion** ([README](https://raw.githubusercontent.com/mikf/gallery-dl/master/README.rst)). ⚠️ Utiliser les cookies de son propre compte expose **ce compte** à un blocage |
| **instaloader** ([dépannage officiel](https://instaloader.github.io/troubleshooting.html)) | Oui (Python) | Instagram | ⚠️ **Le plus risqué** : erreurs 401 répétées (« Please wait a few minutes ») et ouvertes chez eux. Bellingcat prévient que le compte utilisé **peut être perdu** ([toolkit](https://bellingcat.gitbook.io/toolkit/more/all-tools/instaloader)). Des utilisateurs signalent des appareils « restreints pour de bon » ([forum](https://forum.freecodecamp.org/t/i-am-unable-to-access-posts-from-public-accounts-on-instagram/752099)) |
| **Chromium sans interface** (notre relais) | Oui, par `x11-repo` (aucune doc récente trouvée). **Playwright ne s'installe pas** sous Android ([issue](https://github.com/microsoft/playwright/issues/6105)) | Instagram (profils) | ⚠️ C'est de la collecte automatisée, toutes les 5 minutes, avec une fausse signature de navigateur Windows : **contraire aux conditions d'Instagram**. Elle passe par l'adresse Internet du domicile, qui peut être restreinte |
| **termux-url-opener** ([exemple](https://www.github.com/kairusds/termux-url-opener)) | Oui : « Partager → Termux » depuis n'importe quelle appli lance `~/bin/termux-url-opener` avec le lien | Tous | Risque faible côté technique, car c'est un humain qui choisit un post à la fois. Les conditions sur le téléchargement s'appliquent toujours |
| **Termux lui-même** | Installer la version F-Droid ou GitHub : la version Play Store vient d'une autre base de code ([annonce](https://github.com/termux/termux-app/discussions/4000)) | — | Android 12 et plus coupe les processus en arrière-plan ([phantom process killer](https://github.com/agnostic-apollo/Android-Docs/blob/master/en/docs/apps/processes/phantom-cached-and-empty-processes.md)). Sur Android 15, des boucles longues sont tuées même avec un verrou de réveil ([issue 5150](https://github.com/termux/termux-app/issues/5150)) : notre boucle de 5 minutes est fragile |

### 2.3 Les API officielles pour récupérer des médias

- **Instagram Business Discovery** ([doc](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery)) :
  avec **notre** compte pro, on lit les posts publics d'**autres comptes pros** (artistes en compte Créateur ou
  Professionnel) : légendes, chiffres et souvent `media_url`. Exceptions : pas de `media_url` pour les vidéos avec de la
  musique sous droits, ni pour les Reels dont l'auteur a coupé le téléchargement. Rien sur les comptes avec limite d'âge.
  **C'est la voie autorisée pour Instagram.** Elle remplace le Chromium du téléphone pour les artistes en compte pro.
- **oEmbed Meta** : depuis le 3/11/2025, il **ne renvoie plus `thumbnail_url` ni l'auteur**
  ([Meta](https://developers.facebook.com/blog/post/2025/04/08/oembed-updates/)). Inutile pour récupérer des images.
- **Pages Facebook d'autres comptes** : il faut la fonction « Page Public Content Access », soumise à un examen de l'appli
  par Meta ([doc](https://developers.facebook.com/docs/features-reference/page-public-content-access)).
- **TikTok Display API** ([video.list](https://developers.tiktok.com/doc/tiktok-api-v2-video-list)) : seulement les
  vidéos **de l'utilisateur qui a donné son accord** (couverture, titre). Un artiste peut connecter son compte à Cauri.
- **YouTube Data API** : métadonnées et vignettes officielles, **pas de téléchargement des vidéos** (conditions
  ci-dessus).
- **X API** : facturée à l'usage, environ 0,005 $ par post lu ([tarifs](https://docs.x.com/x-api/getting-started/pricing)).
  C'est légal mais payant.

---

## 3. CE QUI POURRAIT ÊTRE AMÉLIORÉ CHEZ NOUS

1. **Une vraie timeline à l'écran** au lieu du formulaire de `studio_edit.py`. Le montage serait décrit en JSON (pistes,
   extraits, textes, transitions), avec un aperçu instantané dans `@remotion/player`. Le même JSON serait rendu par
   Remotion sur GitHub Actions. Un seul format servirait à l'aperçu et au rendu, et les débuts et fins PIL de
   `studio_sequences.py` deviendraient des composants animés en direct.
2. **Envois directs** vers Vercel Blob (ou R2) au lieu des morceaux de 3,5 Mo
   ([doc](https://vercel.com/docs/vercel-blob/client-upload)).
3. **Rognage et prévisualisation sur le téléphone** avec Mediabunny (WebCodecs) : on n'envoie que le passage gardé, donc
   moins de données mobiles.
4. **Le Studio comme cible de partage pour les fichiers** : le manifeste accepte déjà les liens en GET. Passer en
   `POST` multipart avec `files` ([MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/share_target))
   permettrait de partager directement une photo ou une vidéo de la galerie (Chrome Android oui, Safari iOS non).
5. **Collecte Instagram par Business Discovery** au lieu de Chromium sur le téléphone pour les comptes pros. On garde le
   relais seulement en « un lien partagé à la main » (termux-url-opener), et on arrête la boucle de 5 minutes.
6. **Sous-titres mot à mot partout** (pas seulement dans « Paroles ») avec Groq à 0,04 $ par heure : c'est déjà branché.
   Sur GitHub Actions, faster-whisper en secours gratuit.
7. **Voix de secours sous licence claire** (Kokoro, Apache 2.0) si edge-tts tombe.
8. **Publication** : faire respecter dans le code les plafonds officiels (Instagram 100 par 24 h, Facebook Reels 30 par
   24 h, YouTube 100 envois par jour). Lire `/content_publishing_limit` avant de publier. **Lancer l'audit TikTok** pour
   sortir du mode privé.

## 4. CE QUI POURRAIT ÊTRE INVENTÉ (aucun outil ne le fait bien pour nous)

- **Le « kit presse » de l'artiste** : un lien Cauri où l'artiste ou son label **dépose ses photos et vidéos et coche
  l'autorisation d'usage**. Combiné à Business Discovery et à la connexion TikTok de l'artiste, c'est une banque de
  médias **légale, de meilleure qualité, et qui se remplit seule**.
- **Des sous-titres qui connaissent nos langues** : un lexique Cauri (nouchi, pidgin, noms d'artistes, mots en
  yoruba, éwé, fon…) injecté dans la consigne (« prompt ») de Whisper. Chaque correction du fondateur enrichirait le
  lexique.
- **Des gabarits « classement »** liés aux données : glisser un titre du Top dans la timeline insère automatiquement sa
  pochette, sa place, son évolution et les couleurs de son pays. Aucun CapCut ne connaît nos classements.
- **Un « mode pouce »** : un éditeur pensé pour une main et une connexion 3G, avec une suite de cartes (accroche →
  plans → son → fin) plutôt qu'une timeline de bureau, et la timeline complète en option.
- **Un témoin de droits** sur chaque média : source, autorisation (oui, non, inconnue), musique sous droits. La
  publication est bloquée si l'autorisation est « inconnue » sur un post sponsorisé.

---

## 5. RECOMMANDATION : les 5 choses à adopter en premier

1. **`@remotion/player` + un montage décrit en JSON + rendu Remotion sur GitHub Actions** : on connaît déjà Remotion,
   l'aperçu est immédiat, et c'est gratuit si l'équipe compte 3 personnes au plus
   ([licence](https://www.remotion.dev/docs/license/faq)). Les 600 $ de l'[Editor Starter](https://www.remotion.dev/docs/editor-starter)
   valent le coup si l'on veut gagner des semaines sur la timeline. Sinon, on s'inspire d'OpenReel (MIT).
2. **Instagram Business Discovery** pour les photos des artistes en compte pro : c'est la seule voie officielle. Elle
   réduit le risque de blocage du compte et de l'adresse du domicile
   ([doc](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery)).
3. **Partage direct vers le Studio** : `share_target` en POST pour les fichiers, et termux-url-opener pour les liens,
   **à la place de la boucle Chromium automatique**. Un humain choisit chaque média : moins de risque, plus de qualité.
4. **Envois directs vers le stockage + Mediabunny** pour rogner sur le téléphone : fin des morceaux de 3,5 Mo, moins de
   données mobiles ([Vercel Blob](https://vercel.com/docs/vercel-blob/client-upload), [Mediabunny](https://mediabunny.dev/)).
5. **Audit TikTok + plafonds officiels dans le code**, pour publier en public sur TikTok sans dépendre de Buffer
   ([TikTok](https://developers.tiktok.com/doc/content-posting-api-get-started), [Instagram](https://developers.facebook.com/docs/instagram-platform/content-publishing),
   [Facebook Reels](https://developers.facebook.com/docs/video-api/guides/reels-publishing)).

**À éviter ou à signaler** : instaloader (risque de perdre le compte), la collecte automatique de X (dommages
forfaitaires), le modèle BRIA RMBG-2.0 (non commercial), FFmpeg.wasm pour le rendu final sur téléphone (plantages),
@imgly/background-removal sans tenir compte de l'AGPL. Pour yt-dlp et gallery-dl : outils légaux, mais leur usage
automatisé sur YouTube, TikTok, X et Instagram **va contre les conditions de ces réseaux**. On les garde au mieux pour
des contenus dont on a l'autorisation (clips fournis par le label, nos propres posts).

**À vérifier** : la taille de l'équipe (licence Remotion), la règle actuelle de YouTube sur les projets non vérifiés
(envoi d'essai), le texte actuel des conditions d'Instagram et de X (pages non ouvertes par mon outil), la licence des
poids BiRefNet et WhisperX, et les conditions d'edge-tts.
