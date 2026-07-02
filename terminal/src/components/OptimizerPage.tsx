"use client";

import { useEffect, useState } from "react";
import { Zap, TrendingUp, AlertTriangle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface OptResult {
  rank: number;
  score: number;
  params: Record<string, number>;
  return: number;
  status: string;
}

interface OptData {
  signals: Record<string, OptResult[]>;
  rotation: { window: number; rebalance: number; score: number; return: number; sharpe: number; max_dd: number }[];
}

export default function OptimizerPage() {
  const [data, setData] = useState<OptData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/strategy/optimize`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="glass rounded-xl p-8 flex items-center justify-center min-h-[300px]">
      <span className="text-xs text-[#64748B] font-mono">运行参数优化中... 约需60秒</span>
    </div>
  );

  if (!data) return (
    <div className="glass rounded-xl p-8 text-center text-xs text-[#64748B]">优化失败</div>
  );

  const signalNames = Object.keys(data.signals || {});

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-5 text-center">
        <h2 className="text-lg font-bold text-[#E2E8F0]">⚡ 策略参数优化器</h2>
        <p className="text-[10px] text-[#64748B] font-mono mt-1">网格搜索 · 前向验证 · 自动评分</p>
      </div>

      {signalNames.length === 0 ? (
        <div className="glass rounded-xl p-6 text-center">
          <AlertTriangle size={20} className="text-[#F59E0B] mx-auto mb-2" />
          <p className="text-xs text-[#94A3B8]">暂无优化结果 — ETF 数据不足，需至少 60 天历史</p>
        </div>
      ) : (
        signalNames.map(name => {
          const items = data.signals[name] || [];
          const best = items[0];
          return (
            <div key={name} className="glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Zap size={14} className="text-[#F59E0B]" />
                <h3 className="text-sm font-semibold text-[#E2E8F0]">{name}</h3>
                {best && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                    best.score >= 0 ? "bg-[rgba(34,197,94,0.1)] text-[#22C55E]" : "bg-[rgba(239,68,68,0.1)] text-[#EF4444]"
                  }`}>
                    最优 {best.score >= 0 ? "+" : ""}{best.score.toFixed(1)}
                  </span>
                )}
              </div>

              <div className="overflow-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)]">
                      <th className="text-left py-2 px-2 w-8">#</th>
                      <th className="text-left py-2 px-2">参数</th>
                      <th className="text-right py-2 px-2 font-mono">得分</th>
                      <th className="text-right py-2 px-2 font-mono">收益%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((r, i) => (
                      <tr key={i} className={`hover:bg-[rgba(59,130,246,0.03)] ${r.status === "best" ? "bg-[rgba(34,197,94,0.03)]" : ""}`}>
                        <td className="py-2 px-2 text-[#64748B] font-mono">
                          {r.status === "best" ? "⭐" : r.rank}
                        </td>
                        <td className="py-2 px-2 text-[#94A3B8] font-mono">
                          {Object.entries(r.params).map(([k, v]) => (
                            <span key={k} className="mr-2">
                              <span className="text-[#64748B]">{k}</span>={v}
                            </span>
                          ))}
                        </td>
                        <td className={`py-2 px-2 font-mono text-right ${r.score >= 0 ? "text-profit" : "text-loss"}`}>
                          {r.score >= 0 ? "+" : ""}{r.score.toFixed(1)}
                        </td>
                        <td className={`py-2 px-2 font-mono text-right ${r.return >= 0 ? "text-profit" : "text-loss"}`}>
                          {r.return >= 0 ? "+" : ""}{r.return.toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })
      )}

      {/* ETF 轮动优化 */}
      {data.rotation && data.rotation.length > 0 && (
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp size={14} className="text-[#22C55E]" />
            <h3 className="text-sm font-semibold text-[#E2E8F0]">ETF 轮动参数</h3>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)]">
                  <th className="text-left py-2 px-2 w-8">#</th>
                  <th className="text-right py-2 px-2 font-mono">窗口</th>
                  <th className="text-right py-2 px-2 font-mono">调仓</th>
                  <th className="text-right py-2 px-2 font-mono">收益</th>
                  <th className="text-right py-2 px-2 font-mono">夏普</th>
                  <th className="text-right py-2 px-2 font-mono">回撤</th>
                  <th className="text-right py-2 px-2 font-mono">得分</th>
                </tr>
              </thead>
              <tbody>
                {data.rotation.map((r, i) => (
                  <tr key={i} className={i === 0 ? "bg-[rgba(34,197,94,0.03)]" : ""}>
                    <td className="py-2 px-2 text-[#64748B] font-mono">{i === 0 ? "⭐" : i + 1}</td>
                    <td className="py-2 px-2 font-mono text-right text-[#94A3B8]">{r.window}</td>
                    <td className="py-2 px-2 font-mono text-right text-[#94A3B8]">{r.rebalance}</td>
                    <td className={`py-2 px-2 font-mono text-right ${r.return >= 0 ? "text-profit" : "text-loss"}`}>
                      {r.return >= 0 ? "+" : ""}{r.return.toFixed(1)}%
                    </td>
                    <td className="py-2 px-2 font-mono text-right text-[#94A3B8]">{r.sharpe?.toFixed(2) || "—"}</td>
                    <td className="py-2 px-2 font-mono text-right text-[#EF4444]">{r.max_dd?.toFixed(1) || "—"}%</td>
                    <td className={`py-2 px-2 font-mono text-right font-bold ${r.score >= 0 ? "text-profit" : "text-loss"}`}>
                      {r.score?.toFixed(1) || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-[10px] text-[#475569] text-center font-mono">
        前向验证：训练集(80%) → 测试集(20%) 方向验证
      </p>
    </div>
  );
}
