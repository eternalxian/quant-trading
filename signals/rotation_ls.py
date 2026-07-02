"""板块轮动-LS回归策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import linear_regression_score
from signals.base import register


@register
class LSRotationCalculator(BaseSignalCalculator):
    strategy_name = "板块轮动-LS回归"
    strategy_type = "轮动"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 60, "top_n": 3, "rebalance_days": 20})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        lookback = int(self.params.get("lookback", 60))

        if len(close) < lookback:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{lookback})",
                                {"required": lookback, "got": len(close)})

        score = linear_regression_score(close, lookback)
        mom_20d = close[-1] / close[-min(21, len(close) - 1)] - 1

        if score > 0.0003 and mom_20d > 0:
            return SignalResult("buy", float(score),
                                f"回归斜率×R2={score:.6f}，趋势向上",
                                {"ls_score": round(float(score), 6), "mom_20d": round(float(mom_20d), 4)})
        elif score > 0:
            return SignalResult("hold", float(score),
                                f"回归正但动量不足(score={score:.6f})",
                                {"ls_score": round(float(score), 6)})
        elif score < -0.0003:
            return SignalResult("sell", float(score),
                                f"回归斜率×R2={score:.6f}，趋势向下",
                                {"ls_score": round(float(score), 6)})
        else:
            return SignalResult("hold", float(score),
                                f"回归信号中性({score:.6f})",
                                {"ls_score": round(float(score), 6)})

    def compute_all(self, data_dict: dict) -> dict:
        """重写: 对全池排名后确定top_n"""
        all_scores = {}
        for code, df in data_dict.items():
            if df is None or df.empty:
                continue
            close = self.get_close(df)
            lookback = int(self.params.get("lookback", 60))
            if len(close) < lookback:
                continue
            all_scores[code] = (linear_regression_score(close, lookback), df)

        if not all_scores:
            return {}

        top_n = int(self.params.get("top_n", 3))
        ranked = sorted(all_scores.items(), key=lambda x: x[1][0], reverse=True)
        results = {}
        for i, (code, (score, df)) in enumerate(ranked):
            if i < top_n and score > 0:
                results[code] = SignalResult("buy", float(score),
                                             f"LS评分排名第{i+1}，score={score:.6f}",
                                             {"rank": i + 1, "ls_score": round(float(score), 6)})
            elif i < top_n:
                results[code] = SignalResult("hold", float(score),
                                             f"排名第{i+1}但评分为负",
                                             {"rank": i + 1, "ls_score": round(float(score), 6)})
            elif score < -0.0003:
                results[code] = SignalResult("sell", float(score),
                                             f"排名第{i+1}，评分为负",
                                             {"rank": i + 1, "ls_score": round(float(score), 6)})
            else:
                results[code] = SignalResult("hold", float(score),
                                             f"排名第{i+1}",
                                             {"rank": i + 1, "ls_score": round(float(score), 6)})
        return results
