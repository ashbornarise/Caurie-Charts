"""Agents de contrôle : chaque nuit, après la publication, ils relisent tout le site.

  editions     : les numéros Cauri Hebdo et Cauri Matin donnent-ils le même n°1 que le classement ? Sinon, corrigé.
  catalogue    : les artistes du Top 50 ont-ils un pays confirmé, une photo, une chaîne YouTube ? Correction ciblée.
  publications : les posts programmés n'affichent-ils que des artistes confirmés, avec des images en ligne ?
  relecteur IA : la légende de chaque post à venir n'affirme-t-elle rien qui ne soit dans ses faits ?
  pages        : les pages principales du site répondent-elles, sans texte vide (« None ») ni image cassée ?
Chaque constat est noté (corrigé, alerte, info), affiché dans Admin > Contrôles et repris dans le rapport du matin.
"""
import json
import re

from core import budget, clock, db
from core.repos import now_utc

LEVELS = ("corrige", "alerte", "info")


class Run:
    def __init__(self):
        self.findings = []

    def note(self, agent: str, level: str, message: str, link: str | None = None) -> None:
        self.findings.append({"agent": agent, "level": level, "message": message[:600], "link": link})

    def save(self) -> list:
        for f in self.findings:
            db.insert("agent_findings", f)
        return self.findings


# ------------------------------------------------------------ éditions

def check_editions(run: Run) -> None:
    from core.services import live_chart, magazine
    top = [r for r in live_chart.build(None, None, 20, "prime", 20, "latest")["rows"] if not r.get("is_artist") and r.get("status") == "active"]
    if not top:
        return
    one = top[0]
    year, week, _ = clock.today().isocalendar()
    art = db.one("SELECT id, title, slug FROM news WHERE external_guid = ?", [f"cauri-hebdo-{year}-W{week:02d}"])
    if art and one["title"] not in art["title"]:
        f = magazine.facts()
        new = magazine.write(f, str(week))
        if new and new["title"] != art["title"]:
            db.update("news", {"title": new["title"], "summary": new["summary"],
                               "body": new["body"] + f"\n\nMis à jour le {clock.today():%d/%m} : le classement a évolué depuis la première publication."},
                      "id = :id", {"id": art["id"]})
            run.note("editions", "corrige", f"Cauri Hebdo semaine {week} : n°1 mis à jour (« {one['title']} » de {one['artist_name']}).",
                     f"/actualites/{art['slug']}")


# ------------------------------------------------------------ catalogue

def check_catalogue(run: Run) -> None:
    from core.services import live_chart
    rows = [r for r in live_chart.build(None, None, 50, "prime", 20, "latest")["rows"] if not r.get("is_artist")]
    ids = list(dict.fromkeys(int(r["artist_id"]) for r in rows))
    if not ids:
        return
    arts = db.all(f"""SELECT id, name, slug, status, image_url, youtube_channel_id, youtube_subscribers, image_locked, photo_candidates
                      FROM artists WHERE id IN ({','.join(map(str, ids))})""")
    pending = [a for a in arts if a["status"] == "pending"]
    if pending:
        run.note("catalogue", "alerte", f"{len(pending)} artistes du Top 50 attendent la confirmation de leur pays (absents des posts) : "
                 + ", ".join(a["name"] for a in pending[:12]), "/admin/import#artistes")
    # Photos : recherche immédiate pour ceux du Top 50 qui n'en ont pas
    no_photo = [a for a in arts if a["status"] == "active" and not a["image_url"]]
    if no_photo:
        from core.services.imports.photos import ArtistPhotos, best
        from core.services.platforms import HttpClient
        P, fixed = ArtistPhotos(HttpClient(20)), []
        for a in no_photo[:10]:
            if budget.over():
                break
            pick = best([c for c in P.collect(a) if c["source"] != "presse"])
            if pick:
                db.update("artists", {"image_url": pick["site"], "image_hd_url": pick["url"], "image_source": pick["source"],
                                      "image_credit": pick.get("credit"), "photo_checked_at": now_utc()}, "id = :id", {"id": a["id"]})
                fixed.append(a["name"])
        if fixed:
            run.note("catalogue", "corrige", "Photos trouvées : " + ", ".join(fixed))
        rest = [a["name"] for a in no_photo if a["name"] not in fixed]
        if rest:
            run.note("catalogue", "alerte", "Sans photo dans le Top 50 (à fournir via Admin > fiche artiste) : " + ", ".join(rest[:12]))
    # Chaînes YouTube : recherche immédiate pour les artistes confirmés du Top 50
    no_channel = [a for a in arts if a["status"] == "active" and not a["youtube_channel_id"]]
    if no_channel:
        from core import env
        from core.services.imports.channel_sync import YouTubeChannelSync, refresh_channel_stats
        from core.services.platforms import HttpClient, YouTubeQuota
        S, key, found = YouTubeChannelSync(HttpClient(30)), env.get("YOUTUBE_API_KEY", ""), []
        for a in no_channel[:8]:
            if budget.over() or not key or YouTubeQuota.remaining() < YouTubeQuota.RESERVE + 300:
                break
            ch = S._find_channel(a["name"], key, a["id"])
            db.update("artists", {"channel_checked_at": now_utc(), **({"youtube_channel_id": ch} if ch else {})}, "id = :id", {"id": a["id"]})
            if ch:
                found.append(a["name"])
        if found:
            refresh_channel_stats(200)
            run.note("catalogue", "corrige", "Chaînes YouTube rattachées : " + ", ".join(found))
        rest = [a["name"] for a in no_channel if a["name"] not in found]
        if rest:
            run.note("catalogue", "info", "Sans chaîne YouTube confirmée dans le Top 50 : " + ", ".join(rest[:12]))


