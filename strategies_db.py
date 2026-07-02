"""
策略数据库：管理策略定义、信号、绩效对比
数据源：SQLite (db.py)
"""
import json
from datetime import datetime
from db import (get_strategies, get_strategy, add_strategy, update_strategy,
                get_strategy_signals, add_strategy_signal,
                get_strategy_perf, add_strategy_perf)


# ═══════════════════════════════════════════
#  内置策略定义（发现自 GitHub 开源项目）
# ═══════════════════════════════════════════

BUILTIN_STRATEGIES = [
    # ── 轮动策略 ──
    {
        "name": "ETF轮动-回归斜率评分",
        "type": "轮动",
        "description": "线性回归斜率×R²(50%) + 动量(30%) + 均线比(20%) 综合评分，每月调仓到评分最高ETF",
        "params": json.dumps({"score_window": 25, "rebalance_days": 20, "momentum_threshold": 0.02, "max_position_pct": 0.30}),
        "target_type": "ETF",
        "source": "自定义实现(vnpy)",
        "source_url": ""
    },
    {
        "name": "ETF轮动-经典版",
        "type": "轮动",
        "description": "基于N日收益率排名，每月持有最强ETF。来自 chrisphoenixsoar/etf_rotation",
        "params": json.dumps({"rank_days": 20, "top_n": 1, "rebalance_days": 20}),
        "target_type": "ETF",
        "source": "chrisphoenixsoar/etf_rotation",
        "source_url": "https://github.com/chrisphoenixsoar/etf_rotation"
    },
    {
        "name": "板块轮动-LS回归",
        "type": "轮动",
        "description": "对申万一级行业做线性回归斜率评分，轮动配置最强行业ETF。来自 QuantsPlaybook",
        "params": json.dumps({"lookback": 60, "top_n": 3, "rebalance_days": 20}),
        "target_type": "板块ETF",
        "source": "hugo2046/QuantsPlaybook",
        "source_url": "https://github.com/hugo2046/QuantsPlaybook"
    },

    # ── 趋势跟踪 ──
    {
        "name": "双均线交叉",
        "type": "趋势跟踪",
        "description": "经典双均线策略: 短期均线上穿长期均线买入，下穿卖出。支持EMA/SMA",
        "params": json.dumps({"fast": 5, "slow": 20, "type": "SMA"}),
        "target_type": "ETF/基金",
        "source": "通用策略",
        "source_url": ""
    },
    {
        "name": "MACD趋势跟踪",
        "type": "趋势跟踪",
        "description": "MACD金叉死叉: DIF上穿DEA买入，下穿卖出。结合柱状图背离过滤假信号",
        "params": json.dumps({"fast": 12, "slow": 26, "signal": 9}),
        "target_type": "ETF/基金",
        "source": "通用策略",
        "source_url": ""
    },
    {
        "name": "唐奇安通道突破",
        "type": "趋势跟踪",
        "description": "海龟策略简化版: 价格突破N日高点买入，突破N日低点卖出。带ATR止损",
        "params": json.dumps({"entry_period": 20, "exit_period": 10, "atr_multiplier": 2}),
        "target_type": "ETF",
        "source": "通用策略(海龟)",
        "source_url": ""
    },

    # ── 机器学习 ──
    {
        "name": "LSTM时序预测",
        "type": "机器学习",
        "description": "长短期记忆网络预测ETF未来N日收益率，排序选最强。来自 aojie-ju/etf-trading-intelligence",
        "params": json.dumps({"lookback": 60, "forecast": 5, "hidden_size": 64, "layers": 2, "epochs": 50}),
        "target_type": "ETF",
        "source": "aojie-ju/etf-trading-intelligence",
        "source_url": "https://github.com/aojie-ju/etf-trading-intelligence"
    },
    {
        "name": "TFT时序预测",
        "type": "机器学习",
        "description": "Temporal Fusion Transformer: 带可解释性的深度学习时序模型，预测ETF收益率",
        "params": json.dumps({"lookback": 60, "forecast": 5, "hidden_size": 64}),
        "target_type": "ETF",
        "source": "aojie-ju/etf-trading-intelligence",
        "source_url": "https://github.com/aojie-ju/etf-trading-intelligence"
    },
    {
        "name": "LightGBM评分",
        "type": "机器学习",
        "description": "LightGBM梯度提升: 用量价特征训练分类模型，预测ETF涨跌方向。7模型集成成员",
        "params": json.dumps({"lookback": 60, "n_estimators": 200, "learning_rate": 0.05, "max_depth": 5}),
        "target_type": "ETF",
        "source": "aojie-ju/etf-trading-intelligence",
        "source_url": "https://github.com/aojie-ju/etf-trading-intelligence"
    },
    {
        "name": "CatBoost评分",
        "type": "机器学习",
        "description": "CatBoost梯度提升: 处理量价特征，分类预测涨跌。7模型集成成员",
        "params": json.dumps({"lookback": 60, "iterations": 300, "learning_rate": 0.05, "depth": 5}),
        "target_type": "ETF",
        "source": "aojie-ju/etf-trading-intelligence",
        "source_url": "https://github.com/aojie-ju/etf-trading-intelligence"
    },
    {
        "name": "多模型集成投票",
        "type": "机器学习",
        "description": "LSTM+TFT+N-BEATS+LightGBM+CatBoost+SARIMAX 七模型软投票集成",
        "params": json.dumps({"models": ["LSTM", "TFT", "N-BEATS", "LightGBM", "CatBoost", "SARIMAX", "XGBoost"], "voting": "soft"}),
        "target_type": "ETF",
        "source": "aojie-ju/etf-trading-intelligence",
        "source_url": "https://github.com/aojie-ju/etf-trading-intelligence"
    },

    # ── 统计套利 ──
    {
        "name": "RSRS阻力支撑",
        "type": "统计套利",
        "description": "Resistance Support Relative Strength: 用高低点回归度量阻力支撑强度。来自 QuantsPlaybook",
        "params": json.dumps({"lookback": 18, "beta_threshold": 0.5, "r2_threshold": 0.7}),
        "target_type": "ETF/指数",
        "source": "hugo2046/QuantsPlaybook",
        "source_url": "https://github.com/hugo2046/QuantsPlaybook"
    },
    {
        "name": "QRS量化RS",
        "type": "统计套利",
        "description": "Quantitative Relative Strength: 改进版相对强弱指标，过滤噪音。来自 QuantsPlaybook",
        "params": json.dumps({"lookback": 20, "smooth_period": 5}),
        "target_type": "ETF/指数",
        "source": "hugo2046/QuantsPlaybook",
        "source_url": "https://github.com/hugo2046/QuantsPlaybook"
    },
    {
        "name": "HHT希尔伯特黄",
        "type": "统计套利",
        "description": "Hilbert-Huang Transform: 经验模态分解提取市场周期信号。来自 QuantsPlaybook",
        "params": json.dumps({"imf_count": 5, "threshold": 0.5}),
        "target_type": "ETF/指数",
        "source": "hugo2046/QuantsPlaybook",
        "source_url": "https://github.com/hugo2046/QuantsPlaybook"
    },

    # ── 技术指标 ──
    {
        "name": "RSI超买超卖",
        "type": "技术指标",
        "description": "RSI相对强弱: 超卖(<30)买入，超买(>70)卖出，底背离/顶背离增强",
        "params": json.dumps({"period": 14, "oversold": 30, "overbought": 70}),
        "target_type": "ETF/基金",
        "source": "通用策略",
        "source_url": ""
    },
    {
        "name": "布林带反转",
        "type": "技术指标",
        "description": "价格触及下轨买入，上轨卖出。带宽收缩后扩张预示趋势启动",
        "params": json.dumps({"period": 20, "std": 2, "band_shrink_threshold": 0.05}),
        "target_type": "ETF/基金",
        "source": "通用策略",
        "source_url": ""
    },
    {
        "name": "KDJ随机指标",
        "type": "技术指标",
        "description": "KDJ金叉死叉: K值上穿D值买入，下穿卖出。J值>100超买，<0超卖",
        "params": json.dumps({"k_period": 9, "d_period": 3, "j_period": 3}),
        "target_type": "ETF/基金",
        "source": "通用策略",
        "source_url": ""
    },

    # ── 量化因子 ──
    {
        "name": "聪明钱因子",
        "type": "量化因子",
        "description": "大户资金流向跟踪: 基于大单净流入/流出比例判断主力动向。来自 QuantsPlaybook",
        "params": json.dumps({"lookback": 20, "large_trade_threshold": 100000}),
        "target_type": "ETF",
        "source": "hugo2046/QuantsPlaybook",
        "source_url": "https://github.com/hugo2046/QuantsPlaybook"
    },
    {
        "name": "筹码分布因子",
        "type": "量化因子",
        "description": "筹码集中度分析: 基于成交量分布的持仓成本估算。来自 QuantsPlaybook",
        "params": json.dumps({"lookback": 60, "concentration_threshold": 0.3}),
        "target_type": "ETF",
        "source": "hugo2046/QuantsPlaybook",
        "source_url": "https://github.com/hugo2046/QuantsPlaybook"
    },
    {
        "name": "资金流因子",
        "type": "量化因子",
        "description": "资金净流量: 主力/散户资金流向差异，判断短期多空力量",
        "params": json.dumps({"lookback": 10, "money_flow_threshold": 0.05}),
        "target_type": "ETF",
        "source": "通用策略",
        "source_url": ""
    },

    # ── 鳄鱼线 ──
    {
        "name": "鳄鱼线趋势",
        "type": "趋势跟踪",
        "description": "Bill Williams鳄鱼线: 三条均线(BLUE/RED/GREEN)张口闭口判断趋势。来自 QuantsPlaybook",
        "params": json.dumps({"blue_period": 13, "red_period": 8, "green_period": 5, "shift": 8}),
        "target_type": "ETF/指数",
        "source": "hugo2046/QuantsPlaybook",
        "source_url": "https://github.com/hugo2046/QuantsPlaybook"
    },
]


