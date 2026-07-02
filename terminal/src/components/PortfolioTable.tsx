"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { FundItem, SignalsData, StockRankItem, StockSpot } from "@/lib/api";

interface Props {
  funds: FundItem[];
  signals: SignalsData | null;
  stockRank: StockRankItem[];
  stockSpot: StockSpot[];
}

type TabMode = "funds" | "stocks";

export default function PortfolioTable({ funds, signals, stockRank, stockSpot }: Props) {
  const [sortBy, setSortBy] = useState<"pl" | "weight" | "pl_pct">("pl");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [mode, setMode] = useState<TabMode>("funds");

  const signalMap: Record<string, string> = {};
  signals?.signals?.forEach((s) => {
    signalMap[s.code] = s.action;
  });

  const sortedFunds = [...funds].sort((a, b) => {
    const dir = sortDir === "desc" ? -1 : 1;
    return (a[sortBy] - b[sortBy]) * dir;
  });

  const sortedStocks = [...stockRank].sort((a, b) => b.score - a.score);

  return (
    <div className="glass rounded-xl p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex gap-1">
          <button
            onClick={() => setMode("funds")}
            className={`px-3 py-1 text-[11px] rounded-md font-mono transition-all ${
              mode === "funds"
                ? "bg-[rgba(59,130,246,0.15)] text-[#E2E8F0]"
                : "text-[#64748B] hover:text-[#94A3B8]"
            }`}
          >
            基金
          </button>
          <button
            onClick={() => setMode("stocks")}
            className={`px-3 py-1 text-[11px] rounded-md font-mono transition-all ${
              mode === "stocks"
                ? "bg-[rgba(59,130,246,0.15)] text-[#E2E8F0]"
                : "text-[#64748B] hover:text-[#94A3B8]"
            }`}
          >
            个股
          </button>
        </div>
        <span className="text-[10px] text-[#64748B] font-mono">
          共 {mode === "funds" ? funds.length : stockRank.length} 项
        </span>
      </div>

      {mode === "funds" ? (
        <>
          <div className="grid grid-cols-12 gap-2 text-[10px] text-[#64748B] font-mono uppercase tracking-wider pb-2 border-b border-[rgba(59,130,246,0.08)]">
            <span className="col-span-2">代码</span>
            <span className="col-span-2">名称</span>
            <span
              className="col-span-2 cursor-pointer hover:text-[#94A3B8] flex items-center gap-0.5"
              onClick={() => {
                setSortBy("pl");
                setSortDir(sortDir === "desc" ? "asc" : "desc");
              }}
            >
              盈亏{" "}
              {sortBy === "pl" &&
                (sortDir === "desc" ? (
                  <ChevronDown size={10} />
                ) : (
                  <ChevronUp size={10} />
                ))}
            </span>
            <span className="col-span-1">占比</span>
            <span className="col-span-2">信号</span>
            <span className="col-span-3">AI建议</span>
          </div>
          <div className="flex-1 space-y-0.5 overflow-auto mt-1">
            {sortedFunds.length === 0 && (
              <p className="text-[10px] text-[#64748B] p-2">加载中...</p>
            )}
            {sortedFunds.map((f, i) => {
              const action = signalMap[f.code] || "观望";
              return (
                <div
                  key={i}
                  className="grid grid-cols-12 gap-2 py-2 px-1 rounded-md text-xs hover:bg-[rgba(59,130,246,0.04)] transition-all group"
                >
                  <span className="col-span-2 font-mono text-[#94A3B8]">{f.code}</span>
                  <span className="col-span-2 text-[#E2E8F0] truncate">{f.name}</span>
                  <span
                    className={`col-span-2 font-mono ${f.pl >= 0 ? "text-profit" : "text-loss"}`}
                  >
                    {f.pl >= 0 ? "+" : ""}
                    {f.pl.toFixed(0)}
                    <span className="text-[10px] ml-0.5 opacity-70">
                      ({f.pl_pct >= 0 ? "+" : ""}
                      {f.pl_pct}%)
                    </span>
                  </span>
                  <span className="col-span-1 font-mono text-[#94A3B8]">{f.weight}%</span>
                  <span className="col-span-2">
                    <SignalBadge signal={action as "buy" | "sell" | "hold"} />
                  </span>
                  <span className="col-span-3 text-[#94A3B8] text-[11px] group-hover:text-[#E2E8F0] transition-colors">
                    {actionText(action)}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-12 gap-2 text-[10px] text-[#64748B] font-mono uppercase tracking-wider pb-2 border-b border-[rgba(59,130,246,0.08)]">
            <span className="col-span-2">代码</span>
            <span className="col-span-2">名称</span>
            <span className="col-span-2">得分</span>
            <span className="col-span-2">涨跌</span>
            <span className="col-span-2">买入</span>
            <span className="col-span-2">卖出</span>
          </div>
          <div className="flex-1 space-y-0.5 overflow-auto mt-1">
            {sortedStocks.length === 0 && (
              <p className="text-[10px] text-[#64748B] p-2">暂无个股数据 — 运行 python main.py g seed</p>
            )}
            {sortedStocks.map((s, i) => {
              const spot = stockSpot.find((sp) => sp.code === s.code);
              return (
                <div
                  key={i}
                  className="grid grid-cols-12 gap-2 py-2 px-1 rounded-md text-xs hover:bg-[rgba(59,130,246,0.04)] transition-all group"
                >
                  <span className="col-span-2 font-mono text-[#94A3B8]">{s.code}</span>
                  <span className="col-span-2 text-[#E2E8F0] truncate">{s.name}</span>
                  <span className={`col-span-2 font-mono ${s.score >= 0 ? "text-profit" : "text-loss"}`}>
                    {s.score > 0 ? "+" : ""}
                    {s.score}
                  </span>
                  <span className={`col-span-2 font-mono ${(spot?.change_pct ?? 0) >= 0 ? "text-profit" : "text-loss"}`}>
                    {spot ? `${spot.change_pct >= 0 ? "+" : ""}${spot.change_pct.toFixed(2)}%` : "—"}
                  </span>
                  <span className="col-span-2 font-mono text-[#22C55E]">{s.buy}</span>
                  <span className="col-span-2 font-mono text-[#EF4444]">{s.sell}</span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function SignalBadge({ signal }: { signal: "buy" | "sell" | "hold" }) {
  const config = {
    buy: { bg: "rgba(34,197,94,0.12)", text: "text-[#22C55E]", label: "买入" },
    sell: { bg: "rgba(239,68,68,0.12)", text: "text-[#EF4444]", label: "卖出" },
    hold: { bg: "rgba(148,163,184,0.1)", text: "text-[#94A3B8]", label: "观望" },
  };
  const c = config[signal] || config.hold;
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded font-mono"
      style={{ background: c.bg, color: c.text.replace("text-[", "").replace("]", "") }}
    >
      {c.label}
    </span>
  );
}

function actionText(action: string) {
  switch (action) {
    case "买入":
      return "加仓";
    case "卖出":
      return "减仓";
    default:
      return "持有";
  }
}
