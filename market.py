"""
市场扫描：指数、板块、资金流
"""
import pandas as pd
from datetime import datetime
from data import AKSHARE_LOCK, get_all_etfs, get_north_flow
from config import ETF_WATCHLIST


def scan_market() -> dict:
    """扫描当日市场概况"""
    report = {
        "时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "指数": [],
        "ETF": [],
        "北向资金": None,
    }

    # ── 指数实时行情 ──
    try:
        import akshare as ak
        with AKSHARE_LOCK:
            idx_df = ak.stock_zh_index_spot_sina()
        target_names = ["上证指数", "深证成指", "创业板指", "科创50"]
        for _, row in idx_df.iterrows():
            name = str(row.iloc[1])  # 名称
            if name in target_names:
                price = row.iloc[2]  # 最新价
                chg = row.iloc[4]   # 涨跌幅
                if isinstance(chg, (int, float)):
                    chg = f"{chg:+.2f}%"
                report["指数"].append({"name": name, "price": price, "change": chg})
    except Exception as e:
        print(f"  指数行情获取失败: {e}")

    # ── ETF 实时行情 ──
    try:
        import akshare as ak
        with AKSHARE_LOCK:
            etf_spot = ak.fund_etf_spot_em()
        if not etf_spot.empty:
            for code, name in ETF_WATCHLIST.items():
                match = etf_spot[etf_spot["代码"] == code]
                if not match.empty:
                    row = match.iloc[-1]
                    report["ETF"].append({
                        "code": code,
                        "name": name,
                        "close": row.get("最新价", "-"),
                        "change": f"{row.get('涨跌幅', '-'):+.2f}%" if isinstance(row.get('涨跌幅'), (int, float)) else "-",
                    })
    except Exception as e:
        print(f"  ETF 实时行情获取失败: {e}")

    # ── 北向资金 ──
    try:
        import akshare as ak
        with AKSHARE_LOCK:
            nf = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if not nf.empty:
            latest = nf.iloc[-1]
            val = latest.get("value", latest.iloc[-1]) if hasattr(latest, 'get') else latest.iloc[-1]
            report["北向资金"] = {"value": val}
    except Exception as e:
        pass  # 北向资金非必须

    return report


def print_market(report: dict):
    """打印市场概览"""
    print(f"\n{'='*50}")
    print(f"  市场扫描  {report['时间']}")
    print(f"{'='*50}")

    print("\n  指数")
    for idx in report["指数"]:
        print(f"    {idx['name']:8s}  {idx['price']:>10}  {idx['change']}")

    print("\n  关注 ETF")
    for etf in report["ETF"]:
        print(f"    {etf['code']} {etf['name']:12s}  {etf['close']:>8}  {etf['change']}")

    if report["北向资金"]:
        val = report["北向资金"]["value"]
        print(f"\n  北向资金: {val} 亿元")

    print()
