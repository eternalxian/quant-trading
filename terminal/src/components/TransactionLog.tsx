"use client";

import { useEffect, useState } from "react";
import { History } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TxRow {
  id: number; code: string; type: string; amount: number;
  shares: number | null; nav: number | null; fee: number;
  date: string; note: string;
}

export default function TransactionLog() {
  const [txs, setTxs] = useState<TxRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/transactions?limit=25`)
      .then(r => r.json())
      .then(d => { setTxs(d.transactions || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const typeLabel: Record<string, string> = {
    buy: "买入", sell: "卖出", dca: "定投", pending_add: "申购",
    cash_in: "存入", cash_out: "取出", pending_cancel: "取消",
    convert_in: "转入", convert_out: "转出",
  };

  return (
    <div className="glass rounded-xl p-3 space-y-2">
      <div className="flex items-center gap-2">
        <History size={14} className="text-[#64748B]" />
        <span className="text-[10px] text-[#64748B]">交易记录</span>
        <span className="text-[9px] text-[#475569] font-mono ml-auto">{txs.length} 条</span>
      </div>

      {loading ? (
        <div className="text-[10px] text-[#64748B] py-4 text-center">加载中...</div>
      ) : txs.length === 0 ? (
        <div className="text-[10px] text-[#475569] py-4 text-center">暂无交易</div>
      ) : (
        <div className="space-y-0.5 max-h-[300px] overflow-auto">
          {txs.map((tx, i) => {
            const isIn = ["buy", "dca", "pending_add", "cash_in", "convert_in"].includes(tx.type);
            return (
              <div key={i} className="flex items-center text-[10px] py-1 px-1.5 rounded hover:bg-[rgba(59,130,246,0.04)]">
                <span className="text-[#475569] font-mono w-16">{tx.date}</span>
                <span className={`font-mono w-10 ${isIn ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                  {typeLabel[tx.type] || tx.type}
                </span>
                <span className="text-[#E2E8F0] flex-1 truncate text-[9px]">{tx.note || ""}</span>
                <span className={`font-mono ${isIn ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                  {isIn ? "+" : "-"}¥{tx.amount.toFixed(0)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
