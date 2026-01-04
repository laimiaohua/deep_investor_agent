from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    search_line_items,
    get_insider_trades,
    get_company_news,
    get_prices,
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

class StanleyDruckenmillerSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def stanley_druckenmiller_agent(state: AgentState, agent_id: str = "stanley_druckenmiller_agent"):
    """
    Analyzes stocks using Stanley Druckenmiller's investing principles:
      - Seeking asymmetric risk-reward opportunities
      - Emphasizing growth, momentum, and sentiment
      - Willing to be aggressive if conditions are favorable
      - Focus on preserving capital by avoiding high-risk, low-reward bets

    Returns a bullish/bearish/neutral signal with confidence and reasoning.
    """
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    massive_api_key = get_api_key_from_state(state, "MASSIVE_API_KEY")
    cn_api_key = get_api_key_from_state(state, "DEEPALPHA_API_KEY")
    use_openbb = get_use_openbb_from_state(state)
    analysis_data = {}
    druck_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=5, api_key=api_key, cn_api_key=cn_api_key, massive_api_key=massive_api_key, use_openbb=use_openbb)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        # Include relevant line items for Stan Druckenmiller's approach:
        #   - Growth & momentum: revenue, EPS, operating_income, ...
        #   - Valuation: net_income, free_cash_flow, ebit, ebitda
        #   - Leverage: total_debt, shareholders_equity
        #   - Liquidity: cash_and_equivalents
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "earnings_per_share",
                "net_income",
                "operating_income",
                "gross_margin",
                "operating_margin",
                "free_cash_flow",
                "capital_expenditure",
                "cash_and_equivalents",
                "total_debt",
                "shareholders_equity",
                "outstanding_shares",
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
        market_cap = get_market_cap(ticker, end_date, api_key=api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(ticker, end_date, limit=50, api_key=api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        company_news = get_company_news(ticker, end_date, limit=50, api_key=api_key, massive_api_key=massive_api_key)

        progress.update_status(agent_id, ticker, "Fetching recent price data for momentum")
        prices = get_prices(ticker, start_date=start_date, end_date=end_date, api_key=api_key, use_openbb=use_openbb)

        progress.update_status(agent_id, ticker, "Analyzing growth & momentum")
        growth_momentum_analysis = analyze_growth_and_momentum(financial_line_items, prices)

        progress.update_status(agent_id, ticker, "Analyzing sentiment")
        sentiment_analysis = analyze_sentiment(company_news)

        progress.update_status(agent_id, ticker, "Analyzing insider activity")
        insider_activity = analyze_insider_activity(insider_trades)

        progress.update_status(agent_id, ticker, "Analyzing risk-reward")
        risk_reward_analysis = analyze_risk_reward(financial_line_items, prices)

        progress.update_status(agent_id, ticker, "Performing Druckenmiller-style valuation")
        valuation_analysis = analyze_druckenmiller_valuation(financial_line_items, market_cap)

        # Combine partial scores with weights typical for Druckenmiller:
        #   35% Growth/Momentum, 20% Risk/Reward, 20% Valuation,
        #   15% Sentiment, 10% Insider Activity = 100%
        total_score = (
            growth_momentum_analysis["score"] * 0.35
            + risk_reward_analysis["score"] * 0.20
            + valuation_analysis["score"] * 0.20
            + sentiment_analysis["score"] * 0.15
            + insider_activity["score"] * 0.10
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
            "growth_momentum_analysis": growth_momentum_analysis,
            "sentiment_analysis": sentiment_analysis,
            "insider_activity": insider_activity,
            "risk_reward_analysis": risk_reward_analysis,
            "valuation_analysis": valuation_analysis,
        }

        progress.update_status(agent_id, ticker, "Generating Stanley Druckenmiller analysis")
        druck_output = generate_druckenmiller_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        druck_analysis[ticker] = {
            "signal": druck_output.signal,
            "confidence": druck_output.confidence,
            "reasoning": druck_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=druck_output.reasoning)

    # Wrap results in a single message
    message = HumanMessage(content=json.dumps(druck_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(druck_analysis, "Stanley Druckenmiller Agent")

    state["data"]["analyst_signals"][agent_id] = druck_analysis

    progress.update_status(agent_id, None, "Done")
    
    return {"messages": [message], "data": state["data"]}


def analyze_growth_and_momentum(financial_line_items: list, prices: list) -> dict:
    """
    Evaluate:
      - Revenue Growth (YoY)
      - EPS Growth (YoY)
      - Price Momentum
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {"score": 0, "details": "Insufficient financial data for growth analysis"}

    details = []
    raw_score = 0  # We'll sum up a maximum of 9 raw points, then scale to 0–10

    #
    # 1. Revenue Growth (annualized CAGR)
    #
    revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
    if len(revenues) >= 2:
        latest_rev = revenues[0]
        older_rev = revenues[-1]
        num_years = len(revenues) - 1
        if older_rev > 0 and latest_rev > 0:
            # CAGR formula: (ending_value/beginning_value)^(1/years) - 1
            rev_growth = (latest_rev / older_rev) ** (1 / num_years) - 1
            if rev_growth > 0.08:  # 8% annualized (adjusted for CAGR)
                raw_score += 3
                details.append(f"Strong annualized revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.04:  # 4% annualized
                raw_score += 2
                details.append(f"Moderate annualized revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.01:  # 1% annualized
                raw_score += 1
                details.append(f"Slight annualized revenue growth: {rev_growth:.1%}")
            else:
                details.append(f"Minimal/negative revenue growth: {rev_growth:.1%}")
        else:
            details.append("Older revenue is zero/negative; can't compute revenue growth.")
    else:
        details.append("Not enough revenue data points for growth calculation.")

    #
    # 2. EPS Growth (annualized CAGR)
    #
    eps_values = [fi.earnings_per_share for fi in financial_line_items if fi.earnings_per_share is not None]
    if len(eps_values) >= 2:
        latest_eps = eps_values[0]
        older_eps = eps_values[-1]
        num_years = len(eps_values) - 1
        # Calculate CAGR for positive EPS values
        if older_eps > 0 and latest_eps > 0:
            # CAGR formula for EPS
            eps_growth = (latest_eps / older_eps) ** (1 / num_years) - 1
            if eps_growth > 0.08:  # 8% annualized (adjusted for CAGR)
                raw_score += 3
                details.append(f"Strong annualized EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.04:  # 4% annualized
                raw_score += 2
                details.append(f"Moderate annualized EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.01:  # 1% annualized
                raw_score += 1
                details.append(f"Slight annualized EPS growth: {eps_growth:.1%}")
            else:
                details.append(f"Minimal/negative annualized EPS growth: {eps_growth:.1%}")
        else:
            details.append("Older EPS is near zero; skipping EPS growth calculation.")
    else:
        details.append("Not enough EPS data points for growth calculation.")

    #
    # 3. Price Momentum
    #
    # We'll give up to 3 points for strong momentum
    if prices and len(prices) > 30:
        sorted_prices = sorted(prices, key=lambda p: p.time)
        close_prices = [p.close for p in sorted_prices if p.close is not None]
        if len(close_prices) >= 2:
            start_price = close_prices[0]
            end_price = close_prices[-1]
            if start_price > 0:
                pct_change = (end_price - start_price) / start_price
                if pct_change > 0.50:
                    raw_score += 3
                    details.append(f"Very strong price momentum: {pct_change:.1%}")
                elif pct_change > 0.20:
                    raw_score += 2
                    details.append(f"Moderate price momentum: {pct_change:.1%}")
                elif pct_change > 0:
                    raw_score += 1
                    details.append(f"Slight positive momentum: {pct_change:.1%}")
                else:
                    details.append(f"Negative price momentum: {pct_change:.1%}")
            else:
                details.append("Invalid start price (<= 0); can't compute momentum.")
        else:
            details.append("Insufficient price data for momentum calculation.")
    else:
        details.append("Not enough recent price data for momentum analysis.")

    # We assigned up to 3 points each for:
    #   revenue growth, eps growth, momentum
    # => max raw_score = 9
    # Scale to 0–10
    final_score = min(10, (raw_score / 9) * 10)

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
        # Use transaction_shares to determine if it's a buy or sell
        # Negative shares = sell, positive shares = buy
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
        # Heavy buying => +3 points from the neutral 5 => 8
        score = 8
        details.append(f"Heavy insider buying: {buys} buys vs. {sells} sells")
    elif buy_ratio > 0.4:
        # Moderate buying => +1 => 6
        score = 6
        details.append(f"Moderate insider buying: {buys} buys vs. {sells} sells")
    else:
        # Low insider buying => -1 => 4
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
        # More than 30% negative => somewhat bearish => 3/10
        score = 3
        details.append(f"High proportion of negative headlines: {negative_count}/{len(news_items)}")
    elif negative_count > 0:
        # Some negativity => 6/10
        score = 6
        details.append(f"Some negative headlines: {negative_count}/{len(news_items)}")
    else:
        # Mostly positive => 8/10
        score = 8
        details.append("Mostly positive/neutral headlines")

    return {"score": score, "details": "; ".join(details)}


def analyze_risk_reward(financial_line_items: list, prices: list) -> dict:
    """
    Assesses risk via:
      - Debt-to-Equity
      - Price Volatility
    Aims for strong upside with contained downside.
    """
    if not financial_line_items or not prices:
        return {"score": 0, "details": "Insufficient data for risk-reward analysis"}

    details = []
    raw_score = 0  # We'll accumulate up to 6 raw points, then scale to 0-10

    #
    # 1. Debt-to-Equity
    #
    debt_values = [fi.total_debt for fi in financial_line_items if fi.total_debt is not None]
    equity_values = [fi.shareholders_equity for fi in financial_line_items if fi.shareholders_equity is not None]

    if debt_values and equity_values and len(debt_values) == len(equity_values) and len(debt_values) > 0:
        recent_debt = debt_values[0]
        recent_equity = equity_values[0] if equity_values[0] else 1e-9
        de_ratio = recent_debt / recent_equity
        if de_ratio < 0.3:
            raw_score += 3
            details.append(f"Low debt-to-equity: {de_ratio:.2f}")
        elif de_ratio < 0.7:
            raw_score += 2
            details.append(f"Moderate debt-to-equity: {de_ratio:.2f}")
        elif de_ratio < 1.5:
            raw_score += 1
            details.append(f"Somewhat high debt-to-equity: {de_ratio:.2f}")
        else:
            details.append(f"High debt-to-equity: {de_ratio:.2f}")
    else:
        details.append("No consistent debt/equity data available.")

    #
    # 2. Price Volatility
    #
    if len(prices) > 10:
        sorted_prices = sorted(prices, key=lambda p: p.time)
        close_prices = [p.close for p in sorted_prices if p.close is not None]
        if len(close_prices) > 10:
            daily_returns = []
            for i in range(1, len(close_prices)):
                prev_close = close_prices[i - 1]
                if prev_close > 0:
                    daily_returns.append((close_prices[i] - prev_close) / prev_close)
            if daily_returns:
                stdev = statistics.pstdev(daily_returns)  # population stdev
                if stdev < 0.01:
                    raw_score += 3
                    details.append(f"Low volatility: daily returns stdev {stdev:.2%}")
                elif stdev < 0.02:
                    raw_score += 2
                    details.append(f"Moderate volatility: daily returns stdev {stdev:.2%}")
                elif stdev < 0.04:
                    raw_score += 1
                    details.append(f"High volatility: daily returns stdev {stdev:.2%}")
                else:
                    details.append(f"Very high volatility: daily returns stdev {stdev:.2%}")
            else:
                details.append("Insufficient daily returns data for volatility calc.")
        else:
            details.append("Not enough close-price data points for volatility analysis.")
    else:
        details.append("Not enough price data for volatility analysis.")

    # raw_score out of 6 => scale to 0–10
    final_score = min(10, (raw_score / 6) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_druckenmiller_valuation(financial_line_items: list, market_cap: float | None) -> dict:
    """
    Druckenmiller is willing to pay up for growth, but still checks:
      - P/E
      - P/FCF
      - EV/EBIT
      - EV/EBITDA
    Each can yield up to 2 points => max 8 raw points => scale to 0–10.
    """
    if not financial_line_items or market_cap is None:
        return {"score": 0, "details": "Insufficient data to perform valuation"}

    details = []
    raw_score = 0

    # Gather needed data
    net_incomes = [fi.net_income for fi in financial_line_items if fi.net_income is not None]
    fcf_values = [fi.free_cash_flow for fi in financial_line_items if fi.free_cash_flow is not None]
    ebit_values = [fi.ebit for fi in financial_line_items if fi.ebit is not None]
    ebitda_values = [fi.ebitda for fi in financial_line_items if fi.ebitda is not None]

    # For EV calculation, let's get the most recent total_debt & cash
    debt_values = [fi.total_debt for fi in financial_line_items if fi.total_debt is not None]
    cash_values = [fi.cash_and_equivalents for fi in financial_line_items if fi.cash_and_equivalents is not None]
    recent_debt = debt_values[0] if debt_values else 0
    recent_cash = cash_values[0] if cash_values else 0

    enterprise_value = market_cap + recent_debt - recent_cash

    # 1) P/E
    recent_net_income = net_incomes[0] if net_incomes else None
    if recent_net_income and recent_net_income > 0:
        pe = market_cap / recent_net_income
        pe_points = 0
        if pe < 15:
            pe_points = 2
            details.append(f"Attractive P/E: {pe:.2f}")
        elif pe < 25:
            pe_points = 1
            details.append(f"Fair P/E: {pe:.2f}")
        else:
            details.append(f"High or Very high P/E: {pe:.2f}")
        raw_score += pe_points
    else:
        details.append("No positive net income for P/E calculation")

    # 2) P/FCF
    recent_fcf = fcf_values[0] if fcf_values else None
    if recent_fcf and recent_fcf > 0:
        pfcf = market_cap / recent_fcf
        pfcf_points = 0
        if pfcf < 15:
            pfcf_points = 2
            details.append(f"Attractive P/FCF: {pfcf:.2f}")
        elif pfcf < 25:
            pfcf_points = 1
            details.append(f"Fair P/FCF: {pfcf:.2f}")
        else:
            details.append(f"High/Very high P/FCF: {pfcf:.2f}")
        raw_score += pfcf_points
    else:
        details.append("No positive free cash flow for P/FCF calculation")

    # 3) EV/EBIT
    recent_ebit = ebit_values[0] if ebit_values else None
    if enterprise_value > 0 and recent_ebit and recent_ebit > 0:
        ev_ebit = enterprise_value / recent_ebit
        ev_ebit_points = 0
        if ev_ebit < 15:
            ev_ebit_points = 2
            details.append(f"Attractive EV/EBIT: {ev_ebit:.2f}")
        elif ev_ebit < 25:
            ev_ebit_points = 1
            details.append(f"Fair EV/EBIT: {ev_ebit:.2f}")
        else:
            details.append(f"High EV/EBIT: {ev_ebit:.2f}")
        raw_score += ev_ebit_points
    else:
        details.append("No valid EV/EBIT because EV <= 0 or EBIT <= 0")

    # 4) EV/EBITDA
    recent_ebitda = ebitda_values[0] if ebitda_values else None
    if enterprise_value > 0 and recent_ebitda and recent_ebitda > 0:
        ev_ebitda = enterprise_value / recent_ebitda
        ev_ebitda_points = 0
        if ev_ebitda < 10:
            ev_ebitda_points = 2
            details.append(f"Attractive EV/EBITDA: {ev_ebitda:.2f}")
        elif ev_ebitda < 18:
            ev_ebitda_points = 1
            details.append(f"Fair EV/EBITDA: {ev_ebitda:.2f}")
        else:
            details.append(f"High EV/EBITDA: {ev_ebitda:.2f}")
        raw_score += ev_ebitda_points
    else:
        details.append("No valid EV/EBITDA because EV <= 0 or EBITDA <= 0")

    # We have up to 2 points for each of the 4 metrics => 8 raw points max
    # Scale raw_score to 0–10
    final_score = min(10, (raw_score / 8) * 10)

    return {"score": final_score, "details": "; ".join(details)}


def generate_druckenmiller_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
) -> StanleyDruckenmillerSignal:
    """
    Generates a JSON signal in the style of Stanley Druckenmiller.
    """
    # 获取语言设置
    language = state.get("metadata", {}).get("language") or "en"
    is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw", "zh_hans", "zh_hant"])

    # 根据语言生成不同的 prompt
    if is_chinese:
        system_prompt = (
            "你是斯坦利·德鲁肯米勒 AI 智能体，使用他的原则做出投资决策：\n"
            "\n"
            "1. 寻找不对称的风险回报机会（巨大上行空间，有限下行风险）。\n"
            "2. 强调增长、动量和市场情绪。\n"
            "3. 通过避免重大回撤来保护资本。\n"
            "4. 愿意为真正的增长领导者支付更高估值。\n"
            "5. 当确信度高时积极行动。\n"
            "6. 如果论点改变，快速止损。\n"
            "\n"
            "规则：\n"
            "- 奖励显示强劲收入/收益增长和积极股票动量的公司。\n"
            "- 将情绪和内部人活动评估为支持性或矛盾信号。\n"
            "- 注意威胁资本的高杠杆或极端波动性。\n"
            "- 输出包含信号、信心和推理字符串的 JSON 对象。\n"
            "\n"
            "在提供推理时，要详细具体：\n"
            "1. 解释最影响你决策的增长和动量指标\n"
            "2. 用具体数字证据突出风险回报特征\n"
            "3. 讨论可能推动价格行动的市场情绪和催化剂\n"
            "4. 解决上行潜力和下行风险\n"
            "5. 提供相对于增长前景的具体估值背景\n"
            "6. 使用斯坦利·德鲁肯米勒果断、以动量为重点、信念驱动的语调\n"
            "\n"
            "例如，如果看涨：\"该公司显示出卓越的动量，收入从 22% 加速到 35% 年同比增长，股票在过去三个月上涨 28%。风险回报高度不对称，基于 FCF 倍数扩张有 70% 的上行潜力，考虑到强劲的资产负债表（现金与债务比为 3 倍），只有 15% 的下行风险。内部人买入和积极的市场情绪提供了额外的顺风...\"\n"
            "\n"
            "例如，如果看跌：\"尽管最近股票有动量，但收入增长从 30% 放缓到 12% 年同比增长，营业利润率正在收缩。风险回报主张不利，只有 10% 的上行潜力，而面临 40% 的下行风险。竞争格局正在加剧，内部人卖出表明信心减弱。我在其他地方看到更好的机会，有更有利的设置...\""
        )
        human_prompt = (
            "基于以下分析，创建德鲁肯米勒风格的投资信号。\n"
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
            "You are a Stanley Druckenmiller AI agent, making investment decisions using his principles:\n"
            "\n"
            "1. Seek asymmetric risk-reward opportunities (large upside, limited downside).\n"
            "2. Emphasize growth, momentum, and market sentiment.\n"
            "3. Preserve capital by avoiding major drawdowns.\n"
            "4. Willing to pay higher valuations for true growth leaders.\n"
            "5. Be aggressive when conviction is high.\n"
            "6. Cut losses quickly if the thesis changes.\n"
            "\n"
            "Rules:\n"
            "- Reward companies showing strong revenue/earnings growth and positive stock momentum.\n"
            "- Evaluate sentiment and insider activity as supportive or contradictory signals.\n"
            "- Watch out for high leverage or extreme volatility that threatens capital.\n"
            "- Output a JSON object with signal, confidence, and a reasoning string.\n"
            "\n"
            "When providing your reasoning, be thorough and specific by:\n"
            "1. Explaining the growth and momentum metrics that most influenced your decision\n"
            "2. Highlighting the risk-reward profile with specific numerical evidence\n"
            "3. Discussing market sentiment and catalysts that could drive price action\n"
            "4. Addressing both upside potential and downside risks\n"
            "5. Providing specific valuation context relative to growth prospects\n"
            "6. Using Stanley Druckenmiller's decisive, momentum-focused, and conviction-driven voice\n"
            "\n"
            "For example, if bullish: \"The company shows exceptional momentum with revenue accelerating from 22% to 35% YoY and the stock up 28% over the past three months. Risk-reward is highly asymmetric with 70% upside potential based on FCF multiple expansion and only 15% downside risk given the strong balance sheet with 3x cash-to-debt. Insider buying and positive market sentiment provide additional tailwinds...\"\n"
            "\n"
            "For example, if bearish: \"Despite recent stock momentum, revenue growth has decelerated from 30% to 12% YoY, and operating margins are contracting. The risk-reward proposition is unfavorable with limited 10% upside potential against 40% downside risk. The competitive landscape is intensifying, and insider selling suggests waning confidence. I'm seeing better opportunities elsewhere with more favorable setups...\""
        )
        human_prompt = (
            "Based on the following analysis, create a Druckenmiller-style investment signal.\n"
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
        return StanleyDruckenmillerSignal(
            signal="neutral",
            confidence=0.0,
            reasoning=default_reasoning
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=StanleyDruckenmillerSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_signal,
    )
