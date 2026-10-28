"""Programmation des posts sur Instagram, Facebook et TikTok par Buffer (API GraphQL, offre gratuite : 3 comptes).

BUFFER_API_KEY : clé créée sur https://publish.buffer.com/settings/api.
Les visuels sont donnés par leur adresse publique (Vercel Blob) : Buffer les télécharge lui-même.
Chaque post n'est programmé qu'une fois par compte (journal d'audit) ; il reste annulable dans Buffer jusqu'à l'heure prévue.
"""
import json
import re
import time as time_mod
from datetime import date, datetime, time, timedelta, timezone

from core import audit, db, env
from core.helpers import url
from core.services.platforms import HttpClient, PlatformException

API = "https://api.buffer.com"
# Limites des plateformes pour un carrousel de photos
MAX_IMAGES = {"instagram": 20, "facebook": 10, "tiktok": 35}
NOTIFY_REELS = ("instagram", "tiktok")
PUBLISH_HOUR = 18  # heure de Lomé (UTC) : la fin de journée, quand l'audience est sur son téléphone


def evening(day: date) -> datetime:
    return datetime.combine(day, time(PUBLISH_HOUR), timezone.utc)


def configured() -> bool:
    return bool(env.get("BUFFER_API_KEY", ""))


def call(query: str, variables: dict | None = None, http: HttpClient | None = None) -> dict:
    key = env.get("BUFFER_API_KEY", "")
    if not key:
        raise PlatformException("BUFFER_API_KEY absente")
    resp = (http or HttpClient(30)).request("POST", API, {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                                            json.dumps({"query": query, "variables": variables or {}}).encode())
    try:
        data = json.loads(resp["body"])
    except ValueError:
        data = {}
    if data.get("errors"):
        raise PlatformException("Buffer : " + "; ".join(e.get("message", "?") for e in data["errors"]))
    if resp["status"] != 200 or "data" not in data:
        raise PlatformException(f"Buffer : HTTP {resp['status']}")
    return data["data"]


def channels(http: HttpClient | None = None) -> list:
    """Comptes reliés à Buffer (actifs seulement) : [{id, service, name}]."""
    out = []
    for org in call("query { account { organizations { id } } }", None, http)["account"]["organizations"]:
        found = call("query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id name service isDisconnected isLocked } }",
                     {"o": org["id"]}, http)["channels"]
        out += [c for c in found if not c["isDisconnected"] and not c["isLocked"]]
    return out


def text(post: dict, service: str) -> str:
    """Légende : titre, texte, hashtags ; le lien n'est cliquable que sur Facebook (« lien en bio » ailleurs)."""
    from core.services.social import bilingue
    link = url("/") if service == "facebook" else bilingue.LIEN
    if "localhost" in link or "127.0.0.1" in link:
        link = "https://www.cauricharts.com/"  # un post programmé depuis un poste de travail garde le vrai lien du site
    # Français puis anglais (🇬🇧), dans la limite des légendes Instagram et TikTok (2 200 caractères)
    texte = bilingue.legende(post, link) + mention(post, service)
    texte = hashtags_pays(texte)[:2200] if service == "tiktok" else texte
    return minuscules_hashtags(texte)


def mention(post: dict, service: str) -> str:
    """« 🎤 @compte » de l'artiste sur Instagram et TikTok (comptes trouvés par core.services.social.comptes)."""
    if service not in ("instagram", "tiktok"):
        return ""
    try:
        nom = json.loads(post.get("facts") or "{}").get("artiste")
    except ValueError:
        return ""
    if not nom:
        return ""
    try:
        compte = db.value(f"SELECT {service} FROM artists WHERE lower(name) = lower(?) AND coalesce({service}, '') <> '' "
                          "ORDER BY youtube_subscribers DESC NULLS LAST LIMIT 1", [nom])
    except Exception:  # noqa: BLE001 — colonne tiktok absente d'une vieille base
        return ""
    compte = str(compte or "").lstrip("@")
    if not compte or ("@" + compte).lower() in (post.get("caption") or "").lower():
        return ""
    return f"\n\n🎤 @{compte}"


def minuscules_hashtags(texte: str) -> str:
    """Règle du fondateur (26/10/2026) : les hashtags toujours en minuscules (#cauricharts, #togo, #sethlo)."""
    return re.sub(r"#[^\s#.,;:!?)»]+", lambda m: m.group().lower(), texte)


TIKTOK_SIZE = (1080, 1920)  # TikTok refuse les photos de plus de 2 073 600 pixels : nos visuels 4K sont réduits


def tiktok_copies(files: list, base: str) -> list:
    """Copie de 1080 de large de chaque visuel (4:5), créée une fois et déposée à côté de l'original (« …-tt45.jpg »)."""
    import io
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    from core import storage
    from core.services.news import http_get

    def readable(name: str) -> bool:
        return HttpClient(15).request("HEAD", f"{base}/media/social/{name}")["status"] == 200

    def one(f: str) -> str:
        small = f.rsplit(".", 1)[0] + "-tt45n.jpg"
        try:
            if readable(small):
                return small
            data = http_get(f"{base}/media/social/{f}", binary=True)
            img = Image.open(io.BytesIO(data)).convert("RGB")
            if img.size[0] > TIKTOK_SIZE[0]:   # 1080 de large, proportions gardées (4:5 -> 1080 × 1350)
                img = img.resize((TIKTOK_SIZE[0], round(img.size[1] * TIKTOK_SIZE[0] / img.size[0])), Image.LANCZOS)
                # légère netteté après réduction : TikTok recompresse fort, les images sortaient « pas propres » (19/10/2026)
                from PIL import ImageFilter
                img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=2))
            out = io.BytesIO()
            img.save(out, "JPEG", quality=95, subsampling=0, optimize=True)  # couleurs pleines : le texte coloré reste net après la recompression de TikTok
            storage.blob_put(f"media/social/{small}", out.getvalue(), "image/jpeg")
            # une copie toute neuve n'est pas toujours servie tout de suite : Buffer la téléchargerait trop tôt
            # (« Image could not be read from its URL », portrait du 6 octobre 2026) -> on attend qu'elle soit lisible
            for wait in (1, 2, 3, 5, 8):
                if readable(small):
                    return small
                time_mod.sleep(wait)
            return small
        except Exception:  # noqa: BLE001 — sans copie, on garde l'original (TikTok le refusera, l'erreur sera visible)
            return f

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, files))


