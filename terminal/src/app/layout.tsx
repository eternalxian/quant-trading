import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Quant Terminal",
  description: "AI-Powered Quantitative Trading System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="bg-[#020617] text-[#E2E8F0] overflow-hidden h-screen">
        {children}
      </body>
    </html>
  );
}
