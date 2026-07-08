# 数据库说明 v3.5.1-stable

## 架构

三库隔离:

```
data/
├── production.db     ← 真金白银 (不可删除, 必须备份)
├── analytics.db      ← 分析数据 (可重建, 建议备份)
└── reference.db      ← 参考数据 (可重建, 不必频繁备份)
```

## production.db

**重要性: 🔴 核心数据 — 不可删除, 每次备份必含**

| 表名 | 用途 | 备份 |
|------|------|------|
| holdings | 持仓份额/成本 | ✅ 必须 |
| transactions | 交易流水 | ✅ 必须 |
| cash_balance | 余额宝余额 | ✅ 必须 |
| pending_buys | 待确认申购 | ✅ 必须 |
| dca_log | 定投记录 | ✅ 必须 |
| confirmed_daily | 每日确认汇总 | ✅ 必须 |
| confirmed_funds | 基金市值确认历史 | ✅ 必须 |
| known_nav | QDII手动净值 | ⚠️ 可选 |

## analytics.db

**重要性: 🟡 分析数据 — 可重建, 建议备份**

| 表名 | 用途 | 备份 | 新增于 |
|------|------|------|--------|
| strategy_signals | 历史信号(弃用) | ❌ | P0 |
| strategy_health_log | 策略健康度 | ❌ | P0 |
| execution_log | 执行日志 | ⚠️ | P0 |
| strategy_signals | 历史信号(弃用) | ❌ | P0 |
| strategy_performance | 策略绩效(弃用) | ❌ | P0 |
| strategy_health_log | 策略健康度 | ❌ | P0 |
| execution_log | 执行日志 | ⚠️ | P0 |
| advice_log | 策略建议闭环 | ✅ | P2 |
| alert_log | 告警闭环 | ✅ | P2 |
| audit_log | 审计日志 | ✅ | P3 |

## reference.db

**重要性: 🟢 参考数据 — 可重建**

| 表名 | 用途 | 备份 |
|------|------|------|
| strategies | 策略定义 | ⚠️ |

## 备份恢复

- `POST /api/system/backup` — 创建备份（保留最近30个）
- `GET /api/system/backups` — 备份列表
- `POST /api/system/restore/{id}` — 恢复备份（恢复前自动备份当前）
