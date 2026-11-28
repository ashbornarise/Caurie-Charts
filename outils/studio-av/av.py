"""Outils audio de l'atelier vidéo (reconstruit le 28/11/2026).

    python outils/studio-av/av.py master video.mp4 [--vst]   -> video-master.mp4

« master » : niveau final des vidéos du Studio, -14 LUFS intégrés et crêtes sous -1 dBTP (ce que TikTok, YouTube et
Instagram visent), en deux passes loudnorm de ffmpeg ; l'image est recopiée telle quelle. L'ancien atelier passait par le
limiteur FabFilter Pro-L 2 (--vst) : s'il est réinstallé, il est utilisé à la place, sinon l'option est ignorée.
"""
import json
import os
import re
import subprocess
import sys

CIBLE = {"I": -14.0, "TP": -1.0, "LRA": 11.0}
PRO_L = r"C:\Program Files\Common Files\VST3\FabFilter Pro-L 2.vst3"


def _mesure(video: str) -> dict:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vn", "-af",
                        f"loudnorm=I={CIBLE['I']}:TP={CIBLE['TP']}:LRA={CIBLE['LRA']}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if not m:
        raise RuntimeError("mesure du niveau impossible : " + r.stderr[-300:])
    return json.loads(m.group(0))


def master(video: str, vst: bool = False) -> str:
    sortie = re.sub(r"\.mp4$", "", video, flags=re.I) + "-master.mp4"
    if vst and os.path.exists(PRO_L):
        try:
            return _master_vst(video, sortie)
        except Exception as exc:  # noqa: BLE001
            print("Pro-L 2 indisponible, master ffmpeg :", exc)
    m = _mesure(video)
    filtre = (f"loudnorm=I={CIBLE['I']}:TP={CIBLE['TP']}:LRA={CIBLE['LRA']}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
              f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
              "aresample=48000")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-c:v", "copy", "-af", filtre, "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", sortie], check=True)
    return sortie


def _master_vst(video: str, sortie: str) -> str:
    import numpy as np
    from pedalboard import load_plugin
    from pedalboard.io import AudioFile
    wav, wav2 = sortie + ".in.wav", sortie + ".out.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ar", "48000", "-ac", "2", wav], check=True)
    with AudioFile(wav) as f:
        x, sr = f.read(f.frames), f.samplerate
    pl = load_plugin(PRO_L)
    y = pl.process(x.astype(np.float32), sr)
    with AudioFile(wav2, "w", sr, y.shape[0]) as o:
        o.write(y)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", wav2, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-movflags", "+faststart", sortie], check=True)
    for t in (wav, wav2):
        os.remove(t)
    return sortie


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "master":
        print(master(sys.argv[2], "--vst" in sys.argv))
    else:
        print(__doc__)
        sys.exit(1)
