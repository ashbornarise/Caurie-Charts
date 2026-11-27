@echo off
rem Connecteur TikTok LIVE -> regie Cauri Charts, en passant par TikFinity (ouvrir TikFinity et le brancher sur le live d'abord).
cd /d "%~dp0"
if not exist node_modules (echo Installation des modules... & call npm install --silent)
title Connecteur TikTok via TikFinity - Cauri Charts
node connecteur.mjs --tikfinity %*
pause
