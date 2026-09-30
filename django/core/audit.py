"""Journal d'audit : toute action sensible (exclusion, publication, formule...) y est écrite."""
import json

from core import db


def log(user_id, action: str, entity_type: str | None = None, entity_id=None, reason: str | None = None,
        data: dict | None = None, ip: str | None = None) -> None:
    db.insert("audit_log", {
        "user_id": user_id, "action": action, "entity_type": entity_type,
        "entity_id": None if entity_id is None else str(entity_id), "reason": reason,
        "data": json.dumps(data, ensure_ascii=False) if data else None, "ip": ip,
    })
