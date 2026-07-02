# REASONIX.md

AI Quant Runtime — 数据→信号→风控→建议→执行，完整闭环。

## 架构

```
Next.js :3000  →  FastAPI :8000  →  Python 量化模块
前端终端              API Gateway        portfolio/signals/stock/ai
```

启动: `python -m uvicorn server:app --host 0.0.0.0 --port 8000 --log-level critical --workers 1`
前端: `cd terminal && npx next dev --port 3000`

## 项目结构

```
E:\quant\
├── server.py              # FastAPI (20+端点)
├── main.py                # CLI 入口
├── config.py              # FUNDS + ETF_WATCHLIST
├── data.py / db.py        # 数据层 (SQLite + akshare)
├── stock.py               # 个股引擎 (Sina实时+全策略信号)
├── portfolio.py           # 持仓追踪 (市值/盈亏/DCA)
├── market.py              # 市场扫描
├── ai.py                  # LLM 调用 (Ollama deepseek)
├── daily_report.py        # 每日复盘日报
│
├── risk_engine/           # 风控引擎 (确定性规则)
│   ├── rules.py           # RiskDecision + evaluate()
│   └── circuit_breaker.py # 熔断器
│
├── strategy/              # 策略引擎
│   ├── engine.py          # 信号→建议→风控流水线
│   ├── etf_engine.py      # ETF轮动封装
│   ├── health.py          # rolling metrics + 降级
│   └── optimizer.py       # 参数网格搜索
│
├── execution/             # 执行层
│   └── order_manager.py   # BaseBroker → PaperBroker
│
├── runtime/               # 运行时
│   ├── runtime_loop.py    # 主循环 tick() / run_forever()
│   ├── state_checker.py   # 5项一致性检查
│   ├── market_clock.py    # 交易时段
│   └── recovery.py        # 故障恢复/重试
│
├── agents/                # AI Agent (3个)
│   ├── stock_agent.py     # 个股分析
│   ├── macro_agent.py     # 宏观分析
│   └── sentiment_agent.py # 情绪分析
│
├── validators/            # 数据校验
├── signals/               # 26个信号模块
├── backtest/              # 回测引擎
├── terminal/              # Next.js 前端 (10页)
└── data/                  # quant.db + CSV
```

## 当前持仓 (2026-05-20)

8 只基金（007817 国泰通信已于5/19清仓转半导体）：

| 代码 | 名称 | 类型 |
|------|------|------|
| 014319 | 德邦半导体A | A_stock (最大持仓) |
| 011839 | 天弘人工智能A | A_stock |
| 016185 | 广发电力A | A_stock |
| 005698 | 华夏全球科技QDII | QDII |
| 000834 | 大成纳指100QDII | QDII |
| 017641 | 摩根标普500QDII | QDII |
| 270042 | 广发纳指QDII | QDII |
| 012920 | 易方达全球成长QDII | QDII |

定投: 广发纳指 10元/天, 易方达全球成长 20元/天

## 待确认申购 (5/19)

- 014319 +2,447 (通信超级转换)
- 000834 +500
- 270042 +20 (DCA)
- 012920 +40 (DCA)

## 最新确认数据 (5/20 支付宝)

- 总资产: ¥17,517 (基金15,040 + 余额宝2,477)
- 今日收益: +¥188.09 (+1.07%)
- 数据已持久化到 SQLite confirmed_daily 表，重启不丢

## 前端同步面板

概览页顶部：填入基金持有总金额+余额宝+今日收益 → 点确认
点"沿用昨日"自动填前两个，只需改收益

## 关键行为规则

1. **风控绝不LLM化** — 确定性Python规则
2. **基金净值20:00后发布**，系统显示可能滞后，用手动确认数据
3. **ETF实时跟踪开盘才有数据**，盘前显示0是正常的
4. **server.py切勿用--reload**，用--workers 1防止py_mini_racer崩溃
5. **确认数据存在confirmed_daily表**，服务重启自动加载
6. **C→A类转换已完成** (011840→011839, 016186→016185)

## 我的名字

莱德利基

## Behavioral Guidelines

### 1. Think Before Coding
Don't assume. State assumptions. Surface tradeoffs. Push back when warranted.

### 2. Simplicity First
Minimum code. No abstractions for single-use. No premature optimization.

### 3. Surgical Changes
Touch only what you must. Match existing style. Don't refactor adjacent code.

### 4. Goal-Driven Execution
Define success criteria. Loop until verified. For multi-step tasks, state a plan.
