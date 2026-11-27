@echo off
rem Connecteur TikTok LIVE -> regie Cauri Charts. A lancer AVANT ou PENDANT le live (il attend que le live commence).
rem Reglages (jamais dans le depot) : C:\Users\agbal\Cauri-relais\connecteur.env
rem   TIKTOK_COMPTE=caurichartsofficial
rem   REGIE_URL=https://cauricharts.com/live/<jeton de la regie>/regie/commentaires
rem Fermer cette fenetre = arreter le connecteur.
cd /d "%~dp0"
if not exist node_modules (echo Installation des modules... & call npm install --silent)
title Connecteur TikTok - Cauri Charts
node connecteur.mjs %*
pause
