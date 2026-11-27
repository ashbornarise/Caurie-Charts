"""Rapport hebdomadaire en PDF — version magazine (23/11/2026, demande du fondateur : « plus attractif »).

Charte Cauri : blanc dominant, bleu ciel et violet en verre, Anton pour les grands titres, Montserrat pour les intertitres,
DM Sans pour le texte ; icônes au trait (jamais d'émojis). A4 portrait, rendu par Chromium (Playwright).
"""
import base64
import html
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FONTS = ROOT / "resources" / "fonts"
OBJECTIF = 10_000
RESEAUX = (("tiktok", "TikTok", "follower_count"), ("facebook", "Facebook", "followers_count"),
           ("instagram", "Instagram", "followers_count"), ("telegram", "Telegram", "member_count"))
COULEURS = {"tiktok": "#12121F", "facebook": "#1877F2", "instagram": "#C13584", "telegram": "#229ED9"}
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
e = html.escape


def _logo() -> str:
    try:
        return "data:image/svg+xml;base64," + base64.b64encode(__import__("core.saison", fromlist=["chemin"]).chemin(ROOT / "public/assets/img/brand", "logo.svg").read_bytes()).decode("ascii")
    except OSError:
        return ""


def _n(v) -> str:
    try:
        return f"{int(v):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def _jour(iso: str, court: bool = False) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    if court:
        return ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")[d.weekday()] + f" {d.day}"
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def _periode(debut: str, fin: str) -> str:
    try:
        a, b = date.fromisoformat(debut[:10]), date.fromisoformat(fin[:10])
    except ValueError:
        return f"{debut} — {fin}"
    if a.month == b.month:
        return f"{a.day} – {b.day} {MOIS[b.month - 1]} {b.year}"
    return f"{a.day} {MOIS[a.month - 1]} – {b.day} {MOIS[b.month - 1]} {b.year}"


def _delta(a, b) -> str:
    """Pastille d'évolution : « +12 % » vert, « −8 % » rouge (b = semaine précédente)."""
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return ""
    if not b:
        return ""
    p = (a - b) / b * 100
    signe, cls = ("+", "hausse") if p >= 0 else ("−", "baisse")
    return f'<span class="delta {cls}">{signe}{abs(p):.0f} % <small>vs sem. préc.</small></span>'


def _titre_post(t: str) -> str:
    """Titre lisible d'une publication : 1re ligne, sans hashtags ni mentions en rafale, 90 caractères."""
    t = (str(t or "").strip().splitlines() or [""])[0]
    t = re.sub(r"(#\w+\s*){2,}", "", t)
    t = re.sub(r"\s+", " ", t).strip(" ·-—")
    return (t[:88] + "…") if len(t) > 90 else (t if t and t.lower() != "publication" else "Sans légende")


ICONES = {   # au trait, style Lucide
    "abonnes": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    "vues": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "posts": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/>',
    "site": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
}


def _icone(nom: str) -> str:
    return f'<svg class="ic" viewBox="0 0 24 24">{ICONES[nom]}</svg>'


def _barres_h(valeurs: list[tuple[str, float, str]], unite: str = "") -> str:
    """Barres horizontales (libellé, valeur, couleur) en HTML : plus net que le SVG à l'impression."""
    m = max([v for _, v, _ in valeurs] or [1]) or 1
    return '<div class="barres">' + "".join(
        f'<div class="barre"><span class="lib">{e(l)}</span><span class="piste"><i style="width:{max(1.5, 100 * v / m):.1f}%;background:{c}"></i></span>'
        f'<b>{_n(v)}{unite}</b></div>' for l, v, c in valeurs) + "</div>"


def _colonnes(points: list[tuple[str, float]]) -> str:
    """Histogramme vertical (jours de la semaine)."""
    m = max([v for _, v in points] or [1]) or 1
    return '<div class="colonnes">' + "".join(
        f'<div class="col"><b>{_n(v)}</b><span class="tige"><i style="height:{max(2, 100 * v / m):.1f}%"></i></span><small>{e(l)}</small></div>'
        for l, v in points) + "</div>"


