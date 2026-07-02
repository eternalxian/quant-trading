import sys,os,time; sys.path.insert(0,os.path.dirname(__file__))
from datetime import datetime
from stock import get_stock_spot
print("永泰能源 止损1.65 止盈1.89\n")
try:
    while True:
        n=datetime.now().strftime("%H:%M:%S")
        try:
            r=get_stock_spot({"600157":"永泰能源"}).iloc[0]
            p=r["price"]; pct=r["change_pct"] or 0
            pl=(p-1.78)*300
            if p<=1.65:
                print(f"[{n}] !!! 止损触发 {p:.2f} !!! 亏{pl:.0f}")
            elif p>=1.89:
                print(f"[{n}] >>> 止盈触发 {p:.2f} >>> 赚{pl:.0f}")
            elif p<=1.70:
                print(f"[{n}] {p:.2f} 接近止损 (距1.65还差{p-1.65:.2f})")
            elif p>=1.85:
                print(f"[{n}] {p:.2f} 接近止盈 (距1.89还差{1.89-p:.2f})")
            else:
                print(f"[{n}] {p:.2f} {pct:+.2f}%")
        except: pass
        time.sleep(5)
except KeyboardInterrupt:
    print("\nBye")
