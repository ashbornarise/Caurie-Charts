"""Cauri Charts Magazine « riche » : reprend le générateur (gen.py) et ajoute une couverture photo et une page
d'ouverture avant chaque section (photo de l'artiste N°1, grand titre dans une police à son image).

28/11/2026 (reconstruit après la perte de l'ancien PC) : tout est dans ce dossier ; les photos viennent de la banque
de photos des artistes (données de la semaine : photo_wa, photo_n1), plus des fichiers posés à la main ; la couverture
affiche le vrai N°1 de la semaine ; les pages « gâteau de 10 000 points » (ancienne formule) sont retirées.

    python outils/magazine/fabrique.py   -> outils/magazine/gen2.py
"""
import os, re, shutil

ICI = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
MAG = ICI
REPO = os.path.abspath(os.path.join(ICI, "..", "..")).replace("\\", "/")
src = open(MAG + "/gen.py", encoding="utf-8").read()

F = "file:///" + REPO + "/resources/fonts/"
POLICES = {"Cinzel": "Cinzel.ttf", "Playfair": "PlayfairDisplay-Italic.ttf", "DMSerif": "DMSerifDisplay-Regular.ttf", "Bungee": "Bungee-Regular.ttf",
           "Archivo": "ArchivoBlack-Regular.ttf", "Dela": "DelaGothicOne-Regular.ttf", "Abril": "AbrilFatface-Regular.ttf",
           "Cormorant": "CormorantGaramond-Italic.ttf", "Spartan": "LeagueSpartan.ttf", "Climate": "ClimateCrisis.ttf",
           "Unbounded": "Unbounded.ttf", "Syne": "Syne.ttf", "Outfit": "Outfit.ttf", "Alfa": "AlfaSlabOne-Regular.ttf", "Bricolage": "BricolageGrotesque.ttf"}
W = ""
# section : (police, graisse) ; la photo est celle du N°1, prise dans la banque (sinon sa pochette, floutée en fond)
STYLE = {
    "WA": ("Playfair", 400), "TG": ("Bungee", 400), "NG": ("DMSerif", 400), "CI": ("Archivo", 400), "GH": ("Dela", 400),
    "SN": ("Abril", 400), "BJ": ("Cormorant", 400), "BF": ("Spartan", 900), "ML": ("Cinzel", 700), "GN": ("Climate", 400),
    "SL": ("Unbounded", 800), "CV": ("Syne", 800), "GW": ("Outfit", 900), "MR": ("Alfa", 400), "GENRES": ("Bricolage", 800),
}

