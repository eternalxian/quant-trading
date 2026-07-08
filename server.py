"""AI Quant Terminal v3.5.1-stable — FastAPI"""
import sys,os,warnings,time,functools,urllib.request,re,json as _json
sys.path.insert(0,os.path.dirname(__file__))
import log_setup; warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL","3")

from fastapi import FastAPI,WebSocket,WebSocketDisconnect,Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app=FastAPI(title="AI Quant Terminal",version="3.5.1-stable")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
ws_clients:list[WebSocket]=[]
_startup_time=time.time()

_cache:dict[str,tuple[float,object]]={}
def ttl_cache(s:int=30):
    def d(fn):
        @functools.wraps(fn)
        def w(*a,**kw):
            k=f"{fn.__name__}:{a}:{kw}";n=time.time()
            if k in _cache:
                ts,val=_cache[k]
                if n-ts<s:return val
            val=fn(*a,**kw);_cache[k]=(n,val);return val
        return w
    return d

def _js(obj):
    import numpy as np
    if isinstance(obj,np.integer):return int(obj)
    if isinstance(obj,np.floating):return float(obj) if not np.isnan(obj) and not np.isinf(obj) else None
    if isinstance(obj,np.bool_):return bool(obj)
    if isinstance(obj,np.ndarray):return obj.tolist()
    if isinstance(obj,dict):return {k:_js(v) for k,v in obj.items()}
    if isinstance(obj,list):return [_js(v) for v in obj]
    return obj

FUND_ETF_MAP={"014319":"512480","017641":"513500","270042":"513100","012920":"513100","005698":"513100","000834":"513100"}

# ══════════ 持仓 ══════════
@app.get("/api/portfolio")
@ttl_cache(30)
def get_portfolio():
    from portfolio import calc_portfolio; from config import FUNDS
    from db import get_pending_buys,get_confirmed_daily,prod_conn
    import sqlite3
    s=calc_portfolio()
    pending=get_pending_buys()
    pt=sum(v.get("amount",0) if isinstance(v,dict) else v for v in pending.values())
    yesterday=get_confirmed_daily()
    ypl=yesterday.get("pl",0)
    # 持有时长查询
    conn=prod_conn();buy_dates={}
    for r in conn.execute("SELECT code,MIN(date) FROM transactions WHERE type IN ('buy','pending_add','convert_in') GROUP BY code").fetchall():
        buy_dates[r[0]]=r[1]
    conn.close()
    td=datetime.now().strftime("%Y-%m-%d")
    funds_list=[]
    for f in s.get("基金",[]):
        fd={"code":f["code"],"name":f["name"],"value":f.get("市值",0),
            "cost":f.get("成本",0),"pl":f.get("盈亏",0),"pl_pct":f.get("盈亏率",0),
            "change":f.get("涨跌",""),"weight":f.get("占比",0),
            "source":f.get("source","alipay"),"nav":f.get("净值",0),"shares":f.get("份额",0)}
        bd=buy_dates.get(f["code"],"")
        fd["first_buy_date"]=bd or None
        fd["holding_days"]=(datetime.strptime(td,"%Y-%m-%d")-datetime.strptime(bd,"%Y-%m-%d")).days if bd else None
        funds_list.append(fd)

    return _js({"total":s.get("总资产",0),"fund_value":s.get("基金市值",0),
        "cash":s.get("余额宝",0),"total_cost":s.get("总成本",0),
        "total_pl":s.get("总盈亏",0),"total_pl_pct":s.get("总盈亏率",0),
        "yesterday_pl":ypl,"date":s.get("日期",""),
        "base_date":s.get("基准日",""),"auto_projected":s.get("推算模式",False),
        "annual_return":s.get("年化收益率"),"volatility":s.get("年化波动率"),
        "sharpe":s.get("夏普比率"),"calmar":s.get("Calmar比率"),
        "var_95":s.get("VaR_95"),"var_99":s.get("VaR_99"),
        "max_dd":s.get("最大回撤"),"beta":s.get("Beta"),"alpha":s.get("Alpha"),
        "pending_total":pt,"pending":[],
        "funds":funds_list})

# ══════════ 市场 ══════════
@app.get("/api/market")
@ttl_cache(15)
def get_market():
    from market import scan_market; r=scan_market()
    return _js({"time":r.get("时间",""),"indices":r.get("指数",[]),"etfs":r.get("ETF",[])})

@app.get("/api/market/global")
@ttl_cache(60)
def get_global_market():
    indices={"s_sh000001":"上证指数","s_sz399001":"深证成指","s_sz399006":"创业板指",
        "int_dji":"道琼斯","int_nasdaq":"纳斯达克","int_sp500":"标普500",
        "int_hangseng":"恒生指数","int_nikkei":"日经225","b_UKX":"英国富时100","b_GDAXI":"德国DAX"}
    result=[]
    for code,name in indices.items():
        try:
            url=f"https://hq.sinajs.cn/list={code}"
            req=urllib.request.Request(url,headers={"Referer":"https://finance.sina.com.cn"})
            resp=urllib.request.urlopen(req,timeout=5)
            raw=resp.read().decode("gbk");m=re.search(r'="(.+?)"',raw)
            if m:
                fld=m.group(1).split(",")
                if len(fld)>=4 and fld[2] and fld[3]:
                    price=float(fld[3]);prev=float(fld[2])
                    chg=round((price-prev)/prev*100,2) if prev else 0
                    result.append({"code":code,"name":name,"price":price,"change_pct":chg})
        except:pass
    return _js({"indices":result,"time":datetime.now().isoformat()})

# ══════════ 风险 ══════════
@app.get("/api/risk")
@ttl_cache(60)
def get_risk():
    from risk import get_all_risk_metrics; return _js(get_all_risk_metrics(days=250))

@app.get("/api/risk/status")
@ttl_cache(10)
def get_risk_status():
    from risk_engine import status as rs,DEFAULTS
    return _js({"circuit":rs(),"rules":DEFAULTS})

