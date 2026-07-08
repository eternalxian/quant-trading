"use client";

import { useEffect, useState } from "react";
import { Send, Check, RefreshCw } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FundRow { code: string; name: string; value: number; cost: number; }
interface PendingItem { code: string; name: string; amount: number; date: string; }

export default function FundEditor() {
  const [funds, setFunds] = useState<FundRow[]>([]);
  const [editing, setEditing] = useState(false);
  const [pl, setPl] = useState("");
  const [saved, setSaved] = useState(false);
  const [cash, setCash] = useState(0);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [pasteMode, setPasteMode] = useState(false);
  const [pasteText, setPasteText] = useState("");

  useEffect(() => { loadFunds(); }, []);

  const loadFunds = async () => {
    try {
      const cached = localStorage.getItem("fund-editor-data");
      if (cached) {
        const d = JSON.parse(cached);
        if (d.funds?.length > 0 && d.date === new Date().toISOString().slice(0, 10)) {
          setFunds(d.funds); setCash(d.cash || 0);
        }
      }
    } catch {}

    const r1 = await fetch(`${API_BASE}/api/portfolio/confirmed`).then(r => r.json()).catch(() => ({}));
    const r2 = await fetch(`${API_BASE}/api/portfolio`).then(r => r.json()).catch(() => ({ funds: [], cash: 0, pending: [], pending_total: 0 }));

    const cf = (r1.funds || {}) as Record<string, number>;
    const rows: FundRow[] = (r2.funds || [])
      .filter((f: any) => f.code !== "007817")
      .map((f: any) => ({ code: f.code, name: f.name || "", value: cf[f.code] || f.value || 0, cost: f.cost || 0 }));

    setFunds(rows);
    setCash(r2.cash || 0);
    setPending((r2.pending || []).map((p: any) => ({ code: p.code, name: p.name || "", amount: p.amount || 0, date: p.date || "" })));
    setPendingTotal(r2.pending_total || 0);
  };

  const total = funds.reduce((s, f) => s + f.value, 0);

  const saveToLocal = (f: FundRow[]) => {
    try { localStorage.setItem("fund-editor-data", JSON.stringify({ funds: f, cash, date: new Date().toISOString().slice(0, 10) })); } catch {}
  };

  const save = async () => {
    const data: Record<string, number> = {};
    funds.forEach(f => { data[f.code] = f.value; });
    saveToLocal(funds);
    await fetch(`${API_BASE}/api/portfolio/confirm-funds`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ funds: data }),
    }).catch(() => {});

    const plNum = parseFloat(pl) || 0;
    const totalVal = total + cash;
    const plPct = totalVal > 0 ? (plNum / totalVal * 100) : 0;
    await fetch(`${API_BASE}/api/portfolio/confirm-daily?pl=${plNum}&pl_pct=${plPct.toFixed(2)}&total=${totalVal.toFixed(0)}`, { method: "POST" }).catch(() => {});
    setSaved(true); setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="glass rounded-xl p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-[#64748B]">💼 持仓编辑</span>
        <div className="flex gap-2">
          <button onClick={() => { setPasteMode(!pasteMode); setPasteText(""); }}
            className={`text-[9px] font-mono ${pasteMode ? "text-[#F59E0B]" : "text-[#3B82F6]"}`}>
            {pasteMode ? "取消" : "粘贴录入"}
          </button>
          <button onClick={loadFunds} className="text-[9px] text-[#3B82F6] font-mono flex items-center gap-1"><RefreshCw size={10} />刷新</button>
          <button onClick={() => setEditing(!editing)} className={`text-[9px] font-mono ${editing ? "text-[#F59E0B]" : "text-[#3B82F6]"}`}>{editing ? "完成" : "编辑"}</button>
        </div>
      </div>

      {/* 粘贴录入区 */}
      {pasteMode && (
        <div className="space-y-1.5 p-2 rounded bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.15)]">
          <span className="text-[9px] text-[#64748B]">从支付宝持仓页复制，粘贴到下方：</span>
          <textarea value={pasteText} onChange={e => setPasteText(e.target.value)}
            placeholder={"014319 德邦半导体A 4331.75元 +104.65元\n011839 天弘人工智能A 3793.61元 ..."}
            rows={4}
            className="w-full bg-[rgba(8,18,37,0.8)] border border-[rgba(59,130,246,0.12)] rounded p-2 text-[10px] text-[#E2E8F0] font-mono resize-none outline-none"
            style={{ colorScheme: "dark" }} />
          <button onClick={async () => {
            if (!pasteText.trim()) return;
            const r = await fetch(`${API_BASE}/api/portfolio/confirm-text`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ text: pasteText }),
            }).then(r => r.json()).catch(() => ({}));
            if (r.status === "ok") {
              setPasteText(""); setPasteMode(false);
              loadFunds();
            }
          }} className="w-full py-1 rounded text-[9px] font-mono bg-[rgba(59,130,246,0.12)] text-[#3B82F6] hover:bg-[rgba(59,130,246,0.2)]">
            确认录入 ({pasteText.trim().split("\n").filter(l=>/\d{6}/.test(l)).length} 只基金)
          </button>
        </div>
      )}

      <div className="space-y-1">
        {funds.map((f, i) => (
          <div key={i} className="flex items-center justify-between text-[10px] py-0.5">
            <span className="text-[#94A3B8] font-mono w-14">{f.code}</span>
            <span className="text-[#E2E8F0] flex-1 truncate">{f.name.slice(0, 10)}</span>
            {editing ? (
              <input type="number" value={f.value || ""} onChange={e => {
                const nf = [...funds]; nf[i].value = parseFloat(e.target.value) || 0; setFunds(nf); saveToLocal(nf);
              }} className="w-20 text-right bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.12)] rounded px-2 py-0.5 text-[10px] text-[#E2E8F0] font-mono outline-none" style={{ colorScheme: "dark" }} />
            ) : (
              <span className="font-mono text-[#E2E8F0] w-20 text-right">¥{f.value.toFixed(0)}</span>
            )}
            <span className={`font-mono w-16 text-right text-[10px] ${f.value - f.cost >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
              {f.value - f.cost >= 0 ? "+" : ""}{(f.value - f.cost).toFixed(0)}
            </span>
          </div>
        ))}
      </div>

      {/* 申购中 — 从 API 动态渲染 */}
      {pending.length > 0 && (
        <>
          <div className="flex items-center text-[10px] text-[#8B5CF6] gap-1 pt-1">
            <span>⏳</span><span>申购中 ¥{pendingTotal.toFixed(0)}</span>
            <span className="font-mono ml-auto text-[#64748B]">不参与收益</span>
          </div>
          {pending.map((p, i) => (
            <div key={i} className="flex items-center text-[9px] py-0.5 ml-4">
              <span className="text-[#64748B]">{p.name} ({p.date})</span>
              <span className="font-mono ml-auto text-[#8B5CF6]">¥{p.amount.toFixed(0)}</span>
            </div>
          ))}
        </>
      )}

      <div className="flex items-center justify-between text-[10px] pt-2 border-t border-[rgba(59,130,246,0.08)]">
        <span className="text-[#64748B]">基金 ¥{total.toFixed(0)} + 余额宝 ¥{cash.toFixed(0)} = ¥{(total + cash).toFixed(0)}</span>
        <div className="flex items-center gap-2">
          <input type="number" placeholder="今日收益" value={pl} onChange={e => setPl(e.target.value)}
            className="w-20 bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.12)] rounded px-2 py-0.5 text-[10px] text-[#E2E8F0] font-mono outline-none" style={{ colorScheme: "dark" }} />
          <button onClick={save} className={`px-3 py-1 rounded text-[9px] font-mono transition-all ${saved ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E]" : "bg-[rgba(59,130,246,0.12)] text-[#3B82F6]"}`}>
            {saved ? <Check size={12} /> : <Send size={12} />}
          </button>
        </div>
      </div>
    </div>
  );
}
