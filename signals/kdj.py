"""KDJ随机指标策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.common import kdj
from signals.base import register


@register
class KDJCalculator(BaseSignalCalculator):
    strategy_name = "KDJ随机指标"
    strategy_type = "技术指标"

    def __init__(self, params: dict = None):
        super().__init__(params or {"k_period": 9, "d_period": 3, "j_period": 3})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        high = self.get_high(data)
        low = self.get_low(data)
        kp = int(self.params.get("k_period", 9))
        dp = int(self.params.get("d_period", 3))
        jp = int(self.params.get("j_period", 3))

        min_len = kp + dp + 4
        if len(close) < min_len:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{min_len})",
                                {"required": min_len, "got": len(close)})

        k, d, j = kdj(high, low, close, kp, dp, jp)
        cur_k, cur_d, cur_j = k[-1], d[-1], j[-1]
        prev_k, prev_d = k[-2], d[-2]

        if np.isnan(cur_j):
            return SignalResult("hold", 0.0, "KDJ计算中")

        score = (cur_k - 50.0) / 50.0
        golden = cur_k > cur_d and prev_k <= prev_d
        dead = cur_k < cur_d and prev_k >= prev_d

        if golden and cur_j < 20:
            return SignalResult("buy", float(score),
                                f"低位金叉(K={cur_k:.1f}上穿D={cur_d:.1f}, J={cur_j:.1f})",
                                {"K": round(float(cur_k), 1), "D": round(float(cur_d), 1), "J": round(float(cur_j), 1)})
        elif golden:
            return SignalResult("buy", float(score),
                                f"金叉(K={cur_k:.1f}上穿D={cur_d:.1f})",
                                {"K": round(float(cur_k), 1), "D": round(float(cur_d), 1), "J": round(float(cur_j), 1)})
        elif dead and cur_j > 80:
            return SignalResult("sell", float(score),
                                f"高位死叉(K={cur_k:.1f}下穿D={cur_d:.1f}, J={cur_j:.1f})",
                                {"K": round(float(cur_k), 1), "D": round(float(cur_d), 1), "J": round(float(cur_j), 1)})
        elif dead:
            return SignalResult("sell", float(score),
                                f"死叉(K={cur_k:.1f}下穿D={cur_d:.1f})",
                                {"K": round(float(cur_k), 1), "D": round(float(cur_d), 1), "J": round(float(cur_j), 1)})
        elif cur_j > 100:
            return SignalResult("hold", float(score),
                                f"J值超买(J={cur_j:.1f}>100)，关注回落",
                                {"K": round(float(cur_k), 1), "D": round(float(cur_d), 1), "J": round(float(cur_j), 1)})
        elif cur_j < 0:
            return SignalResult("hold", float(score),
                                f"J值超卖(J={cur_j:.1f}<0)，关注反弹",
                                {"K": round(float(cur_k), 1), "D": round(float(cur_d), 1), "J": round(float(cur_j), 1)})
        else:
            return SignalResult("hold", float(score),
                                f"KDJ中性(K={cur_k:.1f} D={cur_d:.1f} J={cur_j:.1f})",
                                {"K": round(float(cur_k), 1), "D": round(float(cur_d), 1), "J": round(float(cur_j), 1)})
