"""Transfère toutes les données de la base MariaDB (site PHP) vers PostgreSQL (site Django).

Mêmes tables, mêmes identifiants. Relançable : la base PostgreSQL est recréée à partir de sql/schema.pg.sql.

    python tools/migrate_data.py                 # MariaDB locale (XAMPP) → PostgreSQL local (port 5433)
    python tools/migrate_data.py --check         # compare seulement le nombre de lignes des deux côtés
"""
import os
import sys
from pathlib import Path

import psycopg
import pymysql

BASE = Path(__file__).resolve().parent.parent

MYSQL = dict(host=os.environ.get("MYSQL_HOST", "127.0.0.1"), port=int(os.environ.get("MYSQL_PORT", 3306)),
             user=os.environ.get("MYSQL_USER", "root"), password=os.environ.get("MYSQL_PASS", ""),
             database=os.environ.get("MYSQL_DB", "cauricharts"), charset="utf8mb4")
PG_DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5433/cauricharts")

# Ordre qui respecte les clés étrangères
TABLES = [
    "countries", "chart_types", "formula_versions", "users", "artists", "tracks", "track_platform_ids",
    "snapshots", "submissions", "chart_runs", "chart_entries", "weekly_scores", "track_reviews",
    "login_attempts", "audit_log", "api_quota", "contact_messages", "news", "social_posts", "partners",
    "chart_observations",
]


def counts(my, pg):
    out = {}
    for t in TABLES:
        with my.cursor() as c:
            c.execute(f"SELECT COUNT(*) FROM `{t}`")
            m = c.fetchone()[0]
        p = pg.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        out[t] = (m, p)
    return out


def main():
    my = pymysql.connect(**MYSQL)
    with psycopg.connect(PG_DSN, autocommit=False) as pg:
        if "--check" not in sys.argv:
            pg.execute((BASE / "sql" / "schema.pg.sql").read_text(encoding="utf-8"))
            for table in TABLES:
                with my.cursor() as c:
                    c.execute(f"SELECT * FROM `{table}`")
                    cols = [d[0] for d in c.description]
                    rows = c.fetchall()
                if rows:
                    col_list = ", ".join(cols)
                    with pg.cursor().copy(f"COPY {table} ({col_list}) FROM STDIN") as copy:
                        for row in rows:
                            copy.write_row(row)
                # Les compteurs d'identifiants repartent après le plus grand identifiant repris
                if "id" in cols:
                    pg.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
                print(f"  {table:<20} {len(rows):>8} lignes")
            pg.commit()
        bad = 0
        for t, (m, p) in counts(my, pg).items():
            flag = "" if m == p else "   <-- DIFFÉRENCE"
            bad += m != p
            if "--check" in sys.argv or flag:
                print(f"  {t:<20} MariaDB {m:>8}   PostgreSQL {p:>8}{flag}")
        print("Vérification :", "identique" if not bad else f"{bad} table(s) différente(s)")
    my.close()


if __name__ == "__main__":
    main()
