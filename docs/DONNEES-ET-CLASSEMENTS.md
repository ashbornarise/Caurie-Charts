# Cauri Charts — Données et classements : état complet

*État au 6 novembre 2026. Ce document décrit ce qui tourne réellement aujourd'hui, du relevé des données à la publication des classements, avec les limites assumées. La méthode publique détaillée reste [METHODOLOGIE.md](../METHODOLOGIE.md) et la page cauricharts.com/methodologie.*

> **Positionnement :** Cauri Charts mesure la consommation musicale **observable** à partir d'un ensemble documenté de sources, puis explique les résultats. Nous ne prétendons pas mesurer toute la consommation musicale (radio, ventes physiques, concerts…).

---

## 1. En chiffres

| | |
|---|---|
| Pays couverts | 16 (toute l'Afrique de l'Ouest) |
| Artistes actifs suivis | 1 176 |
| Titres en base | 33 003 |
| Clips YouTube officiels relevés chaque jour | ≈ 11 800 |
| Classements publiés depuis le lancement | 228 |
| Premier relevé | 30 septembre 2026 |

---

## 2. Les sources

**6 plateformes relevées aujourd'hui** (YouTube, Apple Music, Boomplay, Deezer, Shazam, Spotify), plus les déclarations d'artistes. Une 7e, Audiomack, est prévue dans la formule mais pas encore branchée.

Toutes ne jouent pas le même rôle :

