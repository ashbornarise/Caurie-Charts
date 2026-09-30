"""Compare le contenu de tables entre MariaDB (PHP) et PostgreSQL (Django), hors id et horodatages.

  python tools/compare_tables.py --mysql=cauricharts_parity --pg=cauricharts_parity weekly_scores chart_runs chart_entries
"""
import argparse
import decimal
import json
from collections import Counter
from datetime import date, datetime

import psycopg
import pymysql

SKIP = {"id", "created_at", "updated_at", "computed_at", "published_at", "corrected_at", "chart_run_id", "attempted_at"}


def norm(v):
    if isinstance(v, (decimal.Decimal, float)):
        return round(float(v), 4)
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return json.dumps(_round(json.loads(v)), sort_keys=True)
        except ValueError:
            return v
    return v


def _round(x):
    if isinstance(x, float):
        return round(x, 4)
    if isinstance(x, list):
        return [] if not x else [_round(i) for i in x]
    if isinstance(x, dict):
        return [] if not x else {k: _round(v) for k, v in x.items()}
    return x


def rows(cur, table, cols, extra=""):
    cur.execute(f"SELECT {', '.join(cols)} FROM {table} {extra}")
    return [tuple(norm(v) for v in r) for r in cur.fetchall()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mysql", default="cauricharts_parity")
    ap.add_argument("--pg", default="cauricharts_parity")
    ap.add_argument("tables", nargs="+")
    a = ap.parse_args()
    my = pymysql.connect(host="127.0.0.1", user="root", password="", database=a.mysql).cursor()
    pg = psycopg.connect(f"postgresql://postgres@127.0.0.1:5433/{a.pg}").cursor()
    for table in a.tables:
        pg.execute(f"SELECT * FROM {table} LIMIT 0")
        cols = [d.name for d in pg.description if d.name not in SKIP]
        if table == "chart_entries":  # rattacher chaque ligne à son classement (les id diffèrent)
            join = "e JOIN chart_runs r ON r.id = e.chart_run_id"
            ccols = [f"e.{c}" for c in cols] + ["r.chart_type_id", "r.country_id", "r.period_type", "r.period_key"]
            m, p = Counter(rows(my, "chart_entries " + join, ccols)), Counter(rows(pg, "chart_entries " + join, ccols))
        elif table == "chart_runs":
            cols = [c for c in cols if c != "formula_json"]
            m, p = Counter(rows(my, table, cols)), Counter(rows(pg, table, cols))
        else:
            m, p = Counter(rows(my, table, cols)), Counter(rows(pg, table, cols))
        only_m, only_p = m - p, p - m
        print(f"{'OK ' if not only_m and not only_p else 'DIF'} {table}: {sum(m.values())} / {sum(p.values())} lignes")
        for r in list(only_m)[:4]:
            print("   PHP   ", dict(zip(cols, r)))
        for r in list(only_p)[:4]:
            print("   DJANGO", dict(zip(cols, r)))
