# CAURICHARTS — README / MASTER BLUEPRINT

**Version : 1.0 — 2026**

> **CauriCharts — Where African Music Gets Measured.**
>
> CauriCharts a pour ambition de devenir une infrastructure de données, de classement et de média dédiée à la musique africaine, en commençant par l'Afrique de l'Ouest.

---

# 1. VISION

CauriCharts ne doit pas être simplement un site qui affiche des Top 100.

L'ambition est de construire progressivement :

1. une plateforme de charts ;
2. une base de données musicale africaine ;
3. un média spécialisé ;
4. une plateforme d'intelligence musicale ;
5. une source de référence pour les artistes, labels, managers et médias ;
6. une API de données ;
7. des certifications et récompenses ;
8. une institution reconnue de l'industrie musicale africaine.

### Vision long terme

> **Devenir l'une des références mondiales pour les données, classements et analyses de la musique africaine.**

### Positionnement

**West African Music Intelligence**

### Promesse

> **The Data Behind African Music.**

---

# 2. LE PROBLÈME QUE CAURICHARTS VEUT RÉSOUDRE

Les grands services internationaux disposent de nombreuses données, mais la visibilité des marchés africains reste inégale.

Un artiste peut être :

- peu visible sur Spotify ;
- très fort sur YouTube ;
- très présent sur TikTok ;
- dominant sur Audiomack ou Boomplay ;
- extrêmement populaire dans son pays ;
- presque inconnu dans les classements mondiaux.

CauriCharts doit donc mesurer la performance musicale avec une approche adaptée aux réalités locales.

### Exemple

Un artiste togolais peut avoir :

- 5 000 auditeurs Spotify ;
- 250 000 vues YouTube ;
- 1,5 million de vues TikTok ;
- une forte présence locale ;
- une diffusion radio importante.

Un classement reposant uniquement sur Spotify pourrait sous-estimer sa popularité.

CauriCharts doit construire une vision plus complète.

---

# 3. ARCHITECTURE GLOBALE

```text
CAURICHARTS
│
├── CHARTS
│   ├── West Africa
│   ├── Africa
│   ├── Countries
│   ├── Cities
│   ├── Genres
│   └── Rising
│
├── ARTISTS
│   ├── Profiles
│   ├── Rankings
│   ├── Analytics
│   └── Verification
│
├── SONGS
│   ├── Trending
│   ├── New Releases
│   └── Chart History
│
├── CAURI SCORE
│
├── CAURI INTELLIGENCE
│   ├── Reports
│   ├── Trends
│   └── Market Data
│
├── CAURI NEWS
│
├── CAURI ORIGINALS
│
├── CAURI CARDS
│
├── CAURI CERTIFIED
│
├── SUBMIT
│
├── API
│
├── DATA LAB
│
├── AWARDS
│
└── SUMMIT
```

---

# 4. CAURICHARTS CHARTS

## 4.1 Charts nationaux

Première zone géographique :

- 🇹🇬 Togo
- 🇧🇯 Bénin
- 🇬🇭 Ghana
- 🇳🇬 Nigeria
- 🇸🇳 Sénégal
- 🇨🇮 Côte d'Ivoire
- 🇧🇫 Burkina Faso
- 🇲🇱 Mali
- 🇬🇳 Guinée
- 🇳🇪 Niger
- 🇨🇲 Cameroun
- 🇨🇩 RDC
- 🇨🇬 Congo
- et autres marchés africains.

## 4.2 Types de charts

- Top 100 Songs
- Top Artists
- Top Albums
- Top EPs
- Top Emerging
- Top Viral
- Top Local
- Top International
- Top Producers
- Top Labels
- Top Music Videos

## 4.3 Charts régionaux

### CauriCharts West Africa Top 100

À terme :

### CauriCharts Africa Top 200

Puis éventuellement :

### CauriCharts Global 1000

---

# 5. CAURI SCORE™

Le **Cauri Score™** est l'indicateur propriétaire de CauriCharts.

Il doit permettre d'évaluer la performance globale d'un artiste ou d'un morceau en prenant en compte plusieurs signaux.

## Sources potentielles

