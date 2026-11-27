# 01 — État des lieux du Cauri Studio (Yao, testeur) — 27/11/2026

Base de la refonte « éditeur complet façon CapCut ». Ce que j'ai fait : la suite de tests complète, la lecture
des parcours dans `studio.py`, `studio2.html` (interface v3), les services `studio_*.py`, `vedette.py`, le relais du PC
et les tâches GitHub. J'ai aussi lancé 14 sondes : des appels directs aux vues, avec la base, le Blob et le réseau
simulés. **Rien n'a été écrit dans la vraie base Neon, rien n'a été publié, rien n'a été poussé.**

Ce que je n'ai pas pu faire : rejouer les parcours sur un vrai téléphone. Il faudrait la vraie base et de vrais comptes,
c'est donc interdit ici. Les bugs d'interface viennent de la lecture du code. Ceux marqués « prouvé » ont été rejoués
par une sonde.

---

## 1. Les tests automatiques

Commande lancée, sans aucun accès à la vraie base :

```
cd django
set SECRETS_FILE=            (vide : le fichier de secrets n'est pas chargé)
set PGCONNECT_TIMEOUT=2
set DATABASE_URL=postgresql://nobody@127.0.0.1:1/aucune_base
..\.venv\Scripts\python -m pytest tests -q
```

**Résultat : 272 réussis, 46 ignorés, 0 échec (1 min 53 s).**

- Les 46 ignorés sont ceux qui exigent une base PostgreSQL : `test_pages_publiques` (30), `test_guet` (10),
  `test_redaction` (4) et `test_newsletter` (2). C'est voulu par `tests/conftest.py`.
- Les tests propres au Studio réussissent tous : `test_studio.py`, `test_studio_annulation.py` et `test_studio_raconte.py`.
  Ils ne couvrent que la porte d'entrée (adresse secrète, 401, droits, création de la tâche), l'annulation et le texte
  de « Cauri raconte ». **Rien ne teste la publication, le montage, le collage, les photos, les paroles, la mise en
  valeur, la page `studio2.html` ni le relais du PC.**

### Deux pièges sur le PC neuf (à lire avant de relancer les tests)

- **BLOQUANT (sécurité) — lancer les tests comme le dit la fiche de Yao touche la base de PRODUCTION.**
  - Le fichier `.env` à la racine contient `SECRETS_FILE=…`, et `cauri/settings.py` (lignes 13 à 15) charge ce fichier,
    qui contient le `DATABASE_URL` de Neon.
  - La commande `cd django && ..\.venv\Scripts\python -m pytest tests -q`, lancée telle quelle, se connecte donc à la
    vraie base. Dès qu'elle répond, `conftest.py` active les tests « base requise ».
  - Or `tests/test_redaction.py` (lignes 42 et 50) fait des INSERT et `tests/test_newsletter.py` (ligne 22) fait un
    DELETE. Ces écritures partiraient en production.
  - À faire : que `conftest.py` refuse de tourner si `DATABASE_URL` pointe vers `neon.tech`, et corriger la commande
    dans `.claude/agents/testeur-studio.md`.
