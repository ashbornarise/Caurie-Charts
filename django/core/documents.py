"""Documents publics (PDF illustrés) : une page par document avec l'aperçu de chaque page, le texte lisible par les moteurs
de recherche, les données structurées schema.org et le téléchargement. Fichiers dans public/documents (servis tels quels)."""
from core.helpers import url

# Les magazines sont fabriqués par outils/magazine/fabriquer.py : une fiche par numéro dans core/data/magazines.
DOCUMENTS = [
    {
        "slug": "le-voyage-d-un-titre",
        "categorie": "Comprendre",
        "fichier": "cauri-charts-le-voyage-d-un-titre",
        "date": "2026-11-28",
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
            ("Le calcul", "Chaque place dans les tops des plateformes du pays (Spotify, Apple Music, Boomplay, Deezer, Shazam) devient "
             "une part d'écoute ; Spotify compte double. Les vues du clip officiel YouTube s'y ajoutent, avec moins de poids là où les "
             "écoutes sont bien mesurées. Le N°1 vaut 100 (indice Cauri), les autres en proportion. Un tube vu seulement sur YouTube "
             "compte aussi, avec un poids réduit (depuis le 27 novembre 2026)."),
            ("Le classement", "Six classements : Prime, Buzz, Fresh, Icon, Legend et Afrique de l'Ouest. Trois titres au plus par artiste "
             "dans chaque top ; un titre de plus d'un an sort, sauf vrai regain ; un titre vu seulement sur YouTube entre avec un poids réduit."),
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
        "categorie": "Comprendre",
        "fichier": "cauri-charts-comprendre-nos-classements",
        "date": "2026-11-28",
        "pages": 2,
        "titre": "Comprendre nos classements",
        "sous_titre": "Comment Cauri Charts collecte, vérifie et classe les titres en Afrique de l'Ouest, et ses perspectives",
        "description": "Le parcours d'un titre en cinq étapes, le score (écoutes et vues pesées pays par pays, indice Cauri de 0 à 100), la semaine du vendredi au jeudi, "
                       "les règles du classement, les six classements, la note de fiabilité et les perspectives de Cauri Charts.",
        "format": "PDF · A3 paysage · 2 pages",
        "sections": [
            ("Le parcours d'un titre", "On relève chaque nuit, on range (un titre = son clip officiel), on vérifie, on calcule, puis on publie "
             "chaque vendredi soir."),
            ("Le score d'un titre", "Chaque place dans les tops des plateformes du pays devient une part d'écoute (Spotify compte double) ; "
             "les vues du clip officiel YouTube s'y ajoutent. Le N°1 vaut 100, les autres en proportion. Un tube vu seulement sur YouTube "
             "entre aussi, avec un poids réduit."),
            ("Les règles", "8 artistes suivis au minimum pour qu'un pays ait son classement, seulement les artistes du pays, 3 titres au plus "
             "par artiste, et un tube vu seulement sur YouTube entre avec un poids réduit."),
            ("Nos classements", "Prime, Buzz, Fresh, Icon, Legend et le Top Afrique de l'Ouest, avec une note de fiabilité sur chaque classement."),
            ("Nos perspectives", "La Nuit Cauri Charts, « Pourquoi ce rang ? », Audiomack et TikTok, la radio et la télévision avec nos partenaires."),
        ],
    },
]


def _complet(d: dict) -> dict:
    base = "documents/apercus/" + d["fichier"]
    return {**d, "date_fr": date_fr(d["date"]), "url": url("documents/" + d["slug"]), "pdf": url("documents/" + d["fichier"] + ".pdf"),
            "images": [url(f"{base}/page-{i:02d}.jpg") for i in range(1, d["pages"] + 1)]}


CATEGORIES = ["Magazines", "Comprendre"]


def date_fr(d: str) -> str:
    mois = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    a, m, j = d[:10].split("-")
    return f"{int(j)} {mois[int(m) - 1]} {a}"


def _magazines() -> list:
    """Les numéros fabriqués par outils/magazine/fabriquer.py (une fiche JSON par numéro), du plus récent au plus ancien."""
    import json as _json
    import os
    dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "magazines")
    out = []
    if os.path.isdir(dossier):
        for f in os.listdir(dossier):
            if f.endswith(".json"):
                with open(os.path.join(dossier, f), encoding="utf-8") as fh:
                    m = _json.load(fh)
                PLUS.setdefault(m["slug"], m.pop("plus", {}))
                m.pop("plus", None)
                out.append(m)
    return sorted(out, key=lambda m: m["date"], reverse=True)