- Spotify
- Apple Music
- YouTube
- TikTok
- Audiomack
- Boomplay
- Shazam
- radio
- téléchargements lorsque les données sont disponibles
- autres sources vérifiées.

## Exemple de pondération de départ

> Cette pondération est une proposition initiale et devra être validée par des tests, des experts et des données réelles.

| Source | Poids indicatif |
|---|---:|
| Spotify | 20 % |
| YouTube | 20 % |
| Apple Music | 15 % |
| Audiomack | 15 % |
| Boomplay | 10 % |
| TikTok | 10 % |
| Shazam | 5 % |
| Radio / autres données vérifiées | 5 % |

### Exemple

**Artiste X**

CAURI SCORE™ : **82,7**

Le score doit tenir compte notamment :

- volume ;
- croissance ;
- régularité ;
- géographie ;
- performance récente ;
- présence multi-plateformes.

---

# 6. LOCAL PULSE

## Objectif

Mesurer ce qui est particulièrement populaire dans une ville ou un marché local.

Exemples :

- Cauri Local Pulse — Lomé
- Cauri Local Pulse — Dakar
- Cauri Local Pulse — Accra
- Cauri Local Pulse — Abidjan
- Cauri Local Pulse — Lagos

### Données possibles

- artistes populaires ;
- morceaux populaires ;
- genres dominants ;
- croissance ;
- tendances locales.

---

# 7. PROFILS ARTISTES

Chaque artiste doit disposer d'une page officielle.

## Exemple

**JOACHIM MIGOS**

🇹🇬 Togo

**CAURI RANK:** #17  
**CAURI SCORE:** 74.2

### Performance

- Spotify
- YouTube
- TikTok
- Audiomack
- Boomplay
- Shazam

### Historique

- Peak : #8
- Semaines dans le Top 100 : 21
- Entrée : semaine 32
- Progression : +7 positions

### Géographie

- 🇹🇬 Togo — #3
- 🇧🇯 Bénin — #18
- 🇨🇮 Côte d'Ivoire — #37

---

# 8. CAURI RISING

## Mission

Identifier les artistes dont la progression est la plus forte.

### Critères possibles

- progression dans les charts ;
- croissance du streaming ;
- croissance vidéo ;
- croissance sociale ;
- présence multi-plateformes ;
- progression géographique.

### Exemple

```text
#1  ↑ 43 positions
#2  ↑ 31 positions
#3  ↑ 22 positions
```

### Utilisateurs

- labels ;
- managers ;
- A&R ;
- producteurs ;
- festivals ;
- médias ;
- investisseurs.

---

# 9. CAURI INTELLIGENCE

Section professionnelle consacrée aux analyses du marché.

## Rapports

- West African Music Report
- Togo Music Market Report
- Senegal Music Market Report
- African Music Streaming Report
- African Music Economy Report
- Emerging Artists Report
- African Music Cities Report.

## CAURI INSIGHT

Courtes analyses basées sur les données.

Exemples :

> « Le Rap togolais gagne fortement en présence dans les charts cette semaine. »

> « TikTok devient un moteur majeur de découverte pour cette catégorie d'artistes. »

---

# 10. CAURI NEWS

CauriCharts devient également un média.

## Rubriques

- News
- Charts
- Artists
- Industry
- Business
- Releases
- Culture
- Data
- Opinion.

## Règle éditoriale fondamentale

Cauri News ne doit pas être un simple blog promotionnel.

Il faut séparer clairement :

- contenu éditorial ;
- contenu sponsorisé ;
- publicité ;
- partenariats.

La crédibilité du média dépend de cette séparation.

---

# 11. CAURI ORIGINALS

Contenu propriétaire.

### CAURI 10

10 artistes à surveiller.

### CAURI NEXT

Nouveaux talents.

### CAURI SESSIONS

Performances live.

### CAURI INTERVIEWS

Interviews approfondies.

### CAURI DOCUMENTARY

Mini-documentaires.

### CAURI DATA STORIES

Histoires racontées à partir des données.

---

# 12. CAURI CARDS

Chaque résultat important doit pouvoir être transformé automatiquement en contenu social.

## Exemple

```text
CAURI CHARTS

🇹🇬 TOGO

#01

ARTIST NAME

SONG NAME

WEEK 40 — 2026
```

Formats :

