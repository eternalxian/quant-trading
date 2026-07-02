"""
回测运行器：用 Backtrader 跑策略回测
"""
import os
import backtrader as bt
import pandas as pd
from datetime import datetime
from data import DATA_DIR


class PandasData(bt.feeds.PandasData):
    """将 pandas DataFrame 转为 Backtrader 数据源"""
    params = (
        ("datetime", "日期"),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("openinterest", -1),
    )


def run_backtest(strategy_cls, data_dict: dict, cash=100000.0, **strategy_params):
    """
    运行回测
    data_dict: {code: DataFrame} 包含 '日期' 'open' 'high' 'low' 'close' 'volume' 列
    """
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy_cls, **strategy_params)
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=0.0003)  # 万三

    for code, df in data_dict.items():
        df = df.copy()
        df["日期"] = pd.to_datetime(df["日期"])
        df.set_index("日期", inplace=True)
        data = PandasData(dataname=df)
        cerebro.adddata(data, name=code)

    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

    print(f"\n开始回测...  初始资金: {cash:,.2f}")
    results = cerebro.run()
    print("回测完成")

    strat = results[0]
    analysis = {}

    # 提取分析结果
    ret = strat.analyzers.returns.get_analysis()
    analysis["总收益率"] = f"{ret.get('rtot', 0)*100:.2f}%"
    analysis["年化收益率"] = f"{ret.get('rnorm100', 0):.2f}%"

    sharpe = strat.analyzers.sharpe.get_analysis()
    analysis["夏普比率"] = round(sharpe.get("sharperatio", 0) or 0, 2)

    dd = strat.analyzers.drawdown.get_analysis()
    analysis["最大回撤"] = f"{dd.get('max', {}).get('drawdown', 0):.2f}%"

    final_value = cerebro.broker.getvalue()
    analysis["最终资产"] = f"{final_value:,.2f}"
    analysis["净利润"] = f"{final_value - cash:+,.2f}"

    return analysis, cerebro


def print_results(analysis: dict):
    """打印回测结果"""
    print(f"\n{'='*50}")
    print(f"  回测结果")
    print(f"{'='*50}")
    for k, v in analysis.items():
        print(f"  {k}: {v}")
    print(f"{'='*50}\n")