# ------------------------------------------------------------ publications

def check_publications(run: Run) -> None:
    from core import storage
    from core.services.platforms import HttpClient
    posts = db.all("""SELECT id, theme, title, slot_date, facts, carousel FROM social_posts
                      WHERE slot_date >= CURRENT_DATE - 1 AND status IN ('draft', 'approved') ORDER BY slot_date""")
    base = storage.blob_public_url()
    for p in posts:
        try:
            facts = json.loads(p["facts"] or "{}")
            slides = json.loads(p["carousel"] or "[]")
        except ValueError:
            continue
        names = {str(e.get("artist") or "") for e in facts.get("top") or []} - {""}
        if names:
            bad = [r["name"] for r in db.all(f"SELECT name FROM artists WHERE status <> 'active' AND name IN ({','.join(['?'] * len(names))})", list(names))]
            if bad:
                run.note("publications", "alerte", f"« {p['title']} » ({p['slot_date']}) montre des artistes non confirmés : {', '.join(bad)}.", "/admin/posts")
        if base and slides:
            first = slides[0]["file"] if isinstance(slides[0], dict) else slides[0]
            if HttpClient(15).request("HEAD", f"{base}/media/social/{first}")["status"] != 200:
                run.note("publications", "alerte", f"« {p['title']} » ({p['slot_date']}) : la couverture n'est plus en ligne.", "/admin/posts")


OTHER_MEASURES = {"Shazam": ["vues youtube", "vues sur youtube", "stream", "écoutes", "deezer", "apple music"],
                  "Deezer": ["vues youtube", "vues sur youtube", "shazam", "apple music"],
                  "Apple Music": ["vues youtube", "vues sur youtube", "shazam", "deezer"],
                  "YouTube": ["shazam", "apple music", "streams sur", "écoutes sur deezer"]}


def check_coherence(run: Run) -> None:
    """Un post sur une plateforme ne mélange jamais ses mesures avec celles d'une autre (ex. un post Shazam avec des vues
    YouTube sur les diapositives, ou des « streams » Shazam : Shazam compte des recherches, pas des écoutes)."""
    from core.services.social.generator import PostGenerator
    posts = db.all("""SELECT id, theme, title, caption, carousel, slot_date FROM social_posts
                      WHERE slot_date >= CURRENT_DATE AND status IN ('draft', 'approved') ORDER BY slot_date""")
    for p in posts:
        platform = PostGenerator.THEME_PLATFORM.get(p["theme"])
        if not platform:
            continue
        try:
            slides = json.loads(p["carousel"] or "[]")
        except ValueError:
            slides = []
        wrong = [s.get("figure") for s in slides if isinstance(s, dict) and s.get("figure") and platform.lower() not in s["figure"].lower()
                 and not (platform == "YouTube" and "vues" in s["figure"].lower())]
        words = [w for w in OTHER_MEASURES.get(platform, []) if w in (p["caption"] or "").lower()]
        if wrong or words:
            run.note("coherence", "alerte", f"« {p['title']} » ({p['slot_date']}) : post {platform} qui cite "
                     + ", ".join([f"« {w} » sur les diapositives" for w in wrong[:3]] + [f"« {w} » dans la légende" for w in words])
                     + ". À corriger avant publication.", "/admin/posts")


