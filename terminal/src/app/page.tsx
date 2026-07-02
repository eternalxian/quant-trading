"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import StatusBar from "@/components/StatusBar";
import AssetOverview from "@/components/AssetOverview";
import AIAnalysis from "@/components/AIAnalysis";
import PortfolioTable from "@/components/PortfolioTable";
import {
  MarketPage, PortfolioPage, IndustryPage, RiskPage,
  SignalsPage, StockPage, AIPage,
} from "@/components/Pages";
import EstimatePanel from "@/components/EstimatePanel";
import TradePanel from "@/components/TradePanel";
import DailyReportPage from "@/components/DailyReportPage";
import OptimizerPage from "@/components/OptimizerPage";
import AgentPanel from "@/components/AgentPanel";
import FundRealtime from "@/components/FundRealtime";
import FundEditor from "@/components/FundEditor";
import StrategyHealthPage from "@/components/StrategyHealthPage";
import { motion } from "framer-motion";
import { Layers, Radio, Clock } from "lucide-react";
import {
  getPortfolio, getMarket, getSignals, getStockSpot,
  getStockSignals, getAIAnalysis,
  type PortfolioData, type SignalsData, type MarketETF,
  type StockSpot, type StockRankItem, type AIData,
} from "@/lib/api";

const KLineChart = dynamic(() => import("@/components/KLineChart"), {
  ssr: false,
  loading: () => (
    <div className="glass rounded-xl p-4 flex items-center justify-center min-h-[420px]">
      <span className="text-[#64748B] text-xs font-mono">加载图表...</span>
    </div>
  ),
});

const fadeIn = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as const },
};

export default function Home() {
  const [page, setPage] = useState("概览");
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [signals, setSignals] = useState<SignalsData | null>(null);
  const [sectors, setSectors] = useState<MarketETF[]>([]);
  const [stockRank, setStockRank] = useState<StockRankItem[]>([]);
  const [stockSpot, setStockSpot] = useState<StockSpot[]>([]);
  const [aiAnalysis, setAiAnalysis] = useState<AIData | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [pf, sigs, spot, stockSigs] = await Promise.all([
        getPortfolio(), getSignals().catch(() => null),
        getStockSpot().catch(() => null), getStockSignals().catch(() => null),
      ]);
      getAIAnalysis().then(setAiAnalysis).catch(() => {});
      setPortfolio(pf); setSignals(sigs);
      if (spot) setStockSpot(spot.stocks || []);
      if (stockSigs) setStockRank(stockSigs.rank || []);
      if (sigs?.signals?.length) {
        setSectors(sigs.signals.map((s) => ({
          code: s.code, name: s.name, price: 0,
          change_pct: parseFloat(s.momentum) || 0, amount: 0,
        })));
      } else {
        getMarket().then((m) => { if (m) setSectors(m.etfs || []); }).catch(() => {});
      }
    } catch (_) {}
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#020617]">
      <StatusBar portfolioTotal={portfolio?.total} portfolioPL={portfolio?.total_pl} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar active={page} onNavigate={setPage} />
        <main className="flex-1 overflow-auto p-4 space-y-3">
          {page === "概览" && (
            <>
              <motion.section {...fadeIn}>
                <FundRealtime />
              </motion.section>
              <motion.section {...fadeIn} transition={{ delay: 0.05 }}>
                <FundEditor />
              </motion.section>
              <motion.section {...fadeIn}>
                <AssetOverview portfolio={portfolio} signals={signals} />
              </motion.section>
              <motion.section {...fadeIn} transition={{ delay: 0.1 }} className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                <div className="lg:col-span-2">
                  <KLineChart
                    symbol={sectors.length > 0 ? sectors[0].code : "512480"}
                    name={sectors.length > 0 ? sectors[0].name : "半导体ETF"}
                    signalData={sectors.length > 0 ? { price: sectors[0].price || 0, change_pct: sectors[0].change_pct } : undefined}
                  />
                </div>
                <div className="lg:col-span-1"><AIAnalysis data={aiAnalysis} /></div>
              </motion.section>
              <motion.section {...fadeIn} transition={{ delay: 0.2 }}>
                <EstimatePanel />
              </motion.section>
              <motion.section {...fadeIn} transition={{ delay: 0.22 }}>
                <TradePanel />
              </motion.section>
              <motion.section {...fadeIn} transition={{ delay: 0.25 }}>
                <AgentPanel />
              </motion.section>
              <motion.section {...fadeIn} transition={{ delay: 0.3 }} className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                <div className="lg:col-span-1"><MarketHeat sectors={sectors} /></div>
                <div className="lg:col-span-2">
                  <PortfolioTable funds={portfolio?.funds || []} signals={signals} stockRank={stockRank} stockSpot={stockSpot} />
                </div>
              </motion.section>
              {portfolio?.pending && portfolio.pending.length > 0 && (
                <motion.section {...fadeIn} transition={{ delay: 0.45 }}>
                  <PendingBanner pending={portfolio.pending} total={portfolio.pending_total} />
                </motion.section>
              )}
            </>
          )}
          {page === "市场" && <MarketPage />}
          {page === "持仓" && <PortfolioPage />}
          {page === "行业" && <IndustryPage />}
          {page === "风险" && <RiskPage />}
          {page === "信号" && <SignalsPage />}
          {page === "个股" && <StockPage />}
          {page === "AI" && <AIPage />}
          {page === "日报" && <DailyReportPage />}
          {page === "优化" && <OptimizerPage />}
          {page === "健康" && <StrategyHealthPage />}
          <div className="h-4" />
        </main>
      </div>
    </div>
  );
}

