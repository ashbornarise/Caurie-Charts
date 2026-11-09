"""Espace partenaire protégé par mot de passe : /espace/<slug> (Nec+Ultra Media × Cauri Charts).

Refonte du 09/11/2026 : un portail en onglets plutôt qu'une longue page.
  Vue d'ensemble · Classements (un classement à la fois) · Top 100 · Artistes · Téléchargements
Navigation par liens (?vue=, ?c=, ?semaine=) : aucun script, la page reste sous une politique de sécurité stricte.
Couleurs : Cauri (violet, interface) · partenaire (noir et or : bandeau et n°1) · pays (drapeau, mouvements).
Jamais indexé, jamais mis en cache.
"""
import html
from urllib.parse import urlencode

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token

from core import db, repos
from core.backoffice import auth
from core.services import partenaires as P

e = html.escape
DRAPEAUX = {"CI": ("#F77F00", "#FFFFFF", "#009E60"), "TG": ("#006A4E", "#FFCE00", "#D21034"), "SN": ("#00853F", "#FDEF42", "#E31B23"),
            "GH": ("#CE1126", "#FCD116", "#006B3F"), "NG": ("#008751", "#FFFFFF", "#008751"), "BJ": ("#008751", "#FCD116", "#E8112D")}
SESSION = "espace_partenaire_{}"
VUES = [("accueil", "Vue d'ensemble"), ("classements", "Classements"), ("top100", "Top 100"), ("artistes", "Artistes"),
        ("fichiers", "Téléchargements")]
DESCRIPTIONS = {
    "prime": "Le classement officiel : les titres les plus forts de la semaine.",
    "icon": "Les artistes classés par les points de tous leurs titres additionnés.",
    "saison": "Les points des artistes additionnés semaine après semaine depuis le début de la saison.",
    "buzz": "Les plus fortes progressions de la semaine parmi les titres absents du classement officiel.",
    "fresh": "Les titres sortis depuis moins de 8 semaines et les artistes émergents.",
}
FICHIERS = {"pdf": ("Dossier PDF", "Faits marquants et classements"), "xlsx": ("Tableau Excel", "Une feuille par classement"),
            "zip": ("Visuels TV", "1920 × 1080, prêts pour l'antenne")}


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


# ---------------------------------------------------------------- styles

