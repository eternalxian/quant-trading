"""熔断器 — 异常保护，防止连锁故障"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger("quant.circuit")


@dataclass
class CircuitState:
    closed: bool = True          # True=正常, False=熔断
    opened_at: datetime = None
    reason: str = ""
    consecutive_failures: int = 0
    max_failures: int = 3
    cooldown_seconds: int = 300   # 熔断冷却 5 分钟
    history: list = field(default_factory=list)


_state = CircuitState()


def record_success():
    """记录一次成功，重置连续失败计数"""
    _state.consecutive_failures = 0
    if not _state.closed:
        # 冷却期到自动恢复
        if _state.opened_at and (datetime.now() - _state.opened_at).seconds > _state.cooldown_seconds:
            _state.closed = True
            logger.info("熔断冷却期到，自动恢复")


def record_failure(reason: str):
    """记录一次失败，连续失败达到阈值触发熔断"""
    _state.consecutive_failures += 1
    _state.history.append({"time": datetime.now().isoformat(), "reason": reason})
    if len(_state.history) > 20:
        _state.history = _state.history[-20:]

    if _state.consecutive_failures >= _state.max_failures:
        _state.closed = False
        _state.opened_at = datetime.now()
        _state.reason = reason
        logger.critical(f"熔断触发: {reason} (连续 {_state.consecutive_failures} 次失败)")


def is_closed() -> bool:
    """当前是否允许交易"""
    return _state.closed


def status() -> dict:
    return {
        "closed": _state.closed,
        "opened_at": _state.opened_at.isoformat() if _state.opened_at else None,
        "reason": _state.reason,
        "failures": _state.consecutive_failures,
    }


def reset():
    """手动重置熔断"""
    _state.closed = True
    _state.consecutive_failures = 0
    _state.reason = ""
    _state.opened_at = None
    logger.info("熔断已手动重置")