function MarketHeat({ sectors }: { sectors: MarketETF[] }) {
  return (
    <div className="glass rounded-xl p-4 flex flex-col h-full">
      <div className="flex items-center gap-2 mb-3">
        <Layers size={14} className="text-[#3B82F6]" />
        <h3 className="text-sm font-semibold text-[#E2E8F0]">板块信号</h3>
      </div>
      <div className="space-y-2 flex-1">
        {sectors.length === 0 && <p className="text-[10px] text-[#64748B]">加载中...</p>}
        {sectors.map((s, i) => (
          <div key={i} className="flex items-center justify-between p-2 rounded-md bg-[rgba(8,18,37,0.6)] hover:bg-[rgba(59,130,246,0.04)] transition-all">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${s.change_pct >= 0 ? "bg-[#22C55E]" : "bg-[#EF4444]"}`} />
              <span className="text-xs text-[#E2E8F0] font-medium">{s.name}</span>
            </div>
            <span className={`text-xs font-mono ${s.change_pct >= 0 ? "text-profit" : "text-loss"}`}>
              {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(2)}%
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-[rgba(59,130,246,0.08)] flex items-center justify-between">
        <span className="text-[10px] text-[#64748B] flex items-center gap-1"><Radio size={10} />实时</span>
        <span className="text-[10px] text-[#22C55E] font-mono">{sectors.filter(s=>s.change_pct>=0).length}涨 {sectors.filter(s=>s.change_pct<0).length}跌</span>
      </div>
    </div>
  );
}

function PendingBanner({ pending, total }: { pending: { code: string; name: string; amount: number; date: string }[]; total: number }) {
  return (
    <div className="glass rounded-xl p-4 flex items-center gap-4">
      <Clock size={18} className="text-[#F59E0B] shrink-0" />
      <div className="flex-1">
        <span className="text-xs text-[#F59E0B] font-semibold">⏳ 待确认申购 {total.toFixed(0)} 元</span>
        <span className="text-[10px] text-[#94A3B8] ml-2">
          {pending.map(p => `${p.name} ${p.amount.toFixed(0)}`).join(" · ")}
        </span>
      </div>
      <span className="text-[10px] text-[#64748B]">不参与当日收益计算</span>
    </div>
  );
}

function PagePlaceholder({ title, desc }: { title: string; desc: string }) {
  return (
    <motion.div {...fadeIn} className="glass rounded-xl p-12 flex flex-col items-center justify-center min-h-[400px]">
      <span className="text-4xl mb-3">{title.slice(0, 2)}</span>
      <h2 className="text-lg font-semibold text-[#E2E8F0] mb-1">{title}</h2>
      <p className="text-sm text-[#64748B]">{desc}</p>
      <p className="text-[10px] text-[#475569] mt-4 font-mono">开发中，数据已通过 API 就绪</p>
    </motion.div>
  );
}