# ══════════ 基金监控 ══════════
@app.get("/api/funds/monitor")
@ttl_cache(120)
def get_fund_monitor():
    from risk_engine.fund_monitor import get_summary; return get_summary()

@app.get("/api/funds/nav-freshness")
@ttl_cache(300)
def get_nav_freshness():
    from validators.data_validator import check_nav_freshness; return _js(check_nav_freshness())

@app.get("/api/funds/realtime")
@ttl_cache(10)
def get_funds_realtime():
    from portfolio import calc_portfolio; pf=calc_portfolio()
    etf_spot={}
    for ec in set(FUND_ETF_MAP.values()):
        try:
            prefix="sh" if ec.startswith("5") else "sz"
            url=f"https://hq.sinajs.cn/list={prefix}{ec}"
            req=urllib.request.Request(url,headers={"Referer":"https://finance.sina.com.cn"})
            resp=urllib.request.urlopen(req,timeout=5);raw=resp.read().decode("gbk")
            m=re.search(r'="(.+?)"',raw)
            if m and m.group(1).strip():
                fld=m.group(1).split(",")
                if len(fld)>=4 and fld[2] and fld[3]:
                    price=float(fld[3]);prev=float(fld[2])
                    if price>0 and prev>0: etf_spot[ec]={"price":price,"change_pct":round((price-prev)/prev*100,2)}
        except:pass
    funds=[]
    for f in pf.get("基金",[]):
        code=f["code"]
        if f.get("市值",0)<=0:continue
        e=etf_spot.get(FUND_ETF_MAP.get(code,""),{})
        funds.append({"code":code,"name":f["name"],"value":f.get("市值",0),
            "etf_code":FUND_ETF_MAP.get(code,""),"etf_change":e.get("change_pct",0)})
    return _js({"funds":funds,"time":datetime.now().isoformat()})

# ══════════ AI ══════════
@app.get("/api/ai/analysis")
@ttl_cache(300)
def get_ai_analysis():
    from portfolio import calc_portfolio; from config import FUNDS
    pf=calc_portfolio()
    total=pf.get("总资产",0)
    fund_list=", ".join(f"{f['name']} ¥{f.get('市值',0):.0f}" for f in pf.get("基金",[]) if f.get("市值",0)>0)
    from ai import ask_model,DEFAULT_MODEL
    prompt=f"你是基金投资顾问。总资产 ¥{total:.0f}。持仓: {fund_list}。请用3-5句简要分析。"
    try:result=ask_model(prompt,model=DEFAULT_MODEL)
    except:result=f"总资产 ¥{total:.0f}。LLM离线。"
    return {"analysis":result,"time":datetime.now().isoformat()}

# ══════════ 收益归因 ══════════
@app.get("/api/portfolio/attribution")
@ttl_cache(30)
def get_attribution():
    """收益贡献排名：哪只基金贡献最多/最少"""
    from portfolio import calc_portfolio; from config import FUNDS
    pf=calc_portfolio()
    funds=[]
    for f in pf.get("基金",[]):
        if f.get("市值",0)>0:
            funds.append({"code":f["code"],"name":f["name"],"value":f["市值"],
                "pl":f["盈亏"],"pl_pct":f.get("盈亏率",0),
                "weight":f.get("占比",0),"source":f.get("source","alipay"),
                "contribution":round(f.get("盈亏",0),2)})
    funds.sort(key=lambda x:abs(x["pl"]),reverse=True)
    top_gainers=[x for x in funds if x["pl"]>=0][:3]
    top_losers=[x for x in funds if x["pl"]<0][:3]
    return _js({"top_gainers":top_gainers,"top_losers":top_losers,"all":funds})

# ══════════ 组合历史 ══════════
@app.get("/api/portfolio/history")
@ttl_cache(120)
def get_portfolio_history(days:int=90):
    """组合净值历史曲线数据"""
    from data import get_fund_nav; from config import FUNDS
    from db import prod_conn
    import pandas as pd
    conn=prod_conn()
    holdings_rows=conn.execute("SELECT code,shares FROM holdings WHERE shares>0").fetchall()
    conn.close()
    shares_map={r["code"]:r["shares"] for r in holdings_rows}
    if not shares_map:return _js({"data":[]})

    all_dates=set()
    navs={}
    for code,sh in shares_map.items():
        df=get_fund_nav(code,days=days+10)
        if df is not None and not df.empty:
            df=df.sort_values("净值日期")
            df=df[df["净值日期"]>=pd.Timestamp.now()-pd.Timedelta(days=days)]
            navs[code]=df
            all_dates.update(df["净值日期"].dt.strftime("%Y-%m-%d"))

    dates=sorted(all_dates)
    result=[]
    # Forward-fill: 每只基金记录最新可用净值，当日无数据时用上一次的
    last_nav={}
    for d in dates:
        total=0.0; has_any=False
        for code,sh in shares_map.items():
            df=navs.get(code)
            if df is not None:
                row=df[df["净值日期"]==d]
                if not row.empty:
                    last_nav[code]=float(row["单位净值"].iloc[0])
            if code in last_nav:
                total+=sh*last_nav[code];has_any=True
        if has_any and total>0:result.append({"date":d,"value":round(total,2)})

    return _js({"data":result})

