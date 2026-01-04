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
from src.utils.api_key import get_api_key_from_state, get_use_openbb_from_state
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


def dan_bin_agent(state: AgentState, agent_id: str = "dan_bin_agent"):
    """
    但斌风格智能体：
    - 偏好优秀的品牌消费、白马龙头，强调"时间的朋友"
    - 接受短期波动，更在意企业长期成长性和护城河
    """
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    massive_api_key = get_api_key_from_state(state, "MASSIVE_API_KEY")
    cn_api_key = get_api_key_from_state(state, "DEEPALPHA_API_KEY")
    use_openbb = get_use_openbb_from_state(state)

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
            massive_api_key=massive_api_key,
            use_openbb=use_openbb,
        )

        if not metrics:
            progress.update_status(agent_id, ticker, "Failed: No financial metrics found")
            continue

        latest = metrics[0]

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key, massive_api_key=massive_api_key, use_openbb=use_openbb)

        facts: dict = {
            "ticker": ticker,
            "market_cap": market_cap,
            "metrics": latest.model_dump(),
        }

        # A 股 / 港股：额外引入资产负债表，帮助判断“白马龙头 + 安心持有”
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
                        "goodwill",
                        "intangible_assets",
                        "loan_advance",
                        "bonds_payable",
                    ]:
                        if hasattr(bs_latest, key):
                            bs_snapshot[key] = getattr(bs_latest, key)
                    facts["cn_balance_sheet"] = {
                        "latest_report_period": getattr(bs_latest, "report_period", None),
                        "core_fields": bs_snapshot,
                    }
            except Exception as e:  # noqa: BLE001
                facts["cn_balance_sheet_error"] = str(e)

        progress.update_status(agent_id, ticker, "Generating Dan Bin analysis")
        # 获取语言设置以决定 checklist 的语言
        language = state.get("metadata", {}).get("language") or "en"
        is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"])
        
        if is_chinese:
            checklist = [
                "公司是否属于各自行业中有品牌力或明显龙头优势的企业（从盈利质量、利润率大致判断）",
                "盈利和分红是否稳定增长，体现出'好公司+好生意'",
                "估值是否处在合理区间，即使不便宜，是否对长期投资仍然可以接受",
                "资产负债表是否稳健，是否适合'长期持股不睡不着觉'",
                "未来5-10年大致还能不能看得见成长空间",
            ]
        else:
            checklist = [
                "Is the company a brand leader or clear industry leader in its sector (judged by profit quality and margins)",
                "Are profits and dividends growing steadily, reflecting 'good company + good business'",
                "Is valuation in a reasonable range, even if not cheap, is it still acceptable for long-term investment",
                "Is the balance sheet solid, suitable for 'long-term holding without losing sleep'",
                "Can we still see growth potential over the next 5-10 years",
            ]
        
        output = _generate_chinese_master_output(
            ticker=ticker,
            facts=facts,
            persona_name="Dan Bin",
            persona_label="Dan Bin",
            investing_style=(
                "Adheres to value investing, prefers consumer, healthcare, and blue-chip leaders. "
                "Willing to be 'friends of time' with excellent companies at reasonable or slightly expensive valuations."
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
        show_agent_reasoning(analysis, "Dan Bin Agent")

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
                    f"You are {persona_name} ({persona_label}), a renowned Chinese value investor.\n"
                    f"Investing style: {investing_style}\n\n"
            "你强调'时间的朋友'，更愿意跟优秀企业一起穿越周期。\n"
                    "只根据提供的数据做判断，不要想象股价走势或编造故事。\n"
                    "请按下面清单思考：\n"
                    f"{checklist_text}\n\n"
                    "输出规则：\n"
                    "- bullish：愿意在当前价格持续加仓、长期持有\n"
                    "- bearish：看不到长期价值或估值过高，不愿参与\n"
                    "- neutral：公司不错但价格或确定性一般，小仓或观望\n"
                    "confidence 用 0-100 的整数。\n"
                    "reasoning 需要详细完整（200-500 字符），必须包含：\n"
                    "  1. 核心分析依据：具体的数据指标、财务表现、估值水平等\n"
                    "  2. 企业质量：业务模式、竞争优势、管理团队等\n"
                    "  3. 时间的朋友：为什么这家公司能穿越周期，长期价值如何\n"
                    "  4. 估值判断：当前价格是否合理，是否值得长期持有\n"
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
        default_reasoning = "公司和估值大致合理，但缺乏足够把握，先保持耐心。"
    else:
        system_prompt = (
            f"You are {persona_name} ({persona_label}), a renowned Chinese value investor.\n"
            f"Investing style: {investing_style}\n\n"
            "You emphasize being 'friends of time', more willing to go through cycles with excellent companies.\n"
            "Only make judgments based on the provided data, do not imagine stock price trends or fabricate stories.\n"
            "Please think using the following checklist:\n"
            f"{checklist_text}\n\n"
            "Output rules:\n"
            "- bullish: Willing to continuously add positions at current price and hold long-term\n"
            "- bearish: Cannot see long-term value or valuation too high, unwilling to participate\n"
            "- neutral: Company is good but price or certainty is average, small position or wait and see\n"
            "confidence should be an integer from 0-100.\n"
            "reasoning should be detailed and complete (200-500 characters), must include:\n"
            "  1. Core analysis basis: Specific data indicators, financial performance, valuation levels, etc.\n"
            "  2. Enterprise quality: Business model, competitive advantages, management team, etc.\n"
            "  3. Friends of time: Why this company can go through cycles, what is the long-term value\n"
            "  4. Valuation judgment: Whether the current price is reasonable, whether it's worth holding long-term\n"
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
        default_reasoning = "Company and valuation are roughly reasonable, but lack sufficient confidence, maintain patience for now."

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



