"""多模型集成投票策略"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.base import register
from signals import get_calculator


@register
class EnsembleVotingCalculator(BaseSignalCalculator):
    strategy_name = "多模型集成投票"
    strategy_type = "机器学习"

    MODELS = ["LightGBM评分", "CatBoost评分", "LSTM时序预测", "TFT时序预测",
              "ETF轮动-经典版", "板块轮动-LS回归", "ETF轮动-回归斜率评分"]

    def __init__(self, params: dict = None):
        super().__init__(params or {"models": self.MODELS, "voting": "soft"})

    def compute(self, data) -> SignalResult:
        model_names = self.params.get("models", self.MODELS)
        votes_buy = 0
        votes_sell = 0
        total_score = 0.0
        models_available = 0

        for name in model_names:
            try:
                calc = get_calculator(name)
                sr = calc.compute(data)
                if sr.signal == "buy":
                    votes_buy += 1
                    total_score += sr.score
                elif sr.signal == "sell":
                    votes_sell += 1
                    total_score += sr.score
                else:
                    total_score += sr.score * 0.5
                models_available += 1
            except (KeyError, Exception):
                continue

        if models_available == 0:
            return SignalResult("hold", 0.0, "无可用模型", {})

        avg_score = total_score / models_available
        net = (votes_buy - votes_sell) / models_available

        if net > 0.25:
            return SignalResult("buy", float(avg_score),
                                f"集成投票偏多({votes_buy}买/{votes_sell}卖/{models_available}共)",
                                {"buy": votes_buy, "sell": votes_sell, "total": models_available})
        elif net < -0.25:
            return SignalResult("sell", float(avg_score),
                                f"集成投票偏空({votes_buy}买/{votes_sell}卖/{models_available}共)",
                                {"buy": votes_buy, "sell": votes_sell, "total": models_available})
        else:
            return SignalResult("hold", float(avg_score),
                                f"集成投票分歧({votes_buy}买/{votes_sell}卖/{models_available}共)",
                                {"buy": votes_buy, "sell": votes_sell, "total": models_available})
