"""
持仓穿透分析：基金→股票层 持仓聚合
"""
import pandas as pd
import akshare as ak
from datetime import datetime
from config import FUNDS

# ── ETF联接 → 底层ETF 映射 ──
# 有些ETF联接基金不直接持股，需要查底层ETF
ETF_LINK_MAP = {
    "007817": "515050",  # 国泰通信设备A → 通信ETF
    "016185": "159611",  # 广发电力A → 电力ETF
    "000834": None,      # 大成纳指100 → 纳指100指数
    "270042": None,      # 广发纳指100 → 纳指100指数
    "017641": None,      # 摩根标普500 → 标普500指数
}

INDEX_DESC = {
    "000834": "纳斯达克100指数（QDII，跟踪美股科技）",
    "270042": "纳斯达克100指数（QDII，跟踪美股科技）",
    "017641": "标普500指数（QDII，跟踪美股大盘）",
}


def get_fund_holdings(code: str) -> list:
    """获取基金前十大持仓

    Returns:
        [{"code": str, "name": str, "ratio": float}, ...] 或空列表
    """
    try:
        df = ak.fund_portfolio_hold_em(symbol=code, date="2026")
        if df is None or df.empty:
            return _get_etf_link_holdings(code)
        cols = df.columns.tolist()
        # 列名: 序号, 股票代码, 股票名称, 占净值比例, 持股数, 持仓市值, 季度
        name_col = "股票名称" if "股票名称" in cols else cols[2]
        ratio_col = "占净值比例" if "占净值比例" in cols else cols[3]
        code_col = "股票代码" if "股票代码" in cols else cols[1]

        holdings = []
        for _, row in df.iterrows():
            holdings.append({
                "code": str(row.get(code_col, "")),
                "name": str(row.get(name_col, "")),
                "ratio": float(row.get(ratio_col, 0)),
            })
        return holdings
    except Exception:
        return _get_etf_link_holdings(code)


def _get_etf_link_holdings(code: str) -> list:
    """ETF联接基金：穿透到底层ETF的持仓"""
    if code not in ETF_LINK_MAP:
        return []

    etf_code = ETF_LINK_MAP[code]
    if etf_code:
        # 直接拿底层ETF的持仓
        try:
            df = ak.fund_portfolio_hold_em(symbol=etf_code, date="2026")
            if df is not None and not df.empty:
                cols = df.columns.tolist()
                name_col = "股票名称" if "股票名称" in cols else cols[2]
                ratio_col = "占净值比例" if "占净值比例" in cols else cols[3]
                code_col = "股票代码" if "股票代码" in cols else cols[1]
                holdings = []
                for _, row in df.iterrows():
                    holdings.append({
                        "code": str(row.get(code_col, "")),
                        "name": f"ETF→{row.get(name_col, '')}" if row.get(name_col) else str(row.get(code_col, "")),
                        "ratio": float(row.get(ratio_col, 0)),
                        "note": f"({etf_code} ETF持仓)",
                    })
                return holdings
        except Exception:
            pass
        return [{"code": etf_code, "name": f"→ {etf_code} 底层ETF",
                 "ratio": 95, "note": "ETF联接基金，持仓数据暂不可用"}]

    if code in INDEX_DESC:
        return [{"code": code, "name": INDEX_DESC[code],
                 "ratio": 95, "note": "指数基金，跟踪指数成分股"}]
    return []


def get_all_holdings(fund_values: dict = None) -> dict:
    """获取所有持仓基金的十大持仓

    Args:
        fund_values: {code: current_value}，用于加权计算

    Returns:
        {code: {"fund_name": str, "value": float, "holdings": [...], "date": str}}
    """
    result = {}
    for code, info in FUNDS.items():
        value = (fund_values or {}).get(code, 0)
        holdings = get_fund_holdings(code)
        result[code] = {
            "fund_name": info["name"],
            "value": value,
            "holdings": holdings,
        }
    return result


