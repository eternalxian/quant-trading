"use client";

import { useEffect, useRef, useCallback, useState } from "react";

interface WSMessage {
  type: string;
  time: string;
  portfolio?: {
    total: number;
    cash: number;
    pl: number;
    pl_pct: number;
  };
  risk?: {
    closed: boolean;
    reason: string;
    failures: number;
  };
  stocks?: { code: string; name: string; price: number; change_pct: number }[];
  indices?: { name: string; price: number; change: string }[];
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/realtime";

export function useWebSocket(pingInterval = 30000) {
  const wsRef = useRef<WebSocket | null>(null);
  const [data, setData] = useState<WSMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const [latency, setLatency] = useState(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        setData(msg);
        setLatency(Date.now() - new Date(msg.time).getTime());
      } catch {}
    };

    ws.onclose = () => {
      setConnected(false);
      // 自动重连
      setTimeout(connect, 5000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();

    // 心跳
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping");
      }
    }, pingInterval);

    return () => {
      clearInterval(interval);
      wsRef.current?.close();
    };
  }, [connect, pingInterval]);

  return { data, connected, latency };
}
