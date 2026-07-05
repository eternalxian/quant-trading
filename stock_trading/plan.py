"""
交易计划生成器 — 信号 + 风控 → 可执行计划

输入一只股票 + 当前信号 + 账户参数，输出一份完整的交易计划。
"""

from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

from stock_trading.risk import (
    calc_atr, calc_stop_loss, calc_take_profit, calc_position_size,
    PositionPlan, check_stock_trade, get_price_limit_pct,
    STOCK_RISK_PARAMS,
)
from stock_trading.backtest import resolve_strategy


# ═══════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════

@dataclass
class TradingPlan:
    """个股交易计划"""
    # 基本信息
    code: str
    name: str
    generated_at: str                 # 生成时间
    signal_summary: str               # 信号摘要

    # 入场
    current_price: float
    entry_price_min: float            # 建议入场价下限
    entry_price_max: float            # 建议入场价上限
    entry_type: str                   # 'limit' | 'market'

    # 止损 & 止盈 (必须在有默认值的字段之前)
    stop_loss: float
    take_profit: dict                 # {tp1, tp2, tp3}

    # 风险评估
    risk_reward_ratio: float          # 风报比
    max_loss_amount: float            # 最大亏损金额
    max_loss_pct: float               # 占账户百分比

    # 仓位 (有默认值)
    position: object = None           # PositionPlan

    # 风控意见 (有默认值)
    risk_verdict: str = ""            # 风控判断：通过/警告/否决
    risk_notes: list = field(default_factory=list)

    # 交易参数 (有默认值)
    price_limit_pct: float = 0.10
    min_lot: int = 100

    def is_actionable(self) -> bool:
        """是否可执行"""
        return self.risk_verdict != "否决"


# ═══════════════════════════════════════
#  生成器
# ═══════════════════════════════════════

def generate_plan(
    code: str,
    name: str = "",
    df: pd.DataFrame = None,          # 日K线数据
    spot: dict = None,                # 实时行情 {"price", "change_pct", "prev_close"}
    signal: str = "hold",             # 当前信号 'buy' | 'sell' | 'hold'
    signal_score: float = 0.0,
    signal_reason: str = "",
    capital: float = 100_000,
    current_positions: dict = None,   # 当前持仓
    daily_loss_total: float = 0.0,
) -> TradingPlan | None:
    """生成交易计划

    Args:
        code: 股票代码
        name: 股票名称
        df: 日K线 DataFrame（用于计算 ATR）
        spot: 实时行情快照
        signal: 当前策略信号
        signal_score: 信号得分
        signal_reason: 信号原因
        capital: 账户总资金
        current_positions: 当前持仓 {code: {...}}
        daily_loss_total: 当日已实现亏损

    Returns:
        TradingPlan 或 None（信号不足时）
    """
    current_positions = current_positions or {}
    spot = spot or {}

    # ── 当前价格 ──
    current_price = spot.get("price", 0)
    prev_close = spot.get("prev_close", current_price)
    change_pct = spot.get("change_pct", 0)

    if current_price <= 0 and df is not None and len(df) > 0:
        current_price = float(df.iloc[-1]["close"])
        if len(df) >= 2:
            prev_close = float(df.iloc[-2]["close"])
        else:
            prev_close = current_price

    if current_price <= 0:
        return None

    # ── 价格限制 ──
    price_limit_pct = get_price_limit_pct(code)

    # ── ATR ──
    atr = 0.0
    if df is not None and len(df) >= 15:
        atr = calc_atr(df)

    if atr <= 0:
        atr = current_price * 0.03  # 默认 3% 波动

    # ── 止损价 ──
    atr_mult = STOCK_RISK_PARAMS["default_stop_atr_mult"]
    stop_loss = calc_stop_loss(current_price, atr, atr_mult)

    # ── 止盈目标 ──
    min_rr = STOCK_RISK_PARAMS["min_risk_reward"]
    take_profit = calc_take_profit(current_price, stop_loss, min_rr)

    # ── 仓位计算 ──
    position = calc_position_size(
        capital=capital,
        entry_price=current_price,
        stop_loss=stop_loss,
        max_risk_pct=STOCK_RISK_PARAMS["max_risk_per_trade"],
        max_position_pct=STOCK_RISK_PARAMS["max_position_pct"],
        min_lot=STOCK_RISK_PARAMS["min_lot"],
    )
    position.atr = atr
    position.atr_mult = atr_mult

    # ── 风控检查 ──
    risk_result = check_stock_trade(
        code=code,
        action="buy",
        price=current_price,
        prev_close=prev_close,
        capital=capital,
        current_positions=current_positions,
        daily_loss_total=daily_loss_total,
    )

    # ── 风报比 ──
    risk_per_share = current_price - stop_loss
    reward_per_share = take_profit["tp2"] - current_price
    rr_ratio = reward_per_share / risk_per_share if risk_per_share > 0 else 0

    # ── 入场价区间 ──
    # 在现价 ± 0.5 ATR 范围内限价买入
    entry_min = round(current_price - atr * 0.5, 2)
    entry_max = round(current_price + atr * 0.5, 2)

    # 不能低于跌停价
    limit_down = round(prev_close * (1 - price_limit_pct), 2)
    entry_min = max(entry_min, limit_down)

    # ── 信号摘要 ──
    signal_map = {"buy": "买入", "sell": "卖出", "hold": "观望"}
    signal_summary = signal_map.get(signal, signal)
    if signal_reason:
        signal_summary += f" — {signal_reason}"

    # ── 风控意见 ──
    risk_notes = []
    if not risk_result.allowed:
        risk_verdict = "否决"
        risk_notes.append(f"❌ {risk_result.reason}")
    elif risk_result.level == "warning":
        risk_verdict = "警告"
        risk_notes.append(f"⚠️ {risk_result.reason}")
    else:
        risk_verdict = "通过"

    # 额外提醒
    if signal != "buy":
        risk_notes.append(f"当前信号为「{signal_summary}」，不建议入场")
    if change_pct > 0.05:
        risk_notes.append(f"今日涨幅已达 {change_pct:+.2%}，追高风险较大")
    elif change_pct < -0.05:
        risk_notes.append(f"今日跌幅 {change_pct:+.2%}，可能是抄底机会也可能是接飞刀")

    # 止损比例检查
    stop_pct = (current_price - stop_loss) / current_price
    if stop_pct > 0.10:
        risk_notes.append(f"止损距离 {stop_pct:.1%} 偏大，考虑收紧ATR乘数或等待回调")

    # ── 组装 ──
    plan = TradingPlan(
        code=code,
        name=name,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        signal_summary=signal_summary,
        current_price=current_price,
        entry_price_min=entry_min,
        entry_price_max=entry_max,
        entry_type="limit" if signal == "buy" else "wait",
        position=position,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=round(rr_ratio, 2),
        max_loss_amount=round(position.max_shares * risk_per_share, 2),
        max_loss_pct=round(position.max_shares * risk_per_share / capital, 4) if capital > 0 else 0,
        risk_verdict=risk_verdict,
        risk_notes=risk_notes,
        price_limit_pct=price_limit_pct,
        min_lot=STOCK_RISK_PARAMS["min_lot"],
    )

    return plan


