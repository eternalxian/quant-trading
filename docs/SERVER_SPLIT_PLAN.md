# Server.py 渐进拆分计划 v1.1

> 版本: v3.5.1-stable-candidate | 仅设计文档 | 未实施

## 目标结构

```
server.py          → 仅保留应用装配 (FastAPI init, CORS, TTL cache, _js)
routers/           → HTTP路由、参数解析、响应组装
  ├── portfolio.py
  ├── system.py
  ├── strategy.py
  ├── alerts.py
  └── reports.py
services/          → 业务编排、纯计算
repositories/      → 数据库访问层
```

## 推荐拆分顺序

### Phase 1: 只读系统服务
- `routers/system.py`: health, self-check, backups, audit（已验证无副作用）
- `services/system_service.py` (可选)

### Phase 2: 只读查询
- `routers/fund.py`: kline, exposure（前端已接线）
- `routers/market.py`: market, global

### Phase 3: Analytics 状态服务
- `routers/strategy.py`: advices, confirm, ignore, done, history
- `routers/alerts.py`: alerts, ack, resolve, mute, history

### Phase 4: 报告与备份
- `routers/reports.py`: daily, export
- backup路由保持独立

### Phase 5: Production 写入口
- `routers/portfolio_write.py`: confirm-daily, confirm-funds, set-cash

### Phase 6: /api/portfolio (最后拆)
- 核心依赖最多，风险最高

## 暂不能动

| 组件 | 原因 |
|------|------|
| `calc_portfolio()` | 核心逻辑 |
| `/api/portfolio` 响应结构 | 前端全部依赖 |
| `_js` 序列化 | 所有端点共用 |
| TTL 缓存 | 性能关键路径 |
| 三库路径 + production schema | 数据库完整性 |
| WebSocket 数据结构 | 前端实时依赖 |

## 迁移策略

每阶段:
1. 创建新 router 文件
2. 从 server.py 移动函数
3. 在 server.py 中 import 并注册
4. 运行 test_system.py → 0 failed
5. npm build → exit 0
6. self-check → < 5s

## 回滚方式

- 代码: `git checkout` 恢复
- 数据库: `POST /api/system/restore` 从备份恢复
- 禁止保留注释版旧函数在代码中

## 契约测试

每阶段需验证:
- 响应字段不增删
- HTTP 状态码不变
- TTL 缓存行为一致
