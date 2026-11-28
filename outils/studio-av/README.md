# Atelier vidéo du Cauri Studio

Reconstruit le 28/11/2026 dans le dépôt : l'ancien atelier (`C:\Users\agbal\Studio-AV`) est parti avec l'ancien PC.

- `remotion/` : les compositions vidéo (React + Remotion).
  - `CauriRaconte` : les épisodes « Cauri raconte ». Les données sont préparées par `django/core/services/social/raconte_v4.py` (et v2, v3), puis le rendu est lancé par `studio_raconte.py` sur le PC.
  - `CauriGuide` : la vidéo du guide des documents.
- `assets.py` : remet les sons, la mascotte et le logo dans `remotion/public/raconte/`.
- `av.py master video.mp4` : niveau final de la vidéo, -14 LUFS.
- `essai.py` : épisode d'essai de 30 s, avec une planche de contrôle (`essai.jpg`).

## Installer sur un nouveau PC

```
cd outils/studio-av/remotion
npm install
cd ../../..
python outils/studio-av/assets.py
python outils/studio-av/essai.py
```

Pour mettre l'atelier ailleurs, définir la variable d'environnement `STUDIO_AV` (dossier qui contient `remotion/` et `av.py`).

## Ce qui manque encore

- La pose « surpris » de la mascotte (`m3-surpris.png`) : la pose « question » la remplace pour l'instant.
- iZotope RX 12 (retire le chant des musiques de fond) : sans lui, le chant reste, mais très bas.
- FabFilter Pro-L 2 : sans lui, `av.py` fait le niveau final avec ffmpeg.
