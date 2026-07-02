"""鳄鱼线趋势策略（Bill Williams Alligator）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import alligator
from signals.base import register


@register
class AlligatorTrendCalculator(BaseSignalCalculator):
    strategy_name = "鳄鱼线趋势"
    strategy_type = "趋势跟踪"

    def __init__(self, params: dict = None):
        super().__init__(params or {"blue_period": 13, "red_period": 8, "green_period": 5,
                                     "shift": 8})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        jaw_p = int(self.params.get("blue_period", 13))
        teeth_p = int(self.params.get("red_period", 8))
        lips_p = int(self.params.get("green_period", 5))
        shift = int(self.params.get("shift", 8))

        min_len = jaw_p + shift + 2
        if len(close) < min_len:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{min_len})",
                                {"required": min_len, "got": len(close)})

        jaw, teeth, lips = alligator(close, jaw_p, teeth_p, lips_p, shift, int(shift * 0.625), int(shift * 0.375))

        cur_j, cur_t, cur_l = jaw[-1], teeth[-1], lips[-1]
        if np.isnan(cur_j) or np.isnan(cur_t) or np.isnan(cur_l):
            return SignalResult("hold", 0.0, "鳄鱼线计算中")

        cur_close = close[-1]
        above_jaw = cur_close > cur_j
        above_teeth = cur_close > cur_t
        above_lips = cur_close > cur_l

        # Check if lines are ordered (jaw < teeth < lips = bullish alignment)
        ordered_bull = cur_l > cur_t > cur_j
        ordered_bear = cur_l < cur_t < cur_j

        # Score based on position relative to alligator
        if cur_j > 0:
            score = float(cur_close / cur_j - 1)
        else:
            score = 0.0

        if ordered_bull and above_lips:
            return SignalResult("buy", score,
                                f"鳄鱼张口向上，价格在线上方(多头发散)",
                                {"jaw": round(float(cur_j), 4), "teeth": round(float(cur_t), 4),
                                 "lips": round(float(cur_l), 4)})
        elif ordered_bear and not above_jaw:
            return SignalResult("sell", score,
                                f"鳄鱼张口向下，价格在线下方(空头发散)",
                                {"jaw": round(float(cur_j), 4), "teeth": round(float(cur_t), 4),
                                 "lips": round(float(cur_l), 4)})
        elif not ordered_bull and not ordered_bear:
            return SignalResult("hold", 0.0,
                                "鳄鱼线缠绕，处于休眠期(无趋势)",
                                {"jaw": round(float(cur_j), 4), "teeth": round(float(cur_t), 4),
                                 "lips": round(float(cur_l), 4)})
        elif above_jaw:
            return SignalResult("hold", score, "价格在鳄鱼线上方，偏多",
                                {"jaw": round(float(cur_j), 4)})
        else:
            return SignalResult("hold", score, "价格在鳄鱼线下方，偏空",
                                {"jaw": round(float(cur_j), 4)})
