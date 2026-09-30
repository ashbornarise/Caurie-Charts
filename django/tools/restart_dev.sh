#!/usr/bin/env bash
# Relance les serveurs Django de développement : 8001 (base réelle) et 8003 (copie de parité)
cd "$(dirname "$0")/.."
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*runserver 800*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
(.venv/Scripts/python manage.py runserver 8001 --noreload > ../storage/logs/django-dev.log 2>&1 &)
(DATABASE_URL=postgresql://postgres@127.0.0.1:5433/cauricharts_parity .venv/Scripts/python manage.py runserver 8003 --noreload > ../storage/logs/django-parity.log 2>&1 &)
sleep 4
