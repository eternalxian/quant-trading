"""策略健康度监控 — rolling metrics + 降级检测"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import sqlite3, os

logger = logging.getLogger("quant.health")

DB = os.path.join(os.path.dirname(__file__), "..", "data", "quant.db")


@dataclass
class StrategyHealth:
    name: str
    status: str = "active"     # active | degraded | stopped
    total_return: float = 0.0
    sharpe: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    rolling_sharpe: float = 0.0      # 最近 20 个信号
    rolling_drawdown: float = 0.0
    rolling_winrate: float = 0.0
    consecutive_losses: int = 0
    last_signal_date: str = ""
    degradation_reason: str = ""


def check_health(strategy_name: str, recent_returns: list[float], historical_sharpe: float = 0.5) -> StrategyHealth:
    """检查策略健康度

    Args:
        strategy_name: 策略名
        recent_returns: 最近 N 次信号收益列表（%）
        historical_sharpe: 历史夏普基准

    Returns:
        StrategyHealth with status
    """
    import numpy as np

    health = StrategyHealth(name=strategy_name)

    if not recent_returns:
        health.status = "active"
        return health

    arr = np.array(recent_returns)
    health.total_return = float(np.sum(arr))
    health.win_rate = float(np.sum(arr > 0) / len(arr))

    if len(arr) >= 5:
        health.rolling_sharpe = float(np.mean(arr[-20:]) / (np.std(arr[-20:]) + 1e-8))
        health.rolling_winrate = float(np.sum(arr[-10:] > 0) / min(len(arr[-10:]), 10))

    # 计算滚动最大回撤
    if len(arr) >= 5:
        cumsum = np.cumsum(arr[-20:])
        peak = np.maximum.accumulate(cumsum)
        dd = peak - cumsum
        health.rolling_drawdown = float(np.max(dd) if len(dd) > 0 else 0)

    # ── 降级检测 ──
    if health.rolling_sharpe < historical_sharpe * 0.5 and len(arr) >= 20:
        health.status = "degraded"
        health.degradation_reason = (
            f"滚动夏普 {health.rolling_sharpe:.2f} 低于历史 {historical_sharpe:.2f} 的 50%"
        )

    if health.rolling_drawdown > 10 and len(arr) >= 5:
        health.status = "degraded"
        health.degradation_reason = (
            f"滚动回撤 {health.rolling_drawdown:.1f}% 超过 10% 阈值"
        )

    # 连续亏损
    consecutive = 0
    for r in reversed(arr):
        if r <= 0:
            consecutive += 1
        else:
            break
    health.consecutive_losses = consecutive
    if consecutive >= 5:
        health.status = "stopped"
        health.degradation_reason = f"连续亏损 {consecutive} 次，策略停止"

    return health


def log_health(health: StrategyHealth):
    """持久化健康度到数据库"""
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO strategy_perf_log
               (strategy_name, date, sharpe, win_rate, status, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                health.name,
                datetime.now().strftime("%Y-%m-%d"),
                round(health.rolling_sharpe, 4),
                round(health.rolling_winrate, 4),
                health.status,
                health.degradation_reason,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"记录健康度失败: {e}")
