"""Cauri Studio — section Photos (20/10/2026) : récupérer les photos d'un post (Instagram, TikTok photo, X, Facebook…)
pour la banque de l'artiste.

Le serveur télécharge toutes les images du post (carrousel compris) avec gallery-dl ; si la plateforme refuse le serveur,
l'image principale du post (og:image) sert de repli. Les images sont proposées dans l'appli : seules celles que le
fondateur sélectionne entrent dans la banque (artist_photos), avec le crédit du compte d'origine.
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile

import requests
from PIL import Image

from core import db, storage

MAX_PHOTOS = 20
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic")


def _jpeg(chemin: str) -> bytes | None:
    try:
        with Image.open(chemin) as im:
            im = im.convert("RGB")
            if min(im.size) < 400:          # vignettes et avatars : pas pour nos couvertures
                return None
            out = io.BytesIO(); im.save(out, format="JPEG", quality=94)
            return out.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _gallery_dl(lien: str, dossier: str) -> tuple[list[str], dict]:
    """(images téléchargées, infos du compte) via gallery-dl."""
    cmd = [sys.executable, "-m", "gallery_dl", "--range", f"1-{MAX_PHOTOS}", "--write-metadata", "-D", dossier, lien]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    images = sorted(f for f in glob.glob(os.path.join(dossier, "*")) if f.lower().endswith(EXTENSIONS))
    infos = {}
    for m in glob.glob(os.path.join(dossier, "*.json"))[:1]:
        try:
            d = json.load(open(m, encoding="utf-8"))
            compte = d.get("username") or (d.get("author") or {}).get("name") if isinstance(d.get("author"), dict) else d.get("username")
            infos = {"compte": compte or d.get("owner_username") or d.get("uploader") or "", "plateforme": d.get("category", "")}
        except (ValueError, OSError):
            pass
    return images, infos


COMPTES: list = []   # compte Instagram auteur du post, relevé au passage (crédit, reconnaissance de l'artiste)
LEGENDES: list = []  # texte du post (noms d'artistes cités)
CONTEXTES: dict = {} # url de l'image -> {compte, legende, identifies} du post d'où elle vient
PAR_CHEMIN: dict = {}  # fichier téléchargé -> même contexte


def _images_json(obj, out: list) -> None:
    """Toutes les images (plus grande taille) d'une réponse Instagram : carrousel compris, vidéos exclues."""
    if isinstance(obj, dict):
        ctx, debut = None, len(out)
        if (obj.get("carousel_media") or obj.get("image_versions2")) and isinstance(obj.get("user") or obj.get("owner"), dict):
            COMPTES.append((obj.get("user") or obj.get("owner")).get("username") or "")
            legende = obj["caption"].get("text") or "" if isinstance(obj.get("caption"), dict) else ""
            if legende:
                LEGENDES.append(legende)
            identifies = set()
            for porteur in [obj] + (obj.get("carousel_media") if isinstance(obj.get("carousel_media"), list) else []):
                for t in ((porteur.get("usertags") or {}).get("in") or []) if isinstance(porteur, dict) else []:
                    identifies.add(((t.get("user") or {}).get("username") or "").lower())
            for c in obj.get("coauthor_producers") or []:
                if isinstance(c, dict):
                    identifies.add((c.get("username") or "").lower())
            ctx = {"compte": COMPTES[-1], "legende": legende, "identifies": sorted(i for i in identifies if i)}
        for m in obj.get("carousel_media") or [] if isinstance(obj.get("carousel_media"), list) else []:
            c = (m.get("image_versions2") or {}).get("candidates") or []
            if c and m.get("media_type") in (1, None):
                out.append(max(c, key=lambda x: x.get("width") or 0)["url"])
        if not obj.get("carousel_media") and obj.get("media_type") == 1 and (obj.get("image_versions2") or {}).get("candidates"):
            c = obj["image_versions2"]["candidates"]
            out.append(max(c, key=lambda x: x.get("width") or 0)["url"])
        if ctx:
            for u in out[debut:]:
                CONTEXTES.setdefault(u, ctx)
        for v in obj.values():
            _images_json(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _images_json(v, out)


def _instagram_navigateur(lien: str, dossier: str, defilements: int = 0, maximum: int = MAX_PHOTOS) -> list[str]:
    """Post (ou profil) Instagram public ouvert dans un navigateur sans interface, sans compte : Instagram envoie les
    données des posts (toutes les images des carrousels) à tout visiteur. Rien n'est connecté à un compte.
    Les vidéos ne sont jamais téléchargées (elles bloquaient le chargement, 20/10/2026)."""
    import asyncio
    trouvees: list = []
    COMPTES.clear(); LEGENDES.clear(); CONTEXTES.clear(); PAR_CHEMIN.clear()

    async def ouvre():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            b = await pw.chromium.launch()
            page = await b.new_page(locale="fr-FR", viewport={"width": 1280, "height": 900})

            async def filtre(route):
                req = route.request
                if req.resource_type in ("media", "font") or re.search(r"\.(mp4|m4a|webm)(\?|$)", req.url):
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", filtre)

            async def reponse(r):
                if "json" in (r.headers.get("content-type") or "") or "graphql" in r.url:
                    try:
                        _images_json(await r.json(), trouvees)
                    except Exception:  # noqa: BLE001
                        pass
            page.on("response", reponse)
            await page.goto(lien.split("?")[0], wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)
            for _ in range(defilements):          # profil : on fait défiler pour charger plus de posts
                await page.mouse.wheel(0, 2500)
                await page.wait_for_timeout(1800)
            for bloc in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', await page.content(), re.S):
                try:
                    _images_json(json.loads(bloc), trouvees)
                except Exception:  # noqa: BLE001
                    pass
            await b.close()
    try:
        asyncio.run(ouvre())
    except Exception:  # noqa: BLE001
        return []
    chemins = []
    for k, u in enumerate(list(dict.fromkeys(trouvees))[:maximum]):
        try:
            r = requests.get(u, timeout=30)
            r.raise_for_status()
            c = os.path.join(dossier, f"ig{k:02d}.jpg"); open(c, "wb").write(r.content); chemins.append(c)
            if u in CONTEXTES:
                PAR_CHEMIN[c] = CONTEXTES[u]
        except Exception:  # noqa: BLE001
            continue
    return chemins


def _posts_du_profil(lien: str, defilements: int = 1, maximum: int = 24) -> list[str]:
    """Liens des posts PHOTO visibles sur la grille d'un profil (sans compte). Les reels (vidéos) sont ignorés :
    sans connexion, Instagram ne montre que les 12 derniers posts (vignettes) ; les photos complètes sont sur la page
    de chaque post (carrousel entier)."""
    import asyncio
    liens: list = []

    async def ouvre():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            b = await pw.chromium.launch()
            page = await b.new_page(locale="fr-FR", viewport={"width": 1280, "height": 900})

            async def filtre(route):
                if route.request.resource_type in ("media", "font"):
                    await route.abort()
                else:
                    await route.continue_()
            await page.route("**/*", filtre)
            await page.goto(lien.split("?")[0], wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)
            for texte in ("Refuser les cookies optionnels", "Decline optional cookies"):
                try:
                    await page.get_by_text(texte).first.click(timeout=2500)
                    break
                except Exception:  # noqa: BLE001
                    pass
            for _ in range(defilements + 1):
                for h in await page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
                    m = re.search(r"/p/([A-Za-z0-9_-]+)", h or "")
                    if m:
                        liens.append(f"https://www.instagram.com/p/{m.group(1)}/")
                await page.mouse.wheel(0, 2500)
                await page.wait_for_timeout(1800)
            print(f"profil : « {await page.title()} » → {len(set(liens))} posts photo, url finale {page.url[:80]}", flush=True)
            await b.close()
    try:
        asyncio.run(ouvre())
    except Exception as exc:  # noqa: BLE001
        print("profil illisible :", str(exc)[:200], flush=True)
    return list(dict.fromkeys(liens))[:maximum]


def _og_image(lien: str, dossier: str) -> list[str]:
    """Repli : l'image principale annoncée par la page (balise og:image)."""
    try:
        html = requests.get(lien, timeout=20, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}).text
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', html)
        if not m:
            return []
        r = requests.get(m.group(1).replace("&amp;", "&"), timeout=30)
        r.raise_for_status()
        p = os.path.join(dossier, "og.jpg"); open(p, "wb").write(r.content)
        return [p]
    except Exception:  # noqa: BLE001
        return []


