"""Relais Cauri Studio sur un téléphone Android (Termux) branché chez soi.

Instagram montre la grille d'un profil à une connexion de particulier, pas aux serveurs. Toutes les 5 minutes, le
téléphone demande au site les profils collés dans le studio, les ouvre avec Chromium (sans interface), relève les
posts photo et renvoie leurs liens : le tri part sur GitHub. Aucun compte Instagram, aucune clé du site sur le
téléphone : seulement le jeton du relais (fichier ~/.cauri-relais).

    python relais_telephone.py            # boucle, toutes les 5 minutes
    python relais_telephone.py --une-fois # un seul passage (essai)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

SITE = "https://cauricharts.com/api/relais/profils"
JETON = open(os.path.expanduser("~/.cauri-relais")).read().strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")


def appel(methode: str, corps: dict | None = None) -> dict:
    req = urllib.request.Request(SITE, method=methode, data=json.dumps(corps).encode() if corps else None,
                                 headers={"X-Relais": JETON, "Content-Type": "application/json", "User-Agent": "cauri-relais"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def chromium() -> str:
    for nom in ("chromium-browser", "chromium", "google-chrome", "chrome"):
        if shutil.which(nom):
            return shutil.which(nom)
    raise SystemExit("Chromium introuvable : pkg install x11-repo && pkg install chromium")


def posts_du_profil(lien: str) -> list[str]:
    """Liens des posts PHOTO visibles sur le profil (les reels, des vidéos, sont ignorés)."""
    dom = subprocess.run([chromium(), "--headless=new", "--no-sandbox", "--disable-gpu", "--lang=fr-FR",
                          "--window-size=1280,900", f"--user-agent={UA}", "--virtual-time-budget=25000",
                          "--dump-dom", lien.split("?")[0]], capture_output=True, text=True, timeout=180).stdout
    codes = dict.fromkeys(re.findall(r"/p/([A-Za-z0-9_-]{6,})", dom))
    return [f"https://www.instagram.com/p/{c}/" for c in codes][:24]


def passage() -> None:
    for x in appel("GET").get("profils", []):
        posts = []
        for profil in x["profils"]:
            try:
                trouves = posts_du_profil(profil)
            except subprocess.TimeoutExpired:
                trouves = []
            print(time.strftime("%H:%M"), "tâche", x["job"], profil, "->", len(trouves), "posts photo", flush=True)
            posts += trouves
        print(time.strftime("%H:%M"), "tâche", x["job"], appel("POST", {"job": x["job"], "liens": posts}), flush=True)


if __name__ == "__main__":
    while True:
        try:
            passage()
        except Exception as exc:  # noqa: BLE001 — réseau coupé, site en déploiement… on réessaie au prochain tour
            print(time.strftime("%H:%M"), "erreur :", exc, flush=True)
        if "--une-fois" in sys.argv:
            break
        time.sleep(300)
