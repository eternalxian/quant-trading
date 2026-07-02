"""
信号系统 - 统一策略注册与运行
"""
import os
import importlib
from signals.base import BaseSignalCalculator, SignalResult, register, _registry

# 向后兼容：从旧 signals.py (现 rotation.py) 导出
from signals.rotation import generate_signals, print_signals, save_signals, load_signal_history

# Re-export for convenience
__all__ = ['BaseSignalCalculator', 'SignalResult', 'register', '_registry',
           'generate_signals', 'print_signals', 'save_signals', 'load_signal_history',
           'get_calculator', 'list_calculators', 'compute_all_signals', 'print_all_signals']

# 自动发现并加载所有策略模块
def _discover_strategies():
    _dir = os.path.dirname(__file__)
    for fname in sorted(os.listdir(_dir)):
        if not fname.endswith('.py'):
            continue
        if fname.startswith('_') or fname in ('base.py', 'common.py', 'rotation.py'):
            continue
        mod_name = f"signals.{fname[:-3]}"
        importlib.import_module(mod_name)


def get_calculator(name: str, params: dict = None) -> BaseSignalCalculator:
    cls = _registry.get(name)
    if cls is None:
        raise KeyError(f"Unknown strategy: {name}. Available: {sorted(_registry)}")
    return cls(params=params)


def list_calculators() -> list[str]:
    return sorted(_registry)


def compute_all_signals(data_dict: dict, strategy_names: list[str] = None,
                        persist: bool = True) -> dict:
    names = strategy_names or list(_registry)
    results = {}
    for name in names:
        try:
            calc = get_calculator(name)
            codes = calc.compute_all(data_dict)
            if persist:
                calc.persist_signals(codes)
            results[name] = codes
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def print_all_signals(results: dict):
    total_s = len(results)
    buy_count = sell_count = hold_count = err_count = 0
    print(f"\n{'='*70}")
    print(f"  全策略信号汇总 ({total_s} 个策略)")
    print(f"{'='*70}")

    for sname, codes in sorted(results.items()):
        if isinstance(codes, dict) and "error" in codes:
            print(f"  [{sname}] 错误: {codes['error']}")
            err_count += 1
            continue
        if not isinstance(codes, dict):
            continue
        signals = [s for s in codes.values() if not isinstance(s, str)]
        buys = sum(1 for s in signals if hasattr(s, 'signal') and s.signal == 'buy')
        sells = sum(1 for s in signals if hasattr(s, 'signal') and s.signal == 'sell')
        holds = sum(1 for s in signals if hasattr(s, 'signal') and s.signal == 'hold')
        buy_count += buys; sell_count += sells; hold_count += holds
        print(f"\n  ── {sname} ──")
        for code, sr in sorted(codes.items()):
            if hasattr(sr, 'signal'):
                tag = {"buy": "▲买入", "sell": "▼卖出", "hold": "─观望"}.get(sr.signal, sr.signal)
                print(f"  {code:>7s} {tag:6s} {sr.score:+8.4f}  {sr.reason}")

    print(f"\n  {'='*50}")
    print(f"  总计: ▲买入 {buy_count}  ▼卖出 {sell_count}  ─观望 {hold_count}  错误 {err_count}")
    print(f"{'='*70}\n")


_discover_strategies()