# ═══════════════════════════════════════════
#  种子数据加载
# ═══════════════════════════════════════════

def seed_strategies():
    """将内置策略写入数据库（幂等）"""
    count = 0
    for s in BUILTIN_STRATEGIES:
        rid = add_strategy(s["name"], s["type"], s["description"],
                          s["params"], s["target_type"], s["source"], s["source_url"])
        if rid > 0:
            count += 1
    print(f"✅ 已添加 {count} 个策略到数据库")
    return count


def get_strategy_list(enabled_only: bool = True, type_filter: str = None) -> list:
    """获取策略列表，可选按类型过滤"""
    all_strategies = get_strategies(enabled_only)
    if type_filter:
        return [s for s in all_strategies if s["type"] == type_filter]
    return all_strategies


def get_strategy_types() -> list:
    """获取所有策略类型"""
    strategies = get_strategies(enabled_only=False)
    types = sorted(set(s["type"] for s in strategies if s["type"]))
    return types


# ═══════════════════════════════════════════
#  策略分析
# ═══════════════════════════════════════════

def compare_strategies(strategy_ids: list = None) -> dict:
    """对比多个策略的绩效（回测结果）"""
    if strategy_ids:
        performances = []
        for sid in strategy_ids:
            perfs = get_strategy_perf(strategy_id=sid, limit=1)
            if perfs:
                performances.append(perfs[0])
    else:
        performances = get_strategy_perf(limit=100)

    if not performances:
        return {"summary": "暂无绩效数据", "strategies": []}

    result = {"strategies": performances}

    # 汇总统计
    with_perf = [p for p in performances if p.get("total_return") is not None]
    if with_perf:
        result["summary"] = {
            "count": len(with_perf),
            "avg_return": sum(p["total_return"] for p in with_perf) / len(with_perf),
            "avg_sharpe": sum(p["sharpe_ratio"] or 0 for p in with_perf) / len(with_perf),
            "avg_maxdd": sum(p["max_drawdown"] or 0 for p in with_perf) / len(with_perf),
            "best_return": max(with_perf, key=lambda p: p["total_return"]),
            "best_sharpe": max(with_perf, key=lambda p: p["sharpe_ratio"] or 0),
        }

    return result