CSS = """
:root { --encre:#121118; --encre2:#4a4858; --doux:#77748a; --ligne:#e9e7f1; --fond:#f6f5fa; --carte:#ffffff;
  --violet:#8B52FF; --violet-fond:#f1ebff; --ciel:#38bdf8;
  --pays1:__P1__; --pays2:__P2__; --pays3:__P3__; --nec:__N1__; --or:__N2__;
  --monte:#0b7d4b; --monte-fond:#e3f5ec; --baisse:#c2353b; --baisse-fond:#fcebec; --neuf:#b45300; --neuf-fond:#fff0e0;
  --serif:"Bodoni Moda","Bodoni 72",Didot,Georgia,serif; --sans:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  color-scheme:light }
* { box-sizing:border-box }
body { margin:0; background:var(--fond); color:var(--encre); font:15px/1.5 var(--sans); -webkit-font-smoothing:antialiased }
a { color:inherit }
img { max-width:100% }
.serif { font-family:var(--serif) }
h1,h2,h3 { text-wrap:balance; margin:0 }
.cadre { max-width:1160px; margin:0 auto; padding-left:max(20px,env(safe-area-inset-left,0px)); padding-right:max(20px,env(safe-area-inset-right,0px)) }

/* bandeau partenaire */
.bandeau { background:var(--nec); color:#fff }
.bandeau .cadre { display:flex; align-items:center; justify-content:space-between; gap:16px; padding-block:16px; flex-wrap:wrap }
.duo { display:flex; align-items:center; gap:16px; min-width:0 }
.duo__cauri { height:30px; width:auto; display:block }
.duo__x { width:1px; height:30px; background:rgba(255,255,255,.22) }
.duo__nec { font:600 1.15rem/1 var(--serif); letter-spacing:.04em; color:var(--or); white-space:nowrap }
.duo__nec img { height:30px; width:auto; display:block }
.bandeau__droite { display:flex; align-items:center; gap:18px; font-size:.82rem; color:rgba(255,255,255,.7) }
.bandeau__droite a { color:#fff; text-decoration:none; padding:7px 12px; border:1px solid rgba(255,255,255,.22); border-radius:999px }
.bandeau__droite a:hover { border-color:var(--or) }
.drapeau { display:flex; height:4px } .drapeau i { flex:1 }
.drapeau i:nth-child(1) { background:var(--pays1) } .drapeau i:nth-child(2) { background:var(--pays2) } .drapeau i:nth-child(3) { background:var(--pays3) }
.mini-drapeau { display:inline-flex; width:22px; height:15px; border-radius:3px; overflow:hidden; box-shadow:0 0 0 1px rgba(0,0,0,.08); vertical-align:-2px }
.mini-drapeau i { flex:1 } .mini-drapeau i:nth-child(1) { background:var(--pays1) } .mini-drapeau i:nth-child(2) { background:var(--pays2) }
.mini-drapeau i:nth-child(3) { background:var(--pays3) }

/* barre de navigation */
.barre { position:sticky; top:0; z-index:5; background:rgba(255,255,255,.92); backdrop-filter:blur(12px); border-bottom:1px solid var(--ligne) }
.barre .cadre { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap }
.onglets { display:flex; gap:4px; overflow-x:auto; scrollbar-width:none; margin-bottom:-1px }
.onglets::-webkit-scrollbar { display:none }
.onglets a { text-decoration:none; padding:16px 14px 14px; font-weight:600; font-size:.92rem; color:var(--doux); border-bottom:3px solid transparent; white-space:nowrap }
.onglets a:hover { color:var(--encre) }
.onglets a[aria-current] { color:var(--encre); border-bottom-color:var(--violet) }
.semaine { display:flex; align-items:center; gap:6px; padding-block:8px }
.semaine a, .semaine span.off { display:grid; place-items:center; width:34px; height:34px; border-radius:999px; border:1px solid var(--ligne);
  text-decoration:none; font-size:1.1rem; color:var(--encre); background:#fff }
.semaine a:hover { border-color:var(--violet); color:var(--violet) }
.semaine span.off { color:#cfcbe0 }
.semaine strong { font-size:.9rem; padding:0 6px; white-space:nowrap }

main { padding-block:32px 56px }
.titre { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; flex-wrap:wrap; margin-bottom:24px }
.sur { margin:0 0 6px; font-size:.75rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:var(--doux);
  display:flex; align-items:center; gap:8px }
.titre h1 { font:700 clamp(2rem,4.6vw,3rem)/1.02 var(--serif) }
.titre p.periode { margin:6px 0 0; color:var(--encre2) }
.actions { display:flex; gap:8px; flex-wrap:wrap }
.bouton { display:inline-flex; align-items:center; gap:8px; padding:11px 16px; border-radius:12px; font-weight:600; font-size:.9rem;
  text-decoration:none; border:1px solid var(--ligne); background:#fff; color:var(--encre) }
.bouton:hover { border-color:var(--violet) }
.bouton--plein { background:var(--violet); border-color:var(--violet); color:#fff }
.bouton--plein:hover { background:#7a3ff5 }
.bouton svg { width:17px; height:17px; flex:none }
.note { color:var(--doux); font-size:.88rem; margin:0 }

/* vue d'ensemble : le n°1 et les faits */
.une { display:grid; grid-template-columns:minmax(0,1.15fr) minmax(0,1fr); gap:16px }
@media (max-width:860px) { .une { grid-template-columns:1fr } }
.vedette { position:relative; display:grid; grid-template-columns:minmax(0,220px) minmax(0,1fr); gap:22px; align-items:center;
  background:var(--nec); color:#fff; border-radius:22px; padding:22px; overflow:hidden; text-decoration:none }
.vedette::after { content:""; position:absolute; inset:auto -60px -80px auto; width:260px; height:260px; border-radius:50%;
  background:radial-gradient(circle,rgba(139,82,255,.45),transparent 70%); pointer-events:none }
@media (max-width:520px) { .vedette { grid-template-columns:110px minmax(0,1fr); gap:14px; padding:14px; border-radius:18px }
  .vedette h2 { font-size:1.35rem; margin-top:10px } .stats { gap:14px } .stats b { font-size:1.1rem } }
@media (max-width:640px) { .bandeau__droite span { display:none } .bandeau .cadre { flex-wrap:nowrap } .duo { gap:10px } .duo__cauri { height:24px } .duo__x { height:24px } .duo__nec { font-size:.92rem } .bandeau__droite a { padding:6px 10px; font-size:.78rem } .barre .semaine { margin-left:auto } }
.vedette .visuel { width:100%; aspect-ratio:1; border-radius:14px; object-fit:cover; display:block; box-shadow:0 18px 40px rgba(0,0,0,.35) }
.couronne { display:inline-flex; align-items:center; gap:6px; background:var(--or); color:var(--nec); font:700 .78rem var(--sans);
  letter-spacing:.1em; text-transform:uppercase; padding:5px 10px; border-radius:999px }
.vedette h2 { font:700 clamp(1.6rem,3.4vw,2.3rem)/1.05 var(--serif); margin:14px 0 6px }
.vedette .qui { color:rgba(255,255,255,.78); font-size:1rem }
.vedette .detail { margin-top:14px; font-size:.86rem; color:rgba(255,255,255,.7) }
.faits { display:grid; gap:12px }
.fait { display:grid; grid-template-columns:72px minmax(0,1fr); gap:14px; align-items:center; background:var(--carte);
  border:1px solid var(--ligne); border-radius:18px; padding:12px }
.fait img,.fait .init { width:72px; height:72px; border-radius:12px; object-fit:cover; display:block }
.fait small { display:block; font-size:.7rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--doux) }
.fait strong { display:block; font-size:1rem; line-height:1.25; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.fait span.qui { display:block; color:var(--encre2); font-size:.86rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.fait .mv { margin-top:4px }

.deux { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-top:16px }
@media (max-width:860px) { .deux { grid-template-columns:1fr } }
.bloc { background:var(--carte); border:1px solid var(--ligne); border-radius:22px; padding:20px }
.bloc__tete { display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin-bottom:8px }
.bloc__tete h2 { font:700 1.35rem/1.1 var(--serif) }
.lien { color:var(--violet); font-weight:600; font-size:.88rem; text-decoration:none; white-space:nowrap }
.lien:hover { text-decoration:underline }
.liste { list-style:none; margin:0; padding:0 }
.liste li { display:grid; grid-template-columns:28px 48px minmax(0,1fr) auto; gap:12px; align-items:center; padding:9px 0; border-top:1px solid var(--ligne) }
.liste li:first-child { border-top:0 }
.liste .n { font:700 1.15rem var(--serif); text-align:center }
.liste img,.liste .init { width:48px; height:48px; border-radius:10px; object-fit:cover; display:block }
.liste strong { display:block; font-size:.95rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.liste span.qui { display:block; color:var(--doux); font-size:.84rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.aussi { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; margin-top:16px }
.aussi a { text-decoration:none }
.aussi .fait:hover { border-color:var(--violet) }

/* mouvements */
.mv { display:inline-block; font:700 .72rem/1 var(--sans); padding:5px 8px; border-radius:999px; background:#f1f0f6; color:var(--encre2); white-space:nowrap }
.mv--monte { color:var(--monte); background:var(--monte-fond) } .mv--baisse { color:var(--baisse); background:var(--baisse-fond) }
.mv--neuf { color:var(--neuf); background:var(--neuf-fond) }

/* classements */
.puces { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:22px }
.puces a { text-decoration:none; padding:8px 14px; border-radius:999px; border:1px solid var(--ligne); background:#fff; font-weight:600; font-size:.88rem; color:var(--encre2) }
.puces a:hover { border-color:var(--violet) }
.puces a[aria-current] { background:var(--encre); border-color:var(--encre); color:#fff }
.chart-tete { margin-bottom:18px } .chart-tete h2 { font:700 clamp(1.6rem,3.6vw,2.2rem)/1.05 var(--serif) }
.chart-tete p { margin:6px 0 0; color:var(--encre2); max-width:65ch }
.stats { display:flex; gap:22px; flex-wrap:wrap; margin-top:16px }
.stats div { font-size:.78rem; color:rgba(255,255,255,.65); text-transform:uppercase; letter-spacing:.1em; font-weight:600 }
.stats b { display:block; font:700 1.35rem/1.1 var(--serif); color:#fff; text-transform:none; letter-spacing:0; margin-top:4px }
.grille { display:grid; grid-template-columns:repeat(auto-fill,minmax(168px,1fr)); gap:14px; margin-top:16px }
@media (max-width:520px) { .grille { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px } }
.carte { background:var(--carte); border:1px solid var(--ligne); border-radius:18px; padding:8px 8px 12px; min-width:0 }
.carte__img { position:relative }
.carte__img img,.carte__img .init { width:100%; aspect-ratio:1; border-radius:12px; object-fit:cover; display:block }
.carte .rang { position:absolute; left:8px; bottom:8px; min-width:34px; height:34px; padding:0 8px; border-radius:999px; background:var(--encre);
  color:#fff; display:grid; place-items:center; font:700 1rem var(--serif); box-shadow:0 4px 12px rgba(0,0,0,.25) }
.carte .mv { position:absolute; right:8px; top:8px; box-shadow:0 2px 8px rgba(0,0,0,.12) }
.carte h3 { margin:10px 4px 0; font-size:.93rem; line-height:1.25; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.carte p { margin:2px 4px 0; color:var(--doux); font-size:.82rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }

/* tableaux */
.table { background:var(--carte); border:1px solid var(--ligne); border-radius:20px; overflow:hidden }
table { width:100%; border-collapse:collapse; font-size:.92rem }
th,td { padding:9px 14px; text-align:left; border-bottom:1px solid var(--ligne) }
tbody tr:last-child td { border-bottom:0 }
th { font-size:.7rem; letter-spacing:.12em; text-transform:uppercase; color:var(--doux); background:#fbfafd; font-weight:700 }
td.n { font:700 1.05rem var(--serif); width:56px; text-align:center }
td.n--or { color:var(--or) }
td.qui { min-width:0 }
.ident { display:flex; align-items:center; gap:12px; min-width:0 }
.ident img,.ident .init { width:42px; height:42px; border-radius:9px; object-fit:cover; flex:none; display:block }
.ident strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.ident span { display:block; color:var(--doux); font-size:.83rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.ident > div { min-width:0 }
td.c, th.c { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap }
table { table-layout:fixed }
@media (max-width:640px) { .cache-mobile { display:none } th,td { padding:8px 10px } td.n { width:40px } }

/* podium artistes */
.podium { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin-bottom:16px }
@media (max-width:640px) { .podium { grid-template-columns:1fr } }
.marche { display:grid; grid-template-columns:84px minmax(0,1fr); gap:14px; align-items:center; background:var(--carte); border:1px solid var(--ligne);
  border-radius:20px; padding:14px }
.marche--1 { background:var(--nec); color:#fff; border-color:var(--nec) }
.marche img,.marche .init { width:84px; height:84px; border-radius:50%; object-fit:cover; display:block }
.marche--1 img { box-shadow:0 0 0 3px var(--or) }
.marche small { font-size:.7rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--doux) }
.marche--1 small { color:var(--or) }
.marche strong { display:block; font:700 1.25rem/1.15 var(--serif); margin:2px 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.marche span { font-size:.85rem; color:var(--doux) } .marche--1 span { color:rgba(255,255,255,.7) }

/* téléchargements */
.editions { display:grid; gap:12px }
.edition { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; background:var(--carte);
  border:1px solid var(--ligne); border-radius:20px; padding:18px 20px }
.edition--courante { border-color:var(--violet); box-shadow:0 10px 30px rgba(139,82,255,.10) }
.edition h3 { font:700 1.3rem/1.1 var(--serif) } .edition p { margin:4px 0 0; color:var(--doux); font-size:.86rem }
.vide { background:var(--carte); border:1px dashed var(--ligne); border-radius:20px; padding:28px; color:var(--encre2) }

.init { display:grid !important; place-items:center; background:linear-gradient(135deg,var(--violet),var(--ciel)); color:#fff; font:700 1.2rem var(--serif) }
.pages { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; margin-top:16px }
.pages a { text-decoration:none; padding:8px 14px; border-radius:999px; border:1px solid var(--ligne); background:#fff; font-weight:600; font-size:.85rem; color:var(--encre2) }
.pages a[aria-current] { background:var(--encre); color:#fff; border-color:var(--encre) }
.pied { border-top:1px solid var(--ligne); background:#fff }
.pied .cadre { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; padding-block:20px; font-size:.83rem; color:var(--doux) }

/* connexion */
.connexion { min-height:100vh; padding:0 !important; display:grid; grid-template-columns:minmax(0,1.1fr) minmax(0,1fr); background:#fff }
@media (max-width:860px) { .connexion { grid-template-columns:1fr } }
.connexion__marque { position:relative; overflow:hidden; background:var(--nec); color:#fff; display:flex; flex-direction:column;
  justify-content:space-between; gap:40px; padding:40px max(28px,env(safe-area-inset-left,0px)) }
.connexion__marque::before { content:""; position:absolute; width:520px; height:520px; right:-200px; top:-160px; border-radius:50%;
  background:radial-gradient(circle,rgba(139,82,255,.42),transparent 68%) }
.connexion__marque::after { content:""; position:absolute; left:0; right:0; bottom:0; height:6px;
  background:linear-gradient(90deg,var(--pays1) 0 33.3%,var(--pays2) 33.3% 66.6%,var(--pays3) 66.6%) }
.connexion__marque > * { position:relative }
.connexion__marque h1 { font:700 clamp(2.1rem,4.4vw,3.4rem)/1.04 var(--serif); max-width:15ch }
.connexion__marque p { color:rgba(255,255,255,.72); max-width:46ch; margin:14px 0 0 }
.connexion__pied { font-size:.82rem; color:rgba(255,255,255,.55) }
.connexion__form { display:grid; place-items:center; padding:40px max(24px,env(safe-area-inset-right,0px)) }
.connexion__form form { width:min(380px,100%) }
.connexion__form h2 { font:700 1.8rem/1.1 var(--serif); margin-bottom:6px }
.connexion__form p { color:var(--doux); margin:0 0 24px }
label { display:block; font-weight:600; font-size:.88rem; margin-bottom:8px }
input[type=password] { width:100%; padding:14px 16px; border-radius:12px; border:1px solid #d9d6e5; font:inherit; font-size:1rem; background:#fff }
input[type=password]:focus { outline:3px solid var(--violet-fond); border-color:var(--violet) }
button { margin-top:16px; width:100%; padding:14px; border:0; border-radius:12px; background:var(--violet); color:#fff; font:600 1rem var(--sans); cursor:pointer }
button:hover { background:#7a3ff5 }
.erreur { background:var(--baisse-fond); color:var(--baisse); font-weight:600; padding:10px 14px; border-radius:10px; margin:0 0 16px }
:focus-visible { outline:3px solid var(--violet); outline-offset:2px }
"""

