"use client";

import { Clock, Shield, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import { useEffect, useState } from "react";

interface Props {
  portfolioTotal?: number;
  portfolioPL?: number;
  portfolioPLPct?: number;
  yesterdayPL?: number;
}

export default function StatusBar({ portfolioTotal, portfolioPL, portfolioPLPct, yesterdayPL }: Props) {
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () => {
      setTime(new Date().toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }));
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  const pl = portfolioPL ?? 0;
  const plPct = portfolioPLPct ?? 0;
  const isUp = pl >= 0;

  return (
    <header
      className="h-10 flex items-center justify-between px-4 shrink-0 z-30"
      style={{ background: "rgba(2,6,23,0.95)", borderBottom: "1px solid rgba(59,130,246,0.08)", backdropFilter: "blur(16px)" }}
    >
      {/* 左侧：核心财务数据 */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-[#64748B] font-mono">总资产</span>
          <span className="text-xs font-mono font-bold text-[#E2E8F0]">
            ¥{((portfolioTotal ?? 0) + 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </span>
        </div>
        <span className="text-[#334155]">|</span>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-[#64748B] font-mono">累计盈亏</span>
          <span className={`text-xs font-mono font-bold flex items-center gap-0.5 ${isUp ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
            {isUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            {pl >= 0 ? "+" : ""}{pl.toFixed(0)}
          </span>
          <span className={`text-[10px] font-mono ${isUp ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
            ({plPct >= 0 ? "+" : ""}{plPct.toFixed(2)}%)
          </span>
        </div>
        {yesterdayPL != null && (
          <>
            <span className="text-[#334155]">|</span>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-[#64748B] font-mono">昨日</span>
              <span className={`text-[11px] font-mono ${yesterdayPL >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                {yesterdayPL >= 0 ? "+" : ""}{yesterdayPL.toFixed(0)}
              </span>
            </div>
          </>
        )}
      </div>

      {/* 右侧：状态信息 */}
      <div className="flex items-center gap-4">
        <HealthBar />
        <span className="text-[10px] text-[#22C55E] font-mono flex items-center gap-1">
          <Shield size={11} />
          风控正常
        </span>
        <span className="text-[#334155]">|</span>
        <span className="text-[10px] text-[#3B82F6] font-mono flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E] animate-pulse" />
          已收盘
        </span>
        <span className="text-[#334155]">|</span>
        <span className="text-[10px] text-[#94A3B8] font-mono flex items-center gap-1">
          <Clock size={11} />
          {time}
        </span>
      </div>
    </header>
  );
}

function HealthBar() {
  const [h, setH] = useState<any>(null);
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/system/health`)
      .then(r => r.json()).then(setH).catch(() => setH(null));
  }, []);
  if (!h) return null;
  const fb = h.data_provider?.fallback_level ?? 0;
  const ok = h.data_provider?.healthy;
  const label = fb === 0 ? "数据正常" : fb === 1 ? "已降级" : "缓存模式";
  const color = ok ? "text-[#22C55E]" : "text-[#F59E0B]";
  return <span className={`text-[10px] font-mono flex items-center gap-1 ${color}`}><span className={`w-1.5 h-1.5 rounded-full ${fb === 0 ? "bg-[#22C55E]" : "bg-[#F59E0B]"}`} />{label}</span>;
}
