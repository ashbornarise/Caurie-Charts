"""Envoi d'e-mails par SMTP, avec ou sans contenu HTML et fichier joint."""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from core import env

BRAND = "Cauri Charts"


def configured() -> bool:
    return bool(env.get("SMTP_HOST", "") and env.get("SMTP_USER", "") and env.get("SMTP_PASSWORD", ""))


def _message(to: str, subject: str, text: str, reply_to: str | None = None) -> EmailMessage:
    sender = env.get("MAIL_FROM", "") or env.get("SMTP_USER", "")
    msg = EmailMessage()
    msg["From"] = formataddr((BRAND, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    if reply_to:
        msg["Reply-To"] = reply_to
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


def send(to: str, subject: str, text: str, reply_to: str | None = None) -> bool:
    if not configured() or not to:
        return False
    return _send(_message(to, subject, text, reply_to), to, "texte")


def send_html(to: str, subject: str, text: str, html: str, reply_to: str | None = None) -> bool:
    """Envoie un message multipart texte et HTML."""
    if not configured() or not to:
        return False
    msg = _message(to, subject, text, reply_to)
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
