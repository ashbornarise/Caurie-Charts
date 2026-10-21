"""Accès SQL direct, calqué sur Cauri\\Core\\Database (PHP) : mêmes méthodes all/one/value/insert/update/run.

Les requêtes des services sont traduites de MySQL vers PostgreSQL mais gardent la même structure,
ce qui garantit les mêmes classements et les mêmes chiffres que le site PHP.
Paramètres positionnels « ? » (comme en PHP) ou nommés « :nom ».
"""
import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

from django.db import connection, transaction

_NAMED = re.compile(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)")


def _prepare(sql: str, params):
    """« ? » → %s ; « :nom » → %(nom)s ; « % » littéral protégé."""
    if isinstance(params, dict):
        sql = sql.replace("%", "%%")
        return _NAMED.sub(lambda m: f"%({m.group(1)})s", sql), params
    sql = sql.replace("%", "%%").replace("?", "%s")
    return sql, list(params or [])


def _clean(value):
    # Même représentation que PDO : décimaux en float, dates en chaînes ISO
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _rows(cursor):
    cols = [c.name for c in cursor.description]
    return [{k: _clean(v) for k, v in zip(cols, row)} for row in cursor.fetchall()]


def _posts_changes(sql: str) -> None:
    """Une écriture sur social_posts déclare périmé l'état du guet Cauri Monde (après validation de la transaction)."""
    if "social_posts" in sql and sql.lstrip()[:6].upper() in ("INSERT", "UPDATE", "DELETE"):
        from core import storage
        transaction.on_commit(storage.invalide_guet)


def run(sql: str, params=None) -> int:
    sql, params = _prepare(sql, params)
    with connection.cursor() as c:
        c.execute(sql, params)
        n = c.rowcount
    _posts_changes(sql)
    return n


def all(sql: str, params=None) -> list[dict]:  # noqa: A001
    sql, params = _prepare(sql, params)
    with connection.cursor() as c:
        c.execute(sql, params)
        return _rows(c) if c.description else []


def one(sql: str, params=None) -> dict | None:
    rows = all(sql, params)
    return rows[0] if rows else None


def value(sql: str, params=None):
    sql, params = _prepare(sql, params)
    with connection.cursor() as c:
        c.execute(sql, params)
        row = c.fetchone()
        return _clean(row[0]) if row else None


def insert(table: str, data: dict) -> int:
    cols = list(data.keys())
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id"
    with connection.cursor() as c:
        c.execute(sql, [data[k] for k in cols])
        new_id = c.fetchone()[0]
    _posts_changes(sql)
    return new_id


def update(table: str, data: dict, where: str, where_params: dict | None = None) -> int:
    sets = ", ".join(f"{k} = %({'_v_' + k})s" for k in data)
    params = {"_v_" + k: v for k, v in data.items()}
    where_sql = _NAMED.sub(lambda m: f"%({m.group(1)})s", where.replace("%", "%%"))
    params.update(where_params or {})
    with connection.cursor() as c:
        c.execute(f"UPDATE {table} SET {sets} WHERE {where_sql}", params)
        n = c.rowcount
    _posts_changes(f"UPDATE {table}")
    return n


@contextmanager
def atomic():
    with transaction.atomic():
        yield
