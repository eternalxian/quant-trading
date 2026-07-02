"""
个股引擎：实时行情 + 日K线缓存 + 20策略信号

核心功能：
- 实时行情快照（A股）
- 日K线拉取+CSV缓存
- 复用 signals/ 下的全部策略计算器生成买卖信号
- 多策略投票排名
"""

import os
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
from data import DATA_DIR

# ── 参数 ──
DEFAULT_DAYS = 120         # 默认拉取天数
CACHE_EXPIRE_DAYS = 1      # 日K线缓存一天有效
WATCHLIST_FILE = os.path.join(DATA_DIR, "stock_watchlist.json")

# ── 观察池运行时加载（与 config.py 初始值合并）──
from config import STOCK_WATCHLIST


def save_watchlist():
    """持久化观察池到 JSON"""
    import json
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(STOCK_WATCHLIST, f, ensure_ascii=False, indent=2)


def load_watchlist():
    """从 JSON 恢复观察池，合并到 STOCK_WATCHLIST"""
    import json
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        STOCK_WATCHLIST.update(saved)


# 启动时加载
load_watchlist()


# ═══════════════════════════════════════
#  日K线获取 + CSV 缓存
# ═══════════════════════════════════════

def get_stock_daily(code: str, days: int = DEFAULT_DAYS) -> pd.DataFrame | None:
    """获取A股日K线，本地 CSV 缓存

    Args:
        code: 股票代码（如 '603986'）
        days: 拉取天数

    Returns:
        DataFrame (columns: date, open, close, high, low, volume)
        或 None（数据不足）
    """
    cache_path = os.path.join(DATA_DIR, f"stock_{code}.csv")

    # ── 读缓存 ──
    if os.path.exists(cache_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if (datetime.now() - mtime) < timedelta(days=CACHE_EXPIRE_DAYS):
            df = pd.read_csv(cache_path, parse_dates=["date"])
            if len(df) >= max(days // 2, 20):
                return df.tail(days)

    # ── 拉取 ──
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if df is None or df.empty:
            return None

        # 标准化列名
        col_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        }
        df = df.rename(columns=col_map)
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "open", "close", "high", "low", "volume"]].copy()

        # 写入缓存
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        df.to_csv(cache_path, index=False)

        return df.tail(days)

    except Exception as e:
        # 网络错误时回退缓存
        if os.path.exists(cache_path):
            df = pd.read_csv(cache_path, parse_dates=["date"])
            if not df.empty:
                return df.tail(days)
        return None


# ═══════════════════════════════════════
#  实时行情快照
# ═══════════════════════════════════════

def get_stock_spot(watchlist: dict = None) -> pd.DataFrame:
    """获取实时行情快照（Sina接口，批量快）

    Args:
        watchlist: {code: name}，默认使用全局 STOCK_WATCHLIST

    Returns:
        DataFrame: code, name, price, change_pct, volume, amount, turnover
    """
    codes = list(watchlist or STOCK_WATCHLIST)
    if not codes:
        return pd.DataFrame()

    try:
        # Sina 格式：sz300502,sh600900
        sina_codes = []
        for c in codes:
            prefix = "sh" if c.startswith(("6", "9")) else "sz"
            sina_codes.append(f"{prefix}{c}")
        symbols = ",".join(sina_codes)

        import urllib.request
        import re
        url = f"https://hq.sinajs.cn/list={symbols}"
        headers = {"Referer": "https://finance.sina.com.cn"}
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("gbk")

        rows = []
        for line in raw.strip().split("\n"):
            if not line.strip():
                continue
            # var hq_str_sh600900="三峡能源,8.50,8.35,8.55,..."
            m = re.match(r'var hq_str_(\w+)="(.+)"', line)
            if not m:
                continue
            sym = m.group(1)
            code = sym[2:]  # strip sh/sz prefix
            fields = m.group(2).split(",")
            if len(fields) < 32:
                continue

            name = fields[0]
            price = float(fields[3]) if fields[3] else 0.0
            prev_close = float(fields[2]) if fields[2] else 0.0
            change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            volume = float(fields[8]) if fields[8] else 0.0
            amount = float(fields[9]) if fields[9] else 0.0
            turnover = float(fields[38]) if len(fields) > 38 and fields[38] else None

            rows.append({
                "code": code,
                "name": name,
                "price": price,
                "change_pct": change_pct,
                "volume": volume,
                "amount": amount,
                "turnover": turnover,
            })

        df = pd.DataFrame(rows)
        # 排序：按涨跌幅降序
        if not df.empty:
            df = df.sort_values("change_pct", ascending=False)
        return df

    except Exception:
        return pd.DataFrame()


