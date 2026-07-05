"""
终端实时行情看板 — 轮询 AKShare 快照，持续刷新

用法:
    python -m stock_trading.monitor           # 监控 watchlist 全部
    python -m stock_trading.monitor 603986    # 只监控指定股票
"""

import sys
import os
import time
from datetime import datetime

# 终端颜色（跨平台）
try:
    import colorama
    colorama.init()
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
except ImportError:
    RED = GREEN = YELLOW = CYAN = RESET = BOLD = DIM = ""


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def color_pct(pct: float) -> str:
    """涨跌幅着色"""
    if pct > 0:
        return f"{RED}+{pct:.2f}%{RESET}"
    elif pct < 0:
        return f"{GREEN}{pct:.2f}%{RESET}"
    else:
        return f"{DIM} 0.00%{RESET}"


def color_price_change(change_pct: float) -> str:
    """涨跌颜色标记"""
    if change_pct > 0:
        return RED
    elif change_pct < 0:
        return GREEN
    return ""


def run_monitor(codes: list[str] = None, interval: float = 3.0):
    """启动实时监控

    Args:
        codes: 要监控的股票代码列表，None=使用 STOCK_WATCHLIST
        interval: 刷新间隔（秒），最小1秒
    """
    from stock import STOCK_WATCHLIST, get_stock_spot
    from stock_db import load_db

    interval = max(interval, 1.0)

    if codes is None:
        if not STOCK_WATCHLIST:
            print("\n个股观察池为空。先运行: python main.py g seed\n")
            return
        codes = list(STOCK_WATCHLIST.keys())

    watchlist = {c: STOCK_WATCHLIST.get(c, c) for c in codes}

    # 尝试从 stock_db 补全名称
    db = load_db()
    for code in list(watchlist.keys()):
        if code in db and watchlist[code] == code:
            watchlist[code] = db[code].get("name", code)

    print(f"\n{BOLD}[LIVE] 实时行情监控{CYAN}  {len(watchlist)} 只股票  "
          f"{DIM}{interval:.0f}s刷新  Ctrl+C 退出{RESET}\n")

    error_count = 0

    try:
        while True:
            clear_screen()

            now = datetime.now().strftime("%H:%M:%S")
            is_trading = _is_trading_time()

            status = f"{RED}* 交易中{RESET}" if is_trading else f"{DIM}o 休市{RESET}"

            print(f"{BOLD}{'='*75}{RESET}")
            print(f"  {BOLD}[STOCK] 实时行情{RESET}  {DIM}{now}{RESET}  {status}  "
                  f"{DIM}{len(watchlist)}只{RESET}")
            print(f"{BOLD}{'='*75}{RESET}")
            print(f"  {'代码':>8s}  {'名称':<10s}  {'现价':>10s}  "
                  f"{'涨跌幅':>10s}  {'成交额':>12s}  {'换手率':>8s}")
            print(f"  {'-'*65}")

            try:
                spot = get_stock_spot(watchlist)
                error_count = 0
            except Exception as e:
                error_count += 1
                if error_count <= 2:
                    print(f"  {YELLOW}! 数据获取失败，重试中 ({error_count}/3)...{RESET}")
                else:
                    print(f"  {RED}X 连续失败，请检查网络{RESET}")
                time.sleep(interval)
                continue

            if spot.empty:
                print(f"  {DIM}暂无数据{RESET}")
                time.sleep(interval)
                continue

            # 按涨跌幅排序（从高到低）
            spot = spot.sort_values("change_pct", ascending=False)

            for _, row in spot.iterrows():
                code = row.get("code", "")
                name = str(row.get("name", watchlist.get(code, code)))[:10]
                price = row.get("price", 0)
                change_pct = row.get("change_pct", 0) or 0
                amount = row.get("amount", 0) or 0
                turnover = row.get("turnover", None)

                # 颜色标记
                c = color_price_change(change_pct)

                # 成交额格式化
                if amount >= 1e8:
                    amt_str = f"{amount/1e8:.2f}亿"
                elif amount >= 1e4:
                    amt_str = f"{amount/1e4:.0f}万"
                else:
                    amt_str = f"{amount:.0f}"

                # 换手率
                if turnover is not None and turnover > 0:
                    to_str = f"{turnover:.2f}%"
                else:
                    to_str = "-"

                print(f"  {code:>8s}  {c}{name:<10s}{RESET}  "
                      f"{c}{price:>10.2f}{RESET}  "
                      f"{color_pct(change_pct)}  "
                      f"{amt_str:>12s}  {to_str:>8s}")

            print(f"{'='*75}")
            print(f"  {DIM}{RED}Up{RESET}{DIM}涨 {GREEN}Dn{RESET}{DIM}跌  |  "
                  f"数据来源: AKShare (延迟约15秒)  |  "
                  f"刷新间隔 {interval:.0f}s{RESET}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n{BOLD}Bye 监控结束{RESET}\n")
    except Exception as e:
        print(f"\n{RED}错误: {e}{RESET}\n")


def _is_trading_time() -> bool:
    """简化交易时间判断"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    from datetime import time as ttime
    return (ttime(9, 30) <= t <= ttime(11, 30)) or \
           (ttime(13, 0) <= t <= ttime(15, 0))


# ═══════════════════ 命令行入口 ═══════════════════

if __name__ == "__main__":
    codes = sys.argv[1:] if len(sys.argv) > 1 else None
    run_monitor(codes=codes)
