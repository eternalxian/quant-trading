"""
行业分析与全景透视

功能：
1. 持仓股票 → 行业分类（A股：申万行业，美股：手动映射）
2. 按行业/地域聚合敞口
3. 全市场行业表现跟踪（申万一级行业指数）
"""
import pandas as pd
import akshare as ak
from typing import Optional
from config import FUNDS

# ── 地域映射 ──
REGION_MAP = {"QDII": "美股", "A_stock": "A股"}

# ── 美股持仓 → 行业 手动映射 ──
# 基于 holdings.py 已暴露的美股持仓
US_STOCK_INDUSTRY = {
    "NVDA": "半导体/AI",
    "TSM": "半导体",
    "AMD": "半导体",
    "MRVL": "半导体",
    "MU": "半导体",
    "LITE": "光通信",
    "COHR": "光通信",
    "CIEN": "光通信",
    "VIAV": "光通信/测试",
    "ANET": "通信设备",
    "AMZN": "云计算",
    "MSFT": "AI/云计算",
    "GOOGL": "AI/互联网",
    "META": "AI/互联网",
    "AAPL": "消费电子",
    "CRWD": "网络安全",
    "PANW": "网络安全",
    "SNPS": "EDA/半导体",
    "CDNS": "EDA/半导体",
    "ADI": "模拟芯片",
    "TXN": "模拟芯片",
    "QCOM": "通信芯片",
    "AVGO": "半导体/通信",
    "INTC": "半导体",
    "WDC": "存储",
    "STX": "存储",
    "KLAC": "半导体设备",
    "AMAT": "半导体设备",
    "LRCX": "半导体设备",
    "ASML": "半导体设备",
    "NXPI": "汽车芯片",
}

INDEX_CATEGORY = {
    "纳斯达克100": "美股科技",
    "标普500": "美股大盘",
    "通信ETF": "通信",
    "电力ETF": "电力",
}

# ── 申万一级行业指数代码 ──
SW_INDEX_CODES = {
    "电子": "801080",
    "计算机": "801750",
    "通信": "801770",
    "半导体": "801081",   # 申万二级
    "电力设备": "801730",
    "国防军工": "801740",
    "食品饮料": "801120",
    "医药生物": "801150",
    "银行": "801780",
    "非银金融": "801790",
    "房地产": "801180",
    "汽车": "801880",
    "机械设备": "801890",
    "有色金属": "801050",
    "煤炭": "801950",
    "基础化工": "801030",
    "石油石化": "801960",
    "钢铁": "801040",
    "建筑材料": "801710",
    "建筑装饰": "801720",
    "交通运输": "801200",
    "传媒": "801760",
    "公用事业": "801160",
    "环保": "801970",
    "商贸零售": "801780",  # note: this may conflict with 银行
}

# ── 行业配色方案（用于饼图/热力图）──
INDUSTRY_COLORS = {
    "半导体": "#1f77b4",
    "半导体/AI": "#1f77b4",
    "半导体设备": "#4A90D9",
    "EDA/半导体": "#5BA0E8",
    "存储": "#7FBAE0",
    "光通信": "#ff7f0e",
    "通信设备": "#FFA040",
    "通信芯片": "#FFB866",
    "通信": "#ff7f0e",
    "AI/云计算": "#2ca02c",
    "AI/互联网": "#50B050",
    "云计算": "#2ca02c",
    "网络安全": "#d62728",
    "模拟芯片": "#9467bd",
    "消费电子": "#8c564b",
    "汽车芯片": "#e377c2",
    "电力": "#bcbd22",
    "电子": "#1f77b4",
    "计算机": "#2ca02c",
    "国防军工": "#d62728",
    "食品饮料": "#e377c2",
    "医药生物": "#f37b7b",
    "银行": "#8c564b",
    "非银金融": "#c49c94",
    "房地产": "#f7b6d2",
    "汽车": "#ff9896",
    "机械设备": "#c5b0d5",
    "有色金属": "#c49c94",
    "煤炭": "#636363",
    "基础化工": "#8c6d31",
    "石油石化": "#7f7f7f",
    "钢铁": "#aec7e8",
    "传媒": "#98df8a",
    "公用事业": "#ffbb78",
    "美股科技": "#17becf",
    "美股大盘": "#9edae5",
    "指数基金": "#dbdb8d",
    "其他": "#cccccc",
}


