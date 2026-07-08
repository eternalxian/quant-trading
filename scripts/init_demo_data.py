"""Create deterministic synthetic databases for local demonstration.

The generated records are fictional and must never be replaced with personal data in Git.
"""

from __future__ import annotations

import math
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
DB_NAMES = ("production.db", "analytics.db", "reference.db")


def reset_databases() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for name in DB_NAMES:
        path = DATA_DIR / name
        if path.exists():
            path.unlink()


def seed() -> None:
    reset_databases()

    # Importing db creates the three schemas after old files have been removed.
    import db

    today = date.today()
    funds = {
        "014319": {"shares": 1000.0, "avg_cost": 1.00, "cost": 1000.0, "value": 1120.0},
        "017641": {"shares": 700.0, "avg_cost": 1.10, "cost": 770.0, "value": 820.0},
        "270042": {"shares": 600.0, "avg_cost": 1.30, "cost": 780.0, "value": 850.0},
        "012920": {"shares": 500.0, "avg_cost": 1.20, "cost": 600.0, "value": 640.0},
        "005698": {"shares": 800.0, "avg_cost": 1.20, "cost": 960.0, "value": 1010.0},
        "000834": {"shares": 550.0, "avg_cost": 1.40, "cost": 770.0, "value": 805.0},
    }

    prod = sqlite3.connect(db.PROD_DB)
    for table in (
        "holdings", "transactions", "cash_balance", "pending_buys",
        "dca_log", "confirmed_daily", "confirmed_funds", "known_nav",
    ):
        prod.execute(f"DELETE FROM {table}")

    prod.execute("INSERT INTO cash_balance (id, amount) VALUES (1, ?)", (500.0,))
    for code, item in funds.items():
        prod.execute(
            "INSERT INTO holdings (code, shares, avg_cost, cost_basis, note) VALUES (?,?,?,?,?)",
            (code, item["shares"], item["avg_cost"], item["cost"], "SYNTHETIC DEMO"),
        )
        prod.execute(
            "INSERT INTO transactions (code,type,amount,shares,nav,date,note) VALUES (?,?,?,?,?,?,?)",
            (code, "buy", item["cost"], item["shares"], item["avg_cost"], str(today - timedelta(days=90)), "SYNTHETIC DEMO"),
        )
        prod.execute(
            "INSERT INTO known_nav (code, nav, nav_date) VALUES (?,?,?)",
            (code, item["value"] / item["shares"], str(today)),
        )

    # Sixty deterministic daily snapshots provide enough history for risk metrics.
    for offset in range(60, -1, -1):
        day = today - timedelta(days=offset)
        trend = (60 - offset) * 2.4
        wave = math.sin(offset / 5) * 8
        values = {
            code: round(item["value"] - offset * (1.0 + index * 0.15) + wave * (0.25 + index * 0.08), 2)
            for index, (code, item) in enumerate(funds.items())
        }
        total = round(sum(values.values()) + 500, 2)
        previous = total - 4.0
        pl = round(total - previous, 2)
        prod.execute(
            "INSERT INTO confirmed_daily (date,pl,pl_pct,total,cash) VALUES (?,?,?,?,?)",
            (str(day), pl, round(pl / previous * 100, 4), total, 500.0),
        )
        for code, value in values.items():
            prod.execute("INSERT INTO confirmed_funds (date,code,value) VALUES (?,?,?)", (str(day), code, value))

    prod.commit()
    prod.close()

    ref = sqlite3.connect(db.REF_DB)
    ref.execute(
        "INSERT OR IGNORE INTO strategies (name,type,description,params,target_type,source,enabled) VALUES (?,?,?,?,?,?,?)",
        ("Demo risk review", "rule", "Synthetic demonstration strategy", "{}", "fund", "public-demo", 1),
    )
    ref.commit()
    ref.close()

    print("Synthetic demo databases created in", DATA_DIR)


if __name__ == "__main__":
    seed()
