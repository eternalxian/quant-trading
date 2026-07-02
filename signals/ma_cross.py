"""双均线交叉策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import sma, ema
from signals.base import register


@register
class MovingAverageCrossCalculator(BaseSignalCalculator):
    strategy_name = "双均线交叉"
    strategy_type = "趋势跟踪"

    def __init__(self, params: dict = None):
        super().__init__(params or {"fast": 5, "slow": 20, "type": "SMA"})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        fast_p = int(self.params.get("fast", 5))
        slow_p = int(self.params.get("slow", 20))
        ma_type = self.params.get("type", "SMA")

        min_len = max(fast_p, slow_p) + 2
        if len(close) < min_len:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{min_len})",
                                {"required": min_len, "got": len(close)})

        fn = sma if ma_type == "SMA" else ema
        fast_ma = fn(close, fast_p)
        slow_ma = fn(close, slow_p)

        cur = fast_ma[-1] - slow_ma[-1]
        prev = fast_ma[-2] - slow_ma[-2]
        ratio = fast_ma[-1] / slow_ma[-1] - 1 if slow_ma[-1] > 0 else 0

        if cur > 0 and prev <= 0:
            return SignalResult("buy", float(ratio), f"金叉(快线{fast_p}上穿慢线{slow_p})",
                                {"fast": round(float(fast_ma[-1]), 4), "slow": round(float(slow_ma[-1]), 4)})
        elif cur < 0 and prev >= 0:
            return SignalResult("sell", float(ratio), f"死叉(快线{fast_p}下穿慢线{slow_p})",
                                {"fast": round(float(fast_ma[-1]), 4), "slow": round(float(slow_ma[-1]), 4)})
        elif cur > 0:
            return SignalResult("hold", float(ratio), f"快线在慢线上方，趋势偏多",
                                {"fast": round(float(fast_ma[-1]), 4), "slow": round(float(slow_ma[-1]), 4)})
        else:
            return SignalResult("hold", float(ratio), f"快线在慢线下方，趋势偏空",
                                {"fast": round(float(fast_ma[-1]), 4), "slow": round(float(slow_ma[-1]), 4)})
