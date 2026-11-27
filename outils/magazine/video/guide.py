"""Vidéo « Le guide Cauri Charts » : la méthode (Le voyage d'un titre) puis le magazine N°46, mascotte qui touche les points."""
import json, os, re, subprocess, sys

sys.path.insert(0, r"c:/Users/agbal/OneDrive/Documents/GitHub/Caurie-Charts/django")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cauri.settings")
import django  # noqa: E402
django.setup()
from core import db  # noqa: E402
from core.services.social import raconte_v2 as R2, refrain as RF  # noqa: E402

PUB = "C:/Users/agbal/Studio-AV/remotion/public/guide/"
ICI = os.path.dirname(os.path.abspath(__file__))
W, H = 4129, 2920

# phonétique : même nombre de mots que le texte affiché (les sous-titres reprennent le texte écrit)
DIT = {"Sethlo": "Sètlo", "Ayra": "Aïra", "Starr": "Star", "Zayn": "Zèïne", "Kweku": "Kwékou", "Amadeus": "Amadéousse",
       "Boomplay": "Boumplé", "Deezer": "Dizeur", "Spotify": "Spotifaï", "Prime": "Praïme", "Buzz": "Beuz", "Fresh": "Frèche",
       "Icon": "Aïkone", "Legend": "Lédjeunde", "mbalax": "mbalakh", "R&B": "érène-bi", "GMT": "gé-èm-té", "Lagos": "Lagosse",
       "Remix": "Rimix", "Heaven": "Hèveune", "Baby": "Bébi", "Faith": "Féïth", "Didi": "Didi", "Migbo": "Migbo",
       "cauricharts": "Cauri-Charts", "afrobeats": "afrobits"}

