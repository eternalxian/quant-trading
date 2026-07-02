"""布林带反转策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import bollinger
from signals.base import register


@register
class BollingerReversalCalculator(BaseSignalCalculator):
    strategy_name = "布林带反转"
    strategy_type = "技术指标"

    def __init__(self, params: dict = None):
        super().__init__(params or {"period": 20, "std": 2, "band_shrink_threshold": 0.05})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        period = int(self.params.get("period", 20))
        std_mul = float(self.params.get("std", 2))
        shrink_th = float(self.params.get("band_shrink_threshold", 0.05))

        if len(close) < period + 2:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{period+2})",
                                {"required": period + 2, "got": len(close)})

        mid, upper, lower, bw = bollinger(close, period, std_mul)
        cur_close = close[-1]
        cur_mid = mid[-1]
        cur_upper = upper[-1]
        cur_lower = lower[-1]
        cur_bw = bw[-1]

        if np.isnan(cur_mid):
            return SignalResult("hold", 0.0, "布林带计算中")

        # Price position: 0=mid, +1=upper, -1=lower
        if cur_upper > cur_lower:
            pos = (cur_close - cur_lower) / (cur_upper - cur_lower) * 2 - 1
        else:
            pos = 0
        score = -pos  # 反转: lower band = bullish

        # Band squeeze detection
        if not np.isnan(bw[-2]) and cur_bw < shrink_th and bw[-2] < shrink_th:
            squeeze_note = "，带宽收窄或预示突破"
        else:
            squeeze_note = ""

        if cur_close < cur_lower:
            return SignalResult("buy", float(score),
                                f"跌破下轨反弹({cur_close:.3f}<{cur_lower:.3f}){squeeze_note}",
                                {"upper": round(float(cur_upper), 4), "mid": round(float(cur_mid), 4),
                                 "lower": round(float(cur_lower), 4), "bw": round(float(cur_bw), 4)})
        elif cur_close > cur_upper:
            return SignalResult("sell", float(score),
                                f"突破上轨回落({cur_close:.3f}>{cur_upper:.3f}){squeeze_note}",
                                {"upper": round(float(cur_upper), 4), "mid": round(float(cur_mid), 4),
                                 "lower": round(float(cur_lower), 4), "bw": round(float(cur_bw), 4)})
        elif pos < -0.8:
            return SignalResult("hold", float(score),
                                f"接近下轨({cur_close:.3f}){squeeze_note}",
                                {"pos": round(float(pos), 2)})
        elif pos > 0.8:
            return SignalResult("hold", float(score),
                                f"接近上轨({cur_close:.3f}){squeeze_note}",
                                {"pos": round(float(pos), 2)})
        else:
            return SignalResult("hold", float(score),
                                f"布林带中轨附近({cur_close:.3f}){squeeze_note}",
                                {"pos": round(float(pos), 2)})
