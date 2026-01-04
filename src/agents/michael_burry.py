from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing_extensions import Literal

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from src.tools.api import (
    get_company_news,
    get_financial_metrics,
    get_insider_trades,
    get_market_cap,
    search_line_items,
)
from src.utils.llm import call_llm
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state, get_use_openbb_from_state


class MichaelBurrySignal(BaseModel):
    """Schema returned by the LLM."""

    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float  # 0–100
    reasoning: str


def michael_burry_agent(state: AgentState, agent_id: str = "michael_burry_agent"):
    """Analyse stocks using Michael Burry's deep‑value, contrarian framework."""
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    massive_api_key = get_api_key_from_state(state, "MASSIVE_API_KEY")
    cn_api_key = get_api_key_from_state(state, "DEEPALPHA_API_KEY")
    use_openbb = get_use_openbb_from_state(state)
    data = state["data"]
    end_date: str = data["end_date"]  # YYYY‑MM‑DD
    tickers: list[str] = data["tickers"]

    # We look one year back for insider trades / news flow
    start_date = (datetime.fromisoformat(end_date) - timedelta(days=365)).date().isoformat()

    analysis_data: dict[str, dict] = {}
    burry_analysis: dict[str, dict] = {}

    for ticker in tickers:
        # ------------------------------------------------------------------
        # Fetch raw data
        # ------------------------------------------------------------------
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5, api_key=api_key, cn_api_key=cn_api_key, massive_api_key=massive_api_key, use_openbb=use_openbb)

        progress.update_status(agent_id, ticker, "Fetching line items")
        line_items = search_line_items(
            ticker,
            [
                "free_cash_flow",
                "net_income",
                "total_debt",
                "cash_and_equivalents",
                "total_assets",
                "total_liabilities",
                "outstanding_shares",
                "issuance_or_purchase_of_equity_shares",
            ],
            end_date,
            api_key=api_key,
            cn_api_key=cn_api_key,
            massive_api_key=massive_api_key,
        )

        progress.update_status(agent_id, ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(ticker, end_date=end_date, start_date=start_date, api_key=api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        news = get_company_news(ticker, end_date=end_date, start_date=start_date, limit=250, api_key=api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Fetching market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key, massive_api_key=massive_api_key)

        # ------------------------------------------------------------------
        # Run sub‑analyses
        # ------------------------------------------------------------------
        progress.update_status(agent_id, ticker, "Analyzing value")
        value_analysis = _analyze_value(metrics, line_items, market_cap)

        progress.update_status(agent_id, ticker, "Analyzing balance sheet")
        balance_sheet_analysis = _analyze_balance_sheet(metrics, line_items)

        progress.update_status(agent_id, ticker, "Analyzing insider activity")
        insider_analysis = _analyze_insider_activity(insider_trades)

        progress.update_status(agent_id, ticker, "Analyzing contrarian sentiment")
        contrarian_analysis = _analyze_contrarian_sentiment(news)

        # ------------------------------------------------------------------
        # Aggregate score & derive preliminary signal
        # ------------------------------------------------------------------
        total_score = (
            value_analysis["score"]
            + balance_sheet_analysis["score"]
            + insider_analysis["score"]
            + contrarian_analysis["score"]
        )
        max_score = (
            value_analysis["max_score"]
            + balance_sheet_analysis["max_score"]
            + insider_analysis["max_score"]
            + contrarian_analysis["max_score"]
        )

        if total_score >= 0.7 * max_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_score:
            signal = "bearish"
        else:
            signal = "neutral"

        # ------------------------------------------------------------------
        # Collect data for LLM reasoning & output
        # ------------------------------------------------------------------
        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "value_analysis": value_analysis,
            "balance_sheet_analysis": balance_sheet_analysis,
            "insider_analysis": insider_analysis,
            "contrarian_analysis": contrarian_analysis,
            "market_cap": market_cap,
        }

        progress.update_status(agent_id, ticker, "Generating LLM output")
        burry_output = _generate_burry_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        burry_analysis[ticker] = {
            "signal": burry_output.signal,
            "confidence": burry_output.confidence,
            "reasoning": burry_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=burry_output.reasoning)

    # ----------------------------------------------------------------------
    # Return to the graph
    # ----------------------------------------------------------------------
    message = HumanMessage(content=json.dumps(burry_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(burry_analysis, "Michael Burry Agent")

    state["data"]["analyst_signals"][agent_id] = burry_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


###############################################################################
# Sub‑analysis helpers
###############################################################################


def _latest_line_item(line_items: list):
    """Return the most recent line‑item object or *None*."""
    return line_items[0] if line_items else None


# ----- Value ----------------------------------------------------------------

def _analyze_value(metrics, line_items, market_cap):
    """Free cash‑flow yield, EV/EBIT, other classic deep‑value metrics."""

    max_score = 6  # 4 pts for FCF‑yield, 2 pts for EV/EBIT
    score = 0
    details: list[str] = []

    # Free‑cash‑flow yield
    latest_item = _latest_line_item(line_items)
    fcf = getattr(latest_item, "free_cash_flow", None) if latest_item else None
    if fcf is not None and market_cap:
        fcf_yield = fcf / market_cap
        if fcf_yield >= 0.15:
            score += 4
            details.append(f"Extraordinary FCF yield {fcf_yield:.1%}")
        elif fcf_yield >= 0.12:
            score += 3
            details.append(f"Very high FCF yield {fcf_yield:.1%}")
        elif fcf_yield >= 0.08:
            score += 2
            details.append(f"Respectable FCF yield {fcf_yield:.1%}")
        else:
            details.append(f"Low FCF yield {fcf_yield:.1%}")
    else:
        details.append("FCF data unavailable")

    # EV/EBIT (from financial metrics)
    if metrics:
        ev_ebit = getattr(metrics[0], "ev_to_ebit", None)
        if ev_ebit is not None:
            if ev_ebit < 6:
                score += 2
                details.append(f"EV/EBIT {ev_ebit:.1f} (<6)")
            elif ev_ebit < 10:
                score += 1
                details.append(f"EV/EBIT {ev_ebit:.1f} (<10)")
            else:
                details.append(f"High EV/EBIT {ev_ebit:.1f}")
        else:
            details.append("EV/EBIT data unavailable")
    else:
        details.append("Financial metrics unavailable")

    return {"score": score, "max_score": max_score, "details": "; ".join(details)}


# ----- Balance sheet --------------------------------------------------------

def _analyze_balance_sheet(metrics, line_items):
    """Leverage and liquidity checks."""

    max_score = 3
    score = 0
    details: list[str] = []

    latest_metrics = metrics[0] if metrics else None
    latest_item = _latest_line_item(line_items)

    debt_to_equity = getattr(latest_metrics, "debt_to_equity", None) if latest_metrics else None
    if debt_to_equity is not None:
        if debt_to_equity < 0.5:
            score += 2
            details.append(f"Low D/E {debt_to_equity:.2f}")
        elif debt_to_equity < 1:
            score += 1
            details.append(f"Moderate D/E {debt_to_equity:.2f}")
        else:
            details.append(f"High leverage D/E {debt_to_equity:.2f}")
    else:
        details.append("Debt‑to‑equity data unavailable")

    # Quick liquidity sanity check (cash vs total debt)
    if latest_item is not None:
        cash = getattr(latest_item, "cash_and_equivalents", None)
        total_debt = getattr(latest_item, "total_debt", None)
        if cash is not None and total_debt is not None:
            if cash > total_debt:
                score += 1
                details.append("Net cash position")
            else:
                details.append("Net debt position")
        else:
            details.append("Cash/debt data unavailable")

    return {"score": score, "max_score": max_score, "details": "; ".join(details)}


# ----- Insider activity -----------------------------------------------------

def _analyze_insider_activity(insider_trades):
    """Net insider buying over the last 12 months acts as a hard catalyst."""

    max_score = 2
    score = 0
    details: list[str] = []

    if not insider_trades:
        details.append("No insider trade data")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    shares_bought = sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) > 0)
    shares_sold = abs(sum(t.transaction_shares or 0 for t in insider_trades if (t.transaction_shares or 0) < 0))
    net = shares_bought - shares_sold
    if net > 0:
        score += 2 if net / max(shares_sold, 1) > 1 else 1
        details.append(f"Net insider buying of {net:,} shares")
    else:
        details.append("Net insider selling")

    return {"score": score, "max_score": max_score, "details": "; ".join(details)}


# ----- Contrarian sentiment -------------------------------------------------

def _analyze_contrarian_sentiment(news):
    """Very rough gauge: a wall of recent negative headlines can be a *positive* for a contrarian."""

    max_score = 1
    score = 0
    details: list[str] = []

    if not news:
        details.append("No recent news")
        return {"score": score, "max_score": max_score, "details": "; ".join(details)}

    # Count negative sentiment articles
    sentiment_negative_count = sum(
        1 for n in news if n.sentiment and n.sentiment.lower() in ["negative", "bearish"]
    )
    
    if sentiment_negative_count >= 5:
        score += 1  # The more hated, the better (assuming fundamentals hold up)
        details.append(f"{sentiment_negative_count} negative headlines (contrarian opportunity)")
    else:
        details.append("Limited negative press")

    return {"score": score, "max_score": max_score, "details": "; ".join(details)}


###############################################################################
# LLM generation
###############################################################################

def _generate_burry_output(
    ticker: str,
    analysis_data: dict,
    state: AgentState,
    agent_id: str,
) -> MichaelBurrySignal:
    """Call the LLM to craft the final trading signal in Burry's voice."""
    # 获取语言设置
    language = state.get("metadata", {}).get("language") or "en"
    is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"])

    # 根据语言生成不同的 prompt
    if is_chinese:
        system_prompt = (
            "你是模拟迈克尔·J·伯里博士的 AI 智能体。你的任务：\n"
            "- 使用硬数字（自由现金流、EV/EBIT、资产负债表）在美国股票中寻找深度价值\n"
            "- 逆向思维：如果基本面扎实，媒体的负面报道可能是你的朋友\n"
            "- 首先关注下行风险——避免杠杆资产负债表\n"
            "- 寻找硬催化剂，如内部人买入、回购或资产出售\n"
            "- 以伯里简洁、数据驱动的风格沟通\n"
            "\n"
            "在提供推理时，要详细具体：\n"
            "1. 从驱动你决策的关键指标开始\n"
            "2. 引用具体数字（例如 \"FCF 收益率 14.7%\"，\"EV/EBIT 5.3\"）\n"
            "3. 突出风险因素以及为什么它们可以接受（或不可以）\n"
            "4. 提及相关的内部人活动或逆向机会\n"
            "5. 使用伯里直接、以数字为重点、用词最少的沟通风格\n"
            "\n"
            "例如，如果看涨：\"FCF 收益率 12.8%。EV/EBIT 6.2。债务权益比 0.4。净内部人买入 2.5 万股。市场因对最近诉讼的过度反应而错失价值。强烈买入。\"\n"
            "例如，如果看跌：\"FCF 收益率仅 2.1%。债务权益比令人担忧，为 2.3。管理层稀释股东。放弃。\""
        )
        human_prompt = (
            "基于以下数据，创建迈克尔·伯里风格的投资信号：\n"
            "\n"
            "{ticker} 的分析数据：\n"
            "{analysis_data}\n"
            "\n"
            "严格按照以下 JSON 格式返回交易信号：\n"
            "{{\n"
            '  "signal": "bullish" | "bearish" | "neutral",\n'
            '  "confidence": float (0-100),\n'
            '  "reasoning": "字符串"\n'
            "}}"
        )
        default_reasoning = "解析错误 – 默认中性"
    else:
        system_prompt = (
            "You are an AI agent emulating Dr. Michael J. Burry. Your mandate:\n"
            "- Hunt for deep value in US equities using hard numbers (free cash flow, EV/EBIT, balance sheet)\n"
            "- Be contrarian: hatred in the press can be your friend if fundamentals are solid\n"
            "- Focus on downside first – avoid leveraged balance sheets\n"
            "- Look for hard catalysts such as insider buying, buybacks, or asset sales\n"
            "- Communicate in Burry's terse, data‑driven style\n"
            "\n"
            "When providing your reasoning, be thorough and specific by:\n"
            "1. Start with the key metric(s) that drove your decision\n"
            "2. Cite concrete numbers (e.g. \"FCF yield 14.7%\", \"EV/EBIT 5.3\")\n"
            "3. Highlight risk factors and why they are acceptable (or not)\n"
            "4. Mention relevant insider activity or contrarian opportunities\n"
            "5. Use Burry's direct, number-focused communication style with minimal words\n"
            "\n"
            "For example, if bullish: \"FCF yield 12.8%. EV/EBIT 6.2. Debt-to-equity 0.4. Net insider buying 25k shares. Market missing value due to overreaction to recent litigation. Strong buy.\"\n"
            "For example, if bearish: \"FCF yield only 2.1%. Debt-to-equity concerning at 2.3. Management diluting shareholders. Pass.\""
        )
        human_prompt = (
            "Based on the following data, create the investment signal as Michael Burry would:\n"
            "\n"
            "Analysis Data for {ticker}:\n"
            "{analysis_data}\n"
            "\n"
            "Return the trading signal in the following JSON format exactly:\n"
            "{{\n"
            '  "signal": "bullish" | "bearish" | "neutral",\n'
            '  "confidence": float between 0 and 100,\n'
            '  "reasoning": "string"\n'
            "}}"
        )
        default_reasoning = "Parsing error – defaulting to neutral"

    template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human_prompt),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    # Default fallback signal in case parsing fails
    def create_default_michael_burry_signal():
        return MichaelBurrySignal(signal="neutral", confidence=0.0, reasoning=default_reasoning)

    return call_llm(
        prompt=prompt,
        pydantic_model=MichaelBurrySignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_michael_burry_signal,
    )