# (texte affiché, page, caméra de, caméra à, pose de départ, carte, [(moment 0-1, x, y)])
PRISES = [
    [
        ("[enthousiaste] Salut, c'est le guide de Cauri Charts ! Tu t'es déjà demandé comment une chanson écoutée à Lomé, Lagos ou Abidjan finit dans nos classements ? Suis-moi, je t'explique tout.",
         "v1", (0.30, 0.42, 0.78), (0.42, 0.5, 1.0), "m-marche.png", ("9 étapes", "du clic au classement"), [(0.55, 0.30, 0.40)]),
        ("Tout part des plateformes. YouTube pour les vues des clips officiels. Spotify, Apple Music et Boomplay pour les écoutes. Deezer et Shazam nous aident à vérifier.",
         "v2", (0.67, 0.49, 0.95), (0.70, 0.45, 0.72), "m1-question.png", ("6", "plateformes relevées"), [(0.12, 0.671, 0.256), (0.42, 0.838, 0.49), (0.8, 0.84, 0.15)]),
        ("Chaque nuit, pendant que tu dors, nos robots relèvent les chiffres : près de onze mille huit cents clips officiels, chaque jour !",
         "v3", (0.5, 0.4, 1.0), (0.5, 0.52, 0.82), "m-assis.png", ("≈ 11 800", "clips officiels relevés chaque jour"), [(0.15, 0.5, 0.106), (0.7, 0.5, 0.6)]),
        ("Ensuite, on fait le tri. Un titre, c'est son clip officiel : les reprises, les doublons et les fausses versions, on les écarte.",
         "v4", (0.28, 0.5, 0.78), (0.62, 0.5, 0.78), "m1-question.png", ("1 titre", "= son clip officiel"), [(0.2, 0.17, 0.42), (0.65, 0.686, 0.431)]),
        ("Un chiffre bizarre ? Alerte ! On vérifie sur Google avant de publier. Mais attention : une alerte, ce n'est pas une accusation.",
         "v5", (0.45, 0.48, 0.78), (0.76, 0.4, 0.62), "m-loupe.png", ("Alerte", "puis vérification sur Google"), [(0.18, 0.417, 0.337), (0.72, 0.66, 0.38)]),
        ("Le calcul est simple : moitié vues YouTube, moitié écoutes. Et si une plateforme n'existe pas dans un pays, sa part revient aux autres.",
         "v6", (0.5, 0.5, 1.0), (0.5, 0.55, 0.78), "m1-question.png", ("50 / 50", "vues YouTube · écoutes"), [(0.25, 0.262, 0.5), (0.5, 0.738, 0.5)]),
        ("Puis on classe : Prime, Buzz, Fresh, Icon, Legend et Afrique de l'Ouest. Trois titres maximum par artiste, et deux sources pour entrer dans le Top 5.",
         "v7", (0.35, 0.55, 0.9), (0.78, 0.4, 0.78), "m3-surpris.png", ("6", "classements chaque semaine"), [(0.2, 0.36, 0.72), (0.75, 0.74, 0.25)]),
        ("Et chaque vendredi à dix-neuf heures GMT, le classement sort tout seul, sur le site et sur nos réseaux.",
         "v8", (0.48, 0.54, 0.62), (0.48, 0.5, 0.95), "m4-appel.png", ("VEN 19 h", "GMT, automatiquement"), [(0.35, 0.488, 0.539)]),
    ],
    [
        ("[enthousiaste] Et justement, voici le tout premier Cauri Charts Magazine ! Le numéro quarante-six, du 9 au 12 novembre.",
         "m1", (0.3, 0.45, 0.95), (0.62, 0.42, 0.9), "m3-surpris.png", ("N°46", "du 9 au 12 novembre 2026"), [(0.5, 0.09, 0.49), (0.85, 0.66, 0.35)]),
        ("Numéro un en Afrique de l'Ouest : Heaven Baby, d'Ayra Starr avec Zayn ! Écoute ça.",
         "m3", (0.22, 0.42, 0.78), (0.2, 0.42, 0.62), "m2-presente.png", ("N°1", "Afrique de l'Ouest"), [(0.35, 0.167, 0.33)]),
    ],
    [
        ("[enthousiaste] Pays par pays, voici les numéros un. Au Togo, Migbo Remix de Sethlo. En Côte d'Ivoire, Taper Créer de Himra avec Gazo. Au Ghana, Faith de Kweku Smoke. Et au Sénégal, Dugi-dugi d'Amadeus.",
         "m2", (0.27, 0.55, 0.56), (0.76, 0.55, 0.56), "m2-presente.png", ("13", "pays classés cette semaine"),
         [(0.13, 0.11, 0.42), (0.38, 0.38, 0.42), (0.62, 0.51, 0.42), (0.84, 0.64, 0.42)]),
        ("Et dans chaque page, tout le classement : qui monte, qui descend, qui débarque. En Côte d'Ivoire, Didi B place trois titres dans le Top 10 !",
         "m6", (0.25, 0.45, 0.78), (0.6, 0.42, 0.78), "m-loupe.png", ("3 titres", "de Didi B dans le Top 10 ivoirien"), [(0.35, 0.405, 0.128), (0.75, 0.405, 0.515)]),
        ("Il y a aussi les classements par genre : rap, mbalax, afrobeats, R&B, gospel et coupé-décalé.",
         "m17", (0.5, 0.55, 0.92), (0.45, 0.5, 0.72), "m1-question.png", ("6", "classements par genre"), [(0.3, 0.19, 0.27), (0.65, 0.5, 0.27)]),
        ("Le magazine complet est gratuit, en PDF, sur cauricharts point com. Et toi, c'est quoi ton numéro un de la semaine ? Dis-le en commentaire !",
         "m18", (0.3, 0.5, 0.9), (0.72, 0.5, 0.78), "m4-appel.png", ("PDF gratuit", "cauricharts.com/documents"), [(0.45, 0.76, 0.34)]),
    ],
]


def mots(t):
    return [m for m in re.sub(r"\[[^\]]*\]", " ", t).split() if any(c.isalnum() for c in m)]


