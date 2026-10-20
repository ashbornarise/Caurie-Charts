#!/data/data/com.termux/files/usr/bin/bash
# Installe le relais Cauri Studio sur un téléphone Android (Termux, depuis F-Droid).
#   curl -fsSL https://raw.githubusercontent.com/ashbornarise/Caurie-Charts/main/outils/installer_relais.sh | bash -s JETON
set -e
JETON="$1"
if [ -z "$JETON" ]; then echo "Il manque le jeton du relais (reçu par e-mail)."; exit 1; fi

echo "1/4 Paquets (Python, Chromium)…"
yes | pkg update >/dev/null 2>&1 || true
pkg install -y x11-repo >/dev/null
pkg install -y python chromium >/dev/null

echo "2/4 Relais…"
printf '%s' "$JETON" > ~/.cauri-relais && chmod 600 ~/.cauri-relais
curl -fsSL https://raw.githubusercontent.com/ashbornarise/Caurie-Charts/main/outils/relais_telephone.py -o ~/relais_telephone.py

echo "3/4 Démarrage automatique (application Termux:Boot)…"
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/cauri-relais.sh <<'EOS'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
curl -fsSL https://raw.githubusercontent.com/ashbornarise/Caurie-Charts/main/outils/relais_telephone.py -o ~/relais_telephone.py || true
nohup python ~/relais_telephone.py >> ~/relais.log 2>&1 &
EOS
chmod +x ~/.termux/boot/cauri-relais.sh

echo "4/4 Essai…"
python ~/relais_telephone.py --une-fois && echo "Relais OK."
pkill -f relais_telephone.py 2>/dev/null || true
bash ~/.termux/boot/cauri-relais.sh
echo "Le relais tourne (journal : ~/relais.log). Tu peux fermer Termux, il continue."
