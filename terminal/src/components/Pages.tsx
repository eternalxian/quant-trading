"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import {
  TrendingUp, TrendingDown, Activity, Shield, Zap, Brain,
  BarChart3, PieChart, AlertTriangle, Globe, Layers,
} from "lucide-react";
import {
  getMarket, getSignals, getPortfolio, getStockSpot, getStockSignals,
  getAIAnalysis, getRisk, getHoldings,
  type MarketData, type SignalsData, type PortfolioData,
  type StockSpot, type StockRankItem, type AIData,
} from "@/lib/api";

const fadeIn = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as const },
};

// ═══════════════════ 市场页 ═══════════════════

export function MarketPage() {
  const [data, setData] = useState<MarketData | null>(null);
  useEffect(() => { getMarket().then(setData).catch(() => {}); }, []);

  if (!data) return <Skeleton />;
  return (
    <motion.div {...fadeIn} className="space-y-3">
      <Section title="📈 市场行情" subtitle={data.time} icon={<Globe size={14} className="text-[#3B82F6]" />}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {data.indices.map((idx, i) => (
            <IndexCard key={i} {...idx} />
          ))}
        </div>
      </Section>
      <Section title="📊 ETF 行情" icon={<Activity size={14} className="text-[#22C55E]" />}>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)]">
                <th className="text-left py-2 px-3 font-mono">代码</th>
                <th className="text-left py-2 px-3">名称</th>
                <th className="text-right py-2 px-3 font-mono">现价</th>
                <th className="text-right py-2 px-3 font-mono">涨跌</th>
              </tr>
            </thead>
            <tbody>
              {data.etfs.map((etf, i) => (
                <tr key={i} className="hover:bg-[rgba(59,130,246,0.04)] transition-colors">
                  <td className="py-2 px-3 font-mono text-[#94A3B8]">{etf.code}</td>
                  <td className="py-2 px-3 text-[#E2E8F0]">{etf.name}</td>
                  <td className="py-2 px-3 font-mono text-right">{etf.price?.toFixed(3) || "—"}</td>
                  <td className={`py-2 px-3 font-mono text-right ${(etf.change_pct ?? 0) >= 0 ? "text-profit" : "text-loss"}`}>
                    {(etf.change_pct ?? 0) >= 0 ? "+" : ""}{etf.change_pct?.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </motion.div>
  );
}

function IndexCard({ name, price, change }: { name: string; price: number; change: string }) {
  const isUp = !change.startsWith("-");
  return (
    <div className="glass rounded-xl p-4 hover:scale-[1.02] transition-transform">
      <p className="text-[11px] text-[#94A3B8] mb-1">{name}</p>
      <p className="text-lg font-mono font-bold text-[#E2E8F0]">{price?.toLocaleString()}</p>
      <p className={`text-xs font-mono mt-1 ${isUp ? "text-profit" : "text-loss"}`}>
        {isUp ? <TrendingUp size={12} className="inline mr-1" /> : <TrendingDown size={12} className="inline mr-1" />}
        {change}
      </p>
    </div>
  );
}

// ═══════════════════ 持仓页 ═══════════════════

export function PortfolioPage() {
  const [data, setData] = useState<PortfolioData | null>(null);
  useEffect(() => { getPortfolio().then(setData).catch(() => {}); }, []);

  if (!data) return <Skeleton />;
  return (
    <motion.div {...fadeIn} className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
        <StatCard label="总资产" value={data.total} prefix="¥" />
        <StatCard label="基金市值" value={data.fund_value} prefix="¥" />
        <StatCard label="余额宝" value={data.cash} prefix="¥" />
        <StatCard label="总盈亏" value={data.total_pl} prefix="¥" color={data.total_pl >= 0 ? "text-profit" : "text-loss"} />
        <StatCard label="收益率" value={data.total_pl_pct} suffix="%" color={data.total_pl_pct >= 0 ? "text-profit" : "text-loss"} decimals={2} />
      </div>

      <Section title="💼 持仓明细" subtitle={`${data.funds.length} 只基金`} icon={<BarChart3 size={14} className="text-[#3B82F6]" />}>
        {data.funds.filter(f => f.value > 0).map((f, i) => (
          <div key={i} className="flex items-center justify-between py-3 px-2 border-b border-[rgba(59,130,246,0.06)] last:border-0 hover:bg-[rgba(59,130,246,0.03)]">
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-[10px] font-mono text-[#64748B] w-14 shrink-0">{f.code}</span>
              <div className="min-w-0">
                <p className="text-xs text-[#E2E8F0] truncate">{f.name}</p>
                <p className="text-[10px] text-[#64748B]">成本 ¥{f.cost.toFixed(0)} · 占比 {f.weight}%</p>
              </div>
            </div>
            <div className="text-right shrink-0 ml-3">
              <p className="text-sm font-mono font-bold text-[#E2E8F0]">¥{f.value.toFixed(0)}</p>
              <p className={`text-[10px] font-mono ${f.pl >= 0 ? "text-profit" : "text-loss"}`}>
                {f.pl >= 0 ? "+" : ""}{f.pl.toFixed(0)} ({f.pl_pct >= 0 ? "+" : ""}{f.pl_pct}%)
              </p>
            </div>
          </div>
        ))}
      </Section>

      {data.pending && data.pending.length > 0 && (
        <div className="glass rounded-xl p-4 flex items-center gap-4 border border-[rgba(245,158,11,0.2)]">
          <span className="text-lg">⏳</span>
          <div className="flex-1">
            <p className="text-xs text-[#F59E0B] font-semibold">待确认申购 ¥{data.pending_total.toFixed(0)}</p>
            <p className="text-[10px] text-[#94A3B8]">
              {data.pending.map(p => `${p.name} ¥${p.amount.toFixed(0)}`).join(" · ")}
            </p>
          </div>
          <span className="text-[10px] text-[#64748B]">T+1 确认</span>
        </div>
      )}
    </motion.div>
  );
}

function StatCard({ label, value, prefix = "", suffix = "", color = "text-[#E2E8F0]", decimals = 0 }: {
  label: string; value: number; prefix?: string; suffix?: string; color?: string; decimals?: number;
}) {
  return (
    <div className="glass rounded-xl p-3.5">
      <p className="text-[10px] text-[#64748B] uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-base font-mono font-bold ${color}`}>
        {prefix}{value.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}{suffix}
      </p>
    </div>
  );
}

// ═══════════════════ 行业页 ═══════════════════

export function IndustryPage() {
  const [data, setData] = useState<{ stocks: { 股票: string; 总敞口占比: number; 涉及基金: string; 涉及基金数: number }[] } | null>(null);
  useEffect(() => { getHoldings().then(setData).catch(() => {}); }, []);

  if (!data) return <Skeleton />;
  const top = data.stocks.slice(0, 20);
  return (
    <motion.div {...fadeIn} className="space-y-3">
      <Section title="🏭 持仓穿透" subtitle={`Top ${top.length} 重仓股`} icon={<PieChart size={14} className="text-[#8B5CF6]" />}>
        <div className="overflow-auto max-h-[600px]">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)] sticky top-0 bg-[#020617]">
                <th className="text-left py-2 px-3 w-8">#</th>
                <th className="text-left py-2 px-3">股票</th>
                <th className="text-right py-2 px-3 font-mono">敞口%</th>
                <th className="text-right py-2 px-3 font-mono">涉及基金</th>
                <th className="text-left py-2 px-3 hidden md:table-cell">来源</th>
              </tr>
            </thead>
            <tbody>
              {top.map((s, i) => (
                <tr key={i} className="hover:bg-[rgba(59,130,246,0.04)] transition-colors">
                  <td className="py-2 px-3 text-[#64748B] font-mono">{i + 1}</td>
                  <td className="py-2 px-3 text-[#E2E8F0] font-medium">{s.股票}</td>
                  <td className="py-2 px-3 font-mono text-right text-[#3B82F6]">{s.总敞口占比}%</td>
                  <td className="py-2 px-3 font-mono text-right text-[#94A3B8]">{s.涉及基金数}</td>
                  <td className="py-2 px-3 text-[#64748B] text-[10px] hidden md:table-cell truncate max-w-[200px]">{s.涉及基金}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </motion.div>
  );
}

// ═══════════════════ 风险页 ═══════════════════

export function RiskPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { getRisk().then(setData).catch(() => {}); }, []);

  if (!data) return <Skeleton />;

  const metrics = [
    { label: "年化波动率", value: data.annual_volatility, suffix: "%", icon: <Activity size={14} /> },
    { label: "最大回撤", value: data.max_drawdown, suffix: "%", icon: <TrendingDown size={14} />, color: "text-loss" },
    { label: "夏普比率", value: data.sharpe_ratio, icon: <Zap size={14} />, color: "text-[#3B82F6]" },
    { label: "Calmar 比率", value: data.calmar_ratio, icon: <Shield size={14} />, color: "text-[#22C55E]" },
    { label: "VaR (95%)", value: data.var_95, suffix: "%", icon: <AlertTriangle size={14} />, color: "text-[#F59E0B]" },
    { label: "年化收益", value: data.annual_return, suffix: "%", icon: <TrendingUp size={14} />, color: "text-profit" },
  ].filter(m => m.value != null);

  return (
    <motion.div {...fadeIn} className="space-y-3">
      <Section title="⚠️ 风险指标" subtitle="250日窗口" icon={<Shield size={14} className="text-[#F59E0B]" />}>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {metrics.map((m, i) => (
            <div key={i} className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className={m.color || "text-[#94A3B8]"}>{m.icon}</span>
                <span className="text-[10px] text-[#64748B] uppercase">{m.label}</span>
              </div>
              <p className={`text-xl font-mono font-bold ${m.color || "text-[#E2E8F0]"}`}>
                {typeof m.value === "number" ? m.value.toFixed(2) : m.value}{m.suffix || ""}
              </p>
            </div>
          ))}
        </div>
      </Section>
    </motion.div>
  );
}

// ═══════════════════ 信号页 ═══════════════════

export function SignalsPage() {
  const [data, setData] = useState<SignalsData | null>(null);
  useEffect(() => { getSignals().then(setData).catch(() => {}); }, []);

  if (!data) return <Skeleton />;
  return (
    <motion.div {...fadeIn} className="space-y-3">
      <Section title="⚡ ETF 轮动信号" subtitle={data.time} icon={<Zap size={14} className="text-[#F59E0B]" />}>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)]">
                <th className="text-left py-2 px-3 w-8">#</th>
                <th className="text-left py-2 px-3">名称</th>
                <th className="text-right py-2 px-3 font-mono">评分</th>
                <th className="text-right py-2 px-3 font-mono">动量</th>
                <th className="text-center py-2 px-3">信号</th>
                <th className="text-left py-2 px-3 hidden md:table-cell">理由</th>
              </tr>
            </thead>
            <tbody>
              {data.signals.map((s, i) => (
                <tr key={i} className="hover:bg-[rgba(59,130,246,0.04)] transition-colors">
                  <td className="py-2 px-3 text-[#64748B] font-mono">{i + 1}</td>
                  <td className="py-2 px-3 text-[#E2E8F0] font-medium">{s.name}</td>
                  <td className="py-2 px-3 font-mono text-right">{s.score.toFixed(4)}</td>
                  <td className={`py-2 px-3 font-mono text-right ${s.momentum.startsWith("-") ? "text-loss" : "text-profit"}`}>{s.momentum}</td>
                  <td className="py-2 px-3 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                      s.action === "买入" ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E]" :
                      s.action === "卖出" ? "bg-[rgba(239,68,68,0.12)] text-[#EF4444]" :
                      "bg-[rgba(148,163,184,0.1)] text-[#94A3B8]"
                    }`}>{s.action}</span>
                  </td>
                  <td className="py-2 px-3 text-[#64748B] text-[10px] hidden md:table-cell">{s.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.suggestion && (
          <div className="mt-3 p-3 rounded-lg bg-[rgba(59,130,246,0.06)] border border-[rgba(59,130,246,0.1)]">
            <p className="text-[11px] text-[#94A3B8]">💡 {data.suggestion}</p>
          </div>
        )}
      </Section>
    </motion.div>
  );
}

// ═══════════════════ 个股页 ═══════════════════

export function StockPage() {
  const [spot, setSpot] = useState<StockSpot[]>([]);
  const [rank, setRank] = useState<StockRankItem[]>([]);
  const [selCode, setSelCode] = useState<string>("");
  const [selName, setSelName] = useState<string>("");

  useEffect(() => {
    getStockSpot().then(r => { if (r) setSpot(r.stocks || []); }).catch(() => {});
    getStockSignals().then(r => { if (r) setRank(r.rank || []); }).catch(() => {});
  }, []);

  const KLineChart = dynamic(() => import("@/components/KLineChart"), {
    ssr: false,
    loading: () => (
      <div className="glass rounded-xl p-4 flex items-center justify-center min-h-[420px]">
        <span className="text-[#64748B] text-xs font-mono">加载图表...</span>
      </div>
    ),
  });

  return (
    <motion.div {...fadeIn} className="space-y-3">
      {/* 选中股票的K线图 */}
      {selCode && (
        <motion.div {...fadeIn}>
          <KLineChart symbol={selCode} name={selName} />
        </motion.div>
      )}

      <Section title="📈 个股行情" icon={<Activity size={14} className="text-[#22C55E]" />}>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)]">
                <th className="text-left py-2 px-3">名称</th>
                <th className="text-right py-2 px-3 font-mono">现价</th>
                <th className="text-right py-2 px-3 font-mono">涨跌</th>
                <th className="text-right py-2 px-3 font-mono">成交额(亿)</th>
              </tr>
            </thead>
            <tbody>
              {spot.map((s, i) => (
                <tr key={i}
                  className={`hover:bg-[rgba(59,130,246,0.08)] cursor-pointer transition-colors ${selCode === s.code ? "bg-[rgba(59,130,246,0.1)]" : ""}`}
                  onClick={() => { setSelCode(s.code); setSelName(s.name); }}
                >
                  <td className="py-2 px-3">
                    <span className="text-[#E2E8F0]">{s.name}</span>
                    <span className="text-[10px] text-[#64748B] ml-1 font-mono">{s.code}</span>
                  </td>
                  <td className="py-2 px-3 font-mono text-right">{s.price?.toFixed(2)}</td>
                  <td className={`py-2 px-3 font-mono text-right ${s.change_pct >= 0 ? "text-profit" : "text-loss"}`}>
                    {s.change_pct >= 0 ? "+" : ""}{s.change_pct?.toFixed(2)}%
                  </td>
                  <td className="py-2 px-3 font-mono text-right text-[#94A3B8]">{((s.amount || 0) / 1e8).toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {rank.length > 0 && (
        <Section title="🏆 多策略排名" subtitle={`${rank.length} 只股票`} icon={<Zap size={14} className="text-[#8B5CF6]" />}>
          <div className="overflow-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)]">
                  <th className="text-left py-2 px-3 w-8">#</th>
                  <th className="text-left py-2 px-3">名称</th>
                  <th className="text-right py-2 px-3 font-mono">得分</th>
                  <th className="text-right py-2 px-3 font-mono">🟢买</th>
                  <th className="text-right py-2 px-3 font-mono">🔴卖</th>
                  <th className="text-right py-2 px-3 font-mono">策略</th>
                </tr>
              </thead>
              <tbody>
                {rank.map((r, i) => (
                  <tr key={i} className="hover:bg-[rgba(59,130,246,0.04)]">
                    <td className="py-2 px-3 text-[#64748B] font-mono">{i + 1}</td>
                    <td className="py-2 px-3 text-[#E2E8F0]">{r.name}</td>
                    <td className={`py-2 px-3 font-mono text-right font-bold ${r.score >= 0 ? "text-profit" : "text-loss"}`}>
                      {r.score > 0 ? "+" : ""}{r.score}
                    </td>
                    <td className="py-2 px-3 font-mono text-right text-[#22C55E]">{r.buy}</td>
                    <td className="py-2 px-3 font-mono text-right text-[#EF4444]">{r.sell}</td>
                    <td className="py-2 px-3 font-mono text-right text-[#94A3B8]">{r.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </motion.div>
  );
}

// ═══════════════════ AI 页 ═══════════════════

export function AIPage() {
  const [data, setData] = useState<AIData | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    getAIAnalysis().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  return (
    <motion.div {...fadeIn} className="space-y-3">
      <Section title="🤖 AI 综合分析" subtitle={data?.time ? new Date(data.time).toLocaleString() : ""} icon={<Brain size={14} className="text-[#8B5CF6]" />}>
        {loading ? (
          <div className="flex items-center gap-3 p-8 justify-center">
            <span className="w-3 h-3 rounded-full bg-[#8B5CF6] animate-pulse" />
            <span className="text-sm text-[#94A3B8] font-mono">AI 分析生成中...</span>
          </div>
        ) : data ? (
          <div className="p-4 rounded-lg bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.1)]">
            <pre className="text-xs text-[#CBD5E1] leading-relaxed whitespace-pre-wrap font-sans">{data.analysis}</pre>
          </div>
        ) : (
          <p className="text-xs text-[#64748B] p-4">AI 分析暂不可用（模型未启动或超时）</p>
        )}
        <div className="mt-3 flex items-center justify-between text-[10px] text-[#64748B]">
          <span>推理: deepseek-v4-pro</span>
          <span>仅供参考，不构成投资建议</span>
        </div>
      </Section>
    </motion.div>
  );
}

// ═══════════════════ 通用组件 ═══════════════════

function Section({ title, subtitle, icon, children }: {
  title: string; subtitle?: string; icon?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-semibold text-[#E2E8F0]">{title}</h3>
        {subtitle && <span className="text-[10px] text-[#64748B] font-mono ml-auto">{subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="glass rounded-xl p-8 flex items-center justify-center min-h-[300px]">
      <div className="flex items-center gap-3">
        <span className="w-3 h-3 rounded-full bg-[#3B82F6] animate-pulse" />
        <span className="text-xs text-[#64748B] font-mono">加载中...</span>
      </div>
    </div>
  );
}
