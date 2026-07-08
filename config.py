"""
配置加载器

优先级: 环境变量 QUANT_<KEY> > config.yaml > 硬编码默认值

用法:
    from config import FUNDS, DCA_SCHEDULE, SIGNAL_CONFIG

添加/修改配置:
    1. 编辑 config.yaml（推荐）
    2. 或设置环境变量 QUANT_<KEY>=<value>
"""
import os
import yaml

# ── 默认值（fallback）──

_DEFAULTS = {
    "FUNDS": {
        "014319": {"name": "德邦半导体产业混合A", "type": "A_stock"},
        "017641": {"name": "摩根标普500指数A", "type": "QDII"},
        "270042": {"name": "广发纳斯达克100ETF联接A", "type": "QDII"},
        "012920": {"name": "易方达全球成长精选混合A", "type": "QDII"},
        "005698": {"name": "华夏全球科技先锋混合A", "type": "QDII"},
        "000834": {"name": "大成纳斯达克100ETF联接A", "type": "QDII"},
    },
    "MOMENTUM_DAYS": 20,
    "MA_SHORT": 5,
    "MA_LONG": 20,
    "DCA_SCHEDULE": {},
    "ETF_WATCHLIST": {
        "513100": "纳指ETF", "512480": "半导体ETF", "515050": "通信ETF",
        "159611": "电力ETF", "513500": "标普500ETF", "515070": "人工智能ETF",
    },
    "ROTATION_ETF_CODES": {
        "513100": "纳指ETF", "513500": "标普500ETF", "512480": "半导体ETF",
        "515050": "通信ETF", "515070": "人工智能ETF", "159611": "电力ETF",
    },
    "STOCK_WATCHLIST": {
        "601985": "中国核电", "600905": "三峡能源", "600903": "贵州燃气",
        "601991": "大唐发电", "600589": "大卫科技", "600886": "国投电力",
        "600795": "国电电力", "003816": "中国广核", "600157": "永泰能源",
        "600452": "涪陵电力", "601016": "节能风电", "601778": "晶科科技",
        "000591": "太阳能", "600011": "华能国际", "600674": "川投能源",
        "000690": "宝新能源", "600930": "华电新能", "002195": "岩山科技",
        "300088": "长信科技", "002456": "欧菲光", "002065": "东华软件",
        "000725": "京东方A", "002681": "奋达科技",
    },
    "SIGNAL_CONFIG": {
        "score_window": 25, "rebalance_freq": 20,
        "momentum_threshold": 0.02, "max_position_pct": 0.30,
    },
    "STOCK_TRADING": {
        "max_risk_per_trade": 0.02, "max_position_pct": 0.30,
        "max_total_positions": 5, "default_stop_atr_mult": 2.0,
        "min_risk_reward": 2.0, "max_daily_loss_pct": 0.05,
        "commission": 0.0003, "stamp_tax_sell": 0.001,
        "slippage": 0.001, "default_capital": 4000,
    },
}


def _load_yaml():
    """尝试加载 config.yaml"""
    yaml_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if not os.path.exists(yaml_path):
        return {}
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _merge_env(overrides: dict) -> dict:
    """QUANT_<KEY>=<value> 或 QUANT_<KEY>=<json>"""
    for key, val in os.environ.items():
        if not key.startswith("QUANT_"):
            continue
        config_key = key[6:]  # strip QUANT_
        try:
            val = yaml.safe_load(val)
        except Exception:
            pass  # keep as string
        overrides[config_key] = val
    return overrides


# ── 加载 ──

_yaml_config = _load_yaml()
_merged = {**_DEFAULTS, **_yaml_config}
_merged = _merge_env(_merged)

# key mapping: YAML key → config.py variable name
_KEY_MAP = {
    "funds": "FUNDS", "momentum_days": "MOMENTUM_DAYS",
    "ma_short": "MA_SHORT", "ma_long": "MA_LONG",
    "dca_schedule": "DCA_SCHEDULE", "etf_watchlist": "ETF_WATCHLIST",
    "rotation_etf_codes": "ROTATION_ETF_CODES",
    "stock_watchlist": "STOCK_WATCHLIST",
    "signal_config": "SIGNAL_CONFIG", "stock_trading": "STOCK_TRADING",
}

# 将 YAML 的 snake_case key 映射到 UPPER_CASE 变量名
for yaml_key, var_name in _KEY_MAP.items():
    if yaml_key in _yaml_config:
        _merged[var_name] = _yaml_config[yaml_key]

# ── 导出 ──

FUNDS = _merged.get("FUNDS", _DEFAULTS["FUNDS"])
MOMENTUM_DAYS = _merged.get("MOMENTUM_DAYS", 20)
MA_SHORT = _merged.get("MA_SHORT", 5)
MA_LONG = _merged.get("MA_LONG", 20)
DCA_SCHEDULE = _merged.get("DCA_SCHEDULE", {})
ETF_WATCHLIST = _merged.get("ETF_WATCHLIST", {})
ROTATION_ETF_CODES = _merged.get("ROTATION_ETF_CODES", {})
STOCK_WATCHLIST = _merged.get("STOCK_WATCHLIST", {})
SIGNAL_CONFIG = _merged.get("SIGNAL_CONFIG", {})
STOCK_TRADING = _merged.get("STOCK_TRADING", {})

__all__ = [
    "FUNDS", "MOMENTUM_DAYS", "MA_SHORT", "MA_LONG",
    "DCA_SCHEDULE", "ETF_WATCHLIST", "ROTATION_ETF_CODES",
    "STOCK_WATCHLIST", "SIGNAL_CONFIG", "STOCK_TRADING",
]
