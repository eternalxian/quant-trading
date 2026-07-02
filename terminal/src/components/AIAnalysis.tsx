"use client";

import { Brain, Sparkles, AlertTriangle, TrendingUp, Shield } from "lucide-react";
import type { AIData } from "@/lib/api";

interface Props {
  data: AIData | null;
}

export default function AIAnalysis({ data }: Props) {
  const analysisText = data?.analysis || "";

  // Parse the AI response into sections
  const sections = parseAnalysis(analysisText);

  if (!data) {
    return (
      <div className="glass rounded-xl p-4 flex flex-col h-full items-center justify-center">
        <Sparkles size={20} className="text-[#8B5CF6] animate-pulse mb-2" />
        <span className="text-[10px] text-[#64748B] font-mono">AI 分析中...</span>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl p-4 flex flex-col h-full">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-5 h-5 rounded-full bg-[rgba(139,92,246,0.2)] flex items-center justify-center">
          <Sparkles size={11} className="text-[#8B5CF6]" />
        </div>
        <h3 className="text-sm font-semibold text-[#E2E8F0]">AI 分析</h3>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[rgba(34,197,94,0.12)] text-[#22C55E] font-mono">
          LIVE
        </span>
      </div>

      <div className="space-y-3 flex-1 overflow-auto">
        {sections.map((s, i) => (
          <div
            key={i}
            className="p-3 rounded-lg bg-[rgba(8,18,37,0.6)] border border-[rgba(59,130,246,0.08)] hover:border-[rgba(59,130,246,0.2)] transition-all"
          >
            <div className="flex items-center gap-1.5 mb-1.5">
              {s.icon}
              <span className="text-[11px] font-semibold text-[#CBD5E1]">
                {s.title}
              </span>
            </div>
            <p className="text-[11px] text-[#94A3B8] leading-relaxed">
              {s.content}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-auto pt-3">
        <div className="flex items-center justify-between text-[10px] text-[#64748B]">
          <span>推理模型: deepseek-v4-pro</span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E] animate-pulse" />
            实时
          </span>
        </div>
      </div>
    </div>
  );
}

function parseAnalysis(text: string) {
  if (!text) return [];

  const sections: { icon: React.ReactNode; title: string; content: string }[] = [];

  // Try to split by numbered sections (1. 2. 3. 4. 5.)
  const parts = text.split(/\d+\.\s+\*\*/);
  const iconMap = [
    <Brain key="0" size={14} className="text-[#8B5CF6]" />,
    <TrendingUp key="1" size={14} className="text-[#22C55E]" />,
    <AlertTriangle key="2" size={14} className="text-[#F59E0B]" />,
    <Shield key="3" size={14} className="text-[#3B82F6]" />,
  ];

  if (parts.length > 1) {
    for (let i = 1; i < parts.length && i <= 4; i++) {
      const content = parts[i].replace(/\*\*/g, "").trim();
      const lines = content.split("\n");
      const title = lines[0].replace(/[:：].*/, "").trim().slice(0, 20);
      const body = lines.slice(1).join(" ").trim() || content.slice(title.length).replace(/^[:：]\s*/, "").trim();
      sections.push({
        icon: iconMap[i - 1] || iconMap[3],
        title: title || `分析 ${i}`,
        content: body.slice(0, 200),
      });
    }
  } else {
    // Fallback: split into paragraphs
    const paragraphs = text.split(/\n\n+/).filter((p) => p.trim());
    const titles = ["市场分析", "策略建议", "风险提示", "综合判断"];
    paragraphs.slice(0, 4).forEach((p, i) => {
      sections.push({
        icon: iconMap[i] || iconMap[3],
        title: titles[i] || `分析 ${i + 1}`,
        content: p.trim().slice(0, 200),
      });
    });
  }

  return sections;
}
