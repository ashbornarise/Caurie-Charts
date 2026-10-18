"""Envoi d'e-mails par SMTP (boîte du domaine chez LWS, ou tout autre serveur SMTP).

SMTP_HOST (ex. mail.cauricharts.com), SMTP_PORT (465 = SSL, 587 = STARTTLS), SMTP_USER, SMTP_PASSWORD,
MAIL_FROM (par défaut SMTP_USER), MAIL_ADMIN (destinataire des alertes : messages, revendications).
Un envoi raté n'interrompt jamais la page : il est écrit dans le journal des imports et la page continue.
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from core import env

BRAND = "Cauri Charts"


def configured() -> bool:
    return bool(env.get("SMTP_HOST", "") and env.get("SMTP_USER", "") and env.get("SMTP_PASSWORD", ""))


def send(to: str, subject: str, text: str, reply_to: str | None = None) -> bool:
    if not configured() or not to:
        return False
    sender = env.get("MAIL_FROM", "") or env.get("SMTP_USER", "")
    msg = EmailMessage()
    msg["From"] = formataddr((BRAND, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text + "\n\n-- \n" + BRAND + " · le classement musical de l'Afrique de l'Ouest\nhttps://cauricharts.com\n")
    host, port = env.get("SMTP_HOST", ""), int(env.get("SMTP_PORT", "465") or 465)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=12) as s:
                s.login(env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""))
                s.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        from core.services.platforms import log_write
        log_write("mail", "error", f"envoi à {to} échoué : {exc}")
        return False


def send_html(to: str, subject: str, text: str, html: str, reply_to: str | None = None) -> bool:
    """Envoie un message multipart texte et HTML."""
    if not configured() or not to:
        return False
    sender = env.get("MAIL_FROM", "") or env.get("SMTP_USER", "")
    msg = EmailMessage()
    msg["From"] = formataddr((BRAND, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text + "\n\n-- \n" + BRAND + " · le classement musical de l'Afrique de l'Ouest\nhttps://cauricharts.com\n")
    msg.add_alternative(html, subtype="html")
    host, port = env.get("SMTP_HOST", ""), int(env.get("SMTP_PORT", "465") or 465)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=12) as s:
                s.login(env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", ""))
                s.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        from core.services.platforms import log_write
        log_write("mail", "error", f"envoi HTML à {to} échoué : {exc}")
        return False


def notify_admin(subject: str, text: str, reply_to: str | None = None) -> bool:
    """Alerte à l'équipe (MAIL_ADMIN) ; « Répondre » écrit directement à la personne."""
    return send(env.get("MAIL_ADMIN", "") or env.get("SMTP_USER", ""), "[Cauri Charts] " + subject, text, reply_to)


def acknowledge(to: str, name: str, what: str) -> bool:
    """Accusé de réception, sans reprendre le contenu envoyé (une adresse saisie par un tiers ne reçoit rien d'exploitable)."""
    return send(to, f"{BRAND} : nous avons bien reçu votre {what}",
                f"Bonjour {name[:60]},\n\nMerci, nous avons bien reçu votre {what}. L'équipe vous répond en général sous sept jours, "
                "à cette adresse.\n\nSi vous n'êtes pas à l'origine de ce message, ignorez simplement cet e-mail.")
