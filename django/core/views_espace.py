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
:root { --encre:#0d1330; --encre2:#3c4466; --doux:#6b7394; --fond:#e8eef8; --ligne:rgba(255,255,255,.65);
  --ciel:#00A6FF; --ciel2:#38CFFF; --orange:#FF7A1A; --vert:#12C77A; --violet:#8B52FF;
  --pays1:__P1__; --pays2:__P2__; --pays3:__P3__; --nec:__N1__; --or:__N2__;
  --verre:rgba(255,255,255,.52); --verre2:rgba(255,255,255,.72); --bord:rgba(255,255,255,.75);
  --ombre:0 10px 40px rgba(26,52,120,.12); --neo:7px 7px 16px rgba(163,177,206,.55), -7px -7px 16px rgba(255,255,255,.95);
  --neo-creux:inset 4px 4px 10px rgba(163,177,206,.55), inset -4px -4px 10px rgba(255,255,255,.95);
  --liquide:linear-gradient(125deg,var(--ciel) 0%,var(--violet) 52%,var(--orange) 100%);
  --monte:#05935a; --monte-fond:rgba(18,199,122,.16); --baisse:#d93a4a; --baisse-fond:rgba(255,77,110,.14);
  --neuf:#d35f00; --neuf-fond:rgba(255,122,26,.16);
  --titre:"Unbounded","Space Grotesk",system-ui,sans-serif; --sans:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  color-scheme:light }
* { box-sizing:border-box }
html { background:var(--fond) }
body { margin:0; min-height:100vh; display:flex; flex-direction:column; background:transparent; color:var(--encre); font:15px/1.55 var(--sans);
  -webkit-font-smoothing:antialiased; position:relative; overflow-x:hidden }
a { color:inherit } img { max-width:100% }
h1,h2,h3 { text-wrap:balance; margin:0 }
.cadre { width:100%; max-width:1180px; margin:0 auto; padding-left:max(18px,env(safe-area-inset-left,0px)); padding-right:max(18px,env(safe-area-inset-right,0px)) }
.verre { background:var(--verre); backdrop-filter:blur(22px) saturate(170%); -webkit-backdrop-filter:blur(22px) saturate(170%);
  border:1px solid var(--bord); box-shadow:var(--ombre), inset 0 1px 0 rgba(255,255,255,.9) }

