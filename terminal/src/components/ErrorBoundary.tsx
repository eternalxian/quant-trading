"use client";
import React from "react";

interface Props { children: React.ReactNode; fallback?: string; }
interface State { hasError: boolean; }

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) {
      return <div className="text-[10px] text-[#64748B] py-3 text-center glass rounded-xl">{this.props.fallback || "模块暂不可用"}</div>;
    }
    return this.props.children;
  }
}
