#!/usr/bin/env bash
# Installation de Cauri Charts sur un serveur neuf Ubuntu 24.04 (Hetzner CX23 ou équivalent).
#
# Préparation (sur votre PC) : php bin/package-deploy.php  → cauricharts-site.zip + cauricharts-base.sql
# Envoi (depuis votre PC) :     scp cauricharts-site.zip cauricharts-base.sql deploy/installer-serveur.sh root@IP:/root/
# Lancement (sur le serveur) :  bash /root/installer-serveur.sh cauricharts.com votre@email
#
# Le script est relançable sans danger : ce qui est déjà fait est conservé.
set -euo pipefail

DOMAIN="${1:?Usage : bash installer-serveur.sh domaine.com email@exemple.com}"
EMAIL="${2:?Indiquez l'e-mail pour le certificat HTTPS (Let's Encrypt)}"
APP=/var/www/cauricharts
SECRETS_DIR=/etc/cauricharts

echo "==> 1/8 Paquets (Apache, PHP 8.3, MariaDB, ffmpeg, certificats)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q apache2 mariadb-server ffmpeg unzip curl ufw certbot python3-certbot-apache \
    php8.3 php8.3-cli php8.3-mysql php8.3-gd php8.3-curl php8.3-mbstring php8.3-intl php8.3-xml php8.3-zip libapache2-mod-php8.3
a2enmod rewrite headers expires deflate >/dev/null

echo "==> 2/8 Pare-feu (SSH, HTTP, HTTPS)"
ufw allow OpenSSH >/dev/null
ufw allow 'Apache Full' >/dev/null
ufw --force enable >/dev/null

echo "==> 3/8 Fichiers du site"
mkdir -p "$APP"
unzip -oq /root/cauricharts-site.zip -d "$APP"
mkdir -p "$APP"/storage/{logs,cache,uploads,backups} "$APP"/public/media/{news,social,partners}

echo "==> 4/8 Base de données"
if [ ! -f "$SECRETS_DIR/db.pass" ]; then
    mkdir -p "$SECRETS_DIR"
    openssl rand -base64 30 | tr -d '/+=' | cut -c1-32 > "$SECRETS_DIR/db.pass"
fi
DB_PASS=$(cat "$SECRETS_DIR/db.pass")
mysql -e "CREATE DATABASE IF NOT EXISTS cauricharts CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER IF NOT EXISTS 'cauricharts'@'localhost' IDENTIFIED BY '$DB_PASS'; ALTER USER 'cauricharts'@'localhost' IDENTIFIED BY '$DB_PASS';"
mysql -e "GRANT ALL PRIVILEGES ON cauricharts.* TO 'cauricharts'@'localhost'; FLUSH PRIVILEGES;"
if [ -z "$(mysql -N -e "SELECT 1 FROM information_schema.tables WHERE table_schema='cauricharts' LIMIT 1")" ]; then
    mysql cauricharts < /root/cauricharts-base.sql
    echo "    base importée (données réelles collectées)"
else
    echo "    base déjà présente : conservée"
fi

echo "==> 5/8 Configuration (.env de production, clés hors du site)"
if [ ! -f "$APP/.env" ]; then
    APP_KEY=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-48)
    cat > "$APP/.env" <<ENV
APP_NAME="Cauri Charts"
APP_URL=https://$DOMAIN
APP_ENV=production
APP_DEBUG=false
APP_LOCALE=fr
APP_TIMEZONE=Africa/Lome
APP_KEY=$APP_KEY
CONTACT_EMAIL=$EMAIL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=cauricharts
DB_USER=cauricharts
DB_PASS=$DB_PASS
PILOT_COUNTRY=TG
SECRETS_FILE=$SECRETS_DIR/secrets.env
YOUTUBE_DAILY_QUOTA=10000
YOUTUBE_SEARCH_PER_RUN=10
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-3.5-flash
GEMINI_GROUNDING=false
FFMPEG_PATH=/usr/bin/ffmpeg
SOCIAL_EXPORT_DIR=
YOUTUBE_EMBEDS=true
SPOTIFY_PLAYLIST_ID=58odALZtD41BlpUBTs30Ot
ENV
fi
if [ ! -f "$SECRETS_DIR/secrets.env" ]; then
    printf '# Clés d API (hors du site). Remplir puis : systemctl reload apache2\nYOUTUBE_API_KEY=\nGEMINI_API_KEY=\n' > "$SECRETS_DIR/secrets.env"
fi
chown -R www-data:www-data "$APP" "$SECRETS_DIR"
chmod 600 "$APP/.env" "$SECRETS_DIR"/secrets.env "$SECRETS_DIR"/db.pass
chmod 700 "$SECRETS_DIR"

echo "==> 6/8 Apache"
cat > /etc/apache2/sites-available/cauricharts.conf <<CONF
<VirtualHost *:80>
    ServerName $DOMAIN
    ServerAlias www.$DOMAIN
    DocumentRoot $APP/public
    <Directory $APP/public>
        AllowOverride All
        Require all granted
    </Directory>
    <Directory $APP>
        Options -Indexes
    </Directory>
    ErrorLog \${APACHE_LOG_DIR}/cauricharts-error.log
    CustomLog \${APACHE_LOG_DIR}/cauricharts-access.log combined
</VirtualHost>
CONF
a2dissite 000-default >/dev/null 2>&1 || true
a2ensite cauricharts >/dev/null
sed -i 's/^upload_max_filesize.*/upload_max_filesize = 8M/; s/^post_max_size.*/post_max_size = 10M/; s/^expose_php.*/expose_php = Off/' /etc/php/8.3/apache2/php.ini
systemctl reload apache2

echo "==> 7/8 HTTPS (Let's Encrypt, renouvelé automatiquement)"
if certbot --apache --non-interactive --agree-tos -m "$EMAIL" -d "$DOMAIN" -d "www.$DOMAIN" --redirect; then
    echo "    HTTPS actif"
else
    echo "    !! HTTPS pas encore possible : le domaine ne pointe peut-être pas encore vers ce serveur."
    echo "    Relancez plus tard : certbot --apache -d $DOMAIN -d www.$DOMAIN --redirect"
fi

echo "==> 8/8 Tâches planifiées (chaîne quotidienne, actualités, sauvegarde, purge)"
cat > /etc/cron.d/cauricharts <<CRON
# Chaîne quotidienne complète vers 1 h à Lomé (serveur en UTC) : classements, artistes, vues, posts…
0 1 * * * www-data php $APP/bin/daily.php >> $APP/storage/logs/cron-stdout.log 2>&1
# Actualités toutes les 3 heures
15 */3 * * * www-data php $APP/bin/import-news.php >> $APP/storage/logs/cron-stdout.log 2>&1
# Sauvegarde de la base et durées de conservation
0 4 * * * www-data php $APP/bin/backup.php >> $APP/storage/logs/cron-stdout.log 2>&1
30 4 * * * www-data php $APP/bin/purge.php >> $APP/storage/logs/cron-stdout.log 2>&1
CRON
chmod 644 /etc/cron.d/cauricharts

echo
echo "Terminé. Site : https://$DOMAIN"
echo "À faire maintenant :"
echo "  1. Clés d'API :      nano $SECRETS_DIR/secrets.env"
echo "  2. Compte admin :    sudo -u www-data php $APP/bin/create-admin.php $EMAIL \"Votre nom\" --totp"
echo "  3. Premier passage : sudo -u www-data php $APP/bin/daily.php"
