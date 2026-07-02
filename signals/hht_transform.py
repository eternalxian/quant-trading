"""HHT希尔伯特黄变换策略（EMD + Hilbert Transform）"""
import numpy as np
from signals.base import BaseSignalCalculator, SignalResult
from signals.base import register


def _emd(signal: np.ndarray, max_imf: int = 5, max_iter: int = 100) -> list:
    """简化版经验模态分解(EMD)，返回IMF列表"""
    x = signal.copy().astype(float)
    imfs = []

    for _ in range(max_imf):
        h = x.copy()
        for _ in range(max_iter):
            # Find extrema
            maxima = [i for i in range(1, len(h) - 1) if h[i - 1] < h[i] > h[i + 1]]
            minima = [i for i in range(1, len(h) - 1) if h[i - 1] > h[i] < h[i + 1]]

            if len(maxima) < 2 or len(minima) < 2:
                break

            # Cubic spline envelopes
            max_x = np.array([0] + maxima + [len(h) - 1])
            max_y = np.array([h[0]] + [h[i] for i in maxima] + [h[-1]])
            min_x = np.array([0] + minima + [len(h) - 1])
            min_y = np.array([h[0]] + [h[i] for i in minima] + [h[-1]])

            # Simple linear interpolation for envelopes
            upper = np.interp(np.arange(len(h)), max_x, max_y)
            lower = np.interp(np.arange(len(h)), min_x, min_y)
            mean = (upper + lower) / 2.0

            h_new = h - mean
            # Check convergence
            if np.std(h_new - h) < 1e-6:
                h = h_new
                break
            h = h_new

        imfs.append(h)
        x = x - h

        # Stop if residual is near monotonic
        if np.std(x) < 0.01 * np.std(signal):
            break

    if len(imfs) == 0:
        imfs.append(signal)
    return imfs


def _hilbert_transform(data: np.ndarray) -> np.ndarray:
    """Hilbert变换 via FFT"""
    n = len(data)
    fft = np.fft.fft(data)
    h = np.zeros(n)
    if n % 2 == 0:
        h[0] = h[n // 2] = 1
        h[1:n // 2] = 2
    else:
        h[0] = 1
        h[1:(n + 1) // 2] = 2
    return np.fft.ifft(fft * h).real


@register
class HHTTransformCalculator(BaseSignalCalculator):
    strategy_name = "HHT希尔伯特黄"
    strategy_type = "统计套利"

    def __init__(self, params: dict = None):
        super().__init__(params or {"imf_count": 5, "threshold": 0.5})

    def compute(self, data) -> SignalResult:
        close = self.get_close(data)
        max_imf = int(self.params.get("imf_count", 5))
        threshold = float(self.params.get("threshold", 0.5))

        min_len = 50
        if len(close) < min_len:
            return SignalResult("hold", 0.0, f"数据不足({len(close)}<{min_len})",
                                {"required": min_len, "got": len(close)})

        # Use last 50 points for EMD
        segment = close[-50:]

        try:
            imfs = _emd(segment, max_imf=max_imf)
        except Exception:
            return SignalResult("hold", 0.0, "EMD分解失败")

        if len(imfs) < 2:
            return SignalResult("hold", 0.0, "IMF分量不足")

        # Analyze highest frequency IMF (IMF1) with Hilbert transform
        imf1 = imfs[0]
        hilbert = _hilbert_transform(imf1)

        # Instantaneous phase and frequency
        phase = np.arctan2(hilbert, imf1)
        inst_freq = np.diff(np.unwrap(phase)) / (2.0 * np.pi)

        # Score: recent instantaneous frequency trend
        recent_freq = inst_freq[-10:]
        freq_trend = np.mean(recent_freq)
        freq_std = np.std(recent_freq)

        # High frequency + increasing = bullish cycle
        # Low frequency + decreasing = bearish cycle
        score = float(freq_trend * 10)  # scale up

        if freq_trend > threshold:
            return SignalResult("buy", score,
                                f"HHT检测上升周期(freq={freq_trend:.3f})",
                                {"freq_trend": round(float(freq_trend), 4),
                                 "imf_count": len(imfs)})
        elif freq_trend < -threshold:
            return SignalResult("sell", score,
                                f"HHT检测下降周期(freq={freq_trend:.3f})",
                                {"freq_trend": round(float(freq_trend), 4),
                                 "imf_count": len(imfs)})
        else:
            return SignalResult("hold", score,
                                f"HHT周期中性(freq={freq_trend:.3f})",
                                {"freq_trend": round(float(freq_trend), 4),
                                 "imf_count": len(imfs)})
