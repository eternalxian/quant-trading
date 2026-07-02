"""
入口：命令行选择要执行的操作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import FUNDS, ETF_WATCHLIST, ROTATION_ETF_CODES
from data import get_all_funds_nav, get_all_etfs
from portfolio import calc_portfolio, print_portfolio, apply_dca, settle_pending
from market import scan_market, print_market
from signals import generate_signals, print_signals, save_signals
from ai import ask_model, build_market_prompt, build_portfolio_prompt, DEFAULT_MODEL, REASONING_MODEL
from backtest.runner import run_backtest, print_results
from backtest.strategies import EtfRotationStrategy, MovingAverageCross
from holdings import get_all_holdings, aggregate_by_stock, search_stock, print_holdings, print_aggregated, print_search
from industry import (classify_holdings, aggregate_by_industry, aggregate_by_region,
                       get_multi_period_sector_performance, print_industry_breakdown, print_sector_performance)
from risk import get_all_risk_metrics, print_risk_metrics, print_correlation
from compare import get_comparison_data, print_comparison
from tradelog import (add_trade, get_trades, review_trades, get_trade_stats,
                       print_trades, print_review)
from alert import get_daily_alert_summary, print_alerts
from stock_db import load_db, get_stock_info, query_stock, seed_from_holdings, print_stock_info
from strategies_db import (get_strategies, get_strategy, get_strategy_types,
                           compare_strategies, print_strategy_table, print_strategy_detail)
from db import add_strategy_perf
from stock import (
    STOCK_WATCHLIST, get_stock_daily, get_stock_spot, get_all_stocks_daily,
    generate_stock_signals, rank_stocks, print_stock_spot, print_stock_rank,
)
from holdings import get_top_stocks
from stock_trading import (
    backtest_multi_strategies, print_backtest_result, print_backtest_compare,
    generate_plan, print_trading_plan,
)


def cmd_update():
    """更新数据缓存"""
    print("\n更新数据...")
    get_all_funds_nav(days=60)
    get_all_etfs(days=120)
    print("数据缓存已更新\n")


def cmd_portfolio():
    """显示持仓"""
    summary = calc_portfolio()
    print_portfolio(summary)


def cmd_market():
    """市场扫描"""
    report = scan_market()
    print_market(report)


def cmd_all_signals():
    """全部策略信号"""
    from signals import compute_all_signals, print_all_signals, list_calculators
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    if args and args[0] in ("list", "ls", "l"):
        print(f"\n已注册策略 ({len(list_calculators())} 个):")
        for i, name in enumerate(list_calculators(), 1):
            print(f"  {i:>3}. {name}")
        return

    print(f"\n生成全策略信号 ({len(list_calculators())} 个策略)...")
    etf_data = get_all_etfs(days=120)
    if not etf_data:
        print("  [错误] 无ETF数据")
        return

    results = compute_all_signals(etf_data)
    print_all_signals(results)


def cmd_train():
    """训练ML模型"""
    from signals.ml_trainer import train_all, train_lightgbm, train_lstm, train_catboost
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    print("\n拉取ETF数据用于训练...")
    etf_data = get_all_etfs(days=750)

    if not etf_data:
        print("  [错误] 无ETF数据")
        return

    model_arg = args[0] if args else "all"

    if model_arg in ("lightgbm", "all"):
        train_lightgbm(etf_data)
    if model_arg in ("catboost", "all"):
        train_catboost(etf_data)
    if model_arg in ("lstm", "all"):
        train_lstm(etf_data)
    if model_arg not in ("lightgbm", "catboost", "lstm", "all"):
        print(f"未知模型: {model_arg}")
        print("可用: lightgbm, catboost, lstm, all")
        return

    print("训练完成\n")


def cmd_analyze():
    """AI 全面分析：市场 + 持仓 + 信号"""
    print("\n拉取数据...")
    market_report = scan_market()
    portfolio_summary = calc_portfolio()
    signals = generate_signals(days=60)

    print_market(market_report)
    print_portfolio(portfolio_summary)
    print_signals(signals)

    print("调用 AI 分析...")
    prompt = build_portfolio_prompt(portfolio_summary, market_report)
    result = ask_model(prompt, model=DEFAULT_MODEL)

    print(f"\n{'='*50}")
    print("  AI 分析建议")
    print(f"{'='*50}")
    print(result)
    print(f"{'='*50}\n")


def cmd_signal():
    """ETF 轮动信号（不调用AI，只看数据）"""
    signals = generate_signals(days=60)
    print_signals(signals)
    save_signals(signals)


def cmd_holdings():
    """持仓穿透分析"""
    portfolio = calc_portfolio()
    fund_values = {}
    for item in portfolio["基金"]:
        if item["市值"] > 0:
            fund_values[item["code"]] = item["市值"]

    all_data = get_all_holdings(fund_values)
    agg = aggregate_by_stock(all_data)

    sub = sys.argv[2] if len(sys.argv) > 2 else ""
    if sub == "a" or sub == "agg":
        print_aggregated(agg)
    elif sub == "s" and len(sys.argv) > 3:
        results = search_stock(all_data, sys.argv[3])
        print_search(results, sys.argv[3])
    else:
        print_holdings(all_data)
        print_aggregated(agg)


def cmd_risk():
    """组合风险指标"""
    metrics = get_all_risk_metrics(days=250)
    print_risk_metrics(metrics)
    if metrics.get("correlation") is not None:
        print_correlation(metrics["correlation"])


def cmd_tradelog():
    """交易日志管理"""
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    if not args or args[0] in ("list", "ls", "l"):
        # 查询
        code = args[1] if len(args) > 1 else None
        trades = get_trades(code=code, limit=50)
        print_trades(trades)

        stats = get_trade_stats()
        if stats:
            print(f"  共 {stats['总交易数']} 笔交易")
            print(f"  总投入: {stats['总投入']:.0f}元 | 总卖出: {stats['总卖出']:.0f}元")

    elif args[0] in ("add", "a"):
        # 添加
        if len(args) < 3:
            print("用法: python main.py j add <代码> <操作> <金额> [理由]")
            print(f"  操作: {', '.join(['buy(买入)', 'sell(卖出)', 'dca(定投)'])}")
            return
        code = args[1]
        action = args[2]
        amount = float(args[3]) if len(args) > 3 else 0
        reason = " ".join(args[4:]) if len(args) > 4 else ""

        trade = add_trade(code, action, amount, reason=reason)
        if trade:
            print(f"  已记录: {trade['date']} {trade['action_cn']} {trade['name']} {trade['amount']:.0f}元")
            if trade.get("reason"):
                print(f"  理由: {trade['reason']}")

    elif args[0] in ("review", "r", "rv"):
        code = args[1] if len(args) > 1 else None
        results = review_trades(code=code)
        print_review(results)

    elif args[0] in ("stats", "s"):
        stats = get_trade_stats()
        if not stats:
            print("\n暂无交易记录\n")
            return
        print(f"\n{'='*40}")
        print(f"  交易统计")
        print(f"{'='*40}")
        print(f"  总交易数:  {stats['总交易数']}")
        print(f"  总投入:    {stats['总投入']:.0f}元")
        print(f"  总卖出:    {stats['总卖出']:.0f}元")
        print(f"  净投入:    {stats['净投入']:.0f}元")
        print(f"  买入次数:  {stats['买入次数']}")
        print(f"  卖出次数:  {stats['卖出次数']}")
        print(f"  涉及基金:  {stats['基金数']}只")
        print(f"{'='*40}\n")

    else:
        print(f"未知: {args[0]}")
        print("可用: list, add <code> <action> <amount> [reason], review, stats")


def cmd_alert():
    """净值异动提醒"""
    summary = get_daily_alert_summary()
    print_alerts(summary)


def cmd_stockdb():
    """公司信息库"""
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    if not args:
        db = load_db()
        print(f"\n公司信息库: {len(db)} 只股票")
        print(f"  美股/港股: {len([c for c in db if not c.isdigit()])} 只")
        print(f"  A股: {len([c for c in db if c.isdigit()])} 只")
        print(f"  用法: python main.py k <代码> 查看详情")
        print(f"        python main.py k list [关键词] 搜索")
        print(f"        python main.py k seed 从持仓重新填充")
        return

    if args[0] in ("list", "ls", "l"):
        keyword = args[1] if len(args) > 1 else ""
        results = query_stock(keyword)
        if not results:
            print(f"\n未找到匹配: {keyword}\n")
            return
        print(f"\n搜索 \"{keyword}\" 找到 {len(results)} 只:")
        for r in results:
            print(f"  {r['code']:>6s}  {r['name']}")
        print()
    elif args[0] == "seed":
        print("\n从持仓填充公司信息库...")
        portfolio = calc_portfolio()
        fund_values = {f["code"]: f["市值"] for f in portfolio["基金"] if f["市值"] > 0}
        all_data = get_all_holdings(fund_values)
        seed_from_holdings(all_data)
    else:
        code = args[0]
        print_stock_info(code)


def cmd_stock():
    """个股引擎：实时行情 + 全策略信号"""
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    if not args:
        # 默认：扫描 watchlist + 全信号排名
        if not STOCK_WATCHLIST:
            print("\n个股观察池为空。运行 'python main.py g seed' 从持仓穿透自动填充\n")
            return

        wl = STOCK_WATCHLIST
        print(f"\n拉取 {len(wl)} 只个股数据...")
        stocks_data = get_all_stocks_daily(wl, days=120)
        if not stocks_data:
            print("  无有效数据")
            return

        print(f"  已获取 {len(stocks_data)} 只 (>=30天)")
        print("运行全策略信号...")

        from signals import list_calculators
        strategies = list_calculators()
        print(f"  已注册 {len(strategies)} 个策略")

        signals = generate_stock_signals(stocks_data)
        rank = rank_stocks(signals)

        if rank.empty:
            print("\n暂无可排名个股信号\n")
            return

        try:
            spot = get_stock_spot(wl)
            if not spot.empty:
                print_stock_spot(spot)
        except Exception:
            pass

        print_stock_rank(rank, signals)
        return

    sub = args[0]

    if sub == "spot":
        if not STOCK_WATCHLIST:
            print("\n个股观察池为空\n")
            return
        spot = get_stock_spot(STOCK_WATCHLIST)
        print_stock_spot(spot)

    elif sub == "seed":
        print("\n从持仓穿透提取重仓股...")
        top = get_top_stocks(top_n=15)
        if not top:
            print("  未找到A股持仓（可能QDII基金为主）\n")
            return

        STOCK_WATCHLIST.clear()

        for code in top:
            try:
                from stock_db import load_db
                db = load_db()
                if code in db:
                    name = db[code].get("name", code)
                else:
                    name = code
            except Exception:
                name = code
            STOCK_WATCHLIST[code] = name

        print(f"  已填充 {len(STOCK_WATCHLIST)} 只个股:")
        for code, name in STOCK_WATCHLIST.items():
            print(f"    {code}  {name}")

        from stock import save_watchlist
        save_watchlist()
        print("  已保存到 data/stock_watchlist.json")
        print()

    elif sub == "add":
        if len(args) < 2:
            print("用法: python main.py g add <代码>")
            return
        code = args[1]
        from stock_db import load_db
        db = load_db()
        name = db.get(code, {}).get("name", code) if code in db else code
        STOCK_WATCHLIST[code] = name
        from stock import save_watchlist
        save_watchlist()
        print(f"\n已添加: {code} {name}\n")

    elif sub in ("list", "ls", "l"):
        if not STOCK_WATCHLIST:
            print("\n个股观察池为空\n")
            return
        print(f"\n个股观察池 ({len(STOCK_WATCHLIST)} 只):")
        for code, name in STOCK_WATCHLIST.items():
            print(f"  {code}  {name}")
        print()

    elif sub == "watch":
        codes = args[1:] if len(args) > 1 else None
        from stock_trading.monitor import run_monitor
        run_monitor(codes=codes)

    elif sub == "backtest":
        if len(args) < 2:
            print("用法: python main.py g backtest <代码> [策略名]")
            print("       python main.py g backtest <代码>  — 回测全部策略并排名")
            print("       python main.py g backtest <代码> ma_cross  — 回测指定策略")
            return
        code = args[1]
        strategy = args[2] if len(args) > 2 else None

        from config import STOCK_TRADING
        capital = STOCK_TRADING.get("default_capital", 100_000)

        # 获取名称
        name = STOCK_WATCHLIST.get(code, "")
        if not name:
            from stock_db import load_db
            db = load_db()
            name = db.get(code, {}).get("name", code)

        print(f"\n拉取 {code} {name} 日K线数据...")
        df = get_stock_daily(code, days=250)
        if df is None or len(df) < 60:
            print(f"  数据不足（需要至少60天K线）\n")
            return
        print(f"  已获取 {len(df)} 天数据")

        if strategy:
            # 单策略回测
            from stock_trading import backtest_stock
            result = backtest_stock(df, code=code, name=name,
                                    strategy_name=strategy,
                                    capital=capital,
                                    stop_atr_mult=STOCK_TRADING.get("default_stop_atr_mult", 2.0),
                                    verbose=True)
            print_backtest_result(result)
        else:
            # 多策略对比
            print("运行多策略回测...")
            results = backtest_multi_strategies(df, code=code, name=name,
                                                 capital=capital,
                                                 stop_atr_mult=STOCK_TRADING.get("default_stop_atr_mult", 2.0),
                                                 verbose=True)
            print_backtest_compare(results)

    elif sub == "plan":
        if len(args) < 2:
            print("用法: python main.py g plan <代码> [策略名]")
            return
        code = args[1]
        strategy = args[2] if len(args) > 2 else "双均线交叉"

        name = STOCK_WATCHLIST.get(code, "")
        if not name:
            from stock_db import load_db
            db = load_db()
            name = db.get(code, {}).get("name", code)

        from config import STOCK_TRADING
        from stock_trading.backtest import resolve_strategy
        capital = STOCK_TRADING.get("default_capital", 100_000)
        strategy = resolve_strategy(strategy)

        # 获取数据
        print(f"\n拉取 {code} {name} 数据...")
        df = get_stock_daily(code, days=120)
        if df is None or len(df) < 30:
            print(f"  数据不足\n")
            return

        # 获取实时行情
        spot = {}
        try:
            spot_df = get_stock_spot({code: name})
            if not spot_df.empty:
                row = spot_df.iloc[0]
                raw_change = row.get("change_pct", 0) or 0
                spot = {
                    "price": row.get("price", float(df.iloc[-1]["close"])),
                    "change_pct": raw_change / 100.0,  # AKShare 返回的是百分数（如 1.14 代表 1.14%），转为小数
                    "prev_close": row.get("price", float(df.iloc[-1]["close"]))
                        / (1 + raw_change / 100.0) if raw_change != 0 else float(df.iloc[-2]["close"]) if len(df) > 1 else float(df.iloc[-1]["close"]),
                }
        except Exception:
            spot = {
                "price": float(df.iloc[-1]["close"]),
                "change_pct": 0,
                "prev_close": float(df.iloc[-2]["close"]) if len(df) > 1 else float(df.iloc[-1]["close"]),
            }

        # 生成信号
        from signals import compute_all_signals
        signals = compute_all_signals({code: df}, strategy_names=[strategy], persist=False)
        sig = signals.get(strategy, {}).get(code)
        signal = sig.signal if sig else "hold"
        score = sig.score if sig else 0
        reason = sig.reason if sig else ""

        # 生成计划
        plan = generate_plan(
            code=code, name=name, df=df, spot=spot,
            signal=signal, signal_score=score, signal_reason=reason,
            capital=capital,
        )
        if plan:
            print_trading_plan(plan)
        else:
            print(f"\n无法生成交易计划（数据不足）\n")

    elif sub == "compare":
        if len(args) < 3:
            print("用法: python main.py g compare <代码1> <代码2> [代码3...]")
            return
        codes = args[1:]

        from config import STOCK_TRADING
        capital = STOCK_TRADING.get("default_capital", 100_000)

        all_results = []
        for code in codes:
            name = STOCK_WATCHLIST.get(code, "")
            if not name:
                from stock_db import load_db
                db = load_db()
                name = db.get(code, {}).get("name", code)

            print(f"\n回测 {code} {name}...")
            df = get_stock_daily(code, days=250)
            if df is None or len(df) < 60:
                print(f"  数据不足，跳过")
                continue

            results = backtest_multi_strategies(df, code=code, name=name,
                                                 capital=capital,
                                                 stop_atr_mult=STOCK_TRADING.get("default_stop_atr_mult", 2.0),
                                                 verbose=False)
            if results:
                all_results.append(results[0])  # 取每只股票的最佳策略

        if not all_results:
            print("\n无有效回测结果\n")
            return

        # 横向对比
        print(f"\n{'='*90}")
        print(f"  个股横向对比（每只股票取最佳策略）")
        print(f"{'='*90}")
        print(f"  {'股票':<20s} {'最佳策略':<22s} {'总收益':>8s} {'夏普':>7s} "
              f"{'回撤':>7s} {'胜率':>7s} {'盈亏比':>7s}")
        print(f"  {'-'*80}")
        for r in sorted(all_results, key=lambda x: x.total_return, reverse=True):
            name_str = f"{r.code} {r.name}" if r.name else r.code
            print(f"  {name_str:<20s} {r.strategy:<22s} {r.total_return:>+7.2%} "
                  f"{r.sharpe:>6.2f} {r.max_drawdown:>6.2%} "
                  f"{r.win_rate:>6.1%} {r.profit_factor:>6.2f}")
        print(f"{'='*90}\n")

    else:
        print(f"未知: {sub}")
        print("可用: g(信号排名), spot(快照), seed(填充), add <code>, list, "
              "watch, backtest <code>, plan <code>, compare <code1> <code2>")


def cmd_strategies():
    """策略数据库"""
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    if not args or args[0] in ("list", "ls", "l"):
        type_filter = args[1] if len(args) > 1 and args[0] not in ("list", "ls", "l") else None
        strategies = get_strategies()
        print(f"\n策略数据库 ({len(strategies)} 个策略)")
        print_strategy_table(strategies)
        print(f"\n  用法: python main.py y <命令>")
        print(f"        list [type]   按类型筛选")
        print(f"        info <id|name>  查看详情")
        print(f"        types         查看分类")
        print(f"        compare [id...] 绩效对比")

    elif args[0] in ("info", "i"):
        if len(args) < 2:
            print("用法: python main.py y info <id_or_name>")
            return
        s = get_strategy(args[1])
        print_strategy_detail(s)

    elif args[0] == "types":
        types = get_strategy_types()
        print(f"\n策略分类:")
        for t in types:
            count = len([s for s in get_strategies() if s["type"] == t])
            print(f"  {t}: {count}个")

    elif args[0] == "compare":
        ids = [int(x) for x in args[1:]] if len(args) > 1 else None
        result = compare_strategies(ids)
        if not result["strategies"]:
            print("\n暂无绩效对比数据（运行回测后会自动记录）\n")
        else:
            strategies = result["strategies"]
            best = sorted(strategies, key=lambda x: x.get("total_return") or 0, reverse=True)
            print(f"\n策略绩效对比:")
            print(f"  {'排名':>4} {'策略':22s} {'收益%':>7} {'年化%':>7} {'最大回撤%':>9} {'夏普':>6} {'胜率%':>6}")
            print(f"  {'-'*65}")
            for i, p in enumerate(best, 1):
                print(f"  {i:>4} {p['strategy_name']:22s} {p['total_return'] or 0:>7.2f} "
                      f"{p['annual_return'] or 0:>7.2f} {p['max_drawdown'] or 0:>9.2f} "
                      f"{p['sharpe_ratio'] or 0:>6.2f} {p['win_rate'] or 0:>6.1f}")

    else:
        print(f"未知: {args[0]}")
        print("可用: list, info <id>, types, compare [id...]")


def cmd_compare():
    """业绩对比报告"""
    data = get_comparison_data(days=365)
    print_comparison(data)


def cmd_industry():
    """行业全景分析"""
    portfolio = calc_portfolio()
    fund_values = {f["code"]: f["市值"] for f in portfolio["基金"] if f["市值"] > 0}
    all_data = get_all_holdings(fund_values)

    # 持仓行业分类
    df = classify_holdings(all_data)
    industry_df = aggregate_by_industry(df)
    region_df = aggregate_by_region(df)

    sub = sys.argv[2] if len(sys.argv) > 2 else ""
    if sub == "sector" or sub == "m" or sub == "market":
        perf = get_multi_period_sector_performance()
        print_sector_performance(perf)
    elif sub == "r" or sub == "region":
        print_industry_breakdown(region_df, "地域分布")
    else:
        print_industry_breakdown(industry_df, "持仓行业分布")
        print_industry_breakdown(region_df, "地域分布")
        perf = get_multi_period_sector_performance()
        if not perf.empty:
            print_sector_performance(perf)


def cmd_backtest():
    """回测 ETF 轮动策略（回归斜率评分版）"""
    print("\n拉取 ETF 数据...")
    etf_data = get_all_etfs(days=250)

    data_dict = {}
    for code in ROTATION_ETF_CODES:
        if code in etf_data and not etf_data[code].empty:
            data_dict[code] = etf_data[code]
            print(f"  {code} {ROTATION_ETF_CODES[code]}: {len(etf_data[code])} 条")

    if len(data_dict) < 2:
        print("数据不足，至少需要2支 ETF")
        return

    # 回测：回归斜率评分版
    analysis, _ = run_backtest(
        EtfRotationStrategy,
        data_dict,
        cash=100000.0,
        score_window=25,
        rebalance_days=20,
        top_n=1,
    )
    print_results(analysis)

    # 记录到策略数据库
    try:
        s = get_strategy("ETF轮动-回归斜率评分")
        if s:
            ret = float(analysis.get("总收益率", "0%").replace("%", ""))
            ann = float(analysis.get("年化收益率", "0%").replace("%", ""))
            dd = float(analysis.get("最大回撤", "0%").replace("%", ""))
            sharpe = float(analysis.get("夏普比率", 0))
            add_strategy_perf(s["id"], total_return=ret, annual_return=ann,
                              max_drawdown=dd, sharpe_ratio=sharpe,
                              note="ETF轮动回测(回归斜率评分版)")
    except Exception as e:
        print(f"  [记录绩效] {e}")

    # AI 解读
    print("调用 AI 解读回测结果...")
    analysis_text = "\n".join(f"{k}: {v}" for k, v in analysis.items())
    etf_names = ", ".join(ROTATION_ETF_CODES[c] for c in ROTATION_ETF_CODES)
    prompt = f"""基于以下回测结果，给出策略评价和改进建议：

