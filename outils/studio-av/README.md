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
pip install pedalboard        # pour charger iZotope RX 12 (VST3) depuis Python
python outils/studio-av/assets.py
python outils/studio-av/essai.py
```

Pour mettre l'atelier ailleurs, définir la variable d'environnement `STUDIO_AV` (dossier qui contient `remotion/` et `av.py`).

## Ce qui manque encore

- iZotope RX 12 est installé et branché depuis le 28/11/2026 (Music Rebalance retire le chant des musiques de fond).
- FabFilter Pro-L 2 : il faut la version 64 bits sous licence officielle, installée dans « C:\Program Files\Common Files\VST3 ». Sans elle, `av.py` fait le niveau final avec ffmpeg (-14 LUFS, même cible).
