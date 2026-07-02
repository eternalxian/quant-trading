"use client";

import { useEffect, useState } from "react";
import { Brain, Globe, TrendingUp, AlertTriangle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AgentResult {
  sentiment: number;
  confidence: number;
  summary: string;
  detail?: Record<string, string>;
  error?: string;
}

interface StockResult {
  code: string;
  name: string;
  sentiment: number;
  confidence: number;
  summary: string;
  signals: string[];
}

interface AgentData {
  macro?: AgentResult;
  sentiment?: AgentResult;
  stocks?: StockResult[];
}

export default function AgentPanel() {
  const [data, setData] = useState<AgentData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/agent/analyze`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="glass rounded-xl p-4 flex items-center gap-2 justify-center min-h-[120px]">
      <Brain size={14} className="text-[#8B5CF6] animate-pulse" />
      <span className="text-[10px] text-[#64748B] font-mono">Agent分析中...</span>
    </div>
  );

  if (!data) return null;

  const macro = data.macro;
  const sentiment = data.sentiment;
  const stocks = data.stocks || [];

  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Brain size={14} className="text-[#8B5CF6]" />
        <h3 className="text-sm font-semibold text-[#E2E8F0]">AI Agent 分析</h3>
        <span className="text-[10px] text-[#64748B] font-mono">多Agent协同</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* 宏观 */}
        <AgentCard
          icon={<Globe size={12} />}
          label="宏观"
          color="#F59E0B"
          data={macro}
        />
        {/* 情绪 */}
        <AgentCard
          icon={<AlertTriangle size={12} />}
          label="情绪"
          color="#EF4444"
          data={sentiment}
        />
        {/* 股票 */}
        <div className="col-span-1">
          <div className="text-[10px] text-[#64748B] mb-1.5 font-mono flex items-center gap-1">
            <TrendingUp size={12} className="text-[#22C55E]" />
            个股
          </div>
          {stocks.length === 0 ? (
            <p className="text-[10px] text-[#64748B]">暂无</p>
          ) : (
            <div className="space-y-1.5">
              {stocks.map((s, i) => (
                <div key={i} className="p-2 rounded bg-[rgba(8,18,37,0.6)]">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[10px] text-[#E2E8F0] font-medium">{s.name}</span>
                    <SentimentBadge value={s.sentiment} />
                  </div>
                  <p className="text-[9px] text-[#94A3B8] leading-relaxed">{s.summary}</p>
                  {s.signals.length > 0 && (
                    <div className="flex gap-1 mt-1 flex-wrap">
                      {s.signals.map((t, j) => (
                        <span key={j} className="text-[8px] px-1 py-0.5 rounded bg-[rgba(59,130,246,0.1)] text-[#3B82F6] font-mono">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AgentCard({ icon, label, color, data }: {
  icon: React.ReactNode; label: string; color: string; data?: AgentResult;
}) {
  if (!data || data.error) return (
    <div>
      <div className="text-[10px] text-[#64748B] mb-1.5 font-mono flex items-center gap-1">{icon}{label}</div>
      <p className="text-[10px] text-[#64748B]">{data?.error || "未启动"}</p>
    </div>
  );

  return (
    <div>
      <div className="text-[10px] text-[#64748B] mb-1.5 font-mono flex items-center gap-1">{icon}{label}</div>
      <div className="p-3 rounded bg-[rgba(8,18,37,0.6)]">
        <div className="flex items-center justify-between mb-1">
          <SentimentBadge value={data.sentiment} />
          <span className="text-[9px] text-[#64748B] font-mono">置信{Math.round(data.confidence * 100)}%</span>
        </div>
        <p className="text-[10px] text-[#94A3B8] leading-relaxed">{data.summary}</p>
        {data.detail?.phase && (
          <p className="text-[9px] text-[#64748B] mt-1">阶段: {data.detail.phase} · 风险: {data.detail.risk}</p>
        )}
      </div>
    </div>
  );
}

function SentimentBadge({ value }: { value: number }) {
  const config = value >= 70 ? { bg: "rgba(34,197,94,0.12)", text: "#22C55E", label: "看多" }
    : value >= 50 ? { bg: "rgba(148,163,184,0.1)", text: "#94A3B8", label: "中性" }
    : { bg: "rgba(239,68,68,0.12)", text: "#EF4444", label: "看空" };
  return (
    <span className="text-[9px] px-1.5 py-0.5 rounded font-mono" style={{ background: config.bg, color: config.text }}>
      {config.label} {value}
    </span>
  );
}
