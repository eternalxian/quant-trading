"""
信号计算基础设施
SignalResult + BaseSignalCalculator ABC
"""
from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np


_registry: dict[str, type] = {}


def register(cls):
    _registry[cls.strategy_name] = cls
    return cls


@dataclass
class SignalResult:
    signal: str       # 'buy' | 'sell' | 'hold'
    score: float      # 正=看多, 负=看空
    reason: str       # 中文解释
    detail: dict = field(default_factory=dict)


class BaseSignalCalculator(ABC):
    strategy_name: str = ""
    strategy_type: str = ""

    def __init__(self, params: dict = None):
        self.params = params or {}
        self.strategy_id: Optional[int] = None

    def _get_array(self, data: pd.DataFrame, column: str) -> np.ndarray:
        if column in data.columns:
            return data[column].values.astype(float)
        nav_map = {
            "close": "单位净值", "high": "单位净值", "low": "单位净值",
            "open": "单位净值", "volume": None,
        }
        alt = nav_map.get(column)
        if alt and alt in data.columns:
            return data[alt].values.astype(float)
        if alt is None:
            return np.zeros(len(data))
        raise KeyError(f"Column '{column}' not found")

    def get_close(self, data: pd.DataFrame) -> np.ndarray:
        return self._get_array(data, "close")

    def get_high(self, data: pd.DataFrame) -> np.ndarray:
        return self._get_array(data, "high")

    def get_low(self, data: pd.DataFrame) -> np.ndarray:
        return self._get_array(data, "low")

    def get_open(self, data: pd.DataFrame) -> np.ndarray:
        return self._get_array(data, "open")

    def get_volume(self, data: pd.DataFrame) -> np.ndarray:
        return self._get_array(data, "volume")

    def resolve_strategy_id(self) -> Optional[int]:
        if self.strategy_id is not None:
            return self.strategy_id
        from db import get_strategy
        s = get_strategy(self.strategy_name)
        if s:
            self.strategy_id = s["id"]
        return self.strategy_id

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> SignalResult:
        """单一标的信号计算"""

    def compute_all(self, data_dict: dict) -> dict:
        return {
            code: self.compute(df)
            for code, df in data_dict.items()
            if df is not None and not df.empty
        }

    def persist_signals(self, results: dict, date: str = None):
        sid = self.resolve_strategy_id()
        if sid is None:
            return
        from db import add_strategy_signal
        from datetime import datetime as dt
        if date is None:
            date = dt.now().strftime("%Y-%m-%d")
        for code, sr in results.items():
            add_strategy_signal(sid, code, sr.signal, sr.score,
                                detail=str(sr.detail), date=date)