- **GÊNANT — sans base joignable, la suite dépasse 15 minutes.** Chaque connexion à une base absente attend environ
  2 minutes (j'ai mesuré 2 min 08 s). Avec `PGCONNECT_TIMEOUT=2`, toute la suite tourne en moins de 2 minutes. Ma
  première tentative, sans ce réglage, a été coupée à 45 % au bout de 15 minutes.

---

## 2. Les problèmes trouvés

Classement : **BLOQUANT** (le parcours ne marche pas), **GÊNANT** (il marche mal ou perd des choses), **DÉTAIL**.

### BLOQUANTS

**B1. Sur le PC neuf, tout ce qui passe « par le PC » reste bloqué « Sur le PC » pour toujours**
- Parcours touchés :
  - une vidéo de clip depuis un lien YouTube ;
  - une idée du jour (les clips sont sur YouTube) ;
  - une vidéo paroles et un « Cauri raconte » (toujours sur le PC) ;
  - un montage qui contient un lien YouTube ;
  - le tri d'un profil Instagram ;
  - et hors Studio, les clips du podium du classement officiel (`officiel.py`, ligne 119).
- Pour reproduire : coller un lien YouTube → Vidéo de clip → Fabriquer. Le projet affiche « En attente du PC (il passe
  toutes les 5 minutes) » et n'avance plus.
- Ce qui se passe :
  - `studio.py` `_lance()` (lignes 336 à 350) met la tâche en `attente_pc` et pose un marqueur dans le Blob ;
  - seule `manage.py relais_profils` les traite, lancée par une tâche planifiée Windows toutes les 5 minutes ;
  - sur ce PC, aucune tâche planifiée Cauri ou relais n'existe (vérifié avec `Get-ScheduledTask`) ;
  - le plugin iZotope RX 12 (`studio_paroles.py`, ligne 28) et le projet Remotion `C:\Users\agbal\Studio-AV\remotion`
    (`studio_raconte.py`, ligne 24) sont absents eux aussi.
- Ce qui devrait se passer : soit le relais est réinstallé, soit ces travaux passent dans le cloud. C'est une décision
  clé de la refonte.
- Point positif : on peut annuler ces tâches depuis l'appli (bouton « Annuler »).

**B2. Vidéo paroles avec un fichier son de plus de 4,5 Mo : l'envoi échoue et le projet reste « En cours »**
- Parcours : ＋ → Vidéo paroles → choisir un mp3 du téléphone (une chanson fait en général 4 à 10 Mo) → Préparer la vidéo.
- Ce qui se passe :
  - l'appli envoie le son en une seule requête (`studio2.html`, ligne 1000) ;
  - le serveur accepte jusqu'à 40 Mo (`studio.py`, ligne 907), mais Vercel refuse toute requête de plus de 4,5 Mo
    (`studio_edit.py` le rappelle lui-même dans sa docstring, lignes 4 et 5) ;
  - l'appli affiche « Erreur 413 » ;
  - la tâche, créée juste avant, reste en `telechargement` pour toujours (fantôme « En cours »).
- Ce qui devrait se passer : un envoi en morceaux, comme le Montage (`envoieEnMorceaux`, ligne 1557).
- Variante GÊNANT : un modèle importé dans « Mettre en valeur » est envoyé tel quel jusqu'à 8 Mo (`studio2.html`
  ligne 1101, `studio.py` ligne 1451). Une photo de téléphone de plus de 4,5 Mo échoue de la même façon.

**B3. Un post photo (Annonce, Photo + titre, Photo telle quelle, Collage) qui échoue à la publication est invisible**
- Prouvé par sonde.
- Pour reproduire : publier une Annonce pendant que Buffer est en limite de requêtes et que Meta n'est pas actif (ou en
  ne cochant que Telegram, voir G3).
- Ce qui se passe :
  - la tâche passe en `erreur`, avec « aucun réseau n'a accepté le carrousel » (`studio_photos.py`, ligne 398) ;
  - mais `historique()` cache tout projet photo qui n'est pas « prêt » (`studio.py`, lignes 455 à 457) ;
  - dans la sonde, un carrousel en échec et un carrousel publié ne sont pas renvoyés du tout ; seul le montage en échec
    l'est ;
  - l'écran Annonce dit « Annonce en fabrication, puis envoyée » (ligne 1078), et l'écran de tri « Carrousel en
    fabrication » (ligne 1522). Ensuite, plus aucun retour : le fondateur croit que c'est parti.
- Ce qui devrait se passer : les projets photo publiés ou en échec apparaissent dans l'Historique et dans les « Échecs »
  de l'accueil, comme les vidéos.

### GÊNANTS

**G1. Double appui ou tâche relancée : le même travail part deux fois (risque de double publication)**
- Prouvé par sonde.
- `photos_publier` (lignes 998 à 1022), `vedette_publier` (lignes 1417 à 1441), `paroles_lancer` (lignes 913 à 927) et
  `montage_lancer` (lignes 1537 à 1548) ne vérifient jamais l'état de la tâche. Deux appels donnent deux lancements
  (sonde : `[9, 9]` et `[8, 8]`).
