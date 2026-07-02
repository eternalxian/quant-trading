"""
持仓追踪：计算每日组合市值、涨跌、盈亏、持仓占比
数据源：SQLite (db.py) — 修改数据请用 python db.py <命令>
"""
from datetime import datetime
import pandas as pd
from config import FUNDS, DCA_SCHEDULE
from db import (get_holdings, get_pending_buys, get_cash, get_known_navs, get_dca_log,
                upsert_holding, set_cash, add_pending_buy, add_dca,
                confirm_pending_buy as db_confirm_pending)


# ═══════════════════════════════════════════
#  从数据库加载（模块加载时执行）
# ═══════════════════════════════════════════

def reload_from_db():
    """从 SQLite 重新加载所有数据（供外部调用）"""
    global HOLDINGS, COST_BASIS, CASH_YUEBAO, PENDING_BUYS, DCA_LOG, KNOWN_NAV
    raw = get_holdings()
    HOLDINGS.clear()
    COST_BASIS.clear()
    for code, (shares, avg, cost, _note) in raw.items():
        HOLDINGS[code] = (shares, avg)
        COST_BASIS[code] = cost
    CASH_YUEBAO = get_cash()
    PENDING_BUYS.clear()
    PENDING_BUYS.update(get_pending_buys())
    DCA_LOG.clear()
    DCA_LOG.update(get_dca_log())
    KNOWN_NAV.clear()
    KNOWN_NAV.update(get_known_navs())


# ====== 变量（dashboard 直接引用）======
HOLDINGS = {}      # {code: (shares, avg_cost)}
COST_BASIS = {}    # {code: total_cost}
CASH_YUEBAO = 0.0  # 余额宝
PENDING_BUYS = {}  # {code: {"amount": x, "date": "..."}}
DCA_LOG = {}       # {date: {code: amount}}
KNOWN_NAV = {}     # {code: nav}

reload_from_db()


# ═══════════════════════════════════════════
#  数据操作（同时写回数据库）
# ═══════════════════════════════════════════

def _sync_holdings():
    """将内存持仓同步到 SQLite"""
    for code, (shares, avg) in HOLDINGS.items():
        if shares and shares > 0:
            upsert_holding(code, shares, avg, COST_BASIS.get(code, 0))


def record_buy(code: str, amount: float, nav: float = None):
    """记录买入：更新成本，可选更新份额"""
    COST_BASIS[code] = COST_BASIS.get(code, 0) + amount
    if nav is not None and code in HOLDINGS and HOLDINGS[code] is not None:
        shares_now, avg_cost = HOLDINGS[code]
        new_shares = round(amount / nav, 2)
        total_shares = round(shares_now + new_shares, 2)
        total_cost = shares_now * avg_cost + amount
        new_avg = round(total_cost / total_shares, 4)
        HOLDINGS[code] = (total_shares, new_avg)
    elif nav is not None and (code not in HOLDINGS or HOLDINGS[code] is None):
        shares = round(amount / nav, 2)
        HOLDINGS[code] = (shares, nav)
        COST_BASIS[code] = amount
    _sync_holdings()


def record_sell(code: str, shares_sold: float, nav: float = None):
    """记录卖出：按比例减少成本和份额"""
    if code not in HOLDINGS or HOLDINGS[code] is None:
        return
    shares_now, avg_cost = HOLDINGS[code]
    if shares_now <= 0:
        return
    ratio = shares_sold / shares_now
    COST_BASIS[code] = round(COST_BASIS.get(code, 0) * (1 - ratio), 2)
    remaining = round(shares_now - shares_sold, 2)
    if remaining <= 0.01:
        HOLDINGS[code] = None
        COST_BASIS[code] = 0
    else:
        HOLDINGS[code] = (remaining, avg_cost)
    _sync_holdings()


def confirm_pending_buys(code: str, shares: float, nav: float):
    """待确认→正式持仓"""
    entry = PENDING_BUYS.pop(code, None)
    if entry is None:
        return
    amount = entry["amount"] if isinstance(entry, dict) else float(entry)
    COST_BASIS[code] = COST_BASIS.get(code, 0) + amount
    if code in HOLDINGS and HOLDINGS[code] is not None:
        shares_now, avg_cost = HOLDINGS[code]
        total_shares = round(shares_now + shares, 2)
        total_cost = shares_now * avg_cost + amount
        new_avg = round(total_cost / total_shares, 4)
        HOLDINGS[code] = (total_shares, new_avg)
    else:
        HOLDINGS[code] = (shares, round(amount / shares, 4) if shares else nav)
        if code in COST_BASIS:
            COST_BASIS[code] = amount
    _sync_holdings()


