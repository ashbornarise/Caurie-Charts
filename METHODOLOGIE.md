# Cauri Charts : méthodologie et famille de classements

Version 1.1 (brouillon), 29 septembre 2026. Ce document a deux usages : la partie 1 à 8 sert de cahier des charges interne, la partie 9 est le texte public à publier sur la page Méthodologie du site.

Tout ce qui est chiffré ici (poids, seuils, tailles) est une proposition de départ. Ces valeurs se valident après quatre semaines de vraies données, puis se figent dans une version publiée.

## 1. Principes

1. **Transparence.** La formule, les sources et les règles sont publiques.
2. **Reproductibilité.** Chaque classement se recalcule à partir des relevés stockés. Le numéro de version de la méthodologie est enregistré avec chaque publication.
3. **Aucune position modifiée à la main.** Un admin peut exclure un titre pour anomalie, avec une raison écrite et publique. Il ne peut jamais monter ou descendre un titre.
4. **Mêmes règles pour tous**, y compris pour les artistes de Nova Luz, qui portent un badge visible.
5. **Données vérifiables d'abord.** Les chiffres publics l'emportent sur les déclarations.

## 2. Périmètre

**Pays de départ.** Togo, Bénin, Ghana, Côte d'Ivoire, Sénégal.

**Un artiste est classé dans le pays où il soumet sa musique.** C'est le pays de soumission qui fait foi, pas la nationalité. Le pays où l'artiste est le plus écouté s'affiche à part, comme statistique sur sa fiche, sans changer son classement. Cette répartition par pays vient des captures fournies par l'artiste (Spotify for Artists, YouTube Studio, etc.), pas d'une collecte automatique.

**Regroupement des versions.** Le titre original, son clip officiel, ses versions lyrics et audio, ses remixes et ses lives comptent pour un seul titre. Un remix n'est classé à part que s'il a un autre artiste principal ou s'il a été publié comme titre distinct (à décider au cas par cas, en admin).

**Période de suivi.** Du lundi 00 h 00 au dimanche 23 h 59 (heure de Lomé, UTC+0). Le classement est calculé le lundi, vérifié, puis publié le mardi.

## 3. Sources de données

| Source | Ce qu'on en tire | Statut au départ |
|---|---|---|
| YouTube | Vues des vidéos officielles (clip, audio officiel, Art Track) | Automatisé, API officielle |
| Audiomack | Streams | À vérifier : accès API sur demande, sinon relevé manuel ou déclaré |
| Boomplay | Streams | Pas d'API publique connue : relevé manuel ou déclaré, partenariat à chercher |
| Spotify | Métadonnées et indice de popularité | Pas de streams par titre : sert à identifier les titres, pas au score |
| Apple Music, Deezer | À évaluer par pays | À vérifier selon l'audience réelle |
| Déclarations d'artistes et labels | Captures Spotify for Artists, Audiomack, Boomplay, etc. | Formulaire, validation manuelle |

**Règle sur les compteurs.** Les plateformes donnent des totaux cumulés. Le système enregistre un relevé chaque jour, et la contribution d'une plateforme à la semaine est le compteur du dimanche moins celui du dimanche précédent.

**Ce qui ne compte pas.** Les vues de vidéos non officielles (reprises, montages, TikTok) ne sont pas comptées au départ, faute de moyen de les rattacher proprement.

## 4. Formule du score

```text
score_titre = somme, pour chaque source, de (variation_de_la_semaine x poids_source)
```

Poids de départ :

| Source | Poids |
|---|---|
| Streams audio (Audiomack, Boomplay, autres) | 1,0 |
| Vues YouTube officielles | 0,5 |
| Déclarations validées | 1,0, mais seulement si recoupées par une donnée publique |

Les poids peuvent différer par pays si les usages le justifient (un pays où YouTube domine, par exemple).

**Règle de diversité.** Pour entrer dans le Top 5 d'un pays, un titre doit avoir des données sur au moins deux sources. Sinon, il est plafonné à la sixième place. Cette règle est à tester : elle protège contre la manipulation d'une seule plateforme, mais peut pénaliser un artiste qui n'a qu'une chaîne YouTube.

### Version 1.2 : positions dans les classements des plateformes (annoncée pour le 12 octobre 2026)

