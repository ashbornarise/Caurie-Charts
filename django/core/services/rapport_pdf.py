"""Mise en page et génération du rapport de marque en PDF."""
import base64
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _svg_barres(titre: str, valeurs: list[tuple[str, int]], couleur: str = "#2fa8ff") -> str:
    maximum = max([max(1, int(v or 0)) for _, v in valeurs] or [1])
    lignes = []
    for i, (nom, valeur) in enumerate(valeurs):
        y = 34 + i * 30
        largeur = 420 * max(0, int(valeur or 0)) / maximum
        lignes.append(f'<text x="8" y="{y + 12}" font-size="11">{html.escape(str(nom)[:26])}</text><rect x="190" y="{y}" width="{largeur:.1f}" height="18" rx="8" fill="{couleur}"/><text x="{198 + largeur:.1f}" y="{y + 13}" font-size="10">{int(valeur or 0)}</text>')
    return f'<svg viewBox="0 0 650 {max(70, 55 + 30 * len(valeurs))}" role="img"><text x="8" y="18" font-size="14" font-weight="bold">{html.escape(titre)}</text>{"".join(lignes)}</svg>'


def _logo() -> str:
    try:
        contenu = (ROOT / "public/assets/img/brand/logo.svg").read_bytes()
        return "data:image/svg+xml;base64," + base64.b64encode(contenu).decode("ascii")
    except OSError:
        return ""


