const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const _cache = new Map<string, { data: any; ts: number }>();
const CACHE_TTL = 15_000;

async function fetchAPI<T>(path: string, ttl: number = CACHE_TTL): Promise<T> {
  const key = path;
  const cached = _cache.get(key);
  if (cached && Date.now() - cached.ts < ttl) return cached.data;
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} returned ${res.status}`);
  const data = await res.json();
  _cache.set(key, { data, ts: Date.now() });
  return data;
}

export interface FundItem { code: string; name: string; value: number; cost: number; pl: number; pl_pct: number; change: string; weight: number; source: string; nav: number; shares: number; }
export interface PortfolioData { total: number; fund_value: number; cash: number; total_cost: number; total_pl: number; total_pl_pct: number; daily_change?: string; date: string; yesterday_pl: number; base_date: string; auto_projected: boolean; annual_return?: number; volatility?: number; sharpe?: number; calmar?: number; var_95?: number; var_99?: number; max_dd?: number; beta?: number; alpha?: number; pending_total: number; pending: any[]; funds: FundItem[]; }
export interface AIData { analysis: string; time: string; }
export type SignalsData = { time: string; signals: any[]; suggestion: string; };
export type MarketData = { time: string; indices: any[]; etfs: any[]; };
export interface AdviceItem { code: string; name: string; action: string; reason: string; confidence: number; risk: string; }
export interface AdvicesData { advices: AdviceItem[]; generated_at: string; }
export interface AttributionData { top_gainers: FundAttribution[]; top_losers: FundAttribution[]; all: FundAttribution[]; }
export interface FundAttribution { code: string; name: string; value: number; pl: number; pl_pct: number; weight: number; contribution: number; }
export interface CompareData { date: string; summary: { portfolio: any; benchmark: any; excess_return_pct: number }; monthly: Record<string, { "组合": number; "沪深300": number; "超额": number }>; cumulative: { "组合": Record<string, number>; "沪深300": Record<string, number> }; }
export interface WSAlert { level: "info" | "warn" | "critical"; title: string; message: string; source: string; created_at: string; code: string; }

export function getPortfolio(): Promise<PortfolioData> { return fetchAPI("/api/portfolio", 10_000); }
export function getAIAnalysis(): Promise<AIData> { return fetchAPI("/api/ai/analysis", 60_000); }
export function getAttribution(): Promise<AttributionData> { return fetchAPI("/api/portfolio/attribution", 30_000); }
export function getHistory(days=90): Promise<{data:any[]}> { return fetchAPI(`/api/portfolio/history?days=${days}`, 120_000); }
export function getPeriods(): Promise<{periods:Record<string,number>,latest_date:string}> { return fetchAPI("/api/portfolio/periods", 60_000); }
export function getCompare(days=365): Promise<CompareData> { return fetchAPI(`/api/compare?days=${days}`, 300_000); }
export function getAdvices(): Promise<AdvicesData> { return fetchAPI("/api/strategy/advices", 60_000); }
export function getTransactions(limit=30): Promise<{transactions:any[]}> { return fetchAPI(`/api/transactions?limit=${limit}`, 30_000); }
export function getMarket(): Promise<MarketData> { return fetchAPI("/api/market", 30_000); }
export function getRisk(): Promise<any> { return fetchAPI("/api/risk", 60_000); }
export function getStockDaily(code: string, days = 120): Promise<any> { return fetchAPI(`/api/stock/${code}/daily?days=${days}`, 60_000); }
export function getConfirmedDaily(): Promise<any> { return fetchAPI("/api/portfolio/confirmed", 10_000); }