def traite(job_id: int, job: dict, p: dict, maj) -> dict:
    """Télécharge les photos du post et les propose (Blob media/artists/candidats/)."""
    maj(job_id, statut="telechargement", erreur=None)
    with tempfile.TemporaryDirectory(prefix=f"cauri-photos-{job_id}-") as tmp:
        images, infos = [], {}
        if "instagram.com" in job["lien"]:
            images = _instagram_navigateur(job["lien"], tmp)   # carrousel complet, sans compte
            m = re.search(r"instagram\.com/([^/?]+)/(?:p|reel)/", job["lien"])
            compte = next((c for c in COMPTES if c), "") or (m.group(1) if m and m.group(1) not in ("p", "reel") else "")
            infos = {"compte": compte, "plateforme": "instagram"}
        if not images:
            images, infos2 = _gallery_dl(job["lien"], tmp)
            infos = infos2 or infos
        if not images:
            images = _og_image(job["lien"], tmp)
        noms = []
        for k, chemin in enumerate(images[:MAX_PHOTOS]):
            donnees = _jpeg(chemin)
            if not donnees:
                continue
            nom = f"studio-{job_id}-{k + 1:02d}.jpg"
            storage.store_media("artists/candidats", nom, donnees, "image/jpeg")
            noms.append(nom)
    if not noms:
        raise RuntimeError("aucune photo récupérée : la plateforme refuse peut-être le serveur (post privé ou connexion exigée)")
    plateforme = infos.get("plateforme") or ""
    compte = infos.get("compte") or ""
    p["compte"] = compte   # l'artiste est choisi par le fondateur dans l'appli (décision du 20/10/2026)
    p.update({"photos": noms, "credit": p.get("credit") or (f"@{compte} sur {plateforme.capitalize()}" if compte else plateforme)})
    maj(job_id, statut="pret", params=p)
    return {"statut": "pret", "video": f"{len(noms)} photos"}


