"""
组合风险指标

计算：波动率、最大回撤、夏普比、Calmar比、相关性矩阵、VaR
对比基准：沪深300
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from data import AKSHARE_LOCK, get_fund_nav, get_all_funds_nav
from config import FUNDS
from portfolio import HOLDINGS, COST_BASIS, CASH_YUEBAO

# ── 参数 ──
RISK_FREE_RATE = 0.02       # 无风险利率（中国10年期国债约1.8%，取2%保守值）
TRADING_DAYS = 252           # 年化交易日数
MIN_DATA_DAYS = 20           # 最小数据要求


def get_benchmark_returns(days: int = 250) -> pd.Series:
    """获取沪深300日收益率

    Returns:
        Series index=date, values=daily return %
    """
    import akshare as ak
    try:
        with AKSHARE_LOCK:
            df = ak.stock_zh_index_daily(symbol="sh000300")
        if df is not None and not df.empty:
            df = df.tail(days + 1).copy()
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            df["return"] = df["close"].pct_change() * 100
            return df.dropna(subset=["return"]).set_index("date")["return"]
    except Exception:
        pass
    return pd.Series(dtype=float)


def get_all_nav_returns(days: int = 250) -> pd.DataFrame:
    """获取所有基金的日收益率矩阵

    合并所有基金的日收益率到一个 DataFrame，列=基金代码

    Returns:
        DataFrame: index=日期, columns=基金代码, values=日收益率%
    """
    navs = get_all_funds_nav(days=days + 60)  # 多取一些用于对齐
    returns_dict = {}

    for code in FUNDS:
        df = navs.get(code)
        if df is None or df.empty or len(df) < MIN_DATA_DAYS:
            continue

        df = df.copy()
        df = df.sort_values("净值日期")
        df["return"] = df["单位净值"].pct_change() * 100
        df = df.dropna(subset=["return"])

        if len(df) >= MIN_DATA_DAYS:
            returns_dict[code] = df.set_index("净值日期")["return"]

    if not returns_dict:
        return pd.DataFrame()

    result = pd.DataFrame(returns_dict)
    # 只保留所有基金都有数据的日期
    result = result.dropna(how="all")
    return result


def calc_portfolio_weights() -> pd.Series:
    """计算当前各基金的持仓权重（基于市值，不含余额宝）

    Returns:
        Series index=fund_code, values=weight (0~1)
    """
    values = {}
    total = 0
    for code in FUNDS:
        shares_data = HOLDINGS[code]
        if shares_data is None:
            continue
        shares, _ = shares_data
        # 用最新净值估算市值
        navs = get_all_funds_nav(days=5)
        df = navs.get(code)
        if df is None or df.empty:
            continue
        nav = df.iloc[-1]["单位净值"]
        value = shares * nav
        values[code] = value
        total += value

    if total == 0:
        return pd.Series(dtype=float)
    weights = pd.Series({k: v / total for k, v in values.items()})
    return weights


def calc_portfolio_daily_returns(nav_returns: pd.DataFrame,
                                  weights: pd.Series = None) -> pd.Series:
    """计算组合日收益率 = 各基金收益率的加权和

    Args:
        nav_returns: get_all_nav_returns() 返回值
        weights: 权重，None则等权

    Returns:
        Series: index=日期, values=组合日收益率%
    """
    if nav_returns.empty:
        return pd.Series(dtype=float)

    if weights is None:
        weights = calc_portfolio_weights()

    # 只取有权重的基金
    common_codes = [c for c in weights.index if c in nav_returns.columns]
    if not common_codes:
        return pd.Series(dtype=float)

    w = weights[common_codes]
    w = w / w.sum()  # 重新归一化

    portfolio_returns = nav_returns[common_codes].dot(w)
    return portfolio_returns


# ── 指标计算 ──


def calc_annualized_vol(daily_returns: pd.Series) -> float:
    """年化波动率 (%)"""
    if len(daily_returns) < MIN_DATA_DAYS:
        return None
    return round(daily_returns.std() * np.sqrt(TRADING_DAYS), 2)


def calc_max_drawdown(daily_returns: pd.Series) -> dict:
    """最大回撤

    Returns:
        {"max_dd": %, "start": date, "end": date, "recovery": date or None}
    """
    if len(daily_returns) < MIN_DATA_DAYS:
        return {"max_dd": None, "start": None, "end": None, "recovery": None}

    cum = (1 + daily_returns / 100).cumprod()
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max * 100

    max_dd_idx = drawdown.idxmin()
    max_dd = drawdown[max_dd_idx]

    # 回撤起始日：回到此日期之前最近的峰值
    cum_before = cum[:max_dd_idx]
    peak_before = cum_before.idxmax() if not cum_before.empty else max_dd_idx

    # 恢复日：回撤后首次回到峰值
    recovery = None
    peak_val = rolling_max[max_dd_idx]
    after = cum.loc[max_dd_idx:]
    recovered = after[after >= peak_val]
    if not recovered.empty:
        recovery = recovered.index[0]

    return {
        "max_dd": round(max_dd, 2),
        "start": peak_before,
        "end": max_dd_idx,
        "recovery": recovery,
    }


def calc_sharpe(daily_returns: pd.Series, rf: float = RISK_FREE_RATE) -> float:
    """夏普比

    Sharpe = (年化收益率 - 无风险利率) / 年化波动率
    """
    if len(daily_returns) < MIN_DATA_DAYS:
        return None

    ann_return = daily_returns.mean() * TRADING_DAYS
    ann_vol = daily_returns.std() * np.sqrt(TRADING_DAYS)
    if ann_vol == 0:
        return None

    return round((ann_return - rf) / ann_vol, 2)


def calc_calmar(daily_returns: pd.Series) -> float:
    """Calmar比 = 年化收益率 / 最大回撤绝对值"""
    if len(daily_returns) < MIN_DATA_DAYS:
        return None

    ann_return = daily_returns.mean() * TRADING_DAYS
    dd_info = calc_max_drawdown(daily_returns)
    max_dd = dd_info["max_dd"]
    if max_dd is None or max_dd == 0:
        return None

    return round(ann_return / abs(max_dd), 2)


def calc_var(daily_returns: pd.Series, alpha: float = 0.05) -> float:
    """Value at Risk (历史模拟法)

    Args:
        alpha: 置信水平，0.05 = 95% VaR

    Returns:
        日VaR值（%），如 -2.5 表示95%概率日亏损不超过2.5%
    """
    if len(daily_returns) < MIN_DATA_DAYS:
        return None
    return round(daily_returns.quantile(alpha), 2)


def calc_correlation_matrix(nav_returns: pd.DataFrame) -> pd.DataFrame:
    """基金收益率相关性矩阵

    Returns:
        DataFrame: corr matrix, 列名=基金代码
    """
    if nav_returns.empty or nav_returns.shape[1] < 2:
        return pd.DataFrame()
    return nav_returns.corr()


def get_all_risk_metrics(days: int = 250) -> dict:
    """计算所有风险指标

    Returns:
        dict with keys:
        - portfolio: 组合级指标
        - funds: 各基金指标 {code: {...}}
        - benchmark: 沪深300指标
        - correlation: 相关性矩阵
    """
    # 拉取收益率数据
    nav_returns = get_all_nav_returns(days=days)
    weights = calc_portfolio_weights()
    portfolio_returns = calc_portfolio_daily_returns(nav_returns, weights)
    benchmark_returns = get_benchmark_returns(days=days)

    result = {
        "计算日期": datetime.now().strftime("%Y-%m-%d"),
        "数据天数": len(nav_returns) if not nav_returns.empty else 0,
        "portfolio": {},
        "funds": {},
        "benchmark": {},
        "correlation": None,
    }

    # ── 组合级指标 ──
    if not portfolio_returns.empty:
        dd = calc_max_drawdown(portfolio_returns)
        result["portfolio"] = {
            "年化波动率": calc_annualized_vol(portfolio_returns),
            "最大回撤": dd["max_dd"],
            "回撤起始": dd["start"],
            "回撤结束": dd["end"],
            "恢复日期": dd["recovery"],
            "夏普比": calc_sharpe(portfolio_returns),
            "Calmar比": calc_calmar(portfolio_returns),
            "VaR_95": calc_var(portfolio_returns, 0.05),
            "VaR_99": calc_var(portfolio_returns, 0.01),
            "日收益率均值": round(portfolio_returns.mean(), 2),
            "日收益率标准差": round(portfolio_returns.std(), 2),
            "年化收益率": round(portfolio_returns.mean() * TRADING_DAYS, 2),
            "正收益天数": int((portfolio_returns > 0).sum()),
            "总天数": len(portfolio_returns),
            "胜率": round((portfolio_returns > 0).mean() * 100, 1),
        }

    # ── 各基金指标 ──
    for code in FUNDS:
        if code not in nav_returns.columns:
            continue
        r = nav_returns[code].dropna()
        if len(r) < MIN_DATA_DAYS:
            continue
        dd = calc_max_drawdown(r)
        result["funds"][code] = {
            "名称": FUNDS[code]["name"],
            "年化波动率": calc_annualized_vol(r),
            "最大回撤": dd["max_dd"],
            "夏普比": calc_sharpe(r),
            "年化收益率": round(r.mean() * TRADING_DAYS, 2),
            "胜率": round((r > 0).mean() * 100, 1),
            "数据天数": len(r),
        }

    # ── 沪深300指标 ──
    if not benchmark_returns.empty:
        dd = calc_max_drawdown(benchmark_returns)
        result["benchmark"] = {
            "年化波动率": calc_annualized_vol(benchmark_returns),
            "最大回撤": dd["max_dd"],
            "夏普比": calc_sharpe(benchmark_returns),
            "年化收益率": round(benchmark_returns.mean() * TRADING_DAYS, 2),
            "数据天数": len(benchmark_returns),
        }

    # ── 相关性矩阵 ──
    corr = calc_correlation_matrix(nav_returns)
    if not corr.empty:
        result["correlation"] = corr

    return result


# ── Beta/Alpha ──


def calc_beta_alpha(fund_returns: pd.Series,
                     benchmark_returns: pd.Series) -> dict:
    """计算Beta和Alpha

    Beta = Cov(fund, benchmark) / Var(benchmark)
    Alpha = 年化基金收益 - (无风险利率 + Beta * (年化基准收益 - 无风险利率))

    Returns:
        {"beta": float, "alpha": float (annualized %)}
    """
    aligned = pd.concat([fund_returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < MIN_DATA_DAYS:
        return {"beta": None, "alpha": None}

    fund_col = aligned.columns[0]
    bench_col = aligned.columns[1]

    cov = aligned[fund_col].cov(aligned[bench_col])
    var_bench = aligned[bench_col].var()
    beta = cov / var_bench if var_bench > 0 else 0

    ann_fund = aligned[fund_col].mean() * TRADING_DAYS
    ann_bench = aligned[bench_col].mean() * TRADING_DAYS
    alpha = ann_fund - (RISK_FREE_RATE * 100 + beta * (ann_bench - RISK_FREE_RATE * 100))

    return {"beta": round(beta, 2), "alpha": round(alpha, 2)}


def print_risk_metrics(metrics: dict):
    """CLI 打印风险指标"""
    print(f"\n{'='*55}")
    print(f"  组合风险指标  {metrics['计算日期']}")
    print(f"{'='*55}")

    p = metrics["portfolio"]
    if p:
        print(f"\n  组合  (数据天数: {p['总天数']})")
        print(f"  {'-'*45}")
        print(f"    年化收益率:   {p['年化收益率']:>+7.2f}%")
        print(f"    年化波动率:   {p['年化波动率']:>7.2f}%")
        print(f"    夏普比:       {p['夏普比']:>7.2f}")
        print(f"    Calmar比:     {p['Calmar比']:>7.2f}")
        print(f"    最大回撤:     {p['最大回撤']:>7.2f}%")
        if p.get('回撤起始'):
            print(f"    回撤区间:     {p['回撤起始'].strftime('%m-%d')} → {p['回撤结束'].strftime('%m-%d')}")
        print(f"    VaR(95%):     {p['VaR_95']:>7.2f}%")
        print(f"    VaR(99%):     {p['VaR_99']:>7.2f}%")
        print(f"    胜率:         {p['胜率']:>7.1f}%")
        print(f"    正收益天数:   {p['正收益天数']}/{p['总天数']}")

    # 沪深300 对比
    b = metrics["benchmark"]
    if b:
        print(f"\n  沪深300 (数据天数: {b['数据天数']})")
        print(f"  {'-'*45}")
        print(f"    年化收益率:   {b['年化收益率']:>+7.2f}%")
        print(f"    年化波动率:   {b['年化波动率']:>7.2f}%")
        print(f"    夏普比:       {b['夏普比']:>7.2f}")
        print(f"    最大回撤:     {b['最大回撤']:>7.2f}%")

    # 各基金
    if metrics["funds"]:
        print(f"\n  各基金指标")
        print(f"  {'-'*55}")
        print(f"  {'名称':16s} {'年化收益':>8} {'波动率':>7} {'夏普':>6} {'回撤':>6} {'胜率':>5}")
        print(f"  {'-'*55}")
        for code, f in metrics["funds"].items():
            name = f['名称'][:14]
            ret = f.get('年化收益率', 0)
            vol = f.get('年化波动率', 0)
            sharpe = f.get('夏普比', 0)
            dd = f.get('最大回撤', 0)
            wr = f.get('胜率', 0)
            ret_s = f"{ret:>+7.1f}%" if isinstance(ret, (int, float)) else f"{'N/A':>8}"
            vol_s = f"{vol:>6.1f}%" if isinstance(vol, (int, float)) else f"{'N/A':>7}"
            sharpe_s = f"{sharpe:>5.2f}" if isinstance(sharpe, (int, float)) else f"{'N/A':>6}"
            dd_s = f"{dd:>5.1f}%" if isinstance(dd, (int, float)) else f"{'N/A':>6}"
            wr_s = f"{wr:>4.1f}%" if isinstance(wr, (int, float)) else f"{'N/A':>5}"
            print(f"  {name:16s} {ret_s} {vol_s} {sharpe_s} {dd_s} {wr_s}")

    # Beta/Alpha
    if p and b and b.get("年化收益率") is not None:
        from portfolio import calc_portfolio
        pf = calc_portfolio()
        weights = calc_portfolio_weights()
        nav_returns = get_all_nav_returns()
        portfolio_ret = calc_portfolio_daily_returns(nav_returns, weights)
        bench_ret = get_benchmark_returns()
        if not portfolio_ret.empty and not bench_ret.empty:
            ba = calc_beta_alpha(portfolio_ret, bench_ret)
            if ba["beta"] is not None:
                print(f"\n  Beta/Alpha (vs 沪深300)")
                print(f"  {'-'*45}")
                print(f"    Beta:  {ba['beta']:>7.2f}")
                print(f"    Alpha: {ba['alpha']:>+7.2f}%")

    print(f"\n{'='*55}\n")


def print_correlation(corr_df: pd.DataFrame):
    """打印相关性矩阵"""
    if corr_df is None or corr_df.empty:
        print("\n无相关性数据\n")
        return
    print(f"\n{'='*55}")
    print(f"  基金相关性矩阵")
    print(f"{'='*55}")
    # 显示格式化的矩阵
    names = {c: FUNDS.get(c, {}).get("name", c)[:6] for c in corr_df.columns}
    renamed = corr_df.rename(columns=names, index=names)
    # 四舍五入到2位
    display = renamed.round(2)
    print(display.to_string())
    print()
