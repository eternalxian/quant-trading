"use client";

import {
  LayoutDashboard, TrendingUp, BarChart3, PieChart,
  Shield, Zap, Globe, Brain, Calendar, Activity,
  Settings, Bell, ChevronRight, type LucideIcon,
} from "lucide-react";
import { useState } from "react";

interface NavItem {
  icon: LucideIcon;
  label: string;
  active?: boolean;
  badge?: string;
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: "概览", active: true },
  { icon: TrendingUp, label: "市场", badge: "LIVE" },
  { icon: BarChart3, label: "持仓", badge: "9" },
  { icon: PieChart, label: "行业" },
  { icon: Shield, label: "风险" },
  { icon: Zap, label: "信号", badge: "BUY" },
  { icon: Globe, label: "个股" },
  { icon: Brain, label: "AI" },
  { icon: Calendar, label: "日报" },
  { icon: TrendingUp, label: "优化" },
  { icon: Activity, label: "健康" },
];

interface Props {
  active?: string;
  onNavigate?: (page: string) => void;
}

export default function Sidebar({ active = "概览", onNavigate }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`h-screen flex flex-col transition-all duration-300 ${
        collapsed ? "w-[56px]" : "w-[180px]"
      }`}
      style={{
        background: "rgba(2,6,23,0.96)",
        borderRight: "1px solid rgba(59,130,246,0.08)",
        backdropFilter: "blur(20px)",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-[rgba(59,130,246,0.08)]">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#3B82F6] to-[#8B5CF6] flex items-center justify-center shrink-0">
          <span className="text-white text-[11px] font-bold">Q</span>
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold text-[#E2E8F0] tracking-wide">
            QuantTerminal
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {navItems.map((item, i) => (
          <button
            key={i}
            onClick={() => onNavigate?.(item.label)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all duration-200 group ${
              active === item.label
                ? "bg-[rgba(59,130,246,0.12)] text-[#E2E8F0] shadow-[0_0_8px_rgba(59,130,246,0.08)]"
                : "text-[#64748B] hover:text-[#94A3B8] hover:bg-[rgba(59,130,246,0.04)]"
            }`}
          >
            <item.icon
              size={16}
              className={
                active === item.label ? "text-[#3B82F6]" : "group-hover:text-[#94A3B8]"
              }
            />
            {!collapsed && (
              <>
                <span className="flex-1 text-left">{item.label}</span>
                {item.badge && (
                  <span
                    className={`text-[9px] px-1 py-0.5 rounded font-mono ${
                      item.badge === "BUY"
                        ? "bg-[rgba(34,197,94,0.12)] text-[#22C55E]"
                        : item.badge === "LIVE"
                        ? "bg-[rgba(59,130,246,0.12)] text-[#3B82F6]"
                        : "bg-[rgba(148,163,184,0.1)] text-[#94A3B8]"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </>
            )}
          </button>
        ))}
      </nav>

      {/* Bottom */}
      <div className="px-2 pb-3 space-y-0.5">
        <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-[#64748B] hover:text-[#94A3B8] hover:bg-[rgba(59,130,246,0.04)] transition-all">
          <Bell size={16} />
          {!collapsed && <span>提醒</span>}
        </button>
        <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-[#64748B] hover:text-[#94A3B8] hover:bg-[rgba(59,130,246,0.04)] transition-all">
          <Settings size={16} />
          {!collapsed && <span>设置</span>}
        </button>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center px-3 py-2 rounded-lg text-xs text-[#64748B] hover:text-[#94A3B8] hover:bg-[rgba(59,130,246,0.04)] transition-all"
        >
          <ChevronRight
            size={14}
            className={`transition-transform ${collapsed ? "rotate-180" : ""}`}
          />
        </button>
      </div>
    </aside>
  );
}
