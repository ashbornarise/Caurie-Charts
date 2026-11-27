# Débat des IA : renouveler la course du live TikTok

27/11/2026 (2e débat) · Groq et Gemini en direct, DeepSeek par OpenRouter (clé DeepSeek refusée), deux tours.

## Le brief

Tu participes à un comité de 3 IA (Groq, Gemini, DeepSeek) pour Cauri Charts, média de classements musicaux
d'Afrique de l'Ouest (Togo, Bénin, Ghana, Côte d'Ivoire, Sénégal). Chaque semaine, le fondateur fait un LIVE TikTok
(« la Nuit Cauri Charts ») : un écran vertical 9:16 animé (dans TikTok LIVE Studio) piloté par une régie web. Un connecteur
reçoit en direct les commentaires, les « j'aime » (taps sur l'écran) et les cadeaux TikTok des spectateurs.

LE JEU ACTUEL (« la course ») : 4 pays par manche roulent sur une piste (voitures), tout le monde avance seul à vitesse
lente (200 s si personne ne joue). Un commentaire qui cite un pays (drapeau, nom, code « CI ») = +0,5 % de piste
(anti-spam : 1 action par joueur toutes les 1,5 s, insultes ignorées). Les j'aime d'un joueur inscrit poussent son pays
(+1 % par paquet de 40). Une rose = boost ; un cadeau de 10 pièces ou plus bouscule la voiture de devant. Écran de
victoire avec le meilleur supporter, manche suivante 14 s après. Problèmes : 4 voitures c'est illisible sur téléphone,
le jeu est toujours le même (pays contre pays), et il faut écrire pour jouer.

L'IDÉE DU FONDATEUR : seulement 2 ou 3 équipes à l'écran ; les équipes peuvent être des PAYS, des ARTISTES (ex. Didi B
contre Himra) ou des SUJETS (ex. « Coupé-décalé contre Afrobeats », « Clip contre Audio ») ; les spectateurs poussent
leur équipe en tapant sur l'écran (j'aime) — le geste le plus simple sur TikTok.

CONTRAINTES : lisible en 1 seconde sur un téléphone ; aucun texte long ; rien qui ressemble à un pari ou à de l'argent
à gagner ; respecter les règles des LIVE TikTok (pas de récompense promise contre des cadeaux, pas de contenu trompeur) ;
les j'aime arrivent par paquets (TikTok regroupe les taps) ; ATTENTION : TikTok NE transmet PAS l'endroit de l'écran où le spectateur a tapé, seulement « tel pseudo a envoyé N j'aime » : toucher une zone de l'écran ne peut donc PAS choisir une équipe ; il faut
un moyen simple de rattacher un spectateur à une équipe ; une manche dure 1 à 3 minutes ; le fondateur pilote seul,
depuis son téléphone. Réponds en français, concret, sans emojis.

## Tour 1 : chaque IA propose

### Groq

**1. Nom & principe**  
**« Duel Flash »** – Deux (ou trois) équipes s’affrontent sur une barre de progression verticale ; chaque « like » reçu par un spectateur alimente instantanément la barre de l’équipe qu’il a désignée. La première qui atteint le sommet remporte le round.

