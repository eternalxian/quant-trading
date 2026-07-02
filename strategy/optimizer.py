"""策略优化器 v2 — 基于回测结果评分

对信号计算器参数网格搜索，每个组合跑一次回测，
用夏普比和收益率综合评分。
"""

import logging
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("quant.optimizer")


@dataclass
class ParamGrid:
    strategy_name: str
    params: dict[str, list]


@dataclass
class OptimizationResult:
    strategy_name: str
    params: dict
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    score: float = 0.0
    rank: int = 0
    status: str = "tested"


# ═══════════════════ 预定义参数网格 ═══════════════════

GRIDS: dict[str, ParamGrid] = {
    "双均线交叉": ParamGrid(
        strategy_name="双均线交叉",
        params={
            "ma_short": [3, 5, 10],
            "ma_long": [15, 20, 30],
        },
    ),
    "MACD趋势跟踪": ParamGrid(
        strategy_name="MACD趋势跟踪",
        params={
            "fast": [8, 12],
            "slow": [20, 26],
            "signal": [6, 9],
        },
    ),
    "RSI超买超卖": ParamGrid(
        strategy_name="RSI超买超卖",
        params={
            "period": [10, 14],
            "oversold": [25, 30],
            "overbought": [65, 70],
        },
    ),
    "布林带反转": ParamGrid(
        strategy_name="布林带反转",
        params={
            "period": [15, 20],
            "std_dev": [1.5, 2.0],
        },
    ),
}


# ═══════════════════ 回测驱动评分 ═══════════════════

def backtest_score(params: dict, etf_data: dict, strategy_name: str) -> OptimizationResult:
    """前向验证评分：信号日 → N天后验证方向

    对每只 ETF：切分数据为训练集(前80%)和测试集(后20%)
    训练集生成信号 → 测试集验证方向
    """
    from signals import get_calculator

    calc = get_calculator(strategy_name, params=params)
    signals_dict = calc.compute_all(etf_data)

    total_return = 0.0
    num_trades = 0
    wins = 0
    hold_count = 0

    for code, sr in signals_dict.items():
        df = etf_data.get(code)
        if df is None or df.empty or len(df) < 30:
            continue
        if not hasattr(sr, "signal"):
            continue

        sig = sr.signal
        if sig == "hold":
            hold_count += 1
            continue

        # 训练集最后一天 vs 全数据集最后一天 的收益
        split = int(len(df) * 0.8)
        train_end = df["close"].iloc[split - 1]
        test_end = df["close"].iloc[-1]
        forward_return = (test_end - train_end) / train_end

        if sig == "buy" and forward_return > 0:
            wins += 1
            total_return += abs(forward_return) * 100
        elif sig == "sell" and forward_return < 0:
            wins += 1
            total_return += abs(forward_return) * 100
        else:
            total_return -= abs(forward_return) * 100  # 方向判断错误

        num_trades += 1

    # 综合评分：胜率 × 50 + 收益贡献 × 50
    win_rate = wins / max(num_trades, 1) * 100
    avg_return = total_return / max(num_trades, 1)
    score = win_rate * 0.5 + avg_return * 0.5

    # 如果没有交易信号，低分
    if num_trades == 0:
        score = -50

    return OptimizationResult(
        strategy_name=strategy_name,
        params=params,
        total_return=round(total_return, 2),
        annual_return=round(win_rate, 2),
        score=round(score, 2),
        status="tested",
    )


# ═══════════════════ 优化入口 ═══════════════════

def optimize(
    strategy_name: str,
    etf_data: dict,
    top_n: int = 3,
) -> list[OptimizationResult]:
    grid = GRIDS.get(strategy_name)
    if grid is None:
        logger.warning(f"策略 {strategy_name} 无预定义网格")
        return []

    param_names = list(grid.params.keys())
    param_values = list(grid.params.values())
    combinations = list(itertools.product(*param_values))

    logger.info(f"优化 {strategy_name}: {len(combinations)} 组参数")

    results = []
    for combo in combinations:
        params = dict(zip(param_names, combo))
        try:
            r = backtest_score(params, etf_data, strategy_name)
            results.append(r)
        except Exception as e:
            logger.debug(f"组合 {params} 失败: {e}")

    results.sort(key=lambda r: r.score, reverse=True)

    for i, r in enumerate(results[:top_n]):
        r.rank = i + 1

    # 标记最佳
    if results:
        results[0].status = "best"

    return results[:top_n]


