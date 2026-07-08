"use client";
import { useEffect, useState, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function FundDetails({ code, name }: { code: string; name: string }) {
  const [state, setState] = useState("loading"); // loading|ok|qdii|short|notfound|error
  const [info, setInfo] = useState<any>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartApi = useRef<any>(null);

  // Effect 1: 数据请求，只负责设置 info/state
  useEffect(() => {
    let cancelled = false;
    setState("loading"); setInfo(null);

    async function load() {
      try {
        const r = await fetch(API + "/api/fund/" + encodeURIComponent(code) + "/kline?days=90");
        if (!r.ok) { if (!cancelled) setState(r.status === 404 ? "notfound" : "error"); return; }
        const d = await r.json();
        if (cancelled) return;
        if (!d.data || d.data.length < 5) { setInfo(d); setState("short"); return; }

        // QDII check
        try {
          const nf = await fetch(API + "/api/funds/nav-freshness").then(r => r.json());
          setInfo(d);
          setState(nf && nf[code] && nf[code].type === "QDII" ? "qdii" : "ok");
        } catch { setInfo(d); setState("ok"); }
      } catch { if (!cancelled) setState("error"); }
    }
    load();
    return () => { cancelled = true; };
  }, [code]);

  // Effect 2: 图表渲染，依赖 info + state
  useEffect(() => {
    if (!chartRef.current) return;
    if (state !== "ok" && state !== "qdii") return; // only render chart when data is ready
    if (!info?.data?.length) return;

    let cancelled = false;

    async function render() {
      const { createChart, ColorType, LineSeries } = await import("lightweight-charts");
      if (cancelled) return;

      // 清理旧图表
      if (chartApi.current) { chartApi.current.remove(); chartApi.current = null; }
      chartRef.current!.innerHTML = "";

      const chart = createChart(chartRef.current!, {
        layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94A3B8" },
        grid: { vertLines: { color: "rgba(59,130,246,0.06)" }, horzLines: { color: "rgba(59,130,246,0.06)" } },
        rightPriceScale: { borderColor: "rgba(59,130,246,0.15)" },
        timeScale: { borderColor: "rgba(59,130,246,0.15)" },
        width: chartRef.current!.clientWidth, height: 180,
      });
      chartApi.current = chart;
      const line = chart.addSeries(LineSeries, { color: "#3B82F6", lineWidth: 2 });
      line.setData(info.data.map((p: any) => ({ time: p.date, value: p.nav })));
      chart.timeScale().fitContent();
    }
    render();

    return () => {
      cancelled = true;
      if (chartApi.current) { chartApi.current.remove(); chartApi.current = null; }
    };
  }, [info, state]);

  const statusUI: Record<string, React.ReactNode> = {
    loading: <div className="text-[10px] text-[#64748B] py-6 text-center">正在加载净值曲线</div>,
    notfound: <div className="text-[10px] text-[#64748B] py-6 text-center">基金不存在或暂无净值数据</div>,
    error: <div className="text-[10px] text-[#64748B] py-6 text-center">单基金曲线暂不可用</div>,
    short: <div className="text-[10px] text-[#64748B] py-6 text-center">历史净值不足</div>,
    qdii: (
      <div>
        <div className="text-[9px] text-[#F59E0B] mb-1">QDII 净值存在自然披露延迟（最新: {info?.latest_date}）</div>
        <div ref={chartRef} style={{ height: 180 }} />
      </div>
    ),
    ok: <div ref={chartRef} style={{ height: 180 }} />,
  };

  return (
    <div>
      {info?.metrics && (
        <div className="flex gap-4 text-[10px] mb-2">
          <span className="text-[#64748B]">区间收益 <span className="text-[#E2E8F0] font-mono">{info.metrics.period_return}%</span></span>
          <span className="text-[#64748B]">最大回撤 <span className="text-[#F59E0B] font-mono">{info.metrics.max_drawdown}%</span></span>
          <span className="text-[#64748B]">波动率 <span className="text-[#E2E8F0] font-mono">{info.metrics.volatility}%</span></span>
        </div>
      )}
      {statusUI[state] || statusUI.error}
    </div>
  );
}
