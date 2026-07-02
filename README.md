# 量化交易系统

> Python + Next.js 全栈量化交易平台 · 25 策略信号 · ML 增强 · Web 实时监控

---

## 系统架构

```
                        ┌─────────────────┐
                        │   Web 终端 (Next.js)  │
                        │  K线 · 资产 · AI分析   │
                        └────────┬────────┘
                                 │ WebSocket
              ┌──────────────────┼──────────────────┐
              │                  │                  │
        策略引擎            风控引擎            执行层
    ┌─────┴─────┐      ┌─────┴─────┐      ┌─────┴─────┐
    │ 轮动策略    │      │ 熔断机制    │      │ 订单管理    │
    │ 投票集成    │      │ 规则校验    │      │ 持仓跟踪    │
    │ 动态权重    │      │ 风险敞口    │      │ 交易日志    │
    └─────┬─────┘      └─────┬─────┘      └───────────┘
          │                  │
          └────────┬─────────┘
                   ↓
            信号采集层
    ┌──────────────┼──────────────┐
    │              │              │
  技术指标       ML 模型        资金流
    │              │              │
  MACD/RSI    LightGBM        SmartMoney
  Bollinger   CatBoost        QRS
  MA/KDJ      LSTM            VolumeDist
  Alligator   TFT              MoneyFlow
  Donchian    EnsembleVoting
  RSRS
```

## 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| 后端 | Python | 数据采集、策略计算、风控、订单管理 |
| 数据库 | SQLite | 本地持久化，股票/ETF/基金/信号历史 |
| ML | LightGBM · CatBoost · LSTM | 已训练模型文件，用于信号评分 |
| 前端 | Next.js · TypeScript | SPA，WebSocket 实时推送 |
| 终端 | Recharts · WebSocket | K线图表、资产面板、AI 分析、策略健康 |

## 核心模块

### 信号采集 (`signals/` · 25 个模块)

| 类别 | 策略 | 说明 |
|------|------|------|
| 趋势跟踪 | MACD, MA Cross, Alligator | 多周期趋势识别 |
| 超买超卖 | RSI, KDJ, Bollinger | 反转信号 |
| 突破 | Donchian, RSRS | 支撑阻力突破 |
| ML 评分 | LightGBM Scorer, CatBoost Scorer | 模型预测评分 |
| 深度学习 | LSTM Forecast, TFT Forecast | 时序预测 |
| 资金流 | Smart Money, Money Flow, QRS | 主力资金跟踪 |
| 轮动 | Rotation, Rotation Classic, Rotation LS | 板块/风格轮动 |
| 集成 | Ensemble Voting | 多信号投票融合 |

### 策略引擎 (`strategy/`)

- **Engine** — 核心策略引擎，信号→决策
- **ETF Engine** — 专门优化的 ETF 策略执行
- **Optimizer** — 策略参数优化器
- **Health** — 策略运行健康检查

### 风控引擎 (`risk_engine/`)

- **Circuit Breaker** — 多级熔断（单日跌幅/连续亏损/波动率）
- **Rules** — 可配置风控规则（仓位上限/行业集中度/流动性门槛）

### 运行时 (`runtime/`)

- **Market Clock** — A 股交易时间管理
- **Runtime Loop** — 主循环：采集→信号→决策→执行
- **State Checker** — 系统状态检查与告警
- **Recovery** — 异常恢复机制

### AI 分析 (`agents/`)

- **Macro Agent** — 宏观面分析
- **Sentiment Agent** — 市场情绪分析
- **Stock Agent** — 个股深度分析

### Web 终端 (`terminal/` · 22 个组件)

| 组件 | 功能 |
|------|------|
| KLineChart | 交互式 K 线图 |
| AssetOverview | 资产总览面板 |
| AIAnalysis | AI 分析面板 |
| PortfolioTable | 持仓明细表 |
| TradePanel | 交易操作面板 |
| StatusBar | 系统运行状态 |
| StrategyHealth | 策略健康评分 |
| OptimizerPage | 参数优化界面 |
| DailyReport | 日度报告 |
| FundRealtime | 基金实时估值 |
| ConfirmPanel | 操作二次确认 |
| Sidebar | 导航侧栏 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python db.py

# 启动后端
python main.py

# 启动前端（新终端）
cd terminal && npm install && npm run dev
```

## 项目统计

| 指标 | 数据 |
|------|------|
| 总代码文件 | 94 |
| 策略信号 | 25 |
| 前端组件 | 16 |
| ML 模型 | 3（LightGBM/CatBoost/LSTM） |
| 数据覆盖 | 40+ 股票/ETF/基金 |

## 技术特性

- **ML 增强信号**：LightGBM/CatBoost 评分 + LSTM/TFT 时序预测
- **集成投票机制**：多信号融合决策，降低单一策略噪声
- **多级风控**：熔断 + 仓位上限 + 行业集中度 + 流动性门槛
- **实时 Web 终端**：WebSocket 推送，无需刷新
- **AI 分析面板**：大模型驱动的市场/个股分析

## 许可

MIT License