Sans notoriété, demander des captures d'écran aux artistes ne suffit pas à couvrir les cinq pays. La version 1.2 ajoute une source publique et automatique : la position des titres dans les classements des plateformes.

- **Sources.** Classement Apple Music « les plus écoutés » par pays (flux public, quotidien : Bénin, Côte d'Ivoire, Sénégal, Ghana ; pas de classement pour le Togo). Classements Audiomack « Weekly 100 » par pays (Togo, Bénin, Côte d'Ivoire notamment), importés à la main tant que l'accès à l'API n'est pas accordé. Classements Boomplay, même traitement.
- **Points de position.** Chaque jour de présence rapporte (101 − position) points sur un Top 100 : 100 pour la 1re place, 1 pour la 100e. Moyenne sur les jours relevés de la semaine, puis somme sur les pays où le titre est classé.
- **Poids de départ.** 150 par point de position, pour chaque plateforme : une 1re place tenue toute la semaine vaut 15 000 points, l'équivalent de 15 000 écoutes audio. À valider après quatre semaines de données.
- **Diversité.** Une position compte comme une source pour la règle du Top 5. Une même plateforme présente à la fois en compteur et en classement ne compte qu'une fois.
- **Règle des pays inchangée.** Les classements des plateformes contiennent des artistes d'autres pays (Nigeria, France…). Un artiste découvert par l'import reste en attente et n'est classé qu'après confirmation de son pays de soumission ; les artistes hors des cinq pays sont écartés.
- **Découverte.** L'import crée automatiquement les titres et artistes nouveaux, puis cherche leur clip YouTube officiel (quota limité). Les correspondances automatiques sont vérifiées par l'équipe.

**Départage en cas d'égalité, dans l'ordre :** nombre de sources différentes, meilleure progression sur la semaine, score de la semaine précédente.

## 5. La famille de classements

Chaque nom est une proposition. Les termes "Hot 100", "Billboard 200", "Artist 100", "Bubbling Under" et "Global 200" appartiennent à Billboard : ne pas les reprendre. Les noms de classements ci-dessous (Prime Chart, Buzz Chart, Fresh Chart, Icon Chart, Legend Chart, Vintage Chart) sont des propositions à confirmer, seul le nom de marque Cauri Charts est retenu.

### Phase 1, au lancement

| Classement | Contenu | Période | Taille |
|---|---|---|---|
| **Prime Chart** (par pays) | Le classement principal, l'équivalent du "Hot 100" : les titres les plus performants de la semaine | Hebdomadaire | Top 20 Togo, Top 10 autres pays |
| **Buzz Chart** | Les titres dont la progression est la plus forte et qui ne sont pas encore dans le Prime Chart | Hebdomadaire | 10 |
| **Fresh Chart** | Titres sortis depuis moins de 8 semaines, ou artistes émergents | Hebdomadaire | 10 |
| **Icon Chart** | Classement des artistes : somme des scores de tous leurs titres sur la semaine | Hebdomadaire | 10 |
| **Prime Chart Afrique de l'Ouest** (page d'accueil) | Le classement total des cinq pays : tous les titres classés selon le même score hebdomadaire et les mêmes règles (diversité, départage) que les classements nationaux. Seules les semaines nationales publiées y entrent ; le total est publié quand les cinq pays ont publié. Mois et année : somme des scores | Hebdomadaire, mensuel, annuel | 20 |

Pourquoi le total plutôt que des points par rang : un titre n'est classé que dans le pays de soumission de son artiste, donc il n'apparaît jamais dans plusieurs classements nationaux. Des points par rang mettraient les cinq numéros 1 à égalité, quelle que soit leur audience réelle. Le score est déjà calculé de la même façon partout (mêmes compteurs, mêmes poids) : il se compare directement d'un pays à l'autre.

Règle de Buzz Chart : une progression de plus de 50 % par rapport à la semaine précédente, et un score minimum (à fixer avec les données) pour éviter qu'un titre à 10 écoutes passe pour un phénomène.

### Phase 2, après 6 à 8 semaines de régularité

| Classement | Contenu | Période |
|---|---|---|
| **Prime Chart Mensuel** | Somme des scores hebdomadaires du mois | Mensuel, publié le premier mardi du mois suivant |
| **Records** | Le plus de semaines à la première place, la plus forte entrée, la plus longue présence. Une page de faits, peu coûteuse à produire et très partageable | Mise à jour continue |

