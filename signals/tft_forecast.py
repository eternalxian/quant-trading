"""TFT时序预测策略（简化版 Transformer）"""
import os
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.base import register
from signals.ml_trainer import model_path, engineer_features


@register
class TFTForecastCalculator(BaseSignalCalculator):
    strategy_name = "TFT时序预测"
    strategy_type = "机器学习"

    def __init__(self, params: dict = None):
        super().__init__(params or {"lookback": 60, "forecast": 5, "hidden_size": 64})

    def compute(self, data) -> SignalResult:
        path = model_path("tft_etf.pt")
        # TFT is complex; for now delegate to a simple transformer or fallback
        # Check if we have a trained model
        lstm_path = model_path("lstm_etf.pt")
        if not os.path.exists(lstm_path):
            return SignalResult("hold", 0.0,
                                "TFT模型需先训练（当前用LSTM作为近似）",
                                {"hint": "python main.py T lstm"})

        # For V1, TFT delegates to LSTM with a note
        try:
            import torch
            import torch.nn as nn
        except ImportError:
            return SignalResult("hold", 0.0, "torch未安装")

        try:
            X, _ = engineer_features(data)
            if len(X) == 0:
                return SignalResult("hold", 0.0, "特征不足")

            checkpoint = torch.load(lstm_path, map_location="cpu", weights_only=False)
            n_features = checkpoint.get("n_features", X.shape[1])
            hidden = checkpoint.get("hidden", 64)

            class LSTMClassifier(nn.Module):
                def __init__(self, nf, h):
                    super().__init__()
                    self.lstm = nn.LSTM(nf, h, batch_first=True)
                    self.fc = nn.Linear(h, 1)

                def forward(self, x):
                    out, _ = self.lstm(x)
                    return torch.sigmoid(self.fc(out[:, -1, :]))

            model = LSTMClassifier(n_features, hidden)
            model.load_state_dict(checkpoint["model_state"])
            model.eval()

            with torch.no_grad():
                x_t = torch.tensor(X[-1:], dtype=torch.float32).unsqueeze(1)
                proba = model(x_t).item()

            score = float(proba - 0.5) * 2
            signal = "buy" if proba > 0.6 else ("sell" if proba < 0.4 else "hold")

            return SignalResult(signal, score,
                                f"TFT(近似)预测上涨概率{proba:.1%}",
                                {"prob_up": round(float(proba), 4), "backend": "LSTM"})
        except Exception as e:
            return SignalResult("hold", 0.0, f"TFT推断失败: {e}", {})