/* fond liquide : grandes gouttes de couleur qui dérivent lentement */
.fond { position:fixed; inset:0; z-index:-1; overflow:hidden; pointer-events:none;
  background:radial-gradient(1200px 700px at 50% -10%,#f6f9ff 0%,transparent 70%),var(--fond) }
.fond i { position:absolute; display:block; filter:blur(70px); opacity:.55; border-radius:42% 58% 63% 37% / 41% 44% 56% 59%;
  animation:goutte 26s ease-in-out infinite alternate }
.fond .b1 { width:620px; height:620px; left:-160px; top:-140px; background:var(--ciel) }
.fond .b2 { width:520px; height:520px; right:-140px; top:120px; background:var(--orange); opacity:.42; animation-duration:32s; animation-delay:-8s }
.fond .b3 { width:460px; height:460px; left:32%; bottom:-200px; background:var(--violet); opacity:.38; animation-duration:30s; animation-delay:-14s }
.fond .b4 { width:300px; height:300px; left:8%; bottom:12%; background:var(--vert); opacity:.32; animation-duration:24s; animation-delay:-4s }
@keyframes goutte {
  0% { transform:translate(0,0) rotate(0) scale(1); border-radius:42% 58% 63% 37% / 41% 44% 56% 59% }
  50% { transform:translate(60px,40px) rotate(40deg) scale(1.08); border-radius:58% 42% 35% 65% / 55% 62% 38% 45% }
  100% { transform:translate(-40px,70px) rotate(80deg) scale(.95); border-radius:38% 62% 56% 44% / 63% 37% 63% 37% } }
@keyframes tourne { to { transform:rotate(360deg) } }
@media (prefers-reduced-motion:reduce) { .fond i, .vedette::before, .porte__marque::before { animation:none } }
/* 10/11/2026 : la page ramait sur téléphone (gouttes floues animées + une quinzaine de cartes au flou recalculé à
   chaque image et à chaque défilement). Sur écran tactile / petit écran : gouttes immobiles, verre imité par un blanc
   translucide plus couvrant (même rendu à l'œil, sans calcul de flou), halo de la carte vedette immobile. */
@media (max-width:900px), (hover:none) {
  .fond i, .vedette::before, .porte__marque::before { animation:none !important }
  .fond { contain:strict; transform:translateZ(0) }
  .fond i { filter:blur(48px) }
  :root { --verre:rgba(255,255,255,.84); --verre2:rgba(255,255,255,.9) }
  *, *::before, *::after { backdrop-filter:none !important; -webkit-backdrop-filter:none !important }
}

/* en-tête flottant */
.tete { position:sticky; top:0; z-index:10; padding-block:14px 6px; display:grid; gap:10px }
.tete__barre { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:10px 12px 10px 18px; border-radius:22px }
.duo { display:flex; align-items:center; gap:14px; min-width:0 }
.duo__cauri { height:30px; width:auto; display:block }
.duo__x { font:500 .9rem var(--titre); color:var(--doux) }
.duo__nec { display:inline-flex; align-items:center; padding:8px 14px; border-radius:12px; background:var(--nec); color:var(--or);
  font:700 .74rem/1 var(--titre); letter-spacing:.08em; white-space:nowrap; box-shadow:0 6px 18px rgba(13,19,48,.25), inset 0 1px 0 rgba(255,255,255,.12) }
.duo__nec img { height:40px; width:auto; display:block; border-radius:6px }
.duo__nec:has(img) { padding:4px; background:#000 }
.tete__droite { display:flex; align-items:center; gap:10px }
.sortir { display:inline-flex; align-items:center; gap:6px; text-decoration:none; font-weight:600; font-size:.84rem; padding:9px 14px; border-radius:12px;
  background:var(--fond); box-shadow:var(--neo) }
.sortir svg { width:16px; height:16px }
.sortir:hover { color:var(--violet) }
.semaine { display:flex; align-items:center; gap:4px; padding:4px; border-radius:14px; background:var(--fond); box-shadow:var(--neo-creux) }
.semaine a, .semaine span.off { display:grid; place-items:center; width:32px; height:32px; border-radius:10px; text-decoration:none; font-size:1.1rem; font-weight:700 }
.semaine a { background:var(--fond); box-shadow:3px 3px 8px rgba(163,177,206,.6), -3px -3px 8px #fff; color:var(--ciel) }
.semaine a:hover { color:var(--violet) } .semaine span.off { color:#b9c1d8 }
.semaine strong { font:600 .74rem var(--titre); padding:0 8px; white-space:nowrap }
.onglets { display:flex; gap:4px; padding:6px; border-radius:18px; overflow-x:auto; scrollbar-width:none }
.onglets::-webkit-scrollbar { display:none }
.onglets a { flex:1 0 auto; text-align:center; text-decoration:none; padding:10px 16px; border-radius:13px; font-weight:600; font-size:.9rem;
  color:var(--encre2); white-space:nowrap; transition:background .2s, color .2s }
.onglets a:hover { background:rgba(255,255,255,.6) }
.onglets a[aria-current] { color:#fff; background:var(--liquide); box-shadow:0 8px 22px rgba(0,166,255,.35), inset 0 1px 0 rgba(255,255,255,.35) }

main { padding-block:22px 56px; flex:1 }
.titre { display:flex; align-items:flex-end; justify-content:space-between; gap:18px; flex-wrap:wrap; margin-bottom:22px }
.sur { margin:0 0 12px; font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:var(--encre2);
  display:flex; align-items:center; gap:10px; flex-wrap:wrap }
.titre h1 { font:700 clamp(1.7rem,4.2vw,2.7rem)/1.08 var(--titre); letter-spacing:-.01em; padding-bottom:2px;
  background:linear-gradient(100deg,var(--encre) 25%,var(--violet) 65%,var(--ciel)); -webkit-background-clip:text; background-clip:text; color:transparent }
.titre p.periode { margin:8px 0 0; color:var(--encre2) }
.actions { display:flex; gap:12px; flex-wrap:wrap }
.bouton { display:inline-flex; align-items:center; gap:8px; padding:12px 18px; border-radius:14px; font-weight:600; font-size:.88rem; text-decoration:none;
  background:var(--fond); box-shadow:var(--neo); color:var(--encre); transition:transform .15s, box-shadow .15s }
.bouton:hover { transform:translateY(-1px); color:var(--violet) }
.bouton:active { box-shadow:var(--neo-creux) }
.bouton--plein { background:var(--liquide); color:#fff; box-shadow:0 10px 26px rgba(139,82,255,.38), inset 0 1px 0 rgba(255,255,255,.35) }
.bouton--plein:hover { color:#fff }
.bouton svg { width:17px; height:17px; flex:none }
.note { color:var(--doux); font-size:.86rem; margin:0 }
.mini-drapeau { display:inline-flex; width:22px; height:15px; border-radius:4px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.15) }
.mini-drapeau i { flex:1 } .mini-drapeau i:nth-child(1) { background:var(--pays1) } .mini-drapeau i:nth-child(2) { background:var(--pays2) }
.mini-drapeau i:nth-child(3) { background:var(--pays3) }
.pastille { display:inline-flex; align-items:center; gap:8px; padding:6px 12px 6px 8px; border-radius:999px; background:var(--verre2);
  border:1px solid var(--bord); box-shadow:0 4px 14px rgba(26,52,120,.08) }

/* vedette : la carte liquide du n°1 */
.une { display:grid; grid-template-columns:minmax(0,1.2fr) minmax(0,1fr); gap:18px }
@media (max-width:880px) { .une { grid-template-columns:1fr } }
.vedette { position:relative; isolation:isolate; display:grid; grid-template-columns:minmax(0,230px) minmax(0,1fr); gap:24px; align-items:center;
  color:#fff; border-radius:30px; padding:24px; overflow:hidden; text-decoration:none; background:#141a3a;
  box-shadow:0 24px 60px rgba(60,40,160,.30), inset 0 1px 0 rgba(255,255,255,.25) }
.vedette::before { content:""; position:absolute; inset:-40%; z-index:-2;
  background:conic-gradient(from 0deg at 50% 50%,var(--ciel),var(--violet),var(--orange),var(--violet),var(--ciel));
  filter:blur(60px); opacity:.9; animation:tourne 18s linear infinite }
.vedette::after { content:""; position:absolute; inset:0; z-index:-1; background:linear-gradient(160deg,rgba(13,19,48,.28),rgba(13,19,48,.6)) }
.vedette .visuel { width:100%; aspect-ratio:1; border-radius:22px; object-fit:cover; display:block;
  box-shadow:0 20px 44px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.35) }
.couronne { display:inline-flex; align-items:center; gap:6px; background:linear-gradient(120deg,#FFD66B,var(--or),var(--orange)); color:#2a1600;
  font:700 .66rem var(--titre); letter-spacing:.1em; text-transform:uppercase; padding:7px 12px; border-radius:999px; box-shadow:0 6px 18px rgba(255,122,26,.45) }
.vedette h2 { font:700 clamp(1.4rem,3vw,2.1rem)/1.1 var(--titre); margin:16px 0 6px; text-shadow:0 2px 20px rgba(0,0,0,.25) }
.vedette .qui { color:rgba(255,255,255,.9); font-size:1rem }
.vedette .detail { margin-top:14px; display:inline-block; font-size:.84rem; padding:8px 12px; border-radius:12px; background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.3); backdrop-filter:blur(10px) }
.stats { display:flex; gap:12px; flex-wrap:wrap; margin-top:18px }
.stats div { font:700 .58rem var(--titre); color:rgba(255,255,255,.8); text-transform:uppercase; letter-spacing:.1em; padding:10px 14px; border-radius:16px;
  background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.28); backdrop-filter:blur(10px) }
.stats b { display:block; font:700 1.25rem/1.1 var(--titre); color:#fff; letter-spacing:0; margin-top:5px }
@media (max-width:540px) { .vedette { grid-template-columns:104px minmax(0,1fr); gap:14px; padding:14px; border-radius:24px }
  .vedette h2 { font-size:1.05rem; margin-top:10px } .vedette .visuel { border-radius:14px } .vedette .detail { font-size:.76rem }
  .stats { gap:8px } .stats div { padding:8px 10px } .stats b { font-size:.95rem } }

.faits { display:grid; gap:14px }
.fait { position:relative; display:grid; grid-template-columns:72px minmax(0,1fr); gap:14px; align-items:center; padding:12px 12px 12px 16px; border-radius:22px;
  background:var(--verre); backdrop-filter:blur(22px) saturate(170%); -webkit-backdrop-filter:blur(22px) saturate(170%); border:1px solid var(--bord);
  box-shadow:var(--ombre), inset 0 1px 0 #fff; transition:transform .2s; overflow:hidden }
.fait::before { content:""; position:absolute; left:0; top:16px; bottom:16px; width:4px; border-radius:0 4px 4px 0; background:var(--ciel) }
.faits > .fait:nth-child(2)::before, .aussi > a:nth-child(2) .fait::before { background:var(--vert) }
.faits > .fait:nth-child(3)::before, .aussi > a:nth-child(3) .fait::before { background:var(--orange) }
.aussi > a:nth-child(4n) .fait::before { background:var(--violet) }
.fait img,.fait .init { width:72px; height:72px; border-radius:16px; object-fit:cover; display:block; box-shadow:0 8px 20px rgba(13,19,48,.18) }
.fait small { display:block; font:700 .58rem var(--titre); letter-spacing:.12em; text-transform:uppercase; color:var(--violet) }
.fait strong { display:block; font-size:1rem; line-height:1.25; margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.fait span.qui { display:block; color:var(--encre2); font-size:.85rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.fait .mv { margin-top:6px }

.deux { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; margin-top:18px }
@media (max-width:880px) { .deux { grid-template-columns:1fr } }
.bloc { border-radius:28px; padding:18px; background:var(--verre); backdrop-filter:blur(22px) saturate(170%); -webkit-backdrop-filter:blur(22px) saturate(170%);
  border:1px solid var(--bord); box-shadow:var(--ombre), inset 0 1px 0 #fff }
.bloc__tete { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:2px 4px 10px }
.bloc__tete h2 { font:700 1rem/1.2 var(--titre) }
.lien { font-weight:600; font-size:.8rem; text-decoration:none; white-space:nowrap; padding:8px 12px; border-radius:12px; background:var(--fond);
  box-shadow:var(--neo); color:var(--ciel) }
.lien:hover { color:var(--violet) }
.liste { list-style:none; margin:0; padding:0 }
.liste li { display:grid; grid-template-columns:34px 50px minmax(0,1fr) auto; gap:12px; align-items:center; padding:8px; border-radius:16px; transition:background .2s }
.liste li:hover { background:rgba(255,255,255,.6) }
.liste .n { display:grid; place-items:center; width:34px; height:34px; border-radius:11px; font:700 .8rem var(--titre); background:var(--fond); box-shadow:var(--neo-creux) }
.liste li:first-child .n { background:linear-gradient(120deg,#FFD66B,var(--or),var(--orange)); color:#2a1600; box-shadow:0 4px 12px rgba(255,122,26,.35) }
.liste img,.liste .init { width:50px; height:50px; border-radius:14px; object-fit:cover; display:block }
.liste strong { display:block; font-size:.94rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.liste span.qui { display:block; color:var(--doux); font-size:.83rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.aussi { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; margin-top:18px }
.aussi a { text-decoration:none } .aussi .fait:hover { transform:translateY(-3px) }

.mv { display:inline-block; font:700 .7rem/1 var(--sans); padding:5px 9px; border-radius:999px; background:rgba(107,115,148,.14); color:var(--encre2); white-space:nowrap }
.mv--monte { color:var(--monte); background:var(--monte-fond) } .mv--baisse { color:var(--baisse); background:var(--baisse-fond) }
.mv--neuf { color:var(--neuf); background:var(--neuf-fond) }

/* classements */
.puces { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px }
.puces a { text-decoration:none; padding:10px 16px; border-radius:14px; font-weight:600; font-size:.86rem; color:var(--encre2); background:var(--fond); box-shadow:var(--neo) }
.puces a:hover { color:var(--violet) }
.puces a[aria-current] { box-shadow:var(--neo-creux); color:var(--violet) }
.chart-tete { margin-bottom:18px } .chart-tete h2 { font:700 clamp(1.2rem,2.8vw,1.6rem)/1.15 var(--titre) }
.chart-tete p { margin:6px 0 0; color:var(--encre2); max-width:65ch }
.grille { display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:16px; margin-top:18px }
@media (max-width:540px) { .grille { grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px } }
.carte { min-width:0; padding:8px 8px 14px; border-radius:24px; background:var(--verre); backdrop-filter:blur(22px) saturate(170%);
  -webkit-backdrop-filter:blur(22px) saturate(170%); border:1px solid var(--bord); box-shadow:var(--ombre), inset 0 1px 0 #fff; transition:transform .2s }
.carte:hover { transform:translateY(-4px) }
.carte__img { position:relative }
.carte__img img,.carte__img .init { width:100%; aspect-ratio:1; border-radius:18px; object-fit:cover; display:block }
.carte .rang { position:absolute; left:8px; bottom:8px; min-width:36px; height:36px; padding:0 9px; border-radius:12px; display:grid; place-items:center;
  font:700 .85rem var(--titre); color:var(--encre); background:rgba(255,255,255,.72); backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,.9);
  box-shadow:0 4px 14px rgba(0,0,0,.18) }
.carte .mv { position:absolute; right:8px; top:8px; backdrop-filter:blur(10px); background-color:rgba(255,255,255,.85) }
.carte h3 { margin:10px 6px 0; font-size:.92rem; line-height:1.25; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.carte p { margin:2px 6px 0; color:var(--doux); font-size:.8rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }

/* tableaux */
.table { border-radius:26px; overflow:hidden; background:var(--verre); backdrop-filter:blur(22px) saturate(170%); -webkit-backdrop-filter:blur(22px) saturate(170%);
  border:1px solid var(--bord); box-shadow:var(--ombre) }
table { width:100%; border-collapse:collapse; font-size:.9rem; table-layout:fixed }
th,td { padding:9px 14px; text-align:left; border-bottom:1px solid rgba(160,175,210,.22) }
tbody tr:last-child td { border-bottom:0 } tbody tr:hover td { background:rgba(255,255,255,.5) }
th { font:700 .58rem var(--titre); letter-spacing:.12em; text-transform:uppercase; color:var(--doux); background:rgba(255,255,255,.45) }
td.n { font:700 .8rem var(--titre); width:56px; text-align:center }
td.n--or { color:var(--orange) }
.ident { display:flex; align-items:center; gap:12px; min-width:0 }
.ident img,.ident .init { width:42px; height:42px; border-radius:12px; object-fit:cover; flex:none; display:block }
.ident strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.ident span { display:block; color:var(--doux); font-size:.82rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.ident > div { min-width:0 }
td.c, th.c { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap }
@media (max-width:640px) { .cache-mobile { display:none } th,td { padding:8px 10px } td.n { width:40px } }
.pages { display:flex; flex-wrap:wrap; gap:12px; justify-content:center; margin-top:20px }
.pages a { text-decoration:none; padding:9px 14px; border-radius:12px; font-weight:600; font-size:.82rem; color:var(--encre2); background:var(--fond); box-shadow:var(--neo) }
.pages a[aria-current] { box-shadow:var(--neo-creux); color:var(--violet) }

/* podium artistes */
.podium { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-bottom:18px }
@media (max-width:700px) { .podium { grid-template-columns:1fr } }
.marche { display:grid; grid-template-columns:84px minmax(0,1fr); gap:14px; align-items:center; padding:14px; border-radius:26px;
  background:var(--verre); backdrop-filter:blur(22px) saturate(170%); border:1px solid var(--bord); box-shadow:var(--ombre), inset 0 1px 0 #fff }
.marche--1 { position:relative; isolation:isolate; overflow:hidden; color:#fff; border-color:rgba(255,255,255,.35); background:#141a3a }
.marche--1::before { content:""; position:absolute; inset:0; z-index:-1; background:var(--liquide) }
.marche img,.marche .init { width:84px; height:84px; border-radius:50%; object-fit:cover; display:block; box-shadow:0 8px 22px rgba(13,19,48,.22) }
.marche--1 img { box-shadow:0 0 0 3px rgba(255,255,255,.85), 0 10px 24px rgba(0,0,0,.25) }
.marche small { font:700 .58rem var(--titre); letter-spacing:.12em; text-transform:uppercase; color:var(--violet) }
.marche:nth-child(2) small { color:var(--ciel) } .marche:nth-child(3) small { color:var(--vert) }
.marche--1 small { color:#fff; opacity:.9 }
.marche strong { display:block; font:700 1rem/1.2 var(--titre); margin:5px 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.marche span { font-size:.84rem; color:var(--doux) } .marche--1 span { color:rgba(255,255,255,.88) }

/* téléchargements */
.editions { display:grid; gap:14px }
.edition { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; padding:18px 20px; border-radius:26px;
  background:var(--verre); backdrop-filter:blur(22px) saturate(170%); border:1px solid var(--bord); box-shadow:var(--ombre), inset 0 1px 0 #fff }
.edition--courante { box-shadow:0 0 0 2px rgba(0,166,255,.55), var(--ombre) }
.edition h3 { font:700 1.05rem/1.1 var(--titre) } .edition p { margin:6px 0 0; color:var(--doux); font-size:.85rem }
.vide { padding:28px; border-radius:26px; color:var(--encre2); background:var(--verre); border:1px dashed rgba(107,115,148,.4) }

.init { display:grid !important; place-items:center; background:var(--liquide); color:#fff; font:700 1rem var(--titre) }
.pied { padding-block:8px 22px }
.pied .cadre > div { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; padding:16px 20px; border-radius:20px; font-size:.82rem; color:var(--encre2) }

/* connexion */
.connexion { min-height:100vh; display:grid; place-items:center; padding:32px max(18px,env(safe-area-inset-right,0px)) 32px max(18px,env(safe-area-inset-left,0px)) !important }
.porte { width:min(980px,100%); display:grid; grid-template-columns:minmax(0,1.15fr) minmax(0,1fr); border-radius:36px; overflow:hidden }
@media (max-width:820px) { .porte { grid-template-columns:1fr } }
.porte__marque { position:relative; isolation:isolate; overflow:hidden; color:#fff; padding:34px; display:flex; flex-direction:column;
  justify-content:space-between; gap:34px; min-height:440px; background:#141a3a }
@media (max-width:820px) { .porte__marque { min-height:0; padding:26px } }
.porte__marque::before { content:""; position:absolute; inset:-40%; z-index:-2;
  background:conic-gradient(from 0deg,var(--ciel),var(--violet),var(--orange),var(--violet),var(--ciel)); filter:blur(60px); opacity:.9; animation:tourne 20s linear infinite }
.porte__marque::after { content:""; position:absolute; inset:0; z-index:-1; background:linear-gradient(160deg,rgba(13,19,48,.12),rgba(13,19,48,.55)) }
.porte__marque .duo__cauri { filter:brightness(0) invert(1) }
.porte__marque .duo__x { color:rgba(255,255,255,.75) }
.porte__marque h1 { font:700 clamp(1.5rem,3.4vw,2.4rem)/1.12 var(--titre); max-width:17ch; margin-top:16px }
.porte__marque p { color:rgba(255,255,255,.88); max-width:44ch; margin:14px 0 0 }
.porte__marque .pastille { background:rgba(255,255,255,.18); border-color:rgba(255,255,255,.35); color:#fff; font-size:.68rem; font-weight:700;
  letter-spacing:.12em; text-transform:uppercase; box-shadow:none }
.porte__pied { font-size:.8rem; color:rgba(255,255,255,.78) }
.porte__form { display:grid; place-items:center; padding:34px }
.porte__form form { width:min(360px,100%) }
.porte__form h2 { font:700 1.4rem/1.1 var(--titre); margin-bottom:8px }
.porte__form p { color:var(--doux); margin:0 0 24px }
label { display:block; font-weight:600; font-size:.86rem; margin-bottom:10px }
input[type=password] { width:100%; padding:15px 16px; border:0; border-radius:16px; font:inherit; font-size:1rem; background:var(--fond); box-shadow:var(--neo-creux); color:var(--encre) }
input[type=password]:focus { outline:2px solid var(--ciel); outline-offset:2px }
button { margin-top:18px; width:100%; padding:15px; border:0; border-radius:16px; background:var(--liquide); color:#fff; font:700 .9rem var(--titre); cursor:pointer;
  box-shadow:0 12px 30px rgba(139,82,255,.4), inset 0 1px 0 rgba(255,255,255,.35); transition:transform .15s }
button:hover { transform:translateY(-1px) }
.erreur { background:var(--baisse-fond); color:var(--baisse); font-weight:600; padding:10px 14px; border-radius:12px; margin:0 0 16px }
:focus-visible { outline:3px solid var(--ciel); outline-offset:2px }
@media (max-width:640px) { .tete__barre { padding:8px 8px 8px 12px; gap:8px } .duo { gap:7px } .duo__cauri { height:22px } .duo__x { display:none }
  .duo__nec { padding:6px 8px; font-size:.56rem } .duo__nec img { height:30px } .sortir { padding:8px 9px } .sortir span { display:none }
  .semaine strong { font-size:.62rem; padding:0 3px } .semaine a,.semaine span.off { width:26px; height:26px } .tete__droite { gap:6px }
  .onglets a { padding:9px 12px; font-size:.84rem } }
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
<link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_css(p, pays)}</style></head><body><div class="fond" aria-hidden="true"><i class="b1"></i><i class="b2"></i><i class="b3"></i><i class="b4"></i></div>"""


def _duo(p: dict) -> str:
    nec = f'<img src="{e(p["logo_url"])}" alt="{e(p["nom"])}">' if p.get("logo_url") else e(p["nom"].replace(" Media", "").upper())
    return (f'<div class="duo"><img class="duo__cauri" src="/assets/img/brand/logo.svg" alt="Cauri Charts" width="68" height="30">'
            f'<span class="duo__x" aria-hidden="true">×</span><span class="duo__nec">{nec}</span></div>')


def _drapeau(cls: str = "drapeau") -> str:
    return f'<span class="{cls}" aria-hidden="true"><i></i><i></i><i></i></span>'


def _connexion(request, p: dict, erreur: str) -> str:
    pays = (p.get("pays") or "CI").split(",")[0] or "CI"
    nom_pays = P.NOMS_PAYS.get(pays, pays)
    return (_tete(p, f"Espace {p['nom']} · Cauri Charts", pays) + f"""<main class="connexion"><div class="porte verre">
<section class="porte__marque">{_duo(p)}<div><span class="pastille">{_drapeau("mini-drapeau")} {e(nom_pays)} · espace partenaire</span>
<h1>Les classements de la {e(nom_pays)}, chaque semaine.</h1>
<p>Classements officiels, faits marquants, artistes de la semaine et dossiers prêts pour l'antenne, réservés à {e(p['nom'])}.</p></div>
<p class="porte__pied">Cauri Charts · la référence de la musique ouest-africaine</p></section>
<section class="porte__form"><form method="post"><h2>Connexion</h2><p>Entrez le mot de passe qui vous a été remis.</p>
{f'<p class="erreur" role="alert">{e(erreur)}</p>' if erreur else ''}
<input type="hidden" name="csrfmiddlewaretoken" value="{e(get_token(request))}">
<label for="mdp">Mot de passe</label><input id="mdp" type="password" name="mot_de_passe" autocomplete="current-password" required autofocus>
<button type="submit">Accéder à l'espace</button></form></section></div></main></body></html>""")


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

    html_ = [f"""<header class="tete cadre"><div class="tete__barre verre">{_duo(p)}<div class="tete__droite">{nav_semaine}
<a class="sortir" href="?sortir" title="Se déconnecter"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg><span>Se déconnecter</span></a></div></div>
<nav class="onglets verre" aria-label="Rubriques">{onglets}</nav></header>
<main class="cadre">"""]

    titre = {"accueil": f"Semaine {choisie[-2:]}" if choisie else "Bienvenue", "classements": "Classements officiels",
             "top100": "Les 100 titres de la semaine", "artistes": "Les artistes de la semaine", "fichiers": "Téléchargements"}[vue]
    actions = _boutons(edition) if vue == "accueil" and edition else ""
    html_.append(f'<div class="titre"><div><p class="sur"><span class="pastille">{_drapeau("mini-drapeau")} {e(nom_pays)}</span> {e(p["nom"])} × Cauri Charts</p>'
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

    html_.append(f"""</main><footer class="pied"><div class="cadre"><div class="verre"><span>Cauri Charts · la référence de la musique ouest-africaine ·
mention à l'antenne : « Source : Cauri Charts »</span><span>Espace réservé à {e(p['nom'])} · contact@cauricharts.com</span></div></div></footer>
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


def _date(v):
    """La base renvoie parfois la date en texte (« 2026-11-09 18:02:11 ») : l'onglet Téléchargements plantait (10/11/2026)."""
    from datetime import datetime
    return v if hasattr(v, "strftime") else datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _fichiers(editions: list[dict], choisie: str) -> str:
    if not editions:
        return ('<div class="vide">Le dossier de chaque semaine (PDF, Excel, visuels pour l\'antenne) arrive ici dès la publication '
                'du vendredi soir.</div>')
    blocs = []
    for ed in editions[:20]:
        date = f"Envoyée le {_date(ed['envoye_le']):%d/%m/%Y}" if ed.get("envoye_le") else "Préparée"
        blocs.append(f'<div class="edition{" edition--courante" if ed["semaine"] == choisie else ""}"><div><h3>Semaine {e(ed["semaine"][-2:])}'
                     f'</h3><p>{e(ed["semaine"][:4])} · {date}</p></div><div class="actions">{_boutons(ed)}</div></div>')
    return f'<div class="editions">{"".join(blocs)}</div>'