def images(post: dict, service: str) -> list:
    """Adresses publiques des visuels : 4:5 partout, TikTok compris (couverture puis titres)."""
    from core import storage
    base = storage.blob_public_url()
    if not base:
        raise PlatformException("pas d'adresse publique pour les images (Blob)")
    try:
        slides = json.loads(post.get("carousel") or "[]") or []
    except ValueError:
        slides = []
    if service == "tiktok":
        # Format Instagram 4:5 aussi sur TikTok (décision du 19/10/2026) : en 9:16, la légende et les boutons de TikTok
        # cachaient le texte du bas de l'image
        files = [s["file"] if isinstance(s, dict) else s for s in slides] or [post.get("image_square")]
        files = tiktok_copies([f for f in files if f][:MAX_IMAGES["tiktok"]], base)
    else:
        files = [s["file"] if isinstance(s, dict) else s for s in slides] or [post.get("image_square")]
    return [f"{base}/media/social/{f}" for f in files if f][:MAX_IMAGES.get(service, 10)]


def video_url(post: dict) -> str | None:
    from core import storage
    base = storage.blob_public_url()
    return f"{base}/media/social/{post['video']}" if base and post.get("video") else None


INSTAGRAM_PAR_JOUR = 4
FACEBOOK_PAR_JOUR = 4
# Ce qui mérite Instagram (moins de posts, mieux faits — analyse du 17/10/2026) : vidéos du jour et formats,
# classements officiels, flashs, la première actu de chaque édition Cauri Monde, le magazine de la semaine
INSTAGRAM_THEMES = ("format-", "flash", "monde-matin-1", "monde-soir-1", "hebdo")


