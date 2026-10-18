"""Rapport hebdomadaire fondé sur les mesures réellement enregistrées."""
import calendar
import html
import json
import re
from datetime import date, timedelta
from pathlib import Path

from core import clock, db

ROOT = Path(__file__).resolve().parents[3]


def semaines(aujourdhui: date | None = None) -> tuple[tuple[date, date], tuple[date, date]]:
    """Retourne les deux dernières semaines calendaires terminées (lundi à dimanche)."""
    today = aujourdhui or clock.today()
    lundi = today - timedelta(days=today.weekday() + 7)
    return (lundi, lundi + timedelta(days=6)), (lundi - timedelta(days=7), lundi - timedelta(days=1))


def echeances_mois_suivant(couts: list[dict], aujourdhui: date | None = None) -> list[dict]:
    today = aujourdhui or clock.today()
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    debut, fin = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    return [c for c in couts if c.get("prochaine_echeance") and debut <= date.fromisoformat(c["prochaine_echeance"]) <= fin]


def _theme(theme: str) -> str:
    if theme.startswith("monde-"):
        return "Cauri Monde"
    if theme.startswith("flash-"):
        return "flash"
    if theme.startswith("format-clip-"):
        return "vidéos du jour"
    if theme.startswith("format-interview") or "interview" in theme:
        return "interviews"
    if "evenement" in theme:
        return "événements"
    if theme.startswith("format-"):
        return "formats"
    return theme


def _collecte_plage(start: date, end: date) -> dict:
    debut, fin = start.isoformat(), end.isoformat()
    posts = db.all("SELECT id, slot_date, theme, title, status FROM social_posts WHERE slot_date BETWEEN ? AND ? ORDER BY slot_date, id", [debut, fin])
    par_type = {}
    for p in posts:
        kind = _theme(p["theme"])
        par_type[kind] = par_type.get(kind, 0) + 1
    sent = db.all("""SELECT reason, data, created_at FROM audit_log WHERE action IN ('buffer.post','telegram.post')
                    AND created_at >= ? AND created_at < (?::date + INTERVAL '1 day')""", [debut, fin])
    reseaux = {k: {"crees": 0, "envoyes": 0} for k in ("instagram", "facebook", "tiktok", "telegram")}
    for item in sent:
        raw = f"{item.get('reason') or ''} {item.get('data') or ''}".lower()
        for network in reseaux:
            if network in raw:
                reseaux[network]["envoyes"] += 1
                reseaux[network]["crees"] += 1
    metrics = db.all("""SELECT m.social_post_id, m.channel, m.sent_at, m.metrics, m.text_start, s.theme, s.title
                        FROM post_metrics m LEFT JOIN social_posts s ON s.id=m.social_post_id
                        WHERE m.captured_on BETWEEN ? AND ? AND (m.sent_at::date BETWEEN ? AND ? OR m.sent_at IS NULL)""",
                     [debut, fin, debut, fin])
    metric_rows = []
    for m in metrics:
        try:
            values = json.loads(m["metrics"] or "{}")
        except (ValueError, TypeError):
            values = {}
        metric_rows.append({"titre": m.get("title") or m.get("text_start") or "Publication", "reseau": m["channel"],
                            "type": _theme(m.get("theme") or "inconnu"), "vues": values.get("views", values.get("impressions", 0)) or 0,
                            "portee": values.get("reach", 0) or 0,
                            "reactions": (values.get("reactions", 0) or 0) + (values.get("likes", 0) or 0),
                            "commentaires": values.get("comments", 0) or 0})
    pages = db.all("SELECT path, SUM(views) AS vues FROM page_views WHERE day BETWEEN ? AND ? GROUP BY path ORDER BY vues DESC LIMIT 10", [debut, fin])
    visites_jour = db.all("SELECT day AS jour, SUM(views) AS vues FROM page_views WHERE day BETWEEN ? AND ? GROUP BY day ORDER BY day", [debut, fin])
    nuits = db.all("SELECT ran_at, seconds, failed, steps FROM pipeline_runs WHERE ran_at >= ? AND ran_at < (?::date + INTERVAL '1 day') ORDER BY ran_at", [debut, fin])
    failures = []
    for n in nuits:
        try:
            failures.extend([s[0] for s in json.loads(n["steps"] or "[]") if len(s) > 1 and not s[1]])
        except (ValueError, TypeError):
            pass
    return {"debut": debut, "fin": fin, "posts_crees": len(posts), "posts_par_type": par_type, "posts_par_reseau": reseaux,
            "metriques_posts": metric_rows, "visites_par_jour": visites_jour, "meilleurs_posts": sorted(metric_rows, key=lambda x: x["vues"], reverse=True)[:5],
            "pires_posts": sorted(metric_rows, key=lambda x: x["vues"])[:5],
            "visites": sum(int(p["vues"] or 0) for p in pages), "pages_plus_vues": pages,
            "releves_classements": int(db.value("SELECT COUNT(*) FROM chart_observations WHERE observed_on BETWEEN ? AND ?", [debut, fin]) or 0),
            "artistes_actifs": int(db.value("SELECT COUNT(DISTINCT t.artist_id) FROM chart_observations o JOIN tracks t ON t.id=o.track_id WHERE o.observed_on BETWEEN ? AND ?", [debut, fin]) or 0),
            "nouveaux_artistes": int(db.value("SELECT COUNT(*) FROM artists WHERE created_at >= ? AND created_at < (?::date + INTERVAL '1 day')", [debut, fin]) or 0),
            "classements_officiels_publies": int(db.value("SELECT COUNT(*) FROM chart_runs WHERE status='published' AND published_at >= ? AND published_at < (?::date + INTERVAL '1 day')", [debut, fin]) or 0),
            "nuits": len(nuits), "etapes_en_echec": failures,
            "quota_youtube": int(db.value("SELECT COALESCE(SUM(units_used),0) FROM api_quota WHERE api ILIKE '%youtube%' AND day BETWEEN ? AND ?", [debut, fin]) or 0),
            "constats_agents": db.all("SELECT agent, level, message FROM agent_findings WHERE ran_at >= ? AND ran_at < (?::date + INTERVAL '1 day') ORDER BY ran_at", [debut, fin]),
            "videos_fans": int(db.value("SELECT COUNT(*) FROM fan_videos WHERE created_at >= ? AND created_at < (?::date + INTERVAL '1 day')", [debut, fin]) or 0),
            "actualites_publiees": int(db.value("SELECT COUNT(*) FROM news WHERE status='published' AND published_at >= ? AND published_at < (?::date + INTERVAL '1 day')", [debut, fin]) or 0)}


