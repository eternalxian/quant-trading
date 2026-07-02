"""CatBoost评分策略"""
import os
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.base import register
from signals.ml_trainer import model_path, engineer_features


@register
class CatBoostScorer(BaseSignalCalculator):
    strategy_name = "CatBoost评分"
    strategy_type = "机器学习"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 60, "iterations": 300,
                                     "learning_rate": 0.05, "depth": 5})

    def compute(self, data) -> SignalResult:
        path = model_path("catboost_etf.joblib")
        if not os.path.exists(path):
            return SignalResult("hold", 0.0,
                                "模型未训练，请先运行 python main.py T catboost",
                                {"model_path": path})

        try:
            X, _ = engineer_features(data)
            if len(X) == 0:
                return SignalResult("hold", 0.0, "特征不足")
            try:
                from catboost import CatBoostClassifier
                import joblib
                model = joblib.load(path)
            except ImportError:
                return SignalResult("hold", 0.0, "catboost未安装")

            proba = model.predict_proba(X[-1:])[0]
            score = float(proba[1] - 0.5) * 2

            if proba[1] > 0.6:
                return SignalResult("buy", score, f"CatBoost预测上涨概率{proba[1]:.1%}",
                                    {"prob_up": round(float(proba[1]), 4)})
            elif proba[1] < 0.4:
                return SignalResult("sell", score, f"CatBoost预测下跌概率{1-proba[1]:.1%}",
                                    {"prob_up": round(float(proba[1]), 4)})
            else:
                return SignalResult("hold", score, f"CatBoost预测中性({proba[1]:.1%})",
                                    {"prob_up": round(float(proba[1]), 4)})
        except Exception as e:
            return SignalResult("hold", 0.0, f"CatBoost推断失败: {e}", {})
