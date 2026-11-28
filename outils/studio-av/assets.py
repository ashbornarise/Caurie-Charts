"""Pièces fixes de l'atelier vidéo (sons, mascotte, logo) dans remotion/public/raconte/.

    python outils/studio-av/assets.py

Reconstruit le 28/11/2026 : la banque Mixkit de l'ancien PC est perdue. On reprend les sons du live (même banque, licence
libre sans mention, public/assets/live/sfx) et on fabrique avec ffmpeg ceux qui manquent (battement de cœur, frappes de
machine à écrire, parasites, nappe de suspense). Les noms sont ceux qu'attendent raconte_v2/v3/v4.py.
"""
import os
import shutil
import subprocess

ICI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ICI, "..", ".."))
LIVE = os.path.join(REPO, "public", "assets", "live")
DEST = os.path.join(ICI, "remotion", "public", "raconte")

COPIES = {   # nom attendu -> son du live
    "sfx2/boom-titre.mp3": "boom.mp3", "sfx2/bulle-pop.mp3": "bulle-pop.mp3", "sfx2/impact-epique.mp3": "boom.mp3",
    "sfx2/machine-sonnette.mp3": "ding.mp3", "sfx2/sparkle.mp3": "sparkle.mp3", "sfx2/swell.mp3": "montee.mp3",
    "sfx2/unlock.mp3": "unlock.mp3", "sfx2/verite.mp3": "verite.mp3", "sfx2/whoosh.mp3": "whoosh.mp3",
    "sfx/impact-big.mp3": "boom.mp3", "sfx/riser-drama.mp3": "montee.mp3", "sfx/sparkle-whoosh.mp3": "paillettes.mp3",
    "sfx/swoosh-cine.mp3": "balayage.mp3",
}
# nom -> (entrées ffmpeg, filtre) ; aevalsrc : sons de synthèse, 44,1 kHz stéréo
SYNTHESE = {
    "sfx2/heartbeat.mp3": (["-f", "lavfi", "-i", "aevalsrc='0.9*sin(2*PI*52*t)*exp(-20*t)+0.7*sin(2*PI*48*(t-0.27))*exp(-20*(t-0.27))*gt(t,0.27)"
                            "+0.9*sin(2*PI*52*(t-1))*exp(-20*(t-1))*gt(t,1)+0.7*sin(2*PI*48*(t-1.27))*exp(-20*(t-1.27))*gt(t,1.27)':d=2:s=44100"],
                           "lowpass=f=180,volume=2"),
    "sfx2/machine-frappe1.mp3": (["-f", "lavfi", "-i", "aevalsrc='(random(1)*2-1)*exp(-140*t)+0.6*sin(2*PI*2100*t)*exp(-110*t)':d=0.18:s=44100"], "highpass=f=400"),
    "sfx2/machine-frappe2.mp3": (["-f", "lavfi", "-i", "aevalsrc='(random(2)*2-1)*exp(-120*t)+0.5*sin(2*PI*1700*t)*exp(-100*t)':d=0.18:s=44100"], "highpass=f=350"),
    "sfx2/machine-frappe3.mp3": (["-f", "lavfi", "-i", "aevalsrc='(random(3)*2-1)*exp(-160*t)+0.6*sin(2*PI*2500*t)*exp(-120*t)':d=0.18:s=44100"], "highpass=f=450"),
    "sfx2/mystere-basse.mp3": (["-f", "lavfi", "-i", "aevalsrc='0.35*sin(2*PI*55*t)+0.22*sin(2*PI*82.4*t)*(0.6+0.4*sin(2*PI*0.21*t))"
                                "+0.12*sin(2*PI*110.5*t)*(0.5+0.5*sin(2*PI*0.13*t))':d=40:s=44100"],
                               "lowpass=f=420,afade=t=in:d=2,afade=t=out:st=37:d=3,volume=1.6"),
    "sfx2/parasite-court.mp3": (["-f", "lavfi", "-i", "anoisesrc=d=1.4:c=white:a=0.35"], "bandpass=f=2500:w=1800,tremolo=f=23:d=0.8,afade=t=out:st=1.1:d=0.3"),
    "sfx2/parasite-glitch.mp3": (["-f", "lavfi", "-i", "anoisesrc=d=0.7:c=pink:a=0.45"], "bandpass=f=1200:w=900,tremolo=f=41:d=1,afade=t=out:st=0.5:d=0.2"),
}


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def main():
    for d in ("sfx", "sfx2"):
        os.makedirs(os.path.join(DEST, d), exist_ok=True)
    for nom, src in COPIES.items():
        shutil.copyfile(os.path.join(LIVE, "sfx", src), os.path.join(DEST, nom))
    for nom, (entrees, filtre) in SYNTHESE.items():
        ffmpeg(*entrees, "-af", filtre + ",aformat=channel_layouts=stereo", "-ar", "44100", "-b:a", "192k", os.path.join(DEST, nom))
    w, b = os.path.join(LIVE, "sfx", "whoosh.mp3"), os.path.join(LIVE, "sfx", "boom.mp3")
    ffmpeg("-i", w, "-i", b, "-filter_complex", "[1:a]adelay=350|350[b];[0:a][b]amix=inputs=2:normalize=0", "-ar", "44100", "-b:a", "192k",
           os.path.join(DEST, "sfx2", "whoosh-impact.mp3"))
    ffmpeg("-i", b, "-af", "areverse,afade=t=in:d=0.3", "-ar", "44100", "-b:a", "192k", os.path.join(DEST, "sfx", "reverse-impact.mp3"))
    ffmpeg("-i", w, "-af", "atempo=1.6", "-ar", "44100", "-b:a", "192k", os.path.join(DEST, "sfx", "whoosh-fast.mp3"))
    # mascotte : les 4 poses (« surpris » refaite par Gemini d'après les 3 autres le 28/11/2026, fond détouré par rembg)
    for nom in ("m1-question.png", "m2-presente.png", "m3-surpris.png", "m4-appel.png"):
        shutil.copyfile(os.path.join(LIVE, nom), os.path.join(DEST, nom))
    shutil.copyfile(os.path.join(LIVE, "logo.png"), os.path.join(DEST, "logo.png"))
    print("pièces prêtes dans", DEST)


if __name__ == "__main__":
    main()
