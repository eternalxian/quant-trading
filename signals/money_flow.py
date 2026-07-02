"""资金流因子策略（MFI - Money Flow Index）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import money_flow_index
from signals.base import register


@register
class MoneyFlowCalculator(BaseSignalCalculator):
    strategy_name = "资金流因子"
    strategy_type = "量化因子"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 10, "money_flow_threshold": 0.05})

    def compute(self, data) -> SignalResult:
        high = self.get_high(data)
        low = self.get_low(data)
        close = self.get_close(data)
        volume = self.get_volume(data)
        period = 14  # Standard MFI period

        if len(close) < period + 2:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{period+2})",
                                {"required": period + 2, "got": len(close)})

        mfi = money_flow_index(high, low, close, volume, period)
        cur = mfi[-1]
        prev = mfi[-2]

        if np.isnan(cur):
            return SignalResult("hold", 0.0, "MFI计算中")

        score = (cur - 50.0) / 50.0

        if cur < 20:
            return SignalResult("buy", float(score),
                                f"MFI超卖({cur:.1f}<20)，资金可能回流",
                                {"MFI": round(float(cur), 1), "prev": round(float(prev), 1)})
        elif cur > 80:
            return SignalResult("sell", float(score),
                                f"MFI超买({cur:.1f}>80)，资金可能流出",
                                {"MFI": round(float(cur), 1), "prev": round(float(prev), 1)})
        elif cur > prev and prev < 40:
            return SignalResult("buy", float(score),
                                f"MFI从低位反弹({cur:.1f})",
                                {"MFI": round(float(cur), 1)})
        elif cur < prev and prev > 60:
            return SignalResult("sell", float(score),
                                f"MFI从高位回落({cur:.1f})",
                                {"MFI": round(float(cur), 1)})
        else:
            return SignalResult("hold", float(score),
                                f"MFI中性({cur:.1f})",
                                {"MFI": round(float(cur), 1)})
