"use client";

import { useEffect, useState } from "react";
import { Send, Check, RefreshCw } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FundRow {
  code: string;
  name: string;
  value: number;
  cost: number;
}

export default function FundEditor() {
  const [funds, setFunds] = useState<FundRow[]>([]);
  const [editing, setEditing] = useState(false);
  const [pl, setPl] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => { loadFunds(); }, []);

  const loadFunds = async () => {
    // 先读本地缓存
    try {
      const cached = localStorage.getItem("fund-editor-data");
      if (cached) {
        const d = JSON.parse(cached);
        if (d.funds?.length > 0 && d.date === new Date().toISOString().slice(0, 10)) {
          setFunds(d.funds);
          return;
        }
      }
    } catch {}

    const r1 = await fetch(`${API_BASE}/api/portfolio/confirmed`).then(r => r.json()).catch(() => ({}));
    const r2 = await fetch(`${API_BASE}/api/portfolio`).then(r => r.json()).catch(() => ({ funds: [] }));

    const cf = (r1.funds || {}) as Record<string, number>;
    const rows: FundRow[] = (r2.funds || [])
      .filter((f: any) => f.code !== "007817")
      .map((f: any) => ({
        code: f.code,
        name: f.name || "",
        value: cf[f.code] || f.value || 0,
        cost: f.cost || 0,
      }));

    setFunds(rows);
  };

  const total = funds.reduce((s, f) => s + f.value, 0);

  const saveToLocal = (f: FundRow[]) => {
    try {
      localStorage.setItem("fund-editor-data", JSON.stringify({
        funds: f, date: new Date().toISOString().slice(0, 10)
      }));
    } catch {}
  };

  const save = async () => {
    const data: Record<string, number> = {};
    funds.forEach(f => { data[f.code] = f.value; });
    saveToLocal(funds);
    await fetch(`${API_BASE}/api/portfolio/confirm-funds`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ funds: data }),
    }).catch(() => {});

    const plNum = parseFloat(pl) || 0;
    const cashVal = 2187;
    const totalVal = total + cashVal;
    const plPct = totalVal > 0 ? (plNum / totalVal * 100) : 0;
    await fetch(
      `${API_BASE}/api/portfolio/confirm-daily?pl=${plNum}&pl_pct=${plPct.toFixed(2)}&total=${totalVal.toFixed(0)}`,
      { method: "POST" }
    ).catch(() => {});

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="glass rounded-xl p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-[#64748B]">💼 持仓编辑</span>
        <div className="flex gap-2">
          <button onClick={loadFunds} className="text-[9px] text-[#3B82F6] font-mono flex items-center gap-1">
            <RefreshCw size={10} />刷新
          </button>
          <button onClick={() => setEditing(!editing)}
            className={`text-[9px] font-mono ${editing ? "text-[#F59E0B]" : "text-[#3B82F6]"}`}>
            {editing ? "完成" : "编辑"}
          </button>
        </div>
      </div>

      <div className="space-y-1">
        {funds.map((f, i) => (
          <div key={i} className="flex items-center justify-between text-[10px] py-0.5">
            <span className="text-[#94A3B8] font-mono w-14">{f.code}</span>
            <span className="text-[#E2E8F0] flex-1 truncate">{f.name.slice(0, 10)}</span>
            {editing ? (
              <input
                type="number"
                value={f.value || ""}
                onChange={e => {
                  const newFunds = [...funds];
                  newFunds[i].value = parseFloat(e.target.value) || 0;
                  setFunds(newFunds);
                  saveToLocal(newFunds);
                }}
                className="w-20 text-right bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.12)] rounded px-2 py-0.5 text-[10px] text-[#E2E8F0] font-mono outline-none focus:border-[rgba(59,130,246,0.3)]"
                style={{ colorScheme: "dark" }}
              />
            ) : (
              <span className="font-mono text-[#E2E8F0] w-20 text-right">¥{f.value.toFixed(0)}</span>
            )}
            <span className={`font-mono w-16 text-right text-[10px] ${f.value - f.cost >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
              {f.value - f.cost >= 0 ? "+" : ""}{(f.value - f.cost).toFixed(0)}
            </span>
          </div>
        ))}
      </div>

      {/* 申购中 */}
      <div className="flex items-center text-[10px] text-[#8B5CF6] gap-1 pt-1">
        <span>⏳</span>
        <span>申购中</span>
        <span className="font-mono ml-auto">不参与收益计算</span>
      </div>
      <PendingRow label="德邦半导体(5/19转换)" amount="已到账" done />
      <PendingRow label="大成纳指 500" amount="500" />
      <PendingRow label="广发纳指定投" amount="10" />
      <PendingRow label="易方达定投 20" amount="20" />

      <div className="flex items-center justify-between text-[10px] pt-2 border-t border-[rgba(59,130,246,0.08)]">
        <span className="text-[#64748B]">已确认合计 ¥{total.toFixed(0)}</span>
        <div className="flex items-center gap-2">
          <input type="number" placeholder="今日收益" value={pl}
            onChange={e => setPl(e.target.value)}
            className="w-20 bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.12)] rounded px-2 py-0.5 text-[10px] text-[#E2E8F0] font-mono outline-none focus:border-[rgba(59,130,246,0.3)]"
            style={{ colorScheme: "dark" }} />
          <button onClick={save}
            className={`px-3 py-1 rounded text-[9px] font-mono transition-all ${
              saved ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E]" : "bg-[rgba(59,130,246,0.12)] text-[#3B82F6] hover:bg-[rgba(59,130,246,0.2)]"
            }`}>
            {saved ? <Check size={12} /> : <Send size={12} />}
          </button>
        </div>
      </div>
    </div>
  );
}

function PendingRow({ label, amount, done }: { label: string; amount: string; done?: boolean }) {
  return (
    <div className="flex items-center text-[9px] py-0.5 ml-4">
      <span className="text-[#64748B]">{label}</span>
      <span className={`font-mono ml-auto ${done ? "text-[#22C55E]" : "text-[#8B5CF6]"}`}>
        {done ? "✅ 已到账" : `¥${amount}`}
      </span>
    </div>
  );
}