fonts_css = "".join(f'@font-face{{font-family:"{k}";src:url("{F}{v}")}}' for k, v in POLICES.items())
extra_css = fonts_css + """
.ouv-g{position:absolute;left:18mm;top:30mm;bottom:22mm;width:150mm;display:flex;flex-direction:column;justify-content:center}
.ouv-sec{font-size:9pt;font-weight:700;letter-spacing:.24em;text-transform:uppercase;color:var(--sky);display:flex;align-items:center;gap:8px}
.ouv-sec img{width:12mm;height:8mm;object-fit:cover;border-radius:2px;box-shadow:0 1px 4px rgba(0,0,0,.25)}
.ouv-t{line-height:.92;margin-top:5mm;color:var(--ink)}
.ouv-n1{margin-top:9mm;border-top:2px solid #e9e4ff;padding-top:5mm}
.ouv-n1 span{font-size:9pt;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--mag)}
.ouv-n1 strong{display:block;font-size:24pt;line-height:1.05;margin-top:2mm}
.ouv-n1 i{font-style:normal;font-size:13pt;color:var(--mute)}
.ouv-ph{position:absolute;right:0;top:0;bottom:0;width:236mm;overflow:hidden}
.ouv-ph img.ph{width:100%;height:100%;object-fit:cover;display:block}
.ouv-ph:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,#fff 0,rgba(255,255,255,0) 14%);z-index:1}
.ouv-ph .flou{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.ouv-ph .poch{position:absolute;left:50%;top:50%;width:150mm;height:150mm;transform:translate(-50%,-50%) perspective(900px) rotateY(-8deg);border-radius:22px;object-fit:cover;box-shadow:0 40px 80px rgba(0,0,0,.45),0 0 0 5px #fff;z-index:2}
.credit{position:absolute;right:6mm;bottom:12mm;z-index:4;font-size:7.4pt;color:#fff;background:rgba(10,8,25,.45);padding:3px 9px;border-radius:12px}
.cv3{position:absolute;inset:0}
.cv3 img{width:100%;height:100%;object-fit:cover;display:block}
.cv3:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(10,8,25,.55) 0,rgba(10,8,25,0) 26%,rgba(10,8,25,0) 52%,rgba(10,8,25,.72) 100%)}
.cv3-haut{position:absolute;left:18mm;top:14mm;z-index:3;color:#fff}
.cv3-mast{font-family:Anton;font-size:46pt;line-height:1;text-transform:uppercase;letter-spacing:.02em}
.cv3-num{font-size:11pt;font-weight:700;letter-spacing:.2em;text-transform:uppercase;margin-top:2mm;opacity:.92}
.cv3-bas{position:absolute;left:18mm;bottom:20mm;z-index:3;color:#fff}
.cv3-big{font-family:"Cinzel";font-weight:700;font-size:96pt;line-height:.95;text-shadow:0 6px 30px rgba(0,0,0,.45)}
.cv3-who{font-size:16pt;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-top:3mm}
.page.fil .cont{left:32mm}
.page.fil .pied{left:42mm}
.page.photo .pied{color:rgba(255,255,255,.8)}
.cv2{position:absolute;inset:0}
.cv2 img.ph{position:absolute;right:0;top:0;width:280mm;height:100%;object-fit:cover;object-position:50% 25%}
.cv2:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,#fff 0,#fff 32%,rgba(255,255,255,.85) 42%,rgba(255,255,255,0) 60%);z-index:1}
.cv2-txt{position:absolute;left:18mm;top:24mm;bottom:22mm;width:210mm;z-index:2;display:flex;flex-direction:column}
.cv2-mast{font-family:Anton;font-size:64pt;line-height:.9;text-transform:uppercase;letter-spacing:.01em}
.cv2-num{font-family:Anton;font-size:22pt;color:var(--vio);margin-top:2mm}
.cv2-num span{font-family:Serif;font-size:13pt;color:var(--mute);margin-left:4mm}
.cv2-big{font-family:"Cinzel";font-weight:700;font-size:84pt;line-height:.95;margin-top:auto;color:#16132b}
.cv2-big em{font-family:"Cinzel"}
.cv2-who{font-size:15pt;margin-top:4mm;color:#16132b}
.cv2-who b{color:var(--mag)}
.cv2-sum{display:flex;gap:6mm;margin-top:8mm;font-size:11pt;color:var(--mute)}
.cv2-sum b{display:block;font-family:Anton;font-weight:400;font-size:24pt;color:var(--ink)}
"""