# Hors quota sur tous les réseaux : le classement officiel du mardi (notre cœur, écarté le 27/10/2026 parce que
# Cauri Monde avait rempli la journée) et les posts du Studio choisis à la main
PRIORITAIRES = ("format-officiel", "format-studio", "format-top")   # + tops et versus validés par le fondateur


def facebook_ok(post: dict) -> bool:
    """Facebook (23/10/2026) : 75 posts la semaine 43 pour une portée médiane de 0. Même règle qu'Instagram :
    thèmes prioritaires, FACEBOOK_PAR_JOUR posts par jour au plus ; les posts de Cauri Studio passent toujours."""
    theme = str(post.get("theme") or "")
    if theme.startswith(PRIORITAIRES):
        return True
    if not theme.startswith(INSTAGRAM_THEMES):
        return False
    deja = int(db.value("""SELECT COUNT(DISTINCT a.reason) FROM audit_log a
                           JOIN social_posts p ON a.reason LIKE 'post-' || p.id || '-facebook%'
                           WHERE a.action = 'buffer.post' AND a.created_at >= CURRENT_DATE
                           AND p.theme NOT LIKE 'format-studio%'""") or 0)
    return deja < FACEBOOK_PAR_JOUR


def instagram_ok(post: dict) -> bool:
    """Post retenu pour Instagram : thème prioritaire et moins de INSTAGRAM_PAR_JOUR posts déjà envoyés aujourd'hui.
    Les posts de Cauri Studio, choisis à la main par le fondateur, passent toujours et ne comptent pas dans la limite."""
    if str(post.get("theme") or "").startswith(PRIORITAIRES):
        return True
    if not str(post.get("theme") or "").startswith(INSTAGRAM_THEMES):
        return False
    deja = int(db.value("""SELECT COUNT(DISTINCT a.reason) FROM audit_log a
                           JOIN social_posts p ON a.reason LIKE 'post-' || p.id || '-instagram%'
                           WHERE a.action = 'buffer.post' AND a.created_at >= CURRENT_DATE
                           AND p.theme NOT LIKE 'format-studio%'""") or 0)
    return deja < INSTAGRAM_PAR_JOUR


# TikTok (23/10/2026) : 72 % de l'audience en France, attirée par les sujets mondiaux (Céline Dion, Kendrick…), et deux
# vidéos du Studio exclues du fil « Pour toi » (contenu repris d'un autre compte). TikTok devient le réseau de l'Afrique :
# sujets africains seulement, jamais une vidéo reprise, 3 par jour au plus, aux heures de pointe ouest-africaines.
TIKTOK_PAR_JOUR = 3
TIKTOK_HEURES = ((12, 14), (18, 22))   # GMT
REPRISE = re.compile(r"source\s*:\s*@\S+\s+sur\s+(tiktok|instagram)", re.I)
PAYS_HASHTAGS = [(re.compile(p, re.I), h) for p, h in (
    (r"b[ée]nin", "#Benin #229"), (r"\btogo", "#Togo #228"), (r"c[ôo]te d.ivoire|abidjan|ivoirien", "#CoteDIvoire #225"),
    (r"nig[ée]ria|naija|lagos", "#Naija #Nigeria"), (r"ghana|accra", "#Ghana #233"), (r"s[ée]n[ée]gal|dakar", "#Senegal #221"),
    (r"\bmali\b|bamako", "#Mali #223"), (r"burkina", "#BurkinaFaso #226"), (r"guin[ée]e", "#Guinee #224"),
    (r"\bniger\b|niamey", "#Niger #227"), (r"cameroun", "#Cameroun #237"))]


