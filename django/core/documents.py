"""Documents publics (PDF illustrés) : une page par document avec l'aperçu de chaque page, le texte lisible par les moteurs
de recherche, les données structurées schema.org et le téléchargement. Fichiers dans public/documents (servis tels quels)."""
from core.helpers import url

DOCUMENTS = [
    {
        "slug": "cauri-charts-magazine-n46",
        "fichier": "cauri-charts-magazine-n46",
        "date": "2026-11-14",
        "pages": 33,
        "titre": "Cauri Charts Magazine N°46",
        "sous_titre": "Tous les classements officiels de la semaine du 9 au 12 novembre 2026",
        "description": "Le premier Cauri Charts Magazine, avec Ayra Starr et ZAYN en couverture : le Top 20 Afrique de l'Ouest (N°1 : Heaven Baby d'Ayra Starr feat. ZAYN), les classements complets de 13 pays avec les N°1, les entrées et les mouvements, et les six classements par genre.",
        "format": "PDF · A3 paysage · 33 pages",
        "legendes": ['Couverture : Ayra Starr et ZAYN, Heaven Baby', 'Les N°1 de la semaine', "Ouverture : Afrique de l'Ouest (Ayra Starr)", "Top 20 Afrique de l'Ouest", 'Ouverture : Togo', 'Top Togo', 'Ouverture : Nigeria', 'Top Nigeria', "Ouverture : Côte d'Ivoire", "Top Côte d'Ivoire", 'Ouverture : Ghana', 'Top Ghana', 'Ouverture : Sénégal', 'Top Sénégal', 'Ouverture : Bénin', 'Top Bénin', 'Ouverture : Burkina Faso', 'Top Burkina Faso', 'Ouverture : Mali', 'Top Mali', 'Ouverture : Guinée', 'Top Guinée', 'Ouverture : Sierra Leone', 'Top Sierra Leone', 'Ouverture : Cap-Vert', 'Top Cap-Vert', 'Ouverture : Guinée-Bissau', 'Top Guinée-Bissau', 'Ouverture : Mauritanie', 'Top Mauritanie', 'Ouverture : par genre', 'Classements par genre', 'Comment on calcule'],
        "sections": [
            [
                "Top 20 Afrique de l'Ouest (les 10 premiers)",
                "1. Heaven Baby (feat. ZAYN) (Ayra Starr), 2. Go Hard or Go Home (Chief Priest), 3. SLICK (Victony), 4. Rush (Ayra Starr), 5. Oh No (Rema), 6. Great Change (Nsesaeɛ Kɛseɛ) (Piesie Esther), 7. Djelykaba Bintou Feat. Viviane Chidid - (Djelykaba Bintou), 8. Dugi-dugi (AMADEUS), 9. Namm nama la (AMADEUS), 10. Raay (Momo Dieng)"
            ],
            [
                "Top Togo",
                "1. Migbo (Remix) (sethlo), 2. DESTIN (Joachin Migos), 3. Tout ira mieux (Faut pas m'appeler) (Paki Chenzu), 4. BELIEVE (Paki Chenzu), 5. M'gbabidjio (Santrinos Raphaël)"
            ],
            [
                "Top Nigeria",
                "1. Heaven Baby (feat. ZAYN) (Ayra Starr), 2. Gratitude (Asake), 3. BABA ft. Zlatan (HOTKEED), 4. Forgiveness (Asake), 5. Oh No (Rema)"
            ],
            [
                "Top Côte d'Ivoire",
                "1. TAPER CREER (feat. Gazo) (Himra), 2. ADIOS (Didi B), 3. C'EST PAS DE MA FAUTE (Himra), 4. PARTY (Didi B), 5. PLUS DE LOVE (Himra)"
            ],
            [
                "Top Ghana",
                "1. Faith (Kweku Smoke), 2. Bombele (Kweku Smoke), 3. Bra (Kweku Smoke), 4. Gen Z (Fameye), 5. Sorry I'm Different (Miracle LRE)"
            ],
            [
                "Top Sénégal",
                "1. Dugi-dugi (AMADEUS), 2. Namm nama la (AMADEUS), 3. Raay (Momo Dieng), 4. Nous 2 (feat. Wally B. Seck) (Viviane Chidid), 5. Naataango (AMADEUS)"
            ],
            [
                "Top Bénin",
                "1. Dans La Poussiere (Axel Merryl), 2. Chérie agonkè (First King), 3. Fité (VANO BABY), 4. Je suis béni (First King), 5. Bandit (VANO BABY)"
            ],
            [
                "Top Burkina Faso",
                "1. Velar (Babi Tape), 2. Vis ton Viim (AMZY), 3. Ya maam (AMZY), 4. Weedo (Floby), 5. Ouaga zeune (Floby)"
            ],
            [
                "Top Mali",
                "1. Dali (Seydou Chée), 2. IBN (Malakey), 3. I Ban Ban (Momo Choco), 4. Président (Yacou B OG), 5. Business classe (Seydou Chée)"
            ],
            [
                "Top Guinée",
                "1. Fidjou (SAIFOND), 2. IYE (SAIFOND), 3. LABADHO (SAIFOND), 4. Fulah Me Yes (Wandjan dimedi), 5. Djelykaba Bintou Feat. Viviane Chidid - (Djelykaba Bintou)"
            ],
            [
                "Top Sierra Leone",
                "1. Scatter (Bakitenno), 2. Crush (feat. JZyNO) (INCREDIBLE JJ), 3. GO (Drizilik), 4. Sabi Road (Drizilik), 5. No Games (Drizilik)"
            ],
            [
                "Top Cap-Vert",
                "1. ERRO & ACERTO (Loose jr), 2. Passada (Garry), 3. Vou Ser Teu (feat. Landrick) (Loony Johnson), 4. Kumpanhero (Dynamo), 5. Obrigado (Helio Batalha)"
            ],
            [
                "Top Guinée-Bissau",
                "1. Mistin (As One 1820), 2. MON CHÉRI [2026] (Yasmine), 3. Ley Dy Byda (Justino Delgado), 4. Chatice (As One 1820), 5. SORRISO DE LUZ DE SOL (Chito Kaharam)"
            ],
            [
                "Top Mauritanie",
                "1. Mbiida Yonaani (feat. Sidi Eleya) (Bab's OG), 2. Welema (Bab's OG), 3. Ko Ni'i (BRMX), 4. Somi Dani (feat. Sidi Eleya) (Bab's OG), 5. Hollam (feat. Ceepee) (BRMX)"
            ],
            [
                "Classements par genre",
                "Top Rap, Top Mbalax, Top Afrobeats, Top R&B, Top Gospel et Top Coupé-décalé & Zouglou, sur toute l'Afrique de l'Ouest."
            ]
        ]
    },
    {
        "slug": "le-voyage-d-un-titre",
        "fichier": "cauri-charts-le-voyage-d-un-titre",
        "date": "2026-11-14",
        "pages": 10,
        "titre": "Le voyage d'un titre",
        "sous_titre": "Du premier clic au classement du vendredi soir : la méthode Cauri Charts en 9 étapes illustrées",
        "description": "Comment une chanson écoutée à Lomé, Lagos ou Abidjan devient une place dans les classements Cauri Charts : "
                       "sources, relevés de nuit, tri, vérification, calcul, classement, publication, carte des pays et perspectives.",
        "format": "PDF · A3 paysage · 10 pages",
        "sections": [
            ("Les sources", "Six plateformes relevées dans 16 pays d'Afrique de l'Ouest : YouTube (vues des clips officiels, chaque jour), "
             "Spotify (écoutes de chaque titre, chaque semaine), Apple Music (Top 100 par pays, chaque jour), Boomplay (Top 100 par pays, "
             "chaque semaine), Deezer (contrôle croisé) et Shazam (découverte de titres)."),
            ("La nuit", "Chaque nuit vers 1 h GMT, les relevés démarrent : tops des plateformes, rapprochement de chaque ligne avec un titre "
             "connu, vues YouTube des clips officiels, calcul des scores de la semaine et mise à jour du classement en direct."),
            ("Le tri", "Les mentions comme « Official Video » ou « Lyrics » sont retirées, seul le clip officiel compte (pas les reprises ni "
             "les chaînes « Topic »), les doublons sont fusionnés chaque dimanche et le pays de chaque artiste est vérifié sur Google."),
            ("La vérification", "Un chiffre inhabituel déclenche une alerte : pic soudain, rapport j'aime / vues anormal, moins de 10 000 vues "
             "ou progression négative. Avant publication, les titres en alerte sont vérifiés par une recherche Google."),
            ("Le calcul", "Le score d'un titre est fait pour moitié des vues YouTube gagnées dans la semaine et pour moitié des écoutes, "
             "partagées à parts égales entre Spotify, Apple Music et Boomplay. Une plateforme absente d'un pays laisse sa part aux autres."),
            ("Le classement", "Six classements : Prime, Buzz, Fresh, Icon, Legend et Afrique de l'Ouest. Pour le Top 5, un titre doit être vu "
             "sur au moins deux plateformes ; trois titres au plus par artiste dans chaque top."),
            ("La publication", "La semaine va du vendredi au jeudi ; le classement sort automatiquement chaque vendredi à 19 h GMT sur le site, "
             "Instagram, Facebook, TikTok, Telegram et la newsletter. Un classement publié n'est jamais recalculé en silence."),
            ("La carte et la confiance", "13 pays ont un classement officiel chaque semaine ; chaque classement affiche une note de fiabilité "
             "sur 100 qui dit combien de données on a pour le pays, pas si sa musique est bonne."),
            ("L'horizon", "La Nuit Cauri Charts en direct sur TikTok, le détail « Pourquoi ce rang ? » sur chaque titre, Audiomack et TikTok "
             "à brancher, la radio et la télévision avec nos partenaires en 2027."),
        ],
    },
    {
        "slug": "comprendre-nos-classements",
        "fichier": "cauri-charts-comprendre-nos-classements",
        "date": "2026-11-14",
        "pages": 2,
        "titre": "Comprendre nos classements",
        "sous_titre": "Comment Cauri Charts collecte, vérifie et classe les titres en Afrique de l'Ouest, et ses perspectives",
        "description": "Le parcours d'un titre en cinq étapes, le score moitié YouTube moitié écoutes, la semaine du vendredi au jeudi, "
                       "les règles du classement, les six classements, la note de fiabilité et les perspectives de Cauri Charts.",
        "format": "PDF · A3 paysage · 2 pages",
        "sections": [
            ("Le parcours d'un titre", "On relève chaque nuit, on range (un titre = son clip officiel), on vérifie, on calcule, puis on publie "
             "chaque vendredi soir."),
            ("Le score d'un titre", "50 % pour les vues YouTube gagnées dans la semaine, 50 % pour les écoutes sur Spotify, Apple Music et "
             "Boomplay à parts égales."),
            ("Les règles", "8 artistes suivis au minimum pour qu'un pays ait son classement, seulement les artistes du pays, 3 titres au plus "
             "par artiste, 2 sources pour entrer dans le Top 5."),
            ("Nos classements", "Prime, Buzz, Fresh, Icon, Legend et le Top Afrique de l'Ouest, avec une note de fiabilité sur chaque classement."),
            ("Nos perspectives", "La Nuit Cauri Charts, « Pourquoi ce rang ? », Audiomack et TikTok, la radio et la télévision avec nos partenaires."),
        ],
    },
]


