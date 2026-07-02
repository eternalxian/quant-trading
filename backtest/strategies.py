"""
策略定义：可回测的交易策略
集成 vnpy EtfRotationStrategy 核心逻辑（回归斜率 x R² 评分）
"""
import backtrader as bt
import numpy as np
from sklearn.linear_model import LinearRegression  # noqa: F811
from datetime import datetime


class LinearRegressionScore:
    """
    线性回归斜率 × R² 评分
    来源：vnpy EtfRotationStrategy
    比简单N日动量更平滑，抗噪声更好
    """
    def __init__(self, window: int = 25):
        self.window = window

    def calculate(self, data: np.ndarray) -> float:
        if len(data) < self.window:
            return 0.0
        x = np.arange(1, self.window + 1).reshape(-1, 1)
        y = (data[-self.window:] / data[-self.window]).reshape(-1, 1)
        reg = LinearRegression().fit(x, y)
        slope = reg.coef_[0][0]
        r2 = reg.score(x, y)
        return slope * r2


class ClassicMomentum:
    """简单N日动量（备选评分方式）"""
    def __init__(self, window: int = 20):
        self.window = window

    def calculate(self, data: np.ndarray) -> float:
        if len(data) < self.window:
            return 0.0
        return data[-1] / data[-self.window] - 1


# ── 可回测策略 ──

class EtfRotationStrategy(bt.Strategy):
    """
    ETF 动量轮动策略（回归斜率评分版）
    来源：vnpy EtfRotationStrategy 思路
    """
    params = (
        ("score_window", 25),     # 评分周期
        ("rebalance_days", 20),   # 调仓频率（交易日）
        ("top_n", 1),             # 持有前几名
        ("scoring", "regression"), # regression 或 momentum
    )

    def __init__(self):
        self.datas_by_code = {}
        self.bar_count = 0

        for d in self.datas:
            code = d._name.split(".")[0]
            self.datas_by_code[code] = d

        self.codes = list(self.datas_by_code.keys())

        if self.p.scoring == "regression":
            self.scorer = LinearRegressionScore(window=self.p.score_window)
        else:
            self.scorer = ClassicMomentum(window=self.p.score_window)

        self.order = None

    def next(self):
        self.bar_count += 1
        if self.bar_count < self.p.score_window:
            return

        # 每 rebalance_days 天调仓
        if self.bar_count % self.p.rebalance_days != 0:
            return

        # 计算评分
        scores = {}
        for code, d in self.datas_by_code.items():
            close_arr = np.array(d.close.get(size=self.p.score_window))
            scores[code] = self.scorer.calculate(close_arr)

        if not scores:
            return

        # 选评分最高的 top_n
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winners = [c for c, s in ranked[:self.p.top_n] if s > 0]

        # 如果没有正分的，全仓现金
        if not winners:
            for code, d in self.datas_by_code.items():
                pos = self.getposition(d).size
                if pos > 0:
                    self.close(data=d)
            return

        # 卖出不在 winner 中的
        for code, d in self.datas_by_code.items():
            if code not in winners:
                pos = self.getposition(d).size
                if pos > 0:
                    self.close(data=d)

        # 等权买入 winners
        target_pct = 0.95 / len(winners)
        for code in winners:
            d = self.datas_by_code[code]
            if self.getposition(d).size == 0:
                self.order_target_percent(data=d, target=target_pct)


class MovingAverageCross(bt.Strategy):
    """
    双均线交叉策略：单 ETF 使用
    短期均线上穿长期均线买入，反之卖出
    """
    params = (
        ("short", 5),
        ("long", 20),
    )

    def __init__(self):
        self.sma_short = bt.indicators.SMA(self.data.close, period=self.p.short)
        self.sma_long = bt.indicators.SMA(self.data.close, period=self.p.long)
        self.crossover = bt.indicators.CrossOver(self.sma_short, self.sma_long)
        self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.order = self.sell()
