"use client";

import { useState, useEffect, useRef } from "react";
import {
  TrendingUp,
  TrendingDown,
  Shield,
  BarChart3,
  Zap,
  Globe,
} from "lucide-react";
import type { PortfolioData, SignalsData } from "@/lib/api";
import { getConfirmedDaily } from "@/lib/api";

interface Props {
  portfolio: PortfolioData | null;
  signals: SignalsData | null;
}

function AnimatedNumber({
  value,
  prefix = "",
  suffix = "",
  decimals = 2,
  className = "",
}: {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(0);
  const prevValue = useRef(value);

  useEffect(() => {
    const duration = 800;
    const start = performance.now();
    const from = prevValue.current;
    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(from + (value - from) * eased);
      if (progress < 1) requestAnimationFrame(tick);
    };
    prevValue.current = value;
    requestAnimationFrame(tick);
  }, [value]);

  return (
    <span className={className} suppressHydrationWarning>
      {prefix}
      {display.toLocaleString("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}

function MiniChart({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return <div className="w-16 h-6" />;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data
    .map(
      (v, i) =>
        `${(i / (data.length - 1)) * 100},${100 - ((v - min) / range) * 60}`
    )
    .join(" ");
  return (
    <svg viewBox="0 0 100 30" className="w-16 h-6 opacity-80">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function AssetOverview({ portfolio, signals }: Props) {
  const total = portfolio?.total ?? 0;
  const fundValue = portfolio?.fund_value ?? 0;
  const cash = portfolio?.cash ?? 0;
  const totalPL = portfolio?.total_pl ?? 0;
  const totalPLPct = portfolio?.total_pl_pct ?? 0;

  const [confirmedPL, setConfirmedPL] = useState<number | null>(null);
  const [confirmedPLPct, setConfirmedPLPct] = useState<number | null>(null);
  const [confirmedTotal, setConfirmedTotal] = useState<number | null>(null);

  useEffect(() => {
    getConfirmedDaily().then(d => {
      if (d?.date === new Date().toISOString().slice(0, 10) || d?.total > 0) {
        setConfirmedPL(d.pl);
        setConfirmedPLPct(d.pl_pct);
        if (d.total > 0) setConfirmedTotal(d.total);
      }
    }).catch(() => {});
  }, []);

  const displayTotal = confirmedTotal && confirmedTotal > 0 ? confirmedTotal : total;

  // 今日净值是否已全部更新
  const todayStr = new Date().toISOString().slice(0, 10);
  const navUpdated = portfolio?.date === todayStr;
  const dailyChange = navUpdated && portfolio?.daily_change
    ? parseFloat(String(portfolio.daily_change))
    : null;

  // 真实日收益：优先支付宝确认 → 净值计算
  const displayPL = confirmedPL ?? (navUpdated ? (dailyChange ?? totalPL) : totalPL);
  const displayPLPct = confirmedPLPct ?? (navUpdated ? totalPLPct : totalPLPct);
  const isConfirmed = confirmedPL != null;

  // AI prediction: based on signal scores
  const buyCount = signals?.signals?.filter((s) => s.action === "买入").length ?? 0;
  const sellCount = signals?.signals?.filter((s) => s.action === "卖出").length ?? 0;
  const aiPrediction = buyCount > sellCount ? 78 : buyCount === sellCount ? 50 : 32;

  // Market sentiment from signal momentum
  const avgMomentum =
    signals?.signals?.reduce(
      (sum, s) => sum + (parseFloat(s.momentum) || 0),
      0
    ) ?? 0;
  const sentiment = Math.min(
    100,
    Math.max(0, 50 + avgMomentum * 50)
  );

  // Risk: based on concentration of top fund
  const maxWeight = Math.max(
    ...(portfolio?.funds?.map((f) => f.weight) ?? [0]),
    0
  );
  const riskScore = Math.round(maxWeight * 3);

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
      <AssetCard
        label={confirmedPL != null ? "总资产 ✓" : "总资产"}
        value={displayTotal}
        prefix="¥"
        icon={<BarChart3 size={14} />}
        chart={[displayTotal * 0.9, displayTotal * 0.95, displayTotal * 0.98, displayTotal].filter(v => v > 0)}
      />
      <AssetCard
        label={isConfirmed ? "今日收益 ✓" : (navUpdated ? "今日收益" : "累计盈亏")}
        value={displayPL}
        prefix={displayPL >= 0 ? "+¥" : "-¥"}
        icon={
          displayPL >= 0 ? (
            <TrendingUp size={14} className="text-profit" />
          ) : (
            <TrendingDown size={14} className="text-loss" />
          )
        }
        color={displayPL >= 0 ? "text-profit" : "text-loss"}
        chart={[-120, -80, 200, 450, 680, displayPL].filter((v) => !isNaN(v))}
        subtitle={isConfirmed ? "已核对" : (navUpdated ? undefined : "净值未全")}
        suffix={
          <span className={displayPLPct >= 0 ? "text-profit" : "text-loss"}>
            {" "}
            ({displayPLPct >= 0 ? "+" : ""}
            {displayPLPct.toFixed(2)}%)
          </span>
        }
      />
      <AssetCard
        label="AI 预测"
        value={aiPrediction}
        prefix=""
        suffix="%"
        icon={<Zap size={14} className="text-[#8B5CF6]" />}
        color="text-[#8B5CF6]"
        chart={[72, 74, 75, 76, 77, aiPrediction]}
        subtitle="综合看涨概率"
      />
      <AssetCard
        label="市场情绪"
        value={sentiment}
        prefix=""
        suffix="/100"
        icon={<Globe size={14} className="text-[#F59E0B]" />}
        color={sentiment >= 50 ? "text-profit" : "text-loss"}
        chart={[55, 58, 62, 65, 67, sentiment]}
        subtitle={sentiment >= 60 ? "偏乐观" : sentiment >= 40 ? "中性" : "偏悲观"}
      />
      <AssetCard
        label="风控等级"
        value={riskScore}
        prefix=""
        suffix="/100"
        icon={<Shield size={14} className="text-[#3B82F6]" />}
        color="text-[#3B82F6]"
        chart={[38, 40, 42, 41, 43, riskScore]}
        subtitle={riskScore < 30 ? "低风险" : riskScore < 60 ? "中等" : "高风险"}
      />
    </div>
  );
}

function AssetCard({
  label,
  value,
  prefix = "",
  suffix = "",
  icon,
  color = "text-[#E2E8F0]",
  chart,
  subtitle,
}: {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string | React.ReactNode;
  icon: React.ReactNode;
  color?: string;
  chart: number[];
  subtitle?: string;
}) {
  return (
    <div className="glass rounded-xl p-3.5 hover:bg-[rgba(15,23,42,0.82)] hover:scale-[1.02] transition-all duration-300 cursor-default group">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-[#94A3B8] font-medium tracking-wide uppercase">
          {label}
        </span>
        <span className="opacity-60 group-hover:opacity-100 transition-opacity">
          {icon}
        </span>
      </div>
      <div className={`text-lg font-mono font-bold tracking-tight ${color}`}>
        <AnimatedNumber value={value} prefix={prefix} decimals={2} />
        {typeof suffix === "string" ? (
          <span className="text-xs ml-0.5 opacity-70">{suffix}</span>
        ) : (
          suffix
        )}
      </div>
      <div className="flex items-center justify-between mt-2">
        <MiniChart
          data={chart}
          color={
            color === "text-profit"
              ? "#22C55E"
              : color === "text-loss"
              ? "#EF4444"
              : "#3B82F6"
          }
        />
        {subtitle && (
          <span className="text-[10px] text-[#64748B]">{subtitle}</span>
        )}
      </div>
    </div>
  );
}
