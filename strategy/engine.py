"""策略调度引擎 — 信号 → 建议 → 风控 → 订单"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("quant.strategy")


@dataclass
class TradeAdvice:
    """统一交易建议结构"""
    code: str
    name: str
    action: str              # buy / sell / hold / dca
    amount: float
    reason: str
    confidence: int = 0       # 0-100
    priority: int = 0         # 越高越优先
    risk_ok: bool = True
    risk_detail: str = ""
    metadata: dict = field(default_factory=dict)


# ETF → 基金代码映射
ETF_TO_FUND = {
    "512480": "014319",  # 半导体ETF → 德邦半导体
    "515050": "007817",  # 通信ETF → 国泰通信
    "515070": "011839",  # AI ETF → 天弘AI
    "159611": "016185",  # 电力ETF → 广发电力
    "513100": "005698",  # 纳指ETF → 华夏全球
    "513500": "017641",  # 标普500ETF → 摩根标普500
}


def signals_to_advices(signals: list[dict], portfolio: dict, total_assets: float) -> list[TradeAdvice]:
    """将 ETF 轮动信号转为具体操作建议

    Args:
        signals: generate_signals() 返回的信号列表
        portfolio: calc_portfolio() 返回的持仓数据
        total_assets: 总资产

    Returns:
        按优先级排序的建议列表
    """
    advices = []

    # 按信号操作分类
    for s in signals:
        action = s.get("操作", s.get("action", "观望"))
        if action == "观望":
            continue

        etf_code = s.get("code", "")

        # ETF 映射到基金
        fund_code = ETF_TO_FUND.get(etf_code, "")

        # 找对应基金的当前持仓
        current_value = 0.0
        current_pl_pct = 0.0
        fund_name = s.get("name", "")
        for f in portfolio.get("基金", []):
            if f["code"] == fund_code:
                current_value = f.get("市值", 0)
                current_pl_pct = f.get("盈亏率", 0)
                fund_name = f["name"]
                break

        # 金额建议
        if action == "买入":
            amount = min(total_assets * 0.10, 3000)
            amount = max(amount, 100)
        elif action == "卖出":
            if current_value <= 0:
                continue
            amount = current_value * 0.5
        else:
            continue

        if amount <= 0:
            continue

        advices.append(TradeAdvice(
            code=fund_code or etf_code,
            name=fund_name or s.get("name", ""),
            action="buy" if action == "买入" else "sell",
            amount=round(amount, 2),
            reason=s.get("理由", s.get("reason", "")),
            confidence=min(int(abs(s.get("评分", s.get("score", 0))) * 200), 100),
            priority=2 if action == "买入" else 1,
            metadata={"etf_code": etf_code, "signal_score": s.get("评分", 0)},
        ))

    advices.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
    return advices


def advices_with_risk(advices: list[TradeAdvice], portfolio: dict, cash: float) -> list[TradeAdvice]:
    """对所有建议执行风控检查"""
    from risk_engine import evaluate as risk_eval

    total = portfolio.get("总资产", 0)
    fund_val = portfolio.get("基金市值", 0)
    today_pl = portfolio.get("总盈亏率", 0)

    for a in advices:
        current_val = 0.0
        current_pl = 0.0
        for f in portfolio.get("基金", []):
            if f["code"] == a.code:
                current_val = f.get("市值", 0)
                current_pl = f.get("盈亏率", 0)
                break

        decision = risk_eval(
            code=a.code, action=a.action, amount=a.amount,
            current_value=current_val, total_assets=total,
            fund_value=fund_val, cash=cash,
            today_loss_pct=abs(today_pl) if today_pl < 0 else 0,
            current_pl_pct=current_pl,
        )
        a.risk_ok = decision.allowed
        a.risk_detail = decision.reason

    return advices
