"""Espace partenaire protégé par mot de passe : /espace/<slug> (09/11/2026, Nec+Ultra Media × Cauri Charts).

Tout sur la Côte d'Ivoire (ou les pays du partenaire) : faits marquants, classements officiels en cartes avec
pochettes et photos, classement complet des 100 titres de la semaine, artistes classés avec leurs chiffres,
téléchargements (PDF, Excel, visuels TV) et toutes les semaines publiées. Co-marquage : couleurs du pays,
de Cauri Charts et du partenaire. Jamais indexé, jamais mis en cache.
"""
import html

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token

from core import db, repos
from core.backoffice import auth
from core.services import partenaires as P

e = html.escape
DRAPEAUX = {"CI": ("#F77F00", "#FFFFFF", "#009E60"), "TG": ("#006A4E", "#FFCE00", "#D21034"), "SN": ("#00853F", "#FDEF42", "#E31B23"),
            "GH": ("#CE1126", "#FCD116", "#006B3F"), "NG": ("#008751", "#FFFFFF", "#008751"), "BJ": ("#008751", "#FCD116", "#E8112D")}
SESSION = "espace_partenaire_{}"


def _partenaire(slug: str) -> dict | None:
    try:
        P.assure_tables()
        return db.one("SELECT * FROM partenaires_acces WHERE slug = ? AND actif = 1 AND mdp_hash IS NOT NULL", [slug])
    except Exception:  # noqa: BLE001
        return None


