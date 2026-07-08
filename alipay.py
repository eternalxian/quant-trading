"""
支付宝数据隔离层

所有来自支付宝的手动输入数据统一走这里：
- 份额 (shares)
- 确认市值 (confirmed value)
- 成本 (cost basis)

数据标记:
  source = "alipay"   → 手动确认，有 freshness 要求
  source = "system"   → 系统自动计算（净值 × 份额）
  source = "projected" → 基于日增长率推算
"""
import logging
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("quant.alipay")


@dataclass
class AlipayHolding:
    code: str
    name: str
    shares: float                # 持有份额
    confirmed_value: float       # 支付宝确认市值
    confirmed_date: str          # 确认日期
    cost_basis: float            # 成本
    avg_cost: float              # 持仓均价
    daily_pl: float = 0.0        # 昨日收益
    holding_pl: float = 0.0      # 持有收益
    holding_pl_pct: float = 0.0  # 持有收益率
    freshness_days: int = 0      # 距今几天（0=今天刚确认）
    stale: bool = False          # 超过 7 天未确认？


def load_from_alipay() -> dict[str, AlipayHolding]:
    """从 production.db 加载支付宝确认过的持仓数据

    Returns:
        {code: AlipayHolding} 仅返回 source='alipay' 的基金
    """
    from db import prod_conn
    conn = prod_conn()
    rows = conn.execute("SELECT * FROM holdings WHERE shares > 0").fetchall()
    conn.close()

    result = {}
    for r in rows:
        code = r["code"]
        note = r.get("note", "") or ""

        # 从 confirmed_funds 找最新确认值
        conn2 = prod_conn()
        cf = conn2.execute(
            "SELECT value, date FROM confirmed_funds WHERE code=? ORDER BY date DESC LIMIT 1",
            (code,)
        ).fetchone()
        conn2.close()

        confirmed_value = cf["value"] if cf else 0
        confirmed_date = cf["date"] if cf else ""

        # 新鲜度
        freshness_days = 0
        stale = False
        if confirmed_date:
            try:
                dt = datetime.strptime(confirmed_date, "%Y-%m-%d")
                freshness_days = (datetime.now() - dt).days
                stale = freshness_days > 7
            except Exception:
                pass

        result[code] = AlipayHolding(
            code=code,
            name="",
            shares=r["shares"],
            confirmed_value=confirmed_value,
            confirmed_date=confirmed_date,
            cost_basis=r.get("cost_basis", 0),
            avg_cost=r.get("avg_cost", 0),
            freshness_days=freshness_days,
            stale=stale,
        )

    return result


def update_alipay_holding(code: str, shares: float, confirmed_value: float,
                          cost_basis: float = 0, daily_pl: float = 0,
                          holding_pl: float = 0, note: str = "") -> AlipayHolding:
    """更新支付宝确认的持仓数据（一次写入 holdings + confirmed_funds + confirmed_daily）

    Args:
        code: 基金代码
        shares: 持有份额（从支付宝抄）
        confirmed_value: 支付宝显示的市值
        cost_basis: 成本（value - holding_pl）
        daily_pl: 昨日收益
        holding_pl: 持有收益
        note: 备注（如 "7/6 支付宝确认"）
    """
    from db import upsert_holding, prod_conn
    from config import FUNDS

    name = FUNDS.get(code, {}).get("name", code)
    avg_cost = round(cost_basis / shares, 4) if shares > 0 else 0
    today = datetime.now().strftime("%Y-%m-%d")

    # 写入 holdings
    upsert_holding(code, shares, avg_cost, cost_basis,
                   note=f"alipay|{today}|{note}")

    # 写入 confirmed_funds
    conn = prod_conn()
    conn.execute(
        "INSERT OR REPLACE INTO confirmed_funds (date, code, value) VALUES (?,?,?)",
        (today, code, confirmed_value)
    )
    conn.commit(); conn.close()

    # 写入 confirmed_daily（或更新）
    pl_pct = round(confirmed_value / cost_basis - 1, 4) * 100 if cost_basis > 0 else 0
    from db import save_confirmed_daily
    save_confirmed_daily(today, pl=daily_pl, pl_pct=round(pl_pct, 2),
                         total=confirmed_value, cash=0)

    logger.info(f"Alipay sync: {code} {name} shares={shares} value={confirmed_value}")

    return AlipayHolding(
        code=code, name=name, shares=shares,
        confirmed_value=confirmed_value, confirmed_date=today,
        cost_basis=cost_basis, avg_cost=avg_cost,
        daily_pl=daily_pl, holding_pl=holding_pl,
        holding_pl_pct=round(pl_pct, 2),
        freshness_days=0, stale=False,
    )


def get_freshness_report() -> dict:
    """支付宝数据新鲜度报告

    Returns:
        {"funds": {code: {stale, days_ago, last_sync}}, "overall_stale": bool}
    """
    holdings = load_from_alipay()
    funds = {}
    any_stale = False

    for code, h in holdings.items():
        funds[code] = {
            "stale": h.stale,
            "days_ago": h.freshness_days,
            "last_sync": h.confirmed_date or "从未",
        }
        if h.stale:
            any_stale = True

    return {"funds": funds, "overall_stale": any_stale}
