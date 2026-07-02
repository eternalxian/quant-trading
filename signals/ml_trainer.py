"""ML模型训练pipeline"""
import os
import numpy as np
import pandas as pd

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")


def model_path(name: str) -> str:
    os.makedirs(MODELS_DIR, exist_ok=True)
    return os.path.join(MODELS_DIR, name)


def engineer_features(df: pd.DataFrame) -> tuple:
    """从OHLCV数据构建特征矩阵和标签"""
    close = df["close"].values.astype(float)
    volume = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(df))
    high = df["high"].values.astype(float) if "high" in df.columns else close
    low = df["low"].values.astype(float) if "low" in df.columns else close

    n = len(close)
    features = []

    for i in range(60, n - 5):
        window = close[i - 60:i + 1]
        vol_window = volume[i - 60:i + 1]

        # Returns of various horizons
        ret_1d = window[-1] / window[-2] - 1
        ret_5d = window[-1] / window[-6] - 1
        ret_10d = window[-1] / window[-11] - 1
        ret_20d = window[-1] / window[-21] - 1

        # Volatility
        vol_20d = np.std(window[-20:]) / np.mean(window[-20:]) if np.mean(window[-20:]) > 0 else 0

        # Volume change
        vol_ratio = np.mean(vol_window[-5:]) / np.mean(vol_window[-20:]) if np.mean(vol_window[-20:]) > 0 else 1

        # RSI approximation
        delta = np.diff(window[-15:])
        gain = np.mean(delta[delta > 0]) if (delta > 0).any() else 0
        loss = np.mean(np.abs(delta[delta < 0])) if (delta < 0).any() else 0.0001
        rsi_approx = 100.0 - 100.0 / (1.0 + gain / loss)

        # MA ratio
        ma5 = np.mean(window[-5:])
        ma20 = np.mean(window[-20:])
        ma_ratio = ma5 / ma20 - 1 if ma20 > 0 else 0

        features.append([ret_1d, ret_5d, ret_10d, ret_20d, vol_20d, vol_ratio, rsi_approx, ma_ratio])

        # Label: forward 5-day return > 0
    labels = []
    for i in range(60, n - 5):
        fwd_ret = close[i + 5] / close[i] - 1
        labels.append(1 if fwd_ret > 0 else 0)

    min_len = min(len(features), len(labels))
    return np.array(features[:min_len]), np.array(labels[:min_len])


def train_lightgbm(data_dict: dict, save: bool = True):
    """LightGBM分类模型训练"""
    try:
        import lightgbm as lgb
    except ImportError:
        print("  [跳过] lightgbm未安装")
        return None

    X_list, y_list = [], []
    for code, df in data_dict.items():
        if df is None or df.empty or len(df) < 70:
            continue
        try:
            X, y = engineer_features(df)
            if len(X) > 50:
                X_list.append(X)
                y_list.append(y)
        except Exception:
            continue

    if not X_list:
        print("  [跳过] 训练数据不足")
        return None

    X_all = np.vstack(X_list)
    y_all = np.hstack(y_list)

    # Time-split: 80/20
    split = int(len(X_all) * 0.8)
    X_train, X_test = X_all[:split], X_all[split:]
    y_train, y_test = y_all[:split], y_all[split:]

    model = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, max_depth=5,
                               verbose=-1, random_state=42)
    model.fit(X_train, y_train)

    acc = model.score(X_test, y_test)
    print(f"  LightGBM训练完成: acc={acc:.3f}, samples={len(X_all)}")

    if save:
        import joblib
        path = model_path("lightgbm_etf.joblib")
        joblib.dump(model, path)
        print(f"  已保存: {path}")

    return model


def train_catboost(data_dict: dict, save: bool = True):
    """CatBoost分类模型训练"""
    try:
        from catboost import CatBoostClassifier
    except ImportError:
        print("  [跳过] catboost未安装")
        return None

    X_list, y_list = [], []
    for code, df in data_dict.items():
        if df is None or df.empty or len(df) < 70:
            continue
        try:
            X, y = engineer_features(df)
            if len(X) > 50:
                X_list.append(X)
                y_list.append(y)
        except Exception:
            continue

    if not X_list:
        print("  [跳过] 训练数据不足")
        return None

    X_all = np.vstack(X_list)
    y_all = np.hstack(y_list)

    split = int(len(X_all) * 0.8)
    X_train, X_test = X_all[:split], X_all[split:]
    y_train, y_test = y_all[:split], y_all[split:]

    model = CatBoostClassifier(iterations=300, learning_rate=0.05, depth=5,
                               verbose=0, random_seed=42)
    model.fit(X_train, y_train)

    acc = model.score(X_test, y_test)
    print(f"  CatBoost训练完成: acc={acc:.3f}, samples={len(X_all)}")

    if save:
        import joblib
        path = model_path("catboost_etf.joblib")
        joblib.dump(model, path)
        print(f"  已保存: {path}")

    return model


def train_lstm(data_dict: dict, save: bool = True):
    """LSTM时序模型训练"""
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        print("  [跳过] torch未安装")
        return None

    X_list, y_list = [], []
    for code, df in data_dict.items():
        if df is None or df.empty or len(df) < 70:
            continue
        try:
            X, y = engineer_features(df)
            if len(X) > 50:
                X_list.append(X)
                y_list.append(y)
        except Exception:
            continue

    if not X_list:
        print("  [跳过] 训练数据不足")
        return None

    X_all = np.vstack(X_list)
    y_all = np.hstack(y_list)

    # Simple LSTM model
    class LSTMClassifier(nn.Module):
        def __init__(self, n_features, hidden=64):
            super().__init__()
            self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
            self.fc = nn.Linear(hidden, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return torch.sigmoid(self.fc(out[:, -1, :]))

    n_features = X_all.shape[1]
    model = LSTMClassifier(n_features)

    # Quick training
    X_t = torch.tensor(X_all, dtype=torch.float32).unsqueeze(1)  # (N,1,F)
    y_t = torch.tensor(y_all, dtype=torch.float32)

    opt = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.BCELoss()

    model.train()
    for epoch in range(30):
        opt.zero_grad()
        pred = model(X_t).squeeze()
        loss = loss_fn(pred, y_t)
        loss.backward()
        opt.step()

    with torch.no_grad():
        pred = model(X_t).squeeze().round()
        acc = (pred == y_t).float().mean().item()

    print(f"  LSTM训练完成: acc={acc:.3f}, samples={len(X_all)}")

    if save:
        path = model_path("lstm_etf.pt")
        torch.save({"model_state": model.state_dict(),
                    "n_features": n_features,
                    "hidden": 64}, path)
        print(f"  已保存: {path}")

    return model


def train_all(data_dict: dict):
    """训练所有ML模型"""
    print("\n  === ML模型训练 ===")
    train_lightgbm(data_dict)
    train_catboost(data_dict)
    train_lstm(data_dict)
    print("  训练完成\n")
