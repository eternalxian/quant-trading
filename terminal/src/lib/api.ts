const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} returned ${res.status}`);
  return res.json();
}

export interface FundItem {
  code: string;
  name: string;
  value: number;
  cost: number;
  pl: number;
  pl_pct: number;
  change: string;
  weight: number;
}

export interface PendingItem {
  code: string;
  name: string;
  amount: number;
  date: string;
}

export interface PortfolioData {
  total: number;
  fund_value: number;
  cash: number;
  total_cost: number;
  total_pl: number;
  total_pl_pct: number;
  daily_change: string;
  date: string;
  pending_total: number;
  pending: PendingItem[];
  funds: FundItem[];
}

export interface SignalItem {
  code: string;
  name: string;
  score: number;
  momentum: string;
  action: string;
  reason: string;
}

export interface SignalsData {
  time: string;
  signals: SignalItem[];
  suggestion: string;
}

export interface MarketIndex {
  name: string;
  price: number;
  change: string;
}

export interface MarketETF {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  volume?: number;
  amount?: number;
}

export interface MarketData {
  time: string;
  indices: MarketIndex[];
  etfs: MarketETF[];
}

export interface StockSpot {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  volume?: number;
  amount?: number;
  turnover?: number;
  score?: number;
  buy?: number;
  sell?: number;
}

export interface StockRankItem {
  code: string;
  name: string;
  score: number;
  buy: number;
  sell: number;
  hold: number;
  total: number;
}

export interface StockSignalsData {
  rank: StockRankItem[];
  details: Record<string, { strategy: string; signal: string; score: number; reason: string }[]>;
}

export interface AIData {
  analysis: string;
  time: string;
}

// ── API 调用 ──

export function getPortfolio(): Promise<PortfolioData> {
  return fetchAPI("/api/portfolio");
}

export function getMarket(): Promise<MarketData> {
  return fetchAPI("/api/market");
}

export function getSignals(): Promise<SignalsData> {
  return fetchAPI("/api/signals");
}

export function getStockSpot(): Promise<{ stocks: StockSpot[] }> {
  return fetchAPI("/api/stock/spot");
}

export function getStockSignals(): Promise<StockSignalsData> {
  return fetchAPI("/api/stock/signals");
}

export function getStockDaily(code: string, days = 120): Promise<{ data: { date: string; open: number; high: number; low: number; close: number; volume: number }[] }> {
  return fetchAPI(`/api/stock/${code}/daily?days=${days}`);
}

export function getAIAnalysis(): Promise<AIData> {
  return fetchAPI("/api/ai/analysis");
}

export function getRisk(): Promise<any> {
  return fetchAPI("/api/risk");
}

export function getHoldings(): Promise<any> {
  return fetchAPI("/api/holdings");
}

export interface TradeAdviceItem {
  code: string;
  name: string;
  action: string;
  amount: number;
  reason: string;
  confidence: number;
  priority: number;
  risk_ok: boolean;
  risk_detail: string;
}

export interface TradeAdvicesData {
  time: string;
  suggestion: string;
  advices: TradeAdviceItem[];
}

export function getTradeAdvices(): Promise<TradeAdvicesData> {
  return fetchAPI("/api/strategy/advices");
}

export interface RiskStatus {
  circuit: { closed: boolean; opened_at: string | null; reason: string; failures: number };
  rules: Record<string, number>;
}

export function getRiskStatus(): Promise<RiskStatus> {
  return fetchAPI("/api/risk/status");
}

export function getConfirmedDaily(): Promise<{ pl: number; pl_pct: number; date: string }> {
  return fetchAPI("/api/portfolio/confirmed");
}

export function confirmDailyPL(pl: number, pl_pct: number): Promise<any> {
  return fetch(`${API_BASE}/api/portfolio/confirm-daily?pl=${pl}&pl_pct=${pl_pct}`, { method: "POST" }).then(r => r.json());
}

export interface DailyEstimate {
  date: string;
  total_est: number;
  funds: { code: string; name: string; value: number; etf_code: string; etf_change: number; est_pl: number }[];
}

export function getDailyEstimate(date?: string): Promise<DailyEstimate> {
  const params = date ? `?date=${date}` : "";
  return fetchAPI(`/api/estimate/daily${params}`);
}
