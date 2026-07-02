"""数据校验器 — 检测缺失/异常/重复数据，输出质量评分"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger("quant.validator")


@dataclass
class QualityReport:
    symbol: str
    quality: int = 100           # 0-100
    missing_dates: bool = False
    abnormal_jump: bool = False
    duplicate_rows: bool = False
    stale_data: bool = False     # 数据超过预期天数未更新
    details: str = ""


def validate_kline(df: pd.DataFrame, symbol: str, expected_days: int = 120) -> QualityReport:
    """校验个股/ETF 日K线质量

    Args:
        df: OHLCV DataFrame (date, open, close, high, low, volume)
        symbol: 股票/ETF 代码
        expected_days: 预期数据天数

    Returns:
        QualityReport with quality score
    """
    report = QualityReport(symbol=symbol)
    issues = []

    if df is None or df.empty:
        report.quality = 0
        report.details = "无数据"
        return report

    # 1. 日期连续性
    if "date" in df.columns:
        dates = pd.to_datetime(df["date"]).sort_values()
        if len(dates) >= 2:
            gaps = dates.diff().dropna()
            # 超过 5 个交易日的间隔视为缺失
            big_gaps = gaps[gaps > timedelta(days=7)]
            if len(big_gaps) > 0:
                report.missing_dates = True
                report.quality -= 20
                issues.append(f"日期缺口 {len(big_gaps)} 处")

    # 2. 数据量
    if len(df) < expected_days * 0.5:
        report.stale_data = True
        report.quality -= 30
        issues.append(f"数据量不足 {len(df)}/{expected_days}")

    # 3. 异常价格跳变
    if "close" in df.columns and len(df) >= 2:
        pct_changes = df["close"].pct_change().dropna().abs()
        # 单日涨跌幅 > 15% 视为异常
        jumps = pct_changes[pct_changes > 0.15]
        if len(jumps) > 0:
            report.abnormal_jump = True
            report.quality -= 25
            issues.append(f"异常价格跳变 {len(jumps)} 处")

    # 4. 重复行
    if df.duplicated().any():
        report.duplicate_rows = True
        report.quality -= 15
        issues.append("存在重复行")

    # 5. 检查最新日期是否过期
    if "date" in df.columns and len(df) >= 1:
        latest = pd.to_datetime(df["date"]).max()
        days_since = (datetime.now() - latest).days
        if days_since > 3:
            report.stale_data = True
            report.quality -= 20
            issues.append(f"最新数据 {days_since} 天前")

    report.quality = max(0, report.quality)
    report.details = "; ".join(issues) if issues else "数据质量正常"

    if report.quality < 70:
        logger.warning(f"{symbol} 数据质量 {report.quality}: {report.details}")
    else:
        logger.debug(f"{symbol} 数据质量 {report.quality}")

    return report


def validate_holdings(portfolio: dict) -> QualityReport:
    """校验持仓数据"""
    report = QualityReport(symbol="PORTFOLIO")
    issues = []

    funds = portfolio.get("基金", [])
    if not funds:
        report.quality = 0
        report.details = "无持仓数据"
        return report

    # 检查是否有 0 市值
    zeros = [f for f in funds if f.get("市值", 0) <= 0]
    if zeros:
        report.quality -= 10 * len(zeros)
        issues.append(f"{len(zeros)} 只基金市值为 0")

    # 检查占比总和
    total_weight = sum(f.get("占比", 0) for f in funds)
    if abs(total_weight - 100) > 5:
        report.quality -= 10
        issues.append(f"占比总和 {total_weight:.1f}% 偏离 100%")

    report.quality = max(0, report.quality)
    report.details = "; ".join(issues) if issues else "持仓数据正常"
    return report