def collecter(couts_path: Path | None = None, aujourdhui: date | None = None) -> dict:
    derniere, precedente = semaines(aujourdhui)
    couts = json.loads((couts_path or ROOT / "config" / "couts.json").read_text(encoding="utf-8"))
    from core.services.stats_reseaux import collecter as collecter_reseaux
    return {"semaine": _collecte_plage(*derniere), "semaine_precedente": _collecte_plage(*precedente),
            "reseaux_stats": collecter_reseaux(derniere[1]),
            "couts": couts, "depenses_semaine": [c for c in couts if c.get("date_depense") and derniere[0].isoformat() <= c["date_depense"] <= derniere[1].isoformat()],
            "echeances_mois_prochain": echeances_mois_suivant(couts, aujourdhui)}


def _chiffres(data: dict) -> set[str]:
    return set(re.findall(r"(?<![\w])\d+(?:[.,]\d+)?", json.dumps(data, ensure_ascii=False)))


def rediger(data: dict, client=None) -> str:
    client = client or __import__("core.services.ai", fromlist=["make"]).make()
    prompt = "Rédige en français : résumé de la semaine en 5 phrases, évolution globale, paragraphes réseaux, site, classements, contenus, technique, dépenses, puis 3 recommandations concrètes. Chiffres réels uniquement : utilise exclusivement le JSON ci-dessous, sans ajouter de nombre ni extrapoler. Si une donnée manque, dis qu'elle n'est pas disponible.\nJSON : " + json.dumps(data, ensure_ascii=False)
    try:
        answer = client.ask("Tu es l'assistant éditorial de Cauri Charts. Respecte strictement les chiffres fournis.", prompt, max_tokens=8000)   # large : les modèles qui « réfléchissent » coupaient le texte
        text = answer.get("text", "") if isinstance(answer, dict) else str(answer)
        # Le contrôle strict écarte une réponse dès qu'elle contient un nombre absent des données sources.
        numbers = _chiffres(data)
        # petits nombres (1 à 10 : « 3 recommandations », « 5 phrases ») tolérés, les autres doivent venir des données
        if text:
            # Une phrase qui contient un chiffre absent des données est retirée (pas tout le rapport) ;
            # les petits nombres (1 à 10 : « 3 recommandations ») sont tolérés
            ok = lambda n: n in numbers or n.replace(",", ".") in numbers or (n.isdigit() and int(n) <= 10)  # noqa: E731
            lignes = []
            for ligne in text.splitlines():
                phrases = re.split(r"(?<=[.!?])\s+", ligne)
                gardees = [ph for ph in phrases if all(ok(n) for n in re.findall(r"(?<![\w])\d+(?:[.,]\d+)?", ph))]
                lignes.append(" ".join(gardees))
            propre = "\n".join(lignes).strip()
            if len(propre) > 200:
                return propre
    except Exception:
        pass
    s = data["semaine"]
    return (f"La semaine du {s['debut']} au {s['fin']} compte {s['posts_crees']} posts créés. "
            f"Le site a enregistré {s['visites']} visites et {s['releves_classements']} relevés. "
            f"Les classements publiés sont au nombre de {s['classements_officiels_publies']}. "
            f"La chaîne de nuit a effectué {s['nuits']} exécutions avec {len(s['etapes_en_echec'])} étape(s) en échec. "
            f"Les vidéos de fans reçues sont au nombre de {s['videos_fans']}.\n\n"
            "Évolution : les données de la semaine sont comparées à la semaine précédente dans le bloc de chiffres.\n\n"
            "Réseaux : les publications, leurs métriques et leurs répartitions sont détaillées dans les tableaux.\n\n"
            "Site : les visites et pages les plus consultées sont présentées dans les mesures.\n\n"
            "Classements : les relevés et artistes actifs proviennent des observations enregistrées.\n\n"
            "Contenus : posts, actualités publiées et vidéos de fans sont comptés depuis la base.\n\n"
            "Technique : les exécutions, échecs, quota YouTube et constats des agents figurent dans les données.\n\n"
            "Dépenses : les montants connus et échéances confirmées sont distingués des éléments à confirmer.\n\n"
            "Recommandations : consulter les étapes en échec ; examiner les pages les plus vues ; confirmer les échéances inconnues.")


