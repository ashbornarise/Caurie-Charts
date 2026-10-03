"""Distinctions officielles Cauri Charts : rares, mensuelles, tirées des classements mensuels publiés.

  qui      : le Top 5 de chaque classement mensuel : Afrique de l'Ouest et chaque pays ;
  rareté   : un titre n'est distingué qu'une seule fois par classement (index unique track_id + scope) ;
  numéro   : l'identifiant de la table (N° 0001…), jamais réutilisé : c'est l'archive des classements ouest-africains ;
  envoi    : page publique /distinctions/<n> (carte, PDF d'impression) ; e-mail automatique si l'équipe a saisi le contact
             de l'artiste, sinon un message prêt à envoyer en DM ;
  fichiers : la carte (JPG, sur le Blob, à envoyer à l'artiste) ; l'impression (PDF 8 × 10 po, 300 ppp, fond perdu),
             le calque de dorure et la version encadrée sont produits à la demande depuis l'admin.
"""
import io
import json

from core import budget, conf, db, storage
from core.helpers import country_name, url

TOP = {"prime-wa": 5, "prime": 5}
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def month_label(key: str) -> str:
    """« 2026-10 » → « Octobre 2026 »."""
    y, m = key.split("-")[:2]
    return f"{MONTHS[int(m) - 1].capitalize()} {y}"


def pending_runs() -> list:
    """Classements mensuels publiés qui n'ont pas encore leurs distinctions."""
    return db.all("""SELECT r.id, r.period_key, ct.code AS chart, c.code AS country, c.chart_size
                     FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id LEFT JOIN countries c ON c.id = r.country_id
                     WHERE r.period_type = 'month' AND r.status = 'published' AND r.is_provisional = 0
                       AND ct.code IN ('prime-wa', 'prime')
                       AND NOT EXISTS (SELECT 1 FROM award_distinctions d WHERE d.chart_run_id = r.id)
                     ORDER BY r.period_start, ct.code DESC, c.sort_order""")


def _label(run: dict) -> tuple[str, str]:
    if run["chart"] == "prime-wa":
        return "WA", f"Top {int(conf.get('charts.prime-wa.size', 20))} · Afrique de l’Ouest"
    return run["country"], f"Top {int(run['chart_size'])} · {country_name(run['country'])}"


def generate(run: dict) -> list:
    """Crée les distinctions d'un classement mensuel publié ; retourne leurs numéros."""
    scope, label = _label(run)
    entries = db.all("""SELECT e.position, e.track_id, e.previous_position, e.peak_position, e.weeks_on_chart,
                               t.title, a.id AS artist_id, a.name AS artist_name, a.image_url, a.status
                        FROM chart_entries e JOIN tracks t ON t.id = e.track_id JOIN artists a ON a.id = t.artist_id
                        WHERE e.chart_run_id = ? AND e.position <= ? ORDER BY e.position""", [run["id"], TOP[run["chart"]]])
    done = []
    for e in entries:
        if e["status"] != "active":
            continue  # artiste à confirmer : pas de distinction tant que son identité n'est pas vérifiée
        if db.one("SELECT 1 FROM award_distinctions WHERE track_id = ? AND scope = ?", [e["track_id"], scope]):
            continue  # déjà distingué dans ce classement : une seule fois, c'est ce qui fait la valeur
        stats = {"last": e["previous_position"], "peak": e["peak_position"], "weeks": e["weeks_on_chart"]}
        did = db.insert("award_distinctions", {
            "chart_run_id": run["id"], "scope": scope, "period_key": run["period_key"], "rank": e["position"],
            "track_id": e["track_id"], "artist_id": e["artist_id"], "artist_name": e["artist_name"], "title": e["title"],
            "chart_label": label, "stats": json.dumps(stats), "photo_url": e["image_url"]})
        save_mask(did, e["image_url"])  # d'abord le détourage : la carte s'en sert (portrait qui sort du cadre)
        # Carte numérique principale (page officielle, e-mails, aperçus de liens) : le format publication du kit
        img = kit_image(db.one("SELECT * FROM award_distinctions WHERE id = ?", [did]), "post")
        out = io.BytesIO()
        img.save(out, "JPEG", quality=92, optimize=True, progressive=True)
        storage.store_media("distinctions", f"{did}.jpg", out.getvalue(), "image/jpeg")
        db.update("award_distinctions", {"image_name": f"{did}.jpg"}, "id = :id", {"id": did})
        done.append(did)
    return done


