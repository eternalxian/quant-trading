"""子进程路由检查——6条目标路由验证"""
import sys, os
target = os.path.abspath(sys.argv[1])
root = os.path.dirname(target) if os.path.isfile(target) else target
sys.path.insert(0, root)
os.chdir(root)
from server import app
routes = {}; dup = 0
for r in app.routes:
    m = getattr(r, 'methods', None)
    for method in (m or {'WS'}):
        k = (method, r.path)
        routes[k] = routes.get(k, 0) + 1
        if routes[k] > 1: dup += 1; print(f"DUPLICATE: {k} count={routes[k]}")
targets = [
    ('POST', '/api/system/backup'),
    ('GET', '/api/system/backups'),
    ('POST', '/api/system/restore/{backup_id}'),
    ('GET', '/api/system/self-check'),
    ('GET', '/api/portfolio/exposure'),
    ('GET', '/api/fund/{code}/kline'),
]
all_ok = True
for m, p in targets:
    got = routes.get((m, p), 0)
    ok = (got == 1)
    if not ok: all_ok = False
    print(f"{'OK' if ok else 'MISSING'} {m} {p}: count={got}")
sys.exit(0 if (dup == 0 and all_ok) else 1)