def get_signals_by_code(code: str, days: int = 30) -> list:
    """查询某个标的所有策略的信号（用于 Dashboard 展示）"""
    return get_strategy_signals(code=code, limit=days)


def get_active_signal_summary(date: str = None) -> list:
    """获取某日所有策略信号汇总"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    signals = get_strategy_signals(limit=500)
    # 按日期过滤
    day_signals = [s for s in signals if s["date"] == date]
    return day_signals


# ═══════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════

def print_strategy_table(strategies: list):
    """打印策略列表"""
    if not strategies:
        print("  (空)")
        return
    print(f"  {'ID':>3} {'名称':24s} {'类型':12s} {'标的':12s} {'来源':20s}")
    print(f"  {'-'*75}")
    for s in strategies:
        print(f"  {s['id']:>3} {s['name']:24s} {s['type']:12s} "
              f"{s['target_type'] or '':12s} {(s['source'] or '')[:20]:20s}")


def print_strategy_detail(strategy: dict):
    """打印策略详情"""
    if not strategy:
        print("  未找到策略")
        return
    print(f"\n  {'='*50}")
    print(f"  策略详情")
    print(f"  {'='*50}")
    print(f"  ID:         {strategy['id']}")
    print(f"  名称:       {strategy['name']}")
    print(f"  类型:       {strategy['type']}")
    print(f"  标的:       {strategy['target_type'] or '-'}")
    print(f"  来源:       {strategy['source'] or '-'}")
    print(f"  URL:        {strategy['source_url'] or '-'}")
    print(f"  描述:       {strategy['description'] or '-'}")
    print(f"  参数:       {strategy['params'] or '-'}")
    print(f"  启用:       {'是' if strategy['enabled'] else '否'}")
    print(f"  创建:       {strategy['created_at']}")

    # 显示最近绩效
    perfs = get_strategy_perf(strategy_id=strategy["id"], limit=5)
    if perfs:
        print(f"\n  --- 绩效记录 ---")
        print(f"  {'日期':>10} {'收益%':>7} {'年化%':>7} {'最大回撤%':>9} {'夏普':>6} {'胜率%':>6}")
        print(f"  {'-'*50}")
        for p in perfs:
            print(f"  {p['created_at'][:10] if p.get('created_at') else '':>10} "
                  f"{p['total_return'] or 0:>7.2f} {p['annual_return'] or 0:>7.2f} "
                  f"{p['max_drawdown'] or 0:>9.2f} {p['sharpe_ratio'] or 0:>6.2f} "
                  f"{p['win_rate'] or 0:>6.1f}")


def cli(args: list):
    """命令行入口"""
    if not args:
        strategies = get_strategies()
        print(f"\n策略数据库 ({len(strategies)} 个策略)")
        print_strategy_table(strategies)
        return

    sub = args[0]

    if sub == "seed":
        count = seed_strategies()
        print(f"  种子数据加载完成")

    elif sub == "list":
        type_filter = args[1] if len(args) > 1 else None
        strategies = get_strategy_list(type_filter=type_filter)
        print(f"\n策略列表 ({len(strategies)} 个)")
        print_strategy_table(strategies)

    elif sub == "types":
        types = get_strategy_types()
        print(f"\n策略类型:")
        for t in types:
            count = len(get_strategy_list(type_filter=t))
            print(f"  {t}: {count}")

    elif sub == "info":
        if len(args) < 2:
            print("用法: python strategies_db.py info <name_or_id>")
            return
        strategy = get_strategy(args[1])
        print_strategy_detail(strategy)

    elif sub == "compare":
        ids = [int(x) for x in args[1:]] if len(args) > 1 else None
        result = compare_strategies(ids)
        strategies = result["strategies"]
        if not strategies:
            print("  暂无绩效数据")
            return
        best = sorted(strategies, key=lambda x: x.get("total_return") or 0, reverse=True)
        print(f"\n策略绩效对比:")
        print(f"  {'排名':>4} {'策略':22s} {'收益%':>7} {'年化%':>7} {'最大回撤%':>9} {'夏普':>6} {'胜率%':>6}")
        print(f"  {'-'*65}")
        for i, p in enumerate(best, 1):
            print(f"  {i:>4} {p['strategy_name']:22s} {p['total_return'] or 0:>7.2f} "
                  f"{p['annual_return'] or 0:>7.2f} {p['max_drawdown'] or 0:>9.2f} "
                  f"{p['sharpe_ratio'] or 0:>6.2f} {p['win_rate'] or 0:>6.1f}")

    else:
        print(f"未知: {sub}")
        print("可用: seed, list, types, info, compare")


if __name__ == "__main__":
    import sys
    cli(sys.argv[1:])