def enregistre(job: dict, indices: list[int], artist_id: int, detourable: bool, note: str = "") -> list[str]:
    """Copie les photos choisies dans la banque de l'artiste (Blob media/artists/plans/ + artist_photos)."""
    from core.services.social import plans
    p = job["params"] if isinstance(job["params"], dict) else json.loads(job["params"] or "{}")
    photos = p.get("photos") or []
    a = db.one("SELECT id, slug FROM artists WHERE id = ?", [artist_id])
    if not a:
        raise ValueError("artiste introuvable")
    plans.creer_table()
    plans.colonnes()
    # l'artiste est confirmé : on retient son compte (Instagram…) pour le reconnaître seul les prochaines fois
    if p.get("compte") and not db.value("SELECT instagram FROM artists WHERE id = ? AND COALESCE(instagram, '') <> ''", [a["id"]]):
        db.run("UPDATE artists SET instagram = ? WHERE id = ?", [p["compte"][:120], a["id"]])
    base = storage.blob_public_url()
    gardees = []
    for i in indices:
        if not 0 <= i < len(photos):
            continue
        r = requests.get(f"{base}/media/artists/candidats/{photos[i]}", timeout=30)
        r.raise_for_status()
        nom = f"{re.sub(r'[^a-z0-9-]', '', a['slug'])}-{'profil' if p.get('mode') == 'profil' else 'lien'}-{job['id']}-{i + 1:02d}.jpg"
        storage.store_media("artists/plans", nom, r.content, "image/jpeg")
        entiere = bool(detourable) or bool((p.get("entieres") or [False] * len(photos))[i])
        largeur, hauteur, score = plans.note_qualite(r.content, entiere)
        if not db.value("SELECT 1 FROM artist_photos WHERE fichier = ?", [nom]):
            db.insert("artist_photos", {"artist_id": a["id"], "fichier": nom, "source": "lien", "source_ref": job["lien"][:120],
                                        "credit": (f"Photo : {p.get('credit')}" if p.get("credit") else "Photo partagée par l'artiste")[:300],
                                        "plan_large": entiere, "note": (note or "")[:600] or None,
                                        "largeur": largeur, "hauteur": hauteur, "score": score})
        gardees.append(nom)
    return gardees


# ---------------------------------------------------------------- envoi depuis le téléphone

