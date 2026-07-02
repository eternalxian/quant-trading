"""
数据库层：SQLite 统一管理持仓/交易/待确认/余额
"""
import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_FILE = os.path.join(DB_DIR, "quant.db")
os.makedirs(DB_DIR, exist_ok=True)


# ═══════════════════════════════════════════
#  建表
# ═══════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    code TEXT PRIMARY KEY,
    shares REAL NOT NULL DEFAULT 0,
    avg_cost REAL,
    cost_basis REAL NOT NULL DEFAULT 0,
    note TEXT,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('buy','sell','pending_add','pending_cancel','convert_in','convert_out','dca','cash_in','cash_out','divident')),
    amount REAL NOT NULL,
    shares REAL,
    nav REAL,
    fee REAL DEFAULT 0,
    date TEXT NOT NULL,
    note TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS pending_buys (
    code TEXT NOT NULL,
    amount REAL NOT NULL,
    buy_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code, buy_date)
);

CREATE TABLE IF NOT EXISTS dca_log (
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    amount REAL NOT NULL,
    PRIMARY KEY (date, code)
);

CREATE TABLE IF NOT EXISTS known_nav (
    code TEXT PRIMARY KEY,
    nav REAL NOT NULL,
    nav_date TEXT,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS cash_balance (
    id INTEGER PRIMARY KEY CHECK(id=1),
    amount REAL NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    description TEXT,
    params TEXT,
    target_type TEXT,
    source TEXT,
    source_url TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS strategy_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    signal TEXT NOT NULL,
    score REAL,
    detail TEXT,
    date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE TABLE IF NOT EXISTS strategy_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    backtest_start TEXT,
    backtest_end TEXT,
    total_return REAL,
    annual_return REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    win_rate REAL,
    trades_count INTEGER,
    params_used TEXT,
    note TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

-- 插入默认现金行
INSERT OR IGNORE INTO cash_balance (id, amount) VALUES (1, 0);
"""


# ═══════════════════════════════════════════
#  连接
# ═══════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """建表（安全重复执行）"""
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════
#  持仓
# ═══════════════════════════════════════════

def get_holdings() -> dict:
    """返回 {code: (shares, avg_cost, cost_basis, note)}"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM holdings WHERE shares > 0").fetchall()
    conn.close()
    return {r["code"]: (r["shares"], r["avg_cost"], r["cost_basis"], r["note"] or "")
            for r in rows}


def get_holding(code: str):
    """单条持仓 (shares, avg_cost, cost_basis) 或 None"""
    conn = get_conn()
    r = conn.execute("SELECT * FROM holdings WHERE code=?", (code,)).fetchone()
    conn.close()
    if r and r["shares"] > 0:
        return (r["shares"], r["avg_cost"], r["cost_basis"])
    return None


def upsert_holding(code: str, shares: float, avg_cost: float = None,
                   cost_basis: float = 0, note: str = ""):
    """更新/插入持仓"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO holdings (code, shares, avg_cost, cost_basis, note, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(code) DO UPDATE SET
            shares=excluded.shares,
            avg_cost=COALESCE(excluded.avg_cost, holdings.avg_cost),
            cost_basis=excluded.cost_basis,
            note=excluded.note,
            updated_at=datetime('now','localtime')
    """, (code, shares, avg_cost, cost_basis, note))
    conn.commit()
    conn.close()


def delete_holding(code: str):
    """删除持仓（清仓时用）"""
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE code=?", (code,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════
#  交易记录
# ═══════════════════════════════════════════

def add_transaction(code: str, typ: str, amount: float, date: str = None,
                    shares: float = None, nav: float = None, fee: float = 0,
                    note: str = ""):
    """记录一笔交易"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("""
        INSERT INTO transactions (code, type, amount, shares, nav, fee, date, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (code, typ, amount, shares, nav, fee, date, note))
    conn.commit()
    conn.close()