- `montage_lancer` relance même une tâche déjà **publiée** (`envoye` repasse en `attente`).
- `.github/workflows/studio.yml` n'a pas de `concurrency:`, donc deux montages tournent en parallèle sur la même tâche.
- Côté appli :
  - « Publier le carrousel » (`#tp-publier`, ligne 1518) n'est pas désactivé pendant l'envoi : deux appuis donnent deux
    carrousels publiés ;
  - en revanche, les boutons du projet (`bouton()`, ligne 1217) sont bien protégés.
- Ce qui devrait se passer : n'accepter le lancement que depuis l'état attendu, et poser un verrou côté serveur.

**G2. « Mettre en valeur » : une erreur bloque le projet « En fabrication » pour toujours, et l'annulation est ignorée**
- `studio_montage.traite()` (lignes 748 et 749) appelle `vedette.traite` et `vedette.publie` sans `try/except`.
- Toute erreur (photo illisible, Blob, Buffer…) fait échouer la commande sans écrire `erreur` sur la tâche : elle reste
  en `montage`.
- `vedette.traite` termine par un `db.update(... "a_choisir")` direct (`vedette.py`, ligne 390). Une tâche annulée
  pendant la fabrication repasse donc « À choisir ».

**G3. La case Telegram ne fait rien pour les posts photo et les mises en valeur**
- Seul `_envoyer` (vidéos, lignes 680 à 685) envoie sur Telegram.
- `studio_photos.publie` (ligne 396) et `vedette.publie` n'appellent que `buffer.schedule`, et Buffer ne publie pas
  sur Telegram.
- Si seul Telegram est coché, rien ne part et la tâche passe en échec, invisible à cause de B3.

**G4. Les montages, vidéos paroles et « Cauri raconte » n'ont pas de copie pour Telegram (moins de 20 Mo)**
- `studio_edit.traite` ne fabrique ni la copie TikTok ni la copie Telegram. `studio_paroles` et `studio_raconte`
  fabriquent seulement la copie TikTok.
- Un montage de 60 à 90 s en 1080 × 1920 (crf 18 et 19), ou un « raconte » de 3 à 5 minutes, dépasse 20 Mo. Telegram le
  refuse alors (`telegram.py`, lignes 114 à 125), et l'appli l'annonce dans « Refusé : … ».
- `studio_edit` ne vérifie pas non plus que la vidéo est bien en ligne (`_verifie_en_ligne`), contrairement au clip.

**G5. Montage : aucun champ de texte ; le post part avec « Montage » comme titre et comme légende**
- L'appli n'envoie que `titre: 'Montage'` (ligne 1617). `artiste` et `credit` ne sont jamais envoyés.
- À la publication, `legende_fr` est vide, et la légende reprend donc l'accroche « Montage » (`studio.py`, ligne 619).
- On peut corriger l'accroche dans l'écran Publier, mais rien ne le signale. Le suivi du projet affiche aussi les étapes
  d'un clip (« L'IA regarde la vidéo », « Tu valides l'accroche »), qui n'existent pas pour un montage (lignes 1185 et
  1208).

**G6. Plusieurs saisies bizarres font tomber le serveur avec une page « Erreur 500 » en HTML (prouvé par sonde)**
- Les vues `montage_*`, `outils`, `vedette_*`, `paroles_*` et `collage` ne figurent pas dans la liste
  `_erreur_lisible` (lignes 1342 à 1344).