ouverture_code = r'''

def taille_titre(t, police):
    """Le mot le plus long remplit la colonne de 150 mm (largeur moyenne d'un caractère selon la police)."""
    import re as _re
    long = max(len(m) for m in _re.split(r"[\s-]+", t))
    wf = {"Bungee": 0.82, "Archivo": 0.74, "Dela": 0.86, "Rubik": 0.98, "Unbounded": 0.8, "Syne": 0.66, "Abril": 0.56, "Playfair": 0.5,
          "DMSerif": 0.55, "Cormorant": 0.46, "Spartan": 0.62, "Cinzel": 0.72, "Outfit": 0.6, "Alfa": 0.7, "Shoulders": 0.42}.get(police, 0.6)
    return int(max(48, min(132, 150 / (long * wf * 0.3528))))


def photo_locale(u, largeur=1800):
    """Photo de la banque téléchargée une fois et réduite, proportions gardées (la page d'ouverture la recadre)."""
    import hashlib, io, urllib.request
    from PIL import Image
    os.makedirs(ICI + "/cache", exist_ok=True)
    f = f"{ICI}/cache/{hashlib.md5(u.encode()).hexdigest()}_photo.jpg"
    if not os.path.exists(f):
        try:
            data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read()
            im = Image.open(io.BytesIO(data)).convert("RGB")
            if im.width > largeur:
                im = im.resize((largeur, round(im.height * largeur / im.width)), Image.LANCZOS)
            im.save(f, quality=86, optimize=True, progressive=True)
        except Exception:
            return ""
    return "file:///" + f


def ouverture(code, nom, num, x, sous_titre):
    police, graisse = STYLE.get(code, ("Outfit", 800))
    brute = D.get("photo_wa") if code == "WA" else next((q.get("photo_n1") for q in D["pays"] if q["code"] == code), "")
    photo = photo_locale(brute) if brute else ""
    credit, cadre = "Photo : banque de photos Cauri Charts", "50% 22%"
    if code == "GENRES":
        covers = [local(next(y["cover"] for y in g["entries"] if y.get("cover")), 600) for g in D["genres"] if any(y.get("cover") for y in g["entries"])][:6]
        droite = ('<div class="ouv-ph" style="background:linear-gradient(140deg,#f3eeff,#e8f5ff)"><div style="position:absolute;inset:26mm 20mm 26mm 34mm;'
                  'display:grid;grid-template-columns:repeat(3,1fr);gap:7mm;align-content:center">'
                  + "".join(f'<img src="{c}" style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:16px;box-shadow:0 18px 36px rgba(40,30,90,.25)">' for c in covers)
                  + '</div></div>')
    elif photo:
        droite = f'<div class="ouv-ph"><img class="ph" src="{photo}" style="object-position:{cadre}"></div><div class="credit">{e(credit)}</div>'
    else:
        c = local(x.get("cover"), 1000) if x and x.get("cover") else ""
        flou = ""
        if c:   # fond flou fabriqué à l'avance (un flou CSS gonflait le PDF à 30 Mo)
            from PIL import Image, ImageFilter, ImageEnhance
            f0 = c.replace("file:///", "")
            f1 = f0.replace(".jpg", "_flou.jpg")
            if not os.path.exists(f1):
                im = Image.open(f0).convert("RGB").resize((360, 360))
                im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(18))).enhance(0.85)
                im.save(f1, quality=80)
            flou = "file:///" + f1
        droite = f'<div class="ouv-ph"><img class="flou" src="{flou}"><img class="poch" src="{c}"></div>'
    drapeau = f'<img src="flags/{code.lower()}.svg">' if len(code) == 2 and code != "WA" else ""
    n1 = (f'<div class="ouv-n1"><span>N°1 de la semaine</span><strong style="font-family:\'{police}\';font-weight:{graisse}">{e(propre(x["title"]))}</strong>'
          f'<i>{artiste(x)}</i></div>') if x else ""
    return f"""
{entete(f'Semaine {NUM}', sous_titre)}
<div class="ouv-g">
  <div class="ouv-sec">{drapeau}Section {num:02d}</div>
  <div class="ouv-t" style="font-family:'{police}';font-weight:{graisse};font-size:{taille_titre(nom, police)}pt">{e(nom).replace("-", "-<br>")}</div>
  {n1}
</div>
{droite}
"""
'''

COULEE = open(ICI + "/coulee.py", encoding="utf-8").read()