def save_mask(did: int, photo_url) -> bool:
    """Détourage de la photo (rembg, chaîne de nuit) gardé en PNG : le site s'en sert pour que la tête sorte du cadre."""
    try:
        from core.services.social import image as PI
        from core.services.social import une
        src = PI.photo(photo_url)
        if src is None or not une.available():
            return False
        out = io.BytesIO()
        une._mask(src).point(lambda v: 255 if v > 127 else 0).convert("1").save(out, "PNG", optimize=True)
        storage.store_media("distinctions", f"{did}-masque.png", out.getvalue(), "image/png")
        return True
    except Exception:  # noqa: BLE001 — sans masque, le portrait reste dans le cadre
        return False


def load_mask(did: int):
    from PIL import Image
    base = storage.blob_public_url()
    try:
        if base:
            import requests
            r = requests.get(f"{base}/media/distinctions/{did}-masque.png", timeout=15)
            data = r.content if r.status_code == 200 else None
        else:
            p = storage.MEDIA / "distinctions" / f"{did}-masque.png"
            data = p.read_bytes() if p.is_file() else None
        return Image.open(io.BytesIO(data)).convert("L") if data else None
    except Exception:  # noqa: BLE001
        return None


KIT = ("telephone", "pc", "carre", "post", "carte", "certificat", "enveloppe", "carte_cauri", "carte_code", "carte_qr", "ensemble")
KIT_NAMES = {"telephone": "téléphone 1080x1920", "pc": "PC 1920x1080", "carre": "carré 1080x1080", "post": "publication 1080x1350",
             "carte": "carte 63x88 mm", "certificat": "certificat A4", "enveloppe": "enveloppe DL", "carte_cauri": "carte Cauri Charts 85x55 mm",
             "carte_code": "carte code-barres 85x55 mm", "carte_qr": "carte de vérification 85x55 mm", "ensemble": "photo de l'ensemble"}


def kit_info(d: dict) -> dict:
    return {"artist": d["artist_name"], "title": d["title"], "rank": int(d["rank"]), "chart": d["chart_label"],
            "period": month_label(d["period_key"]), "period_key": d["period_key"], "number": int(d["id"]),
            "stats": json.loads(d["stats"] or "{}"), "photo_url": d["photo_url"], "verify": public_url(d), "mask": load_mask(int(d["id"]))}


def kit_image(d: dict, fmt: str, info: dict | None = None):
    from core.services.social import kit
    info = info or kit_info(d)
    if fmt == "certificat":
        return kit.certificat(info)
    if fmt == "enveloppe":
        return kit.enveloppe(info)
    if fmt == "carte_cauri":
        return kit.card_brand(info)
    if fmt == "carte_code":
        return kit.card_code(info)
    if fmt == "carte_qr":
        return kit.card_qr(info)
    if fmt == "ensemble":
        return kit.ensemble(info, objects(d))
    return kit.render(fmt, info)


def render(d: dict, size=(1600, 2000), **kw):
    """La carte d'une distinction enregistrée (même rendu à chaque fois : tout vient de la ligne en base)."""
    from core.services.social import award
    y, m = str(d["period_key"]).split("-")[:2]
    return award.card(int(d["rank"]), d["chart_label"], d["artist_name"], d["title"], d["photo_url"], month_label(d["period_key"]),
                      size=size, kind="title" if d["title"] else "artist", number=int(d["id"]),
                      stats=json.loads(d["stats"] or "{}"), unit="month", code_period=f"M{int(m):02d}·{y}", **kw)


def objects(d: dict) -> tuple:
    """Les deux objets de la distinction, rendus comme des photos de produit : la plaque encadrée et le bloc acrylique."""
    from core.services.social import plaque
    cover = db.value("SELECT cover_url FROM tracks WHERE id = ?", [d["track_id"]]) if d.get("track_id") else None
    period = month_label(d["period_key"])
    stats = json.loads(d["stats"] or "{}")
    return (plaque.plaque(int(d["rank"]), d["chart_label"], d["artist_name"], d["title"], cover or d["photo_url"], period, int(d["id"]), stats),
            plaque.bloc(int(d["rank"]), d["chart_label"], d["artist_name"], d["title"], period, int(d["id"])))