def tiktok_refus(post: dict) -> str | None:
    """Raison de ne pas envoyer ce post sur TikTok, ou None."""
    theme = str(post.get("theme") or "")
    if REPRISE.search(post.get("caption") or ""):
        return "tiktok : vidéo reprise d'un autre compte (non recommandée par TikTok)"
    if theme.startswith(PRIORITAIRES):
        return None   # classement officiel et posts choisis à la main dans le Studio (actu chaude…) : jamais bloqués (24/10/2026)
    if theme.startswith(("monde", "flash", "ecoutes_monde")):
        try:
            fiches = json.loads(post.get("facts") or "{}").get("fiches") or []
        except ValueError:
            fiches = []
        from core.services.social.monde import africain
        if not fiches or not africain(fiches[0]):
            return "tiktok : sujet mondial (TikTok réservé à l'Afrique)"
    if video_seule(post):
        return None   # vidéos (clips, interviews) prioritaires sur TikTok : hors limite (24/10/2026), la limite vise les photos
    deja =int(db.value("""SELECT COUNT(DISTINCT substring(reason from 'post-(\\d+)-')) FROM audit_log
                           WHERE action = 'buffer.post' AND reason LIKE 'post-%-tiktok%' AND created_at >= CURRENT_DATE""") or 0)
    if deja >= TIKTOK_PAR_JOUR:
        return f"tiktok : {TIKTOK_PAR_JOUR} posts par jour au plus"
    return None


def heure_tiktok(when: datetime | None) -> datetime | None:
    """Ramène l'heure de publication TikTok dans le prochain créneau de pointe africain (12-14 h ou 18-22 h GMT)."""
    if when is None:
        return None
    w = when.astimezone(timezone.utc)
    if any(a <= w.hour < b for a, b in TIKTOK_HEURES):
        return when
    for jour in (0, 1):
        for a, _ in TIKTOK_HEURES:
            c = (w + timedelta(days=jour)).replace(hour=a, minute=0, second=0, microsecond=0)
            if c > w:
                return c
    return when


def hashtags_pays(texte: str) -> str:
    """Hashtags des pays cités dans la légende (signal local pour TikTok)."""
    tags = [h for rx, h in PAYS_HASHTAGS if rx.search(texte) and h.split()[0].lower() not in texte.lower()]
    return (texte + "\n" + " ".join(tags)) if tags else texte


def direct(ch: dict, post: dict, when: datetime | None) -> bool:
    """Envoi direct par l'API Meta (25/10/2026) : Instagram et Facebook, posts à publier dans les 15 min (Studio, file
    d'attente, flashs) ; les posts programmés plus tard et ceux où l'on ajoute la musique dans l'appli restent sur Buffer."""
    from core.services import meta
    if ch["service"] not in ("instagram", "facebook") or not meta.actif():
        return False
    if ch["service"] == "instagram" and (video_muette(post) or notification_demandee(post)):
        return False
    return when is None or when <= datetime.now(timezone.utc) + timedelta(minutes=15)


def video_muette(post: dict) -> bool:
    """Vidéo maison sans son (photos libres) : Instagram et TikTok en notification, pour ajouter le son officiel."""
    try:
        return json.loads(post.get("facts") or "{}").get("kind") == "format-video"
    except ValueError:
        return False


def reseaux(post: dict) -> set | None:
    """Plateformes choisies pour ce post dans Cauri Studio (facts « reseaux »), ou None = toutes."""
    try:
        r = json.loads(post.get("facts") or "{}").get("reseaux")
    except ValueError:
        return None
    return set(r) if r is not None else None   # [] = aucun réseau (TikTok parti en brouillon seul), pas « tous »


def notification_demandee(post: dict) -> bool:
    """Cauri Studio, « J'ajoute ma musique dans l'appli » : Instagram et TikTok en notification (20/10/2026)."""
    try:
        return bool(json.loads(post.get("facts") or "{}").get("notifier"))
    except ValueError:
        return False


def video_seule(post: dict) -> bool:
    """Post vidéo à part entière (extrait de clip au refrain) : la vidéo est le post, avec son propre son."""
    try:
        return json.loads(post.get("facts") or "{}").get("kind") in ("format-clip", "format-video") and bool(post.get("video"))
    except ValueError:
        return False