- Instagram
- TikTok
- X
- Facebook
- WhatsApp.

Objectif : permettre aux artistes de partager leurs performances et faire connaître naturellement CauriCharts.

---

# 13. CAURI CERTIFIED

À terme :

- CAURI GOLD
- CAURI PLATINUM
- CAURI DIAMOND.

Les seuils doivent être publics et documentés.

## Principe anti-fraude

CauriCharts doit développer des règles concernant :

- fake streams ;
- bots ;
- manipulation des vues ;
- manipulation des charts ;
- téléchargements artificiels ;
- trafic suspect.

Un classement crédible doit pouvoir exclure ou corriger les données manipulées.

---

# 14. CAURI SUBMIT

Les artistes peuvent soumettre leur profil.

## Informations

- nom d'artiste ;
- pays ;
- Spotify ;
- Apple Music ;
- YouTube ;
- TikTok ;
- Audiomack ;
- Boomplay ;
- Instagram ;
- label ;
- distributeur.

Après vérification :

**CAURI VERIFIED ✓**

---

# 15. CAURI API

L'API permettra à des entreprises d'utiliser les données CauriCharts.

## Exemples

```text
GET /artists
GET /charts
GET /tracks
GET /countries
GET /rankings
GET /trends
GET /artist/{id}
```

## Clients potentiels

- labels ;
- médias ;
- plateformes ;
- agences ;
- festivals ;
- chercheurs ;
- institutions ;
- investisseurs.

---

# 16. CAURI DATA LAB

Division spécialisée dans la recherche et les données.

## Publications

### CauriCharts African Music Index

Indice général du marché musical africain.

### African Artist Growth Index

Mesure de la croissance des artistes.

### African Music Cities Index

Comparaison des villes musicales.

### West African Music Economy Report

Analyse de l'économie musicale ouest-africaine.

---

# 17. CAURI MUSIC AWARDS

Récompenses annuelles basées sur des données vérifiables.

## Catégories

- Artist of the Year
- Song of the Year
- Album of the Year
- Breakthrough Artist
- Best Togo Artist
- Best Senegal Artist
- Best West African Artist
- Producer of the Year
- Label of the Year.

Le lien entre les awards et les données doit être transparent.

---

# 18. CAURI POWER LIST

Classements professionnels.

## Exemples

### CAURI 100 POWER

100 personnes influentes de la musique africaine.

### CAURI 40 UNDER 40

Professionnels de moins de 40 ans.

### CAURI WOMEN IN MUSIC

Femmes influentes de l'industrie.

### CAURI AFRICA MUSIC LEADERS

Dirigeants et acteurs majeurs du secteur.

---

# 19. CAURI MUSIC SUMMIT

Conférence annuelle.

## Sujets

- Music Business
- Streaming
- AI & Music
- Artist Development
- Distribution
- Publishing
- Labels
- Technology
- African Music Economy.

## Villes potentielles

Phase 1 : Lomé

Phase 2 :

- Accra
- Dakar
- Abidjan
- Lagos
- Paris.

Phase internationale :

- London
- Dubai
- Johannesburg
- New York.

---

# 20. MODÈLE ÉCONOMIQUE

CauriCharts doit être gratuit pour le grand public sur les fonctionnalités essentielles, puis monétiser les services professionnels.

---

# 21. TARIFICATION — ARTISTES

Prix indicatifs en FCFA.

## CAURI FREE

**0 FCFA / mois**

Pour découvrir CauriCharts.

Inclus :

- consultation des charts ;
- recherche artistes ;
- profils publics ;
- classement général ;
- tendances de base.

---

## CAURI ARTIST

**5 000 FCFA / mois**

Pour les artistes indépendants.

Inclus :

- profil artiste amélioré ;
- statistiques de base ;
- historique du classement ;
- Cauri Score ;
- suivi de progression ;
- 3 Cauri Cards / mois ;
- badge artiste ;
- soumission prioritaire.

---

## CAURI ARTIST PRO

**15 000 FCFA / mois**

Pour les artistes professionnels.

Inclus :

