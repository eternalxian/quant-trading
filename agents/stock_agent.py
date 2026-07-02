"""股票分析 Agent — 技术面+情绪面"""

import logging
from .base import BaseAgent, AgentResult

logger = logging.getLogger("quant.agent.stock")


class StockAgent(BaseAgent):
    agent_name = "stock"

    def analyze(self, code: str, name: str = "", kline_summary: str = "",
                news: str = "", fund_holding: str = "") -> AgentResult:
        """分析单只股票

        Args:
            code: 股票代码
            name: 股票名称
            kline_summary: 技术指标摘要（MA/MACD/RSI等）
            news: 相关新闻
            fund_holding: 基金持仓穿透信息
        """
        if not kline_summary:
            return AgentResult(
                agent=self.agent_name, symbol=code,
                sentiment=50, confidence=0, summary="无技术数据",
            )

        prompt = f"""你是A股技术分析师。分析以下股票：

股票: {name}({code})
技术指标: {kline_summary}
{"相关新闻: " + news if news else ""}
{"基金持仓: " + fund_holding if fund_holding else ""}

请输出：
1. 技术面判断（看多/看空/中性）
2. 置信度（0-100）
3. 一句话摘要（<30字）
4. 关键信号标签（如：MACD金叉、放量突破、RSI超卖等）

格式：
判断: [看多/看空/中性]
置信度: [数字]
摘要: [一句话]
信号: [标签1, 标签2, ...]
"""
        result_text = self._call_llm(prompt)

        sentiment = self._parse_sentiment(result_text)
        confidence = self._parse_confidence(result_text)

        # 提取信号标签
        signals = []
        for line in result_text.split("\n"):
            if "信号:" in line or "标签:" in line:
                tags = line.split(":", 1)[1] if ":" in line else ""
                signals = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
                break

        # 提取摘要
        summary = ""
        for line in result_text.split("\n"):
            if "摘要:" in line:
                summary = line.split(":", 1)[1].strip()
                break

        logger.info(f"股票分析 {code}: 情绪{sentiment} 置信{confidence:.0%}")
        return AgentResult(
            agent=self.agent_name, symbol=code,
            sentiment=sentiment, confidence=confidence,
            summary=summary or result_text[:50],
            signals=signals,
            detail={"raw": result_text[:500]},
        )

    def analyze_batch(self, stocks: list[dict], top_n: int = 5) -> list[AgentResult]:
        """批量分析多只股票，返回top_n"""
        results = []
        for s in stocks[:top_n]:
            try:
                r = self.analyze(
                    code=s.get("code", ""), name=s.get("name", ""),
                    kline_summary=s.get("kline_summary", ""),
                    fund_holding=s.get("fund_holding", ""),
                )
                results.append(r)
            except Exception as e:
                logger.warning(f"分析 {s.get('code')} 失败: {e}")
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results
