from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
import math
from src.utils.api_key import get_api_key_from_state, get_use_openbb_from_state


class BenGrahamSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def ben_graham_agent(state: AgentState, agent_id: str = "ben_graham_agent"):
    """
    Analyzes stocks using Benjamin Graham's classic value-investing principles:
    1. Earnings stability over multiple years.
    2. Solid financial strength (low debt, adequate liquidity).
    3. Discount to intrinsic value (e.g. Graham Number or net-net).
    4. Adequate margin of safety.
    """
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    massive_api_key = get_api_key_from_state(state, "MASSIVE_API_KEY")
    cn_api_key = get_api_key_from_state(state, "DEEPALPHA_API_KEY")
    use_openbb = get_use_openbb_from_state(state)
    
    analysis_data = {}
    graham_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=10, api_key=api_key, cn_api_key=cn_api_key, massive_api_key=massive_api_key, use_openbb=use_openbb)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(ticker, ["earnings_per_share", "revenue", "net_income", "book_value_per_share", "total_assets", "total_liabilities", "current_assets", "current_liabilities", "dividends_and_other_cash_distributions", "outstanding_shares"], end_date, period="annual", limit=10, api_key=api_key, cn_api_key=cn_api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key, massive_api_key=massive_api_key)

        # Perform sub-analyses
        progress.update_status(agent_id, ticker, "Analyzing earnings stability")
        earnings_analysis = analyze_earnings_stability(metrics, financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing financial strength")
        strength_analysis = analyze_financial_strength(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing Graham valuation")
        valuation_analysis = analyze_valuation_graham(financial_line_items, market_cap)

        # Aggregate scoring
        total_score = earnings_analysis["score"] + strength_analysis["score"] + valuation_analysis["score"]
        max_possible_score = 15  # total possible from the three analysis functions

        # Map total_score to signal
        if total_score >= 0.7 * max_possible_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_possible_score:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {"signal": signal, "score": total_score, "max_score": max_possible_score, "earnings_analysis": earnings_analysis, "strength_analysis": strength_analysis, "valuation_analysis": valuation_analysis}

        progress.update_status(agent_id, ticker, "Generating Ben Graham analysis")
        graham_output = generate_graham_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        graham_analysis[ticker] = {"signal": graham_output.signal, "confidence": graham_output.confidence, "reasoning": graham_output.reasoning}

        progress.update_status(agent_id, ticker, "Done", analysis=graham_output.reasoning)

    # Wrap results in a single message for the chain
    message = HumanMessage(content=json.dumps(graham_analysis), name=agent_id)

    # Optionally display reasoning
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(graham_analysis, "Ben Graham Agent")

    # Store signals in the overall state
    state["data"]["analyst_signals"][agent_id] = graham_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_earnings_stability(metrics: list, financial_line_items: list) -> dict:
    """
    Graham wants at least several years of consistently positive earnings (ideally 5+).
    We'll check:
    1. Number of years with positive EPS.
    2. Growth in EPS from first to last period.
    """
    score = 0
    details = []

    if not metrics or not financial_line_items:
        return {"score": score, "details": "Insufficient data for earnings stability analysis"}

    eps_vals = []
    for item in financial_line_items:
        if item.earnings_per_share is not None:
            eps_vals.append(item.earnings_per_share)

    if len(eps_vals) < 2:
        details.append("Not enough multi-year EPS data.")
        return {"score": score, "details": "; ".join(details)}

    # 1. Consistently positive EPS
    positive_eps_years = sum(1 for e in eps_vals if e > 0)
    total_eps_years = len(eps_vals)
    if positive_eps_years == total_eps_years:
        score += 3
        details.append("EPS was positive in all available periods.")
    elif positive_eps_years >= (total_eps_years * 0.8):
        score += 2
        details.append("EPS was positive in most periods.")
    else:
        details.append("EPS was negative in multiple periods.")

    # 2. EPS growth from earliest to latest
    if eps_vals[0] > eps_vals[-1]:
        score += 1
        details.append("EPS grew from earliest to latest period.")
    else:
        details.append("EPS did not grow from earliest to latest period.")

    return {"score": score, "details": "; ".join(details)}


def analyze_financial_strength(financial_line_items: list) -> dict:
    """
    Graham checks liquidity (current ratio >= 2), manageable debt,
    and dividend record (preferably some history of dividends).
    """
    score = 0
    details = []

    if not financial_line_items:
        return {"score": score, "details": "No data for financial strength analysis"}

    latest_item = financial_line_items[0]
    total_assets = latest_item.total_assets or 0
    total_liabilities = latest_item.total_liabilities or 0
    current_assets = latest_item.current_assets or 0
    current_liabilities = latest_item.current_liabilities or 0

    # 1. Current ratio
    if current_liabilities > 0:
        current_ratio = current_assets / current_liabilities
        if current_ratio >= 2.0:
            score += 2
            details.append(f"Current ratio = {current_ratio:.2f} (>=2.0: solid).")
        elif current_ratio >= 1.5:
            score += 1
            details.append(f"Current ratio = {current_ratio:.2f} (moderately strong).")
        else:
            details.append(f"Current ratio = {current_ratio:.2f} (<1.5: weaker liquidity).")
    else:
        details.append("Cannot compute current ratio (missing or zero current_liabilities).")

    # 2. Debt vs. Assets
    if total_assets > 0:
        debt_ratio = total_liabilities / total_assets
        if debt_ratio < 0.5:
            score += 2
            details.append(f"Debt ratio = {debt_ratio:.2f}, under 0.50 (conservative).")
        elif debt_ratio < 0.8:
            score += 1
            details.append(f"Debt ratio = {debt_ratio:.2f}, somewhat high but could be acceptable.")
        else:
            details.append(f"Debt ratio = {debt_ratio:.2f}, quite high by Graham standards.")
    else:
        details.append("Cannot compute debt ratio (missing total_assets).")

    # 3. Dividend track record
    div_periods = [item.dividends_and_other_cash_distributions for item in financial_line_items if item.dividends_and_other_cash_distributions is not None]
    if div_periods:
        # In many data feeds, dividend outflow is shown as a negative number
        # (money going out to shareholders). We'll consider any negative as 'paid a dividend'.
        div_paid_years = sum(1 for d in div_periods if d < 0)
        if div_paid_years > 0:
            # e.g. if at least half the periods had dividends
            if div_paid_years >= (len(div_periods) // 2 + 1):
                score += 1
                details.append("Company paid dividends in the majority of the reported years.")
            else:
                details.append("Company has some dividend payments, but not most years.")
        else:
            details.append("Company did not pay dividends in these periods.")
    else:
        details.append("No dividend data available to assess payout consistency.")

    return {"score": score, "details": "; ".join(details)}


def analyze_valuation_graham(financial_line_items: list, market_cap: float) -> dict:
    """
    Core Graham approach to valuation:
    1. Net-Net Check: (Current Assets - Total Liabilities) vs. Market Cap
    2. Graham Number: sqrt(22.5 * EPS * Book Value per Share)
    3. Compare per-share price to Graham Number => margin of safety
    """
    if not financial_line_items or not market_cap or market_cap <= 0:
        return {"score": 0, "details": "Insufficient data to perform valuation"}

    latest = financial_line_items[0]
    current_assets = latest.current_assets or 0
    total_liabilities = latest.total_liabilities or 0
    book_value_ps = latest.book_value_per_share or 0
    eps = latest.earnings_per_share or 0
    shares_outstanding = latest.outstanding_shares or 0

    details = []
    score = 0

    # 1. Net-Net Check
    #   NCAV = Current Assets - Total Liabilities
    #   If NCAV > Market Cap => historically a strong buy signal
    net_current_asset_value = current_assets - total_liabilities
    if net_current_asset_value > 0 and shares_outstanding > 0:
        net_current_asset_value_per_share = net_current_asset_value / shares_outstanding
        price_per_share = market_cap / shares_outstanding if shares_outstanding else 0

        details.append(f"Net Current Asset Value = {net_current_asset_value:,.2f}")
        details.append(f"NCAV Per Share = {net_current_asset_value_per_share:,.2f}")
        details.append(f"Price Per Share = {price_per_share:,.2f}")

        if net_current_asset_value > market_cap:
            score += 4  # Very strong Graham signal
            details.append("Net-Net: NCAV > Market Cap (classic Graham deep value).")
        else:
            # For partial net-net discount
            if net_current_asset_value_per_share >= (price_per_share * 0.67):
                score += 2
                details.append("NCAV Per Share >= 2/3 of Price Per Share (moderate net-net discount).")
    else:
        details.append("NCAV not exceeding market cap or insufficient data for net-net approach.")

    # 2. Graham Number
    #   GrahamNumber = sqrt(22.5 * EPS * BVPS).
    #   Compare the result to the current price_per_share
    #   If GrahamNumber >> price, indicates undervaluation
    graham_number = None
    if eps > 0 and book_value_ps > 0:
        graham_number = math.sqrt(22.5 * eps * book_value_ps)
        details.append(f"Graham Number = {graham_number:.2f}")
    else:
        details.append("Unable to compute Graham Number (EPS or Book Value missing/<=0).")

    # 3. Margin of Safety relative to Graham Number
    if graham_number and shares_outstanding > 0:
        current_price = market_cap / shares_outstanding
        if current_price > 0:
            margin_of_safety = (graham_number - current_price) / current_price
            details.append(f"Margin of Safety (Graham Number) = {margin_of_safety:.2%}")
            if margin_of_safety > 0.5:
                score += 3
                details.append("Price is well below Graham Number (>=50% margin).")
            elif margin_of_safety > 0.2:
                score += 1
                details.append("Some margin of safety relative to Graham Number.")
            else:
                details.append("Price close to or above Graham Number, low margin of safety.")
        else:
            details.append("Current price is zero or invalid; can't compute margin of safety.")
    # else: already appended details for missing graham_number

    return {"score": score, "details": "; ".join(details)}


def generate_graham_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
) -> BenGrahamSignal:
    """
    Generates an investment decision in the style of Benjamin Graham:
    - Value emphasis, margin of safety, net-nets, conservative balance sheet, stable earnings.
    - Return the result in a JSON structure: { signal, confidence, reasoning }.
    """
    # 获取语言设置
    language = state.get("metadata", {}).get("language") or "en"
    is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"])

    # 根据语言生成不同的 prompt
    if is_chinese:
        system_prompt = (
            "你是本杰明·格雷厄姆 AI 智能体，使用他的原则做出投资决策：\n"
            "1. 坚持安全边际，以低于内在价值的价格买入（例如，使用格雷厄姆数字、净流动资产价值）。\n"
            "2. 强调公司的财务实力（低杠杆、充足的流动资产）。\n"
            "3. 偏好多年稳定的收益。\n"
            "4. 考虑股息记录以获得额外安全性。\n"
            "5. 避免投机或高增长假设；专注于经过验证的指标。\n"
            "\n"
            "在提供推理时，要详细具体：\n"
            "1. 解释影响你决策的关键估值指标（格雷厄姆数字、净流动资产价值、市盈率等）\n"
            "2. 突出具体的财务实力指标（流动比率、债务水平等）\n"
            "3. 参考收益随时间的稳定性或不稳定性\n"
            "4. 提供精确数字的定量证据\n"
            "5. 将当前指标与格雷厄姆的具体阈值进行比较（例如，\"流动比率 2.5 超过格雷厄姆的最低要求 2.0\"）\n"
            "6. 使用本杰明·格雷厄姆保守、分析性的声音和风格\n"
            "\n"
            "例如，如果看涨：\"该股票以净流动资产价值 35% 的折扣交易，提供了充足的安全边际。流动比率 2.5 和债务权益比 0.3 表明财务状况强劲...\"\n"
            "例如，如果看跌：\"尽管收益稳定，但当前价格 50 美元超过了我们计算的格雷厄姆数字 35 美元，没有提供安全边际。此外，流动比率仅为 1.2，低于格雷厄姆偏好的 2.0 阈值...\"\n"
            "\n"
            "返回理性建议：看涨、看跌或中性，带有信心水平（0-100）和详细推理。"
        )
        human_prompt = (
            "基于以下分析，创建格雷厄姆风格的投资信号：\n"
            "\n"
            "{ticker} 的分析数据：\n"
            "{analysis_data}\n"
            "\n"
            "严格按照以下 JSON 格式返回：\n"
            "{{\n"
            '  "signal": "bullish" 或 "bearish" 或 "neutral",\n'
            '  "confidence": float (0-100),\n'
            '  "reasoning": "字符串"\n'
            "}}"
        )
        default_reasoning = "生成分析时出错；默认中性。"
    else:
        system_prompt = (
            "You are a Benjamin Graham AI agent, making investment decisions using his principles:\n"
            "1. Insist on a margin of safety by buying below intrinsic value (e.g., using Graham Number, net-net).\n"
            "2. Emphasize the company's financial strength (low leverage, ample current assets).\n"
            "3. Prefer stable earnings over multiple years.\n"
            "4. Consider dividend record for extra safety.\n"
            "5. Avoid speculative or high-growth assumptions; focus on proven metrics.\n"
            "\n"
            "When providing your reasoning, be thorough and specific by:\n"
            "1. Explaining the key valuation metrics that influenced your decision the most (Graham Number, NCAV, P/E, etc.)\n"
            "2. Highlighting the specific financial strength indicators (current ratio, debt levels, etc.)\n"
            "3. Referencing the stability or instability of earnings over time\n"
            "4. Providing quantitative evidence with precise numbers\n"
            "5. Comparing current metrics to Graham's specific thresholds (e.g., \"Current ratio of 2.5 exceeds Graham's minimum of 2.0\")\n"
            "6. Using Benjamin Graham's conservative, analytical voice and style in your explanation\n"
            "\n"
            "For example, if bullish: \"The stock trades at a 35% discount to net current asset value, providing an ample margin of safety. The current ratio of 2.5 and debt-to-equity of 0.3 indicate strong financial position...\"\n"
            "For example, if bearish: \"Despite consistent earnings, the current price of $50 exceeds our calculated Graham Number of $35, offering no margin of safety. Additionally, the current ratio of only 1.2 falls below Graham's preferred 2.0 threshold...\"\n"
            "\n"
            "Return a rational recommendation: bullish, bearish, or neutral, with a confidence level (0-100) and thorough reasoning."
        )
        human_prompt = (
            "Based on the following analysis, create a Graham-style investment signal:\n"
            "\n"
            "Analysis Data for {ticker}:\n"
            "{analysis_data}\n"
            "\n"
            "Return JSON exactly in this format:\n"
            "{{\n"
            '  "signal": "bullish" or "bearish" or "neutral",\n'
            '  "confidence": float (0-100),\n'
            '  "reasoning": "string"\n'
            "}}"
        )
        default_reasoning = "Error in generating analysis; defaulting to neutral."

    template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human_prompt),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def create_default_ben_graham_signal():
        return BenGrahamSignal(signal="neutral", confidence=0.0, reasoning=default_reasoning)

    return call_llm(
        prompt=prompt,
        pydantic_model=BenGrahamSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_ben_graham_signal,
    )