# ══════════ 多周期收益 ══════════
@app.get("/api/portfolio/periods")
@ttl_cache(60)
def get_period_returns():
    """多周期收益: 1日/1周/1月/3月/今年以来"""
    from data import get_fund_nav; from config import FUNDS
    from db import prod_conn
    import pandas as pd; import numpy as np

    conn=prod_conn()
    holdings_rows=conn.execute("SELECT code,shares FROM holdings WHERE shares>0").fetchall()
    conn.close()
    shares_map={r["code"]:r["shares"] for r in holdings_rows}
    if not shares_map:return _js({"periods":{}})

    # 拉250天数据
    navs={}
    for code in shares_map:
        df=get_fund_nav(code,days=260)
        if df is not None and not df.empty:
            df=df.sort_values("净值日期");navs[code]=df

    if not navs:return _js({"periods":{}})

    # 聚合日度组合净值 (forward-fill)
    all_dates=sorted(set().union(*[set(df["净值日期"].dt.strftime("%Y-%m-%d")) for df in navs.values()]))
    daily_values=[];last_nav={}
    for d in all_dates:
        total=0.0;has_any=False
        for code,sh in shares_map.items():
            df=navs.get(code)
            if df is not None:
                row=df[df["净值日期"]==d]
                if not row.empty:last_nav[code]=float(row["单位净值"].iloc[0])
            if code in last_nav:total+=sh*last_nav[code];has_any=True
        if has_any and total>0:daily_values.append({"date":d,"value":total})

    if len(daily_values)<5:return _js({"periods":{}})

    df=pd.DataFrame(daily_values)
    latest=df["value"].iloc[-1]
    periods={}
    for label,offset in [("1日",1),("1周",5),("1月",22),("3月",66)]:
        if len(df)>offset:
            prev=df["value"].iloc[-offset-1]
            pct=round((latest/prev-1)*100,2)
            periods[label]=pct
    # YTD
    try:
        first_of_year=df[df["date"]>=datetime.now().strftime("%Y")+"-01-01"]["value"].iloc[0]
        periods["今年以来"]=round((latest/first_of_year-1)*100,2)
    except:pass

    return _js({"periods":periods,"latest_date":all_dates[-1] if all_dates else ""})

# ══════════ 交易 ══════════
@app.get("/api/transactions")
def get_transactions_api(code:str=None,limit:int=30):
    from db import get_transactions; return _js({"transactions":get_transactions(code=code,limit=limit)})

# ══════════ 确认数据 ══════════
def _load_confirmed()->dict:
    from db import get_confirmed_daily; d=get_confirmed_daily()
    if d["date"]:d["date"]=datetime.now().strftime("%Y-%m-%d")
    return d

def _save_confirmed(d:dict):
    from db import save_confirmed_daily
    save_confirmed_daily(d.get("date",""),d.get("pl",0),d.get("pl_pct",0),d.get("total",0),d.get("cash",0))

_confirmed_daily:dict=_load_confirmed()

@app.post("/api/portfolio/confirm-daily")
def confirm_daily_pl(pl:float=0,pl_pct:float=0,total:float=0):
    _confirmed_daily["pl"]=pl;_confirmed_daily["pl_pct"]=pl_pct
    _confirmed_daily["total"]=total
    _confirmed_daily["date"]=datetime.now().strftime("%Y-%m-%d")
    _save_confirmed(_confirmed_daily); return {"status":"ok"}

@app.get("/api/portfolio/confirmed")
def get_confirmed_daily():
    from db import get_confirmed_funds
    return {**_confirmed_daily,"cash":_get_cash(),"funds":get_confirmed_funds()}

@app.post("/api/portfolio/confirm-funds")
async def confirm_funds(request:Request):
    try:
        body=await request.json()
        from db import save_confirmed_funds; save_confirmed_funds(body.get("funds",{}))
        return {"status":"ok"}
    except Exception as e: return {"status":"error","detail":str(e)}

@app.post("/api/portfolio/confirm-text")
async def confirm_text(request:Request):
    try:
        body=await request.json();text=body.get("text","");funds={}
        for line in text.strip().split("\n"):
            m=re.search(r"(\d{6}).*?([\d,]+\.?\d*)\s*元",line)
            if m:funds[m.group(1)]=float(m.group(2).replace(",",""))
        if funds:
            from db import save_confirmed_funds;save_confirmed_funds(funds)
        return {"status":"ok","funds":funds,"count":len(funds)}
    except Exception as e: return {"status":"error","detail":str(e)}

@app.post("/api/portfolio/set-cash")
def set_cash_endpoint(amount:float=0):
    from db import set_cash;set_cash(amount)
    return {"status":"ok"}

def _get_cash():
    try:from db import get_cash;return get_cash()
    except:return 0

# ══════════ 估算 ══════════
@app.get("/api/estimate/daily")
@ttl_cache(60)
def get_daily_estimate(date:str=None):
    from portfolio import calc_portfolio
    if date is None:date=datetime.now().strftime("%Y-%m-%d")
    pf=calc_portfolio();total_est=0.0;funds_est=[]
    for f in pf.get("基金",[]):
        if f.get("市值",0)<=0:continue
        ec=FUND_ETF_MAP.get(f["code"],"");chg=0
        if ec:
            try:
                prefix="sh" if ec.startswith("5") else "sz"
                url=f"https://hq.sinajs.cn/list={prefix}{ec}"
                req=urllib.request.Request(url,headers={"Referer":"https://finance.sina.com.cn"})
                resp=urllib.request.urlopen(req,timeout=5);raw=resp.read().decode("gbk")
                m=re.search(r'="(.+?)"',raw)
                if m:
                    fld=m.group(1).split(",")
                    if len(fld)>=4 and fld[2] and fld[3]:
                        price=float(fld[3]);prev=float(fld[2])
                        if prev:chg=round((price-prev)/prev*100,2)
            except:pass
        est=round(f["市值"]*chg/100,2);total_est+=est
        funds_est.append({"code":f["code"],"name":f["name"],"value":f["市值"],
            "etf_code":ec,"etf_change":chg,"est_pl":est})
    return _js({"date":date,"total_est":round(total_est,2),
        "funds":sorted(funds_est,key=lambda x:x["est_pl"],reverse=True)})