def _reponse(contenu: str, status: int = 200) -> HttpResponse:
    r = HttpResponse(contenu, status=status)
    r["X-Robots-Tag"] = "noindex, nofollow"
    r["Cache-Control"] = "private, no-store"
    # « same-origin » : avec « no-referrer », le navigateur envoie « Origin: null » et le contrôle CSRF refuse le mot de passe
    r["Referrer-Policy"] = "same-origin"
    # styles intégrés et polices Google autorisés ici seulement (la politique du site les bloque), aucun script
    r["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    return r


def page(request, slug: str):
    p = _partenaire(slug)
    if not p:
        raise Http404
    cle = SESSION.format(p["id"])
    if request.GET.get("sortir") is not None:
        request.session.pop(cle, None)
        return HttpResponseRedirect(f"/espace/{slug}")
    erreur = ""
    if request.method == "POST":
        ip, compte = auth.client_ip(request), f"espace:{slug}"
        if auth.is_locked_out(compte, ip):
            erreur = "Trop d'essais. Réessayez dans 15 minutes."
        else:
            ok = auth.verify_password(request.POST.get("mot_de_passe", ""), p["mdp_hash"])
            auth._record(compte, ip, ok)
            if ok:
                request.session.cycle_key()
                request.session[cle] = True
                return HttpResponseRedirect(f"/espace/{slug}")
            erreur = "Mot de passe incorrect."
    if not request.session.get(cle):
        return _reponse(_connexion(request, p, erreur), 401 if erreur else 200)
    return _reponse(_espace(request, p))


# ---------------------------------------------------------------- mise en page

def _css(p: dict, pays: str) -> str:
    o, b, v = DRAPEAUX.get(pays, ("#F77F00", "#FFFFFF", "#009E60"))
    nec1, nec2 = p.get("couleur") or "#14141c", p.get("couleur2") or "#C9A227"
    return f"""
:root {{ --violet:#7c3aed; --ciel:#38bdf8; --nuit:#0c0b16; --gris:#6b6a7e; --ligne:#e7e5f0; --fond:#f7f7fb; --carte:#ffffff;
  --pays1:{o}; --pays2:{b}; --pays3:{v}; --nec:{nec1}; --nec2:{nec2}; color-scheme:light }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--fond); color:var(--nuit); font:16px/1.5 "DM Sans",system-ui,-apple-system,"Segoe UI",sans-serif }}
h1,h2,h3,.titre {{ font-family:"Montserrat",system-ui,sans-serif; text-wrap:balance }}
.drapeau {{ display:flex; height:8px }} .drapeau i {{ flex:1 }} .drapeau i:nth-child(1) {{ background:var(--pays1) }}
.drapeau i:nth-child(2) {{ background:var(--pays2) }} .drapeau i:nth-child(3) {{ background:var(--pays3) }}
.cauri {{ height:4px; background:linear-gradient(90deg,var(--ciel),var(--violet)) }}
.page {{ max-width:1180px; margin:0 auto; padding:0 max(16px,env(safe-area-inset-right)) 64px max(16px,env(safe-area-inset-left)) }}
.entete {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:16px; padding:22px 0 }}
.duo {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap }}
.marque {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:1.05rem; text-decoration:none; color:inherit }}
.marque__cauri {{ width:40px; height:40px; border-radius:10px; background:var(--violet); color:#fff; display:grid; place-items:center;
  font:800 .95rem Montserrat,sans-serif }}
.fois {{ color:var(--gris); font-size:1.2rem }}
.marque__nec {{ padding:8px 14px; border-radius:10px; background:var(--nec); color:var(--nec2); font:800 1rem Montserrat,sans-serif;
  letter-spacing:.04em }}
.marque__nec img {{ height:28px; display:block }}
.sortir {{ font-size:.85rem; color:var(--gris) }}
.hero {{ position:relative; overflow:hidden; border-radius:28px; padding:36px clamp(20px,4vw,48px); color:#fff;
  background:radial-gradient(120% 140% at 0% 0%, var(--pays1) 0%, transparent 55%),
             radial-gradient(120% 140% at 100% 100%, var(--pays3) 0%, transparent 55%),
             linear-gradient(135deg,var(--nec) 0%, #2a1660 55%, var(--violet) 100%) }}
.hero__sur {{ margin:0; font:700 .78rem Montserrat,sans-serif; letter-spacing:.16em; text-transform:uppercase; opacity:.9 }}
.hero h1 {{ margin:.25em 0 .2em; font-size:clamp(2rem,5.5vw,3.4rem); line-height:1.05 }}
.hero p {{ margin:0; max-width:62ch; opacity:.92 }}
.semaines {{ margin-top:22px; display:flex; flex-wrap:wrap; gap:8px; align-items:center }}
.semaines a {{ color:#fff; text-decoration:none; padding:6px 12px; border-radius:999px; border:1px solid rgba(255,255,255,.35); font-size:.88rem }}
.semaines a[aria-current] {{ background:#fff; color:var(--nuit); border-color:#fff; font-weight:700 }}
.faits {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; margin:22px 0 8px }}
.fait {{ background:var(--carte); border:1px solid var(--ligne); border-left:5px solid var(--pays1); border-radius:16px; padding:14px 16px }}
.fait:nth-child(3n+2) {{ border-left-color:var(--pays3) }} .fait:nth-child(3n) {{ border-left-color:var(--violet) }}
section {{ margin-top:44px }}
.section__tete {{ display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:8px; margin-bottom:14px }}
h2 {{ margin:0; font-size:clamp(1.35rem,3vw,1.8rem) }} .section__tete p {{ margin:0; color:var(--gris); font-size:.92rem }}
.podium {{ display:grid; grid-template-columns:minmax(0,1.05fr) minmax(0,2fr); gap:16px }}
@media (max-width:800px) {{ .podium {{ grid-template-columns:1fr }} }}
.un {{ background:var(--carte); border:1px solid var(--ligne); border-radius:24px; padding:18px; position:relative }}
.un img,.un .init {{ width:100%; aspect-ratio:1; object-fit:cover; border-radius:18px; display:block }}
.un .badge {{ position:absolute; top:28px; left:28px; background:var(--violet); color:#fff; font:800 1.1rem Montserrat,sans-serif;
  padding:6px 14px; border-radius:999px }}
.un h3 {{ margin:14px 0 2px; font-size:1.5rem; line-height:1.15 }} .un .qui {{ color:var(--gris) }}
.grille {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:12px; align-content:start }}
.carte {{ background:var(--carte); border:1px solid var(--ligne); border-radius:18px; padding:10px; position:relative; min-width:0 }}
.carte img,.carte .init {{ width:100%; aspect-ratio:1; object-fit:cover; border-radius:12px; display:block }}
.init {{ display:grid !important; place-items:center; background:linear-gradient(135deg,var(--violet),var(--ciel)); color:#fff;
  font:800 2rem Montserrat,sans-serif }}
.rang {{ position:absolute; top:16px; left:16px; min-width:36px; height:36px; padding:0 8px; border-radius:999px; background:var(--nuit);
  color:#fff; display:grid; place-items:center; font:800 1rem Montserrat,sans-serif }}
.carte h3 {{ margin:8px 2px 0; font-size:.98rem; line-height:1.2; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }}
.carte .qui {{ margin:0 2px; color:var(--gris); font-size:.85rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }}
.mv {{ display:inline-block; margin:6px 2px 0; font:800 .74rem Montserrat,sans-serif; padding:2px 8px; border-radius:999px; background:#f1effa }}
.mv--monte {{ color:#0f8a52; background:#e3f6ec }} .mv--baisse {{ color:#c2353b; background:#fbe9ea }} .mv--neuf {{ color:var(--violet) }}
.onglets {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px }}
.onglets a {{ text-decoration:none; color:inherit; padding:7px 14px; border-radius:999px; border:1px solid var(--ligne); background:#fff; font-size:.9rem }}
.table {{ overflow-x:auto; background:var(--carte); border:1px solid var(--ligne); border-radius:18px }}
table {{ width:100%; border-collapse:collapse; font-size:.93rem }} th,td {{ padding:9px 12px; text-align:left; border-bottom:1px solid var(--ligne) }}
th {{ font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; color:var(--gris); background:#fbfaff }}
td.n {{ font:800 1rem Montserrat,sans-serif; width:48px }} td img {{ width:40px; height:40px; border-radius:8px; object-fit:cover; display:block }}
td .qui {{ color:var(--gris); font-size:.84rem }} td.chiffre {{ font-variant-numeric:tabular-nums; white-space:nowrap }}
.telechargements {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px }}
.fichier {{ display:flex; flex-direction:column; padding:16px; border-radius:16px; border:1px solid var(--ligne); background:#fff; text-decoration:none;
  color:inherit }} .fichier:hover {{ border-color:var(--violet) }} .fichier span {{ color:var(--gris); font-size:.86rem }}
.pied {{ margin-top:56px; padding-top:20px; border-top:1px solid var(--ligne); color:var(--gris); font-size:.86rem; display:flex;
  flex-wrap:wrap; justify-content:space-between; gap:8px }}
.connexion {{ min-height:100vh; display:grid; place-items:center; padding:24px 16px }}
.boite {{ width:min(440px,100%); background:#fff; border:1px solid var(--ligne); border-radius:24px; overflow:hidden; box-shadow:0 20px 60px rgba(20,10,60,.10) }}
.boite__corps {{ padding:28px }} .boite h1 {{ margin:6px 0 4px; font-size:1.6rem }} .boite p {{ color:var(--gris); margin:0 0 18px }}
label {{ display:block; font-weight:700; font-size:.9rem; margin-bottom:6px }}
input[type=password] {{ width:100%; padding:13px 14px; border-radius:12px; border:1px solid var(--ligne); font:inherit }}
button {{ margin-top:14px; width:100%; padding:13px; border:0; border-radius:12px; background:var(--violet); color:#fff; font:700 1rem inherit; cursor:pointer }}
.erreur {{ color:#c2353b; font-weight:700 }}
"""


def _tete(p: dict, titre: str, pays: str) -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>{e(titre)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Montserrat:wght@700;800&display=swap" rel="stylesheet">
<style>{_css(p, pays)}</style></head><body>"""


def _marques(p: dict) -> str:
    nec = f'<img src="{e(p["logo_url"])}" alt="{e(p["nom"])}">' if p.get("logo_url") else e(p["nom"])
    return (f'<div class="duo"><span class="marque"><span class="marque__cauri">CC</span>Cauri Charts</span>'
            f'<span class="fois" aria-hidden="true">×</span><span class="marque__nec">{nec}</span></div>')


def _connexion(request, p: dict, erreur: str) -> str:
    pays = (p.get("pays") or "CI").split(",")[0] or "CI"
    return (_tete(p, f"Espace {p['nom']} · Cauri Charts", pays)
            + f"""<div class="drapeau"><i></i><i></i><i></i></div><div class="cauri"></div><main class="connexion"><div class="boite">
<div class="boite__corps">{_marques(p)}<h1>Espace réservé</h1>
<p>Les classements officiels de la {e(P.NOMS_PAYS.get(pays, pays))}, chaque semaine, dès leur publication.</p>
{f'<p class="erreur" role="alert">{e(erreur)}</p>' if erreur else ''}
<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{e(get_token(request))}">
<label for="mdp">Mot de passe</label><input id="mdp" type="password" name="mot_de_passe" autocomplete="current-password" required autofocus>
<button type="submit">Entrer</button></form></div><div class="drapeau"><i></i><i></i><i></i></div></div></main></body></html>""")


def _img(url: str, nom: str, cls: str = "") -> str:
    if url:
        return f'<img src="{e(url)}" alt="" loading="lazy" referrerpolicy="no-referrer"{f" class={cls}" if cls else ""}>'
    lettres = "".join(m[0] for m in (nom or "?").split()[:2]).upper()
    return f'<span class="init {cls}" aria-hidden="true">{e(lettres)}</span>'


def _mv(l: dict) -> str:
    m = P._mouvement(l)
    cls = "monte" if m.startswith("+") else "baisse" if m.startswith("-") else "neuf" if m in ("NOUVEAU", "RETOUR") else ""
    return f'<span class="mv mv--{cls}">{e(m)}</span>'


def _classement(c: dict) -> str:
    lignes = c["lignes"]
    if not lignes:
        return ""
    n1 = lignes[0]
    nom1 = n1["titre"] or n1["artiste"]
    qui1 = n1["artiste"] if n1["titre"] else f"points sur {n1['titres'] or 1} titre{'s' if (n1['titres'] or 1) > 1 else ''}"
    cartes = "".join(
        f'<article class="carte"><span class="rang">{l["rang"]}</span>{_img(l["image"], l["artiste"])}'
        f'<h3 title="{e(l["titre"] or l["artiste"])}">{e(l["titre"] or l["artiste"])}</h3>'
        f'<p class="qui">{e(l["artiste"] if l["titre"] else "points sur " + str(l["titres"] or 1) + " titres")}</p>{_mv(l)}</article>'
        for l in lignes[1:])
    return (f'<div class="podium"><article class="un"><span class="badge">N°1</span>{_img(n1["image"], n1["artiste"])}'
            f'<h3>{e(nom1)}</h3><div class="qui">{e(qui1)}</div>{_mv(n1)}</article><div class="grille">{cartes}</div></div>')


def _nombre(n) -> str:
    return f"{int(n):,}".replace(",", " ") if n else "—"


def _espace(request, p: dict) -> str:
    pays = (p.get("pays") or "CI").split(",")[0] or "CI"
    nom_pays = P.NOMS_PAYS.get(pays, pays)
    c = db.one("SELECT id FROM countries WHERE code = ?", [pays])
    cid = int(c["id"]) if c else None
    semaines = repos.published_runs(cid, "prime", "week", 30) if cid else []
    choisie = request.GET.get("semaine") or (semaines[0]["period_key"] if semaines else "")
    if semaines and choisie not in {s["period_key"] for s in semaines}:
        choisie = semaines[0]["period_key"]
    d = P.donnees(choisie, [pays]) if choisie else {"perimetres": [], "periode": None}
    local = next((x for x in d["perimetres"] if x["code"] == pays), None)
    periode = f"du {P._date_fr(d['periode'][0])} au {P._date_fr(d['periode'][1])}" if d.get("periode") else ""

    corps = [f"""<div class="drapeau"><i></i><i></i><i></i></div><div class="cauri"></div><div class="page">
<header class="entete">{_marques(p)}<a class="sortir" href="?sortir">Se déconnecter</a></header>
<div class="hero"><p class="hero__sur">{e(p['nom'])} × Cauri Charts · classements officiels</p>
<h1>{e(nom_pays)} · semaine {e(choisie[-2:]) if choisie else '—'}</h1><p>{e(periode)}. Données réelles relevées sur YouTube, Apple Music,
Boomplay, Spotify et les classements des plateformes, publiées chaque vendredi soir. Mention à l'antenne : « Source : Cauri Charts ».</p>
<nav class="semaines" aria-label="Semaines">""" + "".join(
        f'<a href="?semaine={e(s["period_key"])}"{" aria-current=page" if s["period_key"] == choisie else ""}>S{e(s["period_key"][-2:])}</a>'
        for s in semaines[:12]) + "</nav></div>"]

    if not local:
        corps.append('<section><p>Aucun classement publié pour le moment. La première édition arrive vendredi soir.</p></section>')
    else:
        corps.append('<div class="faits">' + "".join(f'<div class="fait">{e(f)}</div>' for f in local["faits"]) + "</div>")
        ancres = [(x["code"], x["nom"]) for x in local["classements"]]
        corps.append('<nav class="onglets" aria-label="Classements">' + "".join(f'<a href="#{e(k)}">{e(n)}</a>' for k, n in ancres)
                     + '<a href="#complet">Classement complet</a><a href="#artistes">Artistes</a><a href="#telechargements">Téléchargements</a></nav>')
        for x in local["classements"]:
            corps.append(f'<section id="{e(x["code"])}"><div class="section__tete"><h2>{e(x["nom"])}</h2>'
                         f'<p>{e(nom_pays)} · semaine {e(choisie[-2:])}</p></div>{_classement(x)}</section>')
        corps.append(_complet(cid, d["periode"][0] if d.get("periode") else None))
        corps.append(_artistes(cid, d["periode"][0] if d.get("periode") else None))
    corps.append(_telechargements(p))
    corps.append(f"""<footer class="pied"><span>Cauri Charts · la référence de la musique ouest-africaine · cauricharts.com</span>
<span>Espace réservé à {e(p['nom'])} · contact@cauricharts.com</span></footer></div></body></html>""")
    return _tete(p, f"{p['nom']} × Cauri Charts · {nom_pays}", pays) + "".join(corps)


def _complet(cid, debut) -> str:
    """Tous les titres de la semaine dans le pays, par score (titres vérifiés seulement)."""
    if not cid or not debut:
        return ""
    rows = db.all("""SELECT t.title, t.featuring, t.cover_url, a.name, COALESCE(a.image_hd_url, a.image_url) AS photo, ws.score
                     FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                     WHERE ws.country_id = ? AND ws.week_start = ? AND ws.score > 0 AND ws.review_status IN ('ok', 'validated')
                     ORDER BY ws.score DESC LIMIT 100""", [cid, debut])
    if not rows:
        return ""
    lignes = "".join(f'<tr><td class="n">{i}</td><td>{_img(r["cover_url"] or r["photo"], r["name"])}</td>'
                     f'<td><strong>{e(r["title"])}</strong><div class="qui">{e(r["name"])}{" feat. " + e(r["featuring"]) if r["featuring"] else ""}</div></td>'
                     f'<td class="chiffre">{_nombre(r["score"])}</td></tr>' for i, r in enumerate(rows, 1))
    return (f'<section id="complet"><div class="section__tete"><h2>Classement complet</h2><p>Les {len(rows)} titres de la semaine, '
            f'par score Cauri</p></div><div class="table"><table><thead><tr><th>Rang</th><th></th><th>Titre</th><th>Score</th></tr>'
            f'</thead><tbody>{lignes}</tbody></table></div></section>')


def _artistes(cid, debut) -> str:
    if not cid or not debut:
        return ""
    rows = db.all("""SELECT a.name, COALESCE(a.image_hd_url, a.image_url) AS photo, a.youtube_subscribers, a.fans,
                            SUM(ws.score) AS points, COUNT(*) AS titres
                     FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                     WHERE ws.country_id = ? AND ws.week_start = ? AND ws.score > 0 AND ws.review_status IN ('ok', 'validated')
                     GROUP BY a.id, a.name, photo, a.youtube_subscribers, a.fans ORDER BY points DESC LIMIT 60""", [cid, debut])
    if not rows:
        return ""
    lignes = "".join(f'<tr><td class="n">{i}</td><td>{_img(r["photo"], r["name"])}</td><td><strong>{e(r["name"])}</strong></td>'
                     f'<td class="chiffre">{_nombre(r["points"])}</td><td class="chiffre">{int(r["titres"])}</td>'
                     f'<td class="chiffre">{_nombre(r["youtube_subscribers"])}</td><td class="chiffre">{_nombre(r["fans"])}</td></tr>'
                     for i, r in enumerate(rows, 1))
    return (f'<section id="artistes"><div class="section__tete"><h2>Les artistes de la semaine</h2><p>Points de tous leurs titres, '
            f'abonnés YouTube et fans Deezer</p></div><div class="table"><table><thead><tr><th>Rang</th><th></th><th>Artiste</th>'
            f'<th>Points</th><th>Titres</th><th>Abonnés YouTube</th><th>Fans Deezer</th></tr></thead><tbody>{lignes}</tbody></table>'
            f'</div></section>')


def _telechargements(p: dict) -> str:
    eds = P.editions(int(p["id"]))
    if not eds:
        return ('<section id="telechargements"><div class="section__tete"><h2>Téléchargements</h2></div>'
                "<p>Le dossier de chaque semaine (PDF, Excel, visuels pour l'antenne) arrive ici dès la publication du vendredi soir.</p></section>")
    noms = {".pdf": ("Dossier PDF", "faits marquants et classements"), ".xlsx": ("Tableau Excel", "une feuille par classement"),
            ".zip": ("Visuels TV", "1920 x 1080, prêts pour l'antenne")}
    blocs = []
    for ed in eds[:8]:
        liens = "".join(f'<a class="fichier" href="{e(url)}" download><strong>{noms.get("." + nom.rsplit(".", 1)[-1], (nom, ""))[0]} · '
                        f'S{e(ed["semaine"][-2:])}</strong><span>{noms.get("." + nom.rsplit(".", 1)[-1], ("", ""))[1]}</span></a>'
                        for nom, url in ed["fichiers"].items())
        blocs.append(liens)
    return (f'<section id="telechargements"><div class="section__tete"><h2>Téléchargements</h2><p>Chaque semaine, dès la '
            f'publication</p></div><div class="telechargements">{"".join(blocs)}</div></section>')