def aggregate_by_stock(all_holdings: dict) -> pd.DataFrame:
    """跨基金聚合：按股票汇总总敞口

    Returns:
        DataFrame with columns: [股票, 总敞口占比, 涉及基金]
    """
    rows = []
    for code, data in all_holdings.items():
        fund_value = data["value"]
        for h in data["holdings"]:
            # 该股票在这个基金中的实际金额占比（相对总持仓）
            weighted_ratio = round(h["ratio"] * (fund_value / 100), 2) if fund_value else h["ratio"]
            rows.append({
                "股票": h["name"],
                "股票代码": h.get("code", ""),
                "占基金比例": h["ratio"],
                "持有基金": data["fund_name"],
                "基金代码": code,
                "基金市值": fund_value,
            })
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 按股票名聚合
    grouped = df.groupby("股票").agg(
        总敞口占比=("占基金比例", "sum"),
        涉及基金数=("持有基金", "nunique"),
        涉及基金=("持有基金", lambda x: ", ".join(sorted(set(x)))),
        股票代码=("股票代码", "first"),
    ).reset_index()
    grouped = grouped.sort_values("总敞口占比", ascending=False).reset_index(drop=True)
    grouped["总敞口占比"] = grouped["总敞口占比"].round(2)
    return grouped


def search_stock(all_holdings: dict, keyword: str) -> list:
    """搜索特定股票/英伟达在所有基金中的暴露

    Returns:
        [{"fund": str, "code": str, "ratio": float, "value_exposure": float}, ...]
    """
    results = []
    for code, data in all_holdings.items():
        for h in data["holdings"]:
            if keyword.lower() in h["name"].lower() or keyword.lower() in h.get("code", "").lower():
                value_exp = round(data["value"] * h["ratio"] / 100, 2)
                results.append({
                    "fund": data["fund_name"],
                    "fund_code": code,
                    "stock": h["name"],
                    "ratio": h["ratio"],
                    "fund_value": data["value"],
                    "value_exposure": value_exp,
                })
    return results


def print_holdings(all_holdings: dict):
    """CLI 打印所有基金持仓"""
    for code, data in all_holdings.items():
        print(f"\n{'='*55}")
        print(f"  {data['fund_name']}  ({code})")
        if data["value"]:
            print(f"  市值: {data['value']:.0f}")
        print(f"{'='*55}")
        if data["holdings"]:
            for h in data["holdings"]:
                note = f"  — {h.get('note', '')}" if h.get('note') else ""
                print(f"  {h['ratio']:>5.1f}%  {h['name']}{note}")
        else:
            print("  （无持仓数据）")


def print_aggregated(df: pd.DataFrame):
    """打印聚合后的持仓"""
    if df.empty:
        print("\n无持仓数据\n")
        return
    print(f"\n{'='*55}")
    print(f"  跨基金持仓聚合")
    print(f"{'='*55}")
    print(f"  {'占比':>5} {'股票':20s} {'涉及基金'}")
    print(f"  {'-'*50}")
    for _, row in df.head(20).iterrows():
        name = row["股票"][:18] if len(str(row["股票"])) > 18 else row["股票"]
        print(f"  {row['总敞口占比']:>5.1f}% {name:20s} {row['涉及基金']}")
    print(f"  {'-'*50}")
    print(f"  共 {len(df)} 只不同股票\n")


def get_top_stocks(top_n: int = 15) -> list[str]:
    """从持仓穿透中提取前 N 大重仓股票代码

    用于 stock.py 自动填充观察池

    Returns:
        股票代码列表（去重，按穿透敞口降序）
    """
    from portfolio import calc_portfolio
    portfolio = calc_portfolio()
    fund_values = {f["code"]: f["市值"] for f in portfolio["基金"] if f["市值"] > 0}
    all_data = get_all_holdings(fund_values)
    agg = aggregate_by_stock(all_data)
    if agg.empty:
        return []
    # 过滤掉非A股代码（美股/港股/指数描述/基金代码等）
    from config import FUNDS
    stocks = []
    for _, row in agg.iterrows():
        code = str(row.get("股票代码", ""))
        # 只保留6位纯数字A股代码，排除基金代码
        if code.isdigit() and len(code) == 6 and code not in FUNDS:
            stocks.append(code)
        if len(stocks) >= top_n:
            break
    return stocks


def print_search(results: list, keyword: str):
    """打印搜索结果"""
    if not results:
        print(f"\n未找到与 '{keyword}' 相关的持仓\n")
        return
    total_exp = sum(r["value_exposure"] for r in results)
    print(f"\n{'='*55}")
    print(f"  '{keyword}' 持仓搜索")
    print(f"{'='*55}")
    for r in results:
        print(f"  {r['ratio']:>5.1f}%  {r['fund']}")
        print(f"       → 敞口金额: {r['value_exposure']:.2f}元")
    print(f"  {'-'*30}")
    print(f"  总敞口: {total_exp:.2f}元")
    print(f"{'='*55}\n")