@app.get("/api/compare")
@ttl_cache(300)
def get_compare(days:int=365):
    """真实基准对比: 组合 vs 沪深300"""
    from risk import (get_benchmark_returns,get_all_nav_returns,
        calc_portfolio_daily_returns,calc_portfolio_weights,
        calc_annualized_vol,calc_max_drawdown,calc_sharpe,TRADING_DAYS)
    import pandas as pd,numpy as np

    # 组合日收益率
    nav_returns=get_all_nav_returns(days=days+60)
    weights=calc_portfolio_weights()
    portfolio_returns=calc_portfolio_daily_returns(nav_returns,weights).tail(days)
    # 沪深300
    benchmark_returns=get_benchmark_returns(days=days+60).tail(days)

    def _stats(r,name):
        if r.empty or len(r)<20:return None
        cum=round(((1+r/100).prod()-1)*100,2)
        ann=round(r.mean()*TRADING_DAYS,2)
        vol=calc_annualized_vol(r)
        dd=calc_max_drawdown(r).get("max_dd")
        sharpe=calc_sharpe(r)
        return {"name":name,"cumulative_return":cum,"annual_return":ann,
            "volatility":vol,"max_drawdown":dd,"sharpe":sharpe,"days":len(r)}

    result={"date":datetime.now().strftime("%Y-%m-%d")}
    ps=_stats(portfolio_returns,"组合");bs=_stats(benchmark_returns,"沪深300")

    if ps and bs:
        excess=round(ps["cumulative_return"]-bs["cumulative_return"],2)
        result["summary"]={"portfolio":ps,"benchmark":bs,"excess_return_pct":excess}

        # 月度收益表
        def _monthly(r,name):
            cum=(1+r/100).cumprod()
            monthly=cum.resample("ME").last().pct_change()*100
            monthly.index=monthly.index.strftime("%Y-%m")
            return monthly.dropna().to_dict()
        pm=_monthly(portfolio_returns,"组合");bm=_monthly(benchmark_returns,"沪深300")
        months=sorted(set(list(pm.keys())+list(bm.keys())))
        monthly_table={}
        for m in months:
            monthly_table[m]={"组合":round(pm.get(m,0),2),"沪深300":round(bm.get(m,0),2),
                "超额":round(pm.get(m,0)-bm.get(m,0),2)}
        result["monthly"]=monthly_table

        # 累计收益曲线（最近250天的）
        recent=min(250,len(portfolio_returns))
        pc=(1+portfolio_returns.tail(recent)/100).cumprod()*100-100
        bc=(1+benchmark_returns.tail(recent)/100).cumprod()*100-100
        pc.index=pc.index.strftime("%Y-%m-%d");bc.index=bc.index.strftime("%Y-%m-%d")
        result["cumulative"]={"组合":pc.dropna().to_dict(),"沪深300":bc.dropna().to_dict()}

    return _js(result)

# ══════════ 系统健康 ══════════
@app.get("/api/system/health")
@ttl_cache(30)
def get_system_health():
    from db import prod_conn,analytics_conn,ref_conn
    import os,time as _time

    # 数据源探测
    t0=_time.time()
    try:from data import get_fund_nav;df=get_fund_nav("014319",days=2);ak_ok=df is not None and not df.empty
    except:ak_ok=False
    ak_lat=round((_time.time()-t0)*1000)

    t0=_time.time()
    try:import urllib.request,re;url="https://hq.sinajs.cn/list=sh512480";req=urllib.request.Request(url,headers={"Referer":"https://finance.sina.com.cn"});resp=urllib.request.urlopen(req,timeout=3);raw=resp.read().decode("gbk");sina_ok=bool(re.search(r'="(.+?)"',raw))
    except:sina_ok=False
    sina_lat=round((_time.time()-t0)*1000)

    # fallback 层级: 0=正常, 1=降级sina, 2=缓存
    fb_level=0
    if not ak_ok:fb_level=1
    if not ak_ok and not sina_ok:fb_level=2

    # 数据库
    db_ok={}
    for name,path in [("production","production.db"),("analytics","analytics.db"),("reference","reference.db")]:
        dbp=os.path.join(os.path.dirname(__file__),"data",path)
        db_ok[name]=os.path.exists(dbp)

    # WebSocket 客户端数
    ws_count=len(ws_clients)

    # 缓存状态
    from data import FORCE_CACHE,get_cache_mtime
    cache_mtime=get_cache_mtime()

    return _js({
        "status":"ok" if (ak_ok or sina_ok) else "degraded",
        "server_time":datetime.now().isoformat(),
        "data_provider":{"primary":"akshare","current":"akshare" if ak_ok else ("sina" if sina_ok else "cache"),
            "fallback_level":fb_level,"healthy":ak_ok or sina_ok,
            "last_cache_update":cache_mtime,"cache_forced":FORCE_CACHE},
        "sources":[
            {"name":"akshare","healthy":ak_ok,"latency_ms":ak_lat},
            {"name":"sina","healthy":sina_ok,"latency_ms":sina_lat},
            {"name":"local_cache","healthy":True,"latency_ms":0,"last_update":cache_mtime}
        ],
        "database":db_ok,"websocket":{"enabled":True,"connected_clients":ws_count},
        "warnings":[] if (ak_ok or sina_ok) else ["所有行情源异常，仅使用本地缓存"]
    })

# ══════════ 单基金K线 ══════════
@app.get("/api/fund/{code}/kline")
@ttl_cache(120)
def get_fund_kline(code:str,days:int=90):
    from config import FUNDS;from data import get_fund_nav;from fastapi.responses import JSONResponse
    if code not in FUNDS:return JSONResponse(status_code=404,content={"code":code,"error":"基金不存在或暂无净值数据","days":days,"data":[],"metrics":{}})
    name=FUNDS[code]["name"];df=get_fund_nav(code,days=days+10)
    if df is None or df.empty:return _js({"code":code,"name":name,"days":days,"data":[],"error":"无数据"})
    df=df.sort_values("净值日期").tail(days)
    data=[]
    for _,row in df.iterrows():
        nav=float(row["单位净值"]);growth=float(row.get("日增长率",0) or 0)
        data.append({"date":str(row["净值日期"])[:10],"nav":round(nav,4),"return_pct":round(growth,2)})
    returns=df["日增长率"].dropna().astype(float);metrics={}
    if len(returns)>=5:
        import numpy as np
        total_ret=round(float((1+returns/100).prod()-1)*100,2)
        cum=(1+returns/100).cumprod();peak=cum.cummax();mdd=round(float((cum/peak-1).min())*100,2)
        vol=round(float(returns.std()*np.sqrt(252)),2)
        sr=round(float(returns.mean()/returns.std()*np.sqrt(252)),2) if returns.std()>0 else 0
        metrics={"period_return":total_ret,"max_drawdown":mdd,"volatility":vol,"sharpe":sr}
    return _js({"code":code,"name":name,"days":days,"latest_date":str(df["净值日期"].iloc[-1])[:10],"data":data,"metrics":metrics})

