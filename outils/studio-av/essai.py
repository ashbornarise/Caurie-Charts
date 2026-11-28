"""Épisode d'essai de « Cauri raconte » (30 s, images de test) : vérifie que l'atelier rend bien chaque élément.

    python outils/studio-av/essai.py          -> outils/studio-av/essai.mp4 + planche de contrôle essai.jpg
"""
import json
import os
import subprocess

ICI = os.path.dirname(os.path.abspath(__file__))
REM = os.path.join(ICI, "remotion")
E = os.path.join(REM, "public", "raconte", "essai")
os.makedirs(E, exist_ok=True)


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


ff("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=8", "-c:v", "libx264", "-pix_fmt", "yuv420p", os.path.join(E, "clip.mp4"))
ff("-f", "lavfi", "-i", "gradients=s=1600x1000:d=1:c0=#7B5CFF:c1=#2FA8FF", "-frames:v", "1", os.path.join(E, "photo.jpg"))
ff("-f", "lavfi", "-i", "sine=f=220:d=30", "-af", "volume=0.15", "-ar", "44100", "-ac", "2", os.path.join(E, "voix.mp3"))
mots = []
t = 1.0
for w in "Voici l'histoire d'un artiste qui a tout changé à Lomé et bien au-delà.".split():
    mots.append({"m": w, "d": round(t, 2), "f": round(t + 0.32, 2)})
    t += 0.38
props = {
    "duree": 30, "voix": "raconte/essai/voix.mp3", "fond": 0.2, "sansBarre": False,
    "titre": {"haut": "LA LÉGENDE DE", "nom": "TOOFAN", "bas": "Le duo qui a fait danser l'Afrique"},
    "mots": mots,
    "plans": [{"src": "raconte/essai/clip.mp4", "d": 0, "f": 8, "libelle": "LIVE"},
              {"src": "raconte/essai/photo.jpg", "fond": "raconte/essai/photo.jpg", "d": 8, "f": 30, "image": True, "annee": "2016", "credit": "Photo : essai"}],
    "flashs": [0.5, 1.1],
    "titresChapitre": [{"d": 5, "f": 7.5, "numero": "Chapitre 1", "titre": "Les débuts", "annees": "2005 – 2012"},
                       {"d": 20, "f": 24.5, "numero": "CHAPITRE 2", "titre": "LA GLOIRE", "annees": "2013", "style": "machine", "bruit": 1.3}],
    "cartes": [{"d": 8.2, "f": 11, "grand": "48 M", "petit": "écoutes sur Spotify", "or": True}],
    "secrets": [{"d": 11.2, "k": 0, "total": 2}],
    "bulles": [{"d": 14, "f": 16.5, "texte": "On dit qu'ils ont commencé dans une cour d'école…", "cote": "gauche", "cri": "PSST !"}],
    "mascottes": [{"src": "raconte/m1-question.png", "d": 13.9, "f": 16.6, "cote": "gauche", "h": 820},
                  {"src": "raconte/m4-appel.png", "d": 26.3, "f": 30, "cote": "gauche", "h": 820}],
    "verites": [{"d": 16.6, "f": 18.6}],
    "contrats": [{"d": 18.7, "f": 19.9, "quoi": "Contrat de distribution", "avec": "Universal", "annee": "2017", "montant": "500 000 $",
                  "devises": ["300 M FCFA"]}],
    "projets": [{"d": 24.6, "f": 26, "cover": "raconte/essai/photo.jpg", "titre": "Tere Tere", "etiquette": "LE TUBE", "chiffre": "1er au Togo",
                 "morceau": "Tere Tere"}],
    "indices": [], "villes": [], "mythes": [],
    "musiques": [{"src": "raconte/sfx2/mystere-basse.mp3", "d": 0, "f": 20, "depuis": 0, "vol": 0.3}],
    "sfx": [{"src": "raconte/sfx2/unlock.mp3", "d": 12.4, "vol": 0.45, "dur": 1.3}, {"src": "raconte/sfx2/verite.mp3", "d": 16.55, "vol": 0.3}],
    "fin": {"d": 26, "titre": "TA LÉGENDE ?", "texte": "Écris-la en commentaire : prochain épisode"},
}
fichier = os.path.join(E, "props.json")
json.dump(props, open(fichier, "w", encoding="utf-8"), ensure_ascii=False)
sortie = os.path.join(ICI, "essai.mp4")
r = subprocess.run(f'npx remotion render src/index.ts CauriRaconte "{sortie}" --props="{fichier}" --concurrency=2', cwd=REM, shell=True,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout[-1500:], r.stderr[-3000:])
if os.path.isfile(sortie):
    instants = [0.6, 2.5, 6, 9.5, 12.5, 15, 17.2, 19.3, 23.5, 25.3, 28]
    for i, s in enumerate(instants):
        ff("-ss", str(s), "-i", sortie, "-frames:v", "1", "-vf", "scale=270:-2", os.path.join(E, f"k{i:02d}.jpg"))
    ff("-i", os.path.join(E, "k%02d.jpg"), "-vf", "tile=6x2:padding=6", "-frames:v", "1", os.path.join(ICI, "essai.jpg"))
    print("ok :", sortie)
