"""
资金日历：待结算、定投、账单等事件时间线
"""
from datetime import datetime, timedelta
from calendar import monthrange
from config import FUNDS, DCA_SCHEDULE
from portfolio import PENDING_BUYS, CASH_YUEBAO


def get_upcoming_events(days: int = 30) -> list:
    """生成未来 events 列表，按日期排序

    Returns:
        [{"date": "05-18", "desc": "...", "amount": float, "type": "in/out/neutral"}, ...]
    """
    today = datetime.now()
    events = []

    # ── PENDING_BUYS 预计到账 ──
    for code, entry in PENDING_BUYS.items():
        amount = entry["amount"] if isinstance(entry, dict) else entry
        buy_date = entry.get("date", "") if isinstance(entry, dict) else ""
        name = FUNDS.get(code, {}).get("name", code)
        if buy_date:
            try:
                dt = datetime.strptime(buy_date, "%Y-%m-%d")
                # T+1 估算到账（跳过周末）
                settle = dt + timedelta(days=1)
                while settle.weekday() >= 5:  # 跳过周六日
                    settle += timedelta(days=1)
                events.append({
                    "date": settle.strftime("%m-%d"),
                    "desc": f"份额到账: {name}",
                    "amount": -amount,
                    "type": "pending_settle",
                })
            except ValueError:
                pass

    # ── 定投扣款（每日）──
    for code, dca_amount in DCA_SCHEDULE.items():
        name = FUNDS.get(code, {}).get("name", code)
        for i in range(1, days + 1):
            day = today + timedelta(days=i)
            if day.weekday() < 5:  # 工作日
                events.append({
                    "date": day.strftime("%m-%d"),
                    "desc": f"定投: {name}",
                    "amount": -dca_amount,
                    "type": "dca",
                })

    # ── 固定账单 ──
    current_year = today.year
    current_month = today.month

    # 话费 100（每月1号）
    next_month1 = current_month if today.day < 1 else current_month + 1
    next_year1 = current_year if next_month1 <= 12 else current_year + 1
    next_month1 = ((next_month1 - 1) % 12) + 1
    bill_date = datetime(next_year1, next_month1, 1)
    if bill_date <= today + timedelta(days=days):
        events.append({
            "date": bill_date.strftime("%m-%d"),
            "desc": "话费",
            "amount": -100,
            "type": "bill",
        })

    # 房租 1,880（每月底）
    for i in range(0, 2):
        m = current_month + i
        y = current_year
        if m > 12:
            m -= 12
            y += 1
        from calendar import monthrange
        last_day = monthrange(y, m)[1]
        rent_date = datetime(y, m, last_day)
        if today < rent_date <= today + timedelta(days=days):
            events.append({
                "date": rent_date.strftime("%m-%d"),
                "desc": "房租",
                "amount": -1880,
                "type": "bill",
            })

    # 工资（每月15号）
    for i in range(0, 2):
        m = current_month + i
        y = current_year
        if m > 12:
            m -= 12
            y += 1
        salary_date = datetime(y, m, 15)
        if today < salary_date <= today + timedelta(days=days):
            # 5月特殊：5,000
            amount = 5000 if salary_date.month == 5 and salary_date.year == 2026 else 4200
            events.append({
                "date": salary_date.strftime("%m-%d"),
                "desc": "工资" + ("(3倍)" if amount == 5000 else ""),
                "amount": amount,
                "type": "salary",
            })

    # 排序
    events.sort(key=lambda e: (e["date"], e["type"]))
    return events


def get_event_summary(events: list) -> dict:
    """汇总：未来N天净现金流"""
    total_in = sum(e["amount"] for e in events if e["amount"] > 0)
    total_out = sum(e["amount"] for e in events if e["amount"] < 0)
    min_balance = CASH_YUEBAO + total_in + total_out

    # 计算每日最低余额
    balance = CASH_YUEBAO
    min_b = balance
    for e in sorted(events, key=lambda x: x["date"]):
        balance += e["amount"]
        min_b = min(min_b, balance)

    return {
        "总流入": total_in,
        "总流出": abs(total_out),
        "当前余额宝": CASH_YUEBAO,
        "预计最低余额": min_b,
        "净现金流": total_in + total_out,
    }