**2. Choix de l’équipe & action du spectateur**  
*Étape 1 :* le présentateur, dès le début du round, indique le **hashtag dédié** à chaque équipe (ex. #CI, #GH, #AFRO).  
*Étape 2 :* le spectateur commente **une seule fois** le hashtag de son équipe ; le système enregistre le pseudo → équipe.  
*Étape 3 :* à chaque fois que le même spectateur envoie des **likes** (ou un cadeau), le backend associe ces réactions à l’équipe déjà enregistrée.  
*Règle anti‑spam* : un même pseudo ne peut changer d’équipe qu’une fois toutes les 30 s, et ne peut envoyer plus de 5 likes consécutifs sans délai de 1 s (TikTok regroupe déjà les likes, donc on compte les paquets).

**3. Affichage 9:16 (max 5 points)**  
1. **Bande supérieure** : titre animé « DUEL FLASH », logo Cauri Charts, compte à rebours du round.  
2. **Zone centrale** : 2‑3 barres verticales parallèles, chaque barre porte le drapeau ou l’icône de l’équipe, couleur distincte, et un petit compteur de likes (ex. + 120 ❤️).  
3. **Bande inférieure** : rang des meilleurs supporters du round (pseudo + nombre de likes).  
4. **Bord latéral** : indicateur de « Boost » (rose) qui apparaît quand un cadeau ≥ 10 coins est reçu – la barre de l’équipe du donateur reçoit un gain de +5 %.  
5. **Transition finale** : écran de victoire 2 s (équipe gagnante + pseudo du super‑supporter), puis fondu vers le prochain round (14 s de pause).

**4. Types de duels & sélection**  

| Type | Exemple | Choix par la régie |
|------|---------|--------------------|
| Pays | **Côte d’Ivoire (CI) vs Ghana (GH)** | Le présentateur sélectionne les deux pays les plus mentionnés dans les commentaires de la semaine précédente. |
| Artistes | **Didi B vs Himra** | L’algorithme récupère les 2 artistes les plus streamés sur les plateformes locales la semaine passée. |
| Sujets | **Coupé‑décalé vs Afrobeats** | Le système tire aléatoirement 2 genres ou concepts populaires dans les tendances TikTok ou les playlists Cauri. |

Le présentateur valide le tirage en temps réel (affiche les hashtags correspondants) et peut, en cas de déséquilibre, remplacer une équipe par la suivante dans le classement.

**5. Facteurs de ré‑engagement**  
- **Progression visible** : la barre se remplit en temps réel, créant un effet de « course » qui pousse les spectateurs à suivre le score.  
- **Retournement** : le « Boost » (rose ou cadeau) peut inverser la tête de la course à tout moment, incitant à réagir rapidement.  
- **Record personnel** : chaque round affiche le nombre maximal de likes cumulés par un supporter ; les spectateurs tentent de battre le record du round précédent.  
- **Mini‑défis** : toutes les 5 rounds, un « défi éclair » (ex. doublez les likes en 30 s) donne un badge visuel au meilleur supporter, visible sur le profil du présentateur.

**6. Risques majeurs & mitigation**  

| Risque | Solution |
|--------|----------|
| **Concentration de likes sur une seule équipe (déséquilibre visuel)** | Limiter le gain maximal par paquet de likes à 3 % de la barre ; les excédents sont redistribués proportionnellement aux équipes restantes. |
| **Violation des règles TikTok (incitation à donner des cadeaux)** | Le « Boost » ne dépend que du **type** de cadeau (rose ou ≥ 10 coins) et non du montant ; aucune promesse de gain monétaire n’est faite, le visuel indique simplement « Boost » sans mentionner de valeur. |

Cette version reste lisible en une seconde, ne nécessite que le geste le plus simple (un like), et offre un cycle de jeu dynamique qui incite les spectateurs à revenir chaque nuit.

### Gemini

Voici ma proposition pour le nouveau jeu.

### 1. Nom et Principe
**Le Choc des Clans**  
Deux ou trois clans s'affrontent dans un duel de jauges verticales en temps réel. Le clan qui remplit sa jauge en premier ou qui domine à la fin du temps imparti gagne la manche.

### 2. Attribution d'équipe et Interactions
L'attribution se fait par le premier mot ou drapeau tapé dans le chat. 
*   **Rejoindre :** Le joueur écrit le nom, le code ou l'élément du clan une seule fois (ex: "CI", "Didi", "A"). Il est verrouillé dans ce clan pour toute la manche.
*   **Pousser (J'aime) :** Une fois inscrit, tous les taps de l'écran envoyés par ce pseudo sont attribués à son clan. 100 taps = +2 % de jauge.
*   **Booster (Cadeaux) :** Une Rose ajoute un bonus instantané de +5 %. Un cadeau de 10 pièces ou plus déclenche un "Freeze" de 3 secondes sur les jauges adverses.

### 3. Disposition Écran (9:16)
1.  **Haut :** Titre du duel et chronomètre (max 2 minutes).
2.  **Centre :** 2 ou 3 jauges verticales massives, côte à côte, avec la photo ou le drapeau du clan au sommet.
3.  **Bas des jauges :** Pourcentage actuel et vitesse de progression en direct.
4.  **Bas d'écran :** Instructions ultra-courtes ("Écris 1 ou 2 pour choisir, puis tapote l'écran").
5.  **Overlay victoires :** Animation de 5 secondes montrant le clan gagnant et le pseudo du "MVP" (plus grand contributeur).

### 4. Types de Duels et Sélection Régie
*   **Pays :** "Sénégal vs Côte d'Ivoire".
*   **Artistes :** "Didi B vs Himra".
*   **Sujets :** "A: Coupé-Décalé vs B: Afrobeats".  
*   **Sélection régie :** Le fondateur clique sur un bouton prédéfini depuis son téléphone sur l'interface régie web. Des duels pré-configurés s'enchaînent automatiquement, mais il peut forcer un duel spécifique en un tap.

### 5. Rétention et Engagement
*   **Mécanique de Comeback :** Dans les 30 dernières secondes ("Happy Hour"), les points des j'aime sont doublés, permettant des retournements de situation spectaculaires.
*   **Série de Victoires (Streak) :** Si un clan gagne 3 fois d'affilée, la manche suivante devient un "Boss Battle" où les adversaires s'allient temporairement contre lui.
*   **Affichage des Records :** Conservation du score de vitesse le plus rapide de la soirée.

### 6. Risques Majeurs et Solutions
*   **Risque 1 : Friction à l'inscription.** Si le spectateur ne sait pas qu'il doit écrire avant de taper, ses j'aime sont perdus.  
    *Solution :* Flèche visuelle clignotante à l'écran indiquant "Chat d'abord, Tap ensuite". Les j'aime envoyés par des spectateurs non-inscrits sont stockés dans une réserve neutre distribuée équitablement pour ne pas frustrer.
*   **Risque 2 : Déséquilibre d'audience (ex: 80% de supporters ivoiriens).**  
    *Solution :* Algorithme de pondération automatique dans la régie. Si un clan a 3 fois plus de joueurs inscrits, l'impact individuel de ses j'aime est légèrement lissé pour garder du suspense.

### DeepSeek

1. Nom et principe
« POUSSE. » Deux ou trois équipes s'affrontent sur une piste unique ; chaque spectateur rejoint une équipe puis la fait avancer en tapant l'écran (j'aime). La première à la ligne d'arrivée gagne la manche.

2. Choisir son équipe et pousser
- Rejoindre : un seul commentaire avec le numéro de l'équipe (1, 2 ou 3) affiché en gros. Le connecteur rattache le pseudo à cette équipe pour la manche. Une inscription par pseudo, anti-spam 1,5 s, insultes ignorées ; on peut changer d'équipe une fois.
- Pousser : ensuite on tape l'écran, rien d'autre. Les j'aime arrivent par paquets : 40 j'aime = +1 % de piste pour son équipe. Plus on tape, plus ça pousse.
- Cadeau (facultatif, jamais obligatoire) : une rose = petit boost ; un cadeau de 10 pièces ou plus repousse l'équipe de devant. Aucune récompense promise : on peut tout gagner gratuitement en tapant.

3. Ce que l'écran montre (9:16)
- En haut : gros titre « POUSSE » + numéro de manche.
- 2 ou 3 couloirs verticaux, chacun coiffé d'une grande image (drapeau, photo d'artiste, icône de sujet) et d'un gros numéro 1 / 2 / 3.
- Une seule barre de progression : les blocs avancent, le meneur clignote.
- En bas : « TAPE 1 · 2 · 3 POUR REJOINDRE », puis « TAPE POUR POUSSER », avec le compteur de joueurs par équipe.
- Un coin : le meilleur supporter de la manche (pseudo).

4. Les trois duels
- Pays : Togo / Bénin / Ghana (trois drapeaux).
- Artistes : Didi B / Himra.
- Sujets : Coupé-décalé / Afrobeats.
Régie : le fondateur choisit dans un panneau web sur son téléphone (boutons pré-réglés), lance le duel et fixe 2 ou 3 équipes. Un vote éclair peut désigner le prochain duel.

5. Ce qui fait revenir
- Suspense : 20 dernières secondes, photo finish, sprint final.
- Retournement : l'équipe troisième peut « surgir » si un gros cadeau tombe au bon moment.
- Record : record de likes de la saison affiché à l'écran ; meilleur supporter cité (sans lot).

6. Les deux plus grands risques
- TikTok ne dit pas où le spectateur a tapé : on ne peut pas choisir une équipe au geste. D'où le numéro en commentaire, une fois par manche, rappelé à l'écran et par la régie, avec compteur visible pour lever le doute.
- Dérive « pari / argent » ou non-respect des règles TikTok : les likes gratuits suffisent à jouer, les cadeaux restent un soutien facultatif sans gain ni cote, aucun contenu trompeur.

## Tour 2 : critiques, votes et version finale

### Groq

**1. Analyse des propositions concurrentes**

| IA | Points forts par rapport à ma proposition |
|----|-------------------------------------------|
| **Gemini** | • Introduit le **« Comeback »** (doublement des likes dans les 30 s) qui crée un retournement spectaculaire. <br>• Propose un **« Boss Battle »** après 3 victoires consécutives, bon levier de ré‑engagement. |
| **DeepSeek** | • Simplifie l’interface : un seul **numéro d’équipe** affiché en gros, ce qui réduit le risque d’erreur de saisie. <br>• Met l’accent sur un **« bloc de progression unique »** où le meneur clignote, ce qui rend la lecture sur mobile très rapide. |

| IA | Ce qui ne fonctionnerait pas en live |
|----|--------------------------------------|
| **Gemini** | • Le texte d’instruction « Écris 1 ou 2 puis tapote » demande deux actions distinctes ; le spectateur peut oublier la première et perdre ses likes. <br>• Le « Freeze » des jauges adverses nécessite de bloquer visuellement les barres, ce qui alourdit l’animation sur le flux TikTok. |
| **DeepSeek** | • Le système de **redistribution des excédents** n’est pas décrit et pourrait créer de la confusion si les spectateurs voient leurs likes « partir ». <br>• Le « Boost » limité à rose ou cadeau ≥10 coins reste, mais aucune pondération n’est prévue pour éviter qu’une petite communauté ne domine. |
| **Ma proposition (Duel Flash)** | • L’attribution via **hashtag** peut être mal comprise si le présentateur ne les montre pas clairement. <br>• Le comptage des likes « par paquet » dépend de la granularité de TikTok ; si les paquets sont trop gros, la progression peut sembler saccadée. |

**2. Vote**

Je vote pour **la proposition de Gemini**. Elle apporte deux mécaniques très puissantes : le doublement des likes en fin de manche (retournement instantané) et le concept de « Boss Battle » qui crée une continuité narrative d’une soirée à l’autre. Ces leviers d’engagement sont supérieurs aux simples boosts de ma version et restent compatibles avec les règles TikTok tant qu’aucune récompense monétaire n’est promise.

**3. Version finale recommandée (8 points max, < 400 mots)**  

| # | Élément | Description concise |
|---|----------|----------------------|
| 1 | **Nom** | **« Duel Flash »** (conservé pour la reconnaissance). |
| 2 | **Sélection d’équipes** | Le présentateur annonce **2 ou 3 hashtags** (ex. #CI, #GH, #AFRO). Chaque spectateur écrit **une seule fois** le hashtag de son équipe dans le chat ; le backend associe son pseudo à cette équipe pour toute la manche. |
| 3 | **Action principale** | Après l’inscription, **tout like** (ou paquet de likes) envoyé par ce pseudo alimente automatiquement la barre de son équipe ; 40 likes = +1 % de progression. Aucun geste supplémentaire n’est requis. |
| 4 | **Boosts** | • **Rose** : +5 % instantané à l’équipe du donateur. <br>• **Cadeau ≥10 coins** : +5 % et déclenche un **« Double »** pendant les 30 s suivantes (les likes comptent double). |
| 5 | **Affichage 9:16** | • **Haut** : titre « Duel Flash », compte à rebours (max 2 min). <br>• **Centre** : 2‑3 barres verticales très larges, drapeau/icone + pourcentage ; le leader clignote. <br>• **Bas** : top‑3 supporters (pseudo + likes). <br>• **Coin droit** : icône « Boost » qui s’allume lorsqu’un cadeau déclenche le double. |
| 6 | **Retournement** | Dans les **30 s finales**, le multiplicateur « Double » s’applique à tous les likes (pas seulement au donateur) ; cela crée un sprint décisif. |
| 7 | **Évolution narrative** | Si une même équipe gagne **3 manches consécutives**, le round suivant devient un **« Boss Battle »** : les deux équipes adverses s’allient (leurs barres fusionnent) contre le champion, augmentant le suspense sans introduire de pari. |
| 8 | **Sécurité TikTok** | Aucun gain monétaire n’est promis. Les boosts sont purement visuels (« Boost », « Double »). Les likes gratuits suffisent à gagner. Anti‑spam : un pseudo ne peut changer d’équipe qu’une fois toutes les 30 s et ne peut envoyer plus de 5 paquets de likes sans pause d’1 s (déjà géré par TikTok). |

Cette version combine : la **simplicité d’inscription** de DeepSeek, le **doublement en fin de manche** et le **Boss Battle** de Gemini, ainsi que la **lisibilité** et le **design épuré** de ma proposition. Le jeu reste lisible en une seconde, ne nécessite qu’un seul geste (like) après l’inscription, et offre des moments de retournement et de narration qui incitent les spectateurs à revenir chaque « Nuit Cauri Charts ».

### Gemini

### 1. Analyse des propositions adverses

**Groq :**
*   **Meilleur :** Utilisation de hashtags (#CI, #GH) très naturelle sur TikTok.
*   **Impracticable :** La limitation de changement d'équipe toutes les 30s et la redistribution des excédents de likes aux équipes adverses complexifient inutilement la régie et troublent la compréhension.

**DeepSeek :**
*   **Meilleur :** Simplicité extrême des commandes ("Écris 1, 2 ou 3") et clarification explicite sur l'absence d'obligation d'achat.
*   **Impracticable :** Permettre de changer d'équipe en cours de manche crée de la confusion et nuit au sentiment d'appartenance à un clan.

### 2. Vote
Je vote pour la proposition de **DeepSeek**. Sa simplicité d'inscription (1, 2 ou 3) est la plus efficace pour convertir un spectateur passif en joueur instantané sur mobile.

---

### 3. Synthèse FINALE Recommandée : « CLAN WARS »

1.  **Principe :** Duel vertical en 2 ou 3 colonnes (1 à 3 minutes). La première équipe qui remplit sa jauge ou domine au chrono gagne. 100% gratuit et équitable.
2.  **Inscription (1 seconde) :** Le spectateur commente uniquement **1**, **2** ou **3** dans le chat. Son pseudo est verrouillé dans cette équipe pour la manche.
3.  **Action principale (Tap) :** Une fois inscrit, le spectateur tapote son écran. Tous ses likes accumulés poussent la jauge de son équipe (ex: 40 likes = +1% de jauge).
4.  **Boosts facultatifs :** Une Rose offre un léger boost visuel (+5%). Un cadeau de ≥10 pièces applique un court Freeze de 3s sur la jauge adverse. Aucun lot ni argent à gagner.
5.  **Interface Écran 9:16 :**
    *   *Haut :* Chrono + Titre du duel.
    *   *Centre :* 2 ou 3 jauges géantes avec visuels (drapeaux, artistes) et chiffres **1 / 2 / 3** massifs.
    *   *Bas :* Consigne ultra-courte : *« Écris 1, 2 ou 3 puis tapote l'écran ! »*.
6.  **Variété des Duels :**
    *   *Pays :* Togo vs Bénin vs CI.
    *   *Artistes :* Didi B vs Himra.
    *   *Sujets :* Coupé-Décalé vs Afrobeats.
7.  **Régie Mobile :** Le fondateur lance les duels pré-configurés en 1 tap depuis son téléphone. Un algorithme lisse automatiquement l'impact des likes si une équipe est en sur-nombre.
8.  **Rétention & Fin de manche :** Écran de victoire de 5s célébrant le clan gagnant et le pseudo du "MVP" (plus grand tapeur). Mode "Sprint Final" dans les 20 dernières secondes où les points des likes sont doublés.

### DeepSeek

1) Groq
Meilleur que chez moi : jauges verticales avec compteur de likes par équipe, plafond de gain par paquet, indicateur de boost très lisible.
Ne marcherait pas en vrai live : les hashtags multiples sont plus lents à comprendre qu’un simple numéro ; la sélection automatique d’artistes/tendances n’est pas pilotable seul en direct ; la redistribution des excédents et les mini-défis sont opaques et ajoutent du texte.

2) Gemini
Meilleur que chez moi : l’onboarding « chat d’abord, tap ensuite », l’écran MVP, les duels préconfigurés et le sprint final.
Ne marcherait pas en vrai live : le Freeze de 3 secondes est punitif et difficile à expliquer ; la pondération automatique selon l’audience est opaque, voire suspecte ; la réserve neutre des non-inscrits peut sembler fausser le jeu.

3) Mon vote : « POUSSE. »
Je garde ma proposition car elle est la plus simple à comprendre en une seconde et la plus sûre côté règles TikTok : inscription par numéro, puis likes gratuits. J’y intègre les jauges verticales de Groq et l’onboarding/MVP de Gemini.

4) Version finale recommandée
1. Nom et principe : « POUSSE. » Deux ou trois équipes, jauges verticales, manche de 60 à 120 secondes. Première jauge au sommet, ou meneuse au chrono, gagne.
2. Rejoindre : un seul commentaire « 1 », « 2 » ou « 3 », numéros affichés en gros. Le pseudo est verrouillé pour la manche ; changement autorisé une fois. Anti-spam 1,5 s, insultes ignorées.
3. Pousser : ensuite, le spectateur tape l’écran. 40 likes = +1 % ; plafond de +3 % par paquet pour éviter l’écrasement. Dernières 20 secondes : gains +50 %, affiché « SPRINT FINAL ».
4. Cadeaux : rose = petit boost visuel ; cadeau de 10 pièces ou plus = pousse légèrement l’équipe du donateur. Aucun gain promis, tout se joue gratuitement.
5. Écran 9:16 : titre + chrono ; 2 ou 3 jauges verticales avec grande image et gros numéro ; compteur de joueurs par équipe ; meneur clignotant ; en bas « TAPE 1 2 3 POUR REJOINDRE », puis « TAPE POUR POUSSER » ; coin MVP.
6. Régie : panneau web sur téléphone avec boutons pré-réglés Pays / Artistes / Sujets, choix 2 ou 3 équipes, durée, reset. Pas d’algorithme automatique.
7. Fin de manche : écran gagnant + pseudo MVP, 14 s, puis manche suivante.
8. Garde-fous : jamais de choix d’équipe par zone de l’écran ; pas de pari, cote ni récompense contre cadeau ; plafonds et compteurs visibles pour éviter les dérives.