def importe(job_id: int, donnees: bytes) -> str | None:
    """Une photo envoyée depuis le téléphone (déjà réduite par l'appli) : ajoutée aux candidates de la tâche."""
    tmp = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
    try:
        tmp.write(donnees); tmp.close()
        jpeg = _jpeg(tmp.name)
    finally:
        os.unlink(tmp.name)
    if not jpeg:
        return None
    job = db.one("SELECT params FROM studio_jobs WHERE id = ?", [job_id])
    p = json.loads(job["params"] or "{}")
    photos = p.get("photos") or []
    if len(photos) >= MAX_PHOTOS:
        return None
    nom = f"studio-{job_id}-{len(photos) + 1:02d}-{os.urandom(2).hex()}.jpg"
    storage.store_media("artists/candidats", nom, jpeg, "image/jpeg")
    p["photos"] = photos + [nom]
    db.update("studio_jobs", {"params": json.dumps(p, ensure_ascii=False), "statut": "pret"}, "id = :id", {"id": job_id})
    return nom


def suggestions(job: dict, indices: list[int], contexte: str = "") -> dict:
    """Accroche et légendes proposées par l'IA à partir des photos choisies (Gemini les regarde)."""
    from core.services.social.studio_montage import analyse
    p = job["params"] if isinstance(job["params"], dict) else json.loads(job["params"] or "{}")
    photos = [p["photos"][i] for i in indices if 0 <= i < len(p.get("photos") or [])][:4]
    base = storage.blob_public_url()
    with tempfile.TemporaryDirectory(prefix="cauri-sugg-") as tmp:
        chemins = []
        for k, nom in enumerate(photos):
            try:
                r = requests.get(f"{base}/media/artists/candidats/{nom}", timeout=20)
                with Image.open(io.BytesIO(r.content)) as im:
                    im = im.convert("RGB"); im.thumbnail((640, 640))
                    c = os.path.join(tmp, f"{k}.jpg"); im.save(c, quality=85); chemins.append(c)
            except Exception:  # noqa: BLE001
                continue
        infos = {"uploader": p.get("credit") or "", "artist": p.get("artiste_nom") or "", "contexte": contexte or p.get("contexte") or ""}
        return analyse(chemins, infos)


# ---------------------------------------------------------------- publication du carrousel

def publie(job_id: int, job: dict, p: dict, maj) -> dict:
    """Carrousel Cauri : couverture actu (1re photo, accroche) puis les autres photos en plein cadre avec le logo ;
    légende FR + EN, crédit ; envoi via Buffer (notification sur Instagram et TikTok si demandé)."""
    from datetime import datetime, timedelta, timezone
    from core.services import buffer
    from core.services.social import couverture2026 as C
    from core.services.social import editorial as E
    from core.services.social import image as PI
    maj(job_id, statut="montage")
    base = storage.blob_public_url()
    choix = [p["photos"][i] for i in p.get("publier_indices", []) if 0 <= i < len(p.get("photos") or [])][:10]
    if not choix:
        raise RuntimeError("aucune photo choisie")
    urls = [f"{base}/media/artists/candidats/{n}" for n in choix]
    PI.DIR.mkdir(parents=True, exist_ok=True)
    nom = f"studio-photos-{job_id}-{os.urandom(2).hex()}"
    fichiers = []
    for k, u in enumerate(urls):
        for fmt, suf in (("feed", ""), ("story", "-916")):
            im = (C.actu(u, (p.get("etiquette") or "PHOTOS").upper()[:28], p.get("accroche") or "", [p.get("artiste_nom") or ""],
                         f"Photo : {p.get('credit')}" if p.get("credit") else "", fmt) if k == 0
                  else C.photo_simple(u, fmt, p.get("credit") or ""))
            PI.save_jpeg(im, PI.DIR / f"{nom}-{k}{suf}.jpg")
        fichiers.append({"file": f"{nom}-{k}.jpg", "tiktok": f"{nom}-{k}-916.jpg", "label": p.get("accroche") or "Photos"})
    legende = (p.get("legende_fr") or p.get("accroche") or "") + (f"\n\n📸 {p.get('credit')}" if p.get("credit") else "")
    artiste = p.get("artiste_nom") or ""
    tags = "#CauriCharts" + (" #" + "".join(ch for ch in artiste if ch.isalnum()) if artiste else "") + " #Afrobeats #MusiqueAfricaine"
    maintenant = datetime.now(timezone.utc)
    faits = {"kind": f"format-studio-photos", "studio_job": job_id, "due": (maintenant + timedelta(minutes=2)).isoformat(),
             "source": job["lien"], "notifier": bool(p.get("notifier")), "reseaux": p.get("reseaux")}
    if p.get("legende_en"):
        faits["en"] = {"title": p.get("accroche") or "", "caption": p["legende_en"] + (f"\n\n📸 {p.get('credit')}" if p.get("credit") else "")}
    from core.studio import theme_libre
    post = E.save_post(theme_libre(job_id, maintenant), maintenant.date().isoformat(), (p.get("accroche") or "Photos")[:160], legende,
                       tags, fichiers, faits)
    resultat = buffer.schedule(post, maintenant + timedelta(minutes=2))
    recus = [r["reason"] for r in db.all("SELECT reason FROM audit_log WHERE reason LIKE ?", [f"post-{post['id']}-%"])]
    maj(job_id, statut="envoye" if recus else "erreur", post_id=post["id"],
        erreur=None if recus else f"aucun réseau n'a accepté le carrousel : {resultat}"[:500])
    return {"statut": "envoye", "video": f"post {post['id']}"}



