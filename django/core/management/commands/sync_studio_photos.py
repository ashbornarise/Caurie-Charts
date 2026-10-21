"""Rattrapage : synchronise les photos ajoutées via le Studio vers photo_candidates / image_url des artistes.

  manage.py sync_studio_photos
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Synchronise les photos Studio (artist_photos) vers les profils artistes (photo_candidates / image_url)."

    def handle(self, *args, **options):
        import json
        from core import db, storage
        from core.services.imports.photos import best

        base = storage.blob_public_url()
        rows = db.all("""
            SELECT a.id, a.slug, a.image_locked, a.photo_candidates,
                   array_agg(ap.fichier ORDER BY ap.id DESC) AS fichiers
            FROM artist_photos ap
            JOIN artists a ON a.id = ap.artist_id
            GROUP BY a.id, a.slug, a.image_locked, a.photo_candidates
        """)
        updated = 0
        for row in rows:
            try:
                cands = json.loads(row.get("photo_candidates") or "[]")
            except ValueError:
                cands = []
            changed = False
            for nom in row["fichiers"]:
                url = f"{base}/media/artists/plans/{nom}"
                if not any(c.get("url") == url for c in cands):
                    cands.insert(0, {"source": "lien", "url": url, "site": url, "side": 1000,
                                     "credit": "Photo ajoutée via Cauri Studio"})
                    changed = True
            if not changed:
                continue
            data: dict = {"photo_candidates": json.dumps(cands, ensure_ascii=False)}
            pick = best(cands)
            if pick and not row.get("image_locked"):
                data.update({"image_url": pick["site"], "image_hd_url": pick["url"],
                             "image_source": pick["source"], "image_credit": pick.get("credit")})
            db.update("artists", data, "id = :id", {"id": row["id"]})
            updated += 1
            self.stdout.write(f"{row['slug']} : {len(row['fichiers'])} photos, profil mis à jour")
        self.stdout.write(f"\n{updated} profil(s) synchronisé(s) sur {len(rows)} artiste(s) avec photos Studio.")