| Source | Ce qu'on relève | Fréquence | Pays | Rôle |
|---|---|---|---|---|
| **YouTube** (API officielle) | Vues et j'aime de chaque clip officiel | Chaque jour | 15 | **Score officiel** : progression des vues de la semaine |
| **Apple Music** (flux public d'Apple) | « Les plus écoutés » : Top 100 par pays | Chaque jour | 14 (pas de classement Apple au Togo) | **Score officiel** : points de position |
| **Boomplay** (outil Apify, depuis le 06/11/2026) | « Top 100 <pays> » officiel de Boomplay | Chaque semaine | 11 : TG, BJ, GH, CI, SN, NG, BF, NE, SL, GN, ML | **Score officiel** : points de position |
| **Déclarations d'artistes** | Écoutes déclarées avec preuves (capture du tableau de bord) | Sur demande | Tous | **Score officiel**, seulement après validation et contrôle |
| **Deezer** (playlists « Top <pays> » de Deezer Charts) | Top 100 | Chaque jour | CI, SN, NG | Classement en direct, contrôle croisé |
| **Shazam** (CSV public) | Top 200 des 7 derniers jours | Chaque jour | GH, CI, SN, NG | Classement en direct, découverte de titres |
| **Popularité Deezer** (calculée) | Popularité des titres des artistes suivis | Chaque jour | 16 | Classement en direct (« indicatif ») |
| **YouTube Tendances / Découverte / chaînes d'artistes** | Nouveaux clips, nouvelles sorties | Chaque jour | Tous | Découverte des nouveaux titres (entrent plus vite dans les relevés) |
| **Spotify** (outil Apify) | Auditeurs mensuels, abonnés, rang mondial, villes d'écoute ; écoutes du Top 50 Nigeria | Chaque semaine | Tous | **Affichage et contrôle anti-fraude, hors score officiel** (décision du 29/10/2026, pour le coût) |
| **Audiomack** | « Weekly 100 » par pays | — | — | Prévu dans la formule, **pas encore branché** (accès API à obtenir, import CSV possible dans l'admin) |

**Spotify :** depuis le 06/11/2026, tous les artistes actifs sont relevés, chacun au moins une fois toutes les 4 semaines. Les artistes des tops sont relevés chaque semaine. Premier passage : 664 artistes.

---

## 3. La nuit : comment les données arrivent

- **Déclenchement :** chaque nuit vers 1 h UTC (Vercel), avec une relance de secours sur GitHub à 4 h 23 UTC si la nuit n'a pas tourné.
- **Deux chaînes en parallèle :**
  - **principal** : relevés des plateformes et calcul ;
  - **catalogue** : découverte de titres, chaînes YouTube, doublons.
- **Étapes principales :**
  1. Relevé des classements des plateformes.
  2. Rapprochement de chaque ligne avec un titre connu : nouveaux titres et nouveaux artistes créés si besoin.
  3. Relevé des vues YouTube des clips officiels.
  4. Calcul des scores de la semaine en cours.
  5. Mise à jour du classement en direct.
- **Rapport :** chaque nuit, un rapport est envoyé par e-mail. Les erreurs restent visibles dans l'admin, à la section « La nuit dernière ».

---

## 4. Nettoyage et rapprochement

- **Titres :** les mentions parasites sont retirées : « Official Video », « Clip officiel », « Lyrics »…
- **Clips :** un titre n'est relié qu'au clip **officiel** de l'artiste. Les chaînes « Topic » et les reprises sont écartées.
- **Doublons :** fusion automatique chaque dimanche (même artiste et même titre normalisé). Les **versions** (remix, live, acoustique) sont gardées à part : si deux clips ont plus de 20 secondes d'écart de durée YouTube, ce ne sont pas les mêmes titres.
- **Pays de l'artiste :** c'est **Google qui décide**, par une recherche vérifiée par l'IA, et seule une certitude « haute » est retenue.
  - Un artiste hors d'Afrique de l'Ouest sort du périmètre (exemple : Akon, Américain).
  - Le pays confirmé est enregistré sur la fiche (correction du 06/11/2026 : Himra et Didi B n'avaient pas de pays).
- **Classement d'un pays :** seuls les artistes **de ce pays** y figurent. Un pays n'a de classement officiel qu'à partir de **8 artistes suivis**.

---

## 5. Le score de la semaine (formule v3)

La semaine va **du lundi au dimanche**. Pour chaque titre :

| Composante | Calcul |
|---|---|
| YouTube | Progression des vues de la semaine × **0,5** |
| Apple Music, Boomplay, Audiomack | Moyenne sur la semaine de (101 − position) × **150** |
| Déclarations validées | Écoutes déclarées × **1**, ramenées à la semaine |

**Chaque composante est enregistrée séparément pour chaque titre**, avec trois informations :
- la valeur brute : vues gagnées ou points de position ;
- le poids appliqué ;
- les points obtenus.

**Garde-fous anti-fraude**, qui signalent le titre et le mettent en attente :

| Garde-fou | Seuil |
|---|---|
| Pic suspect | Plus de 5 fois la moyenne des 4 semaines précédentes |
| Rapport j'aime / vues YouTube anormal | En dehors de 1 à 250 j'aime pour 1 000 vues |
| Minimum de vues pour compter | 10 000 vues |
| Déclaration non corroborée | Écart de plus de 30 % avec les données publiques |
| Variation négative | Progression négative |

**Titres signalés :** ils sont vérifiés par Google (recherche contrôlée par l'IA) le mardi avant publication, puis un rattrapage a lieu le mercredi. Un titre exclu ne compte pas.

---

## 6. Les classements

| Classement | Ce qu'il mesure | Taille |
|---|---|---|
| **Prime** | Les titres qui ont le plus de succès dans la semaine | Top 20 au Togo et au Nigeria, Top 10 ailleurs |
| **Buzz** | Les plus fortes progressions : plus de 50 % et au moins 2 000 points, hors Prime | Idem |
| **Fresh** | Les sorties de moins de 56 jours | Idem |
| **Icon** | Les artistes : somme de leurs titres | Idem |
| **Legend** | Le cumul depuis le début | Idem |
| **Prime Afrique de l'Ouest** | Tous les pays ensemble ; au plus 5 titres d'un même pays | Top 20 |
| **Mois / Année** | Cumul des semaines | — |
| **En direct** | Classement du jour, toutes sources relevées | Top 20 |

**Règles de classement :**
1. **Diversité des sources :** pour entrer dans le Top 5, un titre doit être vu sur au moins **2 sources**. Sinon, il est placé juste après.
2. **Titres anciens :** un titre sorti il y a plus d'un an sort des tops, sauf si son score de la semaine atteint au moins 1,5 fois celui de la semaine précédente (vrai regain).
3. **3 titres au plus par artiste** dans chaque Top de titres. C'est la formule v3, en vigueur à partir de la semaine 45 (décision du fondateur du 06/11/2026). Les titres en trop descendent juste après le Top.
4. **Départage :** score, puis nombre de sources, puis progression, puis score précédent.

---

## 7. Publication

- **Quand :** automatique **chaque mardi à 8 h UTC**, sans validation manuelle (décision du 02/11/2026). Les semaines en retard sont rattrapées automatiquement.
- **Diffusion :** site, chaîne Telegram, post officiel du classement sur Instagram, Facebook et TikTok.
- **Reproductibilité :** chaque classement publié est **figé**, avec la formule exacte utilisée. Mêmes données, même calcul, même résultat. Un classement publié n'est jamais recalculé en silence : une correction porte une note datée.

---

## 8. Indice de fiabilité (sur 100, affiché sur chaque classement)

| Mesure (7 derniers jours) | Points |
|---|---|
| Nombre de plateformes relevées pour le pays (plein à partir de 4) | 40 |
| Nombre de jours relevés | 20 |
| Part des titres du Top vus sur au moins 2 sources | 30 |
| Fraîcheur du dernier relevé | 10 |

- **Lecture :** 70 et plus = fiabilité élevée ; de 45 à 69 = moyenne ; en dessous = faible.
- **Sources calculées :** un pays qui ne repose que sur des sources calculées (popularité Deezer, vues YouTube des artistes suivis) reste « indicatif », plafonné à 30.

---

## 9. Traçabilité : ce qu'on garde

| Donnée | Où | Visible |
|---|---|---|
| Vues et j'aime YouTube, jour par jour | `snapshots` | Admin |
| Positions de chaque plateforme, jour par jour | `chart_observations` | Admin, classement en direct par plateforme |
| Score de chaque titre par semaine, détaillé source par source | `weekly_scores.breakdown` | **Admin seulement** (page d'un classement) |
| Classements publiés, avec la formule appliquée | `chart_runs`, `chart_entries` | Site |
| Versions de la formule, avec date et motif | `formula_versions` | Admin, page Méthode |
| Vérifications de pays par Google | `pays_verifs` | Admin |

---

## 10. Limites assumées

1. **Pas de données radio ni TV.** C'est une audience importante en Afrique de l'Ouest, et nous ne la mesurons pas.
2. **Spotify est hors du score officiel** : ses chiffres sont seulement affichés.
3. **Audiomack et TikTok ne sont pas branchés.** TikTok devra mesurer la viralité, pas des écoutes.
4. **Apple Music n'a pas de classement au Togo.** Shazam ne couvre que 4 pays, Deezer 3.
5. **Boomplay est hebdomadaire** : un relevé par semaine, contre un par jour pour Apple.
6. **Les vues YouTube ne comptent que les clips officiels** : les reprises, les lyrics non officiels et les extraits TikTok ne sont pas comptés.

---

## 11. Ce qui reste à faire

D'après les recommandations pour le projet télévisé en Côte d'Ivoire :

| Chantier | État |
|---|---|
| Score par source conservé (brut, poids, points) | ✅ Fait, visible dans l'admin. **Version publique à faire** : « Pourquoi ce rang ? » sur chaque titre |
| Indice de confiance | ✅ Fait par classement (indice de fiabilité). Par titre : à faire |
| Gel des données et traçabilité | ✅ Fait |
| Documenter les anomalies | ✅ En grande partie : drapeaux, revue Google, journal de la nuit |
| Boomplay | ✅ Branché le 06/11/2026 |
| Fenêtre du samedi pour l'émission | ⏳ À décider |
| Recalcul de l'historique avec la formule finale (10 à 20 semaines) | ⏳ À faire, hors classements publiés |
| Fiche explicative du Top 20 pour la production télé | ⏳ À faire |
| Audiomack, TikTok | ⏳ À brancher selon l'accès aux données |
| Radio, TV, BURIDA | ⏳ Partenariats, 2027 |

---

## 12. Coûts des données (par mois)

| Poste | Montant |
|---|---|
| Apify (Spotify et Boomplay) : plafond automatique | 4,50 $ (1,88 $ dépensés au 06/11) |
| Boomplay seul | ≈ 0,05 $ |
| IA (vérifications Google, textes) | Gemini 5 $ et DeepSeek 5 $ par 30 jours, plafonnés chaque jour |
| YouTube, Apple, Deezer, Shazam | Gratuits (quota YouTube quotidien partagé entre deux clés) |