def _liste() -> list:
    vus = {d["slug"] for d in DOCUMENTS}
    nouveaux = [m for m in _magazines() if m["slug"] not in vus]
    return nouveaux + DOCUMENTS


def tous() -> list:
    return [_complet(d) for d in _liste()]


def par_slug(slug: str) -> dict | None:
    d = next((_complet(d) for d in _liste() if d["slug"] == slug), None)
    return enrichi(d) if d else None


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


# 15/11/2026 : sommaire visuel (« Dans ce numéro »), tuiles de chiffres clés et accroche de la couverture
ICONES = {
    "trophee": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.7V17c0 .6-.5 1-1 1.2C7.9 18.8 7 20.2 7 22M14 14.7V17c0 .6.5 1 1 1.2 1.1.6 2 2 2 3.8M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 4 10 15 15 0 0 1-4 10 15 15 0 0 1-4-10 15 15 0 0 1 4-10z"/>',
    "note": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "calc": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M8 6h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15h.01M8 19h8"/>',
    "route": '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
    "horloge": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "couches": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
}
PLUS = {
    "le-voyage-d-un-titre": {
        "taille": "7 Mo", "coupe": ("Le voyage", "d'un titre"), "badge": "Guide illustré", "accroche": ("Le guide", "du clic au classement"),
        "tuiles": [("route", "9 étapes", "du clic au classement"), ("couches", "6 plateformes", "relevées"),
                   ("calc", "Indice 0-100", "le N°1 vaut 100"), ("horloge", "Vendredi 19 h", "publication automatique")],
        "chapitres": [("Couverture", "le départ", 1, 1, ""), ("Les sources", "six plateformes", 2, 2, ""), ("La nuit", "les relevés", 3, 3, ""),
                      ("Le tri", "un titre = son clip officiel", 4, 4, ""), ("La vérification", "les alertes", 5, 5, ""),
                      ("Le calcul", "écoutes et vues, pays par pays", 6, 6, ""), ("Le classement", "règles et six classements", 7, 7, ""),
                      ("La publication", "vendredi soir", 8, 8, ""), ("La carte", "pays et fiabilité", 9, 9, ""), ("L'horizon", "nos perspectives", 10, 10, "")],
    },
    "comprendre-nos-classements": {
        "taille": "4,5 Mo", "coupe": ("Comprendre", "nos classements"), "badge": "Guide express", "accroche": ("En 2 pages", "la méthode en clair"),
        "tuiles": [("route", "5 étapes", "le parcours d'un titre"), ("calc", "Indice 0-100", "écoutes et vues"),
                   ("trophee", "6 classements", "Prime, Buzz, Fresh…"), ("globe", "13 pays", "classés")],
        "chapitres": [("La méthode, en clair", "parcours, score, semaine", 1, 1, ""), ("Règles et perspectives", "classements, pays, la suite", 2, 2, "")],
    },
}


def enrichi(d: dict) -> dict:
    from markupsafe import Markup
    plus = PLUS.get(d["slug"], {})
    chap = [{"titre": t, "sous": s_, "debut": a, "fin": b, "drapeau": url(f"assets/img/flags/{c}.svg") if c else "",
             "image": d["images"][a - 1], "pages": f"p. {a}" if a == b else f"p. {a}–{b}", "couleur": k % 9}
            for k, (t, s_, a, b, c) in enumerate(plus.get("chapitres", []))]
    tuiles = [{"svg": Markup(f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONES[i]}</svg>'),
               "grand": g, "petit": p_} for i, g, p_ in plus.get("tuiles", [])]
    import json as _json
    debut, fin = plus.get("coupe", (d["titre"], ""))
    reperes = Markup(_json.dumps([[c["debut"], c["fin"], c["titre"]] for c in chap], ensure_ascii=False).replace("</", "<\\/"))
    return {**d, "titre_debut": debut, "titre_fin": fin, "sections_json": reperes, "taille": plus.get("taille", ""), "badge": plus.get("badge", d.get("categorie", "")), "accroche": plus.get("accroche"),
            "chapitres": chap, "tuiles": tuiles}
