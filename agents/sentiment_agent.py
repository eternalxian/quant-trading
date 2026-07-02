"""新闻情绪 Agent — 财经新闻解读+情绪评分"""

import logging
from .base import BaseAgent, AgentResult

logger = logging.getLogger("quant.agent.sentiment")


class SentimentAgent(BaseAgent):
    agent_name = "sentiment"

    def analyze(self, headlines: str = "", sector_news: str = "",
                market_summary: str = "") -> AgentResult:
        """分析市场情绪

        Args:
            headlines: 今日新闻标题（多条换行分隔）
            sector_news: 特定板块新闻
            market_summary: 市场概况
        """
        if not headlines:
            return AgentResult(
                agent=self.agent_name,
                sentiment=50, confidence=0, summary="无新闻数据",
            )

        prompt = f"""你是财经新闻情绪分析师。分析以下新闻对市场的影响：

今日新闻：
{headlines[:1000]}

{"板块新闻: " + sector_news if sector_news else ""}
{"市场概况: " + market_summary if market_summary else ""}

请输出：
1. 整体情绪（乐观/中性/悲观）
2. 情绪评分（0-100，>50偏乐观）
3. 最利好板块
4. 最利空板块
5. 一句话情绪总结（<30字）

格式：
情绪: [乐观/中性/悲观]
评分: [0-100]
利好板块: [板块名]
利空板块: [板块名]
总结: [一句话]
"""
        result_text = self._call_llm(prompt, temperature=0.3)

        sentiment = self._parse_sentiment(result_text)
        confidence = self._parse_confidence(result_text)

        # 提取评分
        import re
        m = re.search(r'评分[：:]?\s*(\d+)', result_text)
        if m:
            sentiment = int(m.group(1))

        # 提取利好/利空板块
        bullish = ""
        bearish = ""
        for line in result_text.split("\n"):
            if "利好板块" in line:
                bullish = line.split(":", 1)[1].strip() if ":" in line else ""
            if "利空板块" in line:
                bearish = line.split(":", 1)[1].strip() if ":" in line else ""

        summary = ""
        for line in result_text.split("\n"):
            if "总结:" in line:
                summary = line.split(":", 1)[1].strip()
                break

        logger.info(f"情绪分析: {sentiment}/100")
        return AgentResult(
            agent=self.agent_name,
            sentiment=sentiment, confidence=confidence,
            summary=summary or result_text[:50],
            detail={
                "bullish_sector": bullish,
                "bearish_sector": bearish,
                "raw": result_text[:500],
            },
        )
