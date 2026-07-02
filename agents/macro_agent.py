"""宏观分析 Agent — 利率/政策/全球市场"""

import logging
from .base import BaseAgent, AgentResult

logger = logging.getLogger("quant.agent.macro")


class MacroAgent(BaseAgent):
    agent_name = "macro"

    def analyze(self, indices: list[dict] = None, etf_market: list[dict] = None,
                news_headlines: str = "", fed_action: str = "") -> AgentResult:
        """分析宏观环境

        Args:
            indices: 指数行情列表 [{"name": "上证", "change": "-0.22%"}, ...]
            etf_market: ETF行情
            news_headlines: 今日新闻摘要
            fed_action: 美联储动态
        """
        index_text = "\n".join(
            f"  {i.get('name','')}: {i.get('change','')}"
            for i in (indices or [])
        ) or "无指数数据"

        prompt = f"""你是宏观策略分析师。分析当前市场环境：

指数表现：
{index_text}

{"今日要闻: " + news_headlines if news_headlines else ""}
{"美联储: " + fed_action if fed_action else ""}

请输出：
1. 市场阶段判断（牛市/熊市/震荡/高波动）
2. 风险等级（低/中/高）
3. 对A股的影响方向（利多/中性/利空）
4. 对QDII/海外的影响
5. 一句话宏观总结（<30字）

格式：
阶段: [判断]
风险: [低/中/高]
A股影响: [利多/中性/利空]
海外影响: [利多/中性/利空]
总结: [一句话]
"""
        result_text = self._call_llm(prompt)
        sentiment = self._parse_sentiment(result_text)
        confidence = self._parse_confidence(result_text)

        # 提取关键信息
        phase = "震荡"
        risk = "中"
        for line in result_text.split("\n"):
            if "阶段:" in line:
                phase = line.split(":", 1)[1].strip()
            if "风险:" in line:
                risk = line.split(":", 1)[1].strip()

        summary = ""
        for line in result_text.split("\n"):
            if "总结:" in line:
                summary = line.split(":", 1)[1].strip()
                break

        logger.info(f"宏观分析: 阶段{phase} 风险{risk}")
        return AgentResult(
            agent=self.agent_name,
            sentiment=sentiment, confidence=confidence,
            summary=summary or f"市场{phase}, 风险{risk}",
            detail={"phase": phase, "risk": risk, "raw": result_text[:500]},
        )
