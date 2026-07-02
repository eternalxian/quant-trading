"""风控规则引擎 — 确定性规则，绝不允许AI介入"""

from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger("quant.risk")


@dataclass
class RiskDecision:
    """统一风控决策结构，所有策略出口必须经过此结构"""
    allowed: bool
    reason: str
    level: str = "info"         # info | warning | critical
    max_position: float = 0.0   # 允许最大仓位（元）
    stop_loss: Optional[float] = None  # 止损线（净值），None=不设
    metadata: dict = field(default_factory=dict)


# ═══════════════════ 规则参数 ═══════════════════

DEFAULTS = {
    "single_position_limit": 0.30,   # 单基金仓位上限 30%
    "total_position_limit": 0.95,    # 总仓位上限 95%（留5%余额宝）
    "max_daily_loss_pct": 0.03,      # 日回撤熔断 3%
    "stop_loss_pct": 0.05,           # 单笔止损 -5%
    "qdii_cooling_days": 5,          # QDII 赎回冷却期（天）
    "min_cash_buffer": 2000.0,       # 余额宝最低安全垫
    "pre_close_lock_minutes": 5,     # 收盘前 N 分钟不交易
    "max_consecutive_losses": 3,     # 连续亏损次数熔断
}


# ═══════════════════ 规则函数 ═══════════════════

def check_single_position(
    code: str, buy_amount: float, current_value: float, total_assets: float
) -> RiskDecision:
    """单仓上限检查"""
    after_value = current_value + buy_amount
    ratio = after_value / total_assets if total_assets > 0 else 1.0
    limit = DEFAULTS["single_position_limit"]
    if ratio > limit:
        return RiskDecision(
            allowed=False,
            reason=f"{code} 买入后仓位 {ratio:.1%} 超过上限 {limit:.0%}",
            level="critical",
            max_position=total_assets * limit,
        )
    return RiskDecision(allowed=True, reason="单仓上限通过", max_position=after_value)


def check_total_position(fund_value: float, total_assets: float) -> RiskDecision:
    """总仓位上限检查"""
    ratio = fund_value / total_assets if total_assets > 0 else 0
    limit = DEFAULTS["total_position_limit"]
    if ratio > limit:
        return RiskDecision(
            allowed=False,
            reason=f"总仓位 {ratio:.1%} 超过上限 {limit:.0%}",
            level="critical",
        )
    return RiskDecision(allowed=True, reason="总仓位通过")


def check_daily_drawdown(today_loss_pct: float) -> RiskDecision:
    """日回撤熔断"""
    threshold = DEFAULTS["max_daily_loss_pct"]
    if abs(today_loss_pct) > threshold:
        return RiskDecision(
            allowed=False,
            reason=f"日回撤 {today_loss_pct:.2%} 超过熔断线 {threshold:.1%}，停止所有交易",
            level="critical",
        )
    return RiskDecision(allowed=True, reason="日回撤正常")


def check_stop_loss(current_pl_pct: float, entry_nav: float = None) -> RiskDecision:
    """单笔止损检查"""
    threshold = DEFAULTS["stop_loss_pct"]
    if current_pl_pct <= -threshold:
        return RiskDecision(
            allowed=False,
            reason=f"触发止损：亏损 {current_pl_pct:.2%} ≥ {threshold:.0%}",
            level="warning",
            stop_loss=entry_nav,
        )
    return RiskDecision(allowed=True, reason="止损线内")


def check_cash_buffer(cash: float, buy_amount: float) -> RiskDecision:
    """余额宝安全垫检查"""
    after = cash - buy_amount
    minimum = DEFAULTS["min_cash_buffer"]
    if after < minimum:
        return RiskDecision(
            allowed=False,
            reason=f"余额宝 {cash:.0f} 买入 {buy_amount:.0f} 后只剩 {after:.0f}，低于安全垫 {minimum:.0f}",
            level="warning",
        )
    return RiskDecision(allowed=True, reason="安全垫充足")


def check_consecutive_losses(count: int) -> RiskDecision:
    """连续亏损熔断"""
    limit = DEFAULTS["max_consecutive_losses"]
    if count >= limit:
        return RiskDecision(
            allowed=False,
            reason=f"连续亏损 {count} 次，触发熔断（上限 {limit} 次），暂停交易",
            level="critical",
        )
    return RiskDecision(allowed=True, reason="连续亏损次数正常")


# ═══════════════════ 统一评估入口 ═══════════════════

def evaluate(
    code: str,
    action: str,          # buy / sell
    amount: float,
    current_value: float,
    total_assets: float,
    fund_value: float,
    cash: float,
    today_loss_pct: float = 0.0,
    current_pl_pct: float = 0.0,
    consecutive_losses: int = 0,
) -> RiskDecision:
    """统一风控评估，所有策略信号必须经过此入口

    Returns:
        RiskDecision: 通过则 allowed=True，拒绝则 allowed=False + reason
    """
    checks = []

    if action == "buy":
        checks.append(check_single_position(code, amount, current_value, total_assets))
        checks.append(check_total_position(fund_value + amount, total_assets))
        checks.append(check_cash_buffer(cash, amount))

    checks.append(check_daily_drawdown(today_loss_pct))
    checks.append(check_consecutive_losses(consecutive_losses))

    if current_pl_pct < 0 and action == "sell":
        checks.append(check_stop_loss(current_pl_pct))

    # 任一条不通过即拒绝
    for c in checks:
        if not c.allowed:
            logger.warning(f"风控拒绝 {code} {action} {amount}: {c.reason}")
            return c

    logger.info(f"风控通过 {code} {action} {amount}")
    return RiskDecision(allowed=True, reason="全部风控规则通过", level="info")
