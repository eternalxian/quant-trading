"""Data contracts for portfolio simulation."""

from dataclasses import asdict, dataclass
from typing import Mapping, Tuple


class SimulationValidationError(ValueError):
    """Raised when a scenario cannot be simulated without guessing user intent."""


@dataclass(frozen=True)
class PositionSnapshot:
    code: str
    name: str
    value: float
    weight: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    total_asset: float
    cash: float
    positions: Tuple[PositionSnapshot, ...]


@dataclass(frozen=True)
class SimulationRequest:
    target_weights: Mapping[str, float]
    target_cash_weight: float
    scenario_name: str = "portfolio-simulation"


@dataclass(frozen=True)
class PositionSimulation:
    code: str
    name: str
    current_value: float
    target_value: float
    trade_delta: float
    action: str
    current_weight: float
    target_weight: float


@dataclass(frozen=True)
class SimulationSummary:
    buy_total: float
    sell_total: float
    net_cash_change: float
    turnover_pct: float
    current_max_weight: float
    target_max_weight: float
    current_hhi: float
    target_hhi: float
    max_weight_change: float
    hhi_change: float


@dataclass(frozen=True)
class SimulationInvariants:
    asset_conserved: bool
    weights_sum_to_100: bool


@dataclass(frozen=True)
class SimulationResult:
    scenario_name: str
    result_type: str
    total_asset: float
    current_cash: float
    target_cash: float
    current_cash_weight: float
    target_cash_weight: float
    positions: Tuple[PositionSimulation, ...]
    summary: SimulationSummary
    warnings: Tuple[str, ...]
    invariants: SimulationInvariants

    def to_dict(self) -> dict:
        """Return a JSON-friendly copy without exposing mutable internal state."""
        return asdict(self)
