"""
个股回测引擎 — 信号驱动，逐日模拟

不依赖 Backtrader，直接基于 signals/ 的信号输出做买卖模拟。
每个交易日向前滚动计算信号（点-in-time），避免前视偏差。
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
import logging

from signals import list_calculators, _registry

logger = logging.getLogger(__name__)

# ── 策略名映射（英文→中文）──
STRATEGY_ALIASES = {
    "ma_cross": "双均线交叉",
    "macd_trend": "MACD趋势跟踪",
    "rsi_reversal": "RSI超买超卖",
    "bollinger": "布林带反转",
    "kdj": "KDJ随机指标",
    "donchian": "唐奇安通道突破",
    "money_flow": "资金流因子",
    "smart_money": "聪明钱因子",
    "alligator": "鳄鱼线趋势",
    "rsrs": "RSRS阻力支撑",
    "qrs": "QRS量化RS",
    "volume_dist": "筹码分布因子",
    "rotation_classic": "ETF轮动-经典版",
    "rotation_ls": "板块轮动-LS回归",
    "lstm": "LSTM时序预测",
    "tft": "TFT时序预测",
    "catboost": "CatBoost评分",
    "lightgbm": "LightGBM评分",
    "ensemble": "多模型集成投票",
    "hht": "HHT希尔伯特黄",
}


def resolve_strategy(name: str) -> str:
    """解析策略名：支持英文别名 + 中文名"""
    # 直接命中 registry
    if name in _registry:
        return name
    # 英文别名
    if name.lower() in STRATEGY_ALIASES:
        cn = STRATEGY_ALIASES[name.lower()]
        if cn in _registry:
            return cn
    # 模糊匹配（不区分大小写）
    for reg_name in _registry:
        if name.lower() == reg_name.lower():
            return reg_name
    # 部分匹配
    for reg_name in _registry:
        if name.lower() in reg_name.lower() or reg_name.lower() in name.lower():
            return reg_name
    raise KeyError(f"未找到策略 '{name}'。可用: {sorted(_registry)}")


# ═══════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════

@dataclass
class Trade:
    """单笔交易记录"""
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    exit_reason: str          # 'signal_sell' | 'stop_loss' | 'end_of_data'
    shares: int
    pnl: float
    pnl_pct: float
    hold_days: int


@dataclass
class BacktestResult:
    """回测结果"""
    code: str
    name: str
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float
    total_return: float           # 总收益率
    annual_return: float          # 年化收益率
    win_rate: float               # 胜率
    max_drawdown: float           # 最大回撤
    sharpe: float                 # 夏普比率
    max_drawdown_duration: int    # 最长回撤持续天数
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_profit_pct: float         # 平均盈利%
    avg_loss_pct: float           # 平均亏损%
    profit_factor: float          # 盈亏比 (总盈利/总亏损)
    avg_hold_days: float
    trades: list = field(default_factory=list)
    daily_equity: list = field(default_factory=list)  # [(date, equity)]


# ═══════════════════════════════════════
#  引擎
# ═══════════════════════════════════════

def backtest_stock(
    df: pd.DataFrame,
    code: str = "",
    name: str = "",
    strategy_name: str = "ma_cross",
    capital: float = 100_000,
    stop_atr_mult: float = 2.0,
    commission_rate: float = 0.0003,      # 万三
    stamp_tax_rate: float = 0.001,        # 千一（仅卖出）
    slippage_pct: float = 0.001,          # 0.1% 滑点
    min_window: int = 30,                 # 最小数据窗口（天）
    verbose: bool = False,
) -> BacktestResult:
    """对单只股票运行单策略回测

    Args:
        df: 日K线 DataFrame，需含列 date, open, high, low, close, volume
             date 列应为字符串 'YYYY-MM-DD' 或 datetime
        code: 股票代码
        name: 股票名称
        strategy_name: 策略名（如 'ma_cross', 'macd_trend'）
        capital: 初始资金
        stop_atr_mult: ATR止损乘数（0=不止损）
        commission_rate: 佣金率
        stamp_tax_rate: 印花税率（卖出）
        slippage_pct: 滑点比例
        min_window: 最小数据窗口，前N天不交易（等信号成熟）
        verbose: 打印每笔交易

    Returns:
        BacktestResult
    """
    from signals import compute_all_signals

    # 解析策略名
    strategy_name = resolve_strategy(strategy_name)

    # ── 准备数据 ──
    df = df.copy()
    df = df.reset_index(drop=True)

    # 标准化列名
    if "日期" in df.columns:
        df.rename(columns={"日期": "date"}, inplace=True)

    # 确保 date 是字符串
    df["date"] = df["date"].astype(str)

    # 数值列
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df["volume"] = df["volume"].astype(float)

    # 按日期排序
    df = df.sort_values("date").reset_index(drop=True)

    n_days = len(df)
    if n_days < min_window:
        return BacktestResult(
            code=code, name=name, strategy=strategy_name,
            start_date="", end_date="", initial_capital=capital,
            final_equity=capital, total_return=0, annual_return=0,
            win_rate=0, max_drawdown=0, sharpe=0,
            max_drawdown_duration=0, total_trades=0,
            winning_trades=0, losing_trades=0,
            avg_profit_pct=0, avg_loss_pct=0, profit_factor=0,
            avg_hold_days=0,
        )

    # ── 状态变量 ──
    cash = capital
    position = 0               # 持股数
    cost_basis = 0.0           # 持仓成本
    buy_date = ""              # 买入日（用于 T+1）
    stop_loss = 0.0            # 止损价
    trades: list[Trade] = []
    daily_equity: list[tuple] = []

    # ATR 相关
    atr_period = 14
    atr_value = 0.0

    # ── 日循环 ──
    for i in range(min_window, n_days):
        today = df.iloc[i]
        prev_day = df.iloc[i - 1]
        date_str = str(today["date"])
        open_price = float(today["open"])
        high_price = float(today["high"])
        low_price = float(today["low"])
        close_price = float(today["close"])
        prev_close = float(prev_day["close"])

        # 无效数据跳过
        if open_price <= 0 or close_price <= 0:
            daily_equity.append((date_str, cash + position * prev_close))
            continue

        # ── 计算当前信号（仅用 i 之前的数据）──
        window_df = df.iloc[:i + 1].copy()
        try:
            all_signals = compute_all_signals(
                {code: window_df},
                strategy_names=[strategy_name],
                persist=False,
            )
            sig_result = all_signals.get(strategy_name, {}).get(code)
            if sig_result is None:
                signal = "hold"
            else:
                signal = sig_result.signal
        except Exception as e:
            if verbose:
                logger.warning(f"  [{date_str}] 信号计算失败: {e}")
            signal = "hold"

        # ── 更新 ATR ──
        if i >= atr_period + 1:
            atr_df = df.iloc[:i + 1]
            atr_value = _calc_atr_simple(atr_df, atr_period)

        # ── T+1 检查 ──
        t1_locked = (position > 0 and date_str <= buy_date)

        # ── 卖出逻辑 ──
        exit_reason = ""
        exit_price = 0.0

        if position > 0 and not t1_locked:
            # 止损检查：日内最低价触及止损价
            if stop_loss > 0 and low_price <= stop_loss:
                exit_reason = "stop_loss"
                # 如果开盘就跳空跌破止损，以开盘价成交
                if open_price <= stop_loss:
                    exit_price = open_price
                else:
                    exit_price = stop_loss

            # 信号卖出
            elif signal == "sell":
                exit_reason = "signal_sell"
                exit_price = open_price

            # 执行卖出
            if exit_reason:
                exit_price = exit_price * (1 - slippage_pct)  # 卖出滑点向下
                exit_price = max(exit_price, 0.01)

                gross_proceeds = position * exit_price
                commission = gross_proceeds * commission_rate
                stamp_tax = gross_proceeds * stamp_tax_rate
                net_proceeds = gross_proceeds - commission - stamp_tax

                pnl = net_proceeds - position * cost_basis
                pnl_pct = pnl / (position * cost_basis) if cost_basis > 0 else 0

                buy_dt = datetime.strptime(buy_date, "%Y-%m-%d")
                sell_dt = datetime.strptime(date_str, "%Y-%m-%d")
                hold_days = (sell_dt - buy_dt).days

                trades.append(Trade(
                    entry_date=buy_date,
                    entry_price=cost_basis,
                    exit_date=date_str,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    shares=position,
                    pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 4),
                    hold_days=max(hold_days, 1),
                ))

                if verbose:
                    tag = "赚" if pnl > 0 else "亏"
                    print(f"  [{date_str}] 卖出 {position}股 @{exit_price:.2f} "
                          f"{tag}¥{pnl:+.0f} ({pnl_pct:+.2%}) [{exit_reason}]")

                cash += net_proceeds
                position = 0
                cost_basis = 0
                stop_loss = 0
                buy_date = ""

        # ── 买入逻辑 ──
        if position == 0 and signal == "buy":
            # 检查涨跌停（简化：如果开盘即涨停则放弃）
            limit_status = _check_limit_at_open(code, open_price, prev_close)
            if limit_status == "limit_up":
                if verbose:
                    print(f"  [{date_str}] 开盘涨停，放弃买入")
                daily_equity.append((date_str, cash))
                continue

            entry_price = open_price * (1 + slippage_pct)  # 买入滑点向上

            # 计算 ATR 止损
            if stop_atr_mult > 0 and atr_value > 0:
                stop_loss = entry_price - atr_value * stop_atr_mult
            else:
                # 固定 5% 止损
                stop_loss = entry_price * 0.95

            # 仓位计算（固定比例风险 2%）
            risk_per_share = entry_price - stop_loss
            if risk_per_share <= 0:
                risk_per_share = entry_price * 0.02

            max_risk = capital * 0.02
            raw_shares = max_risk / risk_per_share
            # 仓位上限 30%
            max_position_amount = capital * 0.30
            max_shares_by_position = max_position_amount / entry_price
            shares = min(raw_shares, max_shares_by_position)
            # 取整到 100 股
            lots = max(1, int(shares / 100))
            shares = lots * 100

            total_cost = shares * entry_price
            commission = total_cost * commission_rate
            required = total_cost + commission

            if required > cash:
                # 钱不够，缩到能买的最大手数
                affordable_lots = int((cash / (1 + commission_rate)) / (entry_price * 100))
                if affordable_lots < 1:
                    if verbose:
                        print(f"  [{date_str}] 资金不足，放弃买入")
                    daily_equity.append((date_str, cash))
                    continue
                shares = affordable_lots * 100
                total_cost = shares * entry_price
                commission = total_cost * commission_rate
                required = total_cost + commission

            cost_basis = entry_price
            cash -= required
            position = shares
            buy_date = date_str

            if verbose:
                print(f"  [{date_str}] 买入 {shares}股 @{entry_price:.2f} "
                      f"¥{required:,.0f}  止损@{stop_loss:.2f}")

        # ── 记录每日权益 ──
        equity = cash + position * close_price
        daily_equity.append((date_str, round(equity, 2)))

    # ── 期末清仓 ──
    if position > 0:
        last_day = df.iloc[-1]
        exit_price = float(last_day["close"]) * (1 - slippage_pct)
        gross_proceeds = position * exit_price
        commission = gross_proceeds * commission_rate
        stamp_tax = gross_proceeds * stamp_tax_rate
        net_proceeds = gross_proceeds - commission - stamp_tax
        pnl = net_proceeds - position * cost_basis
        pnl_pct = pnl / (position * cost_basis) if cost_basis > 0 else 0
        last_date = str(last_day["date"])
        buy_dt = datetime.strptime(buy_date, "%Y-%m-%d") if buy_date else datetime.now()
        sell_dt = datetime.strptime(last_date, "%Y-%m-%d")
        hold_days = (sell_dt - buy_dt).days

        trades.append(Trade(
            entry_date=buy_date,
            entry_price=cost_basis,
            exit_date=last_date,
            exit_price=exit_price,
            exit_reason="end_of_data",
            shares=position,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 4),
            hold_days=max(hold_days, 1),
        ))

        cash += net_proceeds
        position = 0

    # ── 计算统计 ──
    final_equity = daily_equity[-1][1] if daily_equity else cash
    total_return = (final_equity - capital) / capital if capital > 0 else 0

    # 年化
    if len(daily_equity) >= 2:
        start_d = datetime.strptime(str(daily_equity[0][0]), "%Y-%m-%d")
        end_d = datetime.strptime(str(daily_equity[-1][0]), "%Y-%m-%d")
        years = max((end_d - start_d).days / 365.25, 0.05)
        annual_return = (final_equity / capital) ** (1 / years) - 1 if capital > 0 else 0
    else:
        years = 0.05
        annual_return = 0

    # 胜率 & 盈亏比
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    avg_profit = np.mean([t.pnl_pct for t in wins]) if wins else 0
    avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0  # 负值
    total_wins = sum(t.pnl for t in wins)
    total_losses = abs(sum(t.pnl for t in losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else (999 if total_wins > 0 else 0)
    avg_hold = np.mean([t.hold_days for t in trades]) if trades else 0

    # 最大回撤
    equities = [e[1] for e in daily_equity]
    peak = equities[0]
    max_dd = 0.0
    max_dd_duration = 0
    current_dd_duration = 0
    for eq in equities:
        if eq > peak:
            peak = eq
            current_dd_duration = 0
        else:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
            current_dd_duration += 1
            if current_dd_duration > max_dd_duration:
                max_dd_duration = current_dd_duration

    # 夏普比率
    if len(equities) >= 2:
        daily_returns = np.diff(equities) / equities[:-1]
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    return BacktestResult(
        code=code,
        name=name,
        strategy=strategy_name,
        start_date=daily_equity[0][0] if daily_equity else "",
        end_date=daily_equity[-1][0] if daily_equity else "",
        initial_capital=capital,
        final_equity=round(final_equity, 2),
        total_return=round(total_return, 4),
        annual_return=round(annual_return, 4),
        win_rate=round(win_rate, 4),
        max_drawdown=round(max_dd, 4),
        sharpe=round(sharpe, 4),
        max_drawdown_duration=max_dd_duration,
        total_trades=total_trades,
        winning_trades=len(wins),
        losing_trades=len(losses),
        avg_profit_pct=round(avg_profit, 4),
        avg_loss_pct=round(avg_loss, 4),
        profit_factor=round(profit_factor, 2),
        avg_hold_days=round(avg_hold, 1),
        trades=trades,
        daily_equity=daily_equity,
    )


def backtest_multi_strategies(
    df: pd.DataFrame,
    code: str = "",
    name: str = "",
    strategy_names: list[str] = None,
    capital: float = 100_000,
    stop_atr_mult: float = 2.0,
    verbose: bool = False,
) -> list[BacktestResult]:
    """对单只股票运行多个策略回测

    Args:
        df: 日K线
        code: 股票代码
        name: 股票名称
        strategy_names: 要测试的策略名列表，None=全部
        capital: 初始资金
        stop_atr_mult: ATR止损乘数
        verbose: 打印详情

    Returns:
        [BacktestResult] 按总收益率降序排列
    """
    from signals import list_calculators

    all_strategies = list_calculators()
    if strategy_names is None:
        # 默认排除 ML 策略（慢且可能有前视偏差）
        ml_skip = {"LSTM时序预测", "TFT时序预测", "CatBoost评分",
                    "LightGBM评分", "多模型集成投票", "HHT希尔伯特黄"}
        strategy_names = [s for s in all_strategies if s not in ml_skip]
    else:
        strategy_names = [resolve_strategy(s) for s in strategy_names]

    results = []
    for sname in strategy_names:
        if verbose:
            print(f"  回测 {sname}...")
        try:
            result = backtest_stock(
                df, code=code, name=name, strategy_name=sname,
                capital=capital, stop_atr_mult=stop_atr_mult,
                verbose=False,
            )
            results.append(result)
        except Exception as e:
            logger.warning(f"策略 {sname} 回测失败: {e}")
            continue

    # 按总收益率排序
    results.sort(key=lambda r: r.total_return, reverse=True)
    return results


# ═══════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════

def _calc_atr_simple(df: pd.DataFrame, period: int = 14) -> float:
    """简化ATR（回测内部用）"""
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
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return round(float(atr.iloc[-1]), 4)


def _check_limit_at_open(code: str, open_price: float, prev_close: float) -> str:
    """检查开盘是否涨停/跌停"""
    if prev_close <= 0:
        return "normal"
    change = (open_price - prev_close) / prev_close
    # 根据代码判断涨跌停幅度
    code_str = str(code)
    if "ST" in code_str.upper():
        limit = 0.05
    elif code_str.startswith("688"):
        limit = 0.20
    elif code_str.startswith("300") or code_str.startswith("301"):
        limit = 0.20
    elif code_str.startswith("8"):
        limit = 0.30
    else:
        limit = 0.10

    if change >= limit * 0.99:
        return "limit_up"
    elif change <= -limit * 0.99:
        return "limit_down"
    return "normal"


# ═══════════════════════════════════════
#  打印输出
# ═══════════════════════════════════════

def print_backtest_result(r: BacktestResult):
    """打印单个回测结果"""
    name_str = f"{r.code} {r.name}" if r.name else r.code
    print(f"\n{'='*60}")
    print(f"  {name_str} — {r.strategy}")
    print(f"  {r.start_date} → {r.end_date}")
    print(f"{'='*60}")
    print(f"  初始资金:  ¥{r.initial_capital:,.0f}")
    print(f"  最终权益:  ¥{r.final_equity:,.0f}")
    print(f"  总收益率:  {r.total_return:+.2%}")
    print(f"  年化收益:  {r.annual_return:+.2%}")
    print(f"  夏普比率:  {r.sharpe:.2f}")
    print(f"  最大回撤:  {r.max_drawdown:.2%}  (持续{r.max_drawdown_duration}天)")
    print(f"  {'-'*40}")
    print(f"  交易次数:  {r.total_trades}")
    print(f"  胜率:      {r.win_rate:.1%}  ({r.winning_trades}赢/{r.losing_trades}亏)")
    print(f"  平均盈利:  {r.avg_profit_pct:+.2%}")
    print(f"  平均亏损:  {r.avg_loss_pct:+.2%}")
    print(f"  盈亏比:    {r.profit_factor:.2f}")
    print(f"  平均持仓:  {r.avg_hold_days:.0f}天")
    print(f"{'='*60}")

    if r.trades:
        print(f"\n  交易明细:")
        print(f"  {'入场日':>12s}  {'入场价':>8s}  {'出场日':>12s}  "
              f"{'出场价':>8s}  {'盈亏':>10s}  {'收益率':>8s}  {'持仓':>4s}  {'原因'}")
        print(f"  {'-'*75}")
        for t in r.trades:
            pnl_tag = "+" if t.pnl > 0 else ""
            print(f"  {t.entry_date:>12s}  {t.entry_price:>8.2f}  "
                  f"{t.exit_date:>12s}  {t.exit_price:>8.2f}  "
                  f"{pnl_tag}¥{t.pnl:>8.0f}  {t.pnl_pct:>+7.2%}  "
                  f"{t.hold_days:>4d}d  {t.exit_reason}")


def print_backtest_compare(results: list[BacktestResult], top_n: int = 10):
    """打印多策略对比"""
    if not results:
        print("\n无回测结果\n")
        return

    code = results[0].code
    name = results[0].name
    name_str = f"{code} {name}" if name else code

    print(f"\n{'='*90}")
    print(f"  {name_str} — 多策略回测对比")
    print(f"{'='*90}")
    header = (f"  {'策略':<22s} {'总收益':>8s} {'年化':>8s} {'夏普':>7s} "
              f"{'回撤':>7s} {'交易':>5s} {'胜率':>7s} {'盈亏比':>7s} {'均持':>5s}")
    print(header)
    print(f"  {'-'*80}")

    for r in results[:top_n]:
        print(f"  {r.strategy:<22s} {r.total_return:>+7.2%} {r.annual_return:>+7.2%} "
              f"{r.sharpe:>6.2f} {r.max_drawdown:>6.2%} {r.total_trades:>5d} "
              f"{r.win_rate:>6.1%} {r.profit_factor:>6.2f} {r.avg_hold_days:>4.0f}d")

    print(f"{'='*90}")

    # 综合评分
    if len(results) >= 1:
        best = results[0]
        print(f"\n  ★ 最佳策略: {best.strategy}")
        print(f"    总收益 {best.total_return:+.2%}  "
              f"夏普 {best.sharpe:.2f}  "
              f"胜率 {best.win_rate:.1%}  "
              f"最大回撤 {best.max_drawdown:.2%}")
    print()