# 1) la couverture photo remplace l'ancienne
a = src.index("# ------------------------------------------------------------------ couverture")
b = src.index("# ------------------------------------------------------------------ sommaire")
couv = r'''# ------------------------------------------------------------------ couverture : le N°1 Afrique de l'Ouest de la semaine
wa = D["wa"]
n1 = wa[0]
_ph = photo_locale(D["photo_wa"]) if D.get("photo_wa") else ""
_t = propre(n1["title"])
_taille = 96 if len(_t) <= 12 else 78 if len(_t) <= 18 else 60
couverture = f"""
<div class="cv3"><img src="{_ph or local(n1.get('cover'), 1400)}" style="object-position:50% 22%"></div>
<div class="cv3-haut"><div class="cv3-mast">Cauri Charts</div><div class="cv3-num">N°{NUM} · {PERIODE}</div></div>
<div class="cv3-bas"><div class="cv3-big" style="font-size:{_taille}pt">{e(_t)}</div><div class="cv3-who">{artiste(n1)} · N°1 Afrique de l'Ouest</div></div>
<div class="credit">{"Photo : banque de photos Cauri Charts" if _ph else "Pochette officielle"}</div>
"""
page(couverture)

'''
src = src[:a] + couv + src[b:]

# 2) fonction d'ouverture après les helpers
k = src.index("PAGES = []")
src = src[:k] + "W = " + repr(W) + "\nSTYLE = " + repr(STYLE) + "\n" + ouverture_code + COULEE + "\n" + src[k:]

# 3) ouvertures avant le Top 20, chaque pays et les genres ; numéros de page du sommaire recalculés
src = src.replace("# ------------------------------------------------------------------ Top 20 Afrique de l'Ouest",
                  "# ------------------------------------------------------------------ Top 20 Afrique de l'Ouest\npage(ouverture('WA', \"Afrique de l'Ouest\", 1, n1, \"Top 20 Afrique de l'Ouest\"))")
src = src.replace("for p in PAYS:\n    pr = p[\"prime\"]\n    x = pr[0]\n",
                  "for kp, p in enumerate(PAYS):\n    pr = p[\"prime\"]\n    x = pr[0]\n    page(ouverture(p['code'], p['nom'], kp + 2, x, 'Top ' + e(p['nom'])))\n")
src = src.replace("# ------------------------------------------------------------------ genres",
                  "# ------------------------------------------------------------------ genres\npage(ouverture('GENRES', 'Par genre', len(PAYS) + 2, None, 'Les classements par genre'))")
src = src.replace('<span>p. {k + 4}</span>', '<span>p. {2 * k + 6}</span>')
assert "p. {2 * k + 6}" in src
src = src.replace("css = open(ICI + \"/style.css\", encoding=\"utf-8\").read()", "css = open(ICI + \"/style.css\", encoding=\"utf-8\").read() + EXTRA")
src = src.replace('open(ICI + "/magazine.html", "w"', 'open(SORTIE, "w"')
src = "EXTRA = " + repr(extra_css) + "\nSORTIE = " + repr(ICI + "/magazine.html") + "\n" + src
boucle_a = "for n, d, c in PAGES:\n    out.append(f'<section class=\"page\">{chemin(n, d)}<div class=\"cont\">{c}</div>'"
assert boucle_a in src, "boucle de sortie introuvable"
src = src.replace(boucle_a, """FILS = [n for n, d, c in PAGES if 'ouv-ph' not in c and 'cv3' not in c]
for n, d, c in PAGES:
    tete = (f'<section class="page fil">{coulee(FILS.index(n), len(FILS), fin=(n == FILS[-1]))}' if n in FILS else '<section class="page photo">')
    out.append(f'{tete}<div class="cont">{c}</div>'""")
src = src.replace('<div class="arrivee" style="left:400mm;top:276mm">{ico(ETOILE, 20)}</div>', '')
# 28/11/2026 : les trois pages « gâteau de 10 000 points » (guide/points.html, ancienne formule, perdu avec l'ancien PC)
# ne sont plus reprises ; la dernière page explique la formule actuelle.
open(ICI + "/gen2.py", "w", encoding="utf-8").write(src)
print("gen2 ok")
