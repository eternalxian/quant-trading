"use client";

import { useEffect, useState } from "react";
import { Radio, TrendingUp, TrendingDown } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FundRT {
  code: string;
  name: string;
  value: number;
  etf_code: string;
  etf_change: number;
}

const FUND_EMOJI: Record<string, string> = {
  "014319": "💾", "011839": "🤖", "016185": "⚡",
  "005698": "🌍", "000834": "📊", "017641": "🇺🇸",
  "270042": "💵", "012920": "🌐",
};

export default function FundRealtime() {
  const [data, setData] = useState<FundRT[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/funds/realtime`);
      const d = await r.json();
      setData(d.funds || []);
    } catch {} finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 10000);
    return () => clearInterval(id);
  }, []);

  if (loading) return (
    <div className="glass rounded-xl p-3 flex items-center gap-2 justify-center">
      <span className="w-2 h-2 rounded-full bg-[#3B82F6] animate-pulse" />
      <span className="text-[10px] text-[#64748B] font-mono">加载基金...</span>
    </div>
  );

  if (data.length === 0) return null;

  return (
    <div className="glass rounded-xl p-3">
      <div className="flex items-center gap-2 mb-2">
        <Radio size={12} className="text-[#22C55E]" />
        <span className="text-[10px] text-[#22C55E] font-mono">LIVE</span>
        <span className="text-[10px] text-[#64748B]">基金实时跟踪</span>
        <span className="text-[9px] text-[#475569] font-mono ml-auto">ETF映射 · 10s刷新</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {data.map((f, i) => (
          <div key={i} className="px-3 py-1.5 rounded-lg bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.06)] hover:border-[rgba(59,130,246,0.2)] transition-all">
            <div className="flex items-center gap-1.5">
              <span className="text-xs">{FUND_EMOJI[f.code] || "📌"}</span>
              <span className="text-[10px] text-[#E2E8F0] font-medium">{f.name.slice(0, 8)}</span>
              <span className={`text-[10px] font-mono font-bold ${f.etf_change >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                {f.etf_change >= 0 ? <TrendingUp size={10} className="inline" /> : <TrendingDown size={10} className="inline" />}
                {" "}{f.etf_change >= 0 ? "+" : ""}{f.etf_change.toFixed(2)}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
