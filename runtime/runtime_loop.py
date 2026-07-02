"""AI Quant Runtime — 主循环

每天自动：
行情 → 信号 → 风控 → 建议 → 模拟执行 → 健康度 → 状态检查

启动: python -m runtime.runtime_loop
"""

import logging
import time
from datetime import datetime

from .market_clock import is_trading_day, is_market_open, market_phase, seconds_until_open
from .state_checker import check_all
from .recovery import recovery, retry

logger = logging.getLogger("quant.runtime.loop")

# ── 配置 ──
SCAN_INTERVAL = 60       # 交易时段扫描间隔（秒）
IDLE_INTERVAL = 300      # 非交易时段休眠间隔（秒）
HEALTH_CHECK_INTERVAL = 900  # 状态检查间隔（15分钟）


@retry(max_attempts=3, delay_seconds=5)
def run_data_update():
    """更新数据"""
    from data import get_all_funds_nav, get_all_etfs
    logger.info("更新数据...")
    get_all_funds_nav(days=5)
    get_all_etfs(days=120)
    recovery.record_success("data_update")


@retry(max_attempts=2, delay_seconds=3)
def run_signal_cycle() -> dict:
    """信号→建议→风控 完整周期"""
    from signals import generate_signals
    from portfolio import calc_portfolio
    from strategy.engine import signals_to_advices, advices_with_risk

    sigs = generate_signals(days=60)
    pf = calc_portfolio()
    cash = pf.get("余额宝", 0)

    advices = signals_to_advices(sigs.get("信号", []), pf, pf.get("总资产", 0))
    advices = advices_with_risk(advices, pf, cash)

    approved = [a for a in advices if a.risk_ok]
    logger.info(f"信号周期完成: {len(advices)} 建议, {len(approved)} 通过风控")

    recovery.record_success("signal_cycle")
    return {
        "time": sigs.get("时间", ""),
        "suggestion": sigs.get("综合建议", ""),
        "advices": approved,
        "all_advices": advices,
    }


def run_simulation(advices: list) -> list:
    """模拟执行通过风控的建议"""
    from execution import PaperBroker, OrderManager, Order
    from portfolio import calc_portfolio

    pf = calc_portfolio()
    broker = PaperBroker()
    broker.sync_from_portfolio(pf)
    mgr = OrderManager(broker)

    results = []
    for a in advices:
        order = Order(
            code=a.code, name=a.name, action=a.action, amount=a.amount,
            risk_decision="pass" if a.risk_ok else a.risk_detail,
        )
        result = mgr.place_order(order)
        results.append(result)

    filled = [r for r in results if r.status == "filled"]
    logger.info(f"模拟执行: {len(filled)}/{len(results)} 成交")
    recovery.record_success("simulation")
    return results


def run_health_update():
    """更新策略健康度"""
    from strategy.health import check_health, log_health

    # 从 execution_log 拉最近收益
    import sqlite3, os
    DB = os.path.join(os.path.dirname(__file__), "..", "data", "quant.db")
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT amount, action FROM execution_log ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        conn.close()

        returns = []
        for amount, action in rows:
            returns.append(amount if action == "sell" else -amount)
        returns = [r / 10000 for r in returns]  # normalize

        health = check_health("ETF-Rotation", returns)
        log_health(health)
        logger.info(f"健康度: {health.status} sharpe={health.rolling_sharpe:.2f}")
        recovery.record_success("health_update")
    except Exception as e:
        logger.warning(f"健康度更新跳过: {e}")


def tick():
    """单次运行时 tick"""
    phase = market_phase()
    logger.info(f"Tick: {phase}")

    # 1. 状态检查（每15分钟）
    now = datetime.now()
    if now.minute % 15 == 0 or not hasattr(tick, "_last_health"):
        health = check_all()
        tick._last_health = now  # type: ignore
        if not health.healthy:
            logger.error(f"状态检查异常: {health.errors}")
            return

    # 2. 交易时段：完整循环
    if is_market_open():
        run_data_update()
        cycle = run_signal_cycle()
        if cycle["advices"]:
            run_simulation(cycle["advices"])
        run_health_update()
    else:
        # 非交易时段：只做数据更新
        if phase in ("盘前", "收盘后(净值待发布)"):
            run_data_update()
            run_signal_cycle()


def run_forever():
    """主循环 — 永不停止"""
    logger.info("=" * 50)
    logger.info("  AI Quant Runtime 启动")
    logger.info("=" * 50)

    # 启动时先做一次状态检查
    health = check_all()
    if not health.healthy:
        logger.error(f"启动状态检查失败: {health.errors}")
    if health.warnings:
        logger.warning(f"启动警告: {health.warnings}")

    while True:
        try:
            tick()
        except Exception as e:
            logger.error(f"Tick 异常: {e}", exc_info=True)
            recovery.record_failure("runtime_loop", str(e))

        # 动态间隔
        if is_market_open():
            interval = SCAN_INTERVAL
        else:
            interval = IDLE_INTERVAL

        logger.debug(f"休眠 {interval}s")
        time.sleep(interval)


# ═══════════════════ CLI 入口 ═══════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info(f"市场状态: {market_phase()}")
    logger.info(f"距离开盘: {seconds_until_open():.0f}s")

    try:
        run_forever()
    except KeyboardInterrupt:
        logger.info("Runtime 正常退出")
