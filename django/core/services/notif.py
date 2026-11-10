"""Notifications sur le téléphone du fondateur (Web Push, 10/11/2026) : l'appli Cauri Studio installée reçoit des
notifications qui restent affichées jusqu'à ce qu'on les touche (projet à valider, vidéo prête, échec, erreur du site).

Les clés VAPID sont créées une fois et gardées en base (table studio_config) ; les téléphones abonnés dans studio_push.
iPhone : seulement quand le Studio est installé sur l'écran d'accueil (iOS 16.4 et plus). Ne lève jamais d'exception."""
import base64
import json

from core import db


def creer_tables() -> None:
    db.run("""CREATE TABLE IF NOT EXISTS studio_push (
        id BIGSERIAL PRIMARY KEY, user_id BIGINT, endpoint TEXT UNIQUE NOT NULL, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
        appareil TEXT, cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(), dernier_envoi TIMESTAMPTZ)""")
    db.run("CREATE TABLE IF NOT EXISTS studio_config (cle VARCHAR(60) PRIMARY KEY, valeur TEXT NOT NULL)")


def cles() -> tuple[str, str]:
    """(clé privée PEM, clé publique pour le navigateur en base64url) ; créées au premier appel."""
    creer_tables()
    prive = db.value("SELECT valeur FROM studio_config WHERE cle = 'vapid_prive'")
    public = db.value("SELECT valeur FROM studio_config WHERE cle = 'vapid_public'")
    if prive and public:
        return prive, public
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid01
    v = Vapid01()
    v.generate_keys()
    prive = v.private_pem().decode()
    brut = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    public = base64.urlsafe_b64encode(brut).decode().rstrip("=")
    db.run("INSERT INTO studio_config (cle, valeur) VALUES ('vapid_prive', ?) ON CONFLICT (cle) DO NOTHING", [prive])
    db.run("INSERT INTO studio_config (cle, valeur) VALUES ('vapid_public', ?) ON CONFLICT (cle) DO NOTHING", [public])
    return (db.value("SELECT valeur FROM studio_config WHERE cle = 'vapid_prive'"),
            db.value("SELECT valeur FROM studio_config WHERE cle = 'vapid_public'"))


def abonne(user_id, abonnement: dict, appareil: str = "") -> None:
    creer_tables()
    k = abonnement.get("keys") or {}
    if not abonnement.get("endpoint") or not k.get("p256dh") or not k.get("auth"):
        raise ValueError("abonnement incomplet")
    db.run("""INSERT INTO studio_push (user_id, endpoint, p256dh, auth, appareil) VALUES (?, ?, ?, ?, ?)
              ON CONFLICT (endpoint) DO UPDATE SET p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth, user_id = EXCLUDED.user_id""",
           [user_id, abonnement["endpoint"][:1000], k["p256dh"][:200], k["auth"][:100], (appareil or "")[:200]])


def envoie(titre: str, texte: str, projet: int | None = None, etiquette: str | None = None) -> int:
    """Envoie à tous les téléphones abonnés ; rend le nombre d'envois réussis. Les abonnements périmés sont retirés."""
    try:
        from pywebpush import WebPushException, webpush
        creer_tables()
        prive, _ = cles()
        abos = db.all("SELECT * FROM studio_push")
    except Exception:  # noqa: BLE001
        return 0
    from py_vapid import Vapid01
    vapid = Vapid01.from_pem(prive.encode())
    donnees = json.dumps({"titre": titre[:120], "texte": texte[:300], "projet": projet, "tag": etiquette or (f"projet-{projet}" if projet else None)},
                         ensure_ascii=False)
    ok = 0
    for a in abos:
        try:
            webpush({"endpoint": a["endpoint"], "keys": {"p256dh": a["p256dh"], "auth": a["auth"]}}, donnees,
                    vapid_private_key=vapid, vapid_claims={"sub": "mailto:contact@cauricharts.com"}, ttl=86400, timeout=10)
            db.run("UPDATE studio_push SET dernier_envoi = NOW() WHERE id = ?", [a["id"]])
            ok += 1
        except WebPushException as exc:
            if getattr(exc, "response", None) is not None and exc.response.status_code in (404, 410):
                db.run("DELETE FROM studio_push WHERE id = ?", [a["id"]])   # téléphone désabonné ou appli supprimée
        except Exception:  # noqa: BLE001
            pass
    return ok


ETATS = {"a_valider": ("À valider", "L'aperçu est prêt : relis et valide."),
         "a_choisir": ("À choisir", "Les visuels sont prêts : choisis les plus beaux."),
         "pret": ("Prêt à publier", "La vidéo est prête : vérifie et publie."),
         "erreur": ("Échec", "La fabrication a échoué : ouvre le projet pour recommencer.")}


def projet(job_id: int, statut: str) -> None:
    """Un projet du Studio change d'état : notification si l'état demande une action."""
    if statut not in ETATS:
        return
    try:
        j = db.one("SELECT params FROM studio_jobs WHERE id = ?", [job_id])
        p = json.loads((j or {}).get("params") or "{}")
        nom = (f"{p.get('titre')} · {p.get('artistes')}" if p.get("type") == "paroles" else
               p.get("artiste_nom") if p.get("type") == "vedette" else p.get("accroche") or p.get("artiste") or "Vidéo")
        titre, texte = ETATS[statut]
        envoie(f"{titre} : {nom}"[:120], texte, job_id)
    except Exception:  # noqa: BLE001
        pass
