"""
AI Quant Terminal — FastAPI 后端（优化版）

启动: uvicorn server:app --host 0.0.0.0 --port 8000
"""

import sys, os, warnings, time, functools
sys.path.insert(0, os.path.dirname(__file__))

# 静音 ML 库的琐碎警告
warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI(title="AI Quant Terminal API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ws_clients: list[WebSocket] = []

# ── 简易 TTL 缓存 ──
_cache: dict[str, tuple[float, object]] = {}

def ttl_cache(seconds: int = 30):
    """内存缓存装饰器，TTL 秒内复用结果"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            key = f"{fn.__name__}:{a}:{kw}"
            now = time.time()
            if key in _cache:
                ts, val = _cache[key]
                if now - ts < seconds:
                    return val
            val = fn(*a, **kw)
            _cache[key] = (now, val)
            return val
        return wrapper
    return deco


def _json_safe(obj):
    import numpy as np
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, np.floating): return float(obj) if not np.isnan(obj) and not np.isinf(obj) else None
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, dict): return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_json_safe(v) for v in obj]
    return obj


# ═══════════════════ 快速端点（<1s）═══════════════

@app.get("/api/portfolio")
@ttl_cache(30)
def get_portfolio():
    from portfolio import calc_portfolio
    from config import FUNDS
    s = calc_portfolio()
    from db import get_pending_buys
    pending = get_pending_buys()
    pending_total = sum(v.get("amount", 0) if isinstance(v, dict) else v for v in pending.values())
    return _json_safe({
        "total": s.get("总资产", 0), "fund_value": s.get("基金市值", 0),
        "cash": s.get("余额宝", 0), "total_cost": s.get("总成本", 0),
        "total_pl": s.get("总盈亏", 0), "total_pl_pct": s.get("总盈亏率", 0),
        "daily_change": str(s.get("日涨跌", "")), "date": s.get("日期", ""),
        "pending_total": pending_total,
        "pending": [{"code": k, "amount": v.get("amount", 0) if isinstance(v, dict) else v,
                      "date": v.get("date", "") if isinstance(v, dict) else "",
                      "name": FUNDS.get(k, {}).get("name", k)}
                     for k, v in pending.items()],
        "funds": [{"code": f["code"], "name": f["name"], "value": f.get("市值", 0),
                    "cost": f.get("成本", 0), "pl": f.get("盈亏", 0),
                    "pl_pct": f.get("盈亏率", 0), "change": f.get("涨跌", ""),
                    "weight": f.get("占比", 0)} for f in s.get("基金", [])],
    })


@app.get("/api/market")
@ttl_cache(15)
def get_market():
    from market import scan_market
    r = scan_market()
    return _json_safe({"time": r.get("时间", ""), "indices": r.get("指数", []), "etfs": r.get("ETF", [])})


@app.get("/api/signals")
@ttl_cache(30)
def get_signals():
    from signals import generate_signals
    sigs = generate_signals(days=60)
    return _json_safe({
        "time": sigs.get("时间", ""),
        "signals": [{"code": s.get("code",""), "name": s.get("name",""),
                      "score": s.get("评分",0), "momentum": s.get("动量",""),
                      "action": s.get("操作",""), "reason": s.get("理由","")}
                    for s in sigs.get("信号", [])],
        "suggestion": sigs.get("综合建议", ""),
    })


@app.get("/api/stock/spot")
@ttl_cache(10)
def get_stock_spot():
    from stock import get_stock_spot, STOCK_WATCHLIST
    spot = get_stock_spot(STOCK_WATCHLIST)
    return _json_safe({"stocks": spot.to_dict(orient="records") if not spot.empty else []})


@app.get("/api/stock/{code}/daily")
def get_stock_daily_api(code: str, days: int = 120):
    # 先尝试 akshare，失败则用 Sina
    try:
        from stock import get_stock_daily
        df = get_stock_daily(code, days=days)
        if df is not None and not df.empty:
            records = df.to_dict(orient="records")
            for r in records:
                if "date" in r and hasattr(r["date"], "isoformat"):
                    r["date"] = r["date"].isoformat()
            return _json_safe({"data": records})
    except Exception:
        pass

    # 备用：Sina 日线 API
    import urllib.request, re, json
    try:
        prefix = "sh" if code.startswith(("5","6","9")) else "sz"
        # Sina 日线接口
        url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}{code}&scale=240&ma=no&datalen={days}"
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        records = []
        for item in data:
            records.append({
                "date": item.get("day", ""),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": float(item.get("volume", 0)),
            })
        return _json_safe({"data": records})
    except Exception:
        return {"data": []}


@app.get("/api/risk")
@ttl_cache(60)
def get_risk():
    from risk import get_all_risk_metrics
    return _json_safe(get_all_risk_metrics(days=250))


@app.get("/api/holdings")
@ttl_cache(60)
def get_holdings_penetration():
    from holdings import get_all_holdings, aggregate_by_stock
    from portfolio import calc_portfolio
    pf = calc_portfolio()
    fund_values = {f["code"]: f["市值"] for f in pf["基金"] if f["市值"] > 0}
    agg = aggregate_by_stock(get_all_holdings(fund_values))
    return _json_safe({"stocks": agg.to_dict(orient="records") if not agg.empty else []})


# ═══════════════════ 中速端点（含缓存）═══════════════

@app.get("/api/stock/signals")
@ttl_cache(120)
def get_stock_signals(fast: bool = True):
    """个股全策略信号。fast=True 跳过 ML 模型，<2s 返回。"""
    from stock import get_all_stocks_daily, generate_stock_signals, rank_stocks, STOCK_WATCHLIST
    stocks_data = get_all_stocks_daily(STOCK_WATCHLIST, days=120)
    if not stocks_data:
        return {"rank": [], "details": {}}

    # 快模式：只用经典技术指标，跳过慢速 ML 模型
    if fast:
        from signals import list_calculators
        all_names = list_calculators()
        skip_ml = {"CatBoost", "LightGBM", "LSTM", "TFT"}
        names = [n for n in all_names if n not in skip_ml]
    else:
        names = None

    signals = generate_stock_signals(stocks_data, strategy_names=names)
    rank = rank_stocks(signals)

    details = {}
    for sname, codes in signals.items():
        if not isinstance(codes, dict) or "error" in codes:
            continue
        for code, sr in codes.items():
            if not hasattr(sr, "signal"): continue
            details.setdefault(code, []).append({
                "strategy": sname, "signal": sr.signal,
                "score": getattr(sr, "score", 0), "reason": getattr(sr, "reason", ""),
            })

    return _json_safe({
        "rank": rank.to_dict(orient="records") if not rank.empty else [],
        "details": details,
    })


# ═══════════════════ 慢速端点（按需调用）═══════════════

@app.get("/api/ai/analysis")
@ttl_cache(300)
def get_ai_analysis():
    """AI分析 — 当前跳过aksahre（避免py_mini_racer崩溃），纯基于确认数据"""
    from portfolio import calc_portfolio
    pf = calc_portfolio()
    use_confirmed = _confirmed_daily.get("date") == datetime.now().strftime("%Y-%m-%d")
    total_assets = _confirmed_daily["total"] if use_confirmed and _confirmed_daily["total"] > 0 else pf.get("总资产", 0)
    today_pl = _confirmed_daily["pl"] if use_confirmed else 0
    today_pl_pct = _confirmed_daily["pl_pct"] if use_confirmed else 0

    # 本地 LLM 分析（纯确认数据，不碰 akshare）
    from ai import ask_model, DEFAULT_MODEL
    prompt = f"""你是基金投资顾问。基于已核对数据给持仓建议：

总资产 ¥{total_assets:.0f}，今日收益 {today_pl:+.2f}元（{today_pl_pct:+.2f}%）。
持仓 8 只基金，半导体为重仓（约 ¥9000）。

请用 3-5 句简要分析当前表现、风险点、建议。简洁有力。"""

    try:
        result = ask_model(prompt, model=DEFAULT_MODEL)
    except Exception:
        result = f"总资产 ¥{total_assets:.0f}，今日 {today_pl:+.2f}元。LLM离线，此为确认数据。"

    return {"analysis": result, "time": datetime.now().isoformat()}
    from market import scan_market
    from signals import generate_signals
    from ai import ask_model, DEFAULT_MODEL

    pf = calc_portfolio()
    market = {"指数": [], "ETF": [], "时间": ""}
    try:
        market = scan_market()
    except Exception:
        pass
    sigs = {"信号": [], "综合建议": ""}
    try:
        sigs = generate_signals(days=60)
    except Exception:
        pass
    signal_summary = sigs.get("综合建议", "")

    # 优先用确认数据，否则用系统数据
    use_confirmed = _confirmed_daily.get("date") == datetime.now().strftime("%Y-%m-%d")
    total_assets = _confirmed_daily["total"] if use_confirmed and _confirmed_daily["total"] > 0 else pf.get("总资产", 0)
    today_pl = _confirmed_daily["pl"] if use_confirmed else pf.get("总盈亏", 0)
    today_pl_pct = _confirmed_daily["pl_pct"] if use_confirmed else pf.get("总盈亏率", 0)

    # 构建持仓文本：有确认数据时跳过系统净值（避免假数据）
    fund_lines = []
    if use_confirmed:
        fund_lines.append(f"  （持仓明细已与支付宝核对，总市值¥{total_assets - _confirmed_daily.get('cash',0):.0f}）")
    else:
        for f in pf.get("基金", []):
            if f.get("市值", 0) > 0:
                fund_lines.append(
                    f"  {f['code']} {f['name']}: 成本¥{f.get('成本',0):.0f}, "
                    f"累计盈亏{f.get('盈亏',0):+.0f}, 占比{f.get('占比',0)}%"
                )

    index_text = "\n".join(
        f"  {i['name']}: {i.get('price','')} ({i.get('change','')})"
        for i in market.get("指数", [])
    )
    etf_text = "\n".join(
        f"  {e['name']}({e['code']}): {e.get('price','')} ({e.get('change_pct','')}%)"
        for e in market.get("ETF", [])
    )

    pending_text = ""
    if _confirmed_daily.get("date") == datetime.now().strftime("%Y-%m-%d"):
        from db import get_pending_buys
        pending = get_pending_buys()
        if pending:
            pending_total = sum(v.get("amount",0) if isinstance(v,dict) else v for v in pending.values())
            pending_text = f"\n待确认申购: ¥{pending_total:.0f}（不参与今日收益计算）"

    prompt = f"""你现在是一个专业的基金投资顾问。请基于以下真实数据，分析我的持仓状况并给出建议。

⚠️ 重要：以下数据已与支付宝核对，总资产¥{total_assets:.0f}，今日实际收益{today_pl:+.2f}元（{today_pl_pct:+.2f}%）。

持仓组合：
{chr(10).join(fund_lines)}

市场概况：
指数：
{index_text}

ETF行情：
{etf_text}
{pending_text}

请分析：
1. 今日组合整体表现，哪些基金贡献/拖累最多
2. 当前仓位风险和集中度问题
3. 明天（5/19）的操作建议：增持/减持/观望哪些方向
4. 英伟达5/20财报前的策略建议
5. 一句话总结

要求：简洁，每条1-2句话，基于实际数据。
"""
    if signal_summary:
        prompt += f"\n\n附：当前ETF轮动信号 — {signal_summary}"

    result = ask_model(prompt, model=DEFAULT_MODEL)
    return {"analysis": result, "time": datetime.now().isoformat()}


# ═══════════════════ WebSocket ═══════════════════

@app.websocket("/ws/realtime")
async def websocket_realtime(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                from stock import get_stock_spot, STOCK_WATCHLIST
                from market import scan_market
                from portfolio import calc_portfolio
                from risk_engine import status as risk_status

                spot = get_stock_spot(STOCK_WATCHLIST)
                market = scan_market()
                pf = calc_portfolio()

                # 只推送摘要，减少带宽
                payload = _json_safe({
                    "type": "update",
                    "time": datetime.now().isoformat(),
                    "portfolio": {
                        "total": pf.get("总资产", 0),
                        "cash": pf.get("余额宝", 0),
                        "pl": pf.get("总盈亏", 0),
                        "pl_pct": pf.get("总盈亏率", 0),
                    },
                    "stocks": spot.head(8).to_dict(orient="records") if not spot.empty else [],
                    "indices": market.get("指数", []),
                    "risk": risk_status(),
                })
                await ws.send_json(payload)
    except WebSocketDisconnect:
        ws_clients.remove(ws)
    except Exception:
        if ws in ws_clients: ws_clients.remove(ws)


@app.get("/api/strategy/advices")
@ttl_cache(60)
def get_trade_advices():
    """获取当日交易建议（已过风控）"""
    from signals import generate_signals
    from portfolio import calc_portfolio
    from strategy.engine import signals_to_advices, advices_with_risk

    sigs = generate_signals(days=60)
    pf = calc_portfolio()
    cash = pf.get("余额宝", 0)

    advices = signals_to_advices(sigs.get("信号", []), pf, pf.get("总资产", 0))
    advices = advices_with_risk(advices, pf, cash)

    return _json_safe({
        "time": sigs.get("时间", ""),
        "suggestion": sigs.get("综合建议", ""),
        "advices": [
            {
                "code": a.code, "name": a.name, "action": a.action,
                "amount": a.amount, "reason": a.reason,
                "confidence": a.confidence, "priority": a.priority,
                "risk_ok": a.risk_ok, "risk_detail": a.risk_detail,
            }
            for a in advices
        ],
    })


@app.get("/api/risk/status")
@ttl_cache(10)
def get_risk_status():
    """获取风控状态"""
    from risk_engine import status as risk_status, DEFAULTS
    return _json_safe({
        "circuit": risk_status(),
        "rules": DEFAULTS,
    })


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ═══════════════════ 每日收益估算 ═══════════════════

# 基金 → 跟踪 ETF 映射
FUND_ETF_MAP = {
    "014319": "512480",  # 德邦半导体 → 半导体ETF
    "007817": "515050",  # 国泰通信 → 通信ETF
    "011839": "515070",  # 天弘AI → 人工智能ETF
    "016185": "159611",  # 广发电力 → 电力ETF
    "005698": "513100",  # 华夏全球QDII → 纳指ETF
    "000834": "513100",  # 大成纳指 → 纳指ETF
    "017641": "513500",  # 摩根标普500 → 标普500ETF
    "270042": "513100",  # 广发纳指 → 纳指ETF
    "012920": "513100",  # 易方达全球 → 纳指ETF(近似)
}


@app.get("/api/estimate/daily")
@ttl_cache(60)
def get_daily_estimate(date: str = None):
    """基于ETF涨跌估算基金当日收益

    返回每只基金的估算收益 + 汇总
    date: YYYY-MM-DD，默认今天
    """
    from data import get_etf_daily
    from portfolio import calc_portfolio
    from config import FUNDS

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    pf = calc_portfolio()
    total_est = 0.0
    funds_est = []

    # 拉所有 ETF 日线或实时行情
    etf_changes = {}
    today_str = datetime.now().strftime("%Y-%m-%d")

    for etf_code in set(FUND_ETF_MAP.values()):
        if date == today_str:
            # 今天：用 Sina 实时行情（ETF 前缀：5开头→sh，1开头→sz）
            try:
                import urllib.request, re
                prefix = "sh" if etf_code.startswith("5") else "sz"
                url = f"https://hq.sinajs.cn/list={prefix}{etf_code}"
                headers = {"Referer": "https://finance.sina.com.cn"}
                req = urllib.request.Request(url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=5)
                raw = resp.read().decode("gbk")
                m = re.search(r'="(.+?)"', raw)
                if m:
                    fields = m.group(1).split(",")
                    if len(fields) >= 4:
                        price = float(fields[3]) if fields[3] else 0
                        prev_close = float(fields[2]) if fields[2] else 0
                        if prev_close:
                            etf_changes[etf_code] = round((price - prev_close) / prev_close * 100, 2)
                            continue
            except Exception:
                pass

        # 历史日期：用日线
        df = get_etf_daily(etf_code, days=5)
        if df is not None and not df.empty and len(df) >= 2:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            close = latest.get("close", 0)
            prev_close = prev.get("close", 0)
            chg = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0
            etf_changes[etf_code] = chg

    for f in pf.get("基金", []):
        code = f["code"]
        value = f.get("市值", 0)
        if value <= 0:
            continue

        etf_code = FUND_ETF_MAP.get(code)
        etf_chg = etf_changes.get(etf_code, 0) if etf_code else 0
        est_pl = round(value * etf_chg / 100, 2)
        total_est += est_pl

        funds_est.append({
            "code": code,
            "name": f["name"],
            "value": value,
            "etf_code": etf_code or "",
            "etf_change": etf_chg,
            "est_pl": est_pl,
        })

    return _json_safe({
        "date": date,
        "total_est": round(total_est, 2),
        "funds": sorted(funds_est, key=lambda x: x["est_pl"], reverse=True),
    })


@app.get("/api/daily/report")
@ttl_cache(120)
def get_daily_report():
    """获取每日复盘日报"""
    from daily_report import generate, format_text
    report = generate()
    return _json_safe({
        "date": report.date, "total_assets": report.total_assets,
        "fund_value": report.fund_value, "cash": report.cash,
        "today_pl": report.today_pl, "today_pl_pct": report.today_pl_pct,
        "estimated_pl": report.estimated_pl,
        "top_gainer": report.top_gainer, "top_gainer_pl": report.top_gainer_pl,
        "top_loser": report.top_loser, "top_loser_pl": report.top_loser_pl,
        "signal_count": report.signal_count, "buy_count": report.buy_count,
        "sell_count": report.sell_count, "signal_summary": report.signal_summary,
        "advices": report.advices, "circuit_status": report.circuit_status,
        "pending_total": report.pending_total, "pending_items": report.pending_items,
        "data_quality": report.data_quality, "data_warnings": report.data_warnings,
        "generated_at": report.generated_at,
        "text": format_text(report),  # 纯文本版
    })


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ── 今日真实收益（持久化到 SQLite）──

def _load_confirmed() -> dict:
    try:
        import sqlite3, os, json
        DB = os.path.join(os.path.dirname(__file__), "data", "quant.db")
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS confirmed_daily (
            date TEXT PRIMARY KEY, pl REAL, pl_pct REAL, total REAL, cash REAL
        )""")
        cur.execute("SELECT pl, pl_pct, total, cash FROM confirmed_daily ORDER BY date DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            return {"pl": row[0], "pl_pct": row[1], "total": row[2], "cash": row[3] or 0,
                    "date": datetime.now().strftime("%Y-%m-%d")}
    except Exception:
        pass
    return {"pl": 0, "pl_pct": 0, "total": 0, "cash": 0, "date": ""}

