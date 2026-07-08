"""系统测试 v3.5.1 — 父进程隔离 + 子进程测试
Route check via pre-written script (no inline code gen)
"""
import sys,os,shutil,urllib.request,urllib.error,json,time,tempfile,subprocess,socket,hashlib,concurrent.futures

BASE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR=os.path.join(BASE_DIR,"data")
SCRIPTS_DIR=os.path.join(BASE_DIR,"scripts")

def _free_port():
    s=socket.socket();s.bind(("",0));port=s.getsockname()[1];s.close();return port

def _db_hash(dbname):
    with open(os.path.join(DATA_DIR,dbname),"rb") as f:return hashlib.sha256(f.read()).hexdigest()

def _file_hash(p):
    with open(p,"rb") as f:return hashlib.sha256(f.read()).hexdigest()

def parent():
    temp_dir=None;server_proc=None;child_result=None
    try:
        print("=== Parent: recording DB hashes ===")
        hashes_before={db:_db_hash(db) for db in ["production.db","analytics.db","reference.db"]}
        for db,h in hashes_before.items():print(f"  {db}: {h[:16]}...")

        print("\n=== Parent: creating temp project ===")
        temp_dir=tempfile.mkdtemp(prefix="quant_test_");print(f"  {temp_dir}")
        for f in os.listdir(BASE_DIR):
            if f.endswith(".py"):shutil.copy2(os.path.join(BASE_DIR,f),temp_dir)
        shutil.copy2(os.path.join(BASE_DIR,"config.yaml"),temp_dir)
        for d in ["risk_engine","validators"]:
            if os.path.isdir(os.path.join(BASE_DIR,d)):
                shutil.copytree(os.path.join(BASE_DIR,d),os.path.join(temp_dir,d))
        os.makedirs(os.path.join(temp_dir,"data"))
        for f in os.listdir(DATA_DIR):
            src=os.path.join(DATA_DIR,f)
            if os.path.isfile(src) and not f.startswith("backup_") and f!="quant_backup_20260706_205638.db":
                shutil.copy2(src,os.path.join(temp_dir,"data",f))
        os.makedirs(os.path.join(temp_dir,"logs"),exist_ok=True)

        import sqlite3
        tmp_analytics=os.path.join(temp_dir,"data","analytics.db")
        conn=sqlite3.connect(tmp_analytics)
        conn.execute("INSERT OR REPLACE INTO advice_log (id,type,action,target,target_name,level,reason,suggestion,status,created_at) VALUES ('test_advice_r2','rebalance','减仓','014319','测试基金','high','测试集中度','测试建议','pending',datetime('now','localtime'))")
        conn.commit();conn.close()
        tmp_hash_before=_file_hash(tmp_analytics)
        print(f"  test advice inserted, hash_before={tmp_hash_before[:16]}...")

        # Route check via pre-written script
        print("\n=== Parent: route uniqueness check ===")
        rc_src=os.path.join(SCRIPTS_DIR,"_route_check.py")
        rc_dst=os.path.join(temp_dir,"_route_check.py")
        if os.path.exists(rc_src):
            shutil.copy2(rc_src,rc_dst)
            route_result=subprocess.run([sys.executable,rc_dst,temp_dir],capture_output=True,text=True,timeout=30)
            print(route_result.stdout)
            if route_result.returncode!=0:print("Route check FAILED");return 1

        print("\n=== Parent: WebSocket coordinator unit gate ===")
        ws_src=os.path.join(SCRIPTS_DIR,"_ws_unit_check.py")
        ws_dst=os.path.join(temp_dir,"_ws_unit_check.py")
        if not os.path.exists(ws_src):print("WebSocket unit gate MISSING");return 1
        shutil.copy2(ws_src,ws_dst)
        ws_unit_result=subprocess.run([sys.executable,ws_dst],cwd=temp_dir,capture_output=True,text=True,timeout=30)
        print(ws_unit_result.stdout)
        if ws_unit_result.stderr:print(ws_unit_result.stderr)
        if ws_unit_result.returncode!=0:print("WebSocket unit gate FAILED");return 1

        print("\n=== Parent: starting server ===")
        test_port=_free_port()
        env=os.environ.copy()
        env["QUANT_TEST_BASE"]=f"http://127.0.0.1:{test_port}"
        env["QUANT_TEST_CHILD"]="1"
        env["NO_PROXY"]="127.0.0.1,localhost,"+env.get("NO_PROXY",env.get("no_proxy",""))
        env["no_proxy"]=env["NO_PROXY"]
        server_proc=subprocess.Popen(
            [sys.executable,"-m","uvicorn","server:app","--host","127.0.0.1","--port",str(test_port),"--log-level","warning","--workers","1"],
            cwd=temp_dir,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(30):
            try:urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/health",timeout=2);break
            except:time.sleep(0.5)
        else:print("Server failed to start");return 1
        print(f"  Server on port {test_port}")

        print("\n=== Parent: running child tests ===")
        child_result=subprocess.run([sys.executable,__file__],env=env,capture_output=True,text=True,timeout=150)
        print(child_result.stdout)
        if child_result.stderr:print(child_result.stderr)

    finally:
        if server_proc:
            print("\n=== Parent: stopping server ===")
            try:server_proc.terminate();server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:server_proc.kill()
        if temp_dir and os.path.exists(temp_dir):
            print("=== Parent: checking DB hashes ===")
            hashes_after={db:_db_hash(db) for db in ["production.db","analytics.db","reference.db"]}
            all_db_ok=True
            for db in hashes_before:
                ok=hashes_before[db]==hashes_after[db]
                print(f"  {db}: {'UNCHANGED' if ok else 'CHANGED!!!'}")
                if not ok:all_db_ok=False
            tmp_hash_after=_file_hash(tmp_analytics)
            temp_changed=tmp_hash_after!=tmp_hash_before
            print(f"  temp analytics: changed={temp_changed}")
            print(f"\n=== Parent: cleanup ===")
            shutil.rmtree(temp_dir)
            print(f"  {temp_dir} removed")
            child_ok=child_result is not None and child_result.returncode==0
            exit_code=0 if (all_db_ok and temp_changed and child_ok) else 1
            if not all_db_ok:print("FAIL: production DB changed")
            if not temp_changed:print("FAIL: temp analytics not modified")
            if child_result is not None and child_result.returncode!=0:print(f"FAIL: child tests returned {child_result.returncode}")
            elif child_result is None:print("FAIL: child tests not run");exit_code=1
            sys.exit(exit_code)
    return 1

def child():
    BASE=os.environ.get("QUANT_TEST_BASE","http://localhost:8000")
    PASS=FAIL=0
    def _r(ep,method="GET",body=None,timeout=60):
        data=json.dumps(body).encode() if body else None
        req=urllib.request.Request(f"{BASE}{ep}",data=data,method=method)
        if body:req.add_header("Content-Type","application/json")
        return urllib.request.urlopen(req,timeout=timeout)

    def check(ep,label,fn,method="GET",body=None,expect=200):
        nonlocal PASS,FAIL
        try:r=_r(ep,method,body)
        except urllib.error.HTTPError as e:
            if e.code==expect and expect>=400:
                d=json.loads(e.read());ok=fn(d)
                if ok:PASS+=1;print(f"  PASS  {method:4s} {ep:50s} HTTP {e.code} {label}")
                else:FAIL+=1;print(f"  FAIL  {method:4s} {ep:50s} HTTP {e.code}")
            else:FAIL+=1;print(f"  FAIL  {method:4s} {ep:50s} HTTP {e.code} expect {expect}")
            return
        except Exception as e:FAIL+=1;print(f"  FAIL  {method:4s} {ep:50s} {type(e).__name__}: {str(e)[:50]}");return
        if r.status!=expect:FAIL+=1;print(f"  FAIL  {method:4s} {ep:50s} expect {expect} got {r.status}");return
        d=json.loads(r.read());ok=fn(d)
        if ok:PASS+=1;print(f"  PASS  {method:4s} {ep:50s} {label}")
        else:FAIL+=1;print(f"  FAIL  {method:4s} {ep:50s} {label}")

    def verdict(label,ok,detail=""):
        nonlocal PASS,FAIL
        if ok:PASS+=1;print(f"  PASS  WS   {label:54s} {detail}")
        else:FAIL+=1;print(f"  FAIL  WS   {label:54s} {detail}")

    print(f"=== Child: testing {BASE} ===\n")
    check("/api/health","status ok + stable version",lambda d:d.get("status")=="ok" and d.get("version")=="3.5.1-stable")
    check("/api/portfolio","total>0",lambda d:d.get("total",0)>0)
    check("/api/portfolio","has sharpe",lambda d:d.get("sharpe") is not None)
    t0=time.time();sc_resp=_r("/api/system/self-check");sc=json.loads(sc_resp.read());elapsed=round(time.time()-t0,2)
    ok=(sc.get("status")in("ok","warning") and elapsed<5 and len(sc.get("modules",[]))>=8
        and all("duration_ms" in m for m in sc.get("modules",[])) and "3.5.1" in sc.get("version",""))
    if ok:PASS+=1;print(f"  PASS  SELF  /api/system/self-check                             {elapsed}s v{sc.get('version','?')} mods={len(sc.get('modules',[]))}")
    else:FAIL+=1;print("  FAIL  SELF  /api/system/self-check")

    # R4: two WebSocket clients trigger one background refresh while HTTP stays responsive.
    ws1=ws2=None
    try:
        import websocket
        ws_url="ws"+BASE[4:]+"/ws/realtime"
        ws1=websocket.create_connection(ws_url,timeout=10)
        ws2=websocket.create_connection(ws_url,timeout=10)

        def ws_ping(ws):
            t=time.time();ws.send("ping");payload=json.loads(ws.recv())
            return payload,time.time()-t

        def timed_get(path,timeout=15):
            t=time.time();payload=json.loads(_r(path,timeout=timeout).read())
            return payload,time.time()-t

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures=[pool.submit(ws_ping,ws1),pool.submit(ws_ping,ws2),
                     pool.submit(timed_get,"/api/health"),pool.submit(timed_get,"/api/system/self-check"),
                     pool.submit(timed_get,"/api/portfolio")]
            w1,w2,health_live,self_live,portfolio_live=[f.result(timeout=20) for f in futures]

        verdict("two clients receive compatible update",w1[0].get("type")=="update" and w2[0].get("type")=="update" and w1[1]<6.5 and w2[1]<6.5,f"{w1[1]:.2f}s/{w2[1]:.2f}s")
        verdict("health remains below 2s during ping",health_live[0].get("status")=="ok" and health_live[1]<2,f"{health_live[1]:.2f}s")
        verdict("self-check remains below 2s during ping",self_live[0].get("status") in ("ok","warning") and self_live[1]<2,f"{self_live[1]:.2f}s")
        verdict("portfolio survives concurrent first refresh",portfolio_live[0].get("total",0)>0 and portfolio_live[1]<10,f"{portfolio_live[1]:.2f}s")
        # React development mode may issue duplicate initial requests. This used to
        # initialize py_mini_racer concurrently and terminate the whole process.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            compare_futures=[pool.submit(timed_get,"/api/compare?days=30",45) for _ in range(2)]
            compare_results=[f.result(timeout=60) for f in compare_futures]
        compare_alive=all(isinstance(item[0],dict) for item in compare_results)
        verdict("duplicate benchmark requests do not crash AKShare",compare_alive,f"{compare_results[0][1]:.2f}s/{compare_results[1][1]:.2f}s")
        alive=json.loads(_r("/api/health",timeout=5).read()).get("status")=="ok"
        verdict("server process remains alive after concurrent requests",alive)
    except Exception as e:
        verdict("WebSocket concurrency gate",False,f"{type(e).__name__}: {str(e)[:80]}")
    finally:
        for ws in (ws1,ws2):
            if ws:
                try:ws.close()
                except:pass
    check("/api/fund/014319/kline?days=30","has data",lambda d:len(d.get("data",[]))>0)
    check("/api/fund/014319/kline?days=30","has code+metrics",lambda d:d.get("code")=="014319" and d.get("metrics") is not None)
    check("/api/fund/005698/kline?days=30","QDII data",lambda d:len(d.get("data",[]))>0)
    check("/api/fund/999999/kline?days=10","error non-empty",lambda d:isinstance(d.get("error"),str) and len(d.get("error",""))>0,expect=404)
    check("/api/fund/999999/kline?days=10","data empty",lambda d:d.get("data")==[],expect=404)
    check("/api/system/backup","status ok+id",lambda d:d.get("status")=="ok" and isinstance(d.get("backup_id"),str),method="POST")
    check("/api/portfolio/exposure",">=2 themes",lambda d:len(d.get("theme_exposure",[]))>=2)
    check("/api/report/daily","has summary",lambda d:d.get("summary") is not None)
    check("/api/strategy/advices/test_advice_r2/confirm","POST confirm",lambda d:isinstance(d,dict),method="POST",body={})
    check("/api/strategy/advices/history","history accepted",lambda d:any(a.get("id")=="test_advice_r2" and a.get("status")=="accepted" for a in d.get("history",[])))
    check("/api/strategy/advices/test_advice_r2/ignore","POST ignore",lambda d:isinstance(d,dict),method="POST",body={})
    check("/api/strategy/advices/history","history ignored",lambda d:any(a.get("id")=="test_advice_r2" and a.get("status")=="ignored" for a in d.get("history",[])))
    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL==0 else 1

if __name__=="__main__":
    if os.environ.get("QUANT_TEST_CHILD")=="1":sys.exit(child())
    else:sys.exit(parent())
