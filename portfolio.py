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


def record_sell(code: str, shares_sold: float, nav: float = None) -> dict:
    """记录卖出：按比例减少成本和份额，返回已实现盈亏"""
    if code not in HOLDINGS or HOLDINGS[code] is None:
        return {"realized_pl": 0, "realized_pl_pct": 0}
    shares_now, avg_cost = HOLDINGS[code]
    if shares_now <= 0:
        return {"realized_pl": 0, "realized_pl_pct": 0}

    ratio = shares_sold / shares_now
    sold_cost = round(COST_BASIS.get(code, 0) * ratio, 2)
    sell_amount = round(shares_sold * nav, 2) if nav else 0
    realized_pl = round(sell_amount - sold_cost, 2)
    realized_pl_pct = round((sell_amount / sold_cost - 1) * 100, 2) if sold_cost > 0 else 0

    COST_BASIS[code] = round(COST_BASIS.get(code, 0) - sold_cost, 2)
    remaining = round(shares_now - shares_sold, 2)
    if remaining <= 0.01:
        HOLDINGS[code] = None
        COST_BASIS[code] = 0
    else:
        HOLDINGS[code] = (remaining, avg_cost)
    _sync_holdings()

    # 记录交易（含已实现盈亏）
    from db import add_transaction
    add_transaction(code, "sell", sell_amount, note=f"已实现盈亏 {realized_pl:+.2f}元 ({realized_pl_pct:+.1f}%)",
                    shares=shares_sold, nav=nav)

    return {"realized_pl": realized_pl, "realized_pl_pct": realized_pl_pct}


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
    """从 production.db 读取最新已确认的基金市值"""
    try:
        from db import get_confirmed_funds
        return get_confirmed_funds()
    except Exception:
        return {}


def project_from_confirmed() -> dict:
    """从最新 confirmed_funds 基准日，用日增长率推算到最新

    返回: {code: projected_value} 或 {} (无可用的确认数据)
    """
    from db import get_confirmed_funds
    from data import get_fund_nav
    from datetime import datetime, timedelta

    # 找确认日期
    from db import get_confirmed_daily
    daily = get_confirmed_daily()
    base_date = daily.get("date", "")
    if not base_date:
        return {}

    # 用同一基准日取所有基金的确认值（避免不同日期混用）
    confirmed = get_confirmed_funds(base_date)
    if not confirmed:
        return {}

    result = {}
    today = datetime.now().strftime("%Y-%m-%d")

    for code, base_value in confirmed.items():
        if base_value <= 0:
            continue
        df = get_fund_nav(code, days=60)
        if df is None or df.empty:
            continue
        df = df.sort_values("净值日期")

        # 只取基准日之后（不含当日）
        after = df[df["净值日期"] > base_date]
        if after.empty:
            result[code] = base_value  # 没有更新的数据，沿用基准值
            continue

        projected = base_value
        for _, row in after.iterrows():
            g = row.get("日增长率", 0)
            g = float(g) if g and str(g) != "nan" else 0
            projected *= (1 + g / 100)

        result[code] = round(projected, 2)

    return result


