"use client";

import { useState, useEffect } from "react";
import { Check, Send, Wallet, Clock, PiggyBank, RefreshCw } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ConfirmPanel() {
  const [fundValue, setFundValue] = useState("");
  const [cash, setCash] = useState("");
  const [pl, setPl] = useState("");
  const [sent, setSent] = useState(false);
  const [lastConfirmed, setLastConfirmed] = useState<{total:number; pl:number; pl_pct:number; date:string; cash?:number} | null>(null);

  // 加载上次确认数据
  useEffect(() => {
    fetch(`${API_BASE}/api/portfolio/confirmed`)
      .then(r => r.json())
      .then(d => {
        if (d.date) {
          setLastConfirmed(d);
          if (d.cash) setCash(d.cash.toFixed(2));
          if (d.total && d.cash) {
            setFundValue((d.total - d.cash).toFixed(2));
          }
        }
      });

  }, []);

  const fillLast = () => {
    if (lastConfirmed) {
      if (lastConfirmed.cash) setCash(lastConfirmed.cash.toFixed(2));
      if (lastConfirmed.total && lastConfirmed.cash) {
        setFundValue((lastConfirmed.total - lastConfirmed.cash).toFixed(2));
      }
    }
  };

  const submit = async () => {
    const fundNum = parseFloat(fundValue);
    const cashNum = parseFloat(cash);
    const plNum = parseFloat(pl) || 0;
    if (isNaN(fundNum) || isNaN(cashNum)) return;

    const total = fundNum + cashNum;
    const plPct = total > 0 ? (plNum / total * 100) : 0;

    await fetch(
      `${API_BASE}/api/portfolio/confirm-daily?pl=${plNum}&pl_pct=${plPct.toFixed(2)}&total=${total.toFixed(0)}`,
      { method: "POST" }
    );
    await fetch(`${API_BASE}/api/portfolio/set-cash?amount=${cashNum}`, { method: "POST" }).catch(() => {});

    setSent(true);
    setTimeout(() => setSent(false), 2000);

    // 更新本地记录
    setLastConfirmed({ total, pl: plNum, pl_pct: plPct, date: new Date().toISOString().slice(0,10), cash: cashNum });
  };

  const totalDisplay = (fundValue && cash) ? (parseFloat(fundValue) + parseFloat(cash)).toLocaleString() : "—";

  return (
    <div className="glass rounded-xl p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-[#64748B]">
          📱 同步支付宝
          {lastConfirmed && (
            <span className="text-[#475569] ml-1">(上次: {lastConfirmed.date})</span>
          )}
        </span>
        <button onClick={fillLast} className="text-[9px] text-[#3B82F6] hover:text-[#60A5FA] font-mono flex items-center gap-1">
          <RefreshCw size={10} /> 沿用昨日
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1">
          <Wallet size={11} className="text-[#3B82F6]" />
          <span className="text-[9px] text-[#64748B]">基金</span>
          <input type="number" placeholder="持有总金额"
            value={fundValue}
            onChange={e => setFundValue(e.target.value)}
            className="w-24 bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.12)] rounded px-2 py-1 text-[11px] text-[#E2E8F0] font-mono outline-none focus:border-[rgba(59,130,246,0.3)]"
            style={{ colorScheme: "dark" }} />
        </div>
        <span className="text-[#64748B] text-[10px]">+</span>
        <div className="flex items-center gap-1">
          <PiggyBank size={11} className="text-[#F59E0B]" />
          <span className="text-[9px] text-[#F59E0B]">余额宝</span>
          <input type="number" placeholder="余额"
            value={cash}
            onChange={e => setCash(e.target.value)}
            className="w-24 bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.12)] rounded px-2 py-1 text-[11px] text-[#E2E8F0] font-mono outline-none focus:border-[rgba(59,130,246,0.3)]"
            style={{ colorScheme: "dark" }} />
        </div>
        <span className="text-[#64748B] text-[10px]">|</span>
        <span className="text-[9px] text-[#22C55E]">收益</span>
        <input type="number" placeholder="±¥"
          value={pl}
          onChange={e => setPl(e.target.value)}
          className="w-20 bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.12)] rounded px-2 py-1 text-[11px] text-[#E2E8F0] font-mono outline-none focus:border-[rgba(59,130,246,0.3)]"
          style={{ colorScheme: "dark" }} />
        <button onClick={submit} disabled={!fundValue || !cash}
          className={`px-3 py-1 rounded text-[10px] font-mono transition-all ${
            sent ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E]" : "bg-[rgba(59,130,246,0.12)] text-[#3B82F6] hover:bg-[rgba(59,130,246,0.2)]"
          }`}>
          {sent ? <Check size={12} /> : "确认"}
        </button>
      </div>

      {fundValue && cash && (
        <div className="text-[10px] font-mono text-[#64748B]">
          总资产: <span className="text-[#E2E8F0]">¥{totalDisplay}</span>
        </div>
      )}
    </div>
  );
}
