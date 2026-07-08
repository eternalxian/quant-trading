"""
统一日志系统 — 三通道

  logs/quant.log       — 主日志 (INFO+, 保留30天, 每日轮转)
  logs/error.log       — 错误日志 (WARNING+, 保留90天)
  logs/signals.log     — 信号审计追踪 (INFO, 保留365天)
"""
import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 格式
DETAIL_FMT = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s",
    datefmt="%m-%d %H:%M:%S",
)
SIMPLE_FMT = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)


def _make_handler(filename: str, level: int, fmt, backup: int = 30, when: str = "D") -> TimedRotatingFileHandler:
    h = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, filename), when=when, backupCount=backup, encoding="utf-8"
    )
    h.setLevel(level)
    h.setFormatter(fmt)
    return h


# ── Handler 注册 ──

_root = logging.getLogger()
_root.setLevel(logging.DEBUG)

# 主日志
_main = _make_handler("quant.log", logging.INFO, DETAIL_FMT, backup=30)
_root.addHandler(_main)

# 错误日志
_error = _make_handler("error.log", logging.WARNING, DETAIL_FMT, backup=90)
_root.addHandler(_error)

# 信号审计日志（独立 logger）
_signal_logger = logging.getLogger("quant.signals")
_signal_logger.propagate = False
_signal_h = _make_handler("signals.log", logging.INFO, SIMPLE_FMT, backup=365)
_signal_logger.addHandler(_signal_h)

# 控制台（仅开发环境输出到 stderr）
import sys
_console = logging.StreamHandler(sys.stderr)
_console.setLevel(logging.WARNING)
_console.setFormatter(SIMPLE_FMT)
_root.addHandler(_console)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def signal_log(code: str, strategy: str, signal: str, score: float, reason: str = ""):
    """记录信号审计"""
    _signal_logger.info(
        "%s | %-20s | %-4s | %+8.4f | %s",
        code, strategy, signal, score, reason,
    )


# 初始化时记录一条
logging.getLogger("quant").info("日志系统启动")