def _markdown(texte: str) -> str:
    """Texte de l'IA -> HTML : titres, gras, listes, citations ET tableaux (les « |---| » s'affichaient tels quels)."""
    out, liste, tableau = [], False, []

    def ferme_liste():
        nonlocal liste
        if liste:
            out.append("</ul>")
            liste = False

    def ferme_tableau():
        nonlocal tableau
        if tableau:
            lignes = [l for l in tableau if not re.fullmatch(r"\|?[\s:|-]+\|?", l)]
            cellules = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lignes]
            if cellules:
                tete, corps = cellules[0], cellules[1:]
                out.append("<table class='md'><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in tete) + "</tr></thead><tbody>"
                           + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in corps) + "</tbody></table>")
            tableau = []

    for ligne in (texte or "").splitlines():
        l = ligne.strip()
        if l.startswith("|"):
            ferme_liste()
            tableau.append(l)
            continue
        ferme_tableau()
        if not l or set(l) <= {"-", "*", "_"}:
            ferme_liste()
            continue
        if l.startswith("#"):
            ferme_liste()
            niveau = len(l) - len(l.lstrip("#"))
            t = _inline(l.lstrip("#").strip())
            if niveau == 1:
                continue                     # le titre général est déjà sur la page
            out.append(f"<h3>{t}</h3>" if niveau == 2 else f"<h4>{t}</h4>")
        elif l[:2] in ("- ", "* ") or re.match(r"\d+\.\s", l):
            if not liste:
                out.append("<ul>")
                liste = True
            out.append(f"<li>{_inline(re.sub(r'^([-*]|\d+\.)\s+', '', l))}</li>")
        elif l.startswith(">"):
            ferme_liste()
            out.append(f"<blockquote>{_inline(l.lstrip('> '))}</blockquote>")
        else:
            ferme_liste()
            out.append(f"<p>{_inline(l)}</p>")
    ferme_tableau()
    ferme_liste()
    return "".join(out)


def _inline(t: str) -> str:
    h = e(t)
    h = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h)
    return re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<i>\1</i>", h)


def _cinq_phrases(texte: str) -> tuple[str, str]:
    """Sépare le bloc « En 5 phrases » (mis en avant sur la couverture) du reste de l'analyse."""
    m = re.search(r"^##\s*En\s*5\s*phrases?\s*$(.*?)(?=^##\s)", texte or "", re.S | re.M | re.I)
    if not m:
        return "", texte or ""
    return m.group(1).strip(), (texte[:m.start()] + texte[m.end():])