def get_stock_industry_a(stock_code: str) -> str:
    """获取A股个股的申万行业

    Args:
        stock_code: 6位A股代码

    Returns:
        行业名称，如"电子"、"计算机"，查不到返回"其他"
    """
    try:
        info = ak.stock_individual_info_em(symbol=stock_code)
        if info is not None and not info.empty:
            for _, row in info.iterrows():
                item = str(row.iloc[0])
                if "行业" in item:
                    value = str(row.iloc[1]).strip()
                    return value if value else "其他"
    except Exception:
        pass
    return "其他"


def classify_holdings(all_holdings: dict) -> pd.DataFrame:
    """将持仓穿透数据按行业和地域分类

    Args:
        all_holdings: get_all_holdings() 返回值

    Returns:
        DataFrame: [股票, 股票代码, 行业, 地域, 敞口金额, 持有基金, 占基金比例]
    """
    rows = []
    for fund_code, data in all_holdings.items():
        fund_type = FUNDS.get(fund_code, {}).get("type", "unknown")
        region = REGION_MAP.get(fund_type, "其他")
        for h in data["holdings"]:
            stock_code = h.get("code", "")
            stock_name = h["name"]
            ratio = h["ratio"]
            fund_value = data["value"]
            value_exposure = round(fund_value * ratio / 100, 2) if fund_value else 0

            # ── 行业分类 ──
            industry = None

            # 1) 美股代码匹配
            if stock_code in US_STOCK_INDUSTRY:
                industry = US_STOCK_INDUSTRY[stock_code]
            # 2) 名称包含"ETF→"，穿透ETF的持仓
            elif stock_name.startswith("ETF→"):
                industry = "电子"  # 默认，ETF持仓多为科技
            # 3) 指数基金
            elif "指数" in stock_name or "ETF" in stock_name:
                for key, cat in INDEX_CATEGORY.items():
                    if key in stock_name:
                        industry = cat
                        break
                if industry is None:
                    industry = "指数基金"
            # 4) A股6位数字代码
            elif stock_code and stock_code.isdigit() and len(stock_code) == 6:
                industry = get_stock_industry_a(stock_code)

            if industry is None:
                industry = "其他"

            rows.append({
                "股票": stock_name,
                "股票代码": stock_code,
                "行业": industry,
                "地域": region,
                "敞口金额": value_exposure,
                "持有基金": data["fund_name"],
                "占基金比例": ratio,
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def aggregate_by_industry(df: pd.DataFrame) -> pd.DataFrame:
    """按行业聚合总敞口"""
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("行业").agg(
        总敞口=("敞口金额", "sum"),
        涉及股票数=("股票", "nunique"),
        涉及基金数=("持有基金", "nunique"),
    ).reset_index()
    grouped = grouped.sort_values("总敞口", ascending=False).reset_index(drop=True)
    grouped["占比"] = round(grouped["总敞口"] / grouped["总敞口"].sum() * 100, 1)
    return grouped


def aggregate_by_region(df: pd.DataFrame) -> pd.DataFrame:
    """按地域聚合总敞口"""
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("地域").agg(
        总敞口=("敞口金额", "sum"),
        涉及股票数=("股票", "nunique"),
        涉及基金数=("持有基金", "nunique"),
    ).reset_index()
    grouped["占比"] = round(grouped["总敞口"] / grouped["总敞口"].sum() * 100, 1)
    return grouped


# ── 全市场行业表现 ──


def get_sw_index_daily(index_code: str, days: int = 60) -> pd.DataFrame:
    """获取申万指数日线数据

    Args:
        index_code: 申万指数代码，如 "801080"

    Returns:
        DataFrame with columns: [日期, 收盘]
    """
    try:
        df = ak.index_hist_sw(symbol=index_code, period="day")
        if df is not None and not df.empty:
            df = df.tail(days).copy()
            df["日期"] = pd.to_datetime(df["日期"])
            return df[["日期", "收盘"]]
    except Exception:
        pass
    return pd.DataFrame()


_CHG_CACHE = {}


def _get_sw_change(index_code: str, days: int) -> float:
    """获取申万指数N日涨跌幅（带缓存）"""
    cache_key = (index_code, days)
    if cache_key in _CHG_CACHE:
        return _CHG_CACHE[cache_key]
    try:
        df = ak.index_hist_sw(symbol=index_code, period="day")
        if df is not None and len(df) > days:
            close_col = "收盘"
            latest = df.iloc[-1][close_col]
            prev = df.iloc[-days][close_col]
            change = round((latest - prev) / prev * 100, 2)
            _CHG_CACHE[cache_key] = change
            return change
    except Exception:
        pass
    return None


def get_sector_performance(days: int = 20) -> pd.DataFrame:
    """全市场申万一级行业近期涨跌幅排名

    Args:
        days: 统计周期（交易日）

    Returns:
        DataFrame: [行业, {days}日涨跌幅]
    """
    results = []
    for name, index_code in SW_INDEX_CODES.items():
        change = _get_sw_change(index_code, days)
        if change is not None:
            results.append({"行业": name, f"{days}日涨跌": change})

    if not results:
        return pd.DataFrame()
    result_df = pd.DataFrame(results)
    return result_df.sort_values(f"{days}日涨跌", ascending=False).reset_index(drop=True)


def get_multi_period_sector_performance() -> pd.DataFrame:
    """多周期行业表现对比 (5日 / 20日 / 60日)

    Returns:
        DataFrame: [行业, 5日涨跌, 20日涨跌, 60日涨跌]
    """
    all_data = {}
    for name, index_code in SW_INDEX_CODES.items():
        try:
            df = ak.index_hist_sw(symbol=index_code, period="day")
            if df is not None and len(df) >= 60:
                close_col = "收盘"
                all_data[name] = {
                    "5日涨跌": round((df.iloc[-1][close_col] / df.iloc[-5][close_col] - 1) * 100, 2),
                    "20日涨跌": round((df.iloc[-1][close_col] / df.iloc[-20][close_col] - 1) * 100, 2),
                    "60日涨跌": round((df.iloc[-1][close_col] / df.iloc[-60][close_col] - 1) * 100, 2),
                }
        except Exception:
            pass

    if not all_data:
        return pd.DataFrame()
    result_df = pd.DataFrame.from_dict(all_data, orient="index")
    result_df.index.name = "行业"
    result_df = result_df.reset_index()
    return result_df.sort_values("20日涨跌", ascending=False).reset_index(drop=True)


def get_color(industry: str) -> str:
    """获取行业对应的颜色"""
    return INDUSTRY_COLORS.get(industry, "#cccccc")


def print_industry_breakdown(industry_df: pd.DataFrame, title: str = "行业分布"):
    """命令行打印行业分布"""
    if industry_df.empty:
        print(f"\n无{title}数据\n")
        return
    name_col = industry_df.columns[0]  # 第一列是名称列（"行业"或"地域"）
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")
    print(f"  {'占比':>5} {'名称':16s} {'敞口(元)':>10} {'股票数':>6} {'基金数':>6}")
    print(f"  {'-'*45}")
    for _, row in industry_df.iterrows():
        name = str(row[name_col])[:16] if len(str(row[name_col])) > 16 else str(row[name_col])
        print(f"  {row['占比']:>4.1f}% {name:16s} {row['总敞口']:>10.1f} {row['涉及股票数']:>6.0f} {row['涉及基金数']:>6.0f}")
    print(f"  {'-'*45}")
    print(f"  合计 {len(industry_df)} 个\n")


def print_sector_performance(perf_df: pd.DataFrame, days: int = 20):
    """命令行打印行业表现排名"""
    if perf_df.empty:
        print("\n暂无全市场行业数据\n")
        return
    col = f"{days}日涨跌"
    print(f"\n{'='*50}")
    print(f"  全市场行业 {days}日涨跌排名")
    print(f"{'='*50}")
    print(f"  {'排名':>4} {'行业':12s} {'涨跌':>8}")
    print(f"  {'-'*30}")
    for i, (_, row) in enumerate(perf_df.iterrows(), 1):
        chg = row[col]
        marker = " >>" if chg > 3 else " <<" if chg < -3 else "   "  # no emoji — GBK safe
        print(f"  {i:>4d} {row['行业']:12s} {chg:>+7.2f}%{marker}")
