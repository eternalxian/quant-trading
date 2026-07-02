"""唐奇安通道突破策略（海龟简化版）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import donchian, atr
from signals.base import register


@register
class DonchianBreakoutCalculator(BaseSignalCalculator):
    strategy_name = "唐奇安通道突破"
    strategy_type = "趋势跟踪"

    def __init__(self, params: dict = None):
        super().__init__(params or {"entry_period": 20, "exit_period": 10, "atr_multiplier": 2})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        high = self.get_high(data)
        low = self.get_low(data)
        entry_p = int(self.params.get("entry_period", 20))
        exit_p = int(self.params.get("exit_period", 10))

        min_len = entry_p + 2
        if len(close) < min_len:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{min_len})",
                                {"required": min_len, "got": len(close)})

        entry_up, entry_low, _ = donchian(high, low, entry_p)
        exit_up, exit_low, _ = donchian(high, low, exit_p)

        cur_close = close[-1]
        prev_close = close[-2]
        cur_entry_up = entry_up[-1]
        cur_exit_low = exit_low[-1]

        # Breakout entry
        if cur_close > entry_up[-2] and prev_close <= entry_up[-3] if len(close) >= 3 else cur_close > cur_entry_up:
            return SignalResult("buy", float(cur_close / cur_entry_up - 1) if cur_entry_up > 0 else 0,
                                f"突破{entry_p}日高点{cur_entry_up:.3f}",
                                {"entry_high": round(float(cur_entry_up), 4), "exit_low": round(float(cur_exit_low), 4)})
        elif cur_close < cur_exit_low:
            return SignalResult("sell", float(cur_close / cur_exit_low - 1) if cur_exit_low > 0 else 0,
                                f"跌破{exit_p}日低点{cur_exit_low:.3f}",
                                {"exit_low": round(float(cur_exit_low), 4)})
        elif cur_close > cur_entry_up * 0.95:
            return SignalResult("hold", float(cur_close / cur_entry_up - 1) if cur_entry_up > 0 else 0,
                                f"接近通道上轨({cur_entry_up:.3f})，关注突破",
                                {"upper": round(float(cur_entry_up), 4), "lower": round(float(cur_exit_low), 4)})
        else:
            return SignalResult("hold", float(cur_close / ((cur_entry_up + cur_exit_low) / 2) - 1) if cur_exit_low > 0 else 0,
                                "区间震荡，无突破",
                                {"upper": round(float(cur_entry_up), 4), "lower": round(float(cur_exit_low), 4)})
