"""市场时钟 — 判断交易时段、截止时间、休市日"""

import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger("quant.runtime.clock")

# ── 交易时间定义 ──
MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)
CUTOFF_TIME = time(15, 0)          # 当日申购/赎回截止
PRE_CLOSE_LOCK = timedelta(minutes=5)  # 收盘前锁定窗口


def is_trading_day(dt: datetime = None) -> bool:
    """是否交易日（简化：排除周六日）"""
    if dt is None:
        dt = datetime.now()
    return dt.weekday() < 5  # 0=Mon, 6=Sun


def is_market_open(dt: datetime = None) -> bool:
    """当前是否在交易时段内"""
    if dt is None:
        dt = datetime.now()
    if not is_trading_day(dt):
        return False
    t = dt.time()
    return (MORNING_OPEN <= t <= MORNING_CLOSE) or (AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE)


def can_place_order(dt: datetime = None) -> bool:
    """当前是否允许下单（考虑收盘前锁定）"""
    if dt is None:
        dt = datetime.now()
    if not is_market_open(dt):
        return False
    # 收盘前 N 分钟锁定
    cutoff = datetime.combine(dt.date(), AFTERNOON_CLOSE)
    if dt >= cutoff - PRE_CLOSE_LOCK:
        return False
    return True


def seconds_until_open() -> float:
    """距离下一个开盘还有多少秒"""
    now = datetime.now()
    if not is_trading_day(now):
        # 下周一 9:30
        days_until_mon = (7 - now.weekday()) % 7
        if days_until_mon == 0:
            days_until_mon = 1
        next_open = datetime.combine(
            now.date() + timedelta(days=days_until_mon), MORNING_OPEN
        )
        return (next_open - now).total_seconds()

    t = now.time()
    if t < MORNING_OPEN:
        next_open = datetime.combine(now.date(), MORNING_OPEN)
    elif t < AFTERNOON_OPEN and t > MORNING_CLOSE:
        next_open = datetime.combine(now.date(), AFTERNOON_OPEN)
    else:
        # 明天
        next_day = now + timedelta(days=1)
        while not is_trading_day(next_day):
            next_day += timedelta(days=1)
        next_open = datetime.combine(next_day.date(), MORNING_OPEN)

    return (next_open - now).total_seconds()


def market_phase() -> str:
    """当前市场阶段"""
    if not is_trading_day():
        return "休市"
    t = datetime.now().time()
    if t < MORNING_OPEN:
        return "盘前"
    if MORNING_OPEN <= t <= MORNING_CLOSE:
        return "早盘"
    if MORNING_CLOSE < t < AFTERNOON_OPEN:
        return "午休"
    if AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE:
        return "午盘"
    if AFTERNOON_CLOSE < t <= time(20, 0):
        return "收盘后(净值待发布)"
    return "夜间"