- tout CAURI ARTIST ;
- statistiques avancées ;
- historique complet ;
- comparaison avec d'autres artistes ;
- analyse géographique ;
- analyse multi-plateformes ;
- 10 Cauri Cards / mois ;
- rapports mensuels ;
- badge CAURI VERIFIED si éligible ;
- priorité support.

---

## CAURI ARTIST ELITE

**35 000 FCFA / mois**

Pour artistes établis et équipes.

Inclus :

- tout ARTIST PRO ;
- dashboard avancé ;
- rapports détaillés ;
- suivi des concurrents ;
- suivi de plusieurs sorties ;
- analyse de croissance ;
- stratégie de chart ;
- 30 Cauri Cards / mois ;
- rapport professionnel mensuel ;
- support prioritaire.

---

# 22. TARIFICATION — LABELS & MANAGERS

## CAURI LABEL STARTER

**50 000 FCFA / mois**

Jusqu'à 10 artistes.

Inclus :

- dashboard label ;
- suivi artistes ;
- suivi morceaux ;
- classement ;
- Cauri Score ;
- tendances ;
- export de données basique.

---

## CAURI LABEL PRO

**150 000 FCFA / mois**

Jusqu'à 30 artistes.

Inclus :

- dashboard professionnel ;
- comparaison artistes ;
- analyse pays ;
- analyse plateformes ;
- rapports mensuels ;
- exports CSV ;
- suivi concurrentiel ;
- alertes.

---

## CAURI LABEL ENTERPRISE

**À partir de 500 000 FCFA / mois**

Pour :

- grands labels ;
- distributeurs ;
- groupes médias ;
- grandes agences.

Inclus :

- API ;
- accès data avancé ;
- historique complet ;
- dashboards personnalisés ;
- exports massifs ;
- rapports personnalisés ;
- support dédié.

---

# 23. SERVICES PONCTUELS

## CAURI VERIFIED

**5 000 FCFA**

Vérification administrative du profil.

> La vérification ne garantit jamais un classement.

---

## CAURI ARTIST REPORT

**15 000 FCFA**

Rapport professionnel individuel :

- performance ;
- progression ;
- plateformes ;
- géographie ;
- positionnement ;
- recommandations.

---

## CAURI MARKET REPORT

**50 000 FCFA**

Rapport sur un marché donné.

Exemple :

> Togo Music Market Report

---

## CAURI CUSTOM REPORT

**À partir de 100 000 FCFA**

Rapport personnalisé pour :

- labels ;
- entreprises ;
- médias ;
- institutions ;
- festivals.

---

# 24. CAURI API — TARIFS INDICATIFS

## API STARTER

**50 000 FCFA / mois**

Pour petits projets.

---

## API PRO

**200 000 FCFA / mois**

Pour entreprises et médias.

---

## API ENTERPRISE

**À partir de 750 000 FCFA / mois**

Tarification personnalisée selon :

- volume ;
- endpoints ;
- historique ;
- fréquence ;
- nombre d'utilisateurs ;
- besoins commerciaux.

---

# 25. CAURI MEDIA — PUBLICITÉ

## Sponsored Article

**75 000 FCFA**

Article sponsorisé clairement identifié.

## Cauri Interview

**100 000 FCFA**

Interview éditoriale / partenariat clairement signalé.

## Homepage Campaign

**150 000 FCFA / semaine**

Présence publicitaire sur le site.

## Social Media Campaign

**100 000 FCFA / campagne**

Formats sociaux CauriCharts.

## Full Media Package

**300 000 FCFA**

Exemple :

- article ;
- interview ;
- réseaux sociaux ;
- Cauri Card ;
- mise en avant sur le site.

Les contenus payants doivent être identifiés comme tels.

---

# 26. CAURI SUMMIT — TARIFICATION INDICATIVE

## PASS STANDARD

**25 000 FCFA**

## PASS PRO

**75 000 FCFA**

## VIP

**150 000 FCFA**

## PARTENAIRE

**À partir de 500 000 FCFA**

## SPONSOR PRINCIPAL

**À partir de 2 000 000 FCFA**

Ces tarifs sont des hypothèses de lancement et doivent être adaptés à la taille et au lieu de l'événement.

---

# 27. COMMENT DEVENIR UN MÉDIA MONDIALEMENT RECONNU

C'est l'objectif stratégique principal.