# ═══════════════════════════════════════
#  批量信号生成
# ═══════════════════════════════════════

def generate_stock_signals(stocks_data: dict, strategy_names: list[str] = None) -> dict:
    """对一组股票数据运行全部信号计算器

    Args:
        stocks_data: {code: DataFrame(OHLCV)}
        strategy_names: 指定策略名列表，None=全部

    Returns:
        {strategy_name: {code: SignalResult}}
    """
    from signals import compute_all_signals
    return compute_all_signals(stocks_data, strategy_names=strategy_names, persist=False)


def rank_stocks(signals: dict) -> pd.DataFrame:
    """多策略投票排名

    买入 +1, 卖出 -1, 观望 0 → 合计总分

    Returns:
        DataFrame: code, buy_count, sell_count, hold_count, score, total_signals
    """
    if not signals:
        return pd.DataFrame()

    stock_scores: dict[str, dict] = {}

    for sname, codes in signals.items():
        if isinstance(codes, dict) and "error" in codes:
            continue
        if not isinstance(codes, dict):
            continue
        for code, sr in codes.items():
            if not hasattr(sr, "signal"):
                continue
            if code not in stock_scores:
                stock_scores[code] = {"buy": 0, "sell": 0, "hold": 0, "total": 0}
            stock_scores[code][sr.signal] = stock_scores[code].get(sr.signal, 0) + 1
            stock_scores[code]["total"] += 1

    rows = []
    for code, counts in stock_scores.items():
        score = counts["buy"] - counts["sell"]
        name = STOCK_WATCHLIST.get(code, "")
        rows.append({
            "code": code,
            "name": name,
            "buy": counts["buy"],
            "sell": counts["sell"],
            "hold": counts["hold"],
            "score": score,
            "total": counts["total"],
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


# ═══════════════════════════════════════
#  CLI 输出
# ═══════════════════════════════════════

def print_stock_spot(spot_df: pd.DataFrame):
    """打印实时行情"""
    if spot_df.empty:
        print("\n暂无个股实时行情\n")
        return

    print(f"\n{'='*80}")
    print(f"  个股实时行情  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}")
    print(f"  {'代码':>8s}  {'名称':10s}  {'现价':>8s}  {'涨跌幅':>8s}  {'成交额(亿)':>10s}  {'换手率':>8s}")
    print(f"  {'-'*70}")

    for _, row in spot_df.iterrows():
        amount_yi = row.get("amount", 0) / 1e8 if row.get("amount") else 0
        turnover = f"{row.get('turnover', 0):.2f}%" if row.get("turnover") else "-"
        print(f"  {row['code']:>8s}  {str(row['name']):10s}  "
              f"{row.get('price', 0):>8.2f}  "
              f"{row.get('change_pct', 0):>+8.2f}%  "
              f"{amount_yi:>10.2f}  "
              f"{turnover:>8s}")

    print(f"{'='*80}\n")


def print_stock_rank(rank_df: pd.DataFrame, signals: dict = None):
    """打印个股信号排名"""
    if rank_df.empty:
        print("\n暂无个股信号\n")
        return

    print(f"\n{'='*80}")
    print(f"  个股信号排名（多策略投票） {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}")
    print(f"  {'排名':>4s}  {'代码':>8s}  {'名称':10s}  {'得分':>6s}  "
          f"{'买入':>5s}  {'卖出':>5s}  {'观望':>5s}")
    print(f"  {'-'*60}")

    for i, row in rank_df.iterrows():
        tag = "★" if row["score"] >= 3 else ("·" if row["score"] >= 0 else "▼")
        code_name = STOCK_WATCHLIST.get(row["code"], row.get("name", ""))
        print(f"  {i+1:>4d}  {row['code']:>8s}  {str(code_name):10s}  "
              f"{tag} {row['score']:>+4d}  "
              f"{row['buy']:>5d}  {row['sell']:>5d}  {row['hold']:>5d}")

    print(f"{'='*80}\n")


# ═══════════════════════════════════════
#  批量数据获取
# ═══════════════════════════════════════

def get_all_stocks_daily(watchlist: dict = None, days: int = DEFAULT_DAYS) -> dict:
    """批量拉取 watchlist 内所有个股日K线

    Returns:
        {code: DataFrame}  过滤掉数据不足的
    """
    codes = list(watchlist or STOCK_WATCHLIST)
    result = {}
    for code in codes:
        df = get_stock_daily(code, days=days)
        if df is not None and len(df) >= 30:
            result[code] = df
    return result
