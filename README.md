# 基金组合分析与决策辅助系统

一个用于个人基金组合监控、风险分析、策略建议与每日复盘的 AI 协作项目。当前稳定基线为 `v3.5.1-stable`，另包含尚未接入 API/前端的 `P4-1` 目标仓位模拟模块。

> 本仓库只包含源码、公开行情缓存和合成演示数据，不包含真实持仓、交易、资产金额、日志、备份或密钥。系统不构成投资建议，也不提供自动实盘交易或收益承诺。

## 已实现能力

- Next.js 前端 + FastAPI 服务，当前代码包含 40 个 HTTP 接口与 1 个 WebSocket 实时通道。
- 生产、分析、参考三库隔离，分别承载资产记录、分析结果与外部参考数据。
- 组合收益、年化波动率、Sharpe、Calmar、VaR 95/99、Beta/Alpha、最大回撤、基准比较和归因分析。
- 风险预警、策略建议、人工确认、历史状态、每日复盘和报告导出的决策辅助闭环。
- 30 秒缓存、单航班刷新、陈旧缓存可用和数据源降级，降低并发刷新对服务的影响。
- P4-1 目标权重只读模拟：目标金额、调仓差额、单边换手率、最大权重、HHI 集中度和资产守恒校验。

## 项目边界

- 当前不是自动交易平台，不会连接券商下单。
- 当前没有完整策略引擎、完整回测引擎、费用/滑点模型或多用户权限。
- AI仅用于解释和补充分析视角，风险规则和金额计算采用确定性逻辑。
- P4-1 目前是独立纯计算模块，尚未接入 API、数据库写入或前端界面。

## 脱敏说明

公开版主动排除了：

- `production.db`、`analytics.db`、`reference.db` 及任何备份；
- 真实持仓、份额、成本、现金、交易与确认记录；
- 运行日志、调试证据、研究过程目录和本机构建缓存；
- API 密钥、Token、个人账号及本机路径。

如需演示，请先运行 `python scripts/init_demo_data.py`，该脚本只生成明确标记的合成数据。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\init_demo_data.py
cd terminal
npm install
npm run build
cd ..
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

另开终端运行前端：

```powershell
cd terminal
npm run dev
```

后端健康检查：`http://127.0.0.1:8000/api/health`

## 验证

```powershell
python -m unittest tests.test_simulation -v
python tests\test_system.py
cd terminal
npm run build
```

- 19 项仓位模拟单元测试覆盖输入边界、金额舍入、换手率、集中度和资产守恒。
- 内部稳定基线完成 22 项系统验证，覆盖 HTTP、写入闭环、双 WebSocket、并发、缓存发布和降级路径。

更多说明见 [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) 与 [`docs/SIMULATION.md`](docs/SIMULATION.md)。

