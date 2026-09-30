# Mise en ligne sur un serveur Hetzner (paiement au mois)

Serveur conseillé : **Hetzner Cloud CX23** (2 vCPU, 4 Go, environ 6 € par mois, sans engagement), **Ubuntu 24.04**.

## 1. Nom de domaine
Acheter **cauricharts.com** (Cloudflare Registrar, OVH ou Namecheap). Puis, dans la zone DNS du domaine :

| Type | Nom | Valeur |
|---|---|---|
| A | `@` | adresse IP du serveur |
| A | `www` | adresse IP du serveur |

## 2. Serveur
console.hetzner.cloud → New project → Add server : emplacement Falkenstein ou Nuremberg, image **Ubuntu 24.04**, type **CX23**. Noter l'adresse IP et le mot de passe root reçu par e-mail (ou ajouter une clé SSH).

## 3. Préparer et envoyer le site (sur le PC, dans le dossier du projet)
```
C:\xampp\php\php.exe bin\package-deploy.php
scp deploy/out/cauricharts-site.zip deploy/out/cauricharts-base.sql deploy/installer-serveur.sh root@IP:/root/
```

## 4. Installer (sur le serveur)
```
ssh root@IP
bash /root/installer-serveur.sh cauricharts.com votre@email.com
```
Le script installe Apache, PHP 8.3, MariaDB, ffmpeg, le pare-feu, le certificat HTTPS, la chaîne quotidienne et les sauvegardes. Il est relançable sans danger (par exemple si le HTTPS a échoué parce que le domaine ne pointait pas encore).

## 5. Terminer
```
nano /etc/cauricharts/secrets.env        # YOUTUBE_API_KEY=… et GEMINI_API_KEY=… (nouvelles clés, restreintes)
sudo -u www-data php /var/www/cauricharts/bin/create-admin.php votre@email.com "Votre nom" --totp
sudo -u www-data php /var/www/cauricharts/bin/daily.php
```

## Mettre à jour le site plus tard
```
C:\xampp\php\php.exe bin\package-deploy.php            (sur le PC)
scp deploy/out/cauricharts-site.zip root@IP:/root/
ssh root@IP "unzip -oq /root/cauricharts-site.zip -d /var/www/cauricharts && chown -R www-data:www-data /var/www/cauricharts"
```
(Ne pas renvoyer la base : celle du serveur contient les relevés quotidiens.)
