"""AI Agent 基类 — 统一接口，结构化输出"""

import logging
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

logger = logging.getLogger("quant.agent")


@dataclass
class AgentResult:
    """所有 Agent 统一输出结构"""
    agent: str
    symbol: str = ""
    sentiment: int = 50           # 0-100，>50看多
    confidence: float = 0.0        # 0-1
    summary: str = ""              # 一句话摘要
    signals: list[str] = field(default_factory=list)  # 结构化信号标签
    detail: dict = field(default_factory=dict)
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class BaseAgent(ABC):
    """Agent 抽象基类"""

    agent_name: str = "base"

    def __init__(self, model: str = None):
        self.model = model or "modelscope.cn/bartowski/Qwen_Qwen3-14B-GGUF:Q4_K_M"

    @abstractmethod
    def analyze(self, **kwargs) -> AgentResult:
        """执行分析，子类必须实现"""
        ...

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """调用本地 LLM"""
        try:
            from ai import ask_model
            return ask_model(prompt, model=self.model)
        except Exception as e:
            logger.error(f"{self.agent_name} LLM调用失败: {e}")
            return ""

    def _parse_sentiment(self, text: str) -> int:
        """从LLM回复中提取情绪值0-100"""
        text_lower = text.lower()
        if "强烈看多" in text or "极度乐观" in text:
            return 85
        if "看多" in text or "偏乐观" in text or "利好" in text:
            return 70
        if "中性" in text or "震荡" in text or "观望" in text:
            return 50
        if "看空" in text or "偏悲观" in text or "利空" in text:
            return 30
        if "强烈看空" in text or "极度悲观" in text:
            return 15
        return 50

    def _parse_confidence(self, text: str) -> float:
        """从LLM回复中提取置信度"""
        import re
        m = re.search(r'置信[度心]?[：:]?\s*(\d+)', text)
        if m:
            return int(m.group(1)) / 100
        m = re.search(r'confidence[：:]?\s*(\d+)', text, re.IGNORECASE)
        if m:
            return int(m.group(1)) / 100
        return 0.5