def _save_confirmed(d: dict):
    try:
        import sqlite3, os
        DB = os.path.join(os.path.dirname(__file__), "data", "quant.db")
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS confirmed_daily (
            date TEXT PRIMARY KEY, pl REAL, pl_pct REAL, total REAL, cash REAL
        )""")
        cur.execute(
            "INSERT OR REPLACE INTO confirmed_daily (date, pl, pl_pct, total, cash) VALUES (?,?,?,?,?)",
            (d.get("date", ""), d.get("pl", 0), d.get("pl_pct", 0),
             d.get("total", 0), d.get("cash", 0))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

_confirmed_daily: dict = _load_confirmed()

@app.post("/api/portfolio/confirm-daily")
def confirm_daily_pl(pl: float = 0, pl_pct: float = 0, total: float = 0):
    _confirmed_daily["pl"] = pl
    _confirmed_daily["pl_pct"] = pl_pct
    _confirmed_daily["total"] = total
    _confirmed_daily["date"] = datetime.now().strftime("%Y-%m-%d")
    _save_confirmed(_confirmed_daily)
    return {"status": "ok", "confirmed": _confirmed_daily}

@app.get("/api/portfolio/confirmed")
def get_confirmed_daily():
    funds = _load_confirmed_funds()
    return {**_confirmed_daily, "cash": _get_cash(), "funds": funds}


@app.post("/api/portfolio/confirm-funds")
async def confirm_funds(request: Request):
    """批量确认基金市值 JSON: {"funds": {"014319": 4331.75, ...}}"""
    try:
        body = await request.json()
        funds = body.get("funds", {})
        _save_confirmed_funds(funds)
        return {"status": "ok", "funds": funds}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/portfolio/confirm-text")
async def confirm_text(request: Request):
    """解析支付宝AI文本并存入

    格式: 基金代码 基金名称 金额 收益
    例: 014319 德邦半导体A 4331.75元 +104.65元
    """
    import re
    try:
        body = await request.json()
        text = body.get("text", "")
        funds = {}
        # 匹配: 代码(6位) 名称 金额(数字+元) 盈亏
        for line in text.strip().split("\n"):
            m = re.search(r"(\d{6}).*?([\d,]+\.?\d*)\s*元", line)
            if m:
                code = m.group(1)
                value = float(m.group(2).replace(",", ""))
                funds[code] = value
        if funds:
            _save_confirmed_funds(funds)
        return {"status": "ok", "funds": funds, "count": len(funds)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/portfolio/set-cash")
def set_cash_endpoint(amount: float = 0):
    from db import set_cash
    set_cash(amount)
    _confirmed_daily["cash"] = amount
    _save_confirmed(_confirmed_daily)
    return {"status": "ok", "cash": amount}


def _get_cash():
    try:
        from db import get_cash
        return get_cash()
    except:
        return 0


def _save_confirmed_funds(funds: dict):
    try:
        import sqlite3, os
        DB = os.path.join(os.path.dirname(__file__), "data", "quant.db")
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS confirmed_funds (
            date TEXT, code TEXT, value REAL, PRIMARY KEY (date, code)
        )""")
        today = datetime.now().strftime("%Y-%m-%d")
        for code, value in funds.items():
            cur.execute(
                "INSERT OR REPLACE INTO confirmed_funds (date, code, value) VALUES (?,?,?)",
                (today, code, float(value))
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _load_confirmed_funds() -> dict:
    try:
        import sqlite3, os
        DB = os.path.join(os.path.dirname(__file__), "data", "quant.db")
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT code, value FROM confirmed_funds ORDER BY date DESC LIMIT 20")
        funds = {}
        for row in cur.fetchall():
            if row[0] not in funds:
                funds[row[0]] = row[1]
        conn.close()
        return funds
    except Exception:
        return {}


@app.get("/api/agent/analyze")
@ttl_cache(300)
def get_agent_analysis():
    """三Agent综合分析：股票+宏观+情绪"""
    from agents import StockAgent, MacroAgent, SentimentAgent
    from market import scan_market
    from stock import STOCK_WATCHLIST, get_stock_spot, get_stock_daily

    market = scan_market()
    results = {}

    # 1. 宏观分析
    try:
        macro = MacroAgent()
        r = macro.analyze(
            indices=market.get("指数", []),
            etf_market=market.get("ETF", []),
        )
        results["macro"] = {
            "sentiment": r.sentiment, "confidence": r.confidence,
            "summary": r.summary, "detail": r.detail, "error": r.error,
        }
    except Exception as e:
        results["macro"] = {"error": str(e)}

    # 2. 情绪分析（无新闻源时跳过LLM）
    try:
        sentiment = SentimentAgent()
        r = sentiment.analyze(headlines="今日A股三大指数震荡，科创50领涨，半导体板块强势，纳指承压")
        results["sentiment"] = {
            "sentiment": r.sentiment, "confidence": r.confidence,
            "summary": r.summary, "detail": r.detail, "error": r.error,
        }
    except Exception as e:
        results["sentiment"] = {"error": str(e)}

    # 3. 股票分析（取watchlist前3只）
    try:
        stock_agent = StockAgent()
        stock_results = []
        spot = get_stock_spot(STOCK_WATCHLIST)
        for _, row in spot.head(3).iterrows():
            code = row.get("code", "")
            name = row.get("name", "")
            # 生成简单技术摘要
            df = get_stock_daily(code, days=60)
            tech = ""
            if df is not None and len(df) >= 5:
                close = df["close"]
                ma5 = close.rolling(5).mean().iloc[-1]
                ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
                chg = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
                tech = f"现价{close.iloc[-1]:.2f}, MA5={ma5:.2f}, MA20={ma20:.2f}, 5日涨跌{chg:+.1f}%"
            r = stock_agent.analyze(code=code, name=name, kline_summary=tech)
            stock_results.append({
                "code": code, "name": name,
                "sentiment": r.sentiment, "confidence": r.confidence,
                "summary": r.summary, "signals": r.signals,
            })
        results["stocks"] = stock_results
    except Exception as e:
        results["stocks"] = []

    return _json_safe(results)


@app.get("/api/strategy/optimize")
@ttl_cache(600)
def get_optimization():
    from strategy.optimizer import optimize_all, optimize_rotation_strategy
    from data import get_all_etfs
    etf = get_all_etfs(days=250)
    sig = optimize_all(etf, top_n=3)
    rot = optimize_rotation_strategy(etf)
    fmt = {}
    for n, items in sig.items():
        fmt[n] = [{"rank": r.rank, "score": r.score, "params": r.params,
                    "return": r.total_return, "status": r.status} for r in items]
    return _json_safe({"signals": fmt, "rotation": rot})


# ── 基金实时跟踪 ──

@app.get("/api/funds/realtime")
@ttl_cache(10)
def get_funds_realtime():
    from portfolio import calc_portfolio
    pf = calc_portfolio()
    FUND_ETF = {
        "014319": "512480", "011839": "515070", "016185": "159611",
        "005698": "513100", "000834": "513100", "017641": "513500",
        "270042": "513100", "012920": "513100",
    }
    import urllib.request, re
    etf_spot = {}
    for etf_code in set(FUND_ETF.values()):
        try:
            prefix = "sh" if etf_code.startswith("5") else "sz"
            url = f"https://hq.sinajs.cn/list={prefix}{etf_code}"
            req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
            resp = urllib.request.urlopen(req, timeout=5)
            raw = resp.read().decode("gbk")
            m = re.search(r'="(.+?)"', raw)
            if m:
                raw_data = m.group(1)
                if not raw_data.strip():
                    continue
                fld = raw_data.split(",")
                if len(fld) >= 4 and fld[2] and fld[3]:
                    try:
                        price = float(fld[3]); prev = float(fld[2])
                        # 价格=0 说明未开盘或无成交，跳过
                        if price <= 0 or prev <= 0:
                            continue
                        etf_spot[etf_code] = {"price": price, "change_pct": round((price - prev) / prev * 100, 2)}
                    except (ValueError, ZeroDivisionError):
                        continue
        except Exception:
            pass
    funds = []
    for f in pf.get("基金", []):
        code = f["code"]
        if f.get("市值", 0) <= 0: continue
        e = etf_spot.get(FUND_ETF.get(code, ""), {})
        funds.append({"code": code, "name": f["name"], "value": f.get("市值", 0),
                       "etf_code": FUND_ETF.get(code, ""), "etf_change": e.get("change_pct", 0)})
    return _json_safe({"funds": funds, "time": datetime.now().isoformat()})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False, log_level="warning")