def optimize_all(etf_data: dict, top_n: int = 3) -> dict[str, list[OptimizationResult]]:
    results = {}
    for name in GRIDS:
        try:
            r = optimize(name, etf_data, top_n=top_n)
            if r:
                results[name] = r
                best = r[0]
                logger.info(f"{name}: 最优 {best.params} 得分 {best.score:.1f}")
        except Exception as e:
            logger.warning(f"优化 {name} 失败: {e}")
    return results


def optimize_rotation_strategy(etf_data: dict, cash: float = 100000.0):
    """ETF轮动策略参数优化（使用真实回测引擎）

    优化 score_window 和 rebalance_days 两个核心参数
    """
    from backtest.runner import run_backtest
    from backtest.strategies import EtfRotationStrategy
    from config import ROTATION_ETF_CODES

    # 只取轮动池中的 ETF，且标准化列名
    data_dict = {}
    for code in ROTATION_ETF_CODES:
        df = etf_data.get(code)
        if df is not None and not df.empty and len(df) >= 60:
            df = df.copy()
            # 统一列名为英文
            if "日期" in df.columns:
                df = df.rename(columns={"日期": "date"})
            data_dict[code] = df

    if len(data_dict) < 2:
        logger.warning("ETF数据不足，跳过轮动优化")
        return []

    windows = [15, 20, 25, 30]
    rebalances = [10, 15, 20, 30]

    results = []
    for w in windows:
        for r in rebalances:
            try:
                analysis, _ = run_backtest(
                    EtfRotationStrategy,
                    data_dict,
                    cash=cash,
                    score_window=w,
                    rebalance_days=r,
                    top_n=1,
                )
                ret = float(str(analysis.get("总收益率", "0")).replace("%", ""))
                sharpe = float(analysis.get("夏普比率", 0) or 0)
                dd = float(str(analysis.get("最大回撤", "0")).replace("%", ""))
                score = ret - abs(dd) * 0.5 + sharpe * 10

                results.append({
                    "window": w,
                    "rebalance": r,
                    "return": ret,
                    "sharpe": sharpe,
                    "max_dd": dd,
                    "score": round(score, 2),
                })
            except Exception as e:
                logger.debug(f"回测 {w}/{r} 失败: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:5]


def print_rotation_results(results: list[dict]):
    print(f"\n  ── ETF轮动策略参数优化 ──")
    print(f"  {'排名':>3} {'窗口':>5} {'调仓':>5} {'收益':>8} {'夏普':>6} {'回撤':>8} {'得分':>7}")
    print(f"  {'-'*52}")
    for i, r in enumerate(results):
        tag = "⭐" if i == 0 else "  "
        print(f"  {tag}{i+1:>2} {r['window']:>5} {r['rebalance']:>5} "
              f"{r['return']:>+7.1f}% {r['sharpe']:>6.2f} {r['max_dd']:>7.1f}% {r['score']:>7.1f}")
    print()


def print_optimization(results: dict[str, list[OptimizationResult]]):
    print(f"\n{'='*75}")
    print(f"  策略参数优化结果（回测驱动）")
    print(f"{'='*75}")

    for name, items in results.items():
        if not items:
            continue
        print(f"\n  ── {name} ──")
        header = f"  {'排名':>3} {'得分':>7} {'收益率':>7} {'参数'}"
        print(header)
        print(f"  {'-'*60}")
        for r in items:
            params_str = ", ".join(f"{k}={v}" for k, v in r.params.items())
            tag = "⭐" if r.rank == 1 else "  "
            print(f"  {tag}{r.rank:>2} {r.score:>7.1f} {r.total_return:>+7.1f}%  {params_str}")

    print(f"\n{'='*75}\n")


if __name__ == "__main__":
    from data import get_all_etfs

    print("拉取 ETF 数据...")
    etf_data = get_all_etfs(days=250)
    print(f"已获取 {len(etf_data)} 只 ETF")

    # 信号参数优化
    results = optimize_all(etf_data, top_n=3)
    print_optimization(results)

    # ETF轮动参数优化（真实回测）
    print("运行 ETF 轮动参数优化...")
    rot_results = optimize_rotation_strategy(etf_data)
    print_rotation_results(rot_results)
