# 量化交易系统

> Python + Next.js 全栈量化交易平台 · 多策略信号 · ML 增强 · Web 实时监控

---

## 架构

```
                    信号采集层
    ┌──────────────────┼──────────────────┐
    │  技术指标         ML 模型            资金流
    │  MACD/RSI/KDJ    LightGBM/CatBoost   Smart Money
    │  Bollinger/MA     LSTM/TFT            QRS
    └──────────────────┼──────────────────┘
                       ↓
                    策略引擎
           轮动策略 · 投票集成 · 动态权重
                       ↓
              ┌───────┴───────┐
           风控引擎         执行层
       熔断 · 规则校验    订单管理 · 持仓
              └───────┬───────┘
                      ↓
                 Web 终端 (Next.js)
           K线 · 资产概览 · AI 分析 · 实时状态
```

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python + SQLite + Pandas |
| ML | LightGBM / CatBoost / LSTM |
| 前端 | Next.js + TypeScript + WebSocket |
| 终端 | K 线图表 / 资产面板 / AI 分析 / 策略健康 |

## 模块

| 模块 | 文件数 | 功能 |
|------|:--:|------|
| `signals/` | 25 | 技术指标 + ML 评分 + 资金流 + 投票集成 |
| `strategy/` | 5 | 策略引擎、ETF 引擎、优化器、健康检查 |
| `risk_engine/` | 3 | 熔断、规则校验 |
| `runtime/` | 5 | 市场时钟、状态检查、运行时循环、恢复 |
| `agents/` | 5 | 宏观/情绪/股票分析 Agent |
| `terminal/` | 22 | Next.js Web 前端组件 |

## 运行

```bash
python main.py        # 启动后端
cd terminal && npm run dev  # 启动前端
```

## 许可

MIT License