def _css() -> str:
    # polices intégrées (data:) : une page ouverte par set_content ne peut pas lire les fichiers file://
    f = lambda n: "data:font/ttf;base64," + base64.b64encode((FONTS / n).read_bytes()).decode("ascii")  # noqa: E731
    return f"""
@font-face{{font-family:Anton;src:url("{f('Anton-Regular.ttf')}")}}
@font-face{{font-family:Montserrat;src:url("{f('Montserrat.ttf')}");font-weight:100 900}}
@font-face{{font-family:DMSans;src:url("{f('DMSans.ttf')}");font-weight:100 1000}}
:root{{--encre:#12121F;--doux:#4A4A63;--faible:#7A7A92;--trait:#E6E8F2;--violet:#7C3AED;--violet2:#A78BFA;--ciel:#38BDF8;--ciel-pale:#EAF7FF;--violet-pale:#F3EEFF}}
@page{{size:A4;margin:0}}
*{{box-sizing:border-box}}
body{{margin:0;color:var(--encre);font:10.5pt/1.5 DMSans,Arial,sans-serif;-webkit-print-color-adjust:exact}}
.page{{width:210mm;height:297mm;padding:16mm 16mm 20mm;position:relative;page-break-after:always;overflow:hidden;background:#fff}}
.page:last-child{{page-break-after:auto}}
.page.longue{{overflow:visible;height:auto;min-height:297mm}} .page.longue .pied{{display:none}}
.pied{{position:absolute;left:16mm;right:16mm;bottom:9mm;display:flex;justify-content:space-between;font:600 7.5pt Montserrat,Arial;color:var(--faible);letter-spacing:.06em;text-transform:uppercase;border-top:1px solid var(--trait);padding-top:3mm}}
.halo{{position:absolute;border-radius:50%;filter:blur(40px);opacity:.55;z-index:0}}
.contenu{{position:relative;z-index:1}}
.sur{{font:700 8pt Montserrat,Arial;letter-spacing:.22em;text-transform:uppercase;color:var(--violet)}}
h1{{font:54pt/0.95 Anton,Impact,sans-serif;margin:5mm 0 3mm;letter-spacing:-.5px;text-transform:uppercase}}
h1 .v{{color:var(--violet)}}
h2{{font:30pt/1 Anton,Impact,sans-serif;text-transform:uppercase;margin:0 0 2mm}}
.chapeau{{font:500 11pt/1.5 DMSans,Arial;color:var(--doux);margin:0 0 7mm;max-width:150mm}}
.num{{font:700 9pt Montserrat;color:#fff;background:var(--violet);border-radius:99px;padding:1.2mm 3.4mm;margin-right:3mm;vertical-align:middle}}
.verre{{background:linear-gradient(145deg,rgba(255,255,255,.92),rgba(246,248,255,.78));border:1px solid rgba(124,58,237,.14);border-radius:6mm;box-shadow:0 6px 22px rgba(56,38,140,.08)}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm;margin:6mm 0 4mm}}
.kpi{{padding:4.5mm 4mm 4mm}}
.kpi .ic{{width:8mm;height:8mm;stroke:var(--violet);fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;padding:1.6mm;border-radius:2.5mm;background:var(--violet-pale)}}
.kpi strong{{display:block;font:28pt/1 Anton,Impact;margin:2.5mm 0 1mm}}
.kpi span.l{{font:600 7pt Montserrat;color:var(--doux);text-transform:uppercase;letter-spacing:.08em}}
.delta{{display:inline-block;margin-top:2mm;font:700 8.5pt Montserrat;padding:1mm 2.6mm;border-radius:99px}}
.delta small{{font-weight:500;opacity:.8}}
.hausse{{background:#DCFCE7;color:#166534}}.baisse{{background:#FEE2E2;color:#991B1B}}
.objectif{{padding:5mm 6mm;margin-top:4mm}}
.objectif .tete{{display:flex;justify-content:space-between;font:700 9pt Montserrat;text-transform:uppercase;letter-spacing:.08em;color:var(--doux)}}
.jauge{{height:4mm;border-radius:99px;background:#EEF0F7;margin-top:3mm;overflow:hidden}}
.jauge i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--ciel),var(--violet))}}
.resume{{padding:6mm 7mm;margin-top:5mm;border-left:3px solid var(--violet)}}
.resume p{{margin:0 0 2mm}}
.reseaux{{display:grid;grid-template-columns:repeat(2,1fr);gap:4mm;margin-bottom:6mm}}
.reseau{{padding:5mm 6mm}}
.reseau .nom{{display:flex;align-items:center;gap:2.5mm;font:800 11pt Montserrat}}
.reseau .pt{{width:3.2mm;height:3.2mm;border-radius:50%}}
.reseau strong{{display:block;font:30pt/1 Anton;margin:3mm 0 1mm}}
.reseau small{{color:var(--faible);font-size:8.5pt}}
.bloc{{padding:6mm;margin-bottom:5mm}}
.bloc h3{{font:800 10pt Montserrat;text-transform:uppercase;letter-spacing:.08em;margin:0 0 4mm;color:var(--doux)}}
.barres{{display:flex;flex-direction:column;gap:2.6mm}}
.barre{{display:grid;grid-template-columns:44mm 1fr 18mm;gap:3mm;align-items:center;font-size:9.5pt}}
.barre .lib{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--doux)}}
.barre .piste{{height:4.2mm;background:#F1F2F8;border-radius:99px;overflow:hidden}}
.barre .piste i{{display:block;height:100%;border-radius:99px}}
.barre b{{text-align:right;font:700 9.5pt Montserrat}}
.colonnes{{display:flex;gap:3mm;align-items:flex-end;height:62mm}}
.col{{flex:1;display:flex;flex-direction:column;align-items:center;gap:1.5mm;height:100%}}
.col b{{font:700 8pt Montserrat;color:var(--doux)}}
.col .tige{{flex:1;width:100%;display:flex;align-items:flex-end}}
.col .tige i{{display:block;width:100%;border-radius:2.5mm 2.5mm 1mm 1mm;background:linear-gradient(180deg,var(--violet2),var(--ciel))}}
.col small{{font:600 8pt Montserrat;color:var(--faible)}}
.deuxcol{{display:grid;grid-template-columns:1fr 1fr;gap:5mm}}
table{{width:100%;border-collapse:collapse;font-size:9pt}}
th{{text-align:left;font:700 7.5pt Montserrat;text-transform:uppercase;letter-spacing:.08em;color:var(--faible);padding:0 2mm 2mm;border-bottom:1px solid var(--trait)}}
td{{padding:2.4mm 2mm;border-bottom:1px solid #F1F2F8;vertical-align:top}}
td.n,th.n{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
.top{{display:flex;flex-direction:column;gap:3mm}}
.post{{display:grid;grid-template-columns:12mm 1fr 22mm 22mm;gap:3mm;align-items:center;padding:3.5mm 5mm}}
.post .rang{{font:26pt/1 Anton;color:var(--violet)}}
.post .t{{font:600 9.5pt/1.35 DMSans}}
.post .pill{{display:inline-block;margin-top:1.2mm;font:700 7pt Montserrat;color:#fff;border-radius:99px;padding:.6mm 2.4mm;text-transform:uppercase;letter-spacing:.06em}}
.post .m{{text-align:right}} .post .m b{{display:block;font:20pt/1 Anton}} .post .m small{{font:600 7pt Montserrat;color:var(--faible);text-transform:uppercase}}
.prose{{column-count:2;column-gap:8mm;font-size:9.6pt}}
.prose h3{{font:800 10pt Montserrat;text-transform:uppercase;letter-spacing:.06em;color:var(--violet);margin:4mm 0 2mm;break-after:avoid}}
.prose h4{{font:800 9.5pt Montserrat;margin:3mm 0 1.5mm;break-after:avoid}}
.prose p{{margin:0 0 2.6mm}} .prose ul{{margin:0 0 3mm;padding-left:4.5mm}} .prose li{{margin-bottom:1.2mm}}
.prose table.md{{break-inside:avoid;margin:2mm 0 4mm;font-size:8pt}}
.prose blockquote{{margin:0 0 3mm;padding:2mm 4mm;border-left:3px solid var(--ciel);background:var(--ciel-pale);border-radius:0 3mm 3mm 0}}
.chiffres{{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin-bottom:5mm}}
.chiffres div{{padding:5mm}} .chiffres strong{{display:block;font:24pt/1 Anton;margin-bottom:1mm}} .chiffres span{{font:600 8pt Montserrat;color:var(--doux);text-transform:uppercase;letter-spacing:.06em}}
"""


