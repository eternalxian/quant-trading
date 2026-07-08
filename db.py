"""
数据库层：三库隔离

  production.db  — 持仓/交易/确认/现金（真金白银，不可重建）
  analytics.db   — 信号/绩效/执行日志（可重建）
  reference.db   — 策略定义/映射（只读参考）
"""
import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)

PROD_DB = os.path.join(DB_DIR, "production.db")
ANALYTICS_DB = os.path.join(DB_DIR, "analytics.db")
REF_DB = os.path.join(DB_DIR, "reference.db")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def prod_conn(): return _connect(PROD_DB)
def analytics_conn(): return _connect(ANALYTICS_DB)
def ref_conn(): return _connect(REF_DB)


# ═══════════════════════════════════════════
#  初始化（幂等）
# ═══════════════════════════════════════════

PROD_SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    code TEXT PRIMARY KEY, shares REAL NOT NULL DEFAULT 0,
    avg_cost REAL, cost_basis REAL NOT NULL DEFAULT 0,
    note TEXT DEFAULT '', updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL, type TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0, shares REAL, nav REAL, fee REAL DEFAULT 0,
    date TEXT NOT NULL, note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_code ON transactions(code);

CREATE TABLE IF NOT EXISTS cash_balance (
    id INTEGER PRIMARY KEY CHECK(id=1),
    amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
INSERT OR IGNORE INTO cash_balance (id, amount) VALUES (1, 0);

CREATE TABLE IF NOT EXISTS pending_buys (
    code TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
    buy_date TEXT NOT NULL, status TEXT DEFAULT 'pending',
    settled_date TEXT, created_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code, buy_date)
);

CREATE TABLE IF NOT EXISTS dca_log (
    date TEXT NOT NULL, code TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (date, code)
);