- Exemples :
  - `montage/<id>/morceau?k=abc` → ValueError (ligne 1532) ;
  - `montage/nouveau` avec `son` en texte → AttributeError (ligne 1507), ou avec `parts: "deux"` → ValueError (ligne 1493) ;
  - `outils` `{supprimer: "x"}` → ValueError (ligne 172) ;
  - `vedette/preparer` `{artiste_id: "x"}` → ValueError (ligne 1380) ;
  - un corps JSON qui est une liste → AttributeError partout (`_corps`, ligne 109, ne vérifie pas que c'est un objet).
- Dans l'appli, `get()` (ligne 672) ne vérifie pas `r.ok` : une page 500 ou 404 en HTML fait échouer `r.json()`.
  Selon l'écran, on obtient alors un message vague ou rien du tout.

**G7. « Partager → Cauri Studio » perd le lien si le Studio a servi il y a moins de 5 minutes**
- Lecture du code, à vérifier sur téléphone.
- Pour reproduire : utiliser le Studio, puis dans les 5 minutes partager un lien depuis Instagram vers Cauri Studio, dans
  une nouvelle fenêtre de l'appli.
- Ce qui se passe :
  - la page v3 s'ouvre avec `?lien=` ; le verrou (ligne 709) lance `/verrouiller` puis recharge sans paramètre ;
  - mais avant ce rechargement, le démarrage (lignes 1694 et 1695) a déjà lu puis **effacé** `studio-partage` dans
    `sessionStorage` ;
  - après l'empreinte, le lien a disparu.
- Ce qui devrait se passer : n'effacer le lien qu'une fois l'appli déverrouillée.

**G8. Une tâche qui tombe en route (GitHub, PC) reste « En cours » pour toujours**
- Aucun gardien ne remet en échec une tâche `attente`, `telechargement` ou `montage` trop vieille. J'ai cherché
  `studio_jobs` dans `views_cron` et les crons : rien.
- `studio.yml` coupe l'installation à 12 minutes. Si elle échoue, Python ne démarre pas et l'état n'est jamais écrit.
- Le relais du PC efface le marqueur du Blob **avant** de fabriquer (`relais_profils.py`, ligne 30, puis ligne 40) :
  si le PC s'éteint pendant le montage, la tâche est perdue, sans marqueur pour la reprendre.
- Les envois du téléphone coupés en route (montage, paroles, annonce) laissent aussi des tâches fantômes.

**G9. Annonce : l'attente des images peut tourner sans fin ou s'arrêter sans rien dire**
- La boucle `tour()` (lignes 1040 à 1045) ne s'arrête que sur `erreur`, ou sur `pret` avec des photos.
- Une tâche `pret` sans photo, `annule` ou `attente_pc` la fait tourner toutes les 3 secondes, sans fin.
- Une coupure réseau pendant l'attente la tue sans message, et le bouton « Récupérer » reste grisé.

**G10. Banque photos : les photos du téléphone refusées passent en silence, et la sélection s'arrête à 20**
- `#ba-lancer` (lignes 1449 à 1456) fait un `fetch` sans regarder la réponse : une photo trop petite ou illisible
  disparaît sans message.
- Au-delà de 20 photos, le reste est ignoré sans prévenir.

**G11. La tâche manuelle « Studio — publier les clips prêts » publie TOUT ce qui est prêt si on laisse le champ vide**
- Dans `studio_publie.py` (lignes 31 et 32), un champ « job » vide prend toutes les tâches `pret` avec une vidéo, y
  compris des projets laissés de côté depuis des semaines. Un oubli dans le formulaire GitHub suffit.

### DÉTAILS

- **D1.** `fabriquer` : une fin à 0 devient 60 s sans prévenir (`float(c.get("fin") or 60)`, ligne 373 ; prouvé par
  sonde). Un `NaN` dans le JSON passe tous les contrôles (sonde : `fin = nan` enregistré) et casse ffmpeg plus loin.
- **D2.** `annuler` (ligne 496) accepte une tâche déjà `annule` ou `erreur`. `job` inexistant → page 404 en HTML (ligne
  443) ; l'appli affiche alors « Projet introuvable ».
- **D3.** `envoie()` (lignes 673 à 676), qui sert aux fichiers, ne gère pas la session expirée (401). Pas de renvoi vers
  l'empreinte comme `post()` : on obtient « Erreur 401 » en plein envoi de fichiers.
- **D4.** `collage` (ligne 1561) et `montage` (photos de la banque) téléchargent n'importe quelle adresse `https://`
  depuis le serveur. Le risque est faible (Studio privé), mais il vaudrait mieux n'accepter que le domaine du Blob.
- **D5.** Les morceaux envoyés pour un collage vont dans `studio/montage/0-…` (tâche n° 0) et ne sont jamais effacés,
  pas plus que les morceaux des montages.
- **D6.** « Photo telle quelle » : la même image est enregistrée en `-916` pour la story et TikTok, sans recadrage en
  9:16 (`studio_photos.py`, lignes 370 à 376).
- **D7.** `profil_artiste` (GET) appelle Gemini pendant l'ouverture de l'écran Publier. Il peut ralentir de plusieurs
  secondes ; ce n'est pas bloquant, le reste de l'écran s'affiche.
- **D8.** `historique` lit 60 tâches, les filtre, puis en garde 30 : les plus anciennes disparaissent de la liste dès
  qu'il y a beaucoup de tris photo.
- **D9.** L'ancien Studio (`studio.html`, 1 673 lignes) reste accessible par « Ancien Studio » (`?classique=1`) et sert
  toujours d'écran d'empreinte. Il fait double emploi avec la v3, qui compte 1 701 lignes.
- **D10.** `vedette_recents` n'est plus appelé par l'interface v3. `fabriquer` lit `valider` et `reseaux`, mais la v3
  ne les envoie jamais : la validation de l'accroche est toujours demandée, et tous les réseaux sont cochés à la
  création.

### Écarts entre l'interface et le serveur (point 3 de ma méthode)

- Toutes les routes appelées par `studio2.html` existent bien dans `cauri/urls.py` : aucun bouton n'appelle une route
  absente.
- Les vidéos de début et de fin (`public/assets/studio/sequences`, 10 + 10) et les signatures sonores sont toutes
  présentes.
- Champs jamais remplis par l'interface : `montage.artiste` et `montage.credit` (G5) ; `fabriquer.valider` et
  `fabriquer.reseaux` (D10) ; `vedette_publier.legende_en`. L'écran promet que « l'anglais est traduit tout seul »
  (ligne 1415) ; je n'ai pas vérifié que `bilingue` le fait vraiment pour ce type de post.
- Limites de taille contradictoires : le serveur accepte 40 Mo (son) et 8 Mo (modèle), Vercel 4,5 Mo (B2).

---

## 3. Ce qui marche bien

- **La porte d'entrée est solide.**
  - L'adresse secrète est comparée en temps constant, et une mauvaise adresse donne une 404.
  - L'empreinte (WebAuthn) est redemandée après 5 minutes sans activité.
  - Les en-têtes `noindex`, `no-store` et une CSP avec nonce sont en place.
  - Tout cela est testé.
- **L'annulation est réelle pour les clips, montages, paroles et photos.** Chaque étape vérifie `annule` avant
  d'écrire (`_maj`, testé). Seule la mise en valeur y échappe (G2).
- **La publication vidéo est soignée.**
  - Pas de doublon TikTok, avec « Republier quand même ».
  - Le post est supprimé si aucun réseau ne l'a accepté, ce qui permet de réessayer proprement.
  - Les refus sont affichés en clair.
  - Instagram et Facebook partent en direct par Meta quand Buffer est en limite (`buffer.schedule`).
  - Les erreurs de `envoyer` reviennent en JSON lisible.
- **Le Montage envoie les gros fichiers en morceaux de 3,5 Mo**, le bon modèle à généraliser (B2). L'ordre des plans,
  le fondu ou la coupe, le départ de la chanson sur le refrain et le recadrage sur le visage sont là.
- **L'interface v3 est pensée pour le téléphone.**
  - Le geste retour est géré.
  - Les notifications push ouvrent le bon projet.
  - Le partage depuis les autres applis passe par le share target.
  - Les derniers réseaux choisis sont mémorisés.
  - Le bloc TikTok respecte les règles d'audit (visibilité, contenu de marque).
  - Les grilles restent lisibles sur un écran de 320 px (`minmax(0, …)`).
- **Toute la suite de tests passe** (272 sur 272 hors base) et le Studio s'importe sans numpy.

---

## 4. Les 5 corrections prioritaires

1. **Décider où tournent les travaux « PC » (B1).** Soit on réinstalle le relais, iZotope et Remotion sur le PC neuf
   avec une tâche planifiée, soit on les déplace dans le cloud (GitHub ou autre). En attendant, l'appli doit dire
   clairement « le PC est éteint » au lieu de « 5 minutes ».
2. **Envoyer tous les fichiers du téléphone en morceaux (B2)** : son des paroles et modèle de la mise en valeur. Il faut
   aussi supprimer la tâche, ou la passer en échec, si l'envoi échoue.
3. **Rendre visibles les posts photo publiés ou en échec (B3)**, et faire suivre l'Annonce et le carrousel jusqu'au
   résultat, comme une vidéo.
4. **Empêcher les doubles lancements (G1)** : vérifier l'état côté serveur dans `photos_publier`, `vedette_publier`,
   `paroles_lancer` et `montage_lancer`, ajouter `concurrency` à `studio.yml` et désactiver « Publier le carrousel »
   pendant l'envoi.
5. **Un gardien des tâches bloquées (G2 et G8)** : `try/except` pour la mise en valeur, effacer le marqueur du relais
   seulement après la fabrication, et passer en échec, avec un message, toute tâche « en cours » depuis plus de
   45 minutes. Le même jour, protéger les tests contre la base de production (piège de la section 1).

---

## 5. Les tests automatiques qui manquent

- **Garde-fou** : un test qui refuse de lancer la suite si `DATABASE_URL` contient `neon.tech`.
- **`envoyer`** :
  - choix des réseaux ;
  - légende complète, courte ou aucune ;
  - doublon TikTok et `forcer` ;
  - Telegram seul ;
  - aucun réseau accepté, donc post supprimé et erreur 502 ;
  - Buffer en 429 avec Meta actif ou inactif.
- **Doubles appels** : `photos_publier`, `vedette_publier`, `paroles_lancer` et `montage_lancer` deux fois de suite
  donnent un seul lancement ; `montage_lancer` est refusé sur une tâche `envoye`.
- **`historique`** : un post photo `envoye` ou `erreur` est renvoyé (B3).
- **`montage_nouveau`** : saisies invalides (`son` en texte, `parts` non numérique, `k` non numérique), avec une erreur
  400 en JSON, jamais une 500. Plus généralement, un test qui passe toutes les vues en revue avec un corps `[]` et
  vérifie qu'elles répondent en JSON.
- **`studio_edit.traite`** avec un faux ffmpeg : photo seule, vidéo seule, fondu ou coupe, plafond de 90 s, chanson
  « auto » ; annulation au milieu.
- **`vedette.traite` / `publie`** : une erreur donne l'état `erreur`, et une annulation n'est pas écrasée par
  `a_choisir`.
- **Limites de taille** : chaque envoi brut de l'appli reste sous 4,5 Mo, et le serveur refuse au-delà avec la même
  limite.
- **Relais du PC** : le marqueur est gardé tant que la tâche n'est pas finie.
- **`_lance`** : routage correct de chaque type (YouTube, paroles, raconte, montage avec YouTube → PC ; le reste →
  GitHub ; jeton absent → message clair).
- **Interface** (Playwright, écran de 360 px) :
  - coller un lien → bon outil proposé ;
  - partage avec `?lien=` puis verrou → le lien est conservé (G7) ;
  - bouton « Publier le carrousel » désactivé pendant l'envoi ;
  - aucun débordement horizontal.
- **`studio_publie`** sans `--job` : refuser, ou exiger une confirmation explicite (G11).

---

*Sondes et sorties : `sondes_yao.py` et `pytest_complet.txt`, dans le dossier temporaire de la session (hors dépôt).
Aucun autre fichier du dépôt n'a été modifié.*
