"""Cauri Charts Magazine : tous les classements officiels d'une semaine, en A3 paysage, un fil continu de page en page."""
import html, json, os, sys
from datetime import date

ICI = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
# 28/11/2026 : chemins du dépôt (l'original pointait vers c:/Users/agbal/OneDrive/... de l'ancien PC)
REPO = os.path.abspath(os.path.join(ICI, "..", "..")).replace("\\", "/")
ANCIEN = "file:///c:/Users/agbal/OneDrive/Documents/GitHub/Caurie-Charts/"
RACINE = "file:///" + REPO + "/"
SRC = sys.argv[1] if len(sys.argv) > 1 else ICI + "/donnees/s46.json"
D = json.load(open(SRC, encoding="utf-8"))
sys.path.insert(0, REPO + "/django")
from core import saison  # noqa: E402  (logo de Noël du 27/11 au 06/01, officiel sinon)
LOGO = "brand/" + saison.nom("logo.svg", date.fromordinal(date.fromisoformat(D["fin"]).toordinal() + 1) if D.get("fin") else None)  # jour de publication
COUL = ["#19c6ee", "#22b8f4", "#2fa8ff", "#4a8cff", "#5b7cff", "#6b6cff", "#7b5cff", "#9150ff", "#a54dff", "#c24ee8", "#e04fd0"]
MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
NUM = int(D["semaine"].split("W")[1])
d0, d1 = date.fromisoformat(D["debut"]), date.fromisoformat(D["fin"])
PERIODE = f"du {d0.day} au {d1.day} {MOIS[d1.month]} {d1.year}" if d0.month == d1.month else f"du {d0.day} {MOIS[d0.month]} au {d1.day} {MOIS[d1.month]} {d1.year}"
DE = {"BF": "du Burkina Faso", "BJ": "du Bénin", "CI": "de Côte d'Ivoire", "CV": "du Cap-Vert", "GH": "du Ghana", "GN": "de Guinée",
      "GW": "de Guinée-Bissau", "ML": "du Mali", "MR": "de Mauritanie", "NG": "du Nigeria", "SL": "de Sierra Leone", "SN": "du Sénégal",
      "TG": "du Togo", "NE": "du Niger", "LR": "du Liberia", "GM": "de Gambie"}
ORDRE = ["TG", "NG", "CI", "GH", "SN", "BJ", "BF", "ML", "GN", "SL", "CV", "GW", "MR"]
PAYS = sorted(D["pays"], key=lambda p: (ORDRE.index(p["code"]) if p["code"] in ORDRE else 99, p["nom"]))


def e(s):
    return html.escape(str(s or ""))


def ico(d, w=16):
    return f'<svg class="i" style="width:{w}px;height:{w}px" viewBox="0 0 24 24">{d}</svg>'


HAUT = '<path d="m18 15-6-6-6 6"/>'
BAS = '<path d="m6 9 6 6 6-6"/>'
EGAL = '<path d="M5 12h14"/>'
ETOILE = '<path d="M12 3l1.9 5.8L20 9l-4.9 3.6L17 19l-5-3.7L7 19l1.9-6.4L4 9l6.1-.2Z"/>'


def mouvement(x):
    p, av = int(x["position"]), x.get("previous_position")
    if av in (None, "", "None"):
        return '<span class="mv nv">NOUVEAU</span>'
    av = int(av)
    if av > p:
        return f'<span class="mv up">{ico(HAUT, 13)}{av - p}</span>'
    if av < p:
        return f'<span class="mv dn">{ico(BAS, 13)}{p - av}</span>'
    return f'<span class="mv eq">{ico(EGAL, 13)}</span>'


