"""
数据层：AKShare 数据获取 + 本地 CSV 缓存
"""
import os
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
from config import FUNDS, ETF_WATCHLIST

# ── 代理绕过 ──
# 东方财富 API 被代理拦截时，设置 no_proxy
_no_proxy_domains = ["eastmoney.com", "eastmoney", "push2his", "push2"]
_existing_no_proxy = os.environ.get("no_proxy", "")
for d in _no_proxy_domains:
    if d not in _existing_no_proxy:
        _existing_no_proxy = f"{_existing_no_proxy},{d}" if _existing_no_proxy else d
os.environ["no_proxy"] = _existing_no_proxy

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

CACHE_EXPIRE_HOURS = 6  # 净值一天只更新一次，6小时缓存足够

# ── 缓存模式开关（由 Dashboard 侧栏控制）──
FORCE_CACHE = False  # True = 跳过所有 API 请求，只读本地缓存


def get_cache_mtime(code: str = None) -> str:
    """获取最新缓存时间，用于界面显示"""
    import glob
    latest = None
    pattern = os.path.join(DATA_DIR, "nav_*.csv") if code is None else \
             os.path.join(DATA_DIR, f"nav_{code}.csv")
    for f in glob.glob(pattern):
        mtime = datetime.fromtimestamp(os.path.getmtime(f))
        if latest is None or mtime > latest:
            latest = mtime
    return latest.strftime("%m-%d %H:%M") if latest else "暂无"

# ── 缓存模式开关（由 Dashboard 侧栏控制）──
FORCE_CACHE = False  # True = 跳过所有 API 请求，只读本地缓存

# ── 基金净值 ──

def get_fund_nav(code: str, days: int = 60, use_cache: bool = True) -> pd.DataFrame:
    """获取基金历史净值，返回 [日期, 净值, 涨跌幅]"""
    cache_file = os.path.join(DATA_DIR, f"nav_{code}.csv")

    # 强制缓存模式：直接读缓存，过期也返回
    if FORCE_CACHE and os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=["净值日期"])
        return df.tail(days).reset_index(drop=True)

    if use_cache and os.path.exists(cache_file):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - mtime < timedelta(hours=CACHE_EXPIRE_HOURS):
            df = pd.read_csv(cache_file, parse_dates=["净值日期"])
            return df.tail(days).reset_index(drop=True)

    try:
        df = ak.fund_open_fund_info_em(symbol=code)
        df = df.rename(columns={
            "净值日期": "净值日期",
            "单位净值": "单位净值",
            "日增长率": "日增长率",
        })
        df["净值日期"] = pd.to_datetime(df["净值日期"])
        df = df.sort_values("净值日期")
        df.to_csv(cache_file, index=False)
        return df.tail(days).reset_index(drop=True)
    except Exception as e:
        print(f"  [错误] {code} 拉取失败: {e}")
        if os.path.exists(cache_file):
            return pd.read_csv(cache_file, parse_dates=["净值日期"]).tail(days).reset_index(drop=True)
        return pd.DataFrame()


def get_all_funds_nav(days: int = 30) -> dict:
    """获取所有持仓基金的最新净值（并行请求）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    result = {}
    codes = list(FUNDS.keys())
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(get_fund_nav, code, days=days): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                df = future.result()
                if not df.empty:
                    result[code] = df
            except Exception:
                pass
    return result


# ── ETF 行情 ──

def get_etf_daily(code: str, days: int = 120, use_cache: bool = True) -> pd.DataFrame:
    """获取 ETF 日线数据（前复权）
    优先用新浪API（更稳定），东方财富做备选
    """
    cache_file = os.path.join(DATA_DIR, f"etf_{code}.csv")

    # 强制缓存模式
    if FORCE_CACHE and os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=["日期"])
        return df.tail(days).reset_index(drop=True)

    if use_cache and os.path.exists(cache_file):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - mtime < timedelta(hours=CACHE_EXPIRE_HOURS):
            df = pd.read_csv(cache_file, parse_dates=["日期"])
            return df.tail(days).reset_index(drop=True)

    # 尝试新浪 API
    df = _fetch_etf_sina(code, days)
    if df is not None and not df.empty:
        df.to_csv(cache_file, index=False)
        return df.tail(days).reset_index(drop=True)

    # 备选：东方财富 API
    try:
        df = ak.fund_etf_hist_em(
            symbol=code, period="daily",
            start_date=(datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq",
        )
        if not df.empty:
            df = df.rename(columns={"日期": "日期", "开盘": "open", "最高": "high",
                                     "最低": "low", "收盘": "close", "成交量": "volume"})
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.sort_values("日期")
            df.to_csv(cache_file, index=False)
            return df.tail(days).reset_index(drop=True)
    except Exception:
        pass

    # 都失败，尝试读缓存
    if os.path.exists(cache_file):
        return pd.read_csv(cache_file, parse_dates=["日期"]).tail(days).reset_index(drop=True)
    return pd.DataFrame()


def _fetch_etf_sina(code: str, days: int = 120) -> pd.DataFrame:
    """从新浪财经获取ETF历史日线"""
    import requests
    import json

    sh_code = {"513100", "513500", "512480", "515050", "515070", "510880", "518880", "510050", "510300"}
    prefix = "sh" if code[:3] in {"513", "512", "515", "510", "518"} else "sz"
    url = (f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={prefix}{code}&scale=240&datalen={days}")

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200 or not r.text.strip():
            return pd.DataFrame()
        data = json.loads(r.text)
        if not data:
            return pd.DataFrame()

        rows = []
        for item in data:
            rows.append({
                "日期": pd.to_datetime(item["day"]),
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item["volume"]),
            })
        df = pd.DataFrame(rows)
        df = df.sort_values("日期")
        return df
    except Exception:
        return pd.DataFrame()


def get_all_etfs(days: int = 120) -> dict:
    """获取所有关注 ETF 的行情"""
    result = {}
    for code in ETF_WATCHLIST:
        df = get_etf_daily(code, days=days)
        if not df.empty:
            result[code] = df
    return result


# ── 指数 ──

def get_index_data() -> pd.DataFrame:
    """获取主要指数实时行情"""
    try:
        return ak.stock_zh_index_spot_em()
    except Exception as e:
        print(f"  [错误] 指数数据拉取失败: {e}")
        return pd.DataFrame()


# ── 宏观数据 ──

def get_north_flow() -> pd.DataFrame:
    """北向资金流向"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        return df.tail(20)
    except Exception as e:
        print(f"  [错误] 北向资金拉取失败: {e}")
        return pd.DataFrame()


# ── 个股日K线 ──

def get_stock_daily(code: str, days: int = 120) -> pd.DataFrame | None:
    """获取A股个股日K线（前复权），本地CSV缓存

    Args:
        code: 6位A股代码（如 '603986'）
        days: 拉取天数

    Returns:
        DataFrame (date, open, close, high, low, volume) 或 None
    """
    cache_file = os.path.join(DATA_DIR, f"stock_{code}.csv")

    if FORCE_CACHE and os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=["date"])
        return df.tail(days).reset_index(drop=True) if not df.empty else None

    if os.path.exists(cache_file):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - mtime < timedelta(days=1):
            df = pd.read_csv(cache_file, parse_dates=["date"])
            return df.tail(days).reset_index(drop=True) if not df.empty else None

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

        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
        }
        df = df.rename(columns=col_map)
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "open", "close", "high", "low", "volume"]].copy()
        df.to_csv(cache_file, index=False)
        return df.tail(days).reset_index(drop=True)

    except Exception as e:
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=["date"])
            return df.tail(days).reset_index(drop=True) if not df.empty else None
        return None
