"""RSI超买超卖策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import rsi
from signals.base import register


@register
class RSIReversalCalculator(BaseSignalCalculator):
    strategy_name = "RSI超买超卖"
    strategy_type = "技术指标"

    def __init__(self, params: dict = None):
        super().__init__(params or {"period": 14, "oversold": 30, "overbought": 70})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        period = int(self.params.get("period", 14))
        oversold = float(self.params.get("oversold", 30))
        overbought = float(self.params.get("overbought", 70))

        if len(close) < period + 3:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{period+3})",
                                {"required": period + 3, "got": len(close)})

        rsi_vals = rsi(close, period)
        cur = rsi_vals[-1]
        prev = rsi_vals[-2]

        if np.isnan(cur):
            return SignalResult("hold", 0.0, "RSI计算中")

        score = (50.0 - cur) / 50.0  # oversold→positive score

        if cur < oversold and prev < oversold:
            return SignalResult("buy", float(score),
                                f"超卖反弹(RSI={cur:.1f}<{oversold})",
                                {"RSI": round(float(cur), 1), "前日RSI": round(float(prev), 1)})
        elif cur > overbought and prev > overbought:
            return SignalResult("sell", float(score),
                                f"超买回落(RSI={cur:.1f}>{overbought})",
                                {"RSI": round(float(cur), 1), "前日RSI": round(float(prev), 1)})
        elif cur < oversold:
            return SignalResult("buy", float(score),
                                f"进入超卖区(RSI={cur:.1f})",
                                {"RSI": round(float(cur), 1)})
        elif cur > overbought:
            return SignalResult("sell", float(score),
                                f"进入超买区(RSI={cur:.1f})",
                                {"RSI": round(float(cur), 1)})
        else:
            return SignalResult("hold", float(score),
                                f"RSI中性({cur:.1f})",
                                {"RSI": round(float(cur), 1)})