def payload(post: dict, channel: dict, due_at: datetime | None, reel: bool = False) -> dict:
    """Carrousel de photos, ou vidéo 9:16 (reel Instagram et Facebook, vidéo TikTok) si reel=True."""
    service = channel["service"]
    if reel:
        video = video_url(post)
        if not video:
            raise PlatformException("pas de vidéo pour ce post")
        assets = [{"video": {"url": video}}]
    else:
        pics = images(post, service)
        if not pics:
            raise PlatformException("pas d'image pour ce post")
        assets = [{"image": {"url": p}} for p in pics]
    # Vidéo sur Instagram et TikTok : Buffer prévient le téléphone à l'heure dite et ouvre l'application, où l'on ajoute
    # un son de leur bibliothèque (impossible par API). Facebook reçoit le reel par le partage automatique d'Instagram.
    # TikTok : TOUJOURS en notification (carrousels compris) — le fondateur ajoute lui-même un son tendance (12/10/2026)
    # Vidéo au refrain (son du clip déjà dedans) : publiée automatiquement partout, TikTok compris (17/10/2026)
    # Règle du fondateur (17/10/2026) : jamais de notification sur Instagram (il ajoute la musique après publication) ;
    # TikTok en notification (le son ne s'ajoute pas après coup), sauf l'extrait de clip autorisé qui a déjà le sien
    # Vidéo maison muette (18/10/2026) : Instagram aussi en notification, pour y mettre le son avant de publier
    notify = ((video_muette(post) or notification_demandee(post)) and service in ("instagram", "tiktok")) or (
        service == "tiktok" and not (video_seule(post) and not video_muette(post)))
    data = {"channelId": channel["id"], "text": text(post, service), "assets": assets,
            "schedulingType": "notification" if notify else "automatic", "needsApproval": False,
            "mode": "customScheduled" if due_at else "addToQueue"}
    if due_at:
        data["dueAt"] = due_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if service == "instagram":
        # Plusieurs images dans un post « post » : Instagram en fait un carrousel
        data["metadata"] = {"instagram": {"type": "reel" if reel else "post", "shouldShareToFeed": True}}
    elif service == "facebook":
        data["metadata"] = {"facebook": {"type": "reel" if reel else "post"}}
    elif service == "tiktok":
        data["metadata"] = {"tiktok": {"title": post["title"][:90]}}
    return data


CREATE = """mutation($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id dueAt } }
  ... on InvalidInputError { message } ... on LimitReachedError { message } ... on UnauthorizedError { message }
  ... on NotFoundError { message } ... on UnexpectedError { message } ... on RestProxyError { message } } }"""


def capacity(http: HttpClient | None = None) -> tuple[int, int] | None:
    """(limite, posts déjà programmés) de l'organisation Buffer — l'offre gratuite plafonne la file à 10 posts."""
    try:
        orgs = call("query { account { organizations { id limits { scheduledPosts } } } }", None, http)["account"]["organizations"]
        limit, used = 0, 0
        for org in orgs:
            limit += int(org["limits"]["scheduledPosts"])
            found = call("query($o: OrganizationId!) { posts(first: 100, input: {organizationId: $o, filter: {status: [scheduled]}})"
                         " { edges { node { id } } } }", {"o": org["id"]}, http)["posts"]
            used += len(found.get("edges") or [])
        return limit, used
    except (PlatformException, KeyError, TypeError, ValueError):
        return None  # inconnu : on tente quand même, Buffer refusera ce qui dépasse


def failed(result: str) -> bool:
    """Vrai si un envoi du compte rendu de schedule() n'a pas abouti (refus, limite, image manquante…)."""
    parts = [p.strip() for p in (result or "").split(",") if p.strip()]
    return not parts or any(not p.endswith("programmé") for p in parts)


