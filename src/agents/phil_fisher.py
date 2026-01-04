from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_market_cap,
    search_line_items,
    get_insider_trades,
    get_company_news,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
import statistics
from src.utils.api_key import get_api_key_from_state, get_use_openbb_from_state

class PhilFisherSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def phil_fisher_agent(state: AgentState, agent_id: str = "phil_fisher_agent"):
    """
    Analyzes stocks using Phil Fisher's investing principles:
      - Seek companies with long-term above-average growth potential
      - Emphasize quality of management and R&D
      - Look for strong margins, consistent growth, and manageable leverage
      - Combine fundamental 'scuttlebutt' style checks with basic sentiment and insider data
      - Willing to pay up for quality, but still mindful of valuation
      - Generally focuses on long-term compounding

    Returns a bullish/bearish/neutral signal with confidence and reasoning.
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
    fisher_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Gathering financial line items")
        # Include relevant line items for Phil Fisher's approach:
        #   - Growth & Quality: revenue, net_income, earnings_per_share, R&D expense
        #   - Margins & Stability: operating_income, operating_margin, gross_margin
        #   - Management Efficiency & Leverage: total_debt, shareholders_equity, free_cash_flow
        #   - Valuation: net_income, free_cash_flow (for P/E, P/FCF), ebit, ebitda
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "net_income",
                "earnings_per_share",
                "free_cash_flow",
                "research_and_development",
                "operating_income",
                "operating_margin",
                "gross_margin",
                "total_debt",
                "shareholders_equity",
                "cash_and_equivalents",
                "ebit",
                "ebitda",
            ],
            end_date,
            period="annual",
            limit=5,
            api_key=api_key,
            cn_api_key=cn_api_key,
            massive_api_key=massive_api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key, massive_api_key=massive_api_key, use_openbb=use_openbb)

        progress.update_status(agent_id, ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(ticker, end_date, limit=50, api_key=api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        company_news = get_company_news(ticker, end_date, limit=50, api_key=api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Analyzing growth & quality")
        growth_quality = analyze_fisher_growth_quality(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing margins & stability")
        margins_stability = analyze_margins_stability(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing management efficiency & leverage")
        mgmt_efficiency = analyze_management_efficiency_leverage(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing valuation (Fisher style)")
        fisher_valuation = analyze_fisher_valuation(financial_line_items, market_cap)

        progress.update_status(agent_id, ticker, "Analyzing insider activity")
        insider_activity = analyze_insider_activity(insider_trades)

        progress.update_status(agent_id, ticker, "Analyzing sentiment")
        sentiment_analysis = analyze_sentiment(company_news)

        # Combine partial scores with weights typical for Fisher:
        #   30% Growth & Quality
        #   25% Margins & Stability
        #   20% Management Efficiency
        #   15% Valuation
        #   5% Insider Activity
        #   5% Sentiment
        total_score = (
            growth_quality["score"] * 0.30
            + margins_stability["score"] * 0.25
            + mgmt_efficiency["score"] * 0.20
            + fisher_valuation["score"] * 0.15
            + insider_activity["score"] * 0.05
            + sentiment_analysis["score"] * 0.05
        )

        max_possible_score = 10

        # Simple bullish/neutral/bearish signal
        if total_score >= 7.5:
            signal = "bullish"
        elif total_score <= 4.5:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "growth_quality": growth_quality,
            "margins_stability": margins_stability,
            "management_efficiency": mgmt_efficiency,
            "valuation_analysis": fisher_valuation,
            "insider_activity": insider_activity,
            "sentiment_analysis": sentiment_analysis,
        }

        progress.update_status(agent_id, ticker, "Generating Phil Fisher-style analysis")
        fisher_output = generate_fisher_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        fisher_analysis[ticker] = {
            "signal": fisher_output.signal,
            "confidence": fisher_output.confidence,
            "reasoning": fisher_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=fisher_output.reasoning)

    # Wrap results in a single message
    message = HumanMessage(content=json.dumps(fisher_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(fisher_analysis, "Phil Fisher Agent")

    state["data"]["analyst_signals"][agent_id] = fisher_analysis

    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}


def analyze_fisher_growth_quality(financial_line_items: list) -> dict:
    """
    Evaluate growth & quality:
      - Consistent Revenue Growth
      - Consistent EPS Growth
      - R&D as a % of Revenue (if relevant, indicative of future-oriented spending)
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {
            "score": 0,
            "details": "Insufficient financial data for growth/quality analysis",
        }

    details = []
    raw_score = 0  # up to 9 raw points => scale to 0–10

    # 1. Revenue Growth (annualized CAGR)
    revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
    if len(revenues) >= 2:
        # Calculate annualized growth rate (CAGR) for proper comparison
        latest_rev = revenues[0]
        oldest_rev = revenues[-1]
        num_years = len(revenues) - 1
        if oldest_rev > 0 and latest_rev > 0:
            # CAGR formula: (ending_value/beginning_value)^(1/years) - 1
            rev_growth = (latest_rev / oldest_rev) ** (1 / num_years) - 1
            if rev_growth > 0.20:  # 20% annualized
                raw_score += 3
                details.append(f"Very strong annualized revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.10:  # 10% annualized
                raw_score += 2
                details.append(f"Moderate annualized revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.03:  # 3% annualized
                raw_score += 1
                details.append(f"Slight annualized revenue growth: {rev_growth:.1%}")
            else:
                details.append(f"Minimal or negative annualized revenue growth: {rev_growth:.1%}")
        else:
            details.append("Oldest revenue is zero/negative; cannot compute growth.")
    else:
        details.append("Not enough revenue data points for growth calculation.")

    # 2. EPS Growth (annualized CAGR)
    eps_values = [fi.earnings_per_share for fi in financial_line_items if fi.earnings_per_share is not None]
    if len(eps_values) >= 2:
        latest_eps = eps_values[0]
        oldest_eps = eps_values[-1]
        num_years = len(eps_values) - 1
        if oldest_eps > 0 and latest_eps > 0:
            # CAGR formula for EPS
            eps_growth = (latest_eps / oldest_eps) ** (1 / num_years) - 1
            if eps_growth > 0.20:  # 20% annualized
                raw_score += 3
                details.append(f"Very strong annualized EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.10:  # 10% annualized
                raw_score += 2
                details.append(f"Moderate annualized EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.03:  # 3% annualized
                raw_score += 1
                details.append(f"Slight annualized EPS growth: {eps_growth:.1%}")
            else:
                details.append(f"Minimal or negative annualized EPS growth: {eps_growth:.1%}")
        else:
            details.append("Oldest EPS near zero; skipping EPS growth calculation.")
    else:
        details.append("Not enough EPS data points for growth calculation.")

    # 3. R&D as % of Revenue (if we have R&D data)
    rnd_values = [fi.research_and_development for fi in financial_line_items if fi.research_and_development is not None]
    if rnd_values and revenues and len(rnd_values) == len(revenues):
        # We'll just look at the most recent for a simple measure
        recent_rnd = rnd_values[0]
        recent_rev = revenues[0] if revenues[0] else 1e-9
        rnd_ratio = recent_rnd / recent_rev
        # Generally, Fisher admired companies that invest aggressively in R&D,
        # but it must be appropriate. We'll assume "3%-15%" is healthy, just as an example.
        if 0.03 <= rnd_ratio <= 0.15:
            raw_score += 3
            details.append(f"R&D ratio {rnd_ratio:.1%} indicates significant investment in future growth")
        elif rnd_ratio > 0.15:
            raw_score += 2
            details.append(f"R&D ratio {rnd_ratio:.1%} is very high (could be good if well-managed)")
        elif rnd_ratio > 0.0:
            raw_score += 1
            details.append(f"R&D ratio {rnd_ratio:.1%} is somewhat low but still positive")
        else:
            details.append("No meaningful R&D expense ratio")
    else:
        details.append("Insufficient R&D data to evaluate")

    # scale raw_score (max 9) to 0–10
    final_score = min(10, (raw_score / 9) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_margins_stability(financial_line_items: list) -> dict:
    """
    Looks at margin consistency (gross/operating margin) and general stability over time.
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {
            "score": 0,
            "details": "Insufficient data for margin stability analysis",
        }

    details = []
    raw_score = 0  # up to 6 => scale to 0-10

    # 1. Operating Margin Consistency
    op_margins = [fi.operating_margin for fi in financial_line_items if fi.operating_margin is not None]
    if len(op_margins) >= 2:
        # Check if margins are stable or improving (comparing oldest to newest)
        oldest_op_margin = op_margins[-1]
        newest_op_margin = op_margins[0]
        if newest_op_margin >= oldest_op_margin > 0:
            raw_score += 2
            details.append(f"Operating margin stable or improving ({oldest_op_margin:.1%} -> {newest_op_margin:.1%})")
        elif newest_op_margin > 0:
            raw_score += 1
            details.append(f"Operating margin positive but slightly declined")
        else:
            details.append(f"Operating margin may be negative or uncertain")
    else:
        details.append("Not enough operating margin data points")

    # 2. Gross Margin Level
    gm_values = [fi.gross_margin for fi in financial_line_items if fi.gross_margin is not None]
    if gm_values:
        # We'll just take the most recent
        recent_gm = gm_values[0]
        if recent_gm > 0.5:
            raw_score += 2
            details.append(f"Strong gross margin: {recent_gm:.1%}")
        elif recent_gm > 0.3:
            raw_score += 1
            details.append(f"Moderate gross margin: {recent_gm:.1%}")
        else:
            details.append(f"Low gross margin: {recent_gm:.1%}")
    else:
        details.append("No gross margin data available")

    # 3. Multi-year Margin Stability
    #   e.g. if we have at least 3 data points, see if standard deviation is low.
    if len(op_margins) >= 3:
        stdev = statistics.pstdev(op_margins)
        if stdev < 0.02:
            raw_score += 2
            details.append("Operating margin extremely stable over multiple years")
        elif stdev < 0.05:
            raw_score += 1
            details.append("Operating margin reasonably stable")
        else:
            details.append("Operating margin volatility is high")
    else:
        details.append("Not enough margin data points for volatility check")

    # scale raw_score (max 6) to 0-10
    final_score = min(10, (raw_score / 6) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_management_efficiency_leverage(financial_line_items: list) -> dict:
    """
    Evaluate management efficiency & leverage:
      - Return on Equity (ROE)
      - Debt-to-Equity ratio
      - Possibly check if free cash flow is consistently positive
    """
    if not financial_line_items:
        return {
            "score": 0,
            "details": "No financial data for management efficiency analysis",
        }

    details = []
    raw_score = 0  # up to 6 => scale to 0–10

    # 1. Return on Equity (ROE)
    ni_values = [fi.net_income for fi in financial_line_items if fi.net_income is not None]
    eq_values = [fi.shareholders_equity for fi in financial_line_items if fi.shareholders_equity is not None]
    if ni_values and eq_values and len(ni_values) == len(eq_values):
        recent_ni = ni_values[0]
        recent_eq = eq_values[0] if eq_values[0] else 1e-9
        if recent_ni > 0:
            roe = recent_ni / recent_eq
            if roe > 0.2:
                raw_score += 3
                details.append(f"High ROE: {roe:.1%}")
            elif roe > 0.1:
                raw_score += 2
                details.append(f"Moderate ROE: {roe:.1%}")
            elif roe > 0:
                raw_score += 1
                details.append(f"Positive but low ROE: {roe:.1%}")
            else:
                details.append(f"ROE is near zero or negative: {roe:.1%}")
        else:
            details.append("Recent net income is zero or negative, hurting ROE")
    else:
        details.append("Insufficient data for ROE calculation")

    # 2. Debt-to-Equity
    debt_values = [fi.total_debt for fi in financial_line_items if fi.total_debt is not None]
    if debt_values and eq_values and len(debt_values) == len(eq_values):
        recent_debt = debt_values[0]
        recent_equity = eq_values[0] if eq_values[0] else 1e-9
        dte = recent_debt / recent_equity
        if dte < 0.3:
            raw_score += 2
            details.append(f"Low debt-to-equity: {dte:.2f}")
        elif dte < 1.0:
            raw_score += 1
            details.append(f"Manageable debt-to-equity: {dte:.2f}")
        else:
            details.append(f"High debt-to-equity: {dte:.2f}")
    else:
        details.append("Insufficient data for debt/equity analysis")

    # 3. FCF Consistency
    fcf_values = [fi.free_cash_flow for fi in financial_line_items if fi.free_cash_flow is not None]
    if fcf_values and len(fcf_values) >= 2:
        # Check if FCF is positive in recent years
        positive_fcf_count = sum(1 for x in fcf_values if x and x > 0)
        # We'll be simplistic: if most are positive, reward
        ratio = positive_fcf_count / len(fcf_values)
        if ratio > 0.8:
            raw_score += 1
            details.append(f"Majority of periods have positive FCF ({positive_fcf_count}/{len(fcf_values)})")
        else:
            details.append(f"Free cash flow is inconsistent or often negative")
    else:
        details.append("Insufficient or no FCF data to check consistency")

    final_score = min(10, (raw_score / 6) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_fisher_valuation(financial_line_items: list, market_cap: float | None) -> dict:
    """
    Phil Fisher is willing to pay for quality and growth, but still checks:
      - P/E
      - P/FCF
      - (Optionally) Enterprise Value metrics, but simpler approach is typical
    We will grant up to 2 points for each of two metrics => max 4 raw => scale to 0–10.
    """
    if not financial_line_items or market_cap is None:
        return {"score": 0, "details": "Insufficient data to perform valuation"}

    details = []
    raw_score = 0

    # Gather needed data
    net_incomes = [fi.net_income for fi in financial_line_items if fi.net_income is not None]
    fcf_values = [fi.free_cash_flow for fi in financial_line_items if fi.free_cash_flow is not None]

    # 1) P/E
    recent_net_income = net_incomes[0] if net_incomes else None
    if recent_net_income and recent_net_income > 0:
        pe = market_cap / recent_net_income
        pe_points = 0
        if pe < 20:
            pe_points = 2
            details.append(f"Reasonably attractive P/E: {pe:.2f}")
        elif pe < 30:
            pe_points = 1
            details.append(f"Somewhat high but possibly justifiable P/E: {pe:.2f}")
        else:
            details.append(f"Very high P/E: {pe:.2f}")
        raw_score += pe_points
    else:
        details.append("No positive net income for P/E calculation")

    # 2) P/FCF
    recent_fcf = fcf_values[0] if fcf_values else None
    if recent_fcf and recent_fcf > 0:
        pfcf = market_cap / recent_fcf
        pfcf_points = 0
        if pfcf < 20:
            pfcf_points = 2
            details.append(f"Reasonable P/FCF: {pfcf:.2f}")
        elif pfcf < 30:
            pfcf_points = 1
            details.append(f"Somewhat high P/FCF: {pfcf:.2f}")
        else:
            details.append(f"Excessively high P/FCF: {pfcf:.2f}")
        raw_score += pfcf_points
    else:
        details.append("No positive free cash flow for P/FCF calculation")

    # scale raw_score (max 4) to 0–10
    final_score = min(10, (raw_score / 4) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_insider_activity(insider_trades: list) -> dict:
    """
    Simple insider-trade analysis:
      - If there's heavy insider buying, we nudge the score up.
      - If there's mostly selling, we reduce it.
      - Otherwise, neutral.
    """
    # Default is neutral (5/10).
    score = 5
    details = []

    if not insider_trades:
        details.append("No insider trades data; defaulting to neutral")
        return {"score": score, "details": "; ".join(details)}

    buys, sells = 0, 0
    for trade in insider_trades:
        if trade.transaction_shares is not None:
            if trade.transaction_shares > 0:
                buys += 1
            elif trade.transaction_shares < 0:
                sells += 1

    total = buys + sells
    if total == 0:
        details.append("No buy/sell transactions found; neutral")
        return {"score": score, "details": "; ".join(details)}

    buy_ratio = buys / total
    if buy_ratio > 0.7:
        score = 8
        details.append(f"Heavy insider buying: {buys} buys vs. {sells} sells")
    elif buy_ratio > 0.4:
        score = 6
        details.append(f"Moderate insider buying: {buys} buys vs. {sells} sells")
    else:
        score = 4
        details.append(f"Mostly insider selling: {buys} buys vs. {sells} sells")

    return {"score": score, "details": "; ".join(details)}


def analyze_sentiment(news_items: list) -> dict:
    """
    Basic news sentiment: negative keyword check vs. overall volume.
    """
    if not news_items:
        return {"score": 5, "details": "No news data; defaulting to neutral sentiment"}

    negative_keywords = ["lawsuit", "fraud", "negative", "downturn", "decline", "investigation", "recall"]
    negative_count = 0
    for news in news_items:
        title_lower = (news.title or "").lower()
        if any(word in title_lower for word in negative_keywords):
            negative_count += 1

    details = []
    if negative_count > len(news_items) * 0.3:
        score = 3
        details.append(f"High proportion of negative headlines: {negative_count}/{len(news_items)}")
    elif negative_count > 0:
        score = 6
        details.append(f"Some negative headlines: {negative_count}/{len(news_items)}")
    else:
        score = 8
        details.append("Mostly positive/neutral headlines")

    return {"score": score, "details": "; ".join(details)}


def generate_fisher_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
) -> PhilFisherSignal:
    """
    Generates a JSON signal in the style of Phil Fisher.
    """
    # 获取语言设置
    language = state.get("metadata", {}).get("language") or "en"
    is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"])

    # 根据语言生成不同的 prompt
    if is_chinese:
        system_prompt = (
            "你是菲利普·费雪 AI 智能体，使用他的原则做出投资决策：\n"
            "\n"
            "1. 强调长期增长潜力和管理质量。\n"
            "2. 专注于投资研发以开发未来产品/服务的公司。\n"
            "3. 寻找强劲的盈利能力和一致的利润率。\n"
            "4. 愿意为卓越公司支付更高价格，但仍注意估值。\n"
            "5. 依赖彻底的研究（小道消息）和彻底的基本面检查。\n"
            "\n"
            "在提供推理时，要详细具体：\n"
            "1. 详细讨论公司的增长前景，包括具体指标和趋势\n"
            "2. 评估管理质量和他们的资本配置决策\n"
            "3. 突出可能推动未来增长的研发投资和产品管道\n"
            "4. 用精确数字评估利润率和盈利能力指标的一致性\n"
            "5. 解释可能在 3-5 年以上维持增长的竞争优势\n"
            "6. 使用菲利普·费雪有条理、以增长为重点、面向长期的声音\n"
            "\n"
            "例如，如果看涨：\"这家公司展现出我们寻求的持续增长特征，收入在五年内每年增长 18%。管理层通过将收入的 15% 分配给研发，展现了卓越的远见，这已经产生了三个有前景的新产品线。22-24% 的一致营业利润率表明定价能力和运营效率应该继续...\"\n"
            "\n"
            "例如，如果看跌：\"尽管在增长行业中运营，但管理层未能将研发投资（仅占收入的 5%）转化为有意义的新产品。利润率在 10-15% 之间波动，显示运营执行不一致。公司面临来自三个具有更优分销网络的大型竞争对手的日益激烈的竞争。考虑到这些对长期增长可持续性的担忧...\"\n"
            "\n"
            "你必须输出一个 JSON 对象，包含：\n"
            "- \"signal\": \"bullish\" 或 \"bearish\" 或 \"neutral\"\n"
            "- \"confidence\": 0 到 100 之间的 float\n"
            "- \"reasoning\": 详细解释"
        )
        human_prompt = (
            "基于以下分析，创建菲利普·费雪风格的投资信号。\n"
            "\n"
            "{ticker} 的分析数据：\n"
            "{analysis_data}\n"
            "\n"
            "以以下 JSON 格式返回交易信号：\n"
            "{{\n"
            '  "signal": "bullish/bearish/neutral",\n'
            '  "confidence": float (0-100),\n'
            '  "reasoning": "字符串"\n'
            "}}"
        )
        default_reasoning = "分析错误，默认中性"
    else:
        system_prompt = (
            "You are a Phil Fisher AI agent, making investment decisions using his principles:\n"
            "\n"
            "1. Emphasize long-term growth potential and quality of management.\n"
            "2. Focus on companies investing in R&D for future products/services.\n"
            "3. Look for strong profitability and consistent margins.\n"
            "4. Willing to pay more for exceptional companies but still mindful of valuation.\n"
            "5. Rely on thorough research (scuttlebutt) and thorough fundamental checks.\n"
            "\n"
            "When providing your reasoning, be thorough and specific by:\n"
            "1. Discussing the company's growth prospects in detail with specific metrics and trends\n"
            "2. Evaluating management quality and their capital allocation decisions\n"
            "3. Highlighting R&D investments and product pipeline that could drive future growth\n"
            "4. Assessing consistency of margins and profitability metrics with precise numbers\n"
            "5. Explaining competitive advantages that could sustain growth over 3-5+ years\n"
            "6. Using Phil Fisher's methodical, growth-focused, and long-term oriented voice\n"
            "\n"
            "For example, if bullish: \"This company exhibits the sustained growth characteristics we seek, with revenue increasing at 18% annually over five years. Management has demonstrated exceptional foresight by allocating 15% of revenue to R&D, which has produced three promising new product lines. The consistent operating margins of 22-24% indicate pricing power and operational efficiency that should continue to...\"\n"
            "\n"
            "For example, if bearish: \"Despite operating in a growing industry, management has failed to translate R&D investments (only 5% of revenue) into meaningful new products. Margins have fluctuated between 10-15%, showing inconsistent operational execution. The company faces increasing competition from three larger competitors with superior distribution networks. Given these concerns about long-term growth sustainability...\"\n"
            "\n"
            "You must output a JSON object with:\n"
            "- \"signal\": \"bullish\" or \"bearish\" or \"neutral\"\n"
            "- \"confidence\": a float between 0 and 100\n"
            "- \"reasoning\": a detailed explanation"
        )
        human_prompt = (
            "Based on the following analysis, create a Phil Fisher-style investment signal.\n"
            "\n"
            "Analysis Data for {ticker}:\n"
            "{analysis_data}\n"
            "\n"
            "Return the trading signal in this JSON format:\n"
            "{{\n"
            '  "signal": "bullish/bearish/neutral",\n'
            '  "confidence": float (0-100),\n'
            '  "reasoning": "string"\n'
            "}}"
        )
        default_reasoning = "Error in analysis, defaulting to neutral"

    template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human_prompt),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def create_default_signal():
        return PhilFisherSignal(
            signal="neutral",
            confidence=0.0,
            reasoning=default_reasoning
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=PhilFisherSignal,
        state=state,
        agent_name=agent_id,
        default_factory=create_default_signal,
    )
