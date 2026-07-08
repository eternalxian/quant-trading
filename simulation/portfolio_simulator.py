"""Deterministic, side-effect-free target-weight portfolio simulator."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Iterable, Tuple

from .models import (
    PortfolioSnapshot,
    PositionSimulation,
    SimulationInvariants,
    SimulationRequest,
    SimulationResult,
    SimulationSummary,
    SimulationValidationError,
)


_CENT = Decimal("0.01")
_WEIGHT_STEP = Decimal("0.0001")
_HHI_STEP = Decimal("0.000001")
_WEIGHT_TOLERANCE = Decimal("0.01")
_ASSET_TOLERANCE = Decimal("0.02")


def _decimal(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SimulationValidationError(f"{field} must be a finite number") from exc
    if not result.is_finite():
        raise SimulationValidationError(f"{field} must be a finite number")
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _weight(value: Decimal) -> Decimal:
    return value.quantize(_WEIGHT_STEP, rounding=ROUND_HALF_UP)


def _hhi(weights: Iterable[Decimal]) -> Decimal:
    result = sum(((w / Decimal("100")) ** 2 for w in weights), Decimal("0"))
    return result.quantize(_HHI_STEP, rounding=ROUND_HALF_UP)


def _as_float(value: Decimal) -> float:
    return float(value)


def _validate_and_normalize(snapshot: PortfolioSnapshot, request: SimulationRequest):
    total = _decimal(snapshot.total_asset, "total_asset")
    cash = _decimal(snapshot.cash, "cash")
    if total <= 0:
        raise SimulationValidationError("total_asset must be greater than 0")
    if cash < 0:
        raise SimulationValidationError("cash cannot be negative")

    positions = tuple(snapshot.positions)
    codes = [p.code for p in positions]
    if any(not isinstance(code, str) or not code.strip() for code in codes):
        raise SimulationValidationError("position code cannot be empty")
    if len(codes) != len(set(codes)):
        raise SimulationValidationError("position codes must be unique")

    current_values: Dict[str, Decimal] = {}
    names: Dict[str, str] = {}
    for position in positions:
        value = _decimal(position.value, f"position[{position.code}].value")
        supplied_weight = _decimal(position.weight, f"position[{position.code}].weight")
        if value < 0:
            raise SimulationValidationError(f"position[{position.code}].value cannot be negative")
        if supplied_weight < 0 or supplied_weight > 100:
            raise SimulationValidationError(f"position[{position.code}].weight must be between 0 and 100")
        current_values[position.code] = _money(value)
        names[position.code] = position.name

    current_total = sum(current_values.values(), Decimal("0")) + _money(cash)
    total_money = _money(total)
    if abs(current_total - total_money) > _ASSET_TOLERANCE:
        raise SimulationValidationError(
            f"current assets are not conserved: positions+cash={current_total}, total_asset={total_money}"
        )

    try:
        target_items = dict(request.target_weights)
    except Exception as exc:
        raise SimulationValidationError("target_weights must be a mapping") from exc
    unknown = sorted(set(target_items) - set(codes))
    if unknown:
        raise SimulationValidationError(f"unknown fund code(s): {', '.join(unknown)}")

    target_weights: Dict[str, Decimal] = {}
    for code in codes:
        value = _decimal(target_items.get(code, 0), f"target_weights[{code}]")
        if value < 0 or value > 100:
            raise SimulationValidationError(f"target_weights[{code}] must be between 0 and 100")
        target_weights[code] = value

    target_cash_weight = _decimal(request.target_cash_weight, "target_cash_weight")
    if target_cash_weight < 0 or target_cash_weight > 100:
        raise SimulationValidationError("target_cash_weight must be between 0 and 100")

    weight_sum = sum(target_weights.values(), Decimal("0")) + target_cash_weight
    if abs(weight_sum - Decimal("100")) > _WEIGHT_TOLERANCE:
        raise SimulationValidationError(f"target weights plus cash must equal 100, got {weight_sum}")

    return total_money, _money(cash), positions, current_values, names, target_weights, target_cash_weight, weight_sum


def _rounded_targets(
    total: Decimal, target_weights: Dict[str, Decimal], target_cash_weight: Decimal
) -> Tuple[Dict[str, Decimal], Decimal]:
    target_values = {code: _money(total * weight / Decimal("100")) for code, weight in target_weights.items()}
    target_cash = _money(total * target_cash_weight / Decimal("100"))
    residual = total - (sum(target_values.values(), Decimal("0")) + target_cash)
    if residual:
        buckets = [(target_cash_weight, "__cash__")] + [(weight, code) for code, weight in target_weights.items()]
        _, selected = max(buckets, key=lambda item: (item[0], item[1]))
        if selected == "__cash__":
            target_cash += residual
        else:
            target_values[selected] += residual
    return target_values, target_cash


def simulate_portfolio(snapshot: PortfolioSnapshot, request: SimulationRequest) -> SimulationResult:
    """Simulate target weights without changing the input snapshot or external state."""
    (
        total,
        current_cash,
        positions,
        current_values,
        names,
        target_weights,
        target_cash_weight,
        weight_sum,
    ) = _validate_and_normalize(snapshot, request)
    target_values, target_cash = _rounded_targets(total, target_weights, target_cash_weight)

    position_results = []
    deltas = []
    current_weights = []
    for position in positions:
        code = position.code
        current_value = current_values[code]
        target_value = target_values[code]
        delta = _money(target_value - current_value)
        current_weight = _weight(current_value / total * Decimal("100"))
        target_weight = _weight(target_weights[code])
        action = "buy" if delta > 0 else "sell" if delta < 0 else "hold"
        deltas.append(delta)
        current_weights.append(current_weight)
        position_results.append(
            PositionSimulation(
                code=code,
                name=names[code],
                current_value=_as_float(current_value),
                target_value=_as_float(target_value),
                trade_delta=_as_float(delta),
                action=action,
                current_weight=_as_float(current_weight),
                target_weight=_as_float(target_weight),
            )
        )

    buy_total = _money(sum((d for d in deltas if d > 0), Decimal("0")))
    sell_total = _money(-sum((d for d in deltas if d < 0), Decimal("0")))
    turnover = _weight(
        Decimal("0.5") * sum((abs(d) for d in deltas), Decimal("0")) / total * Decimal("100")
    )
    target_weight_values = [_weight(target_weights[p.code]) for p in positions]
    current_max = max(current_weights, default=Decimal("0"))
    target_max = max(target_weight_values, default=Decimal("0"))
    current_hhi = _hhi(current_weights)
    target_hhi = _hhi(target_weight_values)

    warnings = []
    for code, weight in sorted(target_weights.items()):
        if weight > 50:
            warnings.append(f"{code} target weight {weight}% exceeds 50%: high concentration")
        elif weight > 30:
            warnings.append(f"{code} target weight {weight}% exceeds 30%: concentration risk")
    if target_hhi > current_hhi:
        warnings.append("target HHI is higher than current HHI: concentration increases")
    if turnover > 50:
        warnings.append("turnover exceeds 50%: high turnover")

    target_sum = sum(target_values.values(), Decimal("0")) + target_cash
    invariants = SimulationInvariants(
        asset_conserved=target_sum == total,
        weights_sum_to_100=abs(weight_sum - Decimal("100")) <= _WEIGHT_TOLERANCE,
    )

    summary = SimulationSummary(
        buy_total=_as_float(buy_total),
        sell_total=_as_float(sell_total),
        net_cash_change=_as_float(_money(target_cash - current_cash)),
        turnover_pct=_as_float(turnover),
        current_max_weight=_as_float(current_max),
        target_max_weight=_as_float(target_max),
        current_hhi=_as_float(current_hhi),
        target_hhi=_as_float(target_hhi),
        max_weight_change=_as_float(_weight(target_max - current_max)),
        hhi_change=_as_float((target_hhi - current_hhi).quantize(_HHI_STEP, rounding=ROUND_HALF_UP)),
    )

    return SimulationResult(
        scenario_name=str(request.scenario_name),
        result_type="simulation",
        total_asset=_as_float(total),
        current_cash=_as_float(current_cash),
        target_cash=_as_float(target_cash),
        current_cash_weight=_as_float(_weight(current_cash / total * Decimal("100"))),
        target_cash_weight=_as_float(_weight(target_cash_weight)),
        positions=tuple(position_results),
        summary=summary,
        warnings=tuple(warnings),
        invariants=invariants,
    )