CauriCharts ne doit pas essayer de devenir mondial immédiatement.

La stratégie est :

```text
TOGO
  ↓
AFRIQUE DE L'OUEST
  ↓
AFRIQUE
  ↓
DIASPORA AFRICAINE
  ↓
EUROPE / USA / UK
  ↓
INTERNATIONAL
```

---

# 28. PHASE 1 — DOMINER UN MARCHÉ

Objectif :

> Devenir la référence du classement musical au Togo.

Il faut construire :

- données ;
- charts ;
- méthodologie ;
- artistes ;
- médias ;
- partenariats.

Le nombre d'abonnés n'est pas le KPI principal.

Le KPI principal est :

> **Combien d'acteurs professionnels utilisent ou citent CauriCharts ?**

---

# 29. PHASE 2 — CONSTRUIRE LA MÉTHODOLOGIE

Créer :

# CAURICHARTS METHODOLOGY

Document officiel expliquant :

- sources ;
- collecte ;
- fréquence ;
- calcul ;
- pondérations ;
- règles d'éligibilité ;
- collaborations ;
- remixes ;
- versions accélérées ;
- versions ralenties ;
- IA ;
- fake streams ;
- corrections ;
- historique ;
- géographie.

La méthodologie doit être suffisamment claire pour être auditée et suffisamment robuste pour inspirer confiance.

---

# 30. PHASE 3 — CONSEIL INDÉPENDANT

Créer :

# CAURI CHARTS ADVISORY BOARD

Profils :

- music business ;
- data science ;
- droit musical ;
- labels ;
- distribution ;
- médias ;
- chercheurs ;
- industrie culturelle.

Principe :

> Aucun label ne doit pouvoir acheter une position dans un classement.

---

# 31. PHASE 4 — PARTENARIATS DATA

Développer progressivement des relations avec :

- Spotify ;
- Apple Music ;
- YouTube ;
- TikTok ;
- Audiomack ;
- Boomplay ;
- Shazam ;
- radios ;
- TV ;
- labels ;
- distributeurs.

La disponibilité réelle des données dépendra toujours des API, licences et accords commerciaux de chaque plateforme.

---

# 32. PHASE 5 — PARTENARIATS INSTITUTIONNELS

CauriCharts doit progressivement travailler avec :

- ministères de la Culture ;
- organismes de droits d'auteur ;
- sociétés de gestion collective ;
- associations de labels ;
- associations de producteurs ;
- festivals ;
- universités ;
- institutions culturelles.

Objectif :

> Devenir une infrastructure crédible de l'industrie musicale.

---

# 33. PHASE 6 — AUDIT EXTERNE

À mesure que CauriCharts grandit :

> Faire auditer la chaîne de production des charts.

Objectif :

**Données → Calcul → Classement**

devient une chaîne vérifiable.

À terme :

**CAURI CHARTS — DATA VERIFIED**

---

# 34. PHASE 7 — ÊTRE CITÉ PAR LES MÉDIAS

L'indicateur de reconnaissance internationale est simple :

> « According to CauriCharts... »

Puis :

> « CauriCharts data shows... »

Puis :

> « According to the CauriCharts West Africa Top 100... »

Le but n'est donc pas uniquement d'obtenir des followers.

Le but est de devenir une **source**.

---

# 35. PHASE 8 — CRÉER UNE VALEUR SYMBOLIQUE

Un artiste doit vouloir afficher :

> **#1 CAURI CHARTS — TOGO**

sur :

- Instagram ;
- TikTok ;
- dossiers de presse ;
- clips ;
- affiches ;
- sites ;
- communiqués.

Le classement devient alors un élément de carrière.

---

# 36. PHASE 9 — DEVENIR UNE SOURCE INDUSTRIELLE

À maturité :

Les journalistes consultent CauriCharts.

Les labels consultent CauriCharts.

Les managers consultent CauriCharts.

Les festivals consultent CauriCharts.

Les chercheurs consultent CauriCharts.

Les investisseurs consultent CauriCharts.

Les artistes veulent être classés par CauriCharts.

À ce stade :

> **CauriCharts n'est plus seulement un média. C'est une infrastructure de marché.**

---

# 37. CE QUI DOIT ÊTRE SACRÉ

