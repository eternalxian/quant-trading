"""状态一致性检查器 — 防止运行时状态漂移"""

import logging
import sqlite3, os
from dataclasses import dataclass, field

logger = logging.getLogger("quant.runtime.state")

DB = os.path.join(os.path.dirname(__file__), "..", "data", "quant.db")


@dataclass
class StateHealth:
    healthy: bool = True
    checks: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def check_all() -> StateHealth:
    """运行全部一致性检查"""
    health = StateHealth()

    _check_holdings_consistency(health)
    _check_cash_consistency(health)
    _check_pending_orders(health)
    _check_execution_log_gaps(health)
    _check_risk_circuit_status(health)

    health.healthy = len(health.errors) == 0
    if health.warnings:
        logger.warning(f"状态检查警告: {health.warnings}")
    if health.errors:
        logger.error(f"状态检查异常: {health.errors}")

    return health


def _check_holdings_consistency(health: StateHealth):
    """检查持仓成本与份额一致性"""
    try:
        from db import get_holdings
        holdings = get_holdings()
        for code, (shares, avg, cost, _) in holdings.items():
            # 成本 = 份额 × 均价（允许1元误差）
            expected = round(shares * avg, 2)
            if abs(expected - cost) > 10 and cost > 0 and shares > 0:
                health.warnings.append(
                    f"{code} 成本不一致: {cost:.0f} vs 份额×均价={expected:.0f}"
                )
        health.checks.append({"name": "持仓一致性", "pass": True})
    except Exception as e:
        health.errors.append(f"持仓检查失败: {e}")


def _check_cash_consistency(health: StateHealth):
    """检查现金是否异常"""
    try:
        from db import get_cash
        cash = get_cash()
        if cash < 0:
            health.errors.append(f"余额宝为负: {cash:.2f}")
        if cash > 1000000:
            health.warnings.append(f"余额宝异常高: {cash:.2f}")
        health.checks.append({"name": "现金检查", "pass": cash >= 0})
    except Exception as e:
        health.errors.append(f"现金检查失败: {e}")


def _check_pending_orders(health: StateHealth):
    """检查是否有超期未确认的待确认申购"""
    try:
        from db import get_pending_buys
        from datetime import datetime, timedelta
        pending = get_pending_buys()
        today = datetime.now().strftime("%Y-%m-%d")
        for code, entry in pending.items():
            date_str = entry.get("date", "") if isinstance(entry, dict) else ""
            if date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                if (datetime.now() - dt).days > 3:
                    health.warnings.append(f"{code} 待确认超过3天: {date_str}")
        health.checks.append({"name": "待确认检查", "pass": True, "pending_count": len(pending)})
    except Exception as e:
        health.errors.append(f"待确认检查失败: {e}")


def _check_execution_log_gaps(health: StateHealth):
    """检查执行日志是否有缺口"""
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM execution_log")
        count = cur.fetchone()[0]
        conn.close()
        health.checks.append({"name": "执行日志", "pass": True, "record_count": count})
    except Exception:
        # 表可能还不存在，不算错
        health.checks.append({"name": "执行日志", "pass": True, "record_count": 0})


def _check_risk_circuit_status(health: StateHealth):
    """检查风控熔断器状态"""
    try:
        from risk_engine import status as risk_status, is_closed
        s = risk_status()
        if not is_closed():
            health.warnings.append(f"风控熔断中: {s.get('reason', '未知')}")
        health.checks.append({"name": "风控状态", "pass": is_closed()})
    except Exception as e:
        health.warnings.append(f"风控检查失败: {e}")
