"""
AI 分析层：调用本地 Ollama 模型分析数据和市场
"""
import requests
import json
from strategies_db import get_strategies, get_strategy_signals


OLLAMA_URL = "http://localhost:11434/api/generate"
# 从 modelscope 拉取的模型名包含完整路径
DEFAULT_MODEL = "modelscope.cn/bartowski/Qwen_Qwen3-14B-GGUF:Q4_K_M"
REASONING_MODEL = "modelscope.cn/lmstudio-community/DeepSeek-R1-Distill-Qwen-14B-GGUF:Q4_K_M"


def ask_model(prompt: str, model: str = DEFAULT_MODEL, stream: bool = False) -> str:
    """调用本地 Ollama 模型"""
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": 0.3,   # 低温度 = 更严谨
                "num_predict": 2048,
            }
        }, timeout=120)

        if stream:
            result = ""
            for line in r.text.strip().split("\n"):
                if line:
                    data = json.loads(line)
                    result += data.get("response", "")
                    if data.get("done"):
                        break
            return result
        else:
            return r.json().get("response", "")
    except requests.exceptions.ConnectionError:
        return "[错误] 无法连接到 Ollama，请确认已启动: ollama serve"
    except Exception as e:
        return f"[错误] AI调用失败: {e}"


# ── 预设分析提示词 ──

def build_market_prompt(market_report: dict) -> str:
    """生成市场分析提示"""
    text = f"""你现在是一个专业的基金投资顾问。请基于以下市场数据，给出简洁的分析和操作建议。

时间：{market_report['时间']}

指数表现：
{chr(10).join(f"  {i['name']}: {i['price']} ({i['change']})" for i in market_report['指数'])}

关注 ETF 表现：
{chr(10).join(f"  {e['name']}({e['code']}): {e['close']} ({e['change']})" for e in market_report['ETF'])}

请分析：
1. 今日市场整体情绪如何
2. 哪些板块表现较强/较弱
3. 对 QDII 基金（纳指/标普）的影响
4. 对我持有的科技/半导体/通信方向的影响
5. 今日是否适合操作，建议观望还是执行交易

要求：简洁，每条1-2句话，不要长篇大论。
"""
    return text


def build_strategy_context() -> str:
    """从策略数据库读取可用策略，生成 AI 可读的上下文"""
    strategies = get_strategies()
    if not strategies:
        return ""

    lines = ["", "--- 可用量化策略库 ---"]

    # 按类型分组
    by_type = {}
    for s in strategies:
        by_type.setdefault(s["type"], []).append(s)

    for typ, items in by_type.items():
        lines.append(f"\n[{typ}]")
        for s in items:
            lines.append(f"  - {s['name']}: {s['description'][:80]}")
            if s.get("source") and s["source"] != "通用策略":
                lines[-1] += f" (来源: {s['source']})"

    # 最近信号
    signals = get_strategy_signals(limit=10)
    if signals:
        lines.append(f"\n[最近策略信号]")
        for sig in signals[:5]:
            lines.append(f"  {sig['date']} {sig['strategy_name']} → {sig['code']}: {sig['signal']} (评分{sig['score']})")

    lines.append("\n请结合以上策略库中的方法，在分析中引用适用的策略逻辑。")
    return "\n".join(lines)


def build_portfolio_prompt(portfolio_summary: dict, market_report: dict) -> str:
    """生成持仓分析提示"""
    # 基金持仓文本
    fund_lines = []
    for item in portfolio_summary["基金"]:
        fund_lines.append(f"  {item['code']} {item['name']}: {item['市值']}元, 涨跌{item['涨跌']}, 占比{item['占比']}%")

    fund_text = chr(10).join(fund_lines)

    # 市场文本
    index_text = chr(10).join(f"  {i['name']}: {i['price']} ({i['change']})" for i in market_report['指数'])
    etf_text = chr(10).join(f"  {e['name']}({e['code']}): {e['close']} ({e['change']})" for e in market_report['ETF'])

    prompt = f"""你现在是一个专业的基金投资顾问。请基于以下数据，分析我的持仓状况并给出建议。

持仓组合：
{fund_text}

总资产：{portfolio_summary['总资产']}元（日涨跌：{portfolio_summary['日涨跌']}%）
余额宝：{portfolio_summary['余额宝']}元

市场概况：
指数：
{index_text}

ETF：
{etf_text}{build_strategy_context()}

请分析：
1. 今日组合整体表现如何
2. 哪支基金拖累/贡献最多
3. 当前仓位是否合理（科技/AI/半导体集中度偏高的问题）
4. 今天建议增持/减持/观望哪些方向，可以引用量化策略库中的策略信号来支撑判断
5. 一句话总结今日策略

要求：简洁，每条1-2句话，给出具体操作建议，必要时可以引用具体策略名称。
"""
    return prompt


def build_analysis_prompt(signal_summary: str = "") -> str:
    """生成纯策略分析提示（不依赖持仓/市场）"""
    context = build_strategy_context()
    prompt = f"""你是一个量化策略分析师。{context}

当前ETF轮动信号：{signal_summary or "暂无"}

请分析：
1. 当前市场适合哪种类型的策略（趋势跟踪/轮动/技术指标）
2. 量化策略库中有哪些策略适应当前行情
3. 是否出现多策略共振信号
4. 建议重点关注的方向

要求：200字以内。
"""
    return prompt