Pour être reconnu comme une référence, CauriCharts doit protéger cinq principes.

## 1. INDÉPENDANCE

Un client ne peut pas acheter une position.

## 2. TRANSPARENCE

La méthodologie doit être expliquée.

## 3. EXACTITUDE

Les erreurs doivent être corrigées publiquement.

## 4. TRAÇABILITÉ

Les données doivent pouvoir être reliées à leurs sources.

## 5. INTÉGRITÉ ÉDITORIALE

La publicité ne doit pas déterminer les classements.

---

# 38. KPI STRATÉGIQUES

Ne pas mesurer uniquement les followers.

## Produit

- nombre d'artistes ;
- nombre de morceaux ;
- nombre de pays ;
- nombre de données collectées ;
- historique disponible.

## Audience

- utilisateurs mensuels ;
- utilisateurs professionnels ;
- newsletter ;
- réseaux sociaux ;
- visiteurs internationaux.

## Industrie

- labels partenaires ;
- distributeurs ;
- médias ;
- institutions ;
- artistes vérifiés.

## Autorité

- citations médias ;
- reprises des charts ;
- collaborations institutionnelles ;
- rapports téléchargés ;
- API clients.

---

# 39. ROADMAP

## PHASE 0 — FOUNDATION

- identité ;
- site ;
- architecture ;
- base de données ;
- méthodologie V1 ;
- premiers charts ;
- profils artistes.

## PHASE 1 — TOGO

- Top Togo ;
- Artist Database ;
- Cauri Score V1 ;
- Cauri Rising ;
- Cauri Cards ;
- Submit Artist.

## PHASE 2 — WEST AFRICA

- Bénin ;
- Sénégal ;
- Ghana ;
- Côte d'Ivoire ;
- Nigeria ;
- Burkina Faso ;
- Mali ;
- Guinée.

## PHASE 3 — MEDIA

- Cauri News ;
- interviews ;
- Originals ;
- YouTube ;
- newsletter ;
- podcasts.

## PHASE 4 — DATA BUSINESS

- Cauri Intelligence ;
- API ;
- reports ;
- Label dashboards ;
- Data Lab.

## PHASE 5 — INSTITUTION

- Advisory Board ;
- audit ;
- awards ;
- certifications ;
- summit.

## PHASE 6 — GLOBAL

- Africa Top 200 ;
- diaspora ;
- partenariats internationaux ;
- médias internationaux ;
- API internationale ;
- reconnaissance mondiale.

---

# 40. POSITIONNEMENT FINAL

CauriCharts ne doit pas communiquer :

> « Nous sommes le Billboard africain. »

Mais :

> **« CauriCharts is building the data and media infrastructure for African music. »**

Puis, avec le temps, si l'industrie adopte réellement la plateforme :

> **CauriCharts becomes the reference for African music data and charts.**

Le marché pourra alors naturellement commencer à parler de CauriCharts comme :

> **The Billboard of African Music.**

---

# 41. RÈGLE FONDAMENTALE

Ne jamais chercher la reconnaissance mondiale avant d'avoir construit l'autorité locale.

```text
DONNÉES
   ↓
MÉTHODOLOGIE
   ↓
FIABILITÉ
   ↓
CHARTS
   ↓
ARTISTES
   ↓
MÉDIAS
   ↓
INDUSTRIE
   ↓
INSTITUTIONS
   ↓
RECONNAISSANCE INTERNATIONALE
```

**La notoriété vient après la crédibilité.**

---

# 42. RÉSUMÉ EXÉCUTIF

CauriCharts doit évoluer en trois couches :

### CAURI CHARTS
Mesurer la musique.

### CAURI MEDIA
Raconter la musique.

### CAURI INTELLIGENCE
Comprendre la musique.

Puis :

### CAURI INSTITUTION
Structurer et influencer l'industrie.

La finalité est de créer une organisation capable de répondre à une question simple :

> **« Qu'est-ce qui se passe réellement dans la musique africaine ? »**

et d'apporter une réponse basée sur :

**DATA + CHARTS + JOURNALISME + INDUSTRY INTELLIGENCE.**

---

# 43. PHRASE FONDATRICE

> **CauriCharts — We don't just rank African music. We document its rise.**

