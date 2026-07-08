"""基金持仓监控 — 每日自动扫描止损/异动"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("quant.fund_monitor")


@dataclass
class FundAlert:
    code: str
    name: str
    level: str           # "info" | "watch" | "warn" | "critical"
    category: str        # "drawdown" | "consecutive_down" | "daily_crash" | "stale_nav"
    message: str
    detail: dict = field(default_factory=dict)


# ── 阈值配置 ──

THRESHOLDS = {
    "drawdown": {"watch": -3.0, "warn": -5.0, "critical": -8.0},      # 累计亏损%
    "consecutive_down": {"watch": 3, "warn": 5, "critical": 7},         # 连续下跌天数
    "daily_crash": {"watch": -2.0, "warn": -4.0, "critical": -6.0},    # 单日跌幅%
    "stale_nav": {"watch": 2, "warn": 4, "critical": 7},               # 净值过期天数(QDII放宽)
}


def _level(value: float, thresholds: dict) -> str:
    """根据阈值判断告警等级"""
    if value <= thresholds.get("critical", -999):
        return "critical"
    elif value <= thresholds.get("warn", -999):
        return "warn"
    elif value <= thresholds.get("watch", -999):
        return "watch"
    return "info"


def _level_ge(value: int, thresholds: dict) -> str:
    """连续天数版本（越大越严重）"""
    if value >= thresholds.get("critical", 999):
        return "critical"
    elif value >= thresholds.get("warn", 999):
        return "warn"
    elif value >= thresholds.get("watch", 999):
        return "watch"
    return "info"


def scan_all() -> list[FundAlert]:
    """扫描所有持仓基金，返回告警列表（按严重度排序）

    从 production.db 拉取持仓和最新净值，计算：
    1. 累计盈亏率 → 是否触发止损线
    2. 连续下跌天数 → 是否持续走弱
    3. 单日跌幅 → 是否暴跌
    4. 净值新鲜度 → 是否过期
    """
    alerts = []

    try:
        from portfolio import calc_portfolio
        from db import get_holdings, get_known_navs
        from config import FUNDS
        from data import get_fund_nav
    except Exception as e:
        logger.error(f"基金监控初始化失败: {e}")
        return alerts

    pf = calc_portfolio()
    funds = pf.get("基金", [])

    for f in funds:
        code = f["code"]
        name = f["name"]
        value = f.get("市值", 0)
        pl_pct = f.get("盈亏率", 0)
        fund_type = FUNDS.get(code, {}).get("type", "")

        if value <= 0:
            continue

        # ── 1. 累计亏损 ──
        if pl_pct < 0:
            lv = _level(pl_pct, THRESHOLDS["drawdown"])
            if lv != "info":
                alerts.append(FundAlert(
                    code=code, name=name, level=lv, category="drawdown",
                    message=f"{name} 累计亏损 {pl_pct:+.1f}%，触发{lv}线",
                    detail={"pl_pct": pl_pct, "threshold": THRESHOLDS["drawdown"][lv]},
                ))

        # ── 2. 连续下跌天数 ──
        try:
            df = get_fund_nav(code, days=20)
            if df is not None and not df.empty and "日增长率" in df.columns:
                recent = df["日增长率"].tail(10).values
                consecutive = 0
                for r in reversed(recent):
                    r = float(r) if r and str(r) != 'nan' else 0
                    if r < 0:
                        consecutive += 1
                    else:
                        break
                lv = _level_ge(consecutive, THRESHOLDS["consecutive_down"])
                if lv != "info":
                    alerts.append(FundAlert(
                        code=code, name=name, level=lv, category="consecutive_down",
                        message=f"{name} 连续下跌 {consecutive} 天",
                        detail={"consecutive_days": consecutive},
                    ))
        except Exception:
            pass

        # ── 3. 单日暴跌 ──
        try:
            daily_change_str = f.get("涨跌", "0")
            daily_change = float(str(daily_change_str).replace("%", "").replace("+", ""))
            lv = _level(daily_change, THRESHOLDS["daily_crash"])
            if lv != "info":
                alerts.append(FundAlert(
                    code=code, name=name, level=lv, category="daily_crash",
                    message=f"{name} 单日跌幅 {daily_change:+.1f}%",
                    detail={"daily_change": daily_change},
                ))
        except Exception:
            pass

        # ── 4. 净值新鲜度 ──
        try:
            from data import get_fund_nav as _nav
            df = _nav(code, days=5)
            if df is not None and not df.empty:
                last_date = df["净值日期"].iloc[-1]
                if hasattr(last_date, "strftime"):
                    days_ago = (datetime.now() - pd_to_datetime(last_date)).days
                else:
                    days_ago = (datetime.now() - datetime.strptime(str(last_date)[:10], "%Y-%m-%d")).days
                max_stale = 2 if fund_type == "QDII" else 1
                if days_ago > max_stale:
                    lv = "watch" if days_ago <= 4 else "warn"
                    alerts.append(FundAlert(
                        code=code, name=name, level=lv, category="stale_nav",
                        message=f"{name} 净值滞后 {days_ago} 天（{fund_type}允许{max_stale}天）",
                        detail={"days_ago": days_ago, "max_allowed": max_stale},
                    ))
        except Exception:
            pass

    # 按严重度排序: critical > warn > watch > info
    severity_order = {"critical": 0, "warn": 1, "watch": 2, "info": 3}
    alerts.sort(key=lambda a: severity_order.get(a.level, 99))

    return alerts


def pd_to_datetime(val) -> datetime:
    """安全转 datetime"""
    import pandas as pd
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()
    if isinstance(val, datetime):
        return val
    return datetime.strptime(str(val)[:10], "%Y-%m-%d")


def get_summary() -> dict:
    """获取监控摘要（供 API 使用）"""
    alerts = scan_all()
    return {
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a.level == "critical"),
        "warn": sum(1 for a in alerts if a.level == "warn"),
        "watch": sum(1 for a in alerts if a.level == "watch"),
        "alerts": [
            {
                "code": a.code, "name": a.name, "level": a.level,
                "category": a.category, "message": a.message,
                "detail": a.detail,
            }
            for a in alerts
        ],
        "scan_time": datetime.now().isoformat(),
    }
