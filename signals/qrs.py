"""QRS量化RS策略（改进版相对强弱）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import sma
from signals.base import register


@register
class QRSCalculator(BaseSignalCalculator):
    strategy_name = "QRS量化RS"
    strategy_type = "统计套利"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 20, "smooth_period": 5})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        lookback = int(self.params.get("lookback", 20))
        smooth = int(self.params.get("smooth_period", 5))

        min_len = lookback + smooth + 2
        if len(close) < min_len:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{min_len})",
                                {"required": min_len, "got": len(close)})

        # QRS = smoothed ROC / smoothed volatility
        roc = np.zeros(len(close))
        roc[1:] = close[1:] / close[:-1] - 1
        smooth_roc = sma(roc, smooth)
        smooth_vol = sma(np.abs(roc), smooth)

        qrs = np.zeros(len(close))
        for i in range(min_len - 1, len(close)):
            if smooth_vol[i] > 0 and not np.isnan(smooth_vol[i]):
                qrs[i] = smooth_roc[i] / smooth_vol[i]

        cur = qrs[-1]
        if np.isnan(cur):
            return SignalResult("hold", 0.0, "QRS计算中")

        score = float(cur)
        if score > 0.5:
            return SignalResult("buy", score, f"相对走强(QRS={score:.2f})",
                                {"QRS": round(float(cur), 4)})
        elif score < -0.5:
            return SignalResult("sell", score, f"相对走弱(QRS={score:.2f})",
                                {"QRS": round(float(cur), 4)})
        else:
            return SignalResult("hold", score, f"QRS中性({score:.2f})",
                                {"QRS": round(float(cur), 4)})
