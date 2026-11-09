"""Espace privé d'un partenaire média : /partenaire/<jeton> (lien secret, sans mot de passe, jamais indexé).
Toutes les éditions envoyées, avec le PDF, le tableau Excel et les visuels pour l'antenne (09/11/2026)."""
import html

from django.http import Http404, HttpResponse

from core.services import partenaires as P

LIBELLES = {".pdf": ("Dossier PDF", "le dossier complet, faits marquants et classements"),
            ".xlsx": ("Tableau Excel", "tous les classements, une feuille par classement"),
            ".zip": ("Visuels TV", "1920 x 1080, prêts pour l'antenne")}


def page(request, jeton: str):
    p = P.par_jeton(jeton)
    if not p:
        raise Http404
    e = html.escape
    blocs = []
    for i, ed in enumerate(P.editions(int(p["id"]))):
        liens = []
        for nom, url in ed["fichiers"].items():
            ext = "." + nom.rsplit(".", 1)[-1]
            titre, detail = LIBELLES.get(ext, (nom, ""))
            liens.append(f'<a class="fichier" href="{e(url)}" download><strong>{titre}</strong><span>{detail}</span></a>')
        date = f"envoyée le {ed['envoye_le']:%d/%m/%Y à %H h %M} UTC" if ed.get("envoye_le") else "préparée"
        blocs.append(f'<section class="edition{" edition--derniere" if i == 0 else ""}"><h2>Semaine {e(ed["semaine"][-2:])} '
                     f'<small>{e(ed["semaine"][:4])} · {date}</small></h2><div class="fichiers">{"".join(liens)}</div></section>')
    corps = "".join(blocs) or '<p class="vide">La première édition arrivera ici dès la publication du vendredi soir (19 h GMT).</p>'
    contenu = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>Espace {e(p['nom'])} · Cauri Charts</title>
<style>
:root {{ --nuit:#080812; --violet:#7c3aed; --ciel:#38bdf8; --gris:#6b6b80; --ligne:#e6e4f0; }}
* {{ box-sizing:border-box }} body {{ margin:0; background:#f7f7fb; color:var(--nuit); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif }}
.bande {{ height:6px; background:linear-gradient(90deg,var(--ciel),var(--violet)) }}
main {{ max-width:880px; margin:0 auto; padding:40px max(16px,env(safe-area-inset-left)) 64px }}
.sur {{ margin:0; font-size:.78rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:var(--violet) }}
h1 {{ margin:.2em 0 .3em; font-size:clamp(1.8rem,5vw,2.6rem); line-height:1.1 }}
.intro {{ color:var(--gris); max-width:62ch; margin:0 0 32px }}
.edition {{ background:#fff; border:1px solid var(--ligne); border-radius:18px; padding:20px 22px; margin:0 0 16px }}
.edition--derniere {{ border-color:var(--violet); box-shadow:0 8px 30px rgba(124,58,237,.10) }}
h2 {{ margin:0 0 14px; font-size:1.25rem }} h2 small {{ font-weight:400; color:var(--gris); font-size:.85rem; margin-left:8px }}
.fichiers {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px }}
.fichier {{ display:flex; flex-direction:column; gap:2px; padding:14px 16px; border:1px solid var(--ligne); border-radius:14px;
  text-decoration:none; color:inherit; background:#fbfaff }}
.fichier:hover {{ border-color:var(--violet) }} .fichier span {{ font-size:.85rem; color:var(--gris) }}
.vide {{ color:var(--gris) }} footer {{ margin-top:40px; font-size:.85rem; color:var(--gris) }}
</style></head><body><div class="bande"></div><main>
<p class="sur">Cauri Charts · espace réservé</p><h1>{e(p['nom'])}</h1>
<p class="intro">Les classements officiels de chaque semaine, dès leur publication le vendredi soir : le dossier PDF, le tableau
Excel et les visuels pour l'antenne. Ce lien vous est personnel, merci de ne pas le partager. Mention à l'antenne :
« Source : Cauri Charts ».</p>
{corps}
<footer>Cauri Charts · la référence de la musique ouest-africaine · contact@cauricharts.com</footer>
</main></body></html>"""
    r = HttpResponse(contenu)
    r["X-Robots-Tag"] = "noindex, nofollow"
    r["Referrer-Policy"] = "no-referrer"
    r["Cache-Control"] = "private, no-store"
    return r