def schedule(post: dict, due_at: datetime | None = None, force: bool = False, http: HttpClient | None = None) -> str:
    """Programme le post sur chaque compte relié : le carrousel à l'heure prévue, puis la vidéo du Top le lendemain
    à midi (deux publications pour un post). Sans date, chaque envoi prend la prochaine place de la file Buffer.
    La place libre de la file est vérifiée d'abord : faute de place, la vidéo est sacrifiée, puis tout le post
    (jamais un carrousel publié sur un seul réseau)."""
    if not configured():
        return "Buffer non configuré (BUFFER_API_KEY)"
    from core.services.social import hashtags
    post = hashtags.preparer(post)   # hashtags du sujet, les plus utilisés (27/10/2026)
    done = []
    jobs = [("", False, due_at)]
    if video_seule(post):
        jobs = [("-reel", True, due_at)]   # extrait de clip : la vidéo seule, sur tous les comptes (Facebook compris)
    elif post.get("video"):
        # La vidéo le lendemain à midi : le soir reste au carrousel du jour et au magazine du dimanche
        jobs.append(("-reel", True, due_at + timedelta(hours=18) if due_at else None))
    permis = reseaux(post)
    chans = [ch for ch in channels(http) if ch["service"] in MAX_IMAGES and (permis is None or ch["service"] in permis)]

    def todo(js):
        return [(ch, s, r, w) for ch in chans for s, r, w in js
                if not direct(ch, post, w)   # envoi direct Meta : ne prend pas de place dans la file Buffer
                and not (r and ch["service"] not in NOTIFY_REELS and (not video_seule(post) or video_muette(post)))  # Facebook : reel d'Instagram repartagé
                and (force or not db.value("SELECT 1 FROM audit_log WHERE action = 'buffer.post' AND reason = ? LIMIT 1",
                                           [f"post-{post['id']}-{ch['service']}{s}"]))]
    room = capacity(http)
    if room:
        free = room[0] - room[1]
        if len(todo(jobs)) > free and len(jobs) > 1:
            jobs = jobs[:1]
            done.append(f"vidéo non programmée (file Buffer pleine : {room[1]}/{room[0]})")
        if len(todo(jobs)) > free:
            return f"file Buffer pleine : {room[1]}/{room[0]} posts programmés, il faut {len(todo(jobs))} places — rien programmé"
    for ch in chans:
        if ch["service"] == "instagram" and not instagram_ok(post):
            done.append("instagram : réservé aux meilleurs posts du jour")
            continue
        if ch["service"] == "facebook" and not facebook_ok(post):
            done.append("facebook : réservé aux meilleurs posts du jour")
            continue
        if ch["service"] == "tiktok" and (refus := tiktok_refus(post)):
            done.append(refus)
            continue
        for suffix, reel, when in jobs:
            if reel and ch["service"] not in NOTIFY_REELS and (not video_seule(post) or video_muette(post)):
                continue  # Facebook : le reel publié sur Instagram y est repartagé automatiquement, avec son son
            label = ch["service"] + (" (vidéo)" if reel else "")
            key = f"post-{post['id']}-{ch['service']}{suffix}"
            if not force and db.value("SELECT 1 FROM audit_log WHERE action = 'buffer.post' AND reason = ? LIMIT 1", [key]):
                done.append(f"{label} déjà programmé")
                continue
            try:
                if direct(ch, post, when):   # Instagram / Facebook en direct par l'API Meta (collaboration de l'artiste)
                    from core.services import meta
                    mid = (meta.instagram if ch["service"] == "instagram" else meta.facebook)(post, reel)
                    audit.log(None, "buffer.post", "social_post", post["id"], key, {"meta_id": mid, "direct": True}, None)
                    done.append(f"{label} programmé")
                    continue
                # Studio : publié quand le fondateur l'envoie ; les automatismes attendent le créneau de pointe
                studio = str(post.get("theme") or "").startswith("format-studio")
                quand = heure_tiktok(when) if ch["service"] == "tiktok" and not studio else when
                r = call(CREATE, {"input": payload(post, ch, quand, reel)}, http)["createPost"]
            except PlatformException as exc:
                done.append(f"{label} : {exc}")
                continue
            if "post" not in r:
                done.append(f"{label} : {r.get('message', 'refusé')}")
                continue
            audit.log(None, "buffer.post", "social_post", post["id"], key, {"buffer_id": r["post"]["id"], "due": r["post"].get("dueAt")}, None)
            done.append(f"{label} programmé")
    return ", ".join(done) or "aucun compte relié à Buffer"
