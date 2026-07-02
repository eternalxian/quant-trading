"""聪明钱因子策略（大户资金流向）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import sma
from signals.base import register


@register
class SmartMoneyCalculator(BaseSignalCalculator):
    strategy_name = "聪明钱因子"
    strategy_type = "量化因子"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 20, "large_trade_threshold": 100000})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        volume = self.get_volume(data)
        lookback = int(self.params.get("lookback", 20))
        threshold = float(self.params.get("large_trade_threshold", 100000))

        if len(close) < lookback + 2:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{lookback+2})",
                                {"required": lookback + 2, "got": len(close)})

        n = len(close)
        # Approximation: use volume spikes as proxy for large trades
        avg_vol = sma(volume, lookback)
        if np.isnan(avg_vol[-1]):
            return SignalResult("hold", 0.0, "成交量均线计算中")

        vol_ratio = volume / np.where(avg_vol > 0, avg_vol, 1)

        # Classify days: volume > 1.5x avg = "large trade day"
        recent = slice(-lookback, n)
        large_days = vol_ratio[recent] > 1.5
        price_chg = np.diff(close) / np.where(close[:-1] > 0, close[:-1], 1)
        price_chg = np.append(price_chg, price_chg[-1])

        # Net smart money flow: volume-weighted price change on large-volume days
        if large_days.sum() > 0:
            smart_flow = np.sum(price_chg[recent][large_days] * volume[recent][large_days])
            total_flow = np.sum(np.abs(price_chg[recent] * volume[recent]))
            ratio = smart_flow / total_flow if total_flow > 0 else 0
        else:
            ratio = 0

        score = float(ratio)

        if score > 0.05:
            return SignalResult("buy", score,
                                f"聪明钱净流入(ratio={score:.3f})",
                                {"smart_flow_ratio": round(float(ratio), 4),
                                 "large_days": int(large_days.sum())})
        elif score < -0.05:
            return SignalResult("sell", score,
                                f"聪明钱净流出(ratio={score:.3f})",
                                {"smart_flow_ratio": round(float(ratio), 4),
                                 "large_days": int(large_days.sum())})
        else:
            return SignalResult("hold", score,
                                f"聪明钱中性(ratio={score:.3f})",
                                {"smart_flow_ratio": round(float(ratio), 4)})
