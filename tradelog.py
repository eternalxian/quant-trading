"""
交易日志：手动记录每一笔操作的"为什么"

数据存储: data/trades.json
"""
import json
import os
from datetime import datetime
from typing import Optional
from config import FUNDS
from portfolio import HOLDINGS, COST_BASIS, KNOWN_NAV
from data import DATA_DIR, get_fund_nav

TRADES_FILE = os.path.join(DATA_DIR, "trades.json")

# ── 操作类型 ──
ACTIONS = {
    "buy": "买入",
    "sell": "卖出",
    "dca": "定投",
    "switch_in": "转入",
    "switch_out": "转出",
    "dividend": "分红",
}


def _load_trades() -> list:
    """从 trades.json 加载所有交易记录"""
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_trades(trades: list):
    """保存交易记录到 trades.json"""
    try:
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [错误] 保存交易日志失败: {e}")


def add_trade(code: str, action: str, amount: float,
              reason: str = "", nav: float = None,
              date: str = None,
              auto_nav: bool = True) -> dict:
    """添加一条交易记录

    Args:
        code: 基金代码
        action: buy/sell/dca/switch_in/switch_out
        amount: 金额（正数）
        reason: 交易理由
        nav: 交易时的净值（可选）
        date: 交易日期，默认今天
        auto_nav: True时自动补上最新净值

    Returns:
        新增的交易记录 dict
    """
    """添加一条交易记录

    Args:
        code: 基金代码
        action: buy/sell/dca/switch_in/switch_out
        amount: 金额（正数）
        reason: 交易理由
        nav: 交易时的净值（可选）
        date: 交易日期，默认今天

    Returns:
        新增的交易记录 dict
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    if action not in ACTIONS:
        print(f"  未知操作: {action}，可用: {', '.join(ACTIONS.keys())}")
        return None

    trades = _load_trades()

    # 自动补净值（QDII用KNOWN_NAV优先）
    if nav is None and auto_nav and action in ("buy", "dca"):
        known = KNOWN_NAV.get(code)
        if known:
            nav = known
        else:
            try:
                df = get_fund_nav(code, days=5)
                if df is not None and not df.empty:
                    nav = float(df.iloc[-1]["单位净值"])
            except Exception:
                pass

    trade = {
        "id": _next_id(trades),
        "date": date,
        "time": datetime.now().strftime("%H:%M"),
        "code": code,
        "name": FUNDS.get(code, {}).get("name", code),
        "action": action,
        "action_cn": ACTIONS[action],
        "amount": round(amount, 2),
        "nav": nav,
        "reason": reason,
        "created_at": datetime.now().isoformat(),
    }

    trades.append(trade)
    _save_trades(trades)

    return trade


def _next_id(trades: list) -> int:
    """生成下一个交易ID"""
    if not trades:
        return 1
    return max(t["id"] for t in trades) + 1


def get_trades(code: str = None, action: str = None,
               limit: int = None) -> list:
    """查询交易记录

    Args:
        code: 筛选基金代码
        action: 筛选操作类型
        limit: 返回条数

    Returns:
        交易记录列表（按日期降序）
    """
    trades = _load_trades()
    if code:
        trades = [t for t in trades if t["code"] == code]
    if action:
        trades = [t for t in trades if t["action"] == action]
    trades.sort(key=lambda t: (t["date"], t.get("time", "")), reverse=True)
    if limit:
        trades = trades[:limit]
    return trades


def review_trades(code: str = None) -> list:
    """复盘交易：对比买入价和当前净值

    Returns:
        [{"id", "date", "code", "name", "action", "amount",
          "buy_nav", "current_nav", "change%", "pnl"}, ...]
    """
    trades = _load_trades()
    if code:
        trades = [t for t in trades if t["code"] == code]

    # 按日期升序，方便看买入后的走势
    trades.sort(key=lambda t: (t["date"], t.get("time", "")))

    from portfolio import KNOWN_NAV

    results = []
    for t in trades:
        if t["action"] not in ("buy", "dca"):
            continue
        if not t.get("nav"):
            continue

        # 查当前净值（含QDII覆盖）
        df = get_fund_nav(t["code"], days=5)
        if df is None or df.empty:
            continue
        current_nav = df.iloc[-1]["单位净值"]
        known = KNOWN_NAV.get(t["code"])
        if known and abs(current_nav - known) / max(current_nav, known) > 0.1:
            current_nav = known

        change = round((current_nav - t["nav"]) / t["nav"] * 100, 2)
        pnl = round(t["amount"] * change / 100, 2)

        results.append({
            "id": t["id"],
            "date": t["date"],
            "code": t["code"],
            "name": t["name"],
            "action": t["action_cn"],
            "amount": t["amount"],
            "buy_nav": t["nav"],
            "current_nav": current_nav,
            "change": change,
            "pnl": pnl,
            "reason": t.get("reason", ""),
        })

    return results


def get_trade_stats() -> dict:
    """交易统计

    Returns:
        {"总交易数": N, "总投入": X, "买入次数": N, ...}
    """
    trades = _load_trades()
    if not trades:
        return {}

    total_buy = sum(t["amount"] for t in trades
                    if t["action"] in ("buy", "dca"))
    total_sell = sum(t["amount"] for t in trades
                     if t["action"] == "sell")

    # 按基金统计
    by_fund = {}
    for t in trades:
        code = t["code"]
        if code not in by_fund:
            by_fund[code] = {"买入次数": 0, "买入金额": 0,
                             "卖出次数": 0, "卖出金额": 0}
        if t["action"] in ("buy", "dca"):
            by_fund[code]["买入次数"] += 1
            by_fund[code]["买入金额"] += t["amount"]
        elif t["action"] == "sell":
            by_fund[code]["卖出次数"] += 1
            by_fund[code]["卖出金额"] += t["amount"]

    return {
        "总交易数": len(trades),
        "总投入": round(total_buy, 2),
        "总卖出": round(total_sell, 2),
        "净投入": round(total_buy - total_sell, 2),
        "买入次数": sum(1 for t in trades if t["action"] in ("buy", "dca")),
        "卖出次数": sum(1 for t in trades if t["action"] == "sell"),
        "基金数": len(set(t["code"] for t in trades)),
        "按基金": by_fund,
    }


def print_trades(trades: list):
    """CLI 打印交易记录"""
    if not trades:
        print("\n暂无交易记录\n")
        return

    for t in trades:
        amount_str = f"{t['amount']:>8.1f}元" if t['amount'] else ""
        nav_str = f" @净值{t['nav']:.4f}" if t.get('nav') else ""
        reason_str = f"  — {t['reason']}" if t.get('reason') else ""
        print(f"  {t['date']}  {t['action_cn']:4s}  {t['name']}{nav_str}  {amount_str}{reason_str}")


def print_review(results: list):
    """CLI 打印复盘结果"""
    if not results:
        print("\n暂无可复盘的交易\n")
        return

    print(f"\n{'='*55}")
    print(f"  交易复盘")
    print(f"{'='*55}")
    print(f"  {'日期':>10} {'基金':18s} {'买入价':>6} {'当前价':>6} {'涨跌':>7} {'盈亏':>8} {'理由':14s}")
    print(f"  {'-'*55}")
    for r in results:
        name = r['name'][:16]
        change = r['change']
        marker = " 正确" if change > 0 else " 错误" if change < 0 else " 持平"
        print(f"  {r['date']:>10} {name:18s} {r['buy_nav']:>6.3f} {r['current_nav']:>6.3f} "
              f"{change:>+6.2f}% {r['pnl']:>+7.2f} {r['reason'][:12]:12s}{marker}")
    print(f"  {'-'*55}")

    # 统计
    correct = sum(1 for r in results if r['change'] > 0)
    wrong = sum(1 for r in results if r['change'] < 0)
    total_pnl = sum(r['pnl'] for r in results)
    print(f"  正确判断: {correct}  错误判断: {wrong}  合计盈亏: {total_pnl:+.2f}元")
    if correct + wrong > 0:
        print(f"  判断准确率: {correct/(correct+wrong)*100:.0f}%")
    print(f"\n{'='*55}\n")
