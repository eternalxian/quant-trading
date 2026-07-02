"""筹码分布因子策略（成交量加权成本估算）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import sma
from signals.base import register


@register
class VolumeDistributionCalculator(BaseSignalCalculator):
    strategy_name = "筹码分布因子"
    strategy_type = "量化因子"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 60, "concentration_threshold": 0.3})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        volume = self.get_volume(data)
        lookback = int(self.params.get("lookback", 60))
        conc_th = float(self.params.get("concentration_threshold", 0.3))

        if len(close) < lookback + 1:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{lookback+1})",
                                {"required": lookback + 1, "got": len(close)})

        n = len(close)
        recent_c = close[-lookback:]
        recent_v = volume[-lookback:]

        # VWAP = volume-weighted average price
        vwap = np.sum(recent_c * recent_v) / np.sum(recent_v) if np.sum(recent_v) > 0 else np.mean(recent_c)

        # Concentration: how tight the volume is around the VWAP
        # Lower std means more concentrated (筹码集中)
        price_std = np.std(recent_c)
        if vwap > 0:
            concentration = 1.0 - price_std / vwap  # high = concentrated
        else:
            concentration = 0

        # Price position relative to VWAP
        pos = (close[-1] / vwap - 1) if vwap > 0 else 0

        score = float(concentration - 0.5) * 2  # normalize around 0

        if concentration > 0.7 and pos < 0.05:
            return SignalResult("buy", float(score),
                                f"筹码集中(conc={concentration:.2f})，价格接近成本区",
                                {"concentration": round(float(concentration), 4),
                                 "VWAP": round(float(vwap), 4), "pos": round(float(pos), 4)})
        elif concentration < 0.3:
            return SignalResult("hold", float(score),
                                f"筹码分散(conc={concentration:.2f})",
                                {"concentration": round(float(concentration), 4)})
        elif pos > 0.15:
            return SignalResult("sell", float(score),
                                f"价格远离筹码区(pos={pos:.1%})，获利盘压力",
                                {"concentration": round(float(concentration), 4),
                                 "VWAP": round(float(vwap), 4), "pos": round(float(pos), 4)})
        else:
            return SignalResult("hold", float(score),
                                f"筹码集中度{concentration:.2f}，价格在成本区附近",
                                {"concentration": round(float(concentration), 4),
                                 "VWAP": round(float(vwap), 4)})
