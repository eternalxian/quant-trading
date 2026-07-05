# ── 持仓配置 ──
# ⚠️ 公开发布前请将以下数据替换为示例值
FUNDS = {
    "000001": {"name": "示例基金A", "type": "QDII"},
    "000002": {"name": "示例基金B", "type": "A_stock"},
}

# ── 策略参数 ──
MOMENTUM_DAYS = 20
MA_SHORT = 5
MA_LONG = 20

# ── 每日定投计划 ──
DCA_SCHEDULE = {
    "000001": 100,   # 示例
}

# ── ETF 观察池 ──
ETF_WATCHLIST = {
    "510050": "上证50ETF",
    "510300": "沪深300ETF",
    "159915": "创业板ETF",
}
