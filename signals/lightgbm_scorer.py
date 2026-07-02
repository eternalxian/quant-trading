"""LightGBM评分策略"""
import os
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.base import register
from signals.ml_trainer import model_path, engineer_features


@register
class LightGBMScorer(BaseSignalCalculator):
    strategy_name = "LightGBM评分"
    strategy_type = "机器学习"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 60, "n_estimators": 200,
                                     "learning_rate": 0.05, "max_depth": 5})

    def compute(self, data) -> SignalResult:
        path = model_path("lightgbm_etf.joblib")
        if not os.path.exists(path):
            return SignalResult("hold", 0.0,
                                "模型未训练，请先运行 python main.py T lightgbm",
                                {"model_path": path})

        try:
            X, _ = engineer_features(data)
            if len(X) == 0:
                return SignalResult("hold", 0.0, "特征不足")
            import joblib
            model = joblib.load(path)
            proba = model.predict_proba(X[-1:])[0]
            score = float(proba[1] - 0.5) * 2

            if proba[1] > 0.6:
                return SignalResult("buy", score, f"LightGBM预测上涨概率{proba[1]:.1%}",
                                    {"prob_up": round(float(proba[1]), 4)})
            elif proba[1] < 0.4:
                return SignalResult("sell", score, f"LightGBM预测下跌概率{1-proba[1]:.1%}",
                                    {"prob_up": round(float(proba[1]), 4)})
            else:
                return SignalResult("hold", score, f"LightGBM预测中性({proba[1]:.1%})",
                                    {"prob_up": round(float(proba[1]), 4)})
        except Exception as e:
            return SignalResult("hold", 0.0, f"LightGBM推断失败: {e}", {})
