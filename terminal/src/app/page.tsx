"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import StatusBar from "@/components/StatusBar";
import { Maximize2, Minimize2, TrendingUp, TrendingDown, Shield, Activity, BarChart3, Clock, AlertTriangle, Wifi, WifiOff, Zap, Info, ArrowRight, PieChart } from "lucide-react";
import { getPortfolio, getAIAnalysis, getAttribution, getHistory, getPeriods, getCompare, getAdvices, type PortfolioData, type AIData, type AttributionData, type CompareData, type AdviceItem, type WSAlert } from "@/lib/api";

const LazyMarketPage = dynamic(() => import("@/components/Pages").then(m => ({ default: m.MarketPage })), { ssr: false });
const LazyPortfolioPage = dynamic(() => import("@/components/Pages").then(m => ({ default: m.PortfolioPage })), { ssr: false });
const LazyRiskPage = dynamic(() => import("@/components/Pages").then(m => ({ default: m.RiskPage })), { ssr: false });
const LazyAIPage = dynamic(() => import("@/components/Pages").then(m => ({ default: m.AIPage })), { ssr: false });
const TransactionLog = dynamic(() => import("@/components/TransactionLog"), { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SRC_BADGE: Record<string, string> = { alipay: "支付宝", manual: "手动" };

// ── 告警规则中英对照 ──
const ALERT_CN: Record<string, string> = { stale_nav: "净值过期", consecutive_down: "连续下跌", drawdown: "大幅回撤", daily_crash: "单日暴跌", concentration_high: "集中度过高", stop_loss: "止损触发", data_source_degraded: "数据源降级" };

export default function Home() {
  const [page, setPage] = useState("概览");
  const [pf, setPf] = useState<PortfolioData | null>(null);
  const [ai, setAi] = useState<AIData | null>(null);
  const [attr, setAttr] = useState<AttributionData | null>(null);
  const [periods, setPeriods] = useState<Record<string, number> | null>(null);
  const [compare, setCompare] = useState<CompareData | null>(null);
  const [advices, setAdvices] = useState<AdviceItem[] | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<WSAlert[]>([]);
  const [wsStatus, setWsStatus] = useState<"connected" | "disconnected">("disconnected");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"value" | "pl" | "weight">("weight");
  const [selectedFund, setSelectedFund] = useState<{code:string;name:string} | null>(null);

  useEffect(() => {
    getPortfolio().then(setPf).catch(() => setPf(null));
    getAIAnalysis().then(setAi).catch(() => {});
    getAttribution().then(setAttr).catch(() => setAttr(null));
    getPeriods().then(d => setPeriods(d.periods)).catch(() => setPeriods(null));
    getCompare(365).then(setCompare).catch(() => setCompare(null));
    getAdvices().then(d => setAdvices(d.advices)).catch(() => setAdvices(null));
    getHistory(90).then(d => setHistory(d.data || [])).catch(() => {});
  }, []);

  // WebSocket
  useEffect(() => {
    let ws: WebSocket | null = null; let pingId: any = null; let reconnectId: any = null;
    function connect() {
      try {
        ws = new WebSocket((process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000") + "/ws/realtime");
        ws.onopen = () => { setWsStatus("connected"); pingId = setInterval(() => ws?.send("ping"), 30000); };
        ws.onmessage = (e) => {
          try {
            const d = JSON.parse(e.data);
            if (d.alerts?.length) {
              setAlerts(prev => {
                const seen = new Set(prev.map(a => a.code + a.title));
                const merged = [...d.alerts.filter((a: WSAlert) => !seen.has(a.code + a.title)), ...prev].slice(0, 8);
                return merged;
              });
            }
          } catch {}
        };
        ws.onclose = () => { setWsStatus("disconnected"); clearInterval(pingId); reconnectId = setTimeout(connect, 10000); };
        ws.onerror = () => ws?.close();
      } catch { reconnectId = setTimeout(connect, 10000); }
    }
    connect();
    return () => { ws?.close(); clearInterval(pingId); clearTimeout(reconnectId); };
  }, []);

  const fundCount = pf?.funds.filter(f => f.value > 0).length ?? 0;
  const maxWeight = pf ? Math.max(...pf.funds.filter(f => f.value > 0).map(f => f.weight || 0)) : 0;
  const rawFunds = (pf?.funds || []).filter((f: any) => f.value > 0);
  const tableSorted = [...rawFunds].sort((a: any, b: any) => sortBy === "value" ? b.value - a.value : sortBy === "pl" ? b.pl - a.pl : b.weight - a.weight);
  const baseDate = pf?.base_date || "";
  const isAI = ai?.analysis && !ai.analysis.includes("离线") && !ai.analysis.includes("Ollama");

  const fmtN = (v?: number | null, p = "", s = "") => v != null ? `${p}${Math.abs(v) < 1000 ? v.toFixed(v % 1 === 0 ? 0 : 2) : v.toLocaleString("en-US", { maximumFractionDigits: 0 })}${s}` : "暂无";
  const riskClr = (v?: number | null, d = -20, w = -5) => v == null ? "text-[#64748B]" : v <= d ? "text-[#EF4444]" : v <= w ? "text-[#F59E0B]" : "text-[#22C55E]";

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#020617]">
      <StatusBar portfolioTotal={pf?.total} portfolioPL={pf?.total_pl} portfolioPLPct={pf?.total_pl_pct} yesterdayPL={pf?.yesterday_pl} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar active={page} onNavigate={setPage} />
        <main className="flex-1 overflow-auto p-4 space-y-3">
          {page === "概览" && (
            <>
              {/* critical toast */}
              {alerts.filter(a => a.level === "critical").slice(0, 1).map((a, i) => (
                <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.2)] text-[11px] text-[#EF4444]">
                  <AlertTriangle size={14} /> {ALERT_CN[a.title] || a.title}: {a.message}
                </div>
              ))}

              {/* 第一层：总览卡片 */}
              <div className="grid grid-cols-3 md:grid-cols-7 gap-2">
                <MCard label="总资产" v={fmtN(pf?.total, "¥")} />
                <MCard label="累计盈亏" v={fmtN(pf?.total_pl, "¥")} c={pf?.total_pl != null ? (pf.total_pl >= 0 ? "text-[#22C55E]" : "text-[#EF4444]") : ""} />
                <MCard label="累计收益率" v={pf?.total_pl_pct != null ? `${pf.total_pl_pct >= 0 ? "+" : ""}${pf.total_pl_pct.toFixed(2)}%` : "暂无"} c={pf?.total_pl_pct != null ? (pf.total_pl_pct >= 0 ? "text-[#22C55E]" : "text-[#EF4444]") : "text-[#64748B]"} />
                <MCard label="年化(~1年)" v={pf?.annual_return != null ? `${pf.annual_return >= 0 ? "+" : ""}${pf.annual_return.toFixed(1)}%` : "暂无"} c={pf?.annual_return != null ? (pf.annual_return >= 0 ? "text-[#22C55E]" : "text-[#EF4444]") : "text-[#64748B]"} />
                <MCard label="基金数" v={`${fundCount}只`} />
                <MCard label="仓位" v="100%" />
                <MCard label="WS" v={wsStatus} c={wsStatus === "connected" ? "text-[#22C55E]" : "text-[#EF4444]"} i={wsStatus === "connected" ? <Wifi size={10} className="text-[#22C55E] mr-1" /> : <WifiOff size={10} className="text-[#EF4444] mr-1" />} />
              </div>

              {/* 第二层：风险质量 + 基准对比 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* 风险质量 — 修复排版 */}
                <Sect title="风险质量" icon={<Shield size={14} />} ic="text-[#F59E0B]">
                  <div className="space-y-1.5 text-[11px]">
                    <Row label="最大回撤" value={`${pf?.max_dd?.toFixed(1) || "暂无"}%`} color={riskClr(pf?.max_dd, -20, -10)} />
                    <Row label="年化波动率" value={`${pf?.volatility?.toFixed(1) || "暂无"}%`} color="text-[#E2E8F0]" />
                    <Row label="夏普比率" value={pf?.sharpe?.toFixed(2) || "暂无"} />
                    <Row label="Calmar 比率" value={pf?.calmar?.toFixed(2) || "暂无"} />
                    <Row label="VaR (95%)" value={`${pf?.var_95?.toFixed(2) || "暂无"}%`} color="text-[#F59E0B]" />
                    <Row label="Beta" value={pf?.beta?.toFixed(2) || "暂无"} color={pf?.beta != null ? (pf.beta > 1.5 ? "text-[#F59E0B]" : "text-[#E2E8F0]") : "text-[#64748B]"} />
                  </div>
                </Sect>

                {/* 基准对比 — 增强版 */}
                <Sect title="基准对比：组合 vs 沪深300" icon={<Activity size={14} />} ic="text-[#3B82F6]">
                  {compare?.summary ? (
                    <div>
                      <div className="space-y-1.5 text-[11px]">
                        <Row label="组合收益" value={`${compare.summary.portfolio?.cumulative_return >= 0 ? "+" : ""}${compare.summary.portfolio?.cumulative_return?.toFixed(1)}%`} color={compare.summary.portfolio?.cumulative_return >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"} big />
                        <Row label="沪深300" value={`${compare.summary.benchmark?.cumulative_return >= 0 ? "+" : ""}${compare.summary.benchmark?.cumulative_return?.toFixed(1)}%`} color={compare.summary.benchmark?.cumulative_return >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"} />
                        <Row label="超额收益" value={`${compare.summary.excess_return_pct >= 0 ? "+" : ""}${compare.summary.excess_return_pct?.toFixed(1)}%`} color={compare.summary.excess_return_pct >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"} big />
                        <Row label="组合最大回撤" value={`${compare.summary.portfolio?.max_drawdown?.toFixed(1)}%`} color="text-[#F59E0B]" />
                        <Row label="基准最大回撤" value={`${compare.summary.benchmark?.max_drawdown?.toFixed(1)}%`} color="text-[#F59E0B]" />
                        <Row label="组合夏普" value={compare.summary.portfolio?.sharpe?.toFixed(2) || "暂无"} />
                      </div>
                      {(() => {
                        const ex = compare.summary.excess_return_pct;
                        const comboDD = compare.summary.portfolio?.max_drawdown;
                        const benchDD = compare.summary.benchmark?.max_drawdown;
                        let desc = "";
                        if (ex > 10) desc = "组合显著跑赢沪深300";
                        else if (ex > 0) desc = "组合小幅跑赢沪深300";
                        else desc = "组合跑输沪深300";
                        if (comboDD != null && benchDD != null && Math.abs(comboDD) > Math.abs(benchDD)) desc += "，但回撤大于基准，说明收益弹性强但波动风险也更高";
                        else desc += "，风险控制良好";
                        return <p className="text-[10px] text-[#64748B] mt-2 italic">{desc}。</p>;
                      })()}
                    </div>
                  ) : <Emp text="基准对比暂不可用" />}
                </Sect>
              </div>

              {/* 主题暴露 */}
              <ExposureCard />

              {/* 第三层：策略建议 — 卡片化 */}
              <Sect title="策略建议" icon={<Zap size={14} />} ic="text-[#8B5CF6]">
                {advices === null ? <Emp text="策略建议暂不可用" /> : advices.length === 0 ? <Emp text="暂无策略建议" /> : (
                  <div className="space-y-2">
                    {advices.slice(0, 3).map((a, i) => (
                      <div key={i} className={`p-3 rounded-lg border text-[11px] ${a.risk === "high" ? "bg-[rgba(239,68,68,0.04)] border-[rgba(239,68,68,0.15)]" : a.risk === "medium" ? "bg-[rgba(245,158,11,0.04)] border-[rgba(245,158,11,0.15)]" : "bg-[rgba(59,130,246,0.04)] border-[rgba(59,130,246,0.15)]"}`}>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${a.risk === "high" ? "bg-[rgba(239,68,68,0.15)] text-[#EF4444]" : a.risk === "medium" ? "bg-[rgba(245,158,11,0.15)] text-[#F59E0B]" : "bg-[rgba(59,130,246,0.15)] text-[#3B82F6]"}`}>{a.action}</span>
                          {a.name && <span className="text-[#E2E8F0] font-medium">{a.name}</span>}
                          <span className={`text-[9px] ml-auto ${a.risk === "high" ? "text-[#EF4444]" : "text-[#94A3B8]"}`}>置信度 {a.confidence}%</span>
                        </div>
                        <div className="space-y-1 text-[#94A3B8]">
                          <div className="flex items-start gap-1"><Info size={10} className="shrink-0 mt-0.5 text-[#64748B]" /><span>{a.reason}</span></div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Sect>

              {/* 第四层：风险告警 — 中文化 + 去重 */}
              {alerts.length > 0 && (
                <Sect title="风险告警" icon={<AlertTriangle size={14} />} ic="text-[#EF4444]">
                  <div className="space-y-1 max-h-[180px] overflow-auto">
                    {alerts.sort((a, b) => (a.level === "critical" ? -1 : 1) - (b.level === "critical" ? -1 : 1)).map((a, i) => (
                      <div key={i} className={`flex items-start gap-2 text-[10px] p-1.5 rounded ${a.level === "critical" ? "bg-[rgba(239,68,68,0.06)]" : a.level === "warn" ? "bg-[rgba(245,158,11,0.06)]" : ""}`}>
                        <span className={`shrink-0 mt-0.5 text-[9px] px-1 rounded font-mono ${a.level === "critical" ? "bg-[rgba(239,68,68,0.15)] text-[#EF4444]" : a.level === "warn" ? "bg-[rgba(245,158,11,0.15)] text-[#F59E0B]" : "text-[#94A3B8]"}`}>{ALERT_CN[a.title] || a.title}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-[#E2E8F0]">{a.message}</p>
                          <p className="text-[#64748B] text-[9px]">{a.created_at?.slice(11, 16)} · {a.code}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Sect>
              )}

              {/* 第五层：收益归因 + 多周期 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Sect title="收益归因" icon={<TrendingUp size={14} />} ic="text-[#22C55E]">
                  {attr === null ? <Emp text="收益归因暂不可用" /> : (
                    <div>
                      {attr.top_gainers?.length > 0 && <>
                        <p className="text-[9px] text-[#22C55E] mb-1">📈 主要盈利</p>
                        {attr.top_gainers.map((f, i) => (
                          <div key={i} className="flex items-center justify-between text-[10px] py-0.5"><span className="text-[#E2E8F0] truncate max-w-[100px]">{f.name.slice(0, 10)}</span><span className="text-[#EF4444] font-mono">+{f.pl.toFixed(0)} ({f.weight}%)</span></div>
                        ))}
                      </>}
                      {attr.top_losers?.length > 0 && <>
                        <p className="text-[9px] text-[#22C55E] mb-1 mt-1.5">📉 主要拖累</p>
                        {attr.top_losers.map((f, i) => (
                          <div key={i} className="flex items-center justify-between text-[10px] py-0.5"><span className="text-[#E2E8F0] truncate max-w-[100px]">{f.name.slice(0, 10)}</span><span className="text-[#22C55E] font-mono">{f.pl.toFixed(0)} ({f.weight}%)</span></div>
                        ))}
                      </>}
                      {attr.top_gainers?.[0]?.weight > 50 && (
                        <p className="text-[10px] text-[#F59E0B] mt-2">⚠ 收益高度集中于 {attr.top_gainers[0].name.slice(0, 8)}（占比 {attr.top_gainers[0].weight}%），存在单一基金依赖风险。</p>
                      )}
                    </div>
                  )}
                </Sect>

                <Sect title="周期表现" icon={<Clock size={14} />} ic="text-[#3B82F6]">
                  {periods === null ? <Emp text="周期数据暂不可用" /> : (
                    <>
                      <div className="grid grid-cols-3 gap-1.5 text-[10px]">
                        {Object.entries(periods).map(([k, v]) => (
                          <div key={k} className="text-center p-1.5 rounded bg-[rgba(8,18,37,0.6)]">
                            <div className="text-[#64748B]">{k}</div>
                            <div className={`font-mono font-semibold ${v >= 0 ? "text-[#EF4444]" : "text-[#22C55E]"}`}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</div>
                          </div>
                        ))}
                      </div>
                      <p className="text-[8px] text-[#475569] mt-1.5">* 基于组合净值曲线计算，不等同于持仓累计盈亏</p>
                    </>
                  )}
                </Sect>
              </div>

              {/* 第六层：组合净值曲线 */}
              {history.length > 0 && (
                <ExpandModule title="📈 组合净值走势" subtitle={`近90天 · 截至 ${history[history.length-1]?.date || "—"}`} id="nav" expanded={expanded} onToggle={setExpanded}>
                  <div id="portfolio-nav-chart" style={{ height: 200 }} />
                </ExpandModule>
              )}

              {/* 第七层：持仓明细表 */}
              <Sect title="持仓明细" icon={<BarChart3 size={14} />} ic="text-[#3B82F6]" sub={`${fundCount}只 · 基准日 ${baseDate}`}>
                <div className="flex items-center text-[10px] text-[#64748B] py-1.5 border-b border-[rgba(59,130,246,0.08)] mb-1">
                  <span className="w-14 shrink-0 font-mono">代码</span>
                  <span className="flex-1 min-w-0">名称</span>
                  <span onClick={() => setSortBy("value")} className={`w-14 text-right font-mono cursor-pointer ${sortBy === "value" ? "text-[#3B82F6]" : ""}`}>金额{sortBy === "value" ? " ▾" : ""}</span>
                  <span onClick={() => setSortBy("pl")} className={`w-14 text-right font-mono cursor-pointer ${sortBy === "pl" ? "text-[#3B82F6]" : ""}`}>收益{sortBy === "pl" ? " ▾" : ""}</span>
                  <span onClick={() => setSortBy("weight")} className={`w-10 text-right font-mono cursor-pointer ${sortBy === "weight" ? "text-[#3B82F6]" : ""}`}>%{sortBy === "weight" ? " ▾" : ""}</span>
                </div>
                {tableSorted.map((f: any, i: number) => {
                  const riskTag = f.weight > 40 ? "高" : f.weight > 25 ? "中" : "";
                  return (
                    <div key={i} onClick={() => setSelectedFund(selectedFund?.code===f.code?null:{code:f.code,name:f.name})}
                      className={`flex items-center text-[11px] py-1.5 cursor-pointer border-b border-[rgba(59,130,246,0.04)] hover:bg-[rgba(59,130,246,0.03)] ${selectedFund?.code===f.code?"bg-[rgba(59,130,246,0.08)]":""}`}>
                      <span className="w-14 text-[#94A3B8] font-mono">{f.code}</span>
                      <span className="flex-1 text-[#E2E8F0] truncate">{f.name}<span className="text-[9px] ml-1 px-1 rounded bg-[rgba(59,130,246,0.1)] text-[#3B82F6]">{SRC_BADGE[f.source] || "?"}</span></span>
                      <span className="w-14 text-right text-[#E2E8F0] font-mono font-semibold">¥{f.value.toFixed(0)}</span>
                      <span className={`w-14 text-right font-mono font-semibold ${f.pl >= 0 ? "text-[#EF4444]" : "text-[#22C55E]"}`}>{f.pl >= 0 ? "+" : ""}{f.pl.toFixed(0)}</span>
                      <span className="w-10 text-right text-[#64748B] font-mono">{f.weight}%{riskTag && <span className={`text-[8px] ml-0.5 px-0.5 rounded ${riskTag === "高" ? "bg-[rgba(239,68,68,0.1)] text-[#EF4444]" : "bg-[rgba(245,158,11,0.1)] text-[#F59E0B]"}`}>{riskTag}</span>}</span>
                    </div>
                  );
                })}
              </Sect>

              {/* 选中基金K线 */}
              {selectedFund && (
                <Sect title={selectedFund.name} ic="text-[#3B82F6]" sub={selectedFund.code}>
                  <FundDetails code={selectedFund.code} name={selectedFund.name} />
                </Sect>
              )}

              {/* AI 分析 — 结构化 */}
              <div className="glass rounded-xl p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Activity size={14} className="text-[#8B5CF6]" />
                  <span className="text-xs text-[#E2E8F0] font-semibold">AI 分析{!isAI && " · 离线"}</span>
                </div>
                {isAI ? (
                  <p className="text-[11px] text-[#CBD5E1] leading-relaxed">{ai?.analysis}</p>
                ) : (
                  <div className="space-y-2 text-[11px]">
                    <div className="flex items-start gap-2"><span className="text-[#22C55E] shrink-0 mt-0.5">●</span><div><span className="text-[#64748B]">组合结论：</span><span className="text-[#CBD5E1]">当前组合以半导体和 QDII 科技基金为主，总资产 ¥{pf?.total?.toFixed(0)}。</span></div></div>
                    <div className="flex items-start gap-2"><span className="text-[#F59E0B] shrink-0 mt-0.5">●</span><div><span className="text-[#64748B]">主要风险：</span><span className="text-[#CBD5E1]">{pf?.funds?.[0]?.name} 占比 {pf?.funds?.[0]?.weight}%，单一基金集中度偏高。</span></div></div>
                    <div className="flex items-start gap-2"><span className="text-[#3B82F6] shrink-0 mt-0.5">●</span><div><span className="text-[#64748B]">建议：</span><span className="text-[#CBD5E1]">可将第一大持仓降至 30%-40%，增加宽基或低相关资产。</span></div></div>
                    <div className="flex items-start gap-2"><span className="text-[#64748B] shrink-0 mt-0.5">●</span><div><span className="text-[#64748B]">数据状态：</span><span className="text-[#CBD5E1]">基准日 {baseDate || "未确认"}，数据源: 支付宝 + akshare。</span></div></div>
                  </div>
                )}
              </div>
            </>
          )}
          {page === "市场" && <LazyMarketPage />}
          {page === "持仓" && <LazyPortfolioPage />}
          {page === "风险" && <LazyRiskPage />}
          {page === "决策中心" && (
            <div className="space-y-3">
              <Sect title="当前策略建议" icon={<Zap size={14} />} ic="text-[#8B5CF6]" sub={`${advices?.length || 0}条`}>
                {advices?.map((a: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded bg-[rgba(8,18,37,0.6)] mb-1.5 text-[11px]">
                    <div className="flex-1"><span className="font-semibold text-[#E2E8F0]">{a.target_name} - {a.action}</span><p className="text-[#94A3B8] text-[10px]">{a.reason}</p></div>
                    <div className="flex gap-1 ml-2 shrink-0">
                      <button onClick={() => fetch(`${API}/api/strategy/advices/${a.id}/confirm`,{method:"POST"})} className="text-[9px] px-2 py-0.5 rounded bg-[rgba(34,197,94,0.1)] text-[#22C55E]">采纳</button>
                      <button onClick={() => fetch(`${API}/api/strategy/advices/${a.id}/ignore`,{method:"POST"})} className="text-[9px] px-2 py-0.5 rounded bg-[rgba(148,163,184,0.1)] text-[#94A3B8]">忽略</button>
                    </div>
                  </div>
                )) || <Emp text="暂无建议" />}
              </Sect>
            </div>
          )}
          {page === "AI" && <LazyAIPage />}
          {page === "交易记录" && <TransactionLog />}
          <div className="h-4" />
        </main>
      </div>
      <PortfolioNavChartLazy data={history} />
    </div>
  );
}

// ── 子组件 ──
function MCard({ label, v, c = "text-[#E2E8F0]", i }: { label: string; v: string; c?: string; i?: React.ReactNode }) {
  return <div className="glass rounded-xl p-2.5"><p className="text-[10px] text-[#64748B] mb-0.5">{label}</p><p className={`text-xs font-mono font-bold ${c}`}>{i}{v}</p></div>;
}
function Row({ label, value, color = "text-[#E2E8F0]", big }: { label: string; value: string; color?: string; big?: boolean }) {
  return <div className="flex items-center justify-between"><span className="text-[#64748B]">{label}</span><span className={`font-mono text-right ${big ? "font-semibold text-xs" : "text-[11px]"} ${color}`}>{value}</span></div>;
}
function Emp({ text }: { text: string }) { return <div className="text-[10px] text-[#64748B] py-4 text-center">{text}</div>; }
function Sect({ title, icon, ic = "text-[#3B82F6]", sub, children }: { title: string; icon?: React.ReactNode; ic?: string; sub?: string; children: React.ReactNode }) {
  return <div className="glass rounded-xl p-3"><div className="flex items-center gap-2 mb-2">{icon && <span className={ic}>{icon}</span>}<span className="text-[11px] text-[#E2E8F0] font-semibold">{title}</span>{sub && <span className="text-[9px] text-[#64748B] ml-auto">{sub}</span>}</div>{children}</div>;
}
function ExpandModule({ title, subtitle, id, expanded, onToggle, children }: any) {
  const isOpen = expanded === id;
  return <div className={`glass rounded-xl transition-all ${isOpen ? "fixed inset-4 z-50 bg-[#020617] p-4 overflow-auto" : "p-3"}`}>
    <div className="flex items-center justify-between mb-2"><div><span className="text-[11px] text-[#E2E8F0] font-semibold">{title}</span><span className="text-[9px] text-[#64748B] ml-2">{subtitle}</span></div>
    <button onClick={() => onToggle(isOpen ? null : id)} className="text-[#64748B] hover:text-[#94A3B8]">{isOpen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}</button></div>
    <div className={isOpen ? "min-h-[70vh]" : "min-h-[160px] max-h-[240px]"}>{children}</div></div>;
}
function PortfolioNavChartLazy({ data }: { data: any[] }) {
  useEffect(() => {
    if (typeof window === "undefined" || !data.length) return;
    let cancelled = false;
    async function init() {
      const { createChart, ColorType, LineSeries } = await import("lightweight-charts");
      const el = document.getElementById("portfolio-nav-chart");
      if (!el || cancelled) return; el.innerHTML = "";
      const chart = createChart(el, { layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94A3B8" }, grid: { vertLines: { color: "rgba(59,130,246,0.06)" }, horzLines: { color: "rgba(59,130,246,0.06)" } }, rightPriceScale: { borderColor: "rgba(59,130,246,0.15)" }, timeScale: { borderColor: "rgba(59,130,246,0.15)" }, width: el.clientWidth, height: 200 });
      const line = chart.addSeries(LineSeries, { color: "#3B82F6", lineWidth: 2 });
      line.setData(data.map((d: any) => ({ time: d.date, value: d.value })));
      chart.timeScale().fitContent();
    }
    init(); return () => { cancelled = true; };
  }, [data]);
  return null;
}

function ExposureCard() {
  const [d, setD] = useState<any>(null);
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/portfolio/exposure`)
      .then(r => r.json()).then(setD).catch(() => setD(null));
  }, []);
  if (!d) return <Emp text="主题暴露暂不可用" />;
  return (
    <Sect title="主题暴露" icon={<PieChart size={14} />} ic="text-[#8B5CF6]">
      {(d.theme_exposure || []).map((t: any, i: number) => (
        <div key={i} className="flex items-center justify-between text-[10px] py-1">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-[#E2E8F0] w-14">{t.theme}</span>
            <div className="flex-1 h-1.5 rounded-full bg-[rgba(59,130,246,0.06)]">
              <div className={`h-full rounded-full ${t.risk === "high" ? "bg-[#F59E0B]" : "bg-[#3B82F6]"}`} style={{ width: `${Math.min(t.weight, 100)}%` }} />
            </div>
          </div>
          <span className={`font-mono ml-2 ${t.risk === "high" ? "text-[#F59E0B] font-semibold" : "text-[#64748B]"}`}>{t.weight}%</span>
        </div>
      ))}
      {(d.warnings || []).map((w: string, i: number) => (
        <p key={i} className="text-[9px] text-[#F59E0B] mt-1.5">⚠ {w}</p>
      ))}
    </Sect>
  );
}



const FundDetails = dynamic(() => import("@/components/FundDetails"), { ssr: false });

// FundDetails replaced by import