def _markdown(texte: str) -> str:
    """Mise en forme simple du texte de l'IA : titres, gras, listes ; les « --- » sont retirés."""
    out, liste = [], False
    for ligne in texte.splitlines():
        l = ligne.strip()
        if not l or set(l) <= {"-", "*", "_"}:
            if liste:
                out.append("</ul>"); liste = False
            continue
        h = html.escape(l)
        h = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h)
        if l.startswith("#"):
            if liste:
                out.append("</ul>"); liste = False
            out.append(f"<h3>{h.lstrip('#').strip()}</h3>")
        elif l[:2] in ("- ", "* ") or re.match(r"\d+\.\s", l):
            if not liste:
                out.append("<ul>"); liste = True
            out.append(f"<li>{re.sub(r'^([-*]|\d+\.)\s+', '', h)}</li>")
        else:
            if liste:
                out.append("</ul>"); liste = False
            out.append(f"<p>{h}</p>")
    if liste:
        out.append("</ul>")
    return "".join(out)


def rendre(data: dict, texte: str) -> tuple[str, str]:
    s = data["semaine"]
    esc = html.escape
    rows = "".join(f"<tr><td>{esc(str(p['path']))}</td><td>{p['vues']}</td></tr>" for p in s["pages_plus_vues"])
    socials = "".join(f"<tr><td>{esc(k.title())}</td><td>{v['crees']}</td><td>{v['envoyes']}</td></tr>" for k,v in s["posts_par_reseau"].items())
    top = sorted(s["metriques_posts"], key=lambda p: -(p.get("vues") or 0))[:8]   # les 8 posts les plus vus seulement
    metrics = "".join(f"<tr><td>{esc(p['titre'])}</td><td>{esc(p['reseau'])}</td><td>{p['vues']}</td><td>{p['portee']}</td><td>{p['reactions']}</td><td>{p['commentaires']}</td></tr>" for p in top)
    types = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k,v in s["posts_par_type"].items())
    meilleurs = "".join(f"<li>{esc(p['titre'])} · {esc(p['reseau'])} · {p['vues']} vues</li>" for p in s["meilleurs_posts"])
    pires = "".join(f"<li>{esc(p['titre'])} · {esc(p['reseau'])} · {p['vues']} vues</li>" for p in s["pires_posts"])
    couts = "".join(f"<tr><td>{esc(c['nom'])}</td><td>{'à confirmer' if c.get('a_confirmer') else esc(str(c.get('montant') if c.get('montant') is not None else '—')) + ' ' + esc(str(c.get('devise') or ''))}</td><td>{esc(str(c.get('periodicite') or '—'))}</td><td>{esc(str(c.get('prochaine_echeance') or 'à confirmer'))}</td></tr>" for c in data["couts"])
    agents = "".join(f"<li>{esc(a['agent'])} · {esc(a['level'])} : {esc(a['message'])}</li>" for a in s["constats_agents"])
    css = "body{font:15px Arial;color:#20304a;background:#f4faff;padding:24px}main{max-width:900px;margin:auto;background:#fff;padding:28px;border-top:6px solid #a78bfa}h1,h2{color:#5b6ee1}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #d9e4f2;padding:8px;text-align:left}th{background:#e9f5ff}"
    prev = data["semaine_precedente"]
    body = f"<h1>Rapport hebdomadaire · Cauri Charts</h1><p>{s['debut']} — {s['fin']}</p><section>{_markdown(texte)}</section><h2>Publications par réseau</h2><table><tr><th>Réseau</th><th>Programmées</th><th>Enregistrées</th></tr>{socials}</table><h2>Publications par type</h2><table><tr><th>Type</th><th>Créées</th></tr>{types}</table><h2>Les 8 posts les plus vus</h2><table><tr><th>Publication</th><th>Réseau</th><th>Vues</th><th>Portée</th><th>Réactions</th><th>Commentaires</th></tr>{metrics}</table><h3>Meilleurs posts</h3><ul>{meilleurs}</ul><h3>Posts avec le moins de vues</h3><ul>{pires}</ul><h2>Site</h2><p>Visites : {s['visites']} · semaine précédente : {prev['visites']}</p><table><tr><th>Page</th><th>Vues</th></tr>{rows}</table><h2>Classements, contenus et technique</h2><p>Relevés : {s['releves_classements']} (précédente : {prev['releves_classements']}) · Artistes actifs : {s['artistes_actifs']} · Nouveaux artistes : {s['nouveaux_artistes']} · Classements officiels publiés : {s['classements_officiels_publies']}</p><p>Actualités publiées : {s['actualites_publiees']} · Vidéos fans reçues : {s['videos_fans']} · Nuits : {s['nuits']} · Quota YouTube utilisé : {s['quota_youtube']} unités</p><p>Étapes en échec : {esc(', '.join(s['etapes_en_echec']) or 'aucune enregistrée')}</p><ul>{agents}</ul><h2>Dépenses enregistrées cette semaine</h2><pre>{esc(json.dumps(data['depenses_semaine'], ensure_ascii=False, indent=2))}</pre><h2>Abonnements et crédits</h2><table><tr><th>Service</th><th>Montant / état</th><th>Périodicité</th><th>Prochaine échéance</th></tr>{couts}</table><h2>Échéances du mois prochain</h2><pre>{esc(json.dumps(data['echeances_mois_prochain'], ensure_ascii=False, indent=2))}</pre></main>"
    return f"<!doctype html><html lang='fr'><meta charset='utf-8'><style>{css}</style><main>{body}</html>", texte