ICONE_DL = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>')


def _css(p: dict, pays: str) -> str:
    o, b, v = DRAPEAUX.get(pays, DRAPEAUX["CI"])
    return (CSS.replace("__P1__", o).replace("__P2__", b).replace("__P3__", v)
            .replace("__N1__", p.get("couleur") or "#14141c").replace("__N2__", p.get("couleur2") or "#C9A227"))


def _tete(p: dict, titre: str, pays: str) -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>{e(titre)}</title><link rel="icon" href="/assets/img/brand/favicon-32.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,600;6..96,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_css(p, pays)}</style></head><body>"""


def _duo(p: dict) -> str:
    nec = f'<img src="{e(p["logo_url"])}" alt="{e(p["nom"])}">' if p.get("logo_url") else e(p["nom"].replace(" Media", "").upper())
    return (f'<div class="duo"><img class="duo__cauri" src="/assets/img/brand/logo-white.svg" alt="Cauri Charts" width="68" height="30">'
            f'<span class="duo__x" aria-hidden="true"></span><span class="duo__nec">{nec}</span></div>')


def _drapeau(cls: str = "drapeau") -> str:
    return f'<span class="{cls}" aria-hidden="true"><i></i><i></i><i></i></span>'


def _connexion(request, p: dict, erreur: str) -> str:
    pays = (p.get("pays") or "CI").split(",")[0] or "CI"
    nom_pays = P.NOMS_PAYS.get(pays, pays)
    return (_tete(p, f"Espace {p['nom']} · Cauri Charts", pays) + f"""<main class="connexion">
<section class="connexion__marque">{_duo(p)}<div><p class="sur" style="color:rgba(255,255,255,.6)">{_drapeau("mini-drapeau")} {e(nom_pays)} · espace partenaire</p>
<h1>Les classements de la {e(nom_pays)}, chaque semaine.</h1>
<p>Classements officiels, faits marquants, artistes de la semaine et dossiers prêts pour l'antenne, réservés à {e(p['nom'])}.</p></div>
<p class="connexion__pied">Cauri Charts · la référence de la musique ouest-africaine</p></section>
<section class="connexion__form"><form method="post"><h2>Connexion</h2><p>Entrez le mot de passe qui vous a été remis.</p>
{f'<p class="erreur" role="alert">{e(erreur)}</p>' if erreur else ''}
<input type="hidden" name="csrfmiddlewaretoken" value="{e(get_token(request))}">
<label for="mdp">Mot de passe</label><input id="mdp" type="password" name="mot_de_passe" autocomplete="current-password" required autofocus>
<button type="submit">Accéder à l'espace</button></form></section></main></body></html>""")


