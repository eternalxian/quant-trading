"""ETF 轮动引擎 — 接口预留层，封装现有 rotation.py 逻辑"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("quant.etf")


@dataclass
class EtfRotationResult:
    etf_code: str
    etf_name: str
    rank: int
    score: float
    momentum: float
    action: str          # buy / sell / hold
    reason: str
    weight: float = 0.0  # 建议仓位比例


def get_rotation_signals(days: int = 60) -> list[EtfRotationResult]:
    """获取 ETF 轮动信号，封装现有逻辑"""
    from signals import generate_signals

    sigs = generate_signals(days=days)
    results = []

    for i, s in enumerate(sigs.get("信号", [])):
        action_map = {"买入": "buy", "卖出": "sell", "观望": "hold"}
        results.append(EtfRotationResult(
            etf_code=s.get("code", ""),
            etf_name=s.get("name", ""),
            rank=i + 1,
            score=s.get("评分", 0),
            momentum=float(s.get("动量", "0").replace("%", "")) if s.get("动量") else 0,
            action=action_map.get(s.get("操作", ""), "hold"),
            reason=s.get("理由", ""),
        ))

    return results


def get_top_pick() -> Optional[EtfRotationResult]:
    """获取排名第一的 ETF"""
    results = get_rotation_signals()
    if results:
        return results[0]
    return None
