"use client";

import { useEffect, useState } from "react";
import { Calendar, TrendingUp, TrendingDown, Target } from "lucide-react";
import { getDailyEstimate, getConfirmedDaily, type DailyEstimate } from "@/lib/api";

export default function EstimatePanel() {
  const [data, setData] = useState<DailyEstimate | null>(null);
  const [confirmed, setConfirmed] = useState<{ pl: number; pl_pct: number; date: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getDailyEstimate(date).catch(() => null),
      getConfirmedDaily().catch(() => null),
    ]).then(([est, conf]) => {
      setData(est);
      if (conf?.date === date) setConfirmed(conf);
      setLoading(false);
    });
  }, [date]);

  // 日期快捷切换
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp size={14} className="text-[#22C55E]" />
          <h3 className="text-sm font-semibold text-[#E2E8F0]">收盘预估收益</h3>
          <span className="text-[10px] text-[#64748B] font-mono">基于ETF跟踪</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDate(yesterday)}
            className={`text-[10px] px-2 py-1 rounded font-mono transition-all ${
              date === yesterday
                ? "bg-[rgba(59,130,246,0.15)] text-[#E2E8F0]"
                : "text-[#64748B] hover:text-[#94A3B8]"
            }`}
          >
            昨日
          </button>
          <button
            onClick={() => setDate(today)}
            className={`text-[10px] px-2 py-1 rounded font-mono transition-all ${
              date === today
                ? "bg-[rgba(59,130,246,0.15)] text-[#E2E8F0]"
                : "text-[#64748B] hover:text-[#94A3B8]"
            }`}
          >
            今日
          </button>
          <div className="flex items-center gap-1">
            <Calendar size={12} className="text-[#64748B]" />
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="bg-transparent text-[10px] text-[#94A3B8] font-mono border border-[rgba(59,130,246,0.12)] rounded px-2 py-0.5 outline-none focus:border-[rgba(59,130,246,0.3)]"
              style={{ colorScheme: "dark" }}
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-4 justify-center">
          <span className="w-2 h-2 rounded-full bg-[#3B82F6] animate-pulse" />
          <span className="text-[10px] text-[#64748B] font-mono">计算中...</span>
        </div>
      ) : data ? (
        <>
          {/* 汇总：预估 vs 实际 */}
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="p-3 rounded-lg bg-[rgba(8,18,37,0.6)]">
              <span className="text-[10px] text-[#64748B]">📡 ETF 预估</span>
              <p className={`text-base font-mono font-bold mt-1 ${data.total_est >= 0 ? "text-profit" : "text-loss"}`}>
                {data.total_est >= 0 ? "+" : ""}¥{data.total_est.toFixed(2)}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-[rgba(8,18,37,0.6)]">
              <span className="text-[10px] text-[#64748B] flex items-center gap-1">
                <Target size={10} /> 实际
              </span>
              {confirmed ? (
                <p className={`text-base font-mono font-bold mt-1 ${confirmed.pl >= 0 ? "text-profit" : "text-loss"}`}>
                  {confirmed.pl >= 0 ? "+" : ""}¥{confirmed.pl.toFixed(2)}
                  <span className="text-[10px] ml-1 opacity-60">
                    ({(confirmed.pl - data.total_est) >= 0 ? "+" : ""}
                    {(confirmed.pl - data.total_est).toFixed(2)})
                  </span>
                </p>
              ) : (
                <p className="text-xs text-[#64748B] font-mono mt-1">待确认</p>
              )}
            </div>
          </div>

          {/* 逐只明细 */}
          <div className="space-y-1">
            {data.funds.map((f, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-[rgba(59,130,246,0.03)] transition-all text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[10px] font-mono text-[#64748B] w-14 shrink-0">
                    {f.code}
                  </span>
                  <span className="text-[#E2E8F0] truncate">{f.name.slice(0, 12)}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-[10px] text-[#64748B] font-mono">
                    {f.etf_code}
                    <span
                      className={`ml-1 ${
                        f.etf_change >= 0 ? "text-profit" : "text-loss"
                      }`}
                    >
                      {f.etf_change >= 0 ? "+" : ""}
                      {f.etf_change.toFixed(2)}%
                    </span>
                  </span>
                  <span
                    className={`font-mono text-xs font-semibold ${
                      f.est_pl >= 0 ? "text-profit" : "text-loss"
                    }`}
                  >
                    {f.est_pl >= 0 ? (
                      <TrendingUp size={10} className="inline mr-0.5" />
                    ) : (
                      <TrendingDown size={10} className="inline mr-0.5" />
                    )}
                    {f.est_pl >= 0 ? "+" : ""}
                    {f.est_pl.toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="text-[10px] text-[#64748B] py-4 text-center">
          暂无 ETF 数据
        </p>
      )}
    </div>
  );
}