### Phase 3, quand les données sont solides

| Classement | Contenu | Remarque |
|---|---|---|
| **Vintage Chart** | Somme des scores hebdomadaires sur l'année, par pays | Période de suivi à fixer (année civile ou décembre à novembre) |
| **Album Chart** | Somme des scores des titres d'un album ou EP | Demande un rattachement fiable titre-album |
| **Classements par genre** | Afrobeats, rap, gospel, rumba, coupé-décalé, reggae, etc. | Demande un étiquetage des genres par titre |
| **Radio Chart** | Diffusions radio et TV | Demande des partenariats avec des stations |

### Le classement "tout temps"

Il y a un piège : avant le lancement de Cauri Charts, il n'existe aucun relevé hebdomadaire, donc aucun score comparable. Deux versions sont possibles.

1. **Legend Chart** (à ouvrir dès le premier jour). Cumul de tous les scores hebdomadaires depuis le lancement. Il est vide au départ et se construit avec le temps.
2. **Legend Chart Historique** (plus tard). Un classement rétrospectif construit à partir des compteurs cumulés actuels des plateformes (total des vues YouTube d'un clip, par exemple). Il n'est pas comparable au score hebdomadaire et doit l'annoncer clairement : "cumul des compteurs publics à la date du relevé". Utile pour raconter l'histoire de la musique togolaise, mais à présenter comme une autre méthode.

Recommandation : lancer la première version et attendre d'avoir une vraie audience avant la seconde.

## 5 bis. Classements en direct (en attendant et à côté du classement officiel)

Le classement officiel se calcule chaque semaine à partir des écoutes et des vues relevées chaque jour. En attendant sa première publication, puis à côté de lui, le site affiche des **classements en direct** construits uniquement avec des données publiques réelles :

| Source | Pays | Ce qu'elle mesure |
|---|---|---|
| Apple Music (flux public) | Bénin, Ghana, Côte d'Ivoire, Sénégal | Titres les plus écoutés |
| Deezer (classements officiels « Deezer Charts ») | Côte d'Ivoire, Sénégal | Titres les plus écoutés |
| Shazam (Top 200) | Ghana, Côte d'Ivoire, Sénégal | Titres les plus recherchés (découverte) |
| YouTube tendances | Ghana, Sénégal | Vidéos musicales du moment |
| YouTube nouveaux clips | Togo, Bénin | Clips publiés depuis 21 jours, les plus vus |
| Popularité Deezer | Les cinq pays | Score de popularité Deezer des titres des artistes suivis |
| Vues YouTube | Les cinq pays | Vues gagnées sur 7 jours par les clips suivis (vues totales des clips récents les premiers jours) |

Règles :

1. Chaque position rapporte des points sur 100 selon la taille du classement : n° 1 d'un Top 200 = 100 points, dernier = 0,5.
2. Les points d'un titre s'additionnent sur toutes les sources, et sur la période choisie (7 jours, 30 jours, 12 mois, tout temps).
3. **Classement des cinq pays : chaque pays pèse autant.** Les points d'un titre sont divisés par le nombre de sources disponibles dans son pays. Sans cette règle, un pays couvert par cinq plateformes écraserait un pays qui n'en a qu'une ou deux (Togo, Bénin) à popularité égale.
4. Seuls les artistes des cinq pays apparaissent. Le pays d'un artiste est celui de sa scène (origine, public, langue, collaborations), pas le pays qu'il déclare sur les plateformes pour la distribution ou les revenus.
5. Buzz en direct : titres hors du Top du pays, classés sur les sources de découverte (Shazam, YouTube) et sur les places gagnées en une semaine. Fresh : titres sortis depuis moins de 8 semaines. Icon : points de tous les titres de l'artiste. Legend : points cumulés depuis le premier relevé.

Ces classements en direct ne remplacent pas le classement officiel et ne sont pas utilisés pour le calculer.

## 6. Anti-fraude

- **Pic anormal.** Une variation hebdomadaire supérieure à cinq fois la médiane des quatre dernières semaines place le titre "à vérifier". Il n'est pas publié tant qu'un admin ne l'a pas validé ou exclu.
- **Déclaration contredite.** Une déclaration qui s'écarte de plus de 30 % des données publiques est marquée "à vérifier".
- **Ratio suspect sur YouTube.** Un rapport très déséquilibré entre vues et mentions "j'aime" ou commentaires déclenche un contrôle.
- **Pas de contrôle possible, pas de points.** Une donnée qu'on ne peut ni recouper ni vérifier ne compte pas dans le score.
- **Liste publique des retraits.** Chaque mois, la liste des titres exclus pour anomalie est publiée, avec le motif. La liste montre que le système fonctionne.

## 7. Conflit d'intérêts

Cauri Charts appartient au même groupe que Nova Luz. Pour que le classement reste crédible :

1. Le badge "Nova Luz" s'affiche automatiquement sur tout artiste signé chez le label.
2. La page Méthodologie dit clairement que les deux entités appartiennent au même groupe.
3. Les artistes Nova Luz sont soumis aux mêmes contrôles, sans exception. En cas de doute, la donnée publique prévaut sur la déclaration.
4. Nul ne peut modifier une position à la main.
5. Dès que possible, un comité indépendant (un journaliste musical, un producteur extérieur, un représentant d'artistes) relit la méthodologie et peut demander un contrôle. Pour les futurs awards, le jury est indépendant du label.

## 8. Publication, corrections et contestations

- **Calendrier.** Calcul le lundi, vérification, publication le mardi. Les classements mensuels sortent le premier mardi du mois suivant.
- **Historique.** Chaque classement publié reste consultable, avec la version de la méthodologie qui l'a produit.
- **Correction d'erreur.** Toute erreur corrigée est signalée sur la page du classement, avec la date et la raison.
- **Contestation.** Un artiste ou un label peut contester une position ou une exclusion via un formulaire, avec ses preuves. Réponse sous sept jours, et résultat inscrit dans le journal d'audit.
- **Changement de méthode.** Toute modification de formule est annoncée au moins deux semaines avant son entrée en vigueur, avec un numéro de version.

## 9. Texte public pour la page Méthodologie

À publier tel quel, à ajuster une fois les vrais chiffres connus.

---

### Comment sont construits les classements Cauri Charts

Cauri Charts classe la musique d'Afrique de l'Ouest à partir de chiffres d'écoute. Chaque semaine, nous mesurons combien un titre a été écouté ou visionné du lundi au dimanche, nous additionnons ces chiffres selon une formule publique, et nous publions le résultat le mardi.

**D'où viennent les chiffres.** Nous relevons chaque jour les compteurs publics des plateformes (YouTube, Audiomack, Boomplay, et d'autres selon les pays). Quand une plateforme ne donne pas accès à ses données, nous acceptons des déclarations d'artistes et de labels, à condition de pouvoir les recouper avec une donnée publique.

**Comment est calculé le score.** Chaque écoute audio vaut un point. Chaque vue d'une vidéo officielle en vaut un demi. Nous comptons uniquement la progression de la semaine, pas le total accumulé depuis la sortie. Un titre récent peut donc battre un titre ancien.

**Ce que nous vérifions.** Un titre dont les chiffres explosent sans explication est examiné avant publication. Les titres exclus pour anomalie sont listés chaque mois avec la raison.

**Notre position.** Cauri Charts fait partie de Novaluz Group, qui inclut le label Nova Luz Music. Les artistes de ce label sont signalés par un badge et soumis exactement aux mêmes règles. Personne, chez Cauri Charts, ne peut déplacer un titre à la main.

**Une erreur ? Un désaccord ?** Écrivez-nous avec vos preuves. Nous répondons sous sept jours, et toute correction est publiée.

Version de la méthodologie : 1.1.

---

## 10. Points à trancher

1. Un remix compte-t-il avec l'original ou séparément ?
2. (Tranché) Un artiste est classé dans le pays où il soumet sa musique.
3. Le Top 10 des pays autres que le Togo est-il assez fourni en données pour être crédible dès le premier jour ?
4. Lance-t-on "Legend Chart" dès le premier classement, ou après quelques mois ?
5. Année civile ou décembre à novembre pour le bilan annuel ?
6. Qui compose le comité indépendant, et à partir de quand ?
7. Les poids (1,0 pour l'audio, 0,5 pour YouTube) sont-ils justes ? Réponse après quatre semaines de données réelles.