def html_rapport(data: dict, texte: str, exemple: bool = False) -> str:
    s, prev = data["semaine"], data.get("semaine_precedente") or {}
    stats = data.get("reseaux_stats") or {}
    posts = s.get("metriques_posts") or []
    debut, fin = s.get("debut", ""), s.get("fin", "")
    try:
        sem = date.fromisoformat(debut[:10]).isocalendar()[1]
    except ValueError:
        sem = ""
    abonnes = {k: (stats.get(k) or {}).get(cle) for k, _, cle in RESEAUX}
    total = sum(v for v in abonnes.values() if isinstance(v, int))
    vues = sum(int(p.get("vues") or 0) for p in posts)
    vues_prec = sum(int(p.get("vues") or 0) for p in prev.get("metriques_posts") or [])
    cinq, analyse = _cinq_phrases(texte)
    logo = _logo()
    num = [0]

    def page(contenu: str, halos: str = "", longue: bool = False) -> str:
        num[0] += 1
        return (f'<div class="page{" longue" if longue else ""}">{halos}<div class="contenu">{contenu}</div><div class="pied"><span>Cauri Charts · rapport hebdomadaire · '
                f'semaine {sem}</span><span>{num[0]:02d}</span></div></div>')

    halo = lambda x, y, t, c: f'<div class="halo" style="left:{x}mm;top:{y}mm;width:{t}mm;height:{t}mm;background:{c}"></div>'  # noqa: E731
    demo = '<p class="sur" style="color:#B91C1C">Exemple · données factices</p>' if exemple else ""

    # 1. couverture
    kpi = lambda ic, val, lib, d="": f'<div class="kpi verre">{_icone(ic)}<strong>{val}</strong><span class="l">{lib}</span><br>{d}</div>'  # noqa: E731
    couverture = f"""{demo}<div style="display:flex;justify-content:space-between;align-items:center">{f'<img src="{logo}" style="height:13mm">' if logo else '<b>Cauri Charts</b>'}
      <span class="sur">Semaine {sem} · {e(str(date.fromisoformat(fin[:10]).year) if fin else '')}</span></div>
      <p class="sur" style="margin-top:16mm">Rapport hebdomadaire</p>
      <h1>La semaine<br><span class="v">{e(_periode(debut, fin))}</span></h1>
      <p class="chapeau">Audience, réseaux, publications, site et dépenses de Cauri Charts, la référence de la musique ouest-africaine.</p>
      <div class="kpis">{kpi('abonnes', _n(total), 'abonnés, tous réseaux')}{kpi('vues', _n(vues), 'vues des publications', _delta(vues, vues_prec))}
        {kpi('posts', _n(s.get('posts_crees', 0)), 'posts créés', _delta(s.get('posts_crees'), prev.get('posts_crees')))}
        {kpi('site', _n(s.get('visites', 0)), 'visiteurs du site', _delta(s.get('visites'), prev.get('visites')))}</div>
      <div class="objectif verre"><div class="tete"><span>Objectif 31 décembre : {_n(OBJECTIF)} abonnés</span><span>{100 * total / OBJECTIF:.1f} %</span></div>
        <div class="jauge"><i style="width:{min(100, max(1.5, 100 * total / OBJECTIF)):.1f}%"></i></div></div>
      {f'<div class="resume verre"><p class="sur" style="margin-bottom:2mm">En 5 phrases</p><div class="prose" style="column-count:1">{_markdown(cinq)}</div></div>' if cinq else ''}"""
    pages = [page(couverture, halo(120, -40, 140, "#C4B5FD") + halo(-50, 190, 120, "#BAE6FD"))]

    # 2. réseaux
    cartes = ""
    for k, nom, _ in RESEAUX:
        v = abonnes.get(k)
        pr = (s.get("posts_par_reseau") or {}).get(k) or {}
        pp = (prev.get("posts_par_reseau") or {}).get(k) or {}
        cartes += (f'<div class="reseau verre"><div class="nom"><span class="pt" style="background:{COULEURS[k]}"></span>{nom}</div>'
                   f'<strong>{_n(v) if isinstance(v, int) else "—"}</strong><small>abonnés · {pr.get("crees", 0)} posts cette semaine '
                   f'({pp.get("crees", 0)} la précédente)</small><div class="jauge" style="height:2.4mm"><i style="width:{min(100, max(1, 100 * (v or 0) / OBJECTIF)):.1f}%"></i></div></div>')
    formats = sorted(s.get("par_type_publication") or [], key=lambda x: -(x.get("portee_moyenne") or 0))[:7]
    bar_formats = _barres_h([(f"{x.get('reseau', '').title()} · {x.get('format_publication', '')}".replace("inconnu", "vidéo"),
                              float(x.get("portee_moyenne") or 0), COULEURS.get(x.get("reseau"), "#7C3AED")) for x in formats])
    ig = (stats.get("instagram") or {}).get("insights") or {}
    reseaux_html = f"""<p class="sur"><span class="num">01</span>Réseaux sociaux</p><h2>Où en sont nos comptes</h2>
      <p class="chapeau">Abonnés de chaque réseau, publications de la semaine et chemin vers {_n(OBJECTIF)} abonnés.</p>
      <div class="reseaux">{cartes}</div>
      <div class="bloc verre"><h3>Ce qui touche le plus de monde · portée moyenne par format</h3>{bar_formats}</div>
      {f'<div class="chiffres"><div class="verre"><strong>{_n(ig.get("reach"))}</strong><span>portée Instagram</span></div><div class="verre"><strong>{_n(ig.get("total_interactions"))}</strong><span>interactions Instagram</span></div><div class="verre"><strong>{_n(ig.get("profile_views"))}</strong><span>visites du profil</span></div></div>' if ig else ''}"""
    pages.append(page(reseaux_html, halo(150, 200, 110, "#DDD6FE")))

    # 3. publications
    top = sorted(posts, key=lambda x: -(x.get("vues") or 0))[:8]
    lignes = "".join(f'<div class="post verre"><span class="rang">{i + 1}</span><div><div class="t">{e(_titre_post(p.get("titre")))}</div>'
                     f'<span class="pill" style="background:{COULEURS.get(p.get("reseau"), "#7C3AED")}">{e(str(p.get("reseau") or "").title())}</span></div>'
                     f'<div class="m"><b>{_n(p.get("vues"))}</b><small>vues</small></div><div class="m"><b>{_n(p.get("portee"))}</b><small>portée</small></div></div>'
                     for i, p in enumerate(top))
    pages.append(page(f"""<p class="sur"><span class="num">02</span>Publications</p><h2>Le top de la semaine</h2>
      <p class="chapeau">Les {len(top)} publications les plus vues, tous réseaux confondus.</p><div class="top">{lignes or '<p>Aucune mesure disponible.</p>'}</div>""",
                      halo(-40, 60, 100, "#BAE6FD")))

    # 4. site
    jours = [(_jour(x.get("jour", ""), True), float(x.get("vues") or 0)) for x in s.get("visites_par_jour") or []]
    pages_vues = "".join(f'<tr><td>{e(x.get("path", ""))}</td><td class="n">{_n(x.get("vues"))}</td></tr>' for x in (s.get("pages_plus_vues") or [])[:10]
                         if not str(x.get("path", "")).startswith(("/studio/", "/live/")))
    site_html = f"""<p class="sur"><span class="num">03</span>Site cauricharts.com</p><h2>L'audience du site</h2>
      <p class="chapeau">{_n(s.get('visites', 0))} visiteurs cette semaine ({_n(prev.get('visites'))} la précédente). Les colonnes comptent toutes les pages vues, jour par jour.</p>
      <div class="bloc verre"><h3>Pages vues par jour</h3>{_colonnes(jours)}</div>
      <div class="deuxcol"><div class="bloc verre"><h3>Pages les plus visitées</h3><table><thead><tr><th>Page</th><th class="n">Vues</th></tr></thead><tbody>{pages_vues}</tbody></table></div>
      <div class="bloc verre"><h3>Le moteur Cauri</h3><table><tbody>
        <tr><td>Artistes suivis</td><td class="n">{_n(s.get('artistes_actifs'))}</td></tr>
        <tr><td>Classements officiels publiés</td><td class="n">{_n(s.get('classements_officiels_publies'))}</td></tr>
        <tr><td>Relevés des plateformes</td><td class="n">{_n(s.get('releves_classements'))}</td></tr>
        <tr><td>Actualités publiées</td><td class="n">{_n(s.get('actualites_publiees'))}</td></tr>
        <tr><td>Nuits de calcul</td><td class="n">{_n(s.get('nuits'))}</td></tr></tbody></table></div></div>"""
    pages.append(page(site_html, halo(140, 230, 120, "#C4B5FD")))

    # 5. analyse (2 colonnes, peut tenir sur plusieurs pages)
    pages.append(page(f"""<p class="sur"><span class="num">04</span>Analyse</p><h2>Ce qu'il faut retenir</h2>
      <div class="prose">{_markdown(analyse)}</div>""", longue=True))

    # 6. dépenses
    dep = "".join(f'<tr><td>{e(str(x.get("nom", "")))}</td><td class="n">{e(str(x.get("montant", "à confirmer")))} {e(str(x.get("devise", "")))}</td></tr>'
                  for x in data.get("depenses_semaine") or [])
    ech = "".join(f'<tr><td>{e(str(x.get("nom", "")))}</td><td>{e(_jour(str(x.get("prochaine_echeance", ""))))}</td><td class="n">{e(str(x.get("montant", "à confirmer")))}</td></tr>'
                  for x in data.get("echeances_mois_prochain") or [])
    pages.append(page(f"""<p class="sur"><span class="num">05</span>Finances</p><h2>Dépenses et échéances</h2>
      <p class="chapeau">Ce qui a été payé cette semaine et ce qui arrive le mois prochain.</p>
      <div class="bloc verre"><h3>Dépenses de la semaine</h3><table><thead><tr><th>Dépense</th><th class="n">Montant</th></tr></thead><tbody>{dep or '<tr><td colspan="2">Aucune dépense enregistrée.</td></tr>'}</tbody></table></div>
      <div class="bloc verre"><h3>Échéances du mois prochain</h3><table><thead><tr><th>Service</th><th>Échéance</th><th class="n">Montant</th></tr></thead><tbody>{ech or '<tr><td colspan="3">Aucune échéance.</td></tr>'}</tbody></table></div>""",
                      halo(-30, 220, 110, "#BAE6FD")))
    return f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{_css()}</style></head><body>{"".join(pages)}</body></html>'


def generer(data: dict, texte: str, destination: str | Path, exemple: bool = False) -> Path:
    """Génère le PDF A4 avec Chromium via Playwright (pieds de page dans les pages : marges nulles)."""
    from playwright.sync_api import sync_playwright
    cible = Path(destination)
    cible.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        navigateur = playwright.chromium.launch()
        page = navigateur.new_page()
        page.set_content(html_rapport(data, texte, exemple), wait_until="load")
        page.wait_for_timeout(400)
        page.pdf(path=str(cible), format="A4", print_background=True, prefer_css_page_size=True,
                 margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        navigateur.close()
    return cible