# ---------------------------------------------------------------- profil complet, en arrière-plan (20/10/2026)

GARDER = 10          # photos cochées d'avance (reconnues) par profil
MAX_TRI = 24         # photos proposées au tri
ANALYSER = 40        # photos examinées au plus


def _une_personne(im: Image.Image) -> tuple[bool, bool]:
    """(une seule personne bien visible, personne entière) d'après le masque de détourage (rembg)."""
    try:
        import numpy as np
        from rembg import new_session, remove
        global _SESSION_P
        try:
            _SESSION_P
        except NameError:
            _SESSION_P = None
        _SESSION_P = _SESSION_P or new_session("u2net_human_seg")
        petit = im.copy(); petit.thumbnail((320, 320))
        m = np.array(remove(petit, session=_SESSION_P, only_mask=True)) > 128
    except Exception:  # noqa: BLE001
        return True, False
    surface = m.mean()
    if not 0.04 <= surface <= 0.75:
        return False, False
    # nombre de silhouettes : colonnes occupées séparées par un vide franc
    colonnes = m.any(axis=0)
    blocs, dedans = 0, False
    for c in colonnes:
        if c and not dedans:
            blocs += 1
        dedans = bool(c)
    ys = np.where(m.any(axis=1))[0]
    entiere = len(ys) > 0 and (ys[-1] - ys[0]) / m.shape[0] >= 0.75
    return blocs == 1, bool(entiere)


def _empreinte(im: Image.Image) -> int:
    g = im.convert("L").resize((8, 8))
    px = list(g.getdata()); moy = sum(px) / 64
    return sum(1 << k for k, v in enumerate(px) if v > moy)


