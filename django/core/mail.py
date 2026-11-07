"""Envoi d'e-mails par SMTP, avec ou sans contenu HTML et fichier joint.

07/11/2026 (mails arrivés en spam chez des partenaires) : SPF, DKIM et DMARC passent déjà (domaine LWS), mais nos mails
partaient sans en-tête Date (« MISSING_DATE » au filtre de l'hébergeur), en texte brut seulement, sans logo. Désormais :
en-tête Date, version HTML soignée avec le logo pour tout message (le texte reste en alternative), et en-têtes de
désinscription en un clic pour la newsletter (exigés par Gmail et Yahoo pour les envois groupés)."""
import html as _html
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from core import env

BRAND = "Cauri Charts"


def configured() -> bool:
    return bool(env.get("SMTP_HOST", "") and env.get("SMTP_USER", "") and env.get("SMTP_PASSWORD", ""))


LOGO = "https://www.cauricharts.com/assets/img/brand/logo-share.png"
SITE = "https://www.cauricharts.com"


def habiller(text: str) -> str:
    """Version HTML d'un message texte : en-tête au logo, paragraphes, liens cliquables, pied de page de la marque."""
    corps = []
    for bloc in re.split(r"\n\s*\n", text.strip()):
        b = _html.escape(bloc).replace("\n", "<br>")
        b = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" style="color:#5B2BD6;word-break:break-all">\1</a>', b)
        corps.append(f'<p style="margin:0 0 14px;line-height:1.6">{b}</p>')
    return f"""<!doctype html><html lang="fr"><body style="margin:0;padding:0;background:#F4F6FB">
<div style="max-width:600px;margin:0 auto;padding:24px 16px;font-family:Helvetica,Arial,sans-serif;color:#1B1150;font-size:15px">
<div style="background:#FFFFFF;border:1px solid #E4E2F0;border-bottom:0;border-radius:18px 18px 0 0;padding:22px 24px 18px">
<a href="{SITE}"><img src="{LOGO}" alt="{BRAND}" width="150" style="display:block;max-width:150px;height:auto;border:0"></a></div>
<div style="height:5px;background-color:#7A3CF5;background:linear-gradient(90deg,#3FA9F5,#7A3CF5)"></div>
<div style="background:#FFFFFF;border-radius:0 0 18px 18px;padding:24px 24px 16px;border:1px solid #E4E2F0;border-top:0">{"".join(corps)}</div>
<p style="text-align:center;font-size:12px;color:#7A7896;margin:16px 0 0">{BRAND} · la référence de la musique ouest-africaine<br>
<a href="{SITE}" style="color:#7A7896">cauricharts.com</a> · contact@cauricharts.com</p>
</div></body></html>"""


def _message(to: str, subject: str, text: str, reply_to: str | None = None, desinscription: str | None = None) -> EmailMessage:
    sender = env.get("MAIL_FROM", "") or env.get("SMTP_USER", "")
    msg = EmailMessage()
    msg["From"] = formataddr((BRAND, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    if reply_to:
        msg["Reply-To"] = reply_to
    if desinscription:
        msg["List-Unsubscribe"] = f"<{desinscription}>, <mailto:{sender}?subject=unsubscribe>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text + "\n\n-- \n" + BRAND + " · la référence de la musique ouest-africaine\nhttps://cauricharts.com\n")
    return msg


def _send(msg: EmailMessage, to: str, nature: str) -> bool:
    host, port = env.get("SMTP_HOST", ""), int(env.get("SMTP_PORT", "465") or 465)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=12) as smtp:
                smtp.login(env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""))
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""))
                smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        from core.services.platforms import log_write
        log_write("mail", "error", f"envoi {nature} à {to} échoué : {exc}")
        return False


def send(to: str, subject: str, text: str, reply_to: str | None = None, desinscription: str | None = None) -> bool:
    """Texte et sa version HTML au logo (un mail sans HTML ni logo passe plus souvent pour du spam)."""
    if not configured() or not to:
        return False
    msg = _message(to, subject, text, reply_to, desinscription)
    msg.add_alternative(habiller(text), subtype="html")
    return _send(msg, to, "texte")


def send_html(to: str, subject: str, text: str, html: str, reply_to: str | None = None, desinscription: str | None = None) -> bool:
    """Envoie un message multipart texte et HTML."""
    if not configured() or not to:
        return False
    msg = _message(to, subject, text, reply_to, desinscription)
    msg.add_alternative(html, subtype="html")
    return _send(msg, to, "HTML")


def send_html_piece_jointe(to: str, subject: str, text: str, html: str, fichier: str,
                           nom: str = "rapport-hebdo.pdf") -> bool:
    """Envoie le résumé HTML et le PDF en pièce jointe dans un multipart/mixed."""
    if not configured() or not to:
        return False
    msg = _message(to, subject, text)
    msg.add_alternative(html, subtype="html")
    with open(fichier, "rb") as source:
        msg.add_attachment(source.read(), maintype="application", subtype="pdf", filename=nom)
    return _send(msg, to, "HTML avec pièce jointe")


def notify_admin(subject: str, text: str, reply_to: str | None = None) -> bool:
    """Alerte l'équipe ; « Répondre » écrit directement à la personne."""
    return send(env.get("MAIL_ADMIN", "") or env.get("SMTP_USER", ""), "[Cauri Charts] " + subject, text, reply_to)


def acknowledge(to: str, name: str, what: str) -> bool:
    """Accusé de réception sans reprendre le contenu fourni par la personne."""
    return send(to, f"{BRAND} : nous avons bien reçu votre {what}",
                f"Bonjour {name[:60]},\n\nMerci, nous avons bien reçu votre {what}. L'équipe vous répond en général sous sept jours, "
                "à cette adresse. Si vous n'êtes pas à l'origine de ce message, ignorez simplement cet e-mail.")