def dit(t):
    for a, b in DIT.items():
        t = re.sub(rf"(?<![\w-]){re.escape(a)}(?![\w-])", b, t)
    return t


def propre(m):
    return m.strip(".,;:!?«»")


def main():
    segs, sous, voix, t0 = [], [], [], 0.7
    extrait = None
    for k, prise in enumerate(PRISES):
        texte = " ".join(s[0] for s in prise)
        out = PUB + f"voix{k + 1}.mp3"
        cache = ICI + f"/voix{k + 1}.json"
        if os.path.exists(cache) and json.load(open(cache, encoding="utf-8"))["texte"] == texte and os.path.exists(out):
            ms = json.load(open(cache, encoding="utf-8"))["mots"]
        else:
            ms = R2.dit(dit(texte), out)
            json.dump({"texte": texte, "mots": ms}, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
        affiches = [propre(m) for s in prise for m in mots(s[0])]
        if len(affiches) != len(ms):
            print("ATTENTION nombre de mots", k, len(affiches), len(ms))
        duree = R2._duree(out)
        voix.append({"src": f"guide/voix{k + 1}.mp3", "d": round(t0, 2)})
        i = 0
        bornes = []
        for s in prise:
            n = len(mots(s[0]))
            bornes.append(t0 + ms[i]["d"] - 0.12 if i < len(ms) else t0)
            i += n
        fin_prise = t0 + duree
        for j, s in enumerate(prise):
            d = bornes[j] if j else t0 - (0.7 if k == 0 else 0.35)
            f = bornes[j + 1] if j + 1 < len(prise) else fin_prise + 0.25
            segs.append({"d": round(max(0, d), 2), "f": round(f, 2), "page": f"guide/{s[1]}.jpg", "W": W, "H": H, "de": s[2], "a": s[3],
                         "pose": f"{'raconte' if s[4].startswith('m') and s[4][1].isdigit() else 'guide'}/{s[4]}",
                         "carte": {"grand": s[5][0], "petit": s[5][1]}, "touches": [{"t": x[0], "x": x[1], "y": x[2]} for x in s[6]],
                         "etiquette": "LE VOYAGE D'UN TITRE" if k == 0 else "CAURI CHARTS MAGAZINE N°46"})
        for a, m in zip(affiches, ms):
            sous.append({"m": a, "d": round(t0 + m["d"], 3), "f": round(t0 + m["f"], 3)})
        t0 = fin_prise + 0.3
        if k == 1:   # l'extrait du N°1 Afrique de l'Ouest, au refrain
            tid = db.value("SELECT id FROM tracks WHERE slug = ?", ["ayra-starr-heaven-baby-feat-zayn"])
            c = RF.clip_officiel(int(tid)) if tid else None
            clip = RF.telecharge(c["external_id"], ICI) if c else None
            if not clip:
                raise SystemExit("clip de Heaven Baby introuvable (YouTube)")
            r0, _ = RF.refrain(clip)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{r0:.2f}", "-i", clip, "-t", "9.5", "-vf", "scale=-2:1080",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", PUB + "extrait.mp4"], check=True)
            extrait = {"d": round(t0, 2), "f": round(t0 + 9.0, 2), "src": "guide/extrait.mp4", "titre": "Heaven Baby", "artiste": "Ayra Starr feat. ZAYN",
                       "etiquette": "N°1 AFRIQUE DE L'OUEST · SEMAINE 46"}
            t0 += 9.4
    props = {"duree": round(t0 + 2.6, 2), "voix": voix, "mots": sous, "segs": segs, "extrait": extrait, "fond": "guide/ambiance.wav",
             "fin": {"d": round(segs[-1]["f"] - 0.1, 2)}}
    json.dump(props, open(ICI + "/guide-props.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("durée", props["duree"], "s ;", len(segs), "étapes ; extrait", extrait and extrait["d"])


main()