策略：ETF 轮动（线性回归斜率×R²评分，每月调仓到评分最高的一支）
标的：{etf_names}

回测结果：
{analysis_text}

请分析：
1. 这个策略表现如何？收益和风险是否匹配
2. 最大回撤的原因可能是什么
3. 改进方向
4. 是否适应当前市场环境
"""
    result = ask_model(prompt, model=REASONING_MODEL)
    print(f"\n{'='*50}")
    print("  AI 策略分析")
    print(f"{'='*50}")
    print(result)
    print(f"{'='*50}\n")


def cmd_full():
    """完整流程：信号 → AI分析 → 操作建议"""
    print("\n=== 完整分析流程 ===")

    # 1. 信号
    print(">> 1/3 ETF 轮动信号")
    signals = generate_signals(days=60)
    print_signals(signals)

    # 2. 市场 + 持仓
    print(">> 2/3 市场 & 持仓")
    market_report = scan_market()
    portfolio_summary = calc_portfolio()
    print_market(market_report)
    print_portfolio(portfolio_summary)

    # 3. AI 综合建议
    print(">> 3/3 AI 综合建议")
    # 把信号也喂给 AI
    signal_summary = signals["综合建议"] if signals["信号"] else "暂无信号"
    prompt = build_portfolio_prompt(portfolio_summary, market_report)
    prompt += f"\n\n附：当前ETF轮动信号 — {signal_summary}\n请结合轮动信号，给出今日具体操作建议。"

    result = ask_model(prompt, model=DEFAULT_MODEL)
    print(f"\n{'='*50}")
    print("  AI 综合建议")
    print(f"{'='*50}")
    print(result)
    print(f"{'='*50}\n")


def cmd_pl():
    """盈亏看板"""
    summary = calc_portfolio()
    print(f"\n{'='*50}")
    print(f"  盈亏总览  {summary['日期']}")
    print(f"{'='*50}")
    print(f"  总资产:   {summary['总资产']:>8.2f}")
    print(f"  总成本:   {summary['总成本']:>8.2f}")
    print(f"  总盈亏:   {summary['总盈亏']:+.2f}  ({summary['总盈亏率']:+.2f}%)")
    print(f"  {'-'*30}")
    print(f"  基金市值: {summary['基金市值']:>8.2f}")
    print(f"  基金成本: {summary['基金成本']:>8.2f}")
    print(f"  基金盈亏: {summary['基金盈亏']:+.2f}")
    print(f"  余额宝:   {summary['余额宝']:>8.2f}")
    print(f"{'='*50}")

    # 按盈亏排序显示
    funds = [f for f in summary["基金"] if f["市值"] > 0]
    funds.sort(key=lambda x: x["盈亏"], reverse=True)
    for item in funds:
        pl = item["盈亏"]
        pl_str = f"{pl:+.1f}"
        print(f"  {pl_str:>8s}  {item['code']} {item['name']}")
    print(f"{'='*50}\n")


def cmd_daily():
    """每日例行：更新数据 + DCA + 自动结算 + AI分析"""
    print("\n=== 每日例行 ===")
    cmd_update()

    # DCA 定投
    print("\n--- 定投 ---")
    dca_today = apply_dca()
    if dca_today:
        for code, amount in dca_today.items():
            print(f"  记录定投 {code}: {amount}元 → 待确认")
    else:
        print(f"  今日定投已执行过，跳过")

    # 自动结算
    settled = settle_pending()
    if settled:
        print(f"\n--- 自动结算 ---")
        for s in settled:
            print(f"  {s['code']} 到账: {s['shares']:.2f}份 × 净值{s['nav']:.4f}  (金额{s['amount']:.0f}元)")
    else:
        print(f"  无待结算项")

    # 异动提醒
    print("\n--- 净值异动 ---")
    cmd_alert()

    cmd_analyze()


def cmd_dca():
    """定投管理"""
    cmd = input("  (a)应用今日定投  (s)结算pending  (v)查看状态 > ").strip().lower()
    if cmd == "a":
        result = apply_dca()
        if result:
            for code, amount in result.items():
                print(f"  记录定投 {code}: {amount}元")
        else:
            print("  今日定投已执行过")
    elif cmd == "s":
        settled = settle_pending()
        if settled:
            for s in settled:
                print(f"  {s['code']} 到账: {s['shares']:.2f}份 × 净值{s['nav']:.4f}")
        else:
            print("  无可结算项")
    elif cmd == "v":
        print_dca_status()
    else:
        print("  未知命令")


def print_menu():
    print(f"\n{'='*50}")
    print(f"  量化分析系统 v2")
    print(f"{'='*50}")
    print(f"  f) 更新数据 (fetch)")
    print(f"  p) 查看持仓 (portfolio)")
    print(f"  m) 市场扫描 (market)")
    print(f"  s) ETF轮动信号 (signal)")
    print(f"  S) 全策略信号 (all signals)")
    print(f"  a) AI 全面分析 (analyze)")
    print(f"  c) 完整流程 (full)")
    print(f"  l) 盈亏看板 (pnl)")
    print(f"  t) 定投管理 (dca)")
    print(f"  b) 回测策略 (backtest)")
    print(f"  h) 持仓穿透 (holdings)")
    print(f"  i) 行业分析 (industry)")
    print(f"  r) 风险指标 (risk)")
    print(f"  v) 业绩对比 (compare)")
    print(f"  j) 交易日志 (journal)")
    print(f"  n) 异动提醒 (alert)")
    print(f"  k) 公司信息 (stockdb)")
    print(f"  y) 策略数据库 (strategies)")
    print(f"  g) 个股信号 (stock signal)")
    print(f"  T) 训练ML模型 (train)")
    print(f"  d) 每日例行 (daily)")
    print(f"  q) 退出")
    print(f"{'='*50}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "f":
            cmd_update()
        elif cmd == "p":
            cmd_portfolio()
        elif cmd == "m":
            cmd_market()
        elif cmd == "s":
            cmd_signal()
        elif cmd == "S":
            cmd_all_signals()
        elif cmd == "a":
            cmd_analyze()
        elif cmd == "c":
            cmd_full()
        elif cmd == "l":
            cmd_pl()
        elif cmd in ("t", "dca"):
            cmd_dca()
        elif cmd == "b":
            cmd_backtest()
        elif cmd == "d":
            cmd_daily()
        elif cmd in ("h", "holdings"):
            cmd_holdings()
        elif cmd in ("i", "industry"):
            cmd_industry()
        elif cmd in ("r", "risk"):
            cmd_risk()
        elif cmd in ("v", "compare"):
            cmd_compare()
        elif cmd in ("j", "journal", "tradelog"):
            cmd_tradelog()
        elif cmd in ("n", "alert"):
            cmd_alert()
        elif cmd in ("k", "stockdb"):
            cmd_stockdb()
        elif cmd in ("y", "strategy"):
            cmd_strategies()
        elif cmd in ("g", "stock"):
            cmd_stock()
        elif cmd == "T":
            cmd_train()
        else:
            print(f"未知命令: {cmd}")
            print("可用: f(更新) p(持仓) m(市场) s(信号) S(全策略) a(分析) c(完整流程) b(回测) d(日常) h(持仓穿透) i(行业) r(风险) v(业绩) j(交易日志) n(异动) k(公司信息) y(策略) g(个股) T(训练)")
    else:
        while True:
            print_menu()
            choice = input("选择 > ").strip().lower()
            if choice == "q":
                break
            elif choice == "f":
                cmd_update()
            elif choice == "p":
                cmd_portfolio()
            elif choice == "m":
                cmd_market()
            elif choice == "s":
                cmd_signal()
            elif choice == "S":
                cmd_all_signals()
            elif choice == "a":
                cmd_analyze()
            elif choice == "c":
                cmd_full()
            elif choice == "l":
                cmd_pl()
            elif choice in ("t", "dca"):
                cmd_dca()
            elif choice == "b":
                cmd_backtest()
            elif choice in ("h", "holdings"):
                cmd_holdings()
            elif choice in ("i", "industry"):
                cmd_industry()
            elif choice in ("r", "risk"):
                cmd_risk()
            elif choice in ("v", "compare"):
                cmd_compare()
            elif choice in ("j", "journal"):
                print("交易日志子命令: add/list/review/stats")
                sub = input("  > ").strip().split()
                if sub:
                    orig = sys.argv
                    sys.argv = ["main.py", "j"] + sub
                    cmd_tradelog()
                    sys.argv = orig
            elif choice in ("n", "alert"):
                cmd_alert()
            elif choice in ("k", "stockdb"):
                print("公司信息子命令: <代码> / list / seed")
                sub = input("  > ").strip()
                if sub:
                    orig = sys.argv
                    sys.argv = ["main.py", "k"] + sub.split()
                    cmd_stockdb()
                    sys.argv = orig
            elif choice in ("y", "strategy"):
                print("策略子命令: list / info / types / compare")
                sub = input("  > ").strip().split()
                if sub:
                    orig = sys.argv
                    sys.argv = ["main.py", "y"] + sub
                    cmd_strategies()
                    sys.argv = orig
            elif choice == "T":
                cmd_train()
            elif choice == "d":
                cmd_daily()
            elif choice == "g":
                print("个股子命令: spot(快照) seed(填充) add(加股) list(看池) watch(监控) backtest(回测) plan(计划) compare(对比)")
                sub = input("  > ").strip()
                if sub:
                    orig = sys.argv
                    sys.argv = ["main.py", "g"] + sub.split()
                    cmd_stock()
                    sys.argv = orig
            else:
                print("无效选择")
