"""
共享技术指标函数
纯numpy实现，返回与输入等长的数组（前N个值为NaN）
"""
import numpy as np


def sma(data: np.ndarray, period: int) -> np.ndarray:
    """简单移动均线"""
    if len(data) < period:
        return np.full(len(data), np.nan)
    result = np.full(len(data), np.nan)
    cumsum = np.cumsum(np.insert(data, 0, 0))
    result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def ema(data: np.ndarray, period: int) -> np.ndarray:
    """指数移动均线"""
    if len(data) < period:
        return np.full(len(data), np.nan)
    result = np.full(len(data), np.nan)
    result[period - 1] = np.mean(data[:period])
    alpha = 2.0 / (period + 1)
    for i in range(period, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
    """相对强弱指数"""
    if len(data) < period + 1:
        return np.full(len(data), np.nan)
    delta = np.diff(data)
    result = np.full(len(data), np.nan)
    gain = np.maximum(delta[:period], 0).mean()
    loss = np.maximum(-delta[:period], 0).mean()
    if loss == 0:
        result[period] = 100.0
    else:
        result[period] = 100.0 - 100.0 / (1.0 + gain / loss)
    for i in range(period + 1, len(data)):
        g = max(delta[i - 1], 0)
        l = max(-delta[i - 1], 0)
        gain = (gain * (period - 1) + g) / period
        loss = (loss * (period - 1) + l) / period
        if loss == 0:
            result[i] = 100.0
        else:
            result[i] = 100.0 - 100.0 / (1.0 + gain / loss)
    return result


def macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD: 返回 (dif, dea, histogram)"""
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    hist = 2.0 * (dif - dea)
    return dif, dea, hist


def bollinger(data: np.ndarray, period: int = 20, std_mul: float = 2.0):
    """布林带: 返回 (middle, upper, lower, bandwidth)"""
    mid = sma(data, period)
    std = np.full(len(data), np.nan)
    for i in range(period - 1, len(data)):
        std[i] = np.std(data[i - period + 1:i + 1], ddof=1)
    upper = mid + std_mul * std
    lower = mid - std_mul * std
    bw = (upper - lower) / np.where(mid != 0, mid, np.nan)
    return mid, upper, lower, bw


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """平均真实波幅"""
    n = len(close)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(high[i] - low[i],
                    abs(high[i] - close[i - 1]),
                    abs(low[i] - close[i - 1]))
    tr[0] = high[0] - low[0]
    return ema(tr, period)


def donchian(high: np.ndarray, low: np.ndarray, period: int = 20):
    """唐奇安通道: 返回 (upper, lower, middle)"""
    n = len(high)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    for i in range(period - 1, n):
        upper[i] = np.max(high[i - period + 1:i + 1])
        lower[i] = np.min(low[i - period + 1:i + 1])
    mid = (upper + lower) / 2.0
    return upper, lower, mid


def kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray,
        k_period: int = 9, d_period: int = 3, j_period: int = 3):
    """KDJ: 返回 (k, d, j)"""
    n = len(close)
    rsv = np.full(n, np.nan)
    for i in range(k_period - 1, n):
        hh = np.max(high[i - k_period + 1:i + 1])
        ll = np.min(low[i - k_period + 1:i + 1])
        rng = hh - ll
        rsv[i] = 100.0 * (close[i] - ll) / rng if rng > 0 else 50.0

    k = np.full(n, np.nan)
    d = np.full(n, np.nan)
    j = np.full(n, np.nan)
    first = k_period + d_period - 2
    k[first] = rsv[first] if not np.isnan(rsv[first]) else 50.0
    d[first] = 50.0
    for i in range(first + 1, n):
        k[i] = 2.0 / 3.0 * k[i - 1] + 1.0 / 3.0 * (rsv[i] if not np.isnan(rsv[i]) else k[i - 1])
        d[i] = 2.0 / 3.0 * d[i - 1] + 1.0 / 3.0 * k[i]
        j[i] = 3.0 * k[i] - 2.0 * d[i]
    return k, d, j


def linear_regression_score(data: np.ndarray, window: int = 25) -> float:
    """线性回归斜率 × R2"""
    if len(data) < window:
        return 0.0
    x = np.arange(1, window + 1).reshape(-1, 1)
    y = (data[-window:] / data[-window]).reshape(-1, 1)
    X = np.hstack([x, np.ones_like(x)])
    sol = np.linalg.lstsq(X, y, rcond=None)[0]
    slope = float(sol[0])
    y_hat = X @ sol
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return float(slope * max(r2, 0))


def typical_price(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    return (high + low + close) / 3.0


def money_flow_index(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                     volume: np.ndarray, period: int = 14) -> np.ndarray:
    """资金流量指标"""
    tp = typical_price(high, low, close)
    raw_mf = tp * volume
    n = len(close)
    result = np.full(n, np.nan)
    if n < period + 1:
        return result

    pos_flow = np.zeros(n)
    neg_flow = np.zeros(n)
    for i in range(1, n):
        if tp[i] > tp[i - 1]:
            pos_flow[i] = raw_mf[i]
        elif tp[i] < tp[i - 1]:
            neg_flow[i] = raw_mf[i]

    for i in range(period, n):
        pf = np.sum(pos_flow[i - period + 1:i + 1])
        nf = np.sum(neg_flow[i - period + 1:i + 1])
        if nf > 0:
            mr = pf / nf
            result[i] = 100.0 - 100.0 / (1.0 + mr)
        elif pf > 0:
            result[i] = 100.0
        else:
            result[i] = 50.0
    return result


def alligator(close: np.ndarray, jaw_p: int = 13, teeth_p: int = 8, lips_p: int = 5,
              jaw_shift: int = 8, teeth_shift: int = 5, lips_shift: int = 3):
    """鳄鱼线: 返回 (jaw, teeth, lips) — 都用SMMA(shifted SMA)"""
    n = len(close)
    jaw = np.full(n, np.nan)
    teeth = np.full(n, np.nan)
    lips = np.full(n, np.nan)

    def _ssma(arr, period, shift):
        raw = sma(arr, period)
        result = np.full(len(arr), np.nan)
        result[period - 1 + shift:] = raw[period - 1:-shift] if shift > 0 else raw[period - 1:]
        return result

    jaw = _ssma(close, jaw_p, jaw_shift)
    teeth = _ssma(close, teeth_p, teeth_shift)
    lips = _ssma(close, lips_p, lips_shift)
    return jaw, teeth, lips