CREATE TABLE IF NOT EXISTS confirmed_daily (
    date TEXT PRIMARY KEY, pl REAL DEFAULT 0, pl_pct REAL DEFAULT 0,
    total REAL DEFAULT 0, cash REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS confirmed_funds (
    date TEXT NOT NULL, code TEXT NOT NULL, value REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (date, code)
);

CREATE TABLE IF NOT EXISTS known_nav (
    code TEXT PRIMARY KEY, nav REAL NOT NULL,
    nav_date TEXT, updated_at TEXT DEFAULT (datetime('now','localtime'))
);
"""

ANALYTICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL, code TEXT NOT NULL,
    signal TEXT NOT NULL, score REAL DEFAULT 0,
    detail TEXT DEFAULT '', date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sig_strategy ON strategy_signals(strategy_id);
CREATE INDEX IF NOT EXISTS idx_sig_date ON strategy_signals(date);

CREATE TABLE IF NOT EXISTS strategy_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    backtest_start TEXT, backtest_end TEXT,
    total_return REAL, annual_return REAL, max_drawdown REAL,
    sharpe_ratio REAL, win_rate REAL, trades_count INTEGER,
    params_used TEXT DEFAULT '', note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_perf_strategy ON strategy_performance(strategy_id);

CREATE TABLE IF NOT EXISTS strategy_health_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL, date TEXT NOT NULL,
    sharpe REAL, win_rate REAL, status TEXT, note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS advice_log (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL, action TEXT, target TEXT, target_name TEXT,
    level TEXT DEFAULT 'medium', reason TEXT, suggestion TEXT,
    status TEXT DEFAULT 'pending', created_at TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS alert_log (
    id TEXT PRIMARY KEY,
    level TEXT NOT NULL, rule TEXT, target TEXT, target_name TEXT,
    message TEXT, action TEXT, status TEXT DEFAULT 'active',
    created_at TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT, name TEXT, action TEXT, amount REAL,
    status TEXT DEFAULT 'pending', filled_amount REAL, filled_nav REAL,
    slippage REAL, latency_ms REAL, risk_decision TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    executed_at TEXT, note TEXT DEFAULT ''
);
"""

REF_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE, type TEXT NOT NULL,
    description TEXT DEFAULT '', params TEXT DEFAULT '{}',
    target_type TEXT DEFAULT '', source TEXT DEFAULT '', source_url TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    enabled INTEGER DEFAULT 1
);
"""


def init_db():
    """初始化三库（幂等）"""
    for path, schema in [(PROD_DB, PROD_SCHEMA), (ANALYTICS_DB, ANALYTICS_SCHEMA), (REF_DB, REF_SCHEMA)]:
        conn = _connect(path)
        conn.executescript(schema)
        conn.commit()
        conn.close()


# ═══════════════════════════════════════════
#  production.db — 持仓
# ═══════════════════════════════════════════

def get_holdings() -> dict:
    conn = prod_conn()
    rows = conn.execute("SELECT * FROM holdings WHERE shares > 0").fetchall()
    conn.close()
    return {r["code"]: (r["shares"], r["avg_cost"], r["cost_basis"], r["note"] or "") for r in rows}


def get_holding(code: str):
    conn = prod_conn()
    r = conn.execute("SELECT * FROM holdings WHERE code=?", (code,)).fetchone()
    conn.close()
    if r and r["shares"] > 0:
        return (r["shares"], r["avg_cost"], r["cost_basis"])
    return None


def upsert_holding(code: str, shares: float, avg_cost: float = None,
                   cost_basis: float = 0, note: str = ""):
    conn = prod_conn()
    conn.execute("""
        INSERT INTO holdings (code, shares, avg_cost, cost_basis, note, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(code) DO UPDATE SET
            shares=excluded.shares,
            avg_cost=COALESCE(excluded.avg_cost, holdings.avg_cost),
            cost_basis=excluded.cost_basis, note=excluded.note,
            updated_at=datetime('now','localtime')
    """, (code, shares, avg_cost, cost_basis, note))
    conn.commit(); conn.close()


def delete_holding(code: str):
    conn = prod_conn()
    conn.execute("DELETE FROM holdings WHERE code=?", (code,))
    conn.commit(); conn.close()


# ═══════════════════════════════════════════
#  production.db — 交易
# ═══════════════════════════════════════════

def add_transaction(code: str, typ: str, amount: float, date: str = None,
                    shares: float = None, nav: float = None, fee: float = 0, note: str = ""):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = prod_conn()
    conn.execute("INSERT INTO transactions (code, type, amount, shares, nav, fee, date, note) VALUES (?,?,?,?,?,?,?,?)",
                 (code, typ, amount, shares, nav, fee, date, note))
    conn.commit(); conn.close()


def get_transactions(code: str = None, limit: int = 20) -> list:
    conn = prod_conn()
    if code:
        rows = conn.execute("SELECT * FROM transactions WHERE code=? ORDER BY date DESC, id DESC LIMIT ?", (code, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
#  production.db — 待确认
# ═══════════════════════════════════════════

def get_pending_buys() -> dict:
    conn = prod_conn()
    rows = conn.execute("SELECT * FROM pending_buys WHERE status='pending'").fetchall()
    conn.close()
    return {r["code"]: {"amount": r["amount"], "date": r["buy_date"]} for r in rows}


def add_pending_buy(code: str, amount: float, date: str = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = prod_conn()
    conn.execute("INSERT INTO pending_buys (code, amount, buy_date) VALUES (?,?,?) ON CONFLICT(code,buy_date) DO UPDATE SET amount=excluded.amount",
                 (code, amount, date))
    conn.commit(); conn.close()
    add_transaction(code, "pending_add", amount, date, note="待确认申购")


def remove_pending_buy(code: str, date: str = None):
    conn = prod_conn()
    if date:
        conn.execute("DELETE FROM pending_buys WHERE code=? AND buy_date=?", (code, date))
    else:
        conn.execute("DELETE FROM pending_buys WHERE code=?", (code,))
    conn.commit(); conn.close()


def confirm_pending_buy(code: str, shares: float, nav: float, date: str = None):
    conn = prod_conn()
    row = conn.execute("SELECT * FROM pending_buys WHERE code=? AND status='pending' ORDER BY buy_date LIMIT 1", (code,)).fetchone()
    if row:
        conn.execute("UPDATE pending_buys SET status='settled', settled_date=? WHERE code=? AND buy_date=?",
                     (datetime.now().strftime("%Y-%m-%d"), code, row["buy_date"]))
    conn.commit(); conn.close()
    if not row:
        return None

    amount, buy_date = row["amount"], date or row["buy_date"]
    h = get_holding(code)
    if h:
        old_shares, old_avg, old_cost = h
        new_shares = round(old_shares + shares, 2)
        new_cost = old_cost + amount
        new_avg = round(new_cost / new_shares, 4) if new_shares > 0 else old_avg
        upsert_holding(code, new_shares, new_avg, new_cost)
    else:
        upsert_holding(code, shares, round(amount / shares, 4) if shares else nav, amount)
    add_transaction(code, "buy", amount, buy_date, shares, nav, note="份额确认到账")
    return {"code": code, "amount": amount, "shares": shares, "nav": nav, "date": buy_date}


# ═══════════════════════════════════════════
#  production.db — 确认数据 (confirmed_daily / funds)
# ═══════════════════════════════════════════

def get_confirmed_daily(date: str = None) -> dict:
    conn = prod_conn()
    if date:
        r = conn.execute("SELECT * FROM confirmed_daily WHERE date=?", (date,)).fetchone()
    else:
        r = conn.execute("SELECT * FROM confirmed_daily ORDER BY date DESC LIMIT 1").fetchone()
    conn.close()
    if r:
        return {"date": r["date"], "pl": r["pl"] or 0, "pl_pct": r["pl_pct"] or 0, "total": r["total"] or 0, "cash": r["cash"] or 0}
    return {"date": "", "pl": 0, "pl_pct": 0, "total": 0, "cash": 0}


def save_confirmed_daily(date: str, pl: float = 0, pl_pct: float = 0, total: float = 0, cash: float = 0):
    conn = prod_conn()
    conn.execute("INSERT OR REPLACE INTO confirmed_daily (date, pl, pl_pct, total, cash) VALUES (?,?,?,?,?)",
                 (date, pl, pl_pct, total, cash))
    conn.commit(); conn.close()


def get_confirmed_funds(date: str = None) -> dict:
    conn = prod_conn()
    if date:
        rows = conn.execute("SELECT code, value FROM confirmed_funds WHERE date=?", (date,)).fetchall()
    else:
        rows = conn.execute("SELECT code, value FROM confirmed_funds WHERE date=(SELECT MAX(date) FROM confirmed_funds)").fetchall()
    conn.close()
    return {r["code"]: r["value"] for r in rows}


def save_confirmed_funds(funds: dict, date: str = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = prod_conn()
    for code, value in funds.items():
        conn.execute("INSERT OR REPLACE INTO confirmed_funds (date, code, value) VALUES (?,?,?)",
                     (date, code, float(value)))
    conn.commit(); conn.close()


# ═══════════════════════════════════════════
#  production.db — DCA / 余额 / 净值
# ═══════════════════════════════════════════

def get_dca_log(date: str = None) -> dict:
    conn = prod_conn()
    rows = conn.execute("SELECT * FROM dca_log" + (" WHERE date=?" if date else " ORDER BY date DESC"), (date,) if date else ()).fetchall()
    conn.close()
    result = {}
    for r in rows:
        result.setdefault(r["date"], {})[r["code"]] = r["amount"]
    return result


def add_dca(date: str, code: str, amount: float):
    conn = prod_conn()
    conn.execute("INSERT OR IGNORE INTO dca_log (date, code, amount) VALUES (?,?,?)", (date, code, amount))
    conn.commit(); conn.close()


def get_known_navs() -> dict:
    conn = prod_conn()
    rows = conn.execute("SELECT * FROM known_nav").fetchall()
    conn.close()
    return {r["code"]: r["nav"] for r in rows}


def set_known_nav(code: str, nav: float, nav_date: str = None):
    if nav_date is None:
        nav_date = datetime.now().strftime("%Y-%m-%d")
    conn = prod_conn()
    conn.execute("INSERT INTO known_nav (code, nav, nav_date, updated_at) VALUES (?,?,?,datetime('now','localtime')) ON CONFLICT(code) DO UPDATE SET nav=excluded.nav, nav_date=excluded.nav_date, updated_at=datetime('now','localtime')",
                 (code, nav, nav_date))
    conn.commit(); conn.close()


def get_cash() -> float:
    conn = prod_conn()
    r = conn.execute("SELECT amount FROM cash_balance WHERE id=1").fetchone()
    conn.close()
    return r["amount"] if r else 0.0


def set_cash(amount: float, note: str = ""):
    conn = prod_conn()
    old = get_cash()
    conn.execute("UPDATE cash_balance SET amount=?, updated_at=datetime('now','localtime') WHERE id=1", (amount,))
    conn.commit(); conn.close()
    diff = round(amount - old, 2)
    if abs(diff) > 0.01:
        add_transaction("CASH", "cash_in" if diff > 0 else "cash_out", abs(diff), note=note or f"余额变动: {old}->{amount}")


# ═══════════════════════════════════════════
#  reference.db — 策略定义
# ═══════════════════════════════════════════

def get_strategies(enabled_only: bool = True) -> list:
    conn = ref_conn()
    rows = conn.execute("SELECT * FROM strategies" + (" WHERE enabled=1" if enabled_only else "") + " ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_strategy(name_or_id) -> dict:
    conn = ref_conn()
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        r = conn.execute("SELECT * FROM strategies WHERE id=?", (int(name_or_id),)).fetchone()
    else:
        r = conn.execute("SELECT * FROM strategies WHERE name=?", (name_or_id,)).fetchone()
    conn.close()
    return dict(r) if r else {}


def add_strategy(name: str, typ: str, description: str = "", params: str = "",
                 target_type: str = "", source: str = "", source_url: str = "") -> int:
    conn = ref_conn()
    try:
        conn.execute("INSERT INTO strategies (name, type, description, params, target_type, source, source_url) VALUES (?,?,?,?,?,?,?)",
                     (name, typ, description, params, target_type, source, source_url))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        return -1
    finally:
        conn.close()


def update_strategy(strategy_id: int, **kwargs):
    allowed = {"name", "type", "description", "params", "target_type", "source", "source_url", "enabled"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k}=?" for k in updates)
    conn = ref_conn()
    conn.execute(f"UPDATE strategies SET {sets} WHERE id=?", list(updates.values()) + [strategy_id])
    conn.commit(); conn.close()


def delete_strategy(strategy_id: int):
    conn = ref_conn()
    conn.execute("DELETE FROM strategies WHERE id=?", (strategy_id,))
    conn.commit(); conn.close()


# ═══════════════════════════════════════════
#  analytics.db — 信号 / 绩效 / 执行日志
# ═══════════════════════════════════════════

def add_strategy_signal(strategy_id: int, code: str, signal: str, score: float = None,
                        detail: str = "", date: str = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = analytics_conn()
    conn.execute("INSERT INTO strategy_signals (strategy_id, code, signal, score, detail, date) VALUES (?,?,?,?,?,?)",
                 (strategy_id, code, signal, score, detail, date))
    conn.commit(); conn.close()


def get_strategy_signals(strategy_id: int = None, code: str = None, limit: int = 100) -> list:
    conn = analytics_conn()
    # JOIN reference.db for strategy name — need to attach
    conn.execute(f"ATTACH DATABASE ? AS ref", (REF_DB,))
    base = "SELECT s.*, st.name as strategy_name FROM strategy_signals s JOIN ref.strategies st ON s.strategy_id=st.id"
    if strategy_id and code:
        rows = conn.execute(base + " WHERE s.strategy_id=? AND s.code=? ORDER BY s.date DESC LIMIT ?", (strategy_id, code, limit)).fetchall()
    elif strategy_id:
        rows = conn.execute(base + " WHERE s.strategy_id=? ORDER BY s.date DESC LIMIT ?", (strategy_id, limit)).fetchall()
    elif code:
        rows = conn.execute(base + " WHERE s.code=? ORDER BY s.date DESC LIMIT ?", (code, limit)).fetchall()
    else:
        rows = conn.execute(base + " ORDER BY s.date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_strategy_perf(strategy_id: int, total_return: float = None, annual_return: float = None,
                       max_drawdown: float = None, sharpe_ratio: float = None, win_rate: float = None,
                       trades_count: int = None, start: str = None, end: str = None,
                       params_used: str = "", note: str = "") -> int:
    conn = analytics_conn()
    conn.execute("""INSERT INTO strategy_performance
        (strategy_id, backtest_start, backtest_end, total_return, annual_return,
         max_drawdown, sharpe_ratio, win_rate, trades_count, params_used, note)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (strategy_id, start, end, total_return, annual_return, max_drawdown, sharpe_ratio, win_rate, trades_count, params_used, note))
    conn.commit()
    rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return rid


