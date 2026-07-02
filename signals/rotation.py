"""
信号生成：半自动ETF轮动信号
AI 分析 → 生成信号 → 你确认 → 执行

不直接下单，只输出操作建议
"""
import os
import csv
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import LinearRegression
from config import ROTATION_ETF_CODES, SIGNAL_CONFIG
from data import get_etf_daily

# ── 信号历史记录 ──
SIGNAL_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "signal_history.csv")


class SignalScorer:
    """多因子评分器"""

    @staticmethod
    def regression_score(data: np.ndarray, window: int = 25) -> float:
        """线性回归斜率 × R2 (vnpy EtfRotationStrategy 核心)"""
        if len(data) < window:
            return 0.0
        x = np.arange(1, window + 1).reshape(-1, 1)
        y = (data[-window:] / data[-window]).reshape(-1, 1)
        reg = LinearRegression().fit(x, y)
        return float(reg.coef_[0][0] * reg.score(x, y))

    @staticmethod
    def momentum_score(data: np.ndarray, window: int = 20) -> float:
        """简单动量"""
        if len(data) < window:
            return 0.0
        return float(data[-1] / data[-window] - 1)

    @staticmethod
    def ma_ratio(data: np.ndarray, short: int = 5, long: int = 20) -> float:
        """均线比：短期均线/长期均线 - 1"""
        if len(data) < long:
            return 0.0
        sma_short = np.mean(data[-short:])
        sma_long = np.mean(data[-long:])
        if sma_long == 0:
            return 0.0
        return float(sma_short / sma_long - 1)


def generate_signals(days: int = 60) -> dict:
    """
    生成ETF轮动信号
    返回每个ETF的综合评分和操作建议
    """
    result = {
        "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "信号": [],
        "综合建议": "",
    }

    scores = {}
    etf_data = {}

    for code in ROTATION_ETF_CODES:
        df = get_etf_daily(code, days=days, use_cache=True)
        if df is None or df.empty or len(df) < SIGNAL_CONFIG["score_window"]:
            continue

        close = df["close"].values
        etf_data[code] = df

        # 多因子评分
        reg = SignalScorer.regression_score(close, SIGNAL_CONFIG["score_window"])
        mom = SignalScorer.momentum_score(close, 20)
        ma_r = SignalScorer.ma_ratio(close, 5, 20)

        # 综合评分（加权）
        composite = reg * 0.5 + mom * 0.3 + ma_r * 0.2
        scores[code] = {
            "score": round(composite, 6),
            "regression": round(reg, 6),
            "momentum": round(mom, 4),
            "ma_ratio": round(ma_r, 4),
            "close": close[-1],
        }

    if not scores:
        return result

    # 排序
    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)

    # 生成信号
    threshold = SIGNAL_CONFIG["momentum_threshold"]
    max_pos = SIGNAL_CONFIG["max_position_pct"]

    for i, (code, s) in enumerate(ranked):
        name = ROTATION_ETF_CODES[code]
        action = "观望"
        reason = ""

        if i == 0 and s["momentum"] > threshold:
            action = "买入"
            reason = "综合评分第一，动量为正"
        elif i == 0 and s["momentum"] <= threshold:
            action = "关注"
            reason = "评分最高但动量不足，等信号确认"
        elif s["momentum"] < -threshold * 2:
            action = "卖出"
            reason = "动量为负且评分靠后"

        result["信号"].append({
            "code": code,
            "name": name,
            "排名": i + 1,
            "评分": s["score"],
            "趋势": s["regression"],
            "动量": f"{s['momentum']*100:+.1f}%",
            "操作": action,
            "理由": reason,
            "建议仓位": f"{max_pos if action == '买入' else 0:.0%}" if action in ["买入", "关注"] else "0%",
        })

    # 综合建议
    top = result["信号"][0]
    if top["操作"] == "买入":
        result["综合建议"] = f"建议买入 {top['code']} {top['name']}，仓位上限{max_pos:.0%}。其他ETF观望。"
    elif top["操作"] == "关注":
        result["综合建议"] = f"暂无明确信号，{top['code']} {top['name']} 评分最高但动量不足，继续等待。"
    else:
        result["综合建议"] = "所有ETF评分偏低，建议持币观望。"

    return result


def print_signals(result: dict):
    """打印信号表"""
    print(f"\n{'='*55}")
    print(f"  ETF 轮动信号  {result['生成时间']}")
    print(f"{'='*55}")
    print(f"  {'排名':>3} {'代码':>7} {'名称':12s} {'评分':>10} {'动量':>8} {'操作':6s} {'理由'}")
    print(f"  {'-'*52}")

    for s in result["信号"]:
        print(f"  {s['排名']:>3} {s['code']:>7} {s['name']:12s} {s['评分']:>10.6f} {s['动量']:>8} {s['操作']:6s} {s['理由']}")

    print(f"  {'-'*52}")
    print(f"  建议: {result['综合建议']}")
    print(f"{'='*55}\n")


def save_signals(result: dict):
    """将今日信号追加到 signal_history.csv"""
    if not result.get("信号"):
        return
    date_str = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for s in result["信号"]:
        rows.append({
            "日期": date_str,
            "code": s["code"],
            "name": s["name"],
            "排名": s["排名"],
            "评分": s["评分"],
            "趋势": s["趋势"],
            "动量": s["动量"],
            "操作": s["操作"],
        })
    file_exists = os.path.exists(SIGNAL_HISTORY_FILE)
    with open(SIGNAL_HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def load_signal_history() -> pd.DataFrame:
    """读取信号历史记录"""
    if not os.path.exists(SIGNAL_HISTORY_FILE):
        return pd.DataFrame()
    return pd.read_csv(SIGNAL_HISTORY_FILE, parse_dates=["日期"])