# ---------------------------------------------------------------- petits éléments

def _img(url: str, nom: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    if url:
        return f'<img src="{e(url)}" alt="" loading="lazy" referrerpolicy="no-referrer"{c}>'
    lettres = "".join(m[0] for m in (nom or "?").split()[:2]).upper()
    return f'<span class="init{" " + cls if cls else ""}" aria-hidden="true">{e(lettres)}</span>'


def _mv(l: dict) -> str:
    m = P._mouvement(l)
    if m == "NOUVEAU":
        return '<span class="mv mv--neuf">Entrée</span>'
    if m == "RETOUR":
        return '<span class="mv mv--neuf">Retour</span>'
    cls = "monte" if m.startswith("+") else "baisse" if m.startswith("-") else ""
    texte = {"=": "="}.get(m, m.replace("-", "−"))
    return f'<span class="mv mv--{cls}" title="Évolution depuis la semaine passée">{e(texte)}</span>'


def _nombre(n) -> str:
    return f"{int(n):,}".replace(",", " ") if n else "—"


def _nom(l: dict) -> str:
    return l["titre"] or l["artiste"]


def _qui(l: dict) -> str:
    if l["titre"]:
        return l["artiste"] + (f" feat. {l['feat']}" if l.get("feat") else "")
    n = l["titres"] or 1
    return f"points sur {n} titre{'s' if n > 1 else ''}"


# ---------------------------------------------------------------- la page

def _espace(request, p: dict) -> str:
    pays = (p.get("pays") or "CI").split(",")[0] or "CI"
    nom_pays = P.NOMS_PAYS.get(pays, pays)
    c = db.one("SELECT id FROM countries WHERE code = ?", [pays])
    cid = int(c["id"]) if c else None
    semaines = [s["period_key"] for s in (repos.published_runs(cid, "prime", "week", 30) if cid else [])]
    choisie = request.GET.get("semaine") or (semaines[0] if semaines else "")
    if semaines and choisie not in semaines:
        choisie = semaines[0]
    vue = request.GET.get("vue") if request.GET.get("vue") in dict(VUES) else "accueil"
    d = P.donnees(choisie, [pays]) if choisie else {"perimetres": [], "periode": None}
    local = next((x for x in d["perimetres"] if x["code"] == pays), None)
    debut = d["periode"][0] if d.get("periode") else None
    periode = f"Du {P._date_fr(d['periode'][0])} au {P._date_fr(d['periode'][1])}" if d.get("periode") else ""
    editions = P.editions(int(p["id"]))
    edition = next((x for x in editions if x["semaine"] == choisie), None)

    def u(**kw) -> str:
        q = {"semaine": choisie, "vue": vue}
        q.update(kw)
        q = {k: v for k, v in q.items() if v and not (k == "vue" and v == "accueil")}
        return "?" + urlencode(q) if q else "?"

    # semaine précédente / suivante
    i = semaines.index(choisie) if choisie in semaines else -1
    avant = semaines[i + 1] if 0 <= i < len(semaines) - 1 else None
    apres = semaines[i - 1] if i > 0 else None
    fleche = lambda s, sens, t: (f'<a href="{e(u(semaine=s))}" aria-label="{t} (S{e(s[-2:])})">{sens}</a>' if s
                                 else f'<span class="off" aria-hidden="true">{sens}</span>')
    nav_semaine = (f'<div class="semaine">{fleche(avant, "‹", "Semaine précédente")}<strong>Semaine {e(choisie[-2:]) if choisie else "—"}'
                   f'</strong>{fleche(apres, "›", "Semaine suivante")}</div>')
    onglets = "".join(f'<a href="{e(u(vue=k, c=None))}"{" aria-current=page" if k == vue else ""}>{t}</a>' for k, t in VUES)

    html_ = [f"""<header class="bandeau"><div class="cadre">{_duo(p)}<div class="bandeau__droite"><span>Espace partenaire</span>
<a href="?sortir">Se déconnecter</a></div></div></header>{_drapeau()}
<div class="barre"><div class="cadre"><nav class="onglets" aria-label="Rubriques">{onglets}</nav>{nav_semaine}</div></div>
<main class="cadre">"""]

    titre = {"accueil": f"Semaine {choisie[-2:]}" if choisie else "Bienvenue", "classements": "Classements officiels",
             "top100": "Les 100 titres de la semaine", "artistes": "Les artistes de la semaine", "fichiers": "Téléchargements"}[vue]
    actions = _boutons(edition) if vue in ("accueil", "fichiers") and edition else ""
    html_.append(f'<div class="titre"><div><p class="sur">{_drapeau("mini-drapeau")} {e(nom_pays)} · {e(p["nom"])} × Cauri Charts</p>'
                 f'<h1>{e(titre)}</h1><p class="periode">{e(periode)}</p></div><div class="actions">{actions}</div></div>')

    if vue == "fichiers":
        html_.append(_fichiers(editions, choisie))
    elif not local:
        html_.append('<div class="vide">Aucun classement publié pour le moment. La première édition arrive vendredi soir.</div>')
    elif vue == "accueil":
        html_.append(_accueil(local, u, edition))
    elif vue == "classements":
        html_.append(_classements(local, request.GET.get("c"), u, nom_pays))
    elif vue == "top100":
        html_.append(_top100(cid, debut, _page(request), u))
    elif vue == "artistes":
        html_.append(_artistes(cid, debut, _page(request), u))

    html_.append(f"""</main><footer class="pied"><div class="cadre"><span>Cauri Charts · la référence de la musique ouest-africaine ·
mention à l'antenne : « Source : Cauri Charts »</span><span>Espace réservé à {e(p['nom'])} · contact@cauricharts.com</span></div></footer>
</body></html>""")
    return _tete(p, f"{p['nom']} × Cauri Charts · {nom_pays}", pays) + "".join(html_)


def _boutons(ed: dict) -> str:
    out = []
    for nom, url in ed["fichiers"].items():
        ext = nom.rsplit(".", 1)[-1]
        titre = FICHIERS.get(ext, (nom, ""))[0]
        out.append(f'<a class="bouton{" bouton--plein" if ext == "pdf" else ""}" href="{e(url)}" download>{ICONE_DL}{e(titre)}</a>')
    return "".join(out)


def _fait(etiquette: str, l: dict, detail: str = "", mv: bool = False, href: str = "") -> str:
    corps = (f'<div class="fait">{_img(l["image"], l["artiste"])}<div><small>{e(etiquette)}</small><strong>{e(_nom(l))}</strong>'
             f'<span class="qui">{e(detail or _qui(l))}</span>{_mv(l) if mv else ""}</div></div>')
    return f'<a href="{e(href)}">{corps}</a>' if href else corps


def _accueil(local: dict, u, edition) -> str:
    par = {c["code"]: c for c in local["classements"]}
    top = (par.get("prime") or {}).get("lignes") or []
    out = []
    if top:
        n1 = top[0]
        if n1["precedent"] == 1:
            detail = f"Reste n°1 · {n1['semaines'] or 1} semaines au classement"
        elif n1["precedent"]:
            detail = f"Nouveau n°1 · était {P._e(n1['precedent'])} la semaine passée"
        else:
            detail = "Entrée directe à la 1re place"
        faits = []
        if par.get("icon") and par["icon"]["lignes"]:
            a = par["icon"]["lignes"][0]
            faits.append(_fait("Artiste de la semaine", a))
        montees = [l for l in top[1:] if l["precedent"] and l["precedent"] > l["rang"]]
        if montees:
            m = max(montees, key=lambda l: l["precedent"] - l["rang"])
            faits.append(_fait("Plus forte progression", m, f"{m['artiste']} · de la {P._e(m['precedent'])} à la {P._e(m['rang'])} place", True))
        entrees = [l for l in top[1:] if not l["precedent"] and (l["semaines"] or 1) <= 1]
        if entrees:
            en = min(entrees, key=lambda l: l["rang"])
            faits.append(_fait("Meilleure entrée", en, f"{en['artiste']} · entre {P._e(en['rang'])}", True))
        out.append(f'<div class="une"><a class="vedette" href="{e(u(vue="classements", c="prime"))}">{_img(n1["image"], n1["artiste"], "visuel")}'
                   f'<div><span class="couronne">N°1 de la semaine</span><h2>{e(_nom(n1))}</h2><div class="qui">{e(_qui(n1))}</div>'
                   f'<div class="detail">{e(detail)}</div></div></a><div class="faits">{"".join(faits)}</div></div>')

    def liste(code: str, titre: str) -> str:
        c = par.get(code)
        if not c or not c["lignes"]:
            return ""
        lignes = "".join(f'<li><span class="n">{l["rang"]}</span>{_img(l["image"], l["artiste"])}<div><strong>{e(_nom(l))}</strong>'
                         f'<span class="qui">{e(_qui(l))}</span></div>{_mv(l)}</li>' for l in c["lignes"][:5])
        return (f'<section class="bloc"><div class="bloc__tete"><h2>{e(titre)}</h2><a class="lien" href="{e(u(vue="classements", c=code))}">'
                f'Voir les {len(c["lignes"])} →</a></div><ol class="liste">{lignes}</ol></section>')

    out.append(f'<div class="deux">{liste("prime", "Top des titres")}{liste("icon", "Top Artistes")}</div>')
    autres = [c for c in local["classements"] if c["code"] not in ("prime", "icon") and c["lignes"]]
    if autres:
        out.append('<div class="aussi">' + "".join(
            _fait(f"N°1 · {c['nom']}", c["lignes"][0], href=u(vue="classements", c=c["code"])) for c in autres) + "</div>")
    if not edition:
        out.append('<p class="note" style="margin-top:18px">Le dossier PDF, le tableau Excel et les visuels TV de cette semaine '
                   'arrivent dans « Téléchargements » dès la publication du vendredi soir.</p>')
    return "".join(out)


def _classements(local: dict, code: str | None, u, nom_pays: str) -> str:
    charts = [c for c in local["classements"] if c["lignes"]]
    if not charts:
        return '<div class="vide">Aucun classement publié cette semaine.</div>'
    c = next((x for x in charts if x["code"] == code), charts[0])
    puces = "".join(f'<a href="{e(u(vue="classements", c=x["code"]))}"{" aria-current=page" if x is c else ""}>{e(x["nom"])}</a>'
                    for x in charts)
    desc = DESCRIPTIONS.get(c["code"]) or (f"Les titres {c['nom'].replace('Top ', '').lower()} les plus forts de la semaine."
                                           if c["code"].startswith("g-") else "")
    n1, reste = c["lignes"][0], c["lignes"][1:]
    stats = [("Évolution", P._mouvement(n1).replace("NOUVEAU", "Entrée").replace("RETOUR", "Retour").replace("-", "−"))]
    if n1.get("semaines"):
        stats.append(("Semaines", str(n1["semaines"])))
    if n1.get("meilleur"):
        stats.append(("Meilleur rang", str(n1["meilleur"])))
    if c["artistes"] and n1.get("titres"):
        stats.append(("Titres", str(n1["titres"])))
    cartes = "".join(
        f'<article class="carte"><div class="carte__img">{_img(l["image"], l["artiste"])}<span class="rang">{l["rang"]}</span>{_mv(l)}</div>'
        f'<h3 title="{e(_nom(l))}">{e(_nom(l))}</h3><p>{e(_qui(l))}</p></article>' for l in reste)
    return (f'<nav class="puces" aria-label="Classements">{puces}</nav>'
            f'<div class="chart-tete"><h2>{e(c["nom"])} · {e(nom_pays)}</h2><p>{e(desc)}</p></div>'
            f'<div class="vedette">{_img(n1["image"], n1["artiste"], "visuel")}<div><span class="couronne">N°1</span>'
            f'<h2>{e(_nom(n1))}</h2><div class="qui">{e(_qui(n1))}</div><div class="stats">'
            + "".join(f"<div>{e(k)}<b>{e(v)}</b></div>" for k, v in stats) + f'</div></div></div><div class="grille">{cartes}</div>')


def _top100(cid, debut, page: int, u) -> str:
    """Tous les titres de la semaine dans le pays, par score (titres vérifiés seulement)."""
    if not cid or not debut:
        return ""
    rows = db.all("""SELECT t.title, t.featuring, t.cover_url, a.name, COALESCE(a.image_hd_url, a.image_url) AS photo, ws.score
                     FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                     WHERE ws.country_id = ? AND ws.week_start = ? AND ws.score > 0 AND ws.review_status IN ('ok', 'validated')
                     ORDER BY ws.score DESC LIMIT 100""", [cid, debut])
    if not rows:
        return '<div class="vide">Le détail des titres de cette semaine n\'est pas disponible.</div>'
    lignes = "".join(
        f'<tr><td class="n{" n--or" if i == 1 else ""}">{i}</td><td class="qui"><div class="ident">{_img(r["cover_url"] or r["photo"], r["name"])}'
        f'<div><strong>{e(r["title"])}</strong><span>{e(r["name"])}{" feat. " + e(r["featuring"]) if r["featuring"] else ""}</span></div></div></td>'
        f'<td class="c">{_nombre(r["score"])}</td></tr>' for i, r in enumerate(rows, 1) if (page - 1) * 25 < i <= page * 25)
    return (f'<p class="note" style="margin:-8px 0 16px">Tous les titres relevés cette semaine, par score Cauri. Le classement officiel '
            f'(Top 20) est dans « Classements ».</p><div class="table"><table><colgroup><col style="width:56px"><col><col style="width:120px">'
            f'</colgroup><thead><tr><th>Rang</th><th>Titre</th><th class="c">Score</th></tr></thead><tbody>{lignes}</tbody></table></div>' + _pager(len(rows), 25, page, u))


def _artistes(cid, debut, page: int, u) -> str:
    if not cid or not debut:
        return ""
    rows = db.all("""SELECT a.name, COALESCE(a.image_hd_url, a.image_url) AS photo, a.youtube_subscribers, a.fans,
                            SUM(ws.score) AS points, COUNT(*) AS titres
                     FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                     WHERE ws.country_id = ? AND ws.week_start = ? AND ws.score > 0 AND ws.review_status IN ('ok', 'validated')
                     GROUP BY a.id, a.name, photo, a.youtube_subscribers, a.fans ORDER BY points DESC LIMIT 60""", [cid, debut])
    if not rows:
        return '<div class="vide">Le détail des artistes de cette semaine n\'est pas disponible.</div>'
    podium = "".join(
        f'<div class="marche{" marche--1" if i == 1 else ""}">{_img(r["photo"], r["name"])}<div><small>{P._e(i)} de la semaine</small>'
        f'<strong>{e(r["name"])}</strong><span>{_nombre(r["points"])} points · {int(r["titres"])} titre{"s" if r["titres"] > 1 else ""}</span>'
        f'</div></div>' for i, r in enumerate(rows[:3], 1))
    lignes = "".join(
        f'<tr><td class="n">{i}</td><td class="qui"><div class="ident">{_img(r["photo"], r["name"])}<div><strong>{e(r["name"])}</strong>'
        f'<span>{int(r["titres"])} titre{"s" if r["titres"] > 1 else ""}</span></div></div></td><td class="c">{_nombre(r["points"])}</td>'
        f'<td class="c cache-mobile">{_nombre(r["youtube_subscribers"])}</td><td class="c cache-mobile">{_nombre(r["fans"])}</td></tr>'
        for i, r in enumerate(rows, 1) if i > 3 and (page - 1) * 20 < i <= page * 20)
    if page > 1:
        podium = ""
    return (f'<div class="podium">{podium}</div><div class="table"><table><colgroup><col style="width:56px"><col>'
            f'<col style="width:120px"><col class="cache-mobile" style="width:150px"><col class="cache-mobile" style="width:130px"></colgroup>'
            f'<thead><tr><th>Rang</th><th>Artiste</th><th class="c">Points</th><th class="c cache-mobile">Abonnés YouTube</th>'
            f'<th class="c cache-mobile">Fans Deezer</th></tr></thead><tbody>{lignes}</tbody></table></div>'
            + _pager(len(rows), 20, page, u) + f'<p class="note" style="margin-top:12px">Points : somme des scores de tous les titres de l\'artiste cette semaine.</p>')


def _page(request) -> int:
    try:
        return max(1, min(10, int(request.GET.get("page") or 1)))
    except ValueError:
        return 1


def _pager(total: int, par: int, page: int, u) -> str:
    n = (total + par - 1) // par
    if n <= 1:
        return ""
    return '<nav class="pages" aria-label="Pages">' + "".join(
        f'<a href="{e(u(page=str(k) if k > 1 else None))}"{" aria-current=page" if k == page else ""}>{(k - 1) * par + 1}–{min(k * par, total)}</a>'
        for k in range(1, n + 1)) + "</nav>"


def _fichiers(editions: list[dict], choisie: str) -> str:
    if not editions:
        return ('<div class="vide">Le dossier de chaque semaine (PDF, Excel, visuels pour l\'antenne) arrive ici dès la publication '
                'du vendredi soir.</div>')
    blocs = []
    for ed in editions[:20]:
        date = f"Envoyée le {ed['envoye_le']:%d/%m/%Y}" if ed.get("envoye_le") else "Préparée"
        blocs.append(f'<div class="edition{" edition--courante" if ed["semaine"] == choisie else ""}"><div><h3>Semaine {e(ed["semaine"][-2:])}'
                     f'</h3><p>{e(ed["semaine"][:4])} · {date}</p></div><div class="actions">{_boutons(ed)}</div></div>')
    return f'<div class="editions">{"".join(blocs)}</div>'
