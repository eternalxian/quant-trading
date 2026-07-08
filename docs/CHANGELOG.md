# CHANGELOG

## P4-1-candidate (2026-07-08) — 组合模拟核心

- 新增独立 `simulation/` 纯计算层，不修改 `calc_portfolio()` 收益口径。
- 支持当前基金目标权重、目标现金、调仓差额、单边换手率、最大权重和 HHI 对比。
- 使用 Decimal 分币计算和确定性尾差调和，保证资产守恒和输入不可变。
- 新增 19 项模拟测试；既有系统 22 项测试及前端 build 保持通过。
- 无 API、无前端、无数据库写入、无策略/回测/真实交易。

## v3.5.1-stable (2026-07-08) — P3.6.1-R4 稳定性门禁通过

### R4 修复
- WebSocket 快照计算移出事件循环，改为按需 single-flight 后台任务。
- 30 秒缓存 + stale-while-revalidate；首次无缓存最多等待 5 秒并安全降级。
- 主线程仅预加载数据模块，不在启动阶段执行市场/组合重计算。
- Windows 下所有 AKShare 调用增加进程级串行保护，修复 py_mini_racer 并发初始化导致的进程崩溃。
- 路由门禁改为真实计数，覆盖 backup/backups/restore/self-check/exposure/kline。
- 测试扩展至 22 项：双 WebSocket、HTTP 并发、single-flight、缓存发布、异常降级、重复 benchmark 与进程存活。
- Chromium 实际回归通过：014319、005698 QDII、关闭重开、真实 WebSocket ping、Console/Network。

### 门禁结果
- `python tests/test_system.py`: 22 passed, 0 failed。
- `npm run build`: exit 0。
- 正式三库在 Codex 接管执行前后哈希不变。

## v3.5.1-stable-candidate (2026-07-07) — R2 返修完成

### R2 修复
- self-check: 仅本地SQL+表检查+模块导入，无外部请求，2.1s
- kline 404: 无效基金代码返回 HTTP 404 + error字段
- backup POST: 路由装饰器恢复
- data_quality: 恢复duplicate_holdings/negative_value/holdings_count/advice_count
- 重复路由: 清理backup/backups/restore/health重复定义
- 测试: 父进程隔离+子进程测试，16/0，无需改正式DB
- 基金图表: FundDetails双effect+6状态，旧FundKline移除
- 文档: 版本统一3.5.1

### R0-R1 修复
- self-check无副作用：移除get_strategy_advices()和calc_portfolio()
- 主题暴露前端接线：ExposureCard组件
- 单基金K线前端接线：selectedFund+FundDetails
- kline无效代码404契约

## v3.5.0-stable (2026-07-07) — 稳定版基线

### P0-P3 完成
- 数据库三库隔离
- 18个API端点+WebSocket
- 前端8层决策页面
- 决策闭环(建议/告警/复盘/导出)
- 系统可靠性(备份/自检/审计/测试)

### 当前不包含
- 完整回测引擎、完整策略引擎、自动交易、全球市场、AI流式、多用户
