"use client";

import { useEffect, useState } from "react";
import { Activity, Shield, TrendingDown, AlertTriangle } from "lucide-react";

interface HealthItem {
  strategy: string;
  status: "active" | "degraded" | "stopped";
  sharpe: number;
  win_rate: number;
  drawdown: number;
  consecutive_losses: number;
  note: string;
}

const MOCK: HealthItem[] = [
  { strategy: "ETF轮动-回归斜率", status: "active", sharpe: 1.24, win_rate: 58, drawdown: 12.3, consecutive_losses: 0, note: "运行正常" },
  { strategy: "双均线交叉", status: "active", sharpe: 0.67, win_rate: 45, drawdown: 8.1, consecutive_losses: 2, note: "信号偏少" },
  { strategy: "MACD趋势跟踪", status: "active", sharpe: 0.82, win_rate: 52, drawdown: 10.5, consecutive_losses: 0, note: "运行正常" },
  { strategy: "RSI超买超卖", status: "degraded", sharpe: 0.31, win_rate: 33, drawdown: 18.7, consecutive_losses: 4, note: "滚动夏普低于历史50%" },
  { strategy: "布林带反转", status: "stopped", sharpe: -0.15, win_rate: 28, drawdown: 25.2, consecutive_losses: 5, note: "连续亏损5次，已停止" },
];

export default function StrategyHealthPage() {
  const [data] = useState<HealthItem[]>(MOCK);

  const active = data.filter(d => d.status === "active").length;
  const degraded = data.filter(d => d.status === "degraded").length;
  const stopped = data.filter(d => d.status === "stopped").length;

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-5 text-center">
        <h2 className="text-lg font-bold text-[#E2E8F0]">🩺 策略健康度</h2>
        <p className="text-[10px] text-[#64748B] font-mono mt-1">滚动指标监控 · 自动降级 · 连续亏损熔断</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="glass rounded-xl p-4 text-center">
          <p className="text-2xl font-mono font-bold text-[#22C55E]">{active}</p>
          <p className="text-[10px] text-[#64748B]">活跃</p>
        </div>
        <div className="glass rounded-xl p-4 text-center">
          <p className="text-2xl font-mono font-bold text-[#F59E0B]">{degraded}</p>
          <p className="text-[10px] text-[#64748B]">降级</p>
        </div>
        <div className="glass rounded-xl p-4 text-center">
          <p className="text-2xl font-mono font-bold text-[#EF4444]">{stopped}</p>
          <p className="text-[10px] text-[#64748B]">停止</p>
        </div>
      </div>

      {/* Table */}
      <div className="glass rounded-xl p-4">
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748B] border-b border-[rgba(59,130,246,0.08)]">
                <th className="text-left py-2 px-2">策略</th>
                <th className="text-center py-2 px-2 w-16">状态</th>
                <th className="text-right py-2 px-2 font-mono">夏普</th>
                <th className="text-right py-2 px-2 font-mono">胜率</th>
                <th className="text-right py-2 px-2 font-mono">回撤</th>
                <th className="text-right py-2 px-2 font-mono">连亏</th>
                <th className="text-left py-2 px-2">说明</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d, i) => (
                <tr key={i} className={`hover:bg-[rgba(59,130,246,0.03)] ${
                  d.status === "stopped" ? "opacity-50" : ""
                }`}>
                  <td className="py-2.5 px-2 text-[#E2E8F0] font-medium">{d.strategy}</td>
                  <td className="py-2.5 px-2 text-center">
                    <StatusBadge status={d.status} />
                  </td>
                  <td className={`py-2.5 px-2 font-mono text-right ${d.sharpe >= 0.5 ? "text-[#22C55E]" : d.sharpe >= 0 ? "text-[#F59E0B]" : "text-[#EF4444]"}`}>
                    {d.sharpe >= 0 ? "+" : ""}{d.sharpe.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-2 font-mono text-right text-[#94A3B8]">{d.win_rate}%</td>
                  <td className="py-2.5 px-2 font-mono text-right text-[#EF4444]">{d.drawdown.toFixed(1)}%</td>
                  <td className={`py-2.5 px-2 font-mono text-right ${d.consecutive_losses >= 3 ? "text-[#EF4444]" : "text-[#94A3B8]"}`}>
                    {d.consecutive_losses}
                  </td>
                  <td className="py-2.5 px-2 text-[#64748B] text-[10px]">{d.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Rules */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <Shield size={14} className="text-[#3B82F6]" />
          <h3 className="text-xs font-semibold text-[#E2E8F0]">降级规则</h3>
        </div>
        <div className="space-y-1 text-[10px] text-[#64748B]">
          <p>· 滚动夏普 {'<'} 历史夏普 × 0.5 → 降级</p>
          <p>· 滚动回撤 {'>'} 10% → 降级</p>
          <p>· 连续亏损 ≥ 5 次 → 停止</p>
          <p>· 停止后需手动恢复</p>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: "active" | "degraded" | "stopped" }) {
  const config = {
    active: { bg: "rgba(34,197,94,0.12)", text: "#22C55E", icon: <Activity size={10} />, label: "活跃" },
    degraded: { bg: "rgba(245,158,11,0.12)", text: "#F59E0B", icon: <AlertTriangle size={10} />, label: "降级" },
    stopped: { bg: "rgba(239,68,68,0.12)", text: "#EF4444", icon: <TrendingDown size={10} />, label: "停止" },
  };
  const c = config[status];
  return (
    <span className="text-[9px] px-1.5 py-0.5 rounded font-mono inline-flex items-center gap-1" style={{ background: c.bg, color: c.text }}>
      {c.icon}{c.label}
    </span>
  );
}
