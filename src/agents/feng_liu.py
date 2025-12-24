from typing_extensions import Literal

import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    get_cn_balance_sheet_line_items,
)
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class ChineseMasterSignal(BaseModel):
    """Standard signal schema for Chinese investing masters."""

    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Short reasoning for the decision")


def _looks_like_cn_or_hk_ticker(ticker: str) -> bool:
    """
    粗略判断是否是 A 股 / 港股代码：
    - 纯数字（如 600000, 000001）
    - 以 .SH / .SZ / .HK 结尾
    """
    t = ticker.upper()
    if t.endswith((".SH", ".SZ", ".HK")):
        return True
    return t.isdigit()


def feng_liu_agent(state: AgentState, agent_id: str = "feng_liu_agent"):
    """
    冯柳风格智能体：
    - 逆向、耐心，喜欢在市场误解和情绪极端时慢慢建仓
    - 更关注"预期差"和企业真实内在变化，而不是短期故事
    """
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    cn_api_key = get_api_key_from_state(state, "DEEPALPHA_API_KEY")

    analysis: dict[str, dict] = {}

    for ticker in tickers:
        # 1. 先拿通用财务指标（覆盖美股等）
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=4,
            api_key=api_key,
            cn_api_key=cn_api_key,
        )

        if not metrics:
            progress.update_status(agent_id, ticker, "Failed: No financial metrics found")
            continue

        latest = metrics[0]

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        facts: dict = {
            "ticker": ticker,
            "market_cap": market_cap,
            "metrics": latest.model_dump(),
        }

        # 2. 如果像是 A 股 / 港股代码，则尝试额外加载 DeepAlpha 资产负债表，增强“预期差”判断
        if _looks_like_cn_or_hk_ticker(ticker):
            try:
                progress.update_status(agent_id, ticker, "Fetching CN/HK balance sheet (DeepAlpha)")
                cn_items = get_cn_balance_sheet_line_items(ticker, api_key=cn_api_key)
                if cn_items:
                    bs_latest = cn_items[0]
                    # 只挑一些典型字段，避免 prompt 太长；完整字段仍然在 bs_latest 中，可按需扩展
                    bs_snapshot = {}
                    for key in [
                        "t_assets",
                        "t_liability",
                        "t_equity",
                        "loan_advance",
                        "deposit",
                        "deposit_inter",
                        "bonds_payable",
                        "estimate_liability",
                    ]:
                        if hasattr(bs_latest, key):
                            bs_snapshot[key] = getattr(bs_latest, key)
                    facts["cn_balance_sheet"] = {
                        "latest_report_period": getattr(bs_latest, "report_period", None),
                        "core_fields": bs_snapshot,
                    }
            except Exception as e:  # noqa: BLE001
                # DeepAlpha 失败时不阻塞整体分析，只记录一个轻量级标记
                facts["cn_balance_sheet_error"] = str(e)

        progress.update_status(agent_id, ticker, "Generating Feng Liu analysis")
        output = _generate_chinese_master_output(
            ticker=ticker,
            facts=facts,
            persona_name="Feng Liu",
            persona_label="Feng Liu",
            investing_style=(
                "Contrarian and patient, seeks companies misunderstood by the market but with quietly improving fundamentals. "
                "Willing to hold through long periods of sideways movement and volatility, as long as direction and intrinsic value are gradually improving."
            ),
            checklist=[
                "基本面是否在缓慢改善（盈利、现金流、负债结构等）",
                "当前估值是否明显低于历史或内在价值区间",
                "市场情绪是否偏极端悲观，但数据并未那么糟糕",
                "企业是否有自我修复能力，商业模式是否在变好",
                "自己是否愿意忍受几年不涨甚至波动下跌",
            ],
            agent_id=agent_id,
            state=state,
        )

        analysis[ticker] = {
            "signal": output.signal,
            "confidence": output.confidence,
            "reasoning": output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=output.reasoning)

    message = HumanMessage(content=json.dumps(analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(analysis, "Feng Liu Agent")

    state["data"]["analyst_signals"][agent_id] = analysis
    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def _generate_chinese_master_output(
    ticker: str,
    facts: dict,
    persona_name: str,
    persona_label: str,
    investing_style: str,
    checklist: list[str],
    agent_id: str,
    state: AgentState,
) -> ChineseMasterSignal:
    """让 LLM 按指定中国投资大师的风格，给出多空观点。"""

    checklist_text = "\n".join(f"- {item}" for item in checklist)

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    f"You are {persona_name} ({persona_label}), a renowned Chinese contrarian long-term investor.\n"
                    f"Investing style: {investing_style}\n\n"
                    "你更关心“预期差”和企业真实变化，而不是短期故事和情绪。\n"
                    "只看给你的数据，不要胡编股价、K线或新闻。\n"
                    "请按下面清单思考：\n"
                    f"{checklist_text}\n\n"
                    "输出规则：\n"
                    "- bullish：预期差大、内在在变好，愿意慢慢买入并长期持有\n"
                    "- bearish：看不到改善或预期过高，不愿意参与\n"
                    "- neutral：方向不明或好坏对半，看不出大的预期差\n"
                    "confidence 用 0-100 的整数。\n"
                    "reasoning 需要详细完整（200-500 字符），必须包含：\n"
                    "  1. 核心分析依据：具体的数据指标、财务表现、估值水平等\n"
                    "  2. 预期差分析：市场预期与实际情况的差异\n"
                    "  3. 企业变化：业务、财务、管理等方面的真实变化\n"
                    "  4. 投资逻辑：为什么做出这个判断，基于哪些关键因素\n"
                    "  5. 风险提示：需要注意的风险点\n"
                    "  6. 结论：明确的投资建议和理由\n"
                    "只返回 JSON。"
                ),
            ),
            (
                "human",
                "Ticker: {ticker}\n\n"
                "Facts (do not invent new data):\n"
                "{facts}\n\n"
                "Return exactly:\n"
                "{{\n"
                '  "signal": "bullish" | "bearish" | "neutral",\n'
                '  "confidence": int,\n'
                '  "reasoning": "short justification in Chinese"\n'
                "}}",
            ),
        ]
    )

    prompt = template.invoke(
        {
            "ticker": ticker,
            "facts": json.dumps(facts, ensure_ascii=False, separators=(",", ":")),
        }
    )

    def default_signal() -> ChineseMasterSignal:
        return ChineseMasterSignal(
            signal="neutral",
            confidence=50,
            reasoning="暂未看到明显预期差，用小仓位或继续观察更合适。",
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=ChineseMasterSignal,
        agent_name=agent_id,
        state=state,
        default_factory=default_signal,
    )



