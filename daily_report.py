"""每日复盘日报 — 收盘自动生成

生成内容：
- 今日收益
- 持仓变动
- 信号变化
- 风控事件
- 策略建议
- 待确认申购
- AI 摘要（可选）
- 数据质量
"""

import logging
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("quant.daily")


@dataclass
class DailyReport:
    date: str = ""
    # 收益
    total_assets: float = 0.0
    fund_value: float = 0.0
    cash: float = 0.0
    today_pl: float = 0.0
    today_pl_pct: float = 0.0
    estimated_pl: float = 0.0     # ETF 估算

    # 持仓
    total_funds: int = 0
    top_gainer: str = ""
    top_gainer_pl: float = 0.0
    top_loser: str = ""
    top_loser_pl: float = 0.0

    # 信号
    signal_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    signal_summary: str = ""

    # 建议
    advices: list = field(default_factory=list)

    # 风控
    risk_events: list = field(default_factory=list)
    circuit_status: str = "正常"

    # 待确认
    pending_total: float = 0.0
    pending_items: list = field(default_factory=list)

    # 数据质量
    data_quality: int = 100
    data_warnings: list = field(default_factory=list)

    # 系统
    generated_at: str = ""


def generate(date: str = None) -> DailyReport:
    """生成每日复盘日报"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    report = DailyReport(date=date, generated_at=datetime.now().isoformat())

    try:
        _fill_portfolio(report)
    except Exception as e:
        logger.warning(f"日报-持仓: {e}")

    try:
        _fill_signals(report)
    except Exception as e:
        logger.warning(f"日报-信号: {e}")

    try:
        _fill_advices(report)
    except Exception as e:
        logger.warning(f"日报-建议: {e}")

    try:
        _fill_risk(report)
    except Exception as e:
        logger.warning(f"日报-风控: {e}")

    try:
        _fill_pending(report)
    except Exception as e:
        logger.warning(f"日报-待确认: {e}")

    try:
        _fill_estimate(report)
    except Exception as e:
        logger.warning(f"日报-估算: {e}")

    try:
        _fill_quality(report)
    except Exception as e:
        logger.warning(f"日报-质量: {e}")

    return report


def _fill_portfolio(report: DailyReport):
    from portfolio import calc_portfolio
    pf = calc_portfolio()
    report.total_assets = pf.get("总资产", 0)
    report.fund_value = pf.get("基金市值", 0)
    report.cash = pf.get("余额宝", 0)
    report.today_pl = pf.get("总盈亏", 0)
    report.today_pl_pct = pf.get("总盈亏率", 0)

    funds = [f for f in pf.get("基金", []) if f.get("市值", 0) > 0]
    report.total_funds = len(funds)
    if funds:
        sorted_by_pl = sorted(funds, key=lambda x: x.get("盈亏", 0), reverse=True)
        report.top_gainer = sorted_by_pl[0]["name"]
        report.top_gainer_pl = sorted_by_pl[0]["盈亏"]
        report.top_loser = sorted_by_pl[-1]["name"]
        report.top_loser_pl = sorted_by_pl[-1]["盈亏"]


def _fill_signals(report: DailyReport):
    from signals import generate_signals
    sigs = generate_signals(days=60)
    signals = sigs.get("信号", [])
    report.signal_count = len(signals)
    report.buy_count = sum(1 for s in signals if s.get("操作") == "买入")
    report.sell_count = sum(1 for s in signals if s.get("操作") == "卖出")
    report.signal_summary = sigs.get("综合建议", "")


def _fill_advices(report: DailyReport):
    from strategy.engine import signals_to_advices, advices_with_risk
    from signals import generate_signals
    from portfolio import calc_portfolio

    sigs = generate_signals(days=60)
    pf = calc_portfolio()
    advices = signals_to_advices(sigs.get("信号", []), pf, pf.get("总资产", 0))
    advices = advices_with_risk(advices, pf, pf.get("余额宝", 0))

    report.advices = [
        {
            "code": a.code, "name": a.name, "action": a.action,
            "amount": a.amount, "confidence": a.confidence,
            "risk_ok": a.risk_ok, "reason": a.reason,
        }
        for a in advices
    ]


def _fill_risk(report: DailyReport):
    from risk_engine import status as risk_status, is_closed
    s = risk_status()
    report.circuit_status = "正常" if is_closed() else f"熔断: {s.get('reason', '未知')}"

    if not is_closed():
        report.risk_events.append({
            "type": "熔断",
            "detail": s.get("reason", ""),
            "time": s.get("opened_at", ""),
        })


def _fill_pending(report: DailyReport):
    from db import get_pending_buys
    from config import FUNDS
    pending = get_pending_buys()
    report.pending_total = sum(
        v.get("amount", 0) if isinstance(v, dict) else v for v in pending.values()
    )
    report.pending_items = [
        {
            "code": k,
            "name": FUNDS.get(k, {}).get("name", k),
            "amount": v.get("amount", 0) if isinstance(v, dict) else v,
        }
        for k, v in pending.items()
    ]


def _fill_estimate(report: DailyReport):
    """ETF 估算今日收益"""
    try:
        # 调用 server.py 里的估算逻辑
        import urllib.request, json
        url = "http://localhost:8000/api/estimate/daily"
        resp = urllib.request.urlopen(url, timeout=10)
        data = json.loads(resp.read())
        report.estimated_pl = data.get("total_est", 0)
    except Exception:
        pass


def _fill_quality(report: DailyReport):
    from validators import validate_holdings
    from portfolio import calc_portfolio
    pf = calc_portfolio()
    q = validate_holdings(pf)
    report.data_quality = q.quality
    if q.details != "持仓数据正常":
        report.data_warnings.append(q.details)


# ═══════════════════ 格式化输出 ═══════════════════

def format_text(report: DailyReport) -> str:
    """纯文本日报"""
    lines = []
    lines.append("=" * 55)
    lines.append(f"  📊 AI Quant 每日复盘  {report.date}")
    lines.append("=" * 55)
    lines.append("")
    lines.append(f"  💰 总资产: ¥{report.total_assets:,.0f}")
    lines.append(f"     基金:   ¥{report.fund_value:,.0f}")
    lines.append(f"     余额宝: ¥{report.cash:,.0f}")
    pl_tag = "📈" if report.today_pl >= 0 else "📉"
    lines.append(f"  {pl_tag} 累计盈亏: {report.today_pl:+,.0f} ({report.today_pl_pct:+.2f}%)")
    if report.estimated_pl:
        est_tag = "+" if report.estimated_pl >= 0 else ""
        lines.append(f"  📡 ETF估算今日: {est_tag}{report.estimated_pl:,.0f}元")
    lines.append("")

    lines.append(f"  🏆 最佳: {report.top_gainer} +{report.top_gainer_pl:,.0f}")
    lines.append(f"  📉 最差: {report.top_loser} {report.top_loser_pl:+,.0f}")
    lines.append("")

    lines.append(f"  ⚡ 信号: {report.signal_count}条 (买{report.buy_count} 卖{report.sell_count})")
    if report.signal_summary:
        lines.append(f"      {report.signal_summary[:80]}")
    lines.append("")

    if report.advices:
        lines.append("  📋 操作建议:")
        for a in report.advices:
            icon = "✅" if a["risk_ok"] else "❌"
            act = "买入" if a["action"] == "buy" else "卖出"
            lines.append(f"     {icon} {act} {a['name']} ¥{a['amount']:,.0f} ({a['confidence']}%)")
    lines.append("")

    lines.append(f"  🛡️ 风控: {report.circuit_status}")
    if report.pending_total > 0:
        lines.append(f"  ⏳ 待确认: {report.pending_total:,.0f}元")
        for p in report.pending_items:
            lines.append(f"     {p['name']} ¥{p['amount']:,.0f}")
    lines.append("")

    lines.append(f"  📊 数据质量: {report.data_quality}/100")
    if report.data_warnings:
        for w in report.data_warnings:
            lines.append(f"     ⚠️ {w}")
    lines.append("")
    lines.append(f"  生成时间: {report.generated_at}")
    lines.append("=" * 55)

    return "\n".join(lines)


def print_report(report: DailyReport = None):
    """打印日报到终端"""
    if report is None:
        report = generate()
    print(format_text(report))


# ═══════════════════ CLI ═══════════════════

if __name__ == "__main__":
    print_report()