def _cle(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def _cite(ctx: dict, nom: str, handle: str) -> bool:
    """Le post parle-t-il de l'artiste ? nom cité dans la légende, @compte cité ou identifié sur la photo."""
    legende = (ctx.get("legende") or "").lower()
    if handle and (handle in ctx.get("identifies", []) or ("@" + handle) in legende or handle == (ctx.get("compte") or "").lower()):
        return True
    return len(nom) >= 3 and re.search(r"(?<![\w@])" + re.escape(nom.lower()) + r"(?!\w)", legende) is not None


def traite_profil(job_id: int, job: dict, p: dict, maj) -> dict:
    """Profil complet : parcourt les posts visibles et range dans le dossier de l'artiste les meilleures photos OÙ
    C'EST BIEN LUI. Page de l'artiste : tous ses posts ; page média ou de fans : seulement les posts qui le citent
    (nom, @compte, identifié). Puis visage comparé à ses photos déjà validées (ou au visage qui revient sur ses
    posts), une seule personne, taille, netteté, sans doublon."""
    from core.services.social import plans, visages
    maj(job_id, statut="telechargement", erreur=None)
    a = db.one("SELECT id, slug, name, instagram FROM artists WHERE id = ?", [int(p.get("artiste_id") or 0)])
    if not a:
        raise RuntimeError("artiste introuvable : choisis-le dans la liste")
    handle = (a.get("instagram") or "").lstrip("@").lower()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", job["lien"])
    page_de = (m.group(1).lower() if m and m.group(1) not in ("p", "reel", "explore") else "")
    sa_page = bool(page_de) and (page_de == handle or (len(_cle(a["name"])) >= 3 and _cle(a["name"]) in _cle(page_de)))
    refus = {"pas_lui": 0, "pas_cite": 0, "plusieurs": 0, "petite": 0, "doublon": 0, "sans_visage": 0}
    with tempfile.TemporaryDirectory(prefix=f"cauri-profil-{job_id}-") as tmp:
        images, contextes = [], {}
        if "instagram.com" in job["lien"]:
            for k, post in enumerate(_posts_du_profil(job["lien"])):     # post par post, comme un lien de post
                if len(images) >= ANALYSER:
                    break
                sous = os.path.join(tmp, f"post{k:02d}"); os.makedirs(sous, exist_ok=True)
                imgs = _instagram_navigateur(post, sous, maximum=10)
                contextes.update(PAR_CHEMIN)
                images += imgs
        if not images:
            images, _i = _gallery_dl(job["lien"], tmp)
        if not images:
            raise RuntimeError("Instagram exige une connexion pour lire un profil depuis le serveur : "
                               "colle plutôt les liens des posts photo de l'artiste")
        maj(job_id, statut="analyse")
        candidates, vues = [], []
        for chemin in images[:ANALYSER]:
            ctx = contextes.get(chemin)
            if not sa_page and ctx is not None and not _cite(ctx, a["name"], handle):
                refus["pas_cite"] += 1          # page média : ce post ne parle pas de l'artiste
                continue
            donnees = _jpeg(chemin)
            if not donnees:
                refus["petite"] += 1
                continue
            with Image.open(io.BytesIO(donnees)) as im:
                im = im.convert("RGB")
                if min(im.size) < 700:
                    refus["petite"] += 1
                    continue
                emp = _empreinte(im)
                if any(bin(emp ^ e).count("1") <= 6 for e in vues):      # même photo, recadrée ou repostée
                    refus["doublon"] += 1
                    continue
                vues.append(emp)
                seule, entiere = _une_personne(im)
            if not seule:
                refus["plusieurs"] += 1
                continue
            faces = [f for f in visages.analyse(donnees) if f[1] >= 0.75]
            if len(faces) > 1:
                refus["plusieurs"] += 1
                continue
            candidates.append((donnees, entiere, faces))
        # à quoi ressemble l'artiste : ses photos validées à la main, sinon le visage net qui revient sur ses posts
        refs = visages.references_banque(a["id"])
        if not refs:
            refs = visages.visage_dominant([[f[0] for f in c[2] if f[1] >= visages.NET] for c in candidates],
                                           minimum=3 if sa_page else 2)
        notees, verdicts = [], {"lui": 0, "doute": 0}
        for donnees, entiere, faces in candidates:
            v = visages.verdict(faces, refs)
            if v == "pas_lui":
                refus["pas_lui"] += 1
                continue
            verdicts[v] += 1
            _w, _h, score = plans.note_qualite(donnees, entiere)
            notees.append((score + (0.15 if v == "lui" else 0), entiere, donnees, v))   # reconnu : passe devant
    # rien n'entre seul dans la banque : on prépare la sélection, le fondateur valide dans le studio (20/10/2026)
    if page_de and sa_page and not handle:
        db.run("UPDATE artists SET instagram = ? WHERE id = ?", [page_de[:120], a["id"]])
    ordre = sorted(notees, key=lambda t: -t[0])[:MAX_TRI]
    noms, entieres, reconnues = [], [], []
    for k, (score, entiere, donnees, v) in enumerate(ordre):
        nom = f"studio-{job_id}-{k + 1:02d}.jpg"
        storage.store_media("artists/candidats", nom, donnees, "image/jpeg")
        noms.append(nom); entieres.append(bool(entiere)); reconnues.append(v)
    p.update({"photos": noms, "entieres": entieres, "reconnues": reconnues,
              "preselection": [k for k, v in enumerate(reconnues) if v == "lui"][:GARDER],
              "credit": f"@{page_de} sur Instagram" if page_de else "", "compte": page_de if sa_page else "",
              "analysees": len(images), "refus": refus, "verdicts": verdicts, "reference": bool(refs),
              "page": page_de, "sa_page": sa_page, "artiste_nom": a["name"], "a_trier": bool(noms)})
    maj(job_id, statut="pret", params=p, erreur=None if noms else "aucune photo où c'est bien lui sur cette page")
    return {"statut": "pret", "video": f"{len(noms)} photos à trier"}
