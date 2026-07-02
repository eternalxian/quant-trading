"use client";

import {
  Wifi,
  Clock,
  Zap,
  Activity,
  Shield,
  AlertTriangle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useWebSocket } from "@/lib/useWebSocket";

interface Props {
  portfolioTotal?: number;
  portfolioPL?: number;
}

export default function StatusBar({ portfolioTotal, portfolioPL }: Props) {
  const { connected, latency, data } = useWebSocket(30000);
  const riskClosed = data?.risk?.closed ?? true;
  const liveTotal = data?.portfolio?.total ?? portfolioTotal;
  const livePL = data?.portfolio?.pl ?? portfolioPL;
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () => {
      setTime(
        new Date().toLocaleString("zh-CN", {
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header
      className="h-9 flex items-center justify-between px-4 shrink-0 z-30"
      style={{
        background: "rgba(2,6,23,0.95)",
        borderBottom: "1px solid rgba(59,130,246,0.08)",
        backdropFilter: "blur(16px)",
      }}
    >
      <div className="flex items-center gap-4">
        <StatusIndicator icon={<Wifi size={11} />} label="WS" status={connected ? "connected" : "disconnected"} />
        <StatusIndicator icon={<Activity size={11} />} label="数据" status="connected" />
        <StatusIndicator icon={<Zap size={11} />} label="AI" status="connected" />
        <span className="text-[10px] text-[#64748B] font-mono">
          {connected ? `${latency}ms` : "离线"}
        </span>
        {liveTotal && liveTotal > 0 && (
          <>
            <span className="text-[10px] text-[#64748B]">|</span>
            <span className="text-[10px] text-[#E2E8F0] font-mono">
              ¥{liveTotal.toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </span>
            {livePL != null && (
              <span className={`text-[10px] font-mono ${livePL >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                {livePL >= 0 ? "+" : ""}{livePL.toFixed(0)}
              </span>
            )}
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className={`text-[10px] font-mono flex items-center gap-1 ${riskClosed ? "text-[#94A3B8]" : "text-[#EF4444]"}`}>
          {riskClosed ? <Shield size={11} className="text-[#22C55E]" /> : <AlertTriangle size={11} className="text-[#EF4444]" />}
          风控: {riskClosed ? "正常" : "熔断"}
        </span>
        <span className="text-[10px] text-[#64748B]">|</span>
        <span className="text-[10px] text-[#3B82F6] font-mono flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-[#22C55E] animate-pulse" : "bg-[#EF4444]"}`} />
          已收盘
        </span>
        <span className="text-[10px] text-[#64748B]">|</span>
        <span className="text-[10px] text-[#94A3B8] font-mono flex items-center gap-1">
          <Clock size={11} />
          {time}
        </span>
      </div>
    </header>
  );
}

function StatusIndicator({
  icon,
  label,
  status,
}: {
  icon: React.ReactNode;
  label: string;
  status: "connected" | "disconnected";
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={status === "connected" ? "text-[#22C55E]" : "text-[#EF4444]"}>
        {icon}
      </span>
      <span className="text-[10px] text-[#64748B] font-mono">{label}</span>
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          status === "connected" ? "bg-[#22C55E]" : "bg-[#EF4444]"
        }`}
      />
    </div>
  );
}
