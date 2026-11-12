"""Bibliothèque de la régie du live : pour chaque artiste du dernier classement (top 3 Icon + top 5 Prime de chaque pays,
plus les artistes du versus), 2 extraits de ses titres les mieux classés (90 s) et 1 extrait de clip (25 s, sans son).
Fichiers sur le Blob (live/<id>/…), index dans live_cache (« live-biblio »). Les clips viennent des chaînes officielles
(recherche YouTube « artiste titre official »), comme les clips du jour.

    python manage.py live_bibliotheque [--max 60] [--ids 5,8]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand

from core import db, storage
from core import live as L


def _ytdlp() -> str:
    return shutil.which("yt-dlp") or os.path.join(os.path.dirname(sys.executable), "yt-dlp" + (".exe" if os.name == "nt" else ""))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", L._norm(s) or "x")[:40] or "x"


class Command(BaseCommand):
    help = "Prépare les sons et clips de la régie du live"

    def add_arguments(self, parser):
        parser.add_argument("--max", type=int, default=70)
        parser.add_argument("--ids", default="")

    def handle(self, *args, **o):
        sem = db.value("""SELECT MAX(r.period_key) FROM chart_runs r JOIN chart_types t ON t.id = r.chart_type_id
            WHERE t.code = 'icon' AND r.status = 'published' AND r.period_key LIKE '%%-W%%'""")
        ids = [int(x) for x in o["ids"].split(",") if x.strip()] or [r["artist_id"] for r in db.all("""
            SELECT e.artist_id, MIN(e.position) p FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
            JOIN chart_types t ON t.id = r.chart_type_id
            WHERE r.status = 'published' AND r.period_key = ? AND ((t.code = 'icon' AND e.position <= 3) OR (t.code = 'prime' AND e.position <= 5))
            GROUP BY e.artist_id ORDER BY p, e.artist_id""", [sem])]
        for v in (L.ETAT_DEFAUT["versus"]["aId"], L.ETAT_DEFAUT["versus"]["bId"]):
            if v not in ids:
                ids.insert(0, v)
        ids = ids[: o["max"]]
        biblio = L._lit(L.CLE_BIBLIO, {}) or {}
        a_faire = [i for i in ids if str(i) not in biblio]
        self.stdout.write(f"{sem} : {len(ids)} artistes, {len(a_faire)} à préparer")
        with ThreadPoolExecutor(3) as ex:
            for aid, res in zip(a_faire, ex.map(self._artiste, a_faire)):
                if res and (res["sons"] or res["clips"]):
                    biblio[str(aid)] = res
                    L._ecrit(L.CLE_BIBLIO, biblio, jours=60)
        self.stdout.write(f"bibliothèque : {len(biblio)} artistes")

    def _artiste(self, aid: int):
        a = db.one("SELECT id, name FROM artists WHERE id = ?", [aid])
        if not a:
            return None
        titres = [r["title"] for r in db.all("""SELECT tr.title, MIN(e.position) p FROM chart_entries e JOIN chart_runs r ON r.id = e.chart_run_id
            JOIN chart_types t ON t.id = r.chart_type_id JOIN tracks tr ON tr.id = e.track_id
            WHERE e.artist_id = ? AND t.code = 'prime' AND r.status = 'published' GROUP BY tr.title ORDER BY p, tr.title LIMIT 2""", [aid])]
        if not titres:
            titres = [r["title"] for r in db.all("SELECT title FROM tracks WHERE artist_id = ? ORDER BY id DESC LIMIT 2", [aid])]
        res = {"nom": a["name"], "sons": [], "clips": []}
        tmp = tempfile.mkdtemp(prefix="live-")
        try:
            for i, t in enumerate(titres):
                propre = re.split(r"\s*[\(\[]\s*(feat|ft|with)", t, flags=re.I)[0].strip()
                src = os.path.join(tmp, f"{i}.%(ext)s")
                r = subprocess.run([_ytdlp(), "--js-runtimes", "node", "-q", "--no-playlist", "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
                                    "--merge-output-format", "mp4", "--max-filesize", "200M", "-o", src, f"ytsearch1:{a['name']} {propre} official"],
                                   capture_output=True, text=True, timeout=600)
                fichier = next((os.path.join(tmp, f) for f in os.listdir(tmp) if f.startswith(f"{i}.")), None)
                if not fichier:
                    self.stdout.write(f"  {a['name']} · {propre} : introuvable ({(r.stderr or '')[-120:]})")
                    continue
                duree = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", fichier],
                                             capture_output=True, text=True).stdout.strip() or 0)
                debut = min(30.0, max(0.0, duree - 95)) if duree else 0
                son = os.path.join(tmp, f"{i}.mp3")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(debut), "-i", fichier, "-t", "90", "-vn", "-af", "afade=t=in:d=1.5,afade=t=out:st=87:d=3",
                                "-c:a", "libmp3lame", "-b:a", "160k", son], check=True)
                url = storage.blob_put(f"live/{aid}/{_slug(propre)}.mp3", open(son, "rb").read(), "audio/mpeg")
                res["sons"].append({"titre": propre, "url": url})
                if not res["clips"]:   # un seul clip par artiste : celui du titre le mieux classé
                    clip = os.path.join(tmp, f"{i}-clip.mp4")
                    debut_clip = min(45.0, max(0.0, duree - 30)) if duree else 0
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(debut_clip), "-i", fichier, "-t", "25", "-an",
                                    "-vf", "scale=-2:720,fps=30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-movflags", "+faststart", clip], check=True)
                    url = storage.blob_put(f"live/{aid}/{_slug(propre)}-clip.mp4", open(clip, "rb").read(), "video/mp4")
                    res["clips"].append({"titre": propre, "url": url})
            self.stdout.write(f"  {a['name']} : {len(res['sons'])} son(s), {len(res['clips'])} clip(s)")
            return res
        except Exception as e:  # noqa: BLE001 — un artiste raté n'arrête pas les autres
            self.stdout.write(f"  {a['name']} : échec ({e})")
            return res
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
