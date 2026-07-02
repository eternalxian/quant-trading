"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getStockDaily } from "@/lib/api";

interface KLineChartProps {
  symbol?: string;       // e.g. "603986"
  name?: string;         // e.g. "兆易创新"
  className?: string;
  signalData?: { price?: number; change_pct?: number };
}

interface KLineItem {
  time: number;          // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export default function KLineChart({
  symbol = "603986",
  name = "兆易创新",
  className = "",
  signalData,
}: KLineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<"1M" | "3M" | "6M" | "ALL">("ALL");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chartApiRef = useRef<import("lightweight-charts").IChartApi | null>(null);
  const candleRef = useRef<any>(null);
  const volumeRef = useRef<any>(null);
  const ma5Ref = useRef<any>(null);
  const ma20Ref = useRef<any>(null);

  const daysMap: Record<string, number> = { "1M": 22, "3M": 66, "6M": 132, "ALL": 250 };

  const fetchAndRender = useCallback(async (code: string, days: number) => {
    if (!chartApiRef.current) return;
    setLoading(true);
    setError(null);

    try {
      const res = await getStockDaily(code, days);
      if (!res?.data || res.data.length === 0) {
        setError("无数据");
        setLoading(false);
        return;
      }

      const rawData: KLineItem[] = res.data
        .filter((d: any) => d.open > 0 && d.close > 0)
        .map((d: any) => ({
          time: Math.floor(new Date(d.date).getTime() / 1000),
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
          volume: d.volume || 0,
        }))
        .sort((a: KLineItem, b: KLineItem) => a.time - b.time);

      if (rawData.length === 0) {
        setError("数据为空");
        setLoading(false);
        return;
      }

      const candleSeries = candleRef.current;
      const volumeSeries = volumeRef.current;
      const ma5Series = ma5Ref.current;
      const ma20Series = ma20Ref.current;

      candleSeries?.setData(rawData);
      volumeSeries?.setData(
        rawData.map((d: KLineItem) => ({
          time: d.time,
          value: d.volume,
          color: d.close >= d.open ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
        }))
      );

      // MA5 / MA20
      function calcMA(data: KLineItem[], period: number) {
        return data.map((_, i) => {
          if (i < period - 1) return { time: data[i].time, value: 0 };
          const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b.close, 0);
          return { time: data[i].time, value: sum / period };
        });
      }
      ma5Series?.setData(calcMA(rawData, 5));
      ma20Series?.setData(calcMA(rawData, 20));

      chartApiRef.current?.timeScale().fitContent();
    } catch (e) {
      setError("加载失败");
    }
    setLoading(false);
  }, []);

  // 初始化图表
  useEffect(() => {
    if (!chartRef.current || typeof window === "undefined") return;
    let cancelled = false;

    async function init() {
      const { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } =
        await import("lightweight-charts");
      if (cancelled || !chartRef.current) return;

      const container = chartRef.current;
      const chart = createChart(container, {
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: "#94A3B8",
        },
        grid: {
          vertLines: { color: "rgba(59,130,246,0.06)" },
          horzLines: { color: "rgba(59,130,246,0.06)" },
        },
        crosshair: {
          mode: 0,
          vertLine: { color: "rgba(59,130,246,0.3)", width: 1, style: 2 },
          horzLine: { color: "rgba(59,130,246,0.3)", width: 1, style: 2 },
        },
        rightPriceScale: {
          borderColor: "rgba(59,130,246,0.15)",
          scaleMargins: { top: 0.1, bottom: 0.3 },
        },
        timeScale: {
          borderColor: "rgba(59,130,246,0.15)",
          timeVisible: true,
          secondsVisible: false,
        },
        handleScroll: { vertTouchDrag: false },
      });

      chartApiRef.current = chart;
      candleRef.current = chart.addSeries(CandlestickSeries, {
        upColor: "#EF4444",
        downColor: "#22C55E",
        borderUpColor: "#EF4444",
        borderDownColor: "#22C55E",
        wickUpColor: "#EF4444",
        wickDownColor: "#22C55E",
      });
      volumeRef.current = chart.addSeries(HistogramSeries, {
        color: "rgba(59,130,246,0.25)",
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
      ma5Ref.current = chart.addSeries(LineSeries, {
        color: "#F59E0B", lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
      });
      ma20Ref.current = chart.addSeries(LineSeries, {
        color: "#8B5CF6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
      });

      const handleResize = () => {
        if (container) chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
      };
      window.addEventListener("resize", handleResize);
    }

    init();
    return () => {
      cancelled = true;
      chartApiRef.current?.remove();
      chartApiRef.current = null;
    };
  }, []);

  // 当 symbol 或 activeTab 变化时拉数据
  useEffect(() => {
    if (!symbol || !chartApiRef.current) return;
    const days = daysMap[activeTab] || 250;
    fetchAndRender(symbol, days);
  }, [symbol, activeTab, fetchAndRender]);

  const displayName = name || symbol;

  return (
    <div className={`glass rounded-xl p-4 flex flex-col ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-[#E2E8F0] font-mono">
            {displayName}
          </h3>
          <span className="text-[10px] text-[#64748B] font-mono">{symbol}</span>
          <span className="text-xs text-[#94A3B8]">日K</span>
          {loading && <span className="text-[10px] text-[#F59E0B] animate-pulse">加载中...</span>}
          {error && <span className="text-[10px] text-[#EF4444]">{error}</span>}
          {signalData?.price != null && (
            <span className="text-xs text-[#EF4444] font-mono">
              ¥{signalData.price.toFixed(2)}
            </span>
          )}
          {signalData?.change_pct != null && (
            <span
              className={`text-xs font-mono ${
                signalData.change_pct >= 0 ? "text-[#EF4444]" : "text-[#22C55E]"
              }`}
            >
              {signalData.change_pct >= 0 ? "+" : ""}
              {signalData.change_pct.toFixed(2)}%
            </span>
          )}
        </div>
        <div className="flex gap-1">
          {["1M", "3M", "6M", "ALL"].map((t) => (
            <button
              key={t}
              onClick={() => setActiveTab(t as typeof activeTab)}
              className={`px-2 py-0.5 text-[10px] rounded-md font-mono transition-all ${
                activeTab === t
                  ? "bg-[#3B82F6] text-white shadow-[0_0_8px_rgba(59,130,246,0.3)]"
                  : "text-[#64748B] hover:text-[#94A3B8] hover:bg-white/5"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div ref={chartRef} className="flex-1 min-h-[380px]" />
    </div>
  );
}