def get_transactions(code: str = None, limit: int = 20) -> list:
    """获取交易记录，按时间倒序"""
    conn = get_conn()
    if code:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE code=? ORDER BY date DESC, id DESC LIMIT ?",
            (code, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
#  待确认申购
# ═══════════════════════════════════════════

def get_pending_buys() -> dict:
    """返回 {code: {"amount": float, "date": str}}"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM pending_buys").fetchall()
    conn.close()
    return {r["code"]: {"amount": r["amount"], "date": r["buy_date"]} for r in rows}


def add_pending_buy(code: str, amount: float, date: str = None):
    """添加待确认申购"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("""
        INSERT INTO pending_buys (code, amount, buy_date)
        VALUES (?, ?, ?)
        ON CONFLICT(code, buy_date) DO UPDATE SET
            amount=excluded.amount
    """, (code, amount, date))
    conn.commit()
    conn.close()
    add_transaction(code, "pending_add", amount, date, note="待确认申购")


def remove_pending_buy(code: str, date: str = None):
    """移除待确认（确认到账或取消）"""
    conn = get_conn()
    if date:
        conn.execute("DELETE FROM pending_buys WHERE code=? AND buy_date=?", (code, date))
    else:
        conn.execute("DELETE FROM pending_buys WHERE code=?", (code,))
    conn.commit()
    conn.close()


def confirm_pending_buy(code: str, shares: float, nav: float, date: str = None):
    """待确认→正式持仓（到账确认）"""
    entry = None
    conn = get_conn()
    row = conn.execute("SELECT * FROM pending_buys WHERE code=? ORDER BY buy_date LIMIT 1",
                       (code,)).fetchone()
    if row:
        entry = {"amount": row["amount"], "date": row["buy_date"]}
        conn.execute("DELETE FROM pending_buys WHERE code=? AND buy_date=?",
                     (code, row["buy_date"]))
    conn.commit()
    conn.close()

    if not entry:
        return None

    amount = entry["amount"]
    buy_date = date or entry["date"]

    # 更新持仓
    h = get_holding(code)
    if h:
        old_shares, old_avg, old_cost = h
        new_shares = round(old_shares + shares, 2)
        new_cost = old_cost + amount
        new_avg = round(new_cost / new_shares, 4) if new_shares > 0 else old_avg
        upsert_holding(code, new_shares, new_avg, new_cost)
    else:
        upsert_holding(code, shares, round(amount / shares, 4) if shares else nav, amount)

    # 记录交易
    add_transaction(code, "buy", amount, buy_date, shares, nav, note="份额确认到账")

    return {"code": code, "amount": amount, "shares": shares, "nav": nav, "date": buy_date}


# ═══════════════════════════════════════════
#  DCA 定投日志
# ═══════════════════════════════════════════

def get_dca_log(date: str = None) -> dict:
    """获取 DCA 日志 {date: {code: amount}}"""
    conn = get_conn()
    if date:
        rows = conn.execute("SELECT * FROM dca_log WHERE date=?", (date,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM dca_log ORDER BY date DESC").fetchall()
    conn.close()
    result = {}
    for r in rows:
        if r["date"] not in result:
            result[r["date"]] = {}
        result[r["date"]][r["code"]] = r["amount"]
    return result


def add_dca(date: str, code: str, amount: float):
    """记录 DCA 执行"""
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO dca_log (date, code, amount)
        VALUES (?, ?, ?)
    """, (date, code, amount))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════
#  已知净值（QDII 滞后时手动覆盖）
# ═══════════════════════════════════════════

