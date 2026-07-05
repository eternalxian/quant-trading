"""
个股风控模块 — A股特有规则 + 仓位计算 + ATR止损

独立于基金系统的 risk.py / risk_engine/，专为个股交易设计。
"""

import math
import pandas as pd
import numpy as np
from datetime import datetime, time
from dataclasses import dataclass, field


# ═══════════════════════════════════════
#  参数
# ═══════════════════════════════════════

STOCK_RISK_PARAMS = {
    "max_risk_per_trade": 0.02,       # 单笔最多亏总资金 2%
    "max_position_pct": 0.30,         # 单只股票最多占 30% 仓位
    "max_total_positions": 5,         # 最多同时持有 5 只
    "default_stop_atr_mult": 2.0,     # 止损 = 入场价 - 2×ATR
    "min_risk_reward": 2.0,           # 最低风报比 2:1
    "max_daily_loss_pct": 0.05,       # 日亏损超 5% 暂停交易
    "commission": 0.0003,             # 万三佣金
    "stamp_tax_sell": 0.001,          # 卖出印花税 千一（仅卖出）
    "slippage": 0.001,                # 滑点 0.1%
    "min_lot": 100,                   # 最小交易单位 100股/手
}


# ═══════════════════════════════════════
#  涨跌停 & 板块规则
# ═══════════════════════════════════════

def get_price_limit_pct(code: str) -> float:
    """根据股票代码返回涨跌停幅度

    主板(60/00): ±10%
    科创板(688): ±20%
    创业板(300/301): ±20%
    北交所(8): ±30%
    ST(含ST): ±5%
    """
    code = str(code)
    # ST 股票
    if "ST" in code.upper():
        return 0.05
    # 科创板
    if code.startswith("688"):
        return 0.20
    # 创业板
    if code.startswith("300") or code.startswith("301"):
        return 0.20
    # 北交所
    if code.startswith("8"):
        return 0.30
    # 主板（含深市 00xxxx）
    return 0.10


def check_price_limit(code: str, price: float, prev_close: float) -> str:
    """检查是否触及涨跌停

    Returns: 'normal' | 'limit_up' | 'limit_down'
    """
    limit_pct = get_price_limit_pct(code)
    change = (price - prev_close) / prev_close if prev_close > 0 else 0

    if change >= limit_pct * 0.995:
        return "limit_up"
    elif change <= -limit_pct * 0.995:
        return "limit_down"
    return "normal"


def check_t1_sellable(buy_date: str, today: str) -> bool:
    """T+1 检查：买入次日（含）才可卖出

    Args:
        buy_date: 买入日期 'YYYY-MM-DD'
        today: 当前日期 'YYYY-MM-DD'

    Returns:
        True = 可以卖出, False = T+1 锁定中
    """
    return today > buy_date


# ═══════════════════════════════════════
#  ATR 计算
# ═══════════════════════════════════════

def calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    """从日K线DataFrame计算最新ATR

    df 需含列: high, low, close

    Returns:
        最新 ATR 值（float）
    """
    if len(df) < period + 1:
        return 0.0

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder's smoothed ATR
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()

    return round(float(atr.iloc[-1]), 4)


# ═══════════════════════════════════════
#  止损 & 仓位计算
# ═══════════════════════════════════════

@dataclass
class PositionPlan:
    """单笔仓位计划"""
    entry_price: float
    stop_loss: float
    atr: float
    atr_mult: float
    risk_per_share: float        # 每股风险（= 入场价 - 止损价）
    max_shares: int               # 风控允许的最大股数（已取整到100）
    target_amount: float          # 建议买入金额
    position_pct: float           # 占总资金比例
    risk_amount: float            # 本笔最大亏损金额

    def __repr__(self):
        return (f"PositionPlan(入场{self.entry_price:.2f}, "
                f"止损{self.stop_loss:.2f}, "
                f"{self.max_shares}股, "
                f"¥{self.target_amount:,.0f}, "
                f"{self.position_pct:.1%}仓位)")


def calc_stop_loss(entry_price: float, atr: float, atr_mult: float = 2.0) -> float:
    """基于ATR计算止损价

    Args:
        entry_price: 入场价
        atr: 平均真实波幅
        atr_mult: ATR乘数（默认2倍）

    Returns:
        止损价（保留2位小数）
    """
    return round(entry_price - atr * atr_mult, 2)


def calc_take_profit(entry_price: float, stop_loss: float,
                     risk_reward: float = 2.0) -> dict:
    """计算多个止盈目标

    Returns:
        {"tp1": price, "tp2": price, "tp3": price}
    """
    risk = entry_price - stop_loss
    if risk <= 0:
        return {"tp1": entry_price, "tp2": entry_price, "tp3": entry_price}

    return {
        "tp1": round(entry_price + risk * 1.0, 2),   # 1:1 减半仓
        "tp2": round(entry_price + risk * 2.0, 2),   # 2:1 再减半
        "tp3": round(entry_price + risk * 3.0, 2),   # 3:1 清仓
    }