def update_holdings(code: str, shares: float, cost_nav: float = None):
    """直接更新持仓份额（慎用，推荐走 pending 流程）"""
    HOLDINGS[code] = (shares, cost_nav)
    _sync_holdings()


# ═══════════════════════════════════════════
#  定投管理
# ═══════════════════════════════════════════

def apply_dca(date: str = None) -> dict:
    """每日定投：记录 DCA + 加入待确认"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    if date in DCA_LOG:
        return {}

    DCA_LOG[date] = {}
    for code, amount in DCA_SCHEDULE.items():
        DCA_LOG[date][code] = amount
        add_dca(date, code, amount)
        entry = PENDING_BUYS.get(code)
        if entry is None:
            PENDING_BUYS[code] = {"amount": amount, "date": date}
        else:
            existing = entry["amount"] if isinstance(entry, dict) else float(entry)
            PENDING_BUYS[code] = {"amount": existing + amount, "date": date}
        add_pending_buy(code, amount, date)

    return DCA_LOG[date]


def settle_pending(navs: dict = None) -> list:
    """自动结算待确认申购（有 NAV 数据时）"""
    if navs is None:
        navs = get_all_funds_nav(days=10)

    settled = []
    for code in list(PENDING_BUYS.keys()):
        if code not in navs or navs[code].empty:
            continue
        entry = PENDING_BUYS[code]
        amount = entry["amount"] if isinstance(entry, dict) else float(entry)
        buy_date = entry.get("date") if isinstance(entry, dict) else None
        df = navs[code]
        latest = df.iloc[-1]
        nav = latest["单位净值"]
        nav_date = latest.get("净值日期")
        if buy_date and nav_date is not None:
            nav_date_str = nav_date.strftime("%Y-%m-%d") if hasattr(nav_date, "strftime") else str(nav_date)
            if nav_date_str < buy_date:
                continue
        shares = round(amount / nav, 2)
        confirm_pending_buys(code, shares, nav)
        settled.append({"code": code, "amount": amount, "shares": shares, "nav": nav, "date": buy_date})

    return settled


# ═══════════════════════════════════════════
#  组合计算（只读）
# ═══════════════════════════════════════════

def get_confirmed_fund_values() -> dict[str, float]:
    """从 SQLite 读取最新已确认的基金市值"""
    try:
        import sqlite3, os
        DB = os.path.join(os.path.dirname(__file__), "data", "quant.db")
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT code, value FROM confirmed_funds ORDER BY date DESC LIMIT 20")
        funds = {}
        for row in cur.fetchall():
            if row[0] not in funds:
                funds[row[0]] = row[1]
        conn.close()
        return funds
    except Exception:
        return {}


def calc_portfolio(use_confirmed: bool = True) -> dict:
    """计算组合市值、涨跌、盈亏

    use_confirmed=True 时优先使用已确认的基金市值
    """
    confirmed_funds = get_confirmed_fund_values() if use_confirmed else {}

    # 如果全部基金都有确认值，跳过 akshare（避免 py_mini_racer 崩溃）
    all_confirmed = use_confirmed and len(confirmed_funds) >= len(FUNDS) - 1  # 允许差1只
    if all_confirmed:
        navs = {}
    else:
        from data import get_all_funds_nav
        navs = get_all_funds_nav(days=5)
    today = datetime.now().strftime("%Y-%m-%d")

    summary = {
        "日期": today,
        "基金": [],
        "基金市值": 0, "基金成本": 0, "基金盈亏": 0,
        "余额宝": CASH_YUEBAO,
        "总资产": 0, "总成本": CASH_YUEBAO, "总盈亏": 0, "总盈亏率": 0, "日涨跌": 0,
    }

    total_value = CASH_YUEBAO
    prev_total = CASH_YUEBAO

    for code, info in FUNDS.items():
        cost_basis = COST_BASIS.get(code, 0)

        # 优先确认市值
        cf_val = confirmed_funds.get(code)
        if cf_val and cf_val > 0:
            value = cf_val
            pl = round(value - cost_basis, 2)
            pl_pct = round((value / cost_basis - 1) * 100, 2) if cost_basis > 0 else 0
            total_value += value
            summary["基金"].append({
                "code": code, "name": info["name"],
                "市值": value, "成本": cost_basis, "盈亏": pl, "盈亏率": pl_pct,
                "净值": 0, "涨跌": "已确认", "占比": 0,
            })
            continue

        # 无确认值 → 用系统净值（aksahre）
        shares_data = HOLDINGS.get(code)
        if shares_data is None or code not in navs:
            summary["基金"].append({"code": code, "name": info["name"],
                                     "市值": 0, "成本": cost_basis, "盈亏": -cost_basis,
                                     "盈亏率": -100, "涨跌": "-", "备注": "无数据"})
            continue

        shares, avg_cost = shares_data
        df = navs[code]
        latest = df.iloc[-1]
        nav = latest["单位净值"]
        known = KNOWN_NAV.get(code)
        if known and abs(nav - known) / max(nav, known) > 0.1:
            nav = known
        value = round(shares * nav, 2)

        if nav is not None:
            if len(df) >= 2:
                prev_nav = df.iloc[-2]["单位净值"]
                daily_change_pct = round((nav - prev_nav) / prev_nav * 100, 2)
            else:
                daily_change_pct = 0
            prev_value = shares * (df.iloc[-2]["单位净值"] if len(df) >= 2 else nav)
        else:
            # 使用确认市值，无法计算日内涨跌
            daily_change_pct = 0
            prev_value = value  # 假设不变

        pl = round(value - cost_basis, 2)
        pl_pct = round((value / cost_basis - 1) * 100, 2) if cost_basis > 0 else 0

        total_value += value
        prev_total += prev_value

        summary["基金"].append({
            "code": code, "name": info["name"],
            "市值": value, "成本": cost_basis,
            "盈亏": pl, "盈亏率": pl_pct,
            "净值": nav, "涨跌": f"{daily_change_pct:+.2f}%",
        })

    fund_value = round(total_value - CASH_YUEBAO, 2)
    total_cost = sum(COST_BASIS.values()) + CASH_YUEBAO
    total_pl = round(total_value - total_cost, 2)
    total_pl_pct = round((total_value / total_cost - 1) * 100, 4) if total_cost > 0 else 0

    summary["基金市值"] = fund_value
    summary["基金成本"] = round(sum(COST_BASIS.values()), 2)
    summary["基金盈亏"] = round(fund_value - summary["基金成本"], 2)
    summary["总资产"] = round(total_value, 2)
    summary["总成本"] = round(total_cost, 2)
    summary["总盈亏"] = total_pl
    summary["总盈亏率"] = total_pl_pct
    if prev_total > 0:
        summary["日涨跌"] = round((total_value - prev_total) / prev_total * 100, 2)

    for item in summary["基金"]:
        item["占比"] = round(item["市值"] / summary["总资产"] * 100, 1) if summary["总资产"] > 0 else 0

    return summary


def print_portfolio(summary: dict):
    """打印组合概览"""
    print(f"\n{'='*60}")
    print(f"  持仓概览  {summary['日期']}")
    print(f"{'='*60}")
    print(f"  {'代码':>7} {'名称':16s} {'市值':>8} {'成本':>8} {'盈亏':>9} {'涨跌':>7} {'占比':>5}")
    print(f"  {'-'*58}")
    for item in summary["基金"]:
        pl = item.get("盈亏", 0)
        pl_str = f"{pl:+.1f}" if isinstance(pl, (int, float)) else str(pl)
        chg = item.get("涨跌", "-")
        print(f"  {item['code']:>7} {item['name']:16s} {item['市值']:>8.1f} {item.get('成本',0):>8.1f} "
              f"{pl_str:>9s} {chg:>7s} {item.get('占比',0):>4.1f}%")
    print(f"  {'-'*58}")
    print(f"  基金市值: {summary['基金市值']:>8.2f}  成本: {summary['基金成本']:>8.2f}  "
          f"盈亏: {summary['基金盈亏']:+.2f}")
    print(f"  余额宝:   {summary['余额宝']:>8.2f}")
    print(f"  {'='*58}")
    total_pl = summary["总盈亏"]
    total_pl_pct = summary["总盈亏率"]
    print(f"  总资产:   {summary['总资产']:>8.2f}  "
          f"总盈亏: {total_pl:+.2f} ({total_pl_pct:+.2f}%)  "
          f"日涨跌: {summary['日涨跌']:+.2f}%")
    print(f"{'='*60}\n")
