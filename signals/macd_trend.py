"""MACD趋势跟踪策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import macd
from signals.base import register


@register
class MACDTrendCalculator(BaseSignalCalculator):
    strategy_name = "MACD趋势跟踪"
    strategy_type = "趋势跟踪"

    def __init__(self, params: dict = None):
        super().__init__(params or {"fast": 12, "slow": 26, "signal": 9})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        fast_p = int(self.params.get("fast", 12))
        slow_p = int(self.params.get("slow", 26))
        sig_p = int(self.params.get("signal", 9))

        min_len = slow_p + sig_p + 2
        if len(close) < min_len:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{min_len})",
                                {"required": min_len, "got": len(close)})

        dif, dea, hist = macd(close, fast_p, slow_p, sig_p)

        cur_dif, cur_dea = dif[-1], dea[-1]
        prev_dif, prev_dea = dif[-2], dea[-2]
        cur_hist = hist[-1]

        cross_up = cur_dif > cur_dea and prev_dif <= prev_dea
        cross_down = cur_dif < cur_dea and prev_dif >= prev_dea
        score = float(cur_dif - cur_dea) if not np.isnan(cur_dif) and not np.isnan(cur_dea) else 0.0

        if cross_up:
            return SignalResult("buy", score, "MACD金叉(DIF上穿DEA)",
                                {"DIF": round(float(cur_dif), 4), "DEA": round(float(cur_dea), 4),
                                 "柱": round(float(cur_hist), 4)})
        elif cross_down:
            return SignalResult("sell", score, "MACD死叉(DIF下穿DEA)",
                                {"DIF": round(float(cur_dif), 4), "DEA": round(float(cur_dea), 4),
                                 "柱": round(float(cur_hist), 4)})
        elif cur_dif > cur_dea and cur_hist > 0:
            return SignalResult("hold", score, "MACD多头排列，趋势向上",
                                {"DIF": round(float(cur_dif), 4), "DEA": round(float(cur_dea), 4)})
        elif cur_dif < cur_dea and cur_hist < 0:
            return SignalResult("hold", score, "MACD空头排列，趋势向下",
                                {"DIF": round(float(cur_dif), 4), "DEA": round(float(cur_dea), 4)})
        else:
            return SignalResult("hold", score, "MACD方向不明确",
                                {"DIF": round(float(cur_dif), 4), "DEA": round(float(cur_dea), 4)})
