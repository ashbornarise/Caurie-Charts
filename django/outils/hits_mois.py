"""Base « Le son de ta naissance » (16/11/2026) : le N°1 de chaque mois, aux États-Unis et en France, de 1985 à aujourd'hui,
d'après les listes de N°1 de Wikipédia (classement américain Hot 100, classement français SNEP). Lancé une fois sur le PC
(Python avec pandas), le résultat est versionné dans core/data/hits_mois.json ; l'Afrique de l'Ouest vient de notre base.

    python outils/hits_mois.py
"""
import io
import json
import os
import re
import sys
import time

import pandas as pd
import requests

H = {"User-Agent": "CauriCharts/1.0 (https://www.cauricharts.com)"}
MOIS_EN = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                            "october", "november", "december"])}
MOIS_FR = {m: i + 1 for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
                                            "octobre", "novembre", "décembre"])}
SORTIE = os.path.join(os.path.dirname(__file__), "..", "core", "data", "hits_mois.json")


def tables(lang: str, titre: str) -> list:
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", headers=H, timeout=40,
                     params={"action": "parse", "page": titre, "prop": "text", "format": "json", "redirects": 1}).json()
    html = ((r.get("parse") or {}).get("text") or {}).get("*")
    if not html:
        return []
    try:
        return pd.read_html(io.StringIO(html))
    except ValueError:
        return []


def propre(s) -> str:
    s = re.sub(r"\[[^\]]*\]|[†‡§*¤♦]", "", str(s or "")).strip().strip('"“”«» ')
    return re.sub(r"\s+", " ", s)


def colonnes(df) -> tuple:
    noms = [" ".join(str(x) for x in (c if isinstance(c, tuple) else (c,))).lower() for c in df.columns]
    def premier(*mots):
        return next((i for i, n in enumerate(noms) if any(m in n for m in mots)), None)
    return premier("issue date", "date", "week ending", "semaine du"), premier("song", "title", "titre", "single"), premier("artist", "artiste")


def mois_de(texte: str, table: dict) -> int | None:
    t = str(texte).lower()
    for nom, n in table.items():
        if nom in t:
            return n
    return None


def annee(lang: str, titre: str, table_mois: dict) -> dict:
    """{mois: (titre, artiste)} : le titre resté le plus de semaines N°1 dans le mois."""
    meilleur = {}
    for df in tables(lang, titre):
        d, s, a = colonnes(df)
        if d is None or s is None or a is None or len(df) < 8:
            continue
        compte = {}
        for _, ligne in df.iterrows():
            m = mois_de(ligne.iloc[d], table_mois)
            t, ar = propre(ligne.iloc[s]), propre(ligne.iloc[a])
            if not m or not t or t.lower() == "nan" or not ar or ar.lower() == "nan":
                continue
            compte.setdefault(m, {}).setdefault((t, ar), 0)
            compte[m][(t, ar)] += 1
        if len(compte) >= 6:
            for m, c in compte.items():
                meilleur[m] = max(c.items(), key=lambda kv: kv[1])[0]
            break
    return meilleur


def main(debut: int = 1970, fin: int = 2026):
    base = {}
    for an in range(debut, fin + 1):
        us = annee("en", f"List of Billboard Hot 100 number ones of {an}", MOIS_EN)
        fr = annee("fr", f"Liste des titres musicaux numéro un en France en {an}", MOIS_FR)
        for m in range(1, 13):
            x = {}
            if m in us:
                x["monde"] = {"titre": us[m][0], "artiste": us[m][1], "classement": "classement américain"}
            if m in fr:
                x["france"] = {"titre": fr[m][0], "artiste": fr[m][1], "classement": "classement français"}
            if x:
                base[f"{an}-{m:02d}"] = x
        print(an, "États-Unis", len(us), "mois · France", len(fr), "mois", file=sys.stderr)
        time.sleep(0.5)
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    json.dump(base, open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(len(base), "mois enregistrés →", os.path.abspath(SORTIE))


if __name__ == "__main__":
    main()
