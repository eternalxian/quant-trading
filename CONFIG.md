# 配置说明

> config.py 示例。脱敏版。

```python
# 数据库
DB_PATH = "quant.db"

# 数据源
USE_AKSHARE = True  # 免费数据源
CACHE_DIR = "./cache"

# 交易参数
INITIAL_CAPITAL = 100000  # 初始资金
MAX_POSITION_RATIO = 0.3  # 单股最大仓位 30%
MAX_INDUSTRY_RATIO = 0.5  # 单行业最大 50%

# 风控
DAILY_LOSS_LIMIT = 0.05   # 日亏损熔断 5%
CIRCUIT_BREAKER_COOLDOWN = 3600  # 熔断冷却 1小时

# 信号权重
SIGNAL_WEIGHTS = {
    "macd": 0.15,
    "rsi": 0.10,
    "bollinger": 0.10,
    "ml_score": 0.30,
    "money_flow": 0.20,
    "rotation": 0.15
}

# 告警
DINGTALK_WEBHOOK = ""     # 钉钉机器人 webhook（留空=不启用）
```
