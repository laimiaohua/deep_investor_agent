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


def qiu_guolu_agent(state: AgentState, agent_id: str = "qiu_guolu_agent"):
    """
    邱国鹭风格智能体：
    - 自上而下 + 自下而上结合，强调宏观周期与行业景气度
    - 看重估值与安全边际，在悲观时布局，在乐观时收缩
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

        # A 股 / 港股：额外引入资产负债表，帮助判断“周期+安全边际”
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
                        "deposit",
                        "deposit_inter",
                        "bonds_payable",
                        "other_liability",
                    ]:
                        if hasattr(bs_latest, key):
                            bs_snapshot[key] = getattr(bs_latest, key)
                    facts["cn_balance_sheet"] = {
                        "latest_report_period": getattr(bs_latest, "report_period", None),
                        "core_fields": bs_snapshot,
                    }
            except Exception as e:  # noqa: BLE001
                facts["cn_balance_sheet_error"] = str(e)

        progress.update_status(agent_id, ticker, "Generating Qiu Guolu analysis")
        output = _generate_chinese_master_output(
            ticker=ticker,
            facts=facts,
            persona_name="Qiu Guolu",
            persona_label="Qiu Guolu",
            investing_style=(
                "Top-down analysis of macro and industry cycles, bottom-up stock selection. "
                "Emphasizes buying during pessimism and selling during optimism, pursuing safety margin and risk-reward ratio."
            ),
            checklist=[
                "行业当前大致处于景气上行、平台还是下行阶段（根据增长与利润率大致判断）",
                "公司在行业中的竞争地位和盈利质量是否明显优于同类",
                "估值指标（PE、PB、PS等）相对历史和成长是否偏低",
                "资产负债表是否稳健，抗周期能力如何",
                "当前阶段更像“悲观定价”还是“乐观定价”",
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
        show_agent_reasoning(analysis, "Qiu Guolu Agent")

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
                    f"You are {persona_name} ({persona_label}), a renowned Chinese value & macro-cycle investor.\n"
                    f"Investing style: {investing_style}\n\n"
                    "你要像邱国鹭写路演一样，结合行业周期和公司质量来判断。\n"
                    "只根据提供的数据做判断，不要胡编历史或宏观数据。\n"
                    "请按下面清单思考：\n"
                    f"{checklist_text}\n\n"
                    "输出规则：\n"
                    "- bullish：当前定价明显偏悲观、赔率较高\n"
                    "- bearish：估值偏贵或周期高位，性价比一般甚至偏差\n"
                    "- neutral：尚可但缺乏非常好的赔率\n"
                    "confidence 用 0-100 的整数。\n"
                    "reasoning 需要详细完整（200-500 字符），必须包含：\n"
                    "  1. 核心分析依据：具体的数据指标、财务表现、估值水平等\n"
                    "  2. 行业周期：当前处于行业周期的什么位置，未来趋势如何\n"
                    "  3. 公司质量：业务模式、竞争优势、管理团队等\n"
                    "  4. 赔率分析：当前定价是否合理，风险收益比如何\n"
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
            reasoning="对周期和估值缺少足够把握，先控制仓位、耐心观察。",
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=ChineseMasterSignal,
        agent_name=agent_id,
        state=state,
        default_factory=default_signal,
    )



