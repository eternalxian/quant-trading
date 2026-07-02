"""故障恢复 — 自动重试 + 状态恢复"""

import logging
import time
import traceback
from functools import wraps
from typing import Callable

logger = logging.getLogger("quant.runtime.recovery")


def retry(max_attempts: int = 3, delay_seconds: float = 5.0, backoff: float = 2.0):
    """重试装饰器，指数退避"""
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts:
                        wait = delay_seconds * (backoff ** (attempt - 1))
                        logger.warning(
                            f"{fn.__name__} 第 {attempt} 次失败: {e}，{wait:.0f}s 后重试"
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            f"{fn.__name__} 重试 {max_attempts} 次全部失败: {e}"
                        )
            raise last_error
        return wrapper
    return decorator


class RecoveryManager:
    """运行时恢复管理器"""

    def __init__(self):
        self.failure_counts: dict[str, int] = {}
        self.last_success: dict[str, float] = {}

    def record_success(self, module: str):
        self.failure_counts[module] = 0
        self.last_success[module] = time.time()
        from risk_engine.circuit_breaker import record_success
        record_success()

    def record_failure(self, module: str, error: str):
        self.failure_counts[module] = self.failure_counts.get(module, 0) + 1
        from risk_engine.circuit_breaker import record_failure
        record_failure(f"{module}: {error}")
        logger.warning(f"模块 {module} 故障计数: {self.failure_counts[module]}")

    def should_skip(self, module: str, max_failures: int = 5) -> bool:
        """连续失败过多时跳过该模块"""
        return self.failure_counts.get(module, 0) >= max_failures

    def health_report(self) -> dict:
        from risk_engine import status as risk_status
        return {
            "modules": {
                m: {"failures": c, "last_success": self.last_success.get(m)}
                for m, c in self.failure_counts.items()
            },
            "circuit": risk_status(),
        }


# 全局实例
recovery = RecoveryManager()
