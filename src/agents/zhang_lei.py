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


def zhang_lei_agent(state: AgentState, agent_id: str = "zhang_lei_agent"):
    """
    张磊风格智能体：
    - 关注长期复利能力，强调"好公司 + 好价格 + 足够长的时间"
    - 偏好有全球视野、优秀管理层和清晰成长空间的公司
    """
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    cn_api_key = get_api_key_from_state(state, "DEEPALPHA_API_KEY")

    analysis: dict[str, dict] = {}

    for ticker in tickers:
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

        # A 股 / 港股：额外引入资产负债表，帮张磊看“复利质量”和资产结构
        if _looks_like_cn_or_hk_ticker(ticker):
            try:
                progress.update_status(agent_id, ticker, "Fetching CN/HK balance sheet (DeepAlpha)")
                cn_items = get_cn_balance_sheet_line_items(ticker, api_key=cn_api_key)
                if cn_items:
                    bs_latest = cn_items[0]
                    bs_snapshot = {}
                    for key in [
                        "t_assets",
                        "t_liability",
                        "t_equity",
                        "loan_advance",
                        "debt_invest",
                        "other_debt_invest",
                        "goodwill",
                        "intangible_assets",
                    ]:
                        if hasattr(bs_latest, key):
                            bs_snapshot[key] = getattr(bs_latest, key)
                    facts["cn_balance_sheet"] = {
                        "latest_report_period": getattr(bs_latest, "report_period", None),
                        "core_fields": bs_snapshot,
                    }
            except Exception as e:  # noqa: BLE001
                facts["cn_balance_sheet_error"] = str(e)

        progress.update_status(agent_id, ticker, "Generating Zhang Lei analysis")
        # 获取语言设置以决定 checklist 的语言
        language = state.get("metadata", {}).get("language") or "en"
        is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"])
        
        if is_chinese:
            checklist = [
                "收入、利润和自由现金流是否持续多年双位数增长",
                "商业模式是否有网络效应、规模效应或技术壁垒",
                "管理层是否重视长期投入，而不是短期利润冲高",
                "估值相对于成长和行业空间是否可以接受",
                "是否具备全球视野或行业龙头潜质",
            ]
        else:
            checklist = [
                "Are revenue, profit, and free cash flow consistently growing at double-digit rates for multiple years",
                "Does the business model have network effects, scale effects, or technological barriers",
                "Does management focus on long-term investment rather than short-term profit maximization",
                "Is valuation acceptable relative to growth and industry potential",
                "Does the company have global vision or industry leadership potential",
            ]
        
        output = _generate_chinese_master_output(
            ticker=ticker,
            facts=facts,
            persona_name="Zhang Lei",
            persona_label="Zhang Lei",
            investing_style=(
                "Long-term capital position manager, emphasizes compounding ability across cycles. "
                "Seeks companies with global competitiveness, excellent management, and long-term growth potential. "
                "Willing to take significant positions at reasonable or slightly expensive prices."
            ),
            checklist=checklist,
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
        show_agent_reasoning(analysis, "Zhang Lei Agent")

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

    # 获取语言设置
    language = state.get("metadata", {}).get("language") or "en"
    is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"])

    checklist_text = "\n".join(f"- {item}" for item in checklist)

    # 根据语言生成不同的 prompt
    if is_chinese:
        system_prompt = (
                    f"You are {persona_name} ({persona_label}), a renowned Chinese long-term investor.\n"
                    f"Investing style: {investing_style}\n\n"
                    "只根据提供的定量/定性信息做判断，不要自己幻想数据。\n"
                    "请用下面的检查清单来思考：\n"
                    f"{checklist_text}\n\n"
                    "输出规则：\n"
                    "- bullish：愿意长期重仓或显著加仓\n"
                    "- bearish：不愿持有/会明显减仓\n"
                    "- neutral：观望或小仓位试错\n"
                    "confidence 用 0-100 的整数。\n"
                    "reasoning 需要详细完整（200-500 字符），要求专业但通俗，必须包含：\n"
                    "  1. 核心分析依据：具体的数据指标、财务表现、估值水平等\n"
                    "  2. 企业质量：业务模式、竞争优势、复利能力等\n"
                    "  3. 长期复利：为什么这家公司能持续创造价值，复利逻辑是什么\n"
            "  4. 估值判断：当前价格是否合理，是否符合'好公司+好价格+长时间'的标准\n"
                    "  5. 风险提示：需要注意的风险点\n"
                    "  6. 结论：明确的投资建议和理由\n"
                    "只返回 JSON。"
        )
        human_prompt = (
                "Ticker: {ticker}\n\n"
                "Facts (do not invent new data):\n"
                "{facts}\n\n"
                "Return exactly:\n"
                "{{\n"
                '  "signal": "bullish" | "bearish" | "neutral",\n'
                '  "confidence": int,\n'
                '  "reasoning": "short justification in Chinese"\n'
            "}}"
        )
        default_reasoning = "数据有限，看不清未来复利能力，暂时观望。"
    else:
        system_prompt = (
            f"You are {persona_name} ({persona_label}), a renowned Chinese long-term investor.\n"
            f"Investing style: {investing_style}\n\n"
            "Only make judgments based on the provided quantitative/qualitative information, do not fabricate data.\n"
            "Please think using the following checklist:\n"
            f"{checklist_text}\n\n"
            "Output rules:\n"
            "- bullish: Willing to hold long-term with heavy positions or significantly add positions\n"
            "- bearish: Unwilling to hold or will significantly reduce positions\n"
            "- neutral: Wait and see or try with small positions\n"
            "confidence should be an integer from 0-100.\n"
            "reasoning should be detailed and complete (200-500 characters), professional but accessible, must include:\n"
            "  1. Core analysis basis: Specific data indicators, financial performance, valuation levels, etc.\n"
            "  2. Enterprise quality: Business model, competitive advantages, compounding ability, etc.\n"
            "  3. Long-term compounding: Why this company can continuously create value, what is the compounding logic\n"
            "  4. Valuation judgment: Whether the current price is reasonable, does it meet the standard of 'good company + good price + long time'\n"
            "  5. Risk warning: Risk points to pay attention to\n"
            "  6. Conclusion: Clear investment recommendation and reasoning\n"
            "Return JSON only."
        )
        human_prompt = (
            "Ticker: {ticker}\n\n"
            "Facts (do not invent new data):\n"
            "{facts}\n\n"
            "Return exactly:\n"
            "{{\n"
            '  "signal": "bullish" | "bearish" | "neutral",\n'
            '  "confidence": int,\n'
            '  "reasoning": "short justification in English"\n'
            "}}"
        )
        default_reasoning = "Limited data available, unable to assess future compounding ability, wait and see for now."

    template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human_prompt),
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
            reasoning=default_reasoning,
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=ChineseMasterSignal,
        agent_name=agent_id,
        state=state,
        default_factory=default_signal,
    )