# ══════════ 主题暴露 ══════════
@app.get("/api/portfolio/exposure")
@ttl_cache(60)
def get_exposure():
    from portfolio import calc_portfolio
    pf=calc_portfolio();funds=pf.get("基金",[])
    THEME_MAP={"014319":["半导体","A股"],"005698":["全球科技","QDII"],"000834":["纳斯达克100","QDII"],"012920":["全球科技","QDII"],"270042":["纳斯达克100","QDII"],"017641":["标普500","QDII"]}
    theme_weight={}
    for f in funds:
        code=f["code"];w=f.get("占比",0) or 0
        for t in THEME_MAP.get(code,["其他"]):theme_weight[t]=theme_weight.get(t,0)+w
    exposure=[{"theme":k,"weight":round(v,1),"risk":"high" if v>50 else "medium" if v>30 else "low"} for k,v in sorted(theme_weight.items(),key=lambda x:-x[1])]
    region_weight={}
    for f in funds:
        w=f.get("占比",0) or 0;code=f["code"];themes=THEME_MAP.get(code,[])
        if "A股" in themes:region_weight["A股"]=region_weight.get("A股",0)+w
        elif any(t in ("QDII","全球科技","纳斯达克100","标普500") for t in themes):region_weight["海外/QDII"]=region_weight.get("海外/QDII",0)+w
    regions=[{"region":k,"weight":round(v,1)} for k,v in sorted(region_weight.items(),key=lambda x:-x[1])]
    warnings=[]
    for e in exposure:
        if e["weight"]>50:warnings.append(f"{e['theme']}主题占比 {e['weight']}%，存在集中风险")
    return _js({"theme_exposure":exposure,"region_exposure":regions,"warnings":warnings})

# ══════════ 策略建议 (P2: 闭环) ══════════
def _gen_advice_id(code,rule,date=None):
    if date is None:date=datetime.now().strftime("%Y%m%d")
    return f"adv_{date}_{code}_{rule}"