def _complet(d: dict) -> dict:
    base = "documents/apercus/" + d["fichier"]
    return {**d, "url": url("documents/" + d["slug"]), "pdf": url("documents/" + d["fichier"] + ".pdf"),
            "images": [url(f"{base}/page-{i:02d}.jpg") for i in range(1, d["pages"] + 1)]}


def tous() -> list:
    return [_complet(d) for d in DOCUMENTS]


def par_slug(slug: str) -> dict | None:
    return next((_complet(d) for d in DOCUMENTS if d["slug"] == slug), None)


def ld(d: dict) -> dict:
    """Données structurées : un document numérique, son PDF et ses pages en images."""
    return {"@type": "DigitalDocument", "@id": d["url"] + "#document", "name": d["titre"] + " · Cauri Charts",
            "headline": d["titre"], "description": d["description"], "url": d["url"], "inLanguage": "fr",
            "datePublished": d["date"], "dateModified": d["date"], "numberOfPages": d["pages"],
            "image": d["images"], "thumbnailUrl": d["images"][0],
            "encoding": {"@type": "MediaObject", "contentUrl": d["pdf"], "encodingFormat": "application/pdf"},
            "keywords": "Cauri Charts, classement musical, Afrique de l'Ouest, musique ouest-africaine, méthodologie",
            "about": {"@type": "Thing", "name": "Classements musicaux de l'Afrique de l'Ouest"},
            "author": {"@id": url("/") + "#organisation"}, "publisher": {"@id": url("/") + "#organisation"}}
