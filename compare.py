"""
业绩对比报告

对比：组合 vs 沪深300 vs 纳斯达克100 vs 标普500
功能：月度收益表、累计收益曲线、超额收益分析
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data import get_fund_nav, get_all_funds_nav
from config import FUNDS
from portfolio import HOLDINGS
from risk import (get_benchmark_returns, get_all_nav_returns,
                   calc_portfolio_daily_returns, calc_portfolio_weights,
                   TRADING_DAYS)


def get_qdii_returns(code: str, days: int = 365, name: str = "") -> pd.Series:
    """获取QDII基金日收益率作为指数代理

    Args:
        code: 基金代码
        days: 需要多少天数据
        name: 标识名（日志用）

    Returns:
        Series index=日期, values=日收益率%
    """
    df = get_fund_nav(code, days=days + 60)
    if df is None or df.empty or len(df) < 20:
        return pd.Series(dtype=float)

    df = df.sort_values("净值日期")
    df["return"] = df["单位净值"].pct_change() * 100
    df = df.dropna(subset=["return"])
    return df.set_index("净值日期")["return"].tail(days)


def get_monthly_returns(returns: pd.Series) -> pd.DataFrame:
    """日收益率 → 月收益率

    Args:
        returns: index=日期, values=日收益率%

    Returns:
        DataFrame: index=年月(如"2026-05"), values=月收益率%
    """
    if returns.empty:
        return pd.DataFrame()

    cum = (1 + returns / 100).cumprod()
    monthly = cum.resample("ME").last().pct_change() * 100
    monthly = monthly.dropna()
    monthly.index = monthly.index.strftime("%Y-%m")
    return monthly.to_frame(name="月收益率")


def get_comparison_data(days: int = 365) -> dict:
    """获取所有对比数据

    Args:
        days: 回溯交易日数

    Returns:
        dict:
            portfolio_returns: 组合日收益率 Series
            hs300_returns: 沪深300日收益率 Series
            nasdaq_returns: 纳指100日收益率 Series (QDII proxy)
            sp500_returns: 标普500日收益率 Series (QDII proxy)
            monthly_table: 月度收益对比 DataFrame
            cumulative: 累计收益对比 DataFrame
    """
    # 组合
    nav_returns = get_all_nav_returns(days=days + 60)
    weights = calc_portfolio_weights()
    portfolio_returns = calc_portfolio_daily_returns(nav_returns, weights)
    portfolio_returns = portfolio_returns.tail(days)

    # 沪深300
    hs300 = get_benchmark_returns(days=days + 60).tail(days)

    # QDII proxies
    nasdaq = get_qdii_returns("000834", days=days, name="纳指100")
    sp500 = get_qdii_returns("017641", days=days, name="标普500")

    result = {
        "portfolio_returns": portfolio_returns,
        "hs300_returns": hs300,
        "nasdaq_returns": nasdaq,
        "sp500_returns": sp500,
        "计算日期": datetime.now().strftime("%Y-%m-%d"),
        "数据天数": days,
    }

    # ── 月度收益对比 ──
    monthly_data = {}
    for key, label in [("portfolio_returns", "组合"),
                       ("hs300_returns", "沪深300"),
                       ("nasdaq_returns", "纳斯达克100"),
                       ("sp500_returns", "标普500")]:
        r = result[key]
        if not r.empty:
            m = get_monthly_returns(r)
            if not m.empty:
                monthly_data[label] = m["月收益率"]

    if monthly_data:
        monthly_df = pd.DataFrame(monthly_data)
        monthly_df = monthly_df.sort_index(ascending=False)
        result["monthly_table"] = monthly_df
    else:
        result["monthly_table"] = pd.DataFrame()

    # ── 累计收益曲线（对齐到同一时点）──
    cum_data = {}
    for key, label in [("portfolio_returns", "组合"),
                       ("hs300_returns", "沪深300"),
                       ("nasdaq_returns", "纳斯达克100"),
                       ("sp500_returns", "标普500")]:
        r = result[key]
        if not r.empty:
            cum = (1 + r / 100).cumprod() * 100 - 100  # 转为%
            cum_data[label] = cum

    if cum_data:
        cum_df = pd.DataFrame(cum_data)
        cum_df = cum_df.dropna(how="all")
        result["cumulative"] = cum_df
    else:
        result["cumulative"] = pd.DataFrame()

    # ── 统计汇总 ──
    summary = {}
    for key, label in [("portfolio_returns", "组合"),
                       ("hs300_returns", "沪深300"),
                       ("nasdaq_returns", "纳斯达克100"),
                       ("sp500_returns", "标普500")]:
        r = result[key]
        if r.empty:
            continue
        summary[label] = {
            "年化收益": round(r.mean() * TRADING_DAYS, 2),
            "累计收益": round(((1 + r / 100).prod() - 1) * 100, 2),
            "年化波动": round(r.std() * np.sqrt(TRADING_DAYS), 2),
            "最大回撤": _calc_max_dd_simple(r),
            "数据天数": len(r),
        }
    result["summary"] = summary

    return result


def _calc_max_dd_simple(returns: pd.Series) -> float:
    """简化最大回撤计算"""
    if len(returns) < 5:
        return None
    cum = (1 + returns / 100).cumprod()
    rolling_max = cum.cummax()
    dd = ((cum - rolling_max) / rolling_max * 100).min()
    return round(dd, 2)


def print_comparison(data: dict):
    """CLI 打印对比报告"""
    print(f"\n{'='*55}")
    print(f"  业绩对比报告  {data['计算日期']}")
    print(f"{'='*55}")

    # 统计汇总
    summary = data.get("summary", {})
    if summary:
        print(f"\n  累计收益总览")
        print(f"  {'-'*45}")
        print(f"  {'名称':14s} {'累计收益':>8} {'年化收益':>8} {'年化波动':>8} {'最大回撤':>8}")
        print(f"  {'-'*45}")
        for name, s in summary.items():
            ret = s.get("累计收益", 0)
            ann = s.get("年化收益", 0)
            vol = s.get("年化波动", 0)
            dd = s.get("最大回撤", 0) or 0
            print(f"  {name:14s} {ret:>+7.1f}% {ann:>+7.1f}% {vol:>7.1f}% {dd:>7.1f}%")
        print(f"  {'-'*45}")

    # 月度对比
    monthly = data.get("monthly_table", pd.DataFrame())
    if not monthly.empty:
        print(f"\n  月度收益对比")
        print(f"  {'-'*55}")
        cols = monthly.columns.tolist()
        header = f"  {'月份':>7}"
        for c in cols:
            header += f" {c:>12}"
        print(header)
        print(f"  {'-'*55}")
        for month, row in monthly.iterrows():
            line = f"  {month:>7}"
            for c in cols:
                v = row[c]
                if pd.notna(v):
                    line += f" {v:>+11.1f}%"
                else:
                    line += f" {'N/A':>11}"
            print(line)
        print()

        # 超 win 统计
        if "组合" in cols and "沪深300" in cols:
            better = (monthly["组合"] > monthly["沪深300"]).sum()
            total = len(monthly)
            print(f"  跑赢沪深300: {better}/{total}个月 ({better/total*100:.0f}%)")

    print(f"\n{'='*55}\n")
