"""WebSocket snapshot coordinator unit gate (run against a temporary project copy)."""
import asyncio
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = _HERE if os.path.exists(os.path.join(_HERE, "server.py")) else os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

import server


def _snapshot(total):
    return {
        "portfolio": {"total": total, "cash": 0, "pl": 0, "pl_pct": 0},
        "indices": [],
        "alerts": [],
    }


async def main():
    original = {
        "build": server._sync_build,
        "wait": server._WS_INITIAL_WAIT_SECONDS,
        "ttl": server._WS_CACHE_TTL_SECONDS,
        "log_disabled": server._ws_log.disabled,
    }
    calls = {"count": 0}

    def reset():
        server._ws_cache = None
        server._ws_cache_ts = 0.0
        server._ws_task = None
        server._ws_lock = asyncio.Lock()

    try:
        server._WS_INITIAL_WAIT_SECONDS = 0.05
        server._WS_CACHE_TTL_SECONDS = 30.0
        server._ws_log.disabled = True
        reset()

        def slow_build():
            calls["count"] += 1
            time.sleep(0.20)
            return _snapshot(123)

        server._sync_build = slow_build
        started = time.perf_counter()
        first, second = await asyncio.gather(server._get_snapshot(), server._get_snapshot())
        elapsed = time.perf_counter() - started
        assert calls["count"] == 1, f"single-flight started {calls['count']} builds"
        assert first["portfolio"]["total"] == 0 and second["portfolio"]["total"] == 0
        assert elapsed < 0.15, f"timeout fallback took {elapsed:.3f}s"

        await asyncio.sleep(0.25)
        cached = await server._get_snapshot()
        assert cached["portfolio"]["total"] == 123, "completed task was not published"
        assert calls["count"] == 1

        def refresh_build():
            calls["count"] += 1
            time.sleep(0.20)
            return _snapshot(456)

        server._sync_build = refresh_build
        server._ws_cache_ts = time.monotonic() - 60
        started = time.perf_counter()
        stale = await server._get_snapshot()
        stale_elapsed = time.perf_counter() - started
        assert stale["portfolio"]["total"] == 123
        assert stale_elapsed < 0.10, f"stale cache blocked for {stale_elapsed:.3f}s"
        await asyncio.sleep(0.25)
        refreshed = await server._get_snapshot()
        assert refreshed["portfolio"]["total"] == 456, "refresh result was not published"
        assert calls["count"] == 2

        reset()

        def failed_build():
            raise RuntimeError("controlled test failure")

        server._sync_build = failed_build
        fallback = await server._get_snapshot()
        assert fallback == server._empty_ws_snapshot(), "failure fallback is incompatible"
        await asyncio.sleep(0)

        print("PASS WS unit: single-flight=1 timeout fallback cache publish stale refresh error isolation")
        return 0
    finally:
        task = server._ws_task
        if task is not None and not task.done():
            await asyncio.shield(task)
        server._sync_build = original["build"]
        server._WS_INITIAL_WAIT_SECONDS = original["wait"]
        server._WS_CACHE_TTL_SECONDS = original["ttl"]
        server._ws_log.disabled = original["log_disabled"]
        reset()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