def calc_position_size(
    capital: float,
    entry_price: float,
    stop_loss: float,
    max_risk_pct: float = 0.02,
    max_position_pct: float = 0.30,
    min_lot: int = 100,
) -> PositionPlan:
    """固定比例风险法计算仓位

    公式: 股数 = 总资金 × 风险% / (入场价 - 止损价)

    Args:
        capital: 总资金
        entry_price: 入场价
        stop_loss: 止损价
        max_risk_pct: 单笔最大风险比例
        max_position_pct: 单票最大仓位
        min_lot: 最小交易单位（A股=100）

    Returns:
        PositionPlan
    """
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share <= 0:
        risk_per_share = entry_price * 0.02  # fallback: 2% of price

    # 风控允许的最大亏损金额
    max_risk_amount = capital * max_risk_pct

    # 根据风险计算股数
    raw_shares = max_risk_amount / risk_per_share

    # 仓位上限约束
    max_position_amount = capital * max_position_pct
    shares_by_position = max_position_amount / entry_price

    # 取两者的较小值
    shares = min(raw_shares, shares_by_position)

    # 取整到 lot 的倍数
    lots = max(1, int(shares / min_lot))
    final_shares = lots * min_lot

    target_amount = final_shares * entry_price
    actual_risk = final_shares * risk_per_share
    position_pct = target_amount / capital if capital > 0 else 0

    return PositionPlan(
        entry_price=entry_price,
        stop_loss=stop_loss,
        atr=0.0,                    # 由调用方填入
        atr_mult=0.0,
        risk_per_share=risk_per_share,
        max_shares=final_shares,
        target_amount=round(target_amount, 2),
        position_pct=round(position_pct, 4),
        risk_amount=round(actual_risk, 2),
    )


# ═══════════════════════════════════════
#  交易时间 & 日历
# ═══════════════════════════════════════

def is_trading_time() -> bool:
    """判断当前是否在 A 股连续竞价时段

    A股交易时间:
    - 9:30-11:30
    - 13:00-15:00
    """
    now = datetime.now()
    # 周末
    if now.weekday() >= 5:
        return False

    t = now.time()
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)

    return (morning_start <= t <= morning_end) or \
           (afternoon_start <= t <= afternoon_end)


def is_trading_day(date_str: str = None) -> bool:
    """简单判断是否为交易日（排除周末，不含节假日）

    注：精确判断需要交易日历，这里只排除周末。
    A股节假日（春节、国庆等）需额外处理。
    """
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        dt = datetime.now()
    return dt.weekday() < 5


# ═══════════════════════════════════════
#  综合风控检查
# ═══════════════════════════════════════

@dataclass
class RiskCheckResult:
    """风控检查结果"""
    allowed: bool
    reason: str = ""
    level: str = "info"              # info | warning | critical
    details: dict = field(default_factory=dict)


def check_stock_trade(
    code: str,
    action: str,                     # 'buy' | 'sell'
    price: float,
    prev_close: float,
    capital: float,
    current_positions: dict,         # {code: {"shares": int, "buy_date": str, "cost": float}}
    daily_loss_total: float = 0.0,
) -> RiskCheckResult:
    """综合风控入口

    对单笔交易做所有规则检查，返回是否放行。
    """
    # 1. 涨跌停
    limit_status = check_price_limit(code, price, prev_close)
    if action == "buy" and limit_status == "limit_up":
        return RiskCheckResult(False, f"{code} 涨停封板，无法买入", "critical")
    if action == "sell" and limit_status == "limit_down":
        return RiskCheckResult(False, f"{code} 跌停封板，无法卖出", "critical")

    # 2. 仓位数上限（买时检查）
    if action == "buy":
        existing = len(current_positions)
        if existing >= STOCK_RISK_PARAMS["max_total_positions"]:
            return RiskCheckResult(
                False,
                f"已达最大持仓数 {STOCK_RISK_PARAMS['max_total_positions']}",
                "critical",
            )

    # 3. T+1 卖出限制
    if action == "sell" and code in current_positions:
        pos = current_positions[code]
        buy_date = pos.get("buy_date", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if not check_t1_sellable(buy_date, today):
            return RiskCheckResult(False, f"{code} T+1锁定中，买入日{buy_date}，今日不可卖", "critical")

    # 4. 日内亏损熔断
    if daily_loss_total > 0:
        loss_pct = daily_loss_total / capital if capital > 0 else 0
        if loss_pct > STOCK_RISK_PARAMS["max_daily_loss_pct"]:
            return RiskCheckResult(
                False,
                f"日内亏损 {loss_pct:.1%}，超过熔断线 {STOCK_RISK_PARAMS['max_daily_loss_pct']:.0%}",
                "critical",
            )

    # 5. 涨停板附近警告（追高风险）
    if action == "buy":
        change_pct = (price - prev_close) / prev_close if prev_close > 0 else 0
        limit_pct = get_price_limit_pct(code)
        if change_pct > limit_pct * 0.85:
            return RiskCheckResult(
                True,
                f"涨幅 {change_pct:.1%}，接近涨停 {limit_pct:.0%}，追高风险较大",
                "warning",
                {"change_pct": change_pct},
            )

    price_limit_pct = get_price_limit_pct(code)
    return RiskCheckResult(
        True,
        "风控通过",
        "info",
        {
            "price_limit_pct": price_limit_pct,
            "limit_status": limit_status,
        },
    )
