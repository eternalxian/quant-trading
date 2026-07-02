"""执行层 — 订单管理 + 三段式 Broker 抽象"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("quant.execution")


@dataclass
class Order:
    code: str
    name: str
    action: str             # buy / sell
    amount: float
    target_shares: float = 0.0
    status: str = "pending"  # pending → submitted → filled / rejected
    filled_amount: float = 0.0
    filled_nav: float = 0.0
    slippage: float = 0.0
    latency_ms: float = 0.0
    risk_decision: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    executed_at: str = ""
    note: str = ""


# ═══════════════════ 抽象基类 ═══════════════════

class BaseBroker(ABC):
    """Broker 抽象基类，定义统一接口"""

    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        """提交订单，返回更新后的 Order"""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...

    @abstractmethod
    def get_positions(self) -> dict:
        ...

    @abstractmethod
    def get_cash(self) -> float:
        ...


# ═══════════════════ 模拟盘 ═══════════════════

class PaperBroker(BaseBroker):
    """模拟交易 — 无真实资金，用于回测和策略验证"""

    def __init__(self, initial_cash: float = 100000.0, initial_positions: dict = None):
        self.cash = initial_cash
        self.positions: dict[str, dict] = initial_positions or {}
        self.orders: list[Order] = []

    def sync_from_portfolio(self, portfolio: dict):
        """从真实持仓同步到模拟账户"""
        for f in portfolio.get("基金", []):
            if f.get("市值", 0) > 0:
                self.positions[f["code"]] = {
                    "shares": f.get("市值", 0),
                    "avg_cost": f.get("成本", 0) / max(f.get("市值", 0), 1),
                    "total_cost": f.get("成本", 0),
                }
        self.cash = portfolio.get("余额宝", self.cash)
        logger.info(f"模拟账户同步: {len(self.positions)} 只基金, 现金 {self.cash:.0f}")

    def submit_order(self, order: Order) -> Order:
        order.status = "submitted"

        # 模拟成交
        if order.action == "buy":
            cost = order.amount
            if cost > self.cash:
                order.status = "rejected"
                order.note = "余额不足"
                logger.warning(f"模拟拒绝 {order.code}: {order.note}")
                return order

            self.cash -= cost
            if order.code not in self.positions:
                self.positions[order.code] = {"shares": 0, "avg_cost": 0, "total_cost": 0}
            pos = self.positions[order.code]
            pos["total_cost"] += cost
            # 假设按净值 1.0 成交
            shares = cost  # 模拟简化
            pos["shares"] += shares
            order.filled_amount = cost
            order.filled_nav = 1.0

        elif order.action == "sell":
            pos = self.positions.get(order.code)
            if not pos or pos["shares"] <= 0:
                order.status = "rejected"
                order.note = "无持仓可卖"
                return order

            sell_value = order.amount
            self.cash += sell_value
            ratio = sell_value / (pos["shares"] * pos.get("avg_cost", 1) or 1)
            pos["shares"] -= pos["shares"] * ratio
            pos["total_cost"] -= pos["total_cost"] * ratio
            order.filled_amount = sell_value
            order.filled_nav = 1.0

        order.status = "filled"
        order.executed_at = datetime.now().isoformat()
        self.orders.append(order)
        logger.info(f"模拟成交 {order.action} {order.code} {order.amount:.0f}")
        return order

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_positions(self) -> dict:
        return self.positions

    def get_cash(self) -> float:
        return self.cash


# ═══════════════════ 订单管理器 ═══════════════════

class OrderManager:
    """统一订单管理，不关心底层 Broker 类型"""

    def __init__(self, broker: BaseBroker):
        self.broker = broker
        self.history: list[Order] = []

    def place_order(self, order: Order) -> Order:
        """下单入口，记录完整日志"""
        start = datetime.now()
        logger.info(f"下单 {order.action} {order.code} {order.name} {order.amount:.0f}元")

        result = self.broker.submit_order(order)
        result.latency_ms = (datetime.now() - start).total_seconds() * 1000
        self.history.append(result)

        # 写入执行日志
        _log_execution(result)

        return result

    def get_summary(self) -> dict:
        fills = [o for o in self.history if o.status == "filled"]
        return {
            "total_orders": len(self.history),
            "filled": len(fills),
            "rejected": sum(1 for o in self.history if o.status == "rejected"),
            "total_buy": sum(o.filled_amount for o in fills if o.action == "buy"),
            "total_sell": sum(o.filled_amount for o in fills if o.action == "sell"),
        }


def _log_execution(order: Order):
    """写入 execution_log 表"""
    try:
        import sqlite3, os
        DB = os.path.join(os.path.dirname(__file__), "..", "data", "quant.db")
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT, name TEXT, action TEXT, amount REAL,
                status TEXT, filled_amount REAL, filled_nav REAL,
                slippage REAL, latency_ms REAL, risk_decision TEXT,
                created_at TEXT, executed_at TEXT, note TEXT
            )"""
        )
        cur.execute(
            """INSERT INTO execution_log
               (code, name, action, amount, status, filled_amount, filled_nav,
                slippage, latency_ms, risk_decision, created_at, executed_at, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order.code, order.name, order.action, order.amount,
                order.status, order.filled_amount, order.filled_nav,
                order.slippage, order.latency_ms, order.risk_decision,
                order.created_at, order.executed_at, order.note,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"执行日志写入失败: {e}")