# ═══════════════════════════════════════
#  打印输出
# ═══════════════════════════════════════

def print_trading_plan(plan: TradingPlan):
    """格式化打印交易计划"""
    name_str = f"{plan.code} {plan.name}" if plan.name else plan.code
    verdict_icon = {"通过": "✅", "警告": "⚠️", "否决": "❌"}.get(plan.risk_verdict, "?")

    print(f"\n{'='*60}")
    print(f"  📋 交易计划 — {name_str}")
    print(f"  生成时间: {plan.generated_at}")
    print(f"  风控意见: {verdict_icon} {plan.risk_verdict}")
    print(f"{'='*60}")

    # ── 市场状态 ──
    print(f"\n  📊 市场状态")
    print(f"  现价:       ¥{plan.current_price:.2f}")
    print(f"  涨跌停幅度: ±{plan.price_limit_pct:.0%}")
    print(f"  信号:       {plan.signal_summary}")

    # ── 入场计划 ──
    if plan.entry_type == "limit":
        print(f"\n  🎯 入场计划（限价单）")
        print(f"  建议挂单区间: ¥{plan.entry_price_min:.2f} ~ ¥{plan.entry_price_max:.2f}")
    elif plan.entry_type == "market":
        print(f"\n  🎯 入场计划（市价单）")
        print(f"  当前价:       ¥{plan.current_price:.2f}")
    else:
        print(f"\n  ⏸️  当前不建议入场（信号={plan.signal_summary}）")

    # ── 仓位 ──
    pos = plan.position
    if pos:
        print(f"\n  💰 仓位计划")
        print(f"  建议买入:     {pos.max_shares}股（{pos.max_shares // 100}手）")
        print(f"  所需资金:     ¥{pos.target_amount:,.0f}")
        print(f"  仓位占比:     {pos.position_pct:.1%}")
        print(f"  单笔风险上限: ¥{plan.max_loss_amount:,.0f} ({plan.max_loss_pct:.1%} of 账户)")

    # ── 风控 ──
    print(f"\n  🛡️ 风控")
    print(f"  止损价:       ¥{plan.stop_loss:.2f} "
          f"({(plan.stop_loss - plan.current_price) / plan.current_price:+.2%})")
    if pos and pos.atr > 0:
        print(f"  ATR(14):      ¥{pos.atr:.2f}  "
              f"(止损 = 现价 - {pos.atr_mult:.0f}×ATR)")

    tp = plan.take_profit
    print(f"  止盈目标:")
    print(f"    TP1 (1:1): ¥{tp['tp1']:.2f}  "
          f"({(tp['tp1'] - plan.current_price) / plan.current_price:+.2%}) — 减仓1/2")
    print(f"    TP2 (2:1): ¥{tp['tp2']:.2f}  "
          f"({(tp['tp2'] - plan.current_price) / plan.current_price:+.2%}) — 再减1/2")
    print(f"    TP3 (3:1): ¥{tp['tp3']:.2f}  "
          f"({(tp['tp3'] - plan.current_price) / plan.current_price:+.2%}) — 清仓")
    print(f"  风报比:       {plan.risk_reward_ratio}:1")

    # ── 提醒 ──
    if plan.risk_notes:
        print(f"\n  📝 提醒:")
        for note in plan.risk_notes:
            print(f"    {note}")

    print(f"\n{'='*60}")

    if not plan.is_actionable():
        print(f"  ⛔ 风控否决，计划不可执行")
    else:
        print(f"  👆 按以上参数手动下单，交易后记得用 tradelog 记录")
    print(f"{'='*60}\n")
