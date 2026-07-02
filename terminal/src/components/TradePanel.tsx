"use client";

import { useEffect, useState } from "react";
import { Zap, Shield, TrendingUp, TrendingDown, Check, X } from "lucide-react";
import { getTradeAdvices, getRiskStatus, type TradeAdvicesData, type RiskStatus } from "@/lib/api";

export default function TradePanel() {
  const [data, setData] = useState<TradeAdvicesData | null>(null);
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getTradeAdvices().catch(() => null),
      getRiskStatus().catch(() => null),
    ]).then(([d, r]) => {
      setData(d);
      setRisk(r);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="glass rounded-xl p-4 flex items-center gap-2 justify-center min-h-[120px]">
        <span className="w-2 h-2 rounded-full bg-[#3B82F6] animate-pulse" />
        <span className="text-[10px] text-[#64748B] font-mono">生成建议中...</span>
      </div>
    );
  }

  const circuitOk = risk?.circuit?.closed ?? true;
  const advices = data?.advices || [];

  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Zap size={14} className={circuitOk ? "text-[#22C55E]" : "text-[#EF4444]"} />
          <h3 className="text-sm font-semibold text-[#E2E8F0]">今日操作建议</h3>
          {!circuitOk && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[rgba(239,68,68,0.12)] text-[#EF4444] font-mono">
              风控熔断
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px] text-[#64748B] font-mono">
          <Shield size={10} className={circuitOk ? "text-[#22C55E]" : "text-[#EF4444]"} />
          <span>{circuitOk ? "风控正常" : `熔断: ${risk?.circuit?.reason || "异常"}`}</span>
        </div>
      </div>

      {advices.length === 0 ? (
        <p className="text-[11px] text-[#64748B] py-3 text-center font-mono">
          今日无操作建议 — 信号均为观望
        </p>
      ) : (
        <div className="space-y-2">
          {advices.map((a, i) => (
            <div
              key={i}
              className={`p-3 rounded-lg border transition-all ${
                a.risk_ok
                  ? "bg-[rgba(8,18,37,0.6)] border-[rgba(59,130,246,0.1)]"
                  : "bg-[rgba(239,68,68,0.04)] border-[rgba(239,68,68,0.2)]"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {a.action === "buy" ? (
                    <TrendingUp size={14} className="text-[#22C55E]" />
                  ) : (
                    <TrendingDown size={14} className="text-[#EF4444]" />
                  )}
                  <span className="text-xs font-semibold text-[#E2E8F0]">{a.name}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      a.action === "buy"
                        ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E]"
                        : "bg-[rgba(239,68,68,0.12)] text-[#EF4444]"
                    }`}
                  >
                    {a.action === "buy" ? "买入" : "卖出"}
                  </span>
                  {a.risk_ok ? (
                    <Check size={12} className="text-[#22C55E]" />
                  ) : (
                    <X size={12} className="text-[#EF4444]" />
                  )}
                </div>
                <div className="text-right">
                  <span className="text-sm font-mono font-bold text-[#E2E8F0]">
                    ¥{a.amount.toFixed(0)}
                  </span>
                  <span className="text-[10px] text-[#64748B] ml-1 font-mono">
                    {a.confidence}%
                  </span>
                </div>
              </div>
              <p className="text-[10px] text-[#94A3B8] leading-relaxed">
                {a.reason}
              </p>
              {!a.risk_ok && (
                <p className="text-[10px] text-[#EF4444] mt-1 font-mono">
                  ⚠ {a.risk_detail}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {data?.suggestion && (
        <div className="mt-3 pt-3 border-t border-[rgba(59,130,246,0.08)]">
          <p className="text-[10px] text-[#64748B] leading-relaxed">💡 {data.suggestion}</p>
        </div>
      )}
    </div>
  );
}
