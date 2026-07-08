"""Read-only adapters between the existing portfolio output and simulation models."""

from .models import PortfolioSnapshot, PositionSnapshot


def portfolio_result_to_snapshot(portfolio_result: dict) -> PortfolioSnapshot:
    """Convert calc_portfolio() output without mutating it."""
    total = float(portfolio_result.get("总资产", 0) or 0)
    cash = float(portfolio_result.get("余额宝", 0) or 0)
    positions = []
    for fund in portfolio_result.get("基金", ()):
        value = float(fund.get("市值", 0) or 0)
        if value < 0:
            value = float(value)
        weight = value / total * 100 if total > 0 else 0.0
        positions.append(
            PositionSnapshot(
                code=str(fund.get("code", "")),
                name=str(fund.get("name", "")),
                value=value,
                weight=weight,
            )
        )
    return PortfolioSnapshot(total_asset=total, cash=cash, positions=tuple(positions))


def load_current_snapshot() -> PortfolioSnapshot:
    """Load the current portfolio through the existing read-only calculation boundary."""
    from portfolio import calc_portfolio

    return portfolio_result_to_snapshot(calc_portfolio())