def calc_portfolio(use_confirmed: bool = True) -> dict:
    """计算组合市值、涨跌、盈亏

    use_confirmed=True 时优先使用已确认的基金市值
    """
    confirmed_funds = get_confirmed_fund_values() if use_confirmed else {}

    # 如果有确认数据，尝试用日增长率推算到最新
    projected = {}
    base_date = ""
    if use_confirmed and confirmed_funds:
        projected = project_from_confirmed()
        from db import get_confirmed_daily
        base_date = get_confirmed_daily().get("date", "")

    # 拉净值用于显示（即使有确认数据也需要 nav 和 shares）
    from data import get_all_funds_nav
    navs = get_all_funds_nav(days=5)
    today = datetime.now().strftime("%Y-%m-%d")

    summary = {
        "日期": today,
        "基准日": base_date if base_date else today,
        "推算模式": bool(projected),
        "基金": [],
        "基金市值": 0, "基金成本": 0, "基金盈亏": 0,
        "余额宝": CASH_YUEBAO,
        "总资产": 0, "总成本": CASH_YUEBAO, "总盈亏": 0, "总盈亏率": 0, "日涨跌": 0,
    }

    total_value = CASH_YUEBAO
    prev_total = CASH_YUEBAO

    for code, info in FUNDS.items():
        cost_basis = COST_BASIS.get(code, 0)

        # 优先：日增长率推算值
        proj_val = projected.get(code)
        if proj_val and proj_val > 0:
            value = proj_val
            pl = round(value - cost_basis, 2)
            pl_pct = round((value / cost_basis - 1) * 100, 2) if cost_basis > 0 else 0
            total_value += value
            days_ago = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(base_date, "%Y-%m-%d")).days if base_date else 0
            h = HOLDINGS.get(code)
            src = "alipay"
            sh = h[0] if h else 0
            df_nav = navs.get(code)
            cur_nav = float(df_nav.iloc[-1]["单位净值"]) if df_nav is not None and not df_nav.empty else 0
            summary["基金"].append({
                "code": code, "name": info["name"],
                "市值": value, "成本": cost_basis, "盈亏": pl, "盈亏率": pl_pct,
                "净值": cur_nav, "涨跌": f"推算({base_date}, +{days_ago}天)", "占比": 0,
                "source": src, "份额": sh,
            })
            continue

        # 其次：静态确认值
        cf_val = confirmed_funds.get(code)
        if cf_val and cf_val > 0:
            value = cf_val
            pl = round(value - cost_basis, 2)
            pl_pct = round((value / cost_basis - 1) * 100, 2) if cost_basis > 0 else 0
            total_value += value
            h = HOLDINGS.get(code)
            sh = h[0] if h else 0
            summary["基金"].append({
                "code": code, "name": info["name"],
                "市值": value, "成本": cost_basis, "盈亏": pl, "盈亏率": pl_pct,
                "净值": 0, "涨跌": "已确认", "占比": 0,
                "source": "alipay", "份额": sh,
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

        h = HOLDINGS.get(code)
        src = "alipay"  # shares from alipay
        sh = h[0] if h else shares
        summary["基金"].append({
            "code": code, "name": info["name"],
            "市值": value, "成本": cost_basis,
            "盈亏": pl, "盈亏率": pl_pct,
            "净值": nav, "涨跌": f"{daily_change_pct:+.2f}%",
            "source": src, "份额": sh,
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

    # ── 风险调整指标（调用 risk.py）──
    try:
        from risk import (get_all_nav_returns,calc_portfolio_daily_returns,calc_portfolio_weights,
            calc_annualized_vol,calc_max_drawdown,calc_sharpe,calc_calmar,calc_var,
            get_benchmark_returns,calc_beta_alpha)
        nav_r=get_all_nav_returns(days=250)
        w=calc_portfolio_weights()
        pr=calc_portfolio_daily_returns(nav_r,w)
        if not pr.empty and len(pr)>=20:
            summary["年化收益率"] = round(float(pr.mean()*252),2)
            summary["年化波动率"] = calc_annualized_vol(pr)
            dd=calc_max_drawdown(pr)
            summary["最大回撤"] = dd.get("max_dd")
            summary["回撤起始"] = str(dd.get("start",""))[:10] if dd.get("start") else ""
            summary["回撤结束"] = str(dd.get("end",""))[:10] if dd.get("end") else ""
            summary["夏普比率"] = calc_sharpe(pr)
            summary["Calmar比率"] = calc_calmar(pr)
            summary["VaR_95"] = calc_var(pr,0.05)
            summary["VaR_99"] = calc_var(pr,0.01)
            # Beta/Alpha vs HS300
            bm=get_benchmark_returns(days=250)
            if not bm.empty:
                ba=calc_beta_alpha(pr,bm)
                summary["Beta"]=ba.get("beta")
                summary["Alpha"]=ba.get("alpha")
    except Exception:
        pass

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