def cached_pdf(d: dict) -> bytes:
    """Le PDF de reconnaissance, calculé une fois (≈ 1 min) puis relu depuis le Blob."""
    fname = f"{int(d['id'])}-reconnaissance.pdf"
    base = storage.blob_public_url()
    try:
        if base:
            import requests
            r = requests.get(f"{base}/media/distinctions/{fname}", timeout=20)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                return r.content
    except Exception:  # noqa: BLE001
        pass
    data = reconnaissance(d)
    try:
        storage.store_media("distinctions", fname, data, "application/pdf")
    except Exception:  # noqa: BLE001
        pass
    return data


def kit_all(d: dict) -> dict:
    """Toutes les images du kit, calculées une seule fois (pour le ZIP et le PDF de reconnaissance)."""
    from core.services.social import kit
    info = kit_info(d)
    imgs = {"plaque": None, "bloc": None}
    imgs["plaque"], imgs["bloc"] = objects(d)
    for fmt in KIT:
        if fmt != "ensemble":
            imgs[fmt] = kit_image(d, fmt, info)
    imgs["ensemble"] = kit.ensemble(info, (imgs["plaque"], imgs["bloc"]))
    return imgs


def reconnaissance(d: dict, imgs: dict | None = None) -> bytes:
    """PDF de reconnaissance envoyé à l'artiste : la plaque encadrée, le bloc acrylique, puis l'attestation vérifiable."""
    import os
    import tempfile
    from fpdf import FPDF
    from core.services.social import image as PI
    fonts = PI.FONT_DIR
    pdf = FPDF("P", "mm", "A4")
    pdf.set_title(f"Distinction officielle Cauri Charts N° {int(d['id']):04d} · {d['artist_name']}")
    pdf.set_author("Cauri Charts")
    pdf.set_subject(f"N°{d['rank']} du {d['chart_label']}, {month_label(d['period_key'])}")
    pdf.add_font("Sans", "", str(fonts / "Poppins-Regular.ttf"))
    pdf.add_font("Sans", "B", str(fonts / "Poppins-Bold.ttf"))
    pdf.add_font("Serif", "", str(fonts / "DMSerifDisplay-Regular.ttf"))
    pdf.set_auto_page_break(False)
    imgs = imgs or kit_all(d)
    plaque_img, bloc_img = imgs["plaque"], imgs["bloc"]
    with tempfile.TemporaryDirectory() as tmp:
        # Ouverture : tout le kit en une photo
        path = os.path.join(tmp, "ensemble.jpg")
        imgs["ensemble"].save(path, "JPEG", quality=88)
        pdf.add_page(orientation="L")
        pdf.set_fill_color(240, 241, 246)
        pdf.rect(0, 0, 297, 210, "F")
        pdf.image(path, x=8.5, y=8, w=280, h=186.7)
        pdf.set_xy(8.5, 197)
        pdf.set_font("Sans", "B", 9)
        pdf.set_text_color(139, 82, 255)
        pdf.cell(280, 6, f"VOTRE DISTINCTION OFFICIELLE N° {int(d['id']):04d} · LE KIT COMPLET", align="C")
        pdf.add_page(orientation="P")
    with tempfile.TemporaryDirectory() as tmp:
        for i, (img, caption) in enumerate(zip((plaque_img, bloc_img), ("La plaque encadrée", "Le bloc acrylique"))):
            if i:
                pdf.add_page(orientation="P")
            path = os.path.join(tmp, f"{i}.jpg")
            img.save(path, "JPEG", quality=90)
            pdf.set_fill_color(10, 8, 14)
            pdf.rect(0, 0, 210, 297, "F")
            pdf.image(path, x=17, y=14, w=176)  # 4:5 → 176 × 220 mm
            pdf.set_xy(17, 244)
            pdf.set_font("Sans", "B", 9)
            pdf.set_text_color(139, 82, 255)
            pdf.cell(176, 6, f"DISTINCTION OFFICIELLE N° {int(d['id']):04d}", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(17)
            pdf.set_font("Serif", "", 16)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(176, 9, caption, align="C")
    # Certificat A4 paysage
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "certificat.jpg")
        imgs["certificat"].save(path, "JPEG", quality=88)
        pdf.add_page(orientation="P")
        pdf.image(path, x=0, y=0, w=210, h=297)
    # Planche des trois cartes (85 × 55 mm, à découper)
    with tempfile.TemporaryDirectory() as tmp:
        pdf.add_page(orientation="P")
        pdf.set_font("Serif", "", 18)
        pdf.set_text_color(17, 17, 17)
        pdf.set_xy(20, 18)
        pdf.cell(170, 10, "Les cartes", align="C")
        for k, fmt in enumerate(("carte_cauri", "carte_code", "carte_qr")):
            path = os.path.join(tmp, f"{fmt}.jpg")
            imgs[fmt].save(path, "JPEG", quality=92)
            pdf.image(path, x=62.5, y=38 + k * 72, w=85, h=55)
        pdf.set_font("Sans", "", 8)
        pdf.set_text_color(107, 107, 107)
        pdf.set_xy(20, 260)
        pdf.cell(170, 6, "Format carte de visite, 85 × 55 mm, à imprimer sur papier épais.", align="C")
    # Attestation
    pdf.add_page(orientation="P")
    pdf.set_margins(24, 24, 24)
    pdf.set_xy(24, 30)
    pdf.set_font("Sans", "B", 9)
    pdf.set_text_color(139, 82, 255)
    pdf.cell(0, 6, f"ATTESTATION · DISTINCTION OFFICIELLE N° {int(d['id']):04d}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Serif", "", 26)
    pdf.set_text_color(17, 17, 17)
    pdf.multi_cell(0, 12, d["artist_name"], new_x="LMARGIN", new_y="NEXT")
    if d.get("title"):
        pdf.set_font("Serif", "", 16)
        pdf.multi_cell(0, 9, f"« {d['title']} »", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    stats = json.loads(d["stats"] or "{}")
    rows = [("Classement", d["chart_label"]), ("Mois", month_label(d["period_key"])), ("Rang", f"N°{d['rank']}")]
    if stats.get("last") is not None or int(stats.get("weeks") or 0) > 1:
        rows += [("Mois précédent", "nouvelle entrée" if stats.get("last") is None else f"N°{stats['last']}"),
                 ("Meilleur rang", f"N°{stats['peak']}" if stats.get("peak") else "—"), ("Mois au classement", str(stats.get("weeks") or "—"))]
    rows += [("Numéro", f"{int(d['id']):04d}"), ("Vérification", public_url(d))]
    for k, v in rows:
        pdf.set_font("Sans", "", 10)
        pdf.set_text_color(107, 107, 107)
        pdf.cell(48, 8, k)
        pdf.set_font("Sans", "B", 10)
        pdf.set_text_color(17, 17, 17)
        pdf.cell(0, 8, str(v), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Sans", "", 10)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 5.6, "Cette distinction est attribuée au Top 5 de chaque classement mensuel de Cauri Charts, la référence de la "
                           "musique ouest-africaine. Les classements sont calculés chaque semaine à partir de chiffres d’écoute et de vues, "
                           "selon une formule publique ; personne ne peut déplacer un titre à la main. Un titre n’est distingué qu’une seule "
                           "fois par classement.\n\nLa page de vérification ci-dessus confirme l’authenticité de cette distinction. "
                           "Méthode : " + url("methodologie") + ".", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Sans", "", 9)
    pdf.set_text_color(107, 107, 107)
    pdf.multi_cell(0, 5, "Fabrication des objets : la plaque encadrée et le bloc acrylique peuvent être réalisés par un encadreur et un "
                         "atelier de gravure à partir des fichiers fournis par Cauri Charts (contact@cauricharts.com).")
    return bytes(pdf.output())


def files(d: dict, kind: str) -> tuple[bytes, str, str]:
    """Fichier à télécharger depuis l'admin : carte, impression (PDF), dorure (PDF) ou encadrée (JPG)."""
    from PIL import Image, ImageOps
    from core.services.social import award
    name = f"Cauri Charts - Distinction {int(d['id']):04d} - {d['artist_name']}"
    out = io.BytesIO()
    if kind == "reconnaissance":
        return cached_pdf(d), "application/pdf", f"{name} - reconnaissance.pdf"
    if kind in KIT:
        img = kit_image(d, kind)
        dpi = (300, 300) if kind in ("carte", "certificat", "enveloppe", "carte_cauri", "carte_code", "carte_qr") else (72, 72)
        img.save(out, "JPEG", quality=90, dpi=dpi)
        return out.getvalue(), "image/jpeg", f"{name} - {KIT_NAMES[kind]}.jpg"
    if kind == "kit":
        import zipfile
        imgs = kit_all(d)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for fmt in KIT:
                b = io.BytesIO()
                imgs[fmt].save(b, "JPEG", quality=90)
                z.writestr(f"{name} - {KIT_NAMES[fmt]}.jpg", b.getvalue())
            for fmt in ("plaque", "bloc"):
                b = io.BytesIO()
                imgs[fmt].save(b, "JPEG", quality=90)
                z.writestr(f"{name} - {fmt}.jpg", b.getvalue())
            z.writestr(f"{name} - PDF de reconnaissance.pdf", reconnaissance(d, imgs))
        return out.getvalue(), "application/zip", f"{name} - kit complet.zip"
    if kind in ("plaque", "bloc"):
        objects(d)[0 if kind == "plaque" else 1].save(out, "JPEG", quality=92)
        return out.getvalue(), "image/jpeg", f"{name} - {kind}.jpg"
    if kind in ("impression", "dorure"):
        img = render(d, size=(2400, 3000))
        bleed = 36  # 3 mm à 300 ppp
        if kind == "impression":
            ImageOps.expand(img, border=bleed, fill=award.INK).save(out, "PDF", resolution=300)
        else:
            foil = img.info.get("foil", Image.new("L", img.size, 0))
            ImageOps.expand(ImageOps.invert(foil), border=bleed, fill=255).convert("1").save(out, "PDF", resolution=300)
        return out.getvalue(), "application/pdf", f"{name} - {kind}.pdf"
    img = render(d)
    if kind == "cadre":
        img = award.cadre(img, seed=str(d["id"]))
    img.save(out, "JPEG", quality=92)
    return out.getvalue(), "image/jpeg", f"{name} - {kind}.jpg"


def public_url(d: dict) -> str:
    return url(f"distinctions/{int(d['id'])}")


def message(d: dict) -> str:
    """Message à l'artiste (e-mail ou DM Instagram) : la distinction, sa preuve, les liens."""
    what = f"N°{d['rank']} du {d['chart_label']}" + (f" avec « {d['title']} »" if d.get("title") else "")
    return (f"Bonjour {d['artist_name']},\n\n"
            f"Félicitations ! Vous êtes {what} en {month_label(d['period_key']).lower()} sur Cauri Charts, "
            "le classement musical de l'Afrique de l'Ouest calculé sur des données réelles.\n\n"
            f"Votre distinction officielle N° {int(d['id']):04d} vous attend ici : la plaque encadrée, le bloc acrylique, "
            f"la carte à partager et l'attestation, réunis dans votre PDF de reconnaissance :\n{public_url(d)}\n"
            f"PDF de reconnaissance : {public_url(d)}/reconnaissance.pdf\n\n"
            "Partagez-la avec vos fans en mentionnant @cauricharts : nous la republierons.\n\nL'équipe Cauri Charts")


SLOTS = (("distinction", 15), ("distinction-2", 13))  # deux annonces par jour au plus (UTC), loin de la vidéo de midi et du post de 18 h


def announce(d: dict) -> str:
    """Post « distinction remise » : la plaque encadrée sur Instagram, Facebook et TikTok, l'artiste mentionné.
    Deux annonces par jour au plus (15 h puis 13 h UTC), le premier créneau libre à partir de demain."""
    from datetime import datetime, timedelta, timezone
    from core import clock
    from core.services import buffer
    from core.services.social import award
    key = f"distinction-{int(d['id'])}"
    if db.one("SELECT 1 FROM social_posts WHERE theme LIKE 'distinction%' AND facts LIKE ?", [f'%"{key}"%']):
        return "déjà annoncée"
    a = db.one("SELECT instagram, base_country FROM artists WHERE id = ?", [d["artist_id"]]) or {}
    day = clock.today() + timedelta(days=1)
    while True:
        taken = {r["theme"] for r in db.all("SELECT theme FROM social_posts WHERE theme LIKE 'distinction%' AND slot_date = ?", [day.isoformat()])}
        free = [sl for sl in SLOTS if sl[0] not in taken]
        if free:
            theme, hour = free[0]
            break
        day += timedelta(days=1)
    from PIL import Image
    plaque_img = objects(d)[0]
    tall = Image.new("RGB", (1080, 1920), (30, 31, 34))
    tall.paste(plaque_img.resize((1080, 1350), Image.LANCZOS), (0, 285))
    files = {}
    for kind, img in (("file", plaque_img), ("tiktok", tall)):
        out = io.BytesIO()
        img.save(out, "JPEG", quality=90, optimize=True)
        files[kind] = f"{key}-{img.width}.jpg"
        storage.store_media("social", files[kind], out.getvalue(), "image/jpeg")
    who = f"@{a['instagram']}" if a.get("instagram") else d["artist_name"]
    what = f"N°{d['rank']} du {d['chart_label']}" + (f" avec « {d['title']} »" if d.get("title") else "")
    caption = (f"🏆 Distinction officielle N° {int(d['id']):04d}\n\n"
               f"Félicitations {who} ! {what} en {month_label(d['period_key']).lower()}, "
               "d'après le classement Cauri Charts, calculé sur des données réelles.\n\n"
               "Chaque mois, le Top 5 de chaque classement reçoit sa distinction numérotée. Une seule fois par titre.")
    tags = "#CauriCharts #DistinctionOfficielle #MusiqueAfricaine #AfroMusic"
    if a.get("base_country"):
        tags += " #" + country_name(a["base_country"]).replace(" ", "").replace("’", "").replace("'", "")
    pid = db.insert("social_posts", {"slot_date": day.isoformat(), "theme": theme, "title": f"Distinction officielle · {d['artist_name']}"[:160],
                                     "caption": caption, "hashtags": tags, "facts": json.dumps({"key": key, "distinction": int(d["id"])}),
                                     "image_square": files["file"], "image_story": files["tiktok"],
                                     "carousel": json.dumps([files]), "video": None, "status": "approved"})
    post = db.one("SELECT * FROM social_posts WHERE id = ?", [pid])
    due = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    return f"post du {day.isoformat()} : " + buffer.schedule(post, due)


def deliver(d: dict) -> bool:
    """Envoie la distinction par e-mail si l'équipe a saisi le contact de l'artiste ; sinon rien (DM à la main)."""
    from core import mail
    a = db.one("SELECT contact_email FROM artists WHERE id = ?", [d["artist_id"]])
    to = (a or {}).get("contact_email")
    if not to or not mail.send(to, f"Distinction officielle Cauri Charts N° {int(d['id']):04d}", message(d)):
        return False
    db.run("UPDATE award_distinctions SET emailed_at = LOCALTIMESTAMP, status = 'sent', sent_at = COALESCE(sent_at, LOCALTIMESTAMP) WHERE id = ?", [d["id"]])
    try:
        announce(d)
    except Exception:  # noqa: BLE001 — le post est un bonus : l'envoi à l'artiste reste fait
        pass
    return True


def run() -> list:
    """Étape de la chaîne de nuit : distinctions des classements mensuels tout juste publiés, puis un e-mail à l'équipe."""
    lines, made = [], []
    for r in pending_runs():
        if budget.over():
            lines.append("budget atteint : la suite demain")
            break
        ids = generate(r)
        made += ids
        for did in ids:  # envoi direct aux artistes dont l'équipe connaît l'adresse
            deliver(db.one("SELECT * FROM award_distinctions WHERE id = ?", [did]))
        lines.append(f"{r['period_key']} {_label(r)[1]} : {len(ids)} distinction(s)")
    if made:
        try:
            from core import mail
            rows = db.all(f"SELECT id, rank, artist_name, title, chart_label, emailed_at FROM award_distinctions WHERE id IN ({', '.join(['?'] * len(made))}) ORDER BY id", made)
            mail.notify_admin(f"{len(made)} nouvelle(s) distinction(s) Cauri Charts",
                              "\n".join(f"N° {r['id']:04d} · N°{r['rank']} {r['chart_label']} · {r['artist_name']}" + (f" « {r['title']} »" if r["title"] else "")
                                        + (" · envoyée par e-mail" if r["emailed_at"] else " · à envoyer en DM")
                                        for r in rows) + f"\n\nCartes, fichiers d'impression et suivi des envois : {url('admin/distinctions')}")
        except Exception:  # noqa: BLE001 — l'e-mail ne doit jamais bloquer la nuit
            pass
    return lines or ["aucun nouveau classement mensuel publié"]
