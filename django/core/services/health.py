"""Rapport de la nuit : « nuit OK » ou « étape X en échec », envoyé chaque matin à l'équipe.

Par e-mail (MAIL_ADMIN) et, si TELEGRAM_ADMIN_CHAT_ID est renseigné, en message privé Telegram (jamais dans la chaîne
publique). Signale aussi les pannes silencieuses : une nuit sans aucun relevé, ou des sources en erreur dans une
étape qui, elle, s'est terminée.
"""
from core import clock, db, env, mail

WARN = ("ERREUR", "échec", "quota YouTube du jour atteint", "injoignable", "[alerte]")


def summary(report: list, crash: str | None = None) -> tuple[str, str]:
    failed = [r for r in report if not r["ok"]]
    warnings = [(r["step"], line) for r in report for line in r["lines"] if any(w.lower() in line.lower() for w in WARN)]
    observed = int(db.value("SELECT COUNT(*) FROM chart_observations WHERE observed_on = ?", [clock.today().isoformat()]) or 0)
    problems = len(failed) + (1 if crash else 0) + (1 if observed == 0 else 0)
    title = "nuit OK" if not problems else f"{problems} problème{'s' if problems > 1 else ''} cette nuit"
    lines = [f"Cauri Charts · {clock.today():%d/%m/%Y} · {title}", ""]
    if crash:
        lines += [f"LA CHAÎNE S'EST ARRÊTÉE : {crash}", ""]
    if observed == 0:
        lines += ["AUCUN RELEVÉ AUJOURD'HUI : les classements des plateformes n'ont pas été importés.", ""]
    lines.append(f"{observed} positions relevées aujourd'hui · {len(report)} étapes, {len(failed)} en échec, {len(warnings)} avertissements")
    lines.append("")
    for r in report:
        mark = "OK " if r["ok"] else "ÉCHEC"
        lines.append(f"[{mark}] {r['step']} ({r['seconds']:.0f} s)" + ("" if r["ok"] else " : " + "; ".join(r["lines"])[:300]))
    if warnings:
        lines += ["", "Avertissements :"] + [f"- {step} : {line[:200]}" for step, line in warnings[:25]]
    lines += ["", "Journal complet : GitHub > Actions > Chaîne quotidienne > dernier passage."]
    return title, "\n".join(lines)


def send(report: list, crash: str | None = None) -> str:
    title, text = summary(report, crash)
    sent = []
    if mail.configured() and mail.notify_admin(title, text):
        sent.append("e-mail")
    chat = env.get("TELEGRAM_ADMIN_CHAT_ID", "")
    if chat and env.get("TELEGRAM_BOT_TOKEN", ""):
        from core.services import telegram
        try:
            telegram.call("sendMessage", {"chat_id": chat, "text": text[:4000]})
            sent.append("Telegram")
        except Exception:  # noqa: BLE001
            pass
    return f"rapport « {title} » envoyé par " + (", ".join(sent) if sent else "aucun canal (SMTP non configuré)")
