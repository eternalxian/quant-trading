"""
净值异动提醒

监测基金日涨跌幅超过阈值的异动，自动分析上下文：
- 行业/板块联动
- 同类基金对比
- 历史百分位
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data import get_fund_nav, get_all_funds_nav
from config import FUNDS

ALERT_THRESHOLD = 3.0  # 默认阈值 %


def check_nav_alerts(threshold: float = ALERT_THRESHOLD) -> list:
    """检查所有基金的净值异动

    Args:
        threshold: 异动阈值（百分比），默认 3%

    Returns:
        [{"code", "name", "change%", "nav", "prev_nav", "date",
          "type": "涨/跌", "severity": "正常/关注/警告"}, ...]
    """
    navs = get_all_funds_nav(days=10)
    alerts = []

    for code in FUNDS:
        df = navs.get(code)
        if df is None or df.empty or len(df) < 2:
            continue

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        nav_val = latest["单位净值"]
        prev_nav_val = prev["单位净值"]

        # 优先用 AKShare 的日增长率（更准确，不受 QDII NAV 延迟影响）
        if "日增长率" in df.columns:
            latest_growth = df.iloc[-1]["日增长率"]
            if pd.notna(latest_growth):
                change = round(float(latest_growth), 2)
            else:
                change = _calc_change(latest, prev, code)
        else:
            change = _calc_change(latest, prev, code)
        abs_change = abs(change)

        if abs_change < threshold:
            continue

        # 异动等级
        if abs_change >= 5:
            severity = "警告"
        elif abs_change >= 4:
            severity = "关注"
        else:
            severity = "正常"

        alerts.append({
            "code": code,
            "name": FUNDS[code]["name"],
            "change": change,
            "type": "涨" if change > 0 else "跌",
            "severity": severity,
            "nav": nav_val,
            "prev_nav": prev_nav_val,
            "date": datetime.now().strftime("%Y-%m-%d"),
        })

    # 按异动幅度排序
    alerts.sort(key=lambda a: abs(a["change"]), reverse=True)
    return alerts


def _calc_change(latest: pd.Series, prev: pd.Series, code: str = "") -> float:
    """计算前后两行的净值涨跌幅（不用 KNOWN_NAV，避免 QDII 假异动）"""
    nav = latest["单位净值"]
    prev_nav = prev["单位净值"]
    if prev_nav == 0:
        return 0
    return round((nav - prev_nav) / prev_nav * 100, 2)


def get_alert_context(alerts: list) -> list:
    """为异动补充上下文分析

    Args:
        alerts: check_nav_alerts() 的返回值

    Returns:
        在原数据基础上补充 context 字段
    """
    # 获取所有基金近20日涨幅分布
    all_returns = _get_all_fund_returns(days=60)

    for a in alerts:
        context_parts = []

        # 1. 历史百分位
        code = a["code"]
        if code in all_returns:
            hist = all_returns[code]
            if len(hist) > 20:
                pct = (hist > a["change"]).mean() * 100
                if pct < 5:
                    context_parts.append(f"近60日最大涨幅（百分位 {pct:.0f}%）")
                elif pct > 95:
                    context_parts.append(f"近60日最大跌幅（百分位 {pct:.0f}%）")
                elif pct < 20:
                    context_parts.append(f"较大涨幅（百分位 {pct:.0f}%）")
                elif pct > 80:
                    context_parts.append(f"较大跌幅（百分位 {pct:.0f}%）")
                else:
                    context_parts.append(f"正常波动范围（百分位 {pct:.0f}%）")

        # 2. 同类对比（同类型基金平均涨跌）
        same_type = _get_same_type_avg(code)
        if same_type is not None:
            context_parts.append(f"同类平均: {same_type:+.2f}%")

        # 3. 近10日趋势
        if code in all_returns and len(all_returns[code]) >= 10:
            recent = all_returns[code].tail(10)
            cum = round(((1 + recent / 100).prod() - 1) * 100, 2)
            context_parts.append(f"近10日累计: {cum:+.2f}%")

        a["context"] = " | ".join(context_parts) if context_parts else ""

    return alerts


def _get_all_fund_returns(days: int = 60) -> dict:
    """获取所有基金日收益率序列"""
    navs = get_all_funds_nav(days=days + 10)
    result = {}
    for code in FUNDS:
        df = navs.get(code)
        if df is None or df.empty or len(df) < 5:
            continue
        df = df.sort_values("净值日期")
        df["return"] = df["单位净值"].pct_change() * 100
        df = df.dropna(subset=["return"])
        if not df.empty:
            result[code] = df.set_index("净值日期")["return"]
    return result


def _get_same_type_avg(code: str) -> float:
    """计算同类型基金今日平均涨跌幅

    Args:
        code: 基金代码

    Returns:
        同类均值（%），无可比基金返回 None
    """
    fund_type = FUNDS.get(code, {}).get("type", "")
    if not fund_type:
        return None

    same_type_codes = [
        c for c, info in FUNDS.items()
        if info.get("type") == fund_type and c != code
    ]
    if not same_type_codes:
        return None

    navs = get_all_funds_nav(days=5)
    changes = []
    for c in same_type_codes:
        df = navs.get(c)
        if df is not None and len(df) >= 2:
            nav = df.iloc[-1]["单位净值"]
            prev = df.iloc[-2]["单位净值"]
            if prev > 0:
                chg = round((nav - prev) / prev * 100, 2)
                changes.append(chg)
    return round(np.mean(changes), 2) if changes else None


def get_daily_alert_summary() -> dict:
    """每日异动摘要

    Returns:
        {"date": str, "alerts": [...], "total": N, "max_change": float, "max_name": str}
    """
    alerts = check_nav_alerts(threshold=ALERT_THRESHOLD)
    alerts = get_alert_context(alerts)

    summary = {
        "日期": datetime.now().strftime("%Y-%m-%d"),
        "alerts": alerts,
        "总异动数": len(alerts),
    }

    if alerts:
        max_a = max(alerts, key=lambda a: abs(a["change"]))
        summary["最大异动"] = max_a["name"]
        summary["最大异动幅度"] = max_a["change"]

    return summary


def print_alerts(summary: dict):
    """CLI 打印异动提醒"""
    alerts = summary["alerts"]
    if not alerts:
        print(f"\n  [OK] {summary['日期']} 无净值异动（阈值 >{ALERT_THRESHOLD}%）\n")
        return

    print(f"\n{'='*55}")
    print(f"  净值异动提醒  {summary['日期']}  (>{ALERT_THRESHOLD}%)")
    print(f"{'='*55}")

    for a in alerts:
        severity_tag = {"警告": "!!!", "关注": " !!", "正常": "   "}[a["severity"]]
        print(f"  {severity_tag} {a['change']:>+7.2f}%  {a['name']}")
        if a.get("context"):
            print(f"          {a['context']}")

    print(f"  {'-'*35}")
    if summary.get("最大异动"):
        print(f"  最大异动: {summary['最大异动']} ({summary['最大异动幅度']:+.2f}%)")
    print(f"  共 {summary['总异动数']} 只基金异动")
    print(f"{'='*55}\n")
