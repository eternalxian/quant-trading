"use client";

import { useEffect, useState } from "react";
import { Calendar, TrendingUp, TrendingDown, Shield, Zap, AlertTriangle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DailyReportData {
  date: string; total_assets: number; fund_value: number; cash: number;
  today_pl: number; today_pl_pct: number; estimated_pl: number;
  top_gainer: string; top_gainer_pl: number;
  top_loser: string; top_loser_pl: number;
  signal_count: number; buy_count: number; sell_count: number;
  signal_summary: string; circuit_status: string;
  pending_total: number; pending_items: { code: string; name: string; amount: number }[];
  data_quality: number; data_warnings: string[];
  advices: { code: string; name: string; action: string; amount: number; confidence: number; risk_ok: boolean; reason: string }[];
  text: string; generated_at: string;
}

export default function DailyReportPage() {
  const [data, setData] = useState<DailyReportData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/daily/report`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="glass rounded-xl p-8 flex items-center justify-center min-h-[300px]">
      <span className="text-[#64748B] text-xs font-mono">生成日报中...</span>
    </div>
  );

  if (!data) return (
    <div className="glass rounded-xl p-8 text-center text-[#64748B] text-xs">日报生成失败</div>
  );

  return (
    <div className="space-y-4 max-w-3xl mx-auto">
      {/* Header */}
      <div className="glass rounded-xl p-5 text-center">
        <h2 className="text-lg font-bold text-[#E2E8F0] mb-1">📊 AI Quant 每日复盘</h2>
        <p className="text-xs text-[#64748B] font-mono">{data.date}</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniCard label="总资产" value={`¥${(data.total_assets ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`} />
        <MiniCard label="累计盈亏" value={`${(data.today_pl ?? 0) >= 0 ? "+" : ""}${(data.today_pl ?? 0).toFixed(0)}`} color={(data.today_pl ?? 0) >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"} />
        <MiniCard label="ETF估算今日" value={`${(data.estimated_pl ?? 0) >= 0 ? "+" : ""}${(data.estimated_pl ?? 0).toFixed(0)}元`} color={(data.estimated_pl ?? 0) >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"} />
        <MiniCard label="风控" value={data.circuit_status ?? "未知"} color={(data.circuit_status ?? "正常") === "正常" ? "text-[#22C55E]" : "text-[#EF4444]"} />
      </div>

      {/* P&L Details */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={14} className="text-[#22C55E]" />
          <h3 className="text-sm font-semibold text-[#E2E8F0]">持仓表现</h3>
        </div>
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-[#64748B]">🏆 最佳</span>
            <p className="text-[#E2E8F0] font-medium">{data.top_gainer || "—"}</p>
            <p className="text-[#22C55E] font-mono">+{(data.top_gainer_pl ?? 0).toFixed(0)}</p>
          </div>
          <div>
            <span className="text-[#64748B]">📉 最差</span>
            <p className="text-[#E2E8F0] font-medium">{data.top_loser || "—"}</p>
            <p className="text-[#EF4444] font-mono">{(data.top_loser_pl ?? 0) >= 0 ? "+" : ""}{(data.top_loser_pl ?? 0).toFixed(0)}</p>
          </div>
        </div>
      </div>

      {/* Signals */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Zap size={14} className="text-[#F59E0B]" />
          <h3 className="text-sm font-semibold text-[#E2E8F0]">信号 & 建议</h3>
        </div>
        <p className="text-xs text-[#94A3B8] mb-2">
          {data.signal_count}条信号 (买{data.buy_count} 卖{data.sell_count})
        </p>
        {data.advices.length > 0 ? (
          <div className="space-y-2">
            {data.advices.map((a, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded bg-[rgba(8,18,37,0.6)] text-xs">
                <span className="text-[#E2E8F0]">
                  {a.risk_ok ? "✅" : "❌"} {a.action === "buy" ? "买入" : "卖出"} {a.name}
                </span>
                <span className="font-mono text-[#E2E8F0]">¥{a.amount.toFixed(0)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[#64748B]">今日无操作建议</p>
        )}
      </div>

      {/* Pending */}
      {data.pending_total > 0 && (
        <div className="glass rounded-xl p-4 border border-[rgba(245,158,11,0.2)]">
          <div className="flex items-center gap-2 mb-3">
            <Calendar size={14} className="text-[#F59E0B]" />
            <h3 className="text-sm font-semibold text-[#F59E0B]">⏳ 待确认 ¥{data.pending_total.toFixed(0)}</h3>
          </div>
          <div className="space-y-1">
            {data.pending_items.map((p, i) => (
              <p key={i} className="text-xs text-[#94A3B8]">{p.name} ¥{p.amount.toFixed(0)}</p>
            ))}
          </div>
        </div>
      )}

      {/* Data Quality */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <Shield size={14} className={data.data_quality >= 80 ? "text-[#22C55E]" : "text-[#F59E0B]"} />
          <h3 className="text-xs font-semibold text-[#E2E8F0]">数据质量 {data.data_quality}/100</h3>
        </div>
        {data.data_warnings.map((w, i) => (
          <p key={i} className="text-[10px] text-[#F59E0B] flex items-center gap-1">
            <AlertTriangle size={10} /> {w}
          </p>
        ))}
      </div>

      <p className="text-[10px] text-[#475569] text-center font-mono">
        生成于 {new Date(data.generated_at).toLocaleString("zh-CN")}
      </p>
    </div>
  );
}

function MiniCard({ label, value, color = "text-[#E2E8F0]" }: { label: string; value: string; color?: string }) {
  return (
    <div className="glass rounded-xl p-3 text-center">
      <p className="text-[10px] text-[#64748B] mb-1">{label}</p>
      <p className={`text-sm font-mono font-bold ${color}`}>{value}</p>
    </div>
  );
}
