"""RSRS阻力支撑相对强度策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.base import register


@register
class RSRSCalculator(BaseSignalCalculator):
    strategy_name = "RSRS阻力支撑"
    strategy_type = "统计套利"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 18, "beta_threshold": 0.5, "r2_threshold": 0.7})

    def compute(self, data) -> SignalResult:
        high = self.get_high(data)
        low = self.get_low(data)
        lookback = int(self.params.get("lookback", 18))
        beta_th = float(self.params.get("beta_threshold", 0.5))
        r2_th = float(self.params.get("r2_threshold", 0.7))

        if len(data) < lookback + 1:
            return SignalResult("hold", 0.0, f"数据不足({len(data)}<{lookback+1})",
                                {"required": lookback + 1, "got": len(data)})

        # Regress low[t+1] = alpha + beta * high[t]
        y = low[-lookback:]      # low[t+1] approx
        x = high[-lookback-1:-1]  # high[t]

        if len(x) < 5:
            return SignalResult("hold", 0.0, "数据不够")

        X = np.vstack([x, np.ones_like(x)]).T
        sol = np.linalg.lstsq(X, y, rcond=None)[0]
        slope = float(sol[0])
        intercept = float(sol[1])
        y_hat = X @ np.array([slope, intercept])
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        score = float(slope * max(r2, 0) - 1)  # slope>1 means support > resistance

        # Z-score of slope relative to history
        # simplified: just use the slope directly
        if slope > 1.0 and r2 > r2_th:
            return SignalResult("buy", float(score),
                                f"支撑强于阻力(slope={slope:.3f}, R2={r2:.2f})",
                                {"slope": round(float(slope), 4), "R2": round(float(r2), 4)})
        elif slope < beta_th:
            return SignalResult("sell", float(score),
                                f"阻力强于支撑(slope={slope:.3f}, R2={r2:.2f})",
                                {"slope": round(float(slope), 4), "R2": round(float(r2), 4)})
        else:
            return SignalResult("hold", float(score),
                                f"RSRS中性(slope={slope:.3f}, R2={r2:.2f})",
                                {"slope": round(float(slope), 4), "R2": round(float(r2), 4)})
