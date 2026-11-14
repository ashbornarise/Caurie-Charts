"""Documents publics (PDF illustrés) : une page par document avec l'aperçu de chaque page, le texte lisible par les moteurs
de recherche, les données structurées schema.org et le téléchargement. Fichiers dans public/documents (servis tels quels)."""
from core.helpers import url

DOCUMENTS = [
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
