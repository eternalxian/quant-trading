"""P4-1 pure portfolio simulation tests."""

import ast
import copy
import os
import sys
import time
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from simulation.adapter import portfolio_result_to_snapshot
from simulation.models import PortfolioSnapshot, PositionSnapshot, SimulationRequest, SimulationValidationError
from simulation.portfolio_simulator import simulate_portfolio


def basic_snapshot():
    return PortfolioSnapshot(
        total_asset=100_000,
        cash=10_000,
        positions=(
            PositionSnapshot("A", "Fund A", 60_000, 60),
            PositionSnapshot("B", "Fund B", 30_000, 30),
        ),
    )


class PortfolioSimulationTests(unittest.TestCase):
    def test_valid_target_weight_simulation(self):
        result = simulate_portfolio(
            basic_snapshot(), SimulationRequest({"A": 40, "B": 40}, 20, "balanced")
        )
        self.assertEqual(result.result_type, "simulation")
        self.assertEqual(result.scenario_name, "balanced")
        self.assertEqual(result.summary.buy_total, 10_000)
        self.assertEqual(result.summary.sell_total, 20_000)
        self.assertEqual(result.summary.turnover_pct, 15.0)
        self.assertEqual(result.summary.net_cash_change, 10_000)
        self.assertTrue(result.invariants.asset_conserved)
        self.assertTrue(result.invariants.weights_sum_to_100)

    def test_weight_sum_below_100_rejected(self):
        with self.assertRaisesRegex(SimulationValidationError, "must equal 100"):
            simulate_portfolio(basic_snapshot(), SimulationRequest({"A": 30, "B": 30}, 20))

    def test_weight_sum_above_100_rejected(self):
        with self.assertRaisesRegex(SimulationValidationError, "must equal 100"):
            simulate_portfolio(basic_snapshot(), SimulationRequest({"A": 60, "B": 30}, 20))

    def test_negative_weight_rejected(self):
        with self.assertRaisesRegex(SimulationValidationError, "between 0 and 100"):
            simulate_portfolio(basic_snapshot(), SimulationRequest({"A": -1, "B": 81}, 20))

    def test_unknown_fund_rejected(self):
        with self.assertRaisesRegex(SimulationValidationError, "unknown fund code"):
            simulate_portfolio(basic_snapshot(), SimulationRequest({"A": 40, "B": 30, "C": 10}, 20))

    def test_duplicate_position_code_rejected(self):
        snapshot = PortfolioSnapshot(
            100,
            0,
            (PositionSnapshot("A", "A1", 50, 50), PositionSnapshot("A", "A2", 50, 50)),
        )
        with self.assertRaisesRegex(SimulationValidationError, "must be unique"):
            simulate_portfolio(snapshot, SimulationRequest({"A": 100}, 0))

    def test_zero_total_rejected(self):
        with self.assertRaisesRegex(SimulationValidationError, "greater than 0"):
            simulate_portfolio(PortfolioSnapshot(0, 0, ()), SimulationRequest({}, 100))

    def test_all_cash_portfolio(self):
        result = simulate_portfolio(PortfolioSnapshot(1000, 1000, ()), SimulationRequest({}, 100))
        self.assertEqual(result.target_cash, 1000)
        self.assertEqual(result.positions, ())
        self.assertEqual(result.summary.turnover_pct, 0)
        self.assertTrue(result.invariants.asset_conserved)

    def test_omitted_fund_means_clear_position(self):
        result = simulate_portfolio(basic_snapshot(), SimulationRequest({"B": 80}, 20))
        by_code = {p.code: p for p in result.positions}
        self.assertEqual(by_code["A"].target_value, 0)
        self.assertEqual(by_code["A"].action, "sell")
        self.assertEqual(by_code["A"].trade_delta, -60_000)

    def test_concentration_warnings_for_30_and_50(self):
        over_30 = simulate_portfolio(basic_snapshot(), SimulationRequest({"A": 40, "B": 40}, 20))
        self.assertTrue(any("exceeds 30%" in warning for warning in over_30.warnings))
        over_50 = simulate_portfolio(basic_snapshot(), SimulationRequest({"A": 60, "B": 20}, 20))
        self.assertTrue(any("exceeds 50%" in warning for warning in over_50.warnings))

    def test_high_turnover_warning(self):
        snapshot = PortfolioSnapshot(
            100_000,
            0,
            (PositionSnapshot("A", "A", 100_000, 100), PositionSnapshot("B", "B", 0, 0)),
        )
        result = simulate_portfolio(snapshot, SimulationRequest({"A": 0, "B": 100}, 0))
        self.assertEqual(result.summary.turnover_pct, 100)
        self.assertTrue(any("high turnover" in warning for warning in result.warnings))

    def test_hhi_increase_and_decrease(self):
        snapshot = PortfolioSnapshot(
            100,
            0,
            (PositionSnapshot("A", "A", 50, 50), PositionSnapshot("B", "B", 50, 50)),
        )
        increased = simulate_portfolio(snapshot, SimulationRequest({"A": 100, "B": 0}, 0))
        self.assertGreater(increased.summary.target_hhi, increased.summary.current_hhi)
        self.assertTrue(any("HHI" in warning for warning in increased.warnings))

        concentrated = PortfolioSnapshot(
            100,
            0,
            (PositionSnapshot("A", "A", 100, 100), PositionSnapshot("B", "B", 0, 0)),
        )
        decreased = simulate_portfolio(concentrated, SimulationRequest({"A": 50, "B": 50}, 0))
        self.assertLess(decreased.summary.target_hhi, decreased.summary.current_hhi)

    def test_rounding_reconciles_assets_to_the_cent(self):
        snapshot = PortfolioSnapshot(
            100.01,
            33.34,
            (PositionSnapshot("A", "A", 33.34, 33.3367), PositionSnapshot("B", "B", 33.33, 33.3267)),
        )
        result = simulate_portfolio(snapshot, SimulationRequest({"A": 33.33, "B": 33.33}, 33.34))
        target_total = sum(p.target_value for p in result.positions) + result.target_cash
        self.assertAlmostEqual(target_total, 100.01, places=2)
        self.assertTrue(result.invariants.asset_conserved)

    def test_input_objects_are_not_mutated(self):
        snapshot = basic_snapshot()
        weights = {"A": 40, "B": 40}
        request = SimulationRequest(weights, 20)
        before_snapshot = copy.deepcopy(snapshot)
        before_weights = copy.deepcopy(weights)
        simulate_portfolio(snapshot, request)
        self.assertEqual(snapshot, before_snapshot)
        self.assertEqual(weights, before_weights)

    def test_deterministic_repeated_execution(self):
        request = SimulationRequest({"A": 40, "B": 40}, 20)
        first = simulate_portfolio(basic_snapshot(), request)
        second = simulate_portfolio(basic_snapshot(), request)
        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_core_has_no_forbidden_imports(self):
        path = os.path.join(BASE_DIR, "simulation", "portfolio_simulator.py")
        with open(path, encoding="utf-8") as source:
            tree = ast.parse(source.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported.isdisjoint({"db", "data", "server", "portfolio"}), imported)

    def test_adapter_is_read_only(self):
        raw = {
            "总资产": 1000,
            "余额宝": 100,
            "基金": [
                {"code": "A", "name": "Fund A", "市值": 600},
                {"code": "B", "name": "Fund B", "市值": 300},
            ],
        }
        before = copy.deepcopy(raw)
        snapshot = portfolio_result_to_snapshot(raw)
        self.assertEqual(raw, before)
        self.assertEqual(snapshot.total_asset, 1000)
        self.assertEqual(snapshot.positions[0].weight, 60)

    def test_standard_fixture_completes_under_100ms(self):
        started = time.perf_counter()
        simulate_portfolio(basic_snapshot(), SimulationRequest({"A": 40, "B": 40}, 20))
        self.assertLess(time.perf_counter() - started, 0.1)

    def test_current_asset_mismatch_rejected(self):
        snapshot = PortfolioSnapshot(100, 10, (PositionSnapshot("A", "A", 80, 80),))
        with self.assertRaisesRegex(SimulationValidationError, "not conserved"):
            simulate_portfolio(snapshot, SimulationRequest({"A": 80}, 20))


if __name__ == "__main__":
    unittest.main(verbosity=2)