def html_rapport(data: dict, texte: str, exemple: bool = False) -> str:
    s, prev = data["semaine"], data.get("semaine_precedente", {})
    reseaux = s.get("posts_par_reseau", {})
    posts = s.get("metriques_posts", [])
    stats = data.get("reseaux_stats", {})
    abonnements = []
    for nom in ("instagram", "facebook", "telegram", "tiktok"):
        bloc = stats.get(nom, {})
        cle = "member_count" if nom == "telegram" else "follower_count" if nom == "tiktok" else "followers_count"
        val = bloc.get(cle, "non disponible")
        if isinstance(val, int):
            abonnements.append((nom.title(), val))
    total_abonnes = sum(v for _, v in abonnements) if abonnements else "non disponible"
    marqueur = '<div class="demo">EXEMPLE · Données factices</div>' if exemple else ""
    def table(rows, headers):
        return "<table><thead><tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in headers) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{html.escape(str(x))}</td>" for x in row) + "</tr>" for row in rows) + "</tbody></table>"
    posts_reseau = _svg_barres("Publications par réseau", [(k, v.get("crees", 0)) for k, v in reseaux.items()])
    abonnes_svg = _svg_barres("Évolution des abonnés par réseau", abonnements, "#6b4dff")
    jours = s.get("visites_par_jour", [])
    visites_svg = _svg_barres("Visites du site, jour par jour", [(x.get("jour", ""), x.get("vues", 0)) for x in jours])
    top_svg = _svg_barres("Publications les plus vues", [(p.get("titre", "Publication"), p.get("vues", 0)) for p in posts[:5]])
    logo = _logo()
    dépenses = data.get("depenses_semaine", [])
    dep_rows = [(x.get("nom", ""), x.get("montant", "à confirmer"), x.get("devise", "")) for x in dépenses]
    echeances = data.get("echeances_mois_prochain", [])
    ech_rows = [(x.get("nom", ""), x.get("prochaine_echeance", "à confirmer"), x.get("montant", "à confirmer")) for x in echeances]
    return f'''<!doctype html><html lang="fr"><meta charset="utf-8"><style>
    @font-face{{font-family:Inter;src:url("{(ROOT / 'public/assets/machine/fonts/inter.woff2').as_uri()}")}}@font-face{{font-family:Anton;src:url("{(ROOT / 'public/assets/machine/fonts/anton-normal-400.woff2').as_uri()}")}}
    *{{box-sizing:border-box}}body{{margin:0;color:#0d1330;font:11pt Inter,Arial,sans-serif;overflow-wrap:anywhere}}.cover{{height:270mm;padding:20mm;display:flex;flex-direction:column;justify-content:space-between;background:linear-gradient(150deg,#fff 65%,#edf7ff)}}.logo{{max-width:190px;max-height:55px}}.eyebrow{{color:#6b4dff;font-weight:bold;letter-spacing:2px}}h1{{font:48pt Anton,Arial,sans-serif;margin:8mm 0;color:#0d1330}}h2{{font:22pt Anton,Arial,sans-serif;margin:12mm 0 5mm;color:#0d1330;border-bottom:2px solid #2fa8ff;padding-bottom:3mm}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:5mm}}.card{{padding:7mm;border-radius:5mm;background:#fff;border:1px solid #dcecff}}.card strong{{display:block;color:#6b4dff;font:24pt Anton,Arial}}.demo{{position:fixed;top:10mm;right:10mm;padding:3mm 6mm;background:#6b4dff;color:white;font-weight:bold;z-index:2}}section{{padding:0 18mm}}h2{{break-after:avoid}}svg,table,tr,.card{{break-inside:avoid}}li,p{{orphans:3;widows:3}}svg{{width:100%;height:auto;max-height:95mm;margin:4mm 0}}table{{border-collapse:collapse;width:100%;margin:4mm 0 8mm}}th{{background:#edf7ff;color:#0d1330}}td,th{{border-bottom:1px solid #dce4f2;padding:3mm;text-align:left}}.prose p{{line-height:1.55}}.prose ul{{line-height:1.6}}.footer{{position:fixed;bottom:8mm;left:18mm;right:18mm;color:#56617e;font-size:9pt;border-top:1px solid #dce4f2;padding-top:3mm}}
    </style><body>{marqueur}<div class="cover"><header>{f'<img class="logo" src="{logo}">' if logo else '<b>Cauri Charts</b>'}<p class="eyebrow">RAPPORT HEBDOMADAIRE</p><h1>La semaine<br>{html.escape(s.get('debut',''))} — {html.escape(s.get('fin',''))}</h1><div class="cards"><div class="card"><strong>{total_abonnes}</strong>abonnés totaux</div><div class="card"><strong>{sum(int(p.get('vues') or 0) for p in posts)}</strong>vues</div><div class="card"><strong>{s.get('posts_crees',0)}</strong>posts créés</div><div class="card"><strong>{s.get('visites',0)}</strong>visites du site</div></div></header><p>Cauri Charts · la référence de la musique ouest-africaine</p></div>
    <section><h2>Réseaux sociaux</h2>{posts_reseau}{abonnes_svg}<p>Objectif : progression vers 10 000 abonnés au 31 décembre 2026.</p></section><section><h2>Audience du site</h2>{visites_svg}{table([(x.get('path',''), x.get('vues',0)) for x in s.get('pages_plus_vues',[])],['Page','Vues'])}</section><section><h2>Top publications</h2>{top_svg}{table([(p.get('titre',''),p.get('reseau',''),p.get('vues',0),p.get('portee',0)) for p in sorted(posts,key=lambda x:-(x.get('vues') or 0))[:8]],['Publication','Réseau','Vues','Portée'])}</section><section><h2>Analyse de la semaine</h2><div class="prose">{__import__('core.services.rapport',fromlist=['_markdown'])._markdown(texte)}</div></section><section><h2>Dépenses</h2>{table(dep_rows,['Dépense','Montant','Devise'])}<h2>Échéances du mois prochain</h2>{table(ech_rows,['Service','Échéance','Montant'])}</section></body></html>'''


def generer(data: dict, texte: str, destination: str | Path, exemple: bool = False) -> Path:
    """Génère un PDF A4 avec Chromium via Playwright."""
    from playwright.sync_api import sync_playwright
    cible = Path(destination)
    cible.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        navigateur = playwright.chromium.launch()
        page = navigateur.new_page()
        page.set_content(html_rapport(data, texte, exemple), wait_until="load")
        page.pdf(path=str(cible), format="A4", print_background=True, display_header_footer=True,
                 footer_template='<div style="width:100%;font:9px Arial;color:#56617e;padding:0 18mm;border-top:1px solid #dce4f2">Cauri Charts · la référence de la musique ouest-africaine <span style="float:right">Page <span class="pageNumber"></span></span></div>',
                 header_template="<div></div>", margin={"top": "14mm", "bottom": "18mm", "left": "0", "right": "0"})
        navigateur.close()
    return cible
