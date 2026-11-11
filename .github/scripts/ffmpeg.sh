#!/usr/bin/env bash
# ffmpeg sur les serveurs GitHub (11/11/2026 : « Temporary failure resolving 'security.ubuntu.com' », tâches bloquées 1 h 30).
# Ubuntu d'abord (4 min au plus) ; s'il ne répond pas, ffmpeg + ffprobe autonomes téléchargés depuis GitHub (static-ffmpeg).
# Paquets en plus (polices…) : en arguments, installés seulement si Ubuntu répond.
APT="sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20"
if timeout 240 $APT update -qq && timeout 240 $APT install -y -qq ffmpeg "$@" > /dev/null; then
  echo "ffmpeg : paquet Ubuntu"
  exit 0
fi
echo "Ubuntu injoignable : ffmpeg autonome (static-ffmpeg)"
pip install -q static-ffmpeg
DIR=$(python -c "import os, shutil, static_ffmpeg; static_ffmpeg.add_paths(); print(os.path.dirname(shutil.which('ffmpeg')))")
echo "$DIR" >> "$GITHUB_PATH"
"$DIR/ffmpeg" -version | head -1