def get_known_navs() -> dict:
    """返回 {code: nav}"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM known_nav").fetchall()
    conn.close()
    return {r["code"]: r["nav"] for r in rows}


def set_known_nav(code: str, nav: float, nav_date: str = None):
    """设置/更新已知净值"""
    if nav_date is None:
        nav_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("""
        INSERT INTO known_nav (code, nav, nav_date, updated_at)
        VALUES (?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(code) DO UPDATE SET
            nav=excluded.nav, nav_date=excluded.nav_date,
            updated_at=datetime('now','localtime')
    """, (code, nav, nav_date))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════
#  余额宝
# ═══════════════════════════════════════════

def get_cash() -> float:
    conn = get_conn()
    r = conn.execute("SELECT amount FROM cash_balance WHERE id=1").fetchone()
    conn.close()
    return r["amount"] if r else 0.0


def set_cash(amount: float, note: str = ""):
    conn = get_conn()
    old = get_cash()
    conn.execute("UPDATE cash_balance SET amount=?, updated_at=datetime('now','localtime') WHERE id=1",
                 (amount,))
    conn.commit()
    conn.close()
    diff = round(amount - old, 2)
    if abs(diff) > 0.01:
        typ = "cash_in" if diff > 0 else "cash_out"
        add_transaction("CASH", typ, abs(diff),
                        note=note or f"余额变动: {old}→{amount}")


# ═══════════════════════════════════════════
#  迁移：从旧数据初始化 DB
# ═══════════════════════════════════════════

def migrate_from_current():
    """从 portfolio.py 的硬编码变量导入数据"""
    init_db()
    # 注意：运行此函数前 portfolio 模块已被 import，变量已在内存
    from portfolio import HOLDINGS, COST_BASIS, CASH_YUEBAO, PENDING_BUYS, DCA_LOG, KNOWN_NAV

    for code, (shares, avg_cost) in HOLDINGS.items():
        if shares and shares > 0:
            cost = COST_BASIS.get(code, 0)
            upsert_holding(code, shares, avg_cost, cost)

    set_cash(CASH_YUEBAO, "迁移初始化")

    for code, entry in PENDING_BUYS.items():
        amt = entry["amount"] if isinstance(entry, dict) else float(entry)
        d = entry.get("date", "") if isinstance(entry, dict) else ""
        add_pending_buy(code, amt, d or datetime.now().strftime("%Y-%m-%d"))

    for date, items in DCA_LOG.items():
        for code, amt in items.items():
            add_dca(date, code, amt)

    for code, nav in KNOWN_NAV.items():
        set_known_nav(code, nav)

    print(f"[OK] 迁移完成: {len(HOLDINGS)} 持仓, {len(PENDING_BUYS)} 待确认, 余额 {CASH_YUEBAO}")


# ═══════════════════════════════════════════
#  策略数据库
# ═══════════════════════════════════════════

def get_strategies(enabled_only: bool = True) -> list:
    """获取所有策略列表"""
    conn = get_conn()
    if enabled_only:
        rows = conn.execute("SELECT * FROM strategies WHERE enabled=1 ORDER BY id").fetchall()
    else:
        rows = conn.execute("SELECT * FROM strategies ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_strategy(name_or_id) -> dict:
    """按名称或ID查询单个策略"""
    conn = get_conn()
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        r = conn.execute("SELECT * FROM strategies WHERE id=?", (int(name_or_id),)).fetchone()
    else:
        r = conn.execute("SELECT * FROM strategies WHERE name=?", (name_or_id,)).fetchone()
    conn.close()
    return dict(r) if r else {}


def add_strategy(name: str, typ: str, description: str = "", params: str = "",
                 target_type: str = "", source: str = "", source_url: str = "") -> int:
    """添加策略到数据库"""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO strategies (name, type, description, params, target_type, source, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, typ, description, params, target_type, source, source_url))
        conn.commit()
        rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return rid
    except sqlite3.IntegrityError:
        print(f"⚠️ 策略 '{name}' 已存在")
        return -1
    finally:
        conn.close()


def update_strategy(strategy_id: int, **kwargs):
    """更新策略字段"""
    allowed = {"name", "type", "description", "params", "target_type", "source", "source_url", "enabled"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [strategy_id]
    conn = get_conn()
    conn.execute(f"UPDATE strategies SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_strategy(strategy_id: int):
    """删除策略及关联数据"""
    conn = get_conn()
    conn.execute("DELETE FROM strategy_signals WHERE strategy_id=?", (strategy_id,))
    conn.execute("DELETE FROM strategy_performance WHERE strategy_id=?", (strategy_id,))
    conn.execute("DELETE FROM strategies WHERE id=?", (strategy_id,))
    conn.commit()
    conn.close()


def add_strategy_signal(strategy_id: int, code: str, signal: str, score: float = None,
                        detail: str = "", date: str = None):
    """记录策略信号"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("""
        INSERT INTO strategy_signals (strategy_id, code, signal, score, detail, date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (strategy_id, code, signal, score, detail, date))
    conn.commit()
    conn.close()


def get_strategy_signals(strategy_id: int = None, code: str = None, limit: int = 100) -> list:
    """查询策略信号"""
    conn = get_conn()
    if strategy_id and code:
        rows = conn.execute(
            "SELECT s.*, st.name as strategy_name FROM strategy_signals s "
            "JOIN strategies st ON s.strategy_id=st.id "
            "WHERE s.strategy_id=? AND s.code=? ORDER BY s.date DESC LIMIT ?",
            (strategy_id, code, limit)).fetchall()
    elif strategy_id:
        rows = conn.execute(
            "SELECT s.*, st.name as strategy_name FROM strategy_signals s "
            "JOIN strategies st ON s.strategy_id=st.id "
            "WHERE s.strategy_id=? ORDER BY s.date DESC LIMIT ?",
            (strategy_id, limit)).fetchall()
    elif code:
        rows = conn.execute(
            "SELECT s.*, st.name as strategy_name FROM strategy_signals s "
            "JOIN strategies st ON s.strategy_id=st.id "
            "WHERE s.code=? ORDER BY s.date DESC LIMIT ?",
            (code, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT s.*, st.name as strategy_name FROM strategy_signals s "
            "JOIN strategies st ON s.strategy_id=st.id "
            "ORDER BY s.date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_strategy_perf(strategy_id: int, total_return: float = None, annual_return: float = None,
                       max_drawdown: float = None, sharpe_ratio: float = None, win_rate: float = None,
                       trades_count: int = None, start: str = None, end: str = None,
                       params_used: str = "", note: str = "") -> int:
    """记录策略回测/实盘绩效"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO strategy_performance
        (strategy_id, backtest_start, backtest_end, total_return, annual_return,
         max_drawdown, sharpe_ratio, win_rate, trades_count, params_used, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (strategy_id, start, end, total_return, annual_return,
          max_drawdown, sharpe_ratio, win_rate, trades_count, params_used, note))
    conn.commit()
    rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return rid


def get_strategy_perf(strategy_id: int = None, limit: int = 20) -> list:
    """查询策略绩效"""
    conn = get_conn()
    if strategy_id:
        rows = conn.execute(
            "SELECT p.*, s.name as strategy_name FROM strategy_performance p "
            "JOIN strategies s ON p.strategy_id=s.id "
            "WHERE p.strategy_id=? ORDER BY p.id DESC LIMIT ?",
            (strategy_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, s.name as strategy_name FROM strategy_performance p "
            "JOIN strategies s ON p.strategy_id=s.id "
            "ORDER BY p.id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
#  CLI：命令行快速操作
# ═══════════════════════════════════════════
"""
用法：
  python db.py init                    # 初始化/重建数据库
  python db.py migrate                 # 从旧数据迁移
  python db.py holdings                # 查看持仓
  python db.py holding <code>          # 查看单个
  python db.py set <code> <shares> <avg_cost> <cost_basis> [note]   # 更新持仓
  python db.py pending                 # 查看待确认
  python db.py pending_add <code> <amount> [date]   # 添加待确认
  python db.py pending_rm <code> [date]             # 移除待确认
  python db.py confirm <code> <shares> <nav>        # 确认到账
  python db.py cash                    # 查看余额
  python db.py cash_set <amount> [note]             # 更新余额
  python db.py nav                     # 查看已知净值
  python db.py nav_set <code> <nav> [date]          # 设置已知净值
  python db.py tx [code]               # 查看交易记录
  python db.py buy <code> <amount> <shares> <nav> [date]    # 记录买入
  python db.py sell <code> <shares> <nav> [date]            # 记录卖出
  python db.py strategy list              # 列出策略
  python db.py strategy add <name> <type> [desc] [params] [target] [source] [url]  # 添加策略
  python db.py strategy signals <id>      # 查看策略信号
  python db.py strategy perf [id]         # 查看策略绩效
"""

if __name__ == "__main__":
    import sys

    init_db()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    # ── init / migrate ──
    if cmd == "init":
        init_db()
        print("✅ 数据库已初始化")

    elif cmd == "migrate":
        migrate_from_current()

    # ── holdings 查看 ──
    elif cmd == "holdings":
        rows = get_holdings()
        if not rows:
            print("(空)")
        else:
            print(f"{'代码':>7} {'份额':>8} {'均价':>8} {'成本':>10} {'备注':>10}")
            print("-" * 50)
            for code, (shares, avg, cost, note) in sorted(rows.items()):
                print(f"{code:>7} {shares:>8.2f} {avg or 0:>8.4f} {cost:>10.2f} {note:>10}")

    elif cmd == "holding":
        code = sys.argv[2]
        h = get_holding(code)
        if h:
            print(f"{code}: 份额={h[0]:.2f}, 均价={h[1]:.4f}, 成本={h[2]:.2f}")
        else:
            print(f"{code}: 无持仓")

    # ── set 更新持仓 ──
    elif cmd == "set":
        code = sys.argv[2]
        shares = float(sys.argv[3])
        avg = float(sys.argv[4]) if len(sys.argv) > 4 else None
        cost = float(sys.argv[5]) if len(sys.argv) > 5 else 0
        note = sys.argv[6] if len(sys.argv) > 6 else ""
        upsert_holding(code, shares, avg, cost, note)
        print(f"✅ {code}: 份额={shares}, 均价={avg}, 成本={cost}")

    elif cmd == "delete_holding":
        code = sys.argv[2]
        delete_holding(code)
        print(f"✅ {code} 已删除")

    # ── pending 待确认 ──
    elif cmd == "pending":
        rows = get_pending_buys()
        if not rows:
            print("(无待确认)")
        else:
            for code, v in rows.items():
                print(f"{code}: {v['amount']:.0f}元 (买入日: {v['date']})")

    elif cmd == "pending_add":
        code = sys.argv[2]
        amt = float(sys.argv[3])
        date = sys.argv[4] if len(sys.argv) > 4 else None
        add_pending_buy(code, amt, date)
        print(f"✅ {code}: 待确认 {amt:.0f} 元")

    elif cmd == "pending_rm":
        code = sys.argv[2]
        date = sys.argv[3] if len(sys.argv) > 3 else None
        remove_pending_buy(code, date)
        print(f"✅ {code}: 待确认已移除")

    elif cmd == "confirm":
        code = sys.argv[2]
        shares = float(sys.argv[3])
        nav = float(sys.argv[4])
        r = confirm_pending_buy(code, shares, nav)
        if r:
            print(f"✅ {code}: 确认 {r['shares']:.2f}份 @ NAV={r['nav']:.4f}, 金额={r['amount']:.0f}元")
        else:
            print(f"⚠️ {code}: 无待确认记录")

    # ── cash 现金 ──
    elif cmd == "cash":
        print(f"余额宝: {get_cash():.2f} 元")

    elif cmd == "cash_set":
        amt = float(sys.argv[2])
        note = sys.argv[3] if len(sys.argv) > 3 else ""
        set_cash(amt, note)
        print(f"✅ 余额: {amt:.2f} 元")

    # ── nav 已知净值 ──
    elif cmd == "nav":
        navs = get_known_navs()
        if not navs:
            print("(无)")
        else:
            for code, nav in navs.items():
                print(f"{code}: {nav:.4f}")

    elif cmd == "nav_set":
        code = sys.argv[2]
        nav = float(sys.argv[3])
        date = sys.argv[4] if len(sys.argv) > 4 else None
        set_known_nav(code, nav, date)
        print(f"✅ {code}: NAV={nav:.4f}")

    # ── tx 交易记录 ──
    elif cmd == "tx":
        code = sys.argv[2] if len(sys.argv) > 2 else None
        rows = get_transactions(code, limit=30)
        if not rows:
            print("(无交易记录)")
        else:
            print(f"{'日期':>10} {'类型':>12} {'金额':>8} {'份额':>8} {'NAV':>8} {'备注':>10}")
            print("-" * 60)
            for r in rows:
                print(f"{r['date']:>10} {r['type']:>12} {r['amount']:>8.0f} "
                      f"{r['shares'] or 0:>8.2f} {r['nav'] or 0:>8.4f} {r.get('note','') or '':>10}")

    # ── buy / sell 直接记录 ──
    elif cmd == "buy":
        code = sys.argv[2]
        amount = float(sys.argv[3])
        shares = float(sys.argv[4])
        nav = float(sys.argv[5])
        date = sys.argv[6] if len(sys.argv) > 6 else None
        # 更新持仓
        h = get_holding(code)
        if h:
            old_shares, old_avg, old_cost = h
            new_shares = round(old_shares + shares, 2)
            new_cost = old_cost + amount
            new_avg = round(new_cost / new_shares, 4)
            upsert_holding(code, new_shares, new_avg, new_cost)
        else:
            upsert_holding(code, shares, round(amount / shares, 4), amount)
        add_transaction(code, "buy", amount, date, shares, nav, note="手动买入")
        print(f"✅ {code}: 买入 {amount:.0f}元, {shares:.2f}份 @ {nav:.4f}")

    elif cmd == "sell":
        code = sys.argv[2]
        shares_sold = float(sys.argv[3])
        nav = float(sys.argv[4])
        date = sys.argv[5] if len(sys.argv) > 5 else None
        h = get_holding(code)
        if not h:
            print(f"⚠️ {code}: 无持仓")
            sys.exit(1)
        old_shares, old_avg, old_cost = h
        ratio = shares_sold / old_shares if old_shares > 0 else 1
        amount = round(shares_sold * nav, 2)
        new_shares = round(old_shares - shares_sold, 2)
        new_cost = round(old_cost * (1 - ratio), 2)
        if new_shares <= 0:
            delete_holding(code)
        else:
            upsert_holding(code, new_shares, old_avg, new_cost)
        add_transaction(code, "sell", amount, date, shares_sold, nav, note="手动卖出")
        print(f"✅ {code}: 卖出 {amount:.0f}元, {shares_sold:.2f}份 @ {nav:.4f}")

    # ── strategy 策略管理 ──
    elif cmd == "strategy" and len(sys.argv) >= 3:
        sub = sys.argv[2]
        if sub == "list":
            rows = get_strategies(enabled_only=False)
            if not rows:
                print("(空)")
            else:
                print(f"{'ID':>3} {'名称':20s} {'类型':12s} {'标的':12s} {'来源':16s} {'启用':>4}")
                print("-" * 75)
                for r in rows:
                    print(f"{r['id']:>3} {r['name']:20s} {r['type']:12s} "
                          f"{r['target_type'] or '':12s} {(r['source'] or '')[:16]:16s} "
                          f"{'✅' if r['enabled'] else '❌'}")
        elif sub == "add" and len(sys.argv) >= 5:
            name = sys.argv[3]
            typ = sys.argv[4]
            desc = sys.argv[5] if len(sys.argv) > 5 else ""
            params = sys.argv[6] if len(sys.argv) > 6 else ""
            target = sys.argv[7] if len(sys.argv) > 7 else ""
            source = sys.argv[8] if len(sys.argv) > 8 else ""
            url = sys.argv[9] if len(sys.argv) > 9 else ""
            rid = add_strategy(name, typ, desc, params, target, source, url)
            if rid > 0:
                print(f"✅ 策略 '{name}' (ID={rid}) 已添加")
        elif sub == "signals":
            sid = int(sys.argv[3]) if len(sys.argv) > 3 else None
            rows = get_strategy_signals(strategy_id=sid, limit=30)
            if not rows:
                print("(无信号)")
            else:
                print(f"{'日期':>10} {'策略':20s} {'代码':>8} {'信号':8s} {'评分':>6}")
                print("-" * 60)
                for r in rows:
                    print(f"{r['date']:>10} {r['strategy_name']:20s} {r['code']:>8} "
                          f"{r['signal']:8s} {r['score'] or 0:>6.2f}")
        elif sub == "perf":
            sid = int(sys.argv[3]) if len(sys.argv) > 3 else None
            rows = get_strategy_perf(strategy_id=sid)
            if not rows:
                print("(无绩效记录)")
            else:
                print(f"{'策略':20s} {'收益%':>7} {'年化%':>7} {'最大回撤%':>9} {'夏普':>6} {'胜率%':>6}")
                print("-" * 65)
                for r in rows:
                    print(f"{r['strategy_name']:20s} {r['total_return'] or 0:>7.2f} "
                          f"{r['annual_return'] or 0:>7.2f} {r['max_drawdown'] or 0:>9.2f} "
                          f"{r['sharpe_ratio'] or 0:>6.2f} {r['win_rate'] or 0:>6.1f}")
        else:
            print(f"未知子命令: {sub}")

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