def review_captions(run: Run) -> None:
    """Relecteur IA : compare la légende de chaque post à venir à ses faits ; signale toute affirmation non vérifiable."""
    from core.services import ai
    client = ai.make()
    if not client or not client.is_available():
        return
    posts = db.all("""SELECT id, title, caption, facts, slot_date FROM social_posts
                      WHERE slot_date >= CURRENT_DATE AND status IN ('draft', 'approved') ORDER BY slot_date LIMIT 6""")
    system = ("Tu es relecteur pour un classement musical. On te donne les FAITS (JSON) et la LÉGENDE d'un post. "
              "Liste uniquement les affirmations de la légende qui ne sont PAS soutenues par les faits (chiffre, rang, pays, "
              "plateforme, record inventé). Réponds en JSON : {\"problemes\": [\"...\"]} ; liste vide si tout est exact.")
    for p in posts:
        if budget.over():
            break
        try:
            facts = {k: v for k, v in json.loads(p["facts"] or "{}").items() if k not in ("ranks",)}
            if facts.get("kind") in ("presentation", "hebdo") or len(json.dumps(facts, default=str)) < 120:
                continue  # texte de la rédaction ou sans faits à comparer
            answer = client.ask(system, json.dumps({"faits": facts, "legende": p["caption"]}, ensure_ascii=False, default=str)[:12000], 500)
            problems = (ai.extract_json(answer["text"]) or {}).get("problemes") or []
        except Exception:  # noqa: BLE001
            continue
        if problems:
            run.note("relecteur IA", "alerte", f"« {p['title']} » ({p['slot_date']}) : " + " ; ".join(map(str, problems[:3])), "/admin/posts")


# ------------------------------------------------------------ pages

def check_pages(run: Run) -> None:
    from core import env
    from core.services.platforms import HttpClient
    site = (env.get("APP_URL", "") or "https://cauricharts.com").rstrip("/")
    pages = ["/", "/classements/afrique-de-l-ouest", "/actualites", "/methodologie", "/a-propos"]
    pages += [f"/classements/{r['code'].lower()}/prime" for r in db.all("SELECT code FROM countries WHERE is_active = 1 ORDER BY sort_order LIMIT 6")]
    pages += [f"/artiste/{r['slug']}" for r in db.all("""SELECT a.slug FROM artists a WHERE a.status = 'active' ORDER BY COALESCE(a.youtube_subscribers, 0) DESC LIMIT 5""")]
    # articles déjà en ligne seulement : un article programmé (Distinctions, 6 oct. 2026 à 16 h) répond 404 avant son heure
    pages += [f"/actualites/{r['slug']}" for r in db.all(
        "SELECT slug FROM news WHERE origin = 'manual' AND status = 'published' AND published_at <= ? ORDER BY published_at DESC LIMIT 2",
        [now_utc()])]
    http = HttpClient(20)
    for path in pages:
        try:
            r = http.request("GET", site + path, {"User-Agent": "CauriCharts-controle/1.0 (bot)"})
        except Exception as exc:  # noqa: BLE001
            run.note("pages", "alerte", f"{path} injoignable : {exc}", path)
            continue
        if r["status"] != 200:
            run.note("pages", "alerte", f"{path} répond {r['status']}.", path)
            continue
        text = re.sub(r"<script.*?</script>|<style.*?</style>", "", r["body"], flags=re.S)
        if re.search(r">\s*(None|nan|undefined|null)\s*<", text):
            run.note("pages", "alerte", f"{path} affiche une valeur vide (« None »).", path)


AGENTS = [("éditions", check_editions), ("catalogue", check_catalogue), ("publications", check_publications), ("cohérence", check_coherence),
          ("relecteur IA", review_captions), ("pages", check_pages)]


def run_all() -> list:
    run = Run()
    for name, fn in AGENTS:
        try:
            fn(run)
        except Exception as exc:  # noqa: BLE001 — un agent en panne n'arrête pas les autres
            run.note(name, "alerte", f"agent en panne : {exc}")
    found = run.save()
    fixed = sum(1 for f in found if f["level"] == "corrige")
    alerts = sum(1 for f in found if f["level"] == "alerte")
    return [f"{fixed} corrections, {alerts} alertes"] + [f"[{f['level']}] {f['agent']} : {f['message']}" for f in found]
