"""ETF轮动-经典版策略（纯动量排名）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.base import register


@register
class ClassicRotationCalculator(BaseSignalCalculator):
    strategy_name = "ETF轮动-经典版"
    strategy_type = "轮动"

    def __init__(self, params: dict = None):
        super().__init__(params or {"rank_days": 20, "top_n": 1, "rebalance_days": 20})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        rank_days = int(self.params.get("rank_days", 20))
        top_n = int(self.params.get("top_n", 1))

        if len(close) < rank_days + 1:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{rank_days+1})",
                                {"required": rank_days + 1, "got": len(close)})

        ret = close[-1] / close[-rank_days] - 1
        mom_5d = close[-1] / close[-min(6, len(close) - 1)] - 1 if len(close) >= 6 else 0

        if ret > 0.03 and mom_5d > 0:
            return SignalResult("buy", float(ret),
                                f"{rank_days}日动量+{ret*100:.1f}%，排名有望领先",
                                {"rank_days_ret": round(float(ret), 4), "5d_mom": round(float(mom_5d), 4)})
        elif ret > 0:
            return SignalResult("hold", float(ret),
                                f"{rank_days}日动量+{ret*100:.1f}%，正但不够强",
                                {"rank_days_ret": round(float(ret), 4)})
        elif ret < -0.05:
            return SignalResult("sell", float(ret),
                                f"{rank_days}日动量{ret*100:.1f}%，排名靠后",
                                {"rank_days_ret": round(float(ret), 4)})
        else:
            return SignalResult("hold", float(ret),
                                f"{rank_days}日动量{ret*100:.1f}%",
                                {"rank_days_ret": round(float(ret), 4)})

    def compute_all(self, data_dict: dict) -> dict:
        """重写: 对全池排名后确定top_n"""
        all_scores = {}
        for code, df in data_dict.items():
            if df is None or df.empty:
                continue
            close = self.get_close(df)
            rank_days = int(self.params.get("rank_days", 20))
            if len(close) < rank_days + 1:
                continue
            ret = close[-1] / close[-rank_days] - 1
            mom_5d = close[-1] / close[-min(6, len(close) - 1)] - 1 if len(close) >= 6 else 0
            all_scores[code] = (ret, mom_5d, df)

        if not all_scores:
            return {}

        top_n = int(self.params.get("top_n", 1))
        ranked = sorted(all_scores.items(), key=lambda x: x[1][0], reverse=True)
        results = {}
        for i, (code, (ret, mom_5d, df)) in enumerate(ranked):
            if i < top_n and ret > 0:
                results[code] = SignalResult("buy", float(ret),
                                             f"排名第{i+1}，动量+{ret*100:.1f}%",
                                             {"rank": i + 1, "ret": round(float(ret), 4)})
            elif i < top_n:
                results[code] = SignalResult("hold", float(ret),
                                             f"排名第{i+1}但动量为负",
                                             {"rank": i + 1, "ret": round(float(ret), 4)})
            elif ret < -0.05:
                results[code] = SignalResult("sell", float(ret),
                                             f"排名第{i+1}，动量显著为负",
                                             {"rank": i + 1, "ret": round(float(ret), 4)})
            else:
                results[code] = SignalResult("hold", float(ret),
                                             f"排名第{i+1}",
                                             {"rank": i + 1, "ret": round(float(ret), 4)})
        return results