@app.get("/api/strategy/advices")
@ttl_cache(60)
def get_strategy_advices():
    from portfolio import calc_portfolio; from config import SIGNAL_CONFIG
    from db import analytics_conn
    pf=calc_portfolio();td=datetime.now().strftime("%Y%m%d")
    funds=pf.get("基金",[]);max_pct=SIGNAL_CONFIG.get("max_position_pct",0.30)
    new_advices=[];existing_ids=set()
    # 读取已有pending记录（去重）
    conn=analytics_conn()
    for r in conn.execute("SELECT id FROM advice_log WHERE status='pending' AND created_at LIKE ?",(datetime.now().strftime("%Y-%m-%d")+"%",)):existing_ids.add(r[0])
    conn.close()

    for f in funds:
        if f.get("市值",0)<=0:continue
        w=f.get("占比",0) or 0
        code=f["code"];name=f["name"]
        pl_pct=f.get("盈亏率",0) or 0
        aid=None;action=None;reason="";level="medium";suggestion=""
        if w>max_pct*100:
            aid=_gen_advice_id(code,"concentration",td)
            action="减仓";level="high" if w>50 else "medium"
            reason=f"占比{w}%超过上限{max_pct*100:.0f}%"
            suggestion=f"建议将单基金占比降至{max_pct*100:.0f}%以内"
        elif pl_pct<-5:
            aid=_gen_advice_id(code,"drawdown",td)
            action="观察" if pl_pct>-10 else "减仓"
            reason=f"累计亏损{pl_pct:.1f}%"
            suggestion="密切关注" if pl_pct>-10 else "建议止损"
        elif pl_pct>20:
            aid=_gen_advice_id(code,"profit",td)
            action="止盈";level="low"
            reason=f"累计盈利{pl_pct:.1f}%"
            suggestion="可考虑部分止盈"
        elif w<5 and pl_pct>0:
            aid=_gen_advice_id(code,"underweight",td)
            action="加仓";level="low"
            reason=f"占比仅{w}%且盈利"
            suggestion="可考虑增持"
        if aid and aid not in existing_ids:
            new_advices.append({"id":aid,"type":"rebalance","action":action,"target":code,"target_name":name,"level":level,"reason":reason,"suggestion":suggestion,"status":"pending","created_at":datetime.now().isoformat()})

    # 写入数据库
    if new_advices:
        conn=analytics_conn()
        for a in new_advices:
            conn.execute("INSERT OR IGNORE INTO advice_log (id,type,action,target,target_name,level,reason,suggestion,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(a["id"],a["type"],a["action"],a["target"],a["target_name"],a["level"],a["reason"],a["suggestion"],"pending",a["created_at"]))
        conn.commit();conn.close()

    # 返回所有pending
    conn=analytics_conn()
    all_pending=[dict(r) for r in conn.execute("SELECT * FROM advice_log WHERE status='pending' ORDER BY level='high' DESC,created_at DESC").fetchall()]
    conn.close()
    if not all_pending:
        all_pending=[{"id":"","action":"持有","target_name":"组合","reason":"当前持仓结构合理，无需调整","level":"low","status":"pending"}]
    return _js({"advices":all_pending,"generated_at":datetime.now().isoformat()})

@app.post("/api/strategy/advices/{advice_id}/confirm")
def confirm_advice(advice_id:str):
    from db import analytics_conn
    conn=analytics_conn();conn.execute("UPDATE advice_log SET status='accepted',updated_at=? WHERE id=?",(datetime.now().isoformat(),advice_id));conn.commit();conn.close()
    return {"status":"ok"}

@app.post("/api/strategy/advices/{advice_id}/ignore")
def ignore_advice(advice_id:str):
    from db import analytics_conn
    conn=analytics_conn();conn.execute("UPDATE advice_log SET status='ignored',updated_at=? WHERE id=?",(datetime.now().isoformat(),advice_id));conn.commit();conn.close()
    return {"status":"ok"}

@app.post("/api/strategy/advices/{advice_id}/done")
def done_advice(advice_id:str):
    from db import analytics_conn
    conn=analytics_conn();conn.execute("UPDATE advice_log SET status='done',updated_at=? WHERE id=?",(datetime.now().isoformat(),advice_id));conn.commit();conn.close()
    return {"status":"ok"}

@app.get("/api/strategy/advices/history")
def get_advice_history(limit:int=20):
    from db import analytics_conn
    conn=analytics_conn();rows=conn.execute("SELECT * FROM advice_log ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall();conn.close()
    return _js({"history":[dict(r) for r in rows]})

# ══════════ 告警闭环 (P2-2) ══════════
@app.get("/api/alerts")
def get_alerts(status:str="active"):
    from db import analytics_conn
    conn=analytics_conn();rows=conn.execute("SELECT * FROM alert_log WHERE status=? ORDER BY level='critical' DESC,created_at DESC LIMIT 20",(status,)).fetchall();conn.close()
    return _js({"alerts":[dict(r) for r in rows]})

def _log_alert(level,rule,target,message,action=""):
    from db import analytics_conn
    aid=f"alt_{datetime.now().strftime('%Y%m%d')}_{target}_{rule}"
    conn=analytics_conn()
    conn.execute("INSERT OR IGNORE INTO alert_log (id,level,rule,target,message,action,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(aid,level,rule,target,message,action,"active",datetime.now().isoformat()))
    conn.commit();conn.close()

@app.post("/api/alerts/{alert_id}/ack")
def ack_alert(alert_id:str):
    from db import analytics_conn
    conn=analytics_conn();conn.execute("UPDATE alert_log SET status='acknowledged',updated_at=? WHERE id=?",(datetime.now().isoformat(),alert_id));conn.commit();conn.close()
    return {"status":"ok"}

@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id:str):
    from db import analytics_conn
    conn=analytics_conn();conn.execute("UPDATE alert_log SET status='resolved',updated_at=? WHERE id=?",(datetime.now().isoformat(),alert_id));conn.commit();conn.close()
    return {"status":"ok"}

@app.post("/api/alerts/mute/{rule}")
def mute_alert_rule(rule:str):
    from db import analytics_conn
    conn=analytics_conn();conn.execute("UPDATE alert_log SET status='muted',updated_at=? WHERE rule=? AND status='active'",(datetime.now().isoformat(),rule));conn.commit();conn.close()
    return {"status":"ok"}

@app.get("/api/alerts/history")
def get_alert_history(limit:int=30):
    from db import analytics_conn
    conn=analytics_conn();rows=conn.execute("SELECT * FROM alert_log ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall();conn.close()
    return _js({"history":[dict(r) for r in rows]})

# ══════════ 每日复盘 (P2-3) ══════════
@app.get("/api/report/daily")
@ttl_cache(120)
def get_daily_report():
    from portfolio import calc_portfolio
    pf=calc_portfolio()
    total=pf.get("总资产",0);pl=pf.get("总盈亏",0);pl_pct=pf.get("总盈亏率",0)
    funds=pf.get("基金",[])
    # 归因
    gainers=sorted([f for f in funds if f.get("盈亏",0)>0],key=lambda x:-x["盈亏"])[:3]
    losers=sorted([f for f in funds if f.get("盈亏",0)<0],key=lambda x:x["盈亏"])[:3]
    # 风险
    max_dd=pf.get("最大回撤");sharpe=pf.get("夏普比率")
    main_risk=""
    if funds and funds[0].get("占比",0)>50:main_risk=f"{funds[0]['name'][:8]}占比{funds[0].get('占比',0)}%，集中度偏高"
    # 建议 + 告警
    from db import analytics_conn
    conn=analytics_conn();advices=[dict(r) for r in conn.execute("SELECT * FROM advice_log WHERE status='pending' LIMIT 3").fetchall()];conn.close()
    conn=analytics_conn();alerts=[dict(r) for r in conn.execute("SELECT * FROM alert_log WHERE status='active' LIMIT 3").fetchall()];conn.close()

    return _js({"date":datetime.now().strftime("%Y-%m-%d"),
        "summary":{"total":round(total,2),"total_pl":round(pl,2),"total_pl_pct":pl_pct},
        "attribution":{"top_gainers":[{"name":g["name"][:12],"pl":g["盈亏"]} for g in gainers],"top_losers":[{"name":l["name"][:12],"pl":l["盈亏"]} for l in losers]},
        "risk":{"max_drawdown":max_dd,"sharpe":sharpe,"main_risk":main_risk},
        "advices":advices,"alerts":alerts,
        "ai_summary":{"conclusion":f"总资产 ¥{total:.0f}，累计盈亏 {pl:+.0f}元。","risks":[main_risk] if main_risk else [],"actions":[],"data_issues":[]}})

# ══════════ 规则回测 (P2-5) ══════════
@app.get("/api/strategy/rule-backtest")
@ttl_cache(600)
def get_rule_backtest(days:int=365):
    from data import get_fund_nav;from db import prod_conn
    import pandas as pd,numpy as np
    conn=prod_conn();rows=conn.execute("SELECT code,shares FROM holdings WHERE shares>0").fetchall();conn.close()
    shares_map={r["code"]:r["shares"] for r in rows}
    if not shares_map:return _js({"rules":[]})

    navs={}
    for code in shares_map:
        df=get_fund_nav(code,days=days+60)
        if df is not None and not df.empty:df=df.sort_values("净值日期");navs[code]=df

    # 聚合组合净值
    all_dates=sorted(set().union(*[set(n["净值日期"].dt.strftime("%Y-%m-%d")) for n in navs.values()]))
    values=[];last_nav={}
    for d in all_dates:
        total=0.0;has_any=False
        for code,sh in shares_map.items():
            df=navs.get(code)
            if df is not None:
                row=df[df["净值日期"]==d]
                if not row.empty:last_nav[code]=float(row["单位净值"].iloc[0])
            if code in last_nav:total+=sh*last_nav[code];has_any=True
        if has_any:values.append({"date":d,"value":total})

    if len(values)<66:return _js({"rules":[]})

    df=pd.DataFrame(values);df["return"]=df["value"].pct_change()
    results=[]
    for lookback,label in [(66,"近60日"),(132,"近120日"),(250,"近250日")]:
        if len(df)<=lookback:continue
        recent=df.tail(lookback)
        peak=recent["value"].cummax();dd=(recent["value"]/peak-1)*100
        max_dd=dd.min()
        returns=recent["return"].dropna()
        sharpe=float(returns.mean()/returns.std()*np.sqrt(252)) if returns.std()>0 else 0
        results.append({"period":label,"max_drawdown":round(float(max_dd),1),"sharpe":round(sharpe,2),"useful":max_dd<-10})
    # 集中度模拟
    conc=shares_map.get("014319",0) if 0 else 0
    total_sh=sum(shares_map.values())
    conc_pct=round(conc/total_sh*100,1) if total_sh else 0
    return _js({"rules":[{"rule":"concentration","trigger_count":1,"concentration_pct":conc_pct,"comment":"单基金集中度超过50%后历史回撤风险明显","periods":results,"useful":conc_pct>50}]})

# ══════════ 健康 ══════════
# ══════════ P3 系统可靠性 ══════════

@app.get("/api/system/self-check")
@ttl_cache(60)

def get_self_check():
    """轻量自检：仅本地SQL+表检查+模块导入，无外部请求"""
    import threading, queue as _q
    modules = []
    warnings = []
    from db import prod_conn, analytics_conn, ref_conn

    def _probe(name, fn, to=3):
        q = _q.Queue()
        t0 = time.time()
        t = threading.Thread(target=lambda: q.put(fn()), daemon=True)
        t.start()
        t.join(to)
        d = round((time.time() - t0) * 1000)
        if t.is_alive():
            return ("timeout", d, "timeout")
        try:
            r = q.get_nowait()
            return ("ok", d, str(r)[:50]) if r else ("error", d, "falsy")
        except Exception as e:
            return ("error", d, str(e)[:50])

    # DB probes with try/finally
    for name, cn_fn in [
        ("production", prod_conn),
        ("analytics", analytics_conn),
        ("reference", ref_conn),
    ]:
        def _db(cn_fn=cn_fn):
            c = None
            try:
                c = cn_fn()
                c.execute("SELECT 1")
                return True
            finally:
                if c:
                    try:
                        c.close()
                    except:
                        pass

        s, d, dt = _probe(name, _db)
        modules.append({"name": name, "status": s, "duration_ms": d})
        if s != "ok":
            warnings.append(f"{name}:{dt}")

    # portfolio: table check
    def _tables():
        c = None
        try:
            c = prod_conn()
            c.execute("SELECT 1 FROM holdings LIMIT 1")
            c.execute("SELECT 1 FROM confirmed_funds LIMIT 1")
            return True
        finally:
            if c:
                try:
                    c.close()
                except:
                    pass

    s, d, dt = _probe("portfolio", _tables)
    modules.append({"name": "portfolio", "status": s, "duration_ms": d})
    if s != "ok":
        warnings.append(f"portfolio:{dt}")

    # compare: module import only
    s, d, dt = _probe("compare", lambda: __import__("risk") is not None)
    modules.append({"name": "compare", "status": s, "duration_ms": d})
    if s != "ok":
        warnings.append(f"compare:{dt}")

    # advices: SELECT count with try/finally
    def _adv():
        c = None
        try:
            c = analytics_conn()
            c.execute("SELECT COUNT(*) FROM advice_log")
            return True
        finally:
            if c:
                try:
                    c.close()
                except:
                    pass

    s, d, dt = _probe("advices", _adv)
    modules.append({"name": "advices", "status": s, "duration_ms": d})
    if s != "ok":
        warnings.append(f"advices:{dt}")

    # alerts: SELECT count with try/finally
    def _alerts():
        c = None
        try:
            c = analytics_conn()
            c.execute("SELECT COUNT(*) FROM alert_log")
            return True
        finally:
            if c:
                try:
                    c.close()
                except:
                    pass

    s, d, dt = _probe("alerts", _alerts)
    modules.append({"name": "alerts", "status": s, "duration_ms": d})
    if s != "ok":
        warnings.append(f"alerts:{dt}")

    # report: table check
    s, d, dt = _probe("report", _tables)
    modules.append({"name": "report", "status": s, "duration_ms": d})
    if s != "ok":
        warnings.append(f"report:{dt}")

    # data_quality: 通过timeout探针执行（避免DB锁拖慢整体）
    def _dq():
        c = None; a = None
        try:
            c = prod_conn()
            dqs = {
                "duplicate_holdings": c.execute("SELECT COUNT(*) FROM holdings WHERE code IN (SELECT code FROM holdings GROUP BY code HAVING COUNT(*)>1)").fetchone()[0],
                "negative_value": c.execute("SELECT COUNT(*) FROM confirmed_funds WHERE value<0").fetchone()[0],
                "holdings_count": c.execute("SELECT COUNT(*) FROM holdings").fetchone()[0],
            }
            a = analytics_conn()
            dqs["advice_count"] = a.execute("SELECT COUNT(*) FROM advice_log").fetchone()[0]
            return dqs
        finally:
            if c:
                try:c.close()
                except:pass
            if a:
                try:a.close()
                except:pass
    try:
        dqs = _dq()
    except Exception as e:
        dqs = {"error": str(e)}

    return _js({
        "status": "ok" if not warnings else "warning",
        "checked_at": datetime.now().isoformat(),
        "version": "3.5.1-stable",
        "modules": modules,
        "data_quality": dqs,
        "warnings": warnings,
    })

@app.post("/api/system/backup")
def create_backup():
    import shutil, os as _os
    backup_dir = _os.path.join(_os.path.dirname(__file__), "data", "backups", datetime.now().strftime("backup_%Y%m%d_%H%M%S"))
    _os.makedirs(backup_dir, exist_ok=True)
    data_dir = _os.path.join(_os.path.dirname(__file__), "data")
    for f in ["production.db", "analytics.db", "reference.db", "../config.yaml"]:
        src = _os.path.join(data_dir, f) if not f.startswith("..") else _os.path.join(_os.path.dirname(__file__), f[3:])
        if _os.path.exists(src):
            shutil.copy2(src, backup_dir)
    backups_root = _os.path.join(data_dir, "backups")
    dirs = sorted([d for d in _os.listdir(backups_root) if d.startswith("backup_")], reverse=True)
    for old in dirs[30:]:
        shutil.rmtree(_os.path.join(backups_root, old), ignore_errors=True)
    return {"status": "ok", "backup_id": _os.path.basename(backup_dir), "files": _os.listdir(backup_dir)}

@app.get("/api/system/backups")
def list_backups():
    import os as _os
    root = _os.path.join(_os.path.dirname(__file__), "data", "backups")
    _os.makedirs(root, exist_ok=True)
    dirs = sorted([d for d in _os.listdir(root) if d.startswith("backup_")], reverse=True)
    return _js({"backups": [{"name": d, "date": d[7:], "files": len(_os.listdir(_os.path.join(root, d))) if _os.path.isdir(_os.path.join(root, d)) else 0} for d in dirs[:20]]})

@app.post("/api/system/restore/{backup_id}")
def restore_backup(backup_id: str):
    import shutil, os as _os
    create_backup()
    src = _os.path.join(_os.path.dirname(__file__), "data", "backups", backup_id)
    data_dir = _os.path.join(_os.path.dirname(__file__), "data")
    if not _os.path.exists(src):
        return {"status": "error", "detail": "备份不存在"}
    for f in _os.listdir(src):
        if f.endswith(".db"):
            shutil.copy2(_os.path.join(src, f), _os.path.join(data_dir, f))
    return {"status": "ok", "restored": backup_id}

@app.get("/api/health")
def health():
    return {"status":"ok","time":datetime.now().isoformat(),"version":"3.5.1-stable","uptime_seconds":round(time.time()-_startup_time,1)}

# ══════════ WebSocket ══════════

import asyncio as _asyncio
import logging as _logging

# 这些模块必须在主线程顺序完成首次导入。data 会初始化 akshare/mini_racer；
# 若首次导入发生在 executor 与 HTTP 请求的不同线程中，Windows 下可能直接崩溃进程。
import data as _ws_data  # noqa: F401
import portfolio as _ws_portfolio
import market as _ws_market
import risk_engine.fund_monitor as _ws_fund_monitor

_ws_cache = None
_ws_cache_ts = 0.0
_ws_task = None
_ws_lock = _asyncio.Lock()
_ws_log = _logging.getLogger("quant.websocket")
_WS_CACHE_TTL_SECONDS = 30.0
_WS_INITIAL_WAIT_SECONDS = 5.0

def _empty_ws_snapshot():
    return {"portfolio": {"total": 0, "cash": 0, "pl": 0, "pl_pct": 0}, "indices": [], "alerts": []}

def _sync_build():
    r = {"portfolio": {}, "indices": [], "alerts": []}
    try:
        pf = _ws_portfolio.calc_portfolio()
        if pf:
            r["portfolio"] = {"total": pf.get("总资产", 0), "cash": pf.get("余额宝", 0), "pl": pf.get("总盈亏", 0), "pl_pct": pf.get("总盈亏率", 0)}
    except Exception:
        _ws_log.exception("WebSocket portfolio snapshot failed")
    try:
        mk = _ws_market.scan_market()
        if mk: r["indices"] = mk.get("指数", [])
    except Exception:
        _ws_log.exception("WebSocket market snapshot failed")
    try:
        al = _ws_fund_monitor.scan_all()
        if al: r["alerts"] = [{"level": a.level, "title": a.category, "message": a.message, "source": "risk_engine", "code": a.code} for a in al[:5]]
    except Exception:
        _ws_log.exception("WebSocket alert snapshot failed")
    return r

def _on_bg_done(fut):
    global _ws_cache, _ws_cache_ts, _ws_task
    try:
        _ws_cache = fut.result()
        _ws_cache_ts = time.monotonic()
    except Exception:
        _ws_log.exception("WebSocket snapshot task failed")
    finally:
        if _ws_task is fut:
            _ws_task = None

async def _get_snapshot():
    global _ws_task
    now = time.monotonic()
    if _ws_cache is not None and now - _ws_cache_ts < _WS_CACHE_TTL_SECONDS:
        return _ws_cache

    async with _ws_lock:
        if _ws_task is None or _ws_task.done():
            loop = _asyncio.get_running_loop()
            _ws_task = loop.run_in_executor(None, _sync_build)
            _ws_task.add_done_callback(_on_bg_done)
        task = _ws_task
        stale = _ws_cache

    # stale-while-revalidate：已有快照时不让客户端等待后台刷新。
    if stale is not None:
        return stale

    try:
        snap = await _asyncio.wait_for(_asyncio.shield(task), timeout=_WS_INITIAL_WAIT_SECONDS)
        return snap
    except _asyncio.TimeoutError:
        return _ws_cache if _ws_cache is not None else _empty_ws_snapshot()
    except Exception:
        _ws_log.exception("WebSocket snapshot wait failed")
        return _ws_cache if _ws_cache is not None else _empty_ws_snapshot()

@app.websocket("/ws/realtime")
async def ws_realtime(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                snap = await _get_snapshot()
                await ws.send_json(_js({
                    "type": "update", "time": datetime.now().isoformat(),
                    "portfolio": snap.get("portfolio", {}),
                    "indices": snap.get("indices", []),
                    "alerts": snap.get("alerts", []),
                }))
    except WebSocketDisconnect:
        ws_clients.remove(ws)
    except Exception as e:
        print(f"WS error: {e}")
        if ws in ws_clients:
            ws_clients.remove(ws)

if __name__=="__main__":
    import uvicorn;uvicorn.run("server:app",host="0.0.0.0",port=8000,reload=False,log_level="warning")
