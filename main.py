"""AI Quant Terminal v3.0 — CLI"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import FUNDS
from portfolio import calc_portfolio, print_portfolio
from market import scan_market, print_market
from ai import ask_model, DEFAULT_MODEL
from risk import get_all_risk_metrics, print_risk_metrics
from alipay import update_alipay_holding, get_freshness_report

def cmd_portfolio():
    s = calc_portfolio(); print_portfolio(s)

def cmd_market():
    r = scan_market(); print_market(r)

def cmd_risk():
    m = get_all_risk_metrics(days=250); print_risk_metrics(m)

def cmd_ai():
    s = calc_portfolio()
    fund_list = ", ".join(f"{f['name']} ¥{f.get('市值',0):.0f}" for f in s.get("基金",[]) if f.get("市值",0)>0)
    prompt = f"你是基金投资顾问。总资产 ¥{s.get('总资产',0):.0f}。持仓: {fund_list}。请用3-5句简要分析。"
    print("\nAI 分析:\n" + ask_model(prompt, model=DEFAULT_MODEL))

def cmd_add_fund():
    code = input("基金代码: ").strip()
    shares = float(input("持有份额: "))
    value = float(input("当前市值: "))
    cost = float(input("成本 (市值-持有收益): ") or (value - float(input("持有收益: ") or 0)))
    update_alipay_holding(code, shares, value, cost, note="手动录入")
    print(f"已录入 {code}")

def cmd_freshness():
    r = get_freshness_report()
    print("\n数据新鲜度:")
    for code, f in r["funds"].items():
        flag = "⚠️ 过期" if f["stale"] else "✅"
        print(f"  {flag} {code}: {f['days_ago']}天前 ({f['last_sync']})")

def print_menu():
    print(f"\n{'='*40}")
    print(f"  AI Quant Terminal v3.0")
    print(f"  基金: {len(FUNDS)} 只")
    print(f"{'='*40}")
    print(f"  p) 持仓  m) 市场  r) 风险")
    print(f"  a) AI分析  f) 数据新鲜度")
    print(f"  +) 录入基金  q) 退出")

if __name__ == "__main__":
    while True:
        print_menu()
        c = input("> ").strip().lower()
        if c == "q": break
        elif c == "p": cmd_portfolio()
        elif c == "m": cmd_market()
        elif c == "r": cmd_risk()
        elif c == "a": cmd_ai()
        elif c == "f": cmd_freshness()
        elif c == "+": cmd_add_fund()