def get_strategy_perf(strategy_id: int = None, limit: int = 20) -> list:
    conn = analytics_conn()
    conn.execute(f"ATTACH DATABASE ? AS ref", (REF_DB,))
    base = "SELECT p.*, s.name as strategy_name FROM strategy_performance p JOIN ref.strategies s ON p.strategy_id=s.id"
    if strategy_id:
        rows = conn.execute(base + " WHERE p.strategy_id=? ORDER BY p.id DESC LIMIT ?", (strategy_id, limit)).fetchall()
    else:
        rows = conn.execute(base + " ORDER BY p.id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── 执行日志 ──

def log_strategy_health(name: str, sharpe: float, win_rate: float, status: str, note: str = ""):
    conn = analytics_conn()
    conn.execute("INSERT INTO strategy_health_log (strategy_name, date, sharpe, win_rate, status, note) VALUES (?,?,?,?,?,?)",
                 (name, datetime.now().strftime("%Y-%m-%d"), sharpe, win_rate, status, note))
    conn.commit(); conn.close()


def log_execution(code: str, name: str, action: str, amount: float, status: str = "pending",
                  filled_amount: float = None, filled_nav: float = None,
                  slippage: float = None, latency_ms: float = None,
                  risk_decision: str = "", note: str = ""):
    conn = analytics_conn()
    conn.execute("""INSERT INTO execution_log (code, name, action, amount, status,
        filled_amount, filled_nav, slippage, latency_ms, risk_decision, note)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (code, name, action, amount, status, filled_amount, filled_nav, slippage, latency_ms, risk_decision, note))
    conn.commit(); conn.close()


def get_execution_log(limit: int = 20) -> list:
    conn = analytics_conn()
    rows = conn.execute("SELECT * FROM execution_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
#  初始化（模块加载时自动执行）
# ═══════════════════════════════════════════

init_db()