def local(u, px):
    """Télécharge l'image une fois, la recadre au carré et la réduit : poids du PDF maîtrisé (une pochette pesait 12 Mo)."""
    import hashlib, io, urllib.request
    from PIL import Image
    os.makedirs(ICI + "/cache", exist_ok=True)
    f = f"{ICI}/cache/{hashlib.md5(u.encode()).hexdigest()}_{px}.jpg"
    if not os.path.exists(f):
        try:
            data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
            im = Image.open(io.BytesIO(data)).convert("RGB")
            c = min(im.size); im = im.crop(((im.width - c) // 2, (im.height - c) // 2, (im.width + c) // 2, (im.height + c) // 2))
            im.resize((px, px), Image.LANCZOS).save(f, quality=84, optimize=True, progressive=True)
        except Exception:
            return ""
    return "file:///" + f


def img(u, cls="pc"):
    px = 1000 if cls == "cv-pochette" else 760 if cls == "h-poch" else 300 if cls == "t1c" else 140
    u = local(u, px) if u else ""
    if not u:
        return f'<div class="{cls} vide">{ico(ETOILE, 18)}</div>'
    return f'<img class="{cls}" src="{e(u)}" alt="" loading="eager">'


def propre(t):
    """Affichage seulement : retire les mentions de clip restées dans certains titres YouTube."""
    import re
    t = re.sub(r"\s*[\(\[][^)\]]*(clip|officiel|official|video|vid[ée]o|lyrics?|audio|visuali[sz]er)[^)\]]*[\)\]]?\s*$", "", str(t or ""), flags=re.I)
    return re.sub(r"[\s\-–|·]+$", "", t).strip()


def titre_complet(x):
    return e(propre(x.get("title")))


def artiste(x):
    a = e(x.get("artist_name"))
    if x.get("featuring"):
        a += f' <i>feat. {e(x["featuring"])}</i>'
    return a


def ligne(x, compact=False):
    sem = int(x.get("weeks_on_chart") or 1)
    return (f'<div class="row{" c" if compact else ""}"><b class="rk">{int(x["position"])}</b>{mouvement(x)}{img(x.get("cover"))}'
            f'<div class="tt"><strong>{titre_complet(x)}</strong><span>{artiste(x)}</span></div>'
            f'<div class="st"><b>{sem}</b><span>{"semaine" if sem == 1 else "semaines"}</span></div></div>')


def chemin(n, d):
    a, b = COUL[(n - 1) % 10], COUL[n % 10 if n % 10 else 10]
    return f"""<svg class="chemin" viewBox="0 0 420 297"><defs><linearGradient id="g{n}" gradientUnits="userSpaceOnUse" x1="0" x2="420" y1="0" y2="0">
<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>
<path d="{d}" fill="none" stroke="url(#g{n})" stroke-width="6" stroke-linecap="round" opacity=".12"/>
<path d="{d}" fill="none" stroke="url(#g{n})" stroke-width="1.8" stroke-linecap="round"/>
<path d="{d}" fill="none" stroke="#fff" stroke-width=".45" stroke-dasharray="2 3" opacity=".9"/></svg>"""


def vague(k):
    """Fil du bas de page : entre et sort toujours à 276 mm, ondule différemment à chaque page."""
    h = [262, 284, 266, 286, 264, 282][k % 6]
    return f"M0 276 C70 276 110 {h} 210 {h} C310 {h} 350 276 420 276"


def entete(gauche, droite):
    return (f'<div class="ent"><img class="logo" src="{LOGO}"><div class="eti"><span>{gauche}</span>{droite}</div></div>')


PAGES = []


def page(contenu, d=None):
    n = len(PAGES) + 1
    PAGES.append((n, d or vague(n), contenu))
    return n


# ------------------------------------------------------------------ couverture
wa = D["wa"]
n1 = wa[0]
couverture = f"""
{entete('Cauri Charts Magazine', f'Semaine {NUM} · {PERIODE}')}
<div class="cv-g">
  <div class="kick">Le magazine des classements officiels</div>
  <h1 class="mast">Cauri<br><em>Charts</em></h1>
  <div class="cv-num">N°{NUM}<span>{PERIODE}</span></div>
  <ul class="cv-sum">
    <li><b>Top 20</b> Afrique de l'Ouest</li>
    <li><b>{len(PAYS)} pays</b> classés cette semaine</li>
    <li><b>{len(D['genres'])} classements</b> par genre</li>
  </ul>
</div>
<div class="cv-d">
  <div class="cv-halo"></div>
  {img(n1.get('cover'), 'cv-pochette')}
  <div class="cv-n1"><span>N°1 Afrique de l'Ouest</span><strong>{e(propre(n1['title']))}</strong><i>{artiste(n1)}</i></div>
</div>
<div class="depart" style="left:20mm;top:268mm"><span></span>Le fil de la semaine</div>
"""
page(couverture, "M28 276 C110 276 150 262 240 262 C320 262 360 276 420 276")

# ------------------------------------------------------------------ sommaire : les N°1
tuiles = ""
for k, p in enumerate(PAYS):
    x = p["prime"][0]
    tuiles += (f'<div class="t1"><div class="t1h"><img class="fl" src="flags/{p["code"].lower()}.svg"><b>{e(p["nom"])}</b><span>p. {k + 4}</span></div>'
               f'{img(x.get("cover"), "t1c")}<strong>{e(propre(x["title"]))}</strong><i>{e(x["artist_name"])}</i></div>')
sommaire = f"""
{entete(f'Semaine {NUM}', 'Les N°1 de la semaine')}
<div class="titre-p"><div class="kick">Sommaire</div><h2 class="titre">Les <em>N°1</em> de la semaine</h2>
<p class="serif">Un pays, un titre au sommet. Les classements complets suivent, page après page.</p></div>
<div class="t1grid">{tuiles}</div>
"""
page(sommaire)

# ------------------------------------------------------------------ Top 20 Afrique de l'Ouest
g1 = "".join(ligne(x, True) for x in wa[1:10])
g2 = "".join(ligne(x, True) for x in wa[10:20])
top_wa = f"""
{entete(f'Semaine {NUM}', "Top 20 Afrique de l'Ouest")}
<div class="hero">
  <div class="kick">Top 20 Afrique de l'Ouest</div>
  <div class="h-num">N°1</div>
  {img(n1.get('cover'), 'h-poch')}
  <h2 class="h-t">{e(propre(n1['title']))}</h2>
  <p class="h-a">{artiste(n1)}</p>
  <div class="chips"><span><b>{int(n1.get('weeks_on_chart') or 1)}</b> semaines</span><span>meilleure place <b>{int(n1.get('peak_position') or 1)}</b></span></div>
</div>
<div class="liste deux"><div>{g1}</div><div>{g2}</div></div>
<div class="note-bas">Tous les pays ensemble, au plus 5 titres d'un même pays.</div>
"""
page(top_wa)

# ------------------------------------------------------------------ une page par pays
for p in PAYS:
    pr = p["prime"]
    x = pr[0]
    if len(pr) > 10:
        liste = f'<div class="liste deux"><div>{"".join(ligne(y, True) for y in pr[1:11])}</div><div>{"".join(ligne(y, True) for y in pr[11:20])}</div></div>'
    else:
        liste = f'<div class="liste"><div>{"".join(ligne(y) for y in pr[1:10])}</div></div>'

    def mini(titre, rows, artistes=False):
        it = ""
        for y in (rows or [])[:3]:
            if artistes:
                it += f'<div class="mi">{img(y.get("photo"), "mp rond")}<div><strong>{e(y["artist_name"])}</strong><span>N°{int(y["position"])}</span></div></div>'
            else:
                it += f'<div class="mi">{img(y.get("cover"), "mp")}<div><strong>{e(propre(y["title"]))}</strong><span>{e(y["artist_name"])}</span></div></div>'
        return f'<div class="mini"><h4>{titre}</h4>{it or "<p>—</p>"}</div>'
    contenu = f"""
{entete(f'Semaine {NUM}', 'Top ' + e(p['nom']))}
<div class="hero">
  <div class="kick"><img class="flk" src="flags/{p['code'].lower()}.svg">Top {len(pr)} {DE.get(p['code'], e(p['nom']))}</div>
  <div class="h-num">N°1</div>
  {img(x.get('cover'), 'h-poch')}
  <h2 class="h-t">{e(propre(x['title']))}</h2>
  <p class="h-a">{artiste(x)}</p>
  <div class="chips"><span><b>{int(x.get('weeks_on_chart') or 1)}</b> {"semaine" if int(x.get('weeks_on_chart') or 1) == 1 else "semaines"}</span><span>meilleure place <b>{int(x.get('peak_position') or 1)}</b></span>{mouvement(x)}</div>
</div>
{liste}
<div class="minis">{mini('Buzz · les plus fortes hausses', p.get('buzz'))}{mini('Fresh · les nouveautés', p.get('fresh'))}{mini('Icon · les artistes', p.get('icon'), True)}</div>
"""
    page(contenu)

# ------------------------------------------------------------------ genres
cartes = ""
for k, g in enumerate(D["genres"]):
    rows = "".join(f'<div class="gr"><b>{int(y["position"])}</b>{img(y.get("cover"), "gp")}<div><strong>{e(propre(y["title"]))}</strong><span>{e(y["artist_name"])}</span></div></div>' for y in g["entries"])
    cartes += f'<div class="genre" style="--c:{COUL[(k * 2) % 10 + 1]}"><h3>{e(g["nom"])}</h3>{rows}</div>'
genres = f"""
{entete(f'Semaine {NUM}', 'Les classements par genre')}
<div class="titre-p"><div class="kick">Afrique de l'Ouest</div><h2 class="titre">Par <em>genre</em></h2></div>
<div class="genres">{cartes}</div>
"""
page(genres)

# ------------------------------------------------------------------ fin
fin = f"""
{entete(f'Semaine {NUM}', 'À la semaine prochaine')}
<div class="titre-p" style="top:40mm"><div class="kick">Comment on calcule</div><h2 class="titre" style="line-height:1.08">Chaque <em>place</em>,<br>une part d'<em>écoute</em></h2>
<p class="serif" style="width:170mm">Chaque semaine, nous relevons les classements d'Apple Music, Spotify, Deezer, Shazam et Boomplay, et les vues
des clips officiels sur YouTube. Chaque place devient une part d'écoute ; les plateformes sont combinées selon leur poids
dans le pays, et le score final devient l'indice Cauri, de 0 à 100 (le N°1 vaut 100). Les chiffres inhabituels sont
vérifiés avant publication. La méthode complète est publique.</p>
<div class="logos-fin"><img src="plateformes/youtube.png"><img src="plateformes/apple-music.png"><img src="plateformes/spotify.png"><img src="plateformes/deezer.png"><img src="plateformes/shazam.png"><img src="plateformes/boomplay.png"></div>
<p class="lien">cauricharts.com/documents · cauricharts.com/methodologie</p></div>
<div class="rdv"><div class="kick" style="color:#fff">Prochain numéro</div><strong>Vendredi soir, 19 h GMT</strong>
<p>Tous les classements, tous les pays, chaque semaine sur cauricharts.com</p>
<div class="res"><span><img src="reseaux/instagram.png">@cauricharts</span><span><img src="reseaux/tiktok.png">@caurichartsofficial</span><span><img src="reseaux/facebook.png">Cauri Charts</span></div></div>
<div class="arrivee" style="left:400mm;top:276mm">{ico(ETOILE, 20)}</div>
"""
page(fin, "M0 276 C70 276 110 264 210 264 C300 264 340 276 400 276")

N = len(PAGES)
css = open(ICI + "/style.css", encoding="utf-8").read().replace(ANCIEN, RACINE)
out = ['<!doctype html><html lang="fr"><head><meta charset="utf-8">',
       f'<title>Cauri Charts Magazine N°{NUM} · Classements de la semaine {PERIODE}</title>',
       f'<base href="{RACINE}public/assets/img/">', f'<style>{css}</style></head><body>']
for n, d, c in PAGES:
    out.append(f'<section class="page">{chemin(n, d)}<div class="cont">{c}</div>'
               f'<div class="pied"><span>Cauri Charts Magazine N°{NUM} · la référence de la musique ouest-africaine</span><span>{n:02d} / {N:02d}</span></div></section>')
out.append("</body></html>")
open(ICI + "/magazine.html", "w", encoding="utf-8").write("\n".join(out))
print("ok", N, "pages")
