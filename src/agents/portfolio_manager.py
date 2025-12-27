import json
import time
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState, agent_id: str = "portfolio_manager"):
    """Makes final trading decisions and generates orders for multiple tickers"""

    progress.set_language(state.get("metadata", {}).get("language") or "en")
    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]

    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Processing analyst signals")

        # Find the corresponding risk manager for this portfolio manager
        if agent_id.startswith("portfolio_manager_"):
            suffix = agent_id.split('_')[-1]
            risk_manager_id = f"risk_management_agent_{suffix}"
        else:
            risk_manager_id = "risk_management_agent"  # Fallback for CLI

        risk_data = analyst_signals.get(risk_manager_id, {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0.0)
        current_prices[ticker] = float(risk_data.get("current_price", 0.0))

        # Calculate maximum shares allowed based on position limit and price
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] // current_prices[ticker])
        else:
            max_shares[ticker] = 0

        # Compress analyst signals to {sig, conf}
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if not agent.startswith("risk_management_agent") and ticker in signals:
                sig = signals[ticker].get("signal")
                conf = signals[ticker].get("confidence")
                if sig is not None and conf is not None:
                    ticker_signals[agent] = {"sig": sig, "conf": conf}
        signals_by_ticker[ticker] = ticker_signals

    state["data"]["current_prices"] = current_prices

    progress.update_status(agent_id, None, "Generating trading decisions")

    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        agent_id=agent_id,
        state=state,
    )
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()},
                             "Portfolio Manager")

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def compute_allowed_actions(
        tickers: list[str],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
) -> dict[str, dict[str, int]]:
    """Compute allowed actions and max quantities for each ticker deterministically."""
    allowed = {}
    cash = float(portfolio.get("cash", 0.0))
    positions = portfolio.get("positions", {}) or {}
    margin_requirement = float(portfolio.get("margin_requirement", 0.5))
    margin_used = float(portfolio.get("margin_used", 0.0))
    equity = float(portfolio.get("equity", cash))

    for ticker in tickers:
        price = float(current_prices.get(ticker, 0.0))
        pos = positions.get(
            ticker,
            {"long": 0, "long_cost_basis": 0.0, "short": 0, "short_cost_basis": 0.0},
        )
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        max_qty = int(max_shares.get(ticker, 0) or 0)

        # Start with zeros
        actions = {"buy": 0, "sell": 0, "short": 0, "cover": 0, "hold": 0}

        # Long side
        if long_shares > 0:
            actions["sell"] = long_shares
        if cash > 0 and price > 0:
            max_buy_cash = int(cash // price)
            max_buy = max(0, min(max_qty, max_buy_cash))
            if max_buy > 0:
                actions["buy"] = max_buy

        # Short side
        if short_shares > 0:
            actions["cover"] = short_shares
        if price > 0 and max_qty > 0:
            if margin_requirement <= 0.0:
                # If margin requirement is zero or unset, only cap by max_qty
                max_short = max_qty
            else:
                available_margin = max(0.0, (equity / margin_requirement) - margin_used)
                max_short_margin = int(available_margin // price)
                max_short = max(0, min(max_qty, max_short_margin))
            if max_short > 0:
                actions["short"] = max_short

        # Hold always valid
        actions["hold"] = 0

        # Prune zero-capacity actions to reduce tokens, keep hold
        pruned = {"hold": 0}
        for k, v in actions.items():
            if k != "hold" and v > 0:
                pruned[k] = v

        allowed[ticker] = pruned

    return allowed


def _compact_signals(signals_by_ticker: dict[str, dict]) -> dict[str, dict]:
    """Keep only {agent: {sig, conf}} and drop empty agents."""
    out = {}
    for t, agents in signals_by_ticker.items():
        if not agents:
            out[t] = {}
            continue
        compact = {}
        for agent, payload in agents.items():
            sig = payload.get("sig") or payload.get("signal")
            conf = payload.get("conf") if "conf" in payload else payload.get("confidence")
            if sig is not None and conf is not None:
                compact[agent] = {"sig": sig, "conf": conf}
        out[t] = compact
    return out


def generate_trading_decision(
        tickers: list[str],
        signals_by_ticker: dict[str, dict],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
        agent_id: str,
        state: AgentState,
) -> PortfolioManagerOutput:
    """Get decisions from the LLM with deterministic constraints and a minimal prompt."""

    # Deterministic constraints
    allowed_actions_full = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)

    # Pre-fill pure holds to avoid sending them to the LLM at all
    prefilled_decisions: dict[str, PortfolioDecision] = {}
    tickers_for_llm: list[str] = []
    for t in tickers:
        aa = allowed_actions_full.get(t, {"hold": 0})
        # If only 'hold' key exists, there is no trade possible
        if set(aa.keys()) == {"hold"}:
            prefilled_decisions[t] = PortfolioDecision(
                action="hold", quantity=0, confidence=100.0, reasoning="No valid trade available"
            )
        else:
            tickers_for_llm.append(t)

    if not tickers_for_llm:
        return PortfolioManagerOutput(decisions=prefilled_decisions)

    # Build compact payloads only for tickers sent to LLM
    compact_signals = _compact_signals({t: signals_by_ticker.get(t, {}) for t in tickers_for_llm})
    compact_allowed = {t: allowed_actions_full[t] for t in tickers_for_llm}
    
    # Build current positions info for context
    positions = portfolio.get("positions", {}) or {}
    compact_positions = {}
    for t in tickers_for_llm:
        pos = positions.get(t, {"long": 0, "short": 0})
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        compact_positions[t] = {
            "long": long_shares,
            "short": short_shares
        }

    # Enhanced prompt template with detailed analysis requirements
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a professional portfolio manager making final trading decisions.\n\n"
                "Your responsibilities:\n"
                "1. Analyze all analyst signals for each ticker (bullish/bearish/neutral with confidence levels)\n"
                "2. Consider current portfolio positions (if any) for each ticker\n"
                "3. Synthesize multiple analyst opinions into a coherent investment thesis\n"
                "4. Make trading decisions (buy/sell/short/cover/hold) with appropriate quantities\n"
                "5. Provide comprehensive reasoning that includes:\n"
                "   - Summary of analyst consensus or divergence\n"
                "   - Current position status and how it affects your decision\n"
                "   - Key factors driving the decision (valuation, growth, risk, sentiment, etc.)\n"
                "   - Specific metrics or data points that support your decision\n"
                "   - Risk considerations and position sizing rationale\n"
                "   - Expected outcome and time horizon\n\n"
                "CRITICAL - Signal-to-Action Mapping Rules (PRIORITY ORDER - THESE ARE MANDATORY):\n"
                "1. PRIMARY RULE: Follow analyst signals as the primary guide:\n"
                "   - If majority of analysts are BULLISH → Action should be BUY (if not holding) or HOLD/INCREASE (if already holding)\n"
                "   - If majority of analysts are BEARISH → Action should be SELL (if holding) or SHORT (if not holding)\n"
                "   - ⚠️ MANDATORY: If ALL or majority of analysts are NEUTRAL → Action MUST be HOLD (regardless of current position)\n"
                "   - If analysts are mixed (some bullish, some bearish) → Use weighted average confidence to decide\n\n"
                "2. EXCEPTION RULE: Only deviate from analyst signals if you have STRONG, SPECIFIC reasons:\n"
                "   - BULLISH signal but SELL: Only if (a) already holding significant position AND (b) profit-taking/rebalancing needed AND (c) price already reflects bullish expectations\n"
                "   - BEARISH signal but BUY: Only if (a) contrarian opportunity with strong value case AND (b) risk-reward is favorable\n"
                "   - ⚠️ CRITICAL: NEUTRAL signals CANNOT be overridden - they MUST result in HOLD action\n"
                "   - If you deviate (except for NEUTRAL→HOLD which is mandatory), you MUST provide detailed justification in reasoning\n\n"
                "3. POSITION-AWARE DECISIONS:\n"
                "   - If NOT holding and analysts are BULLISH → BUY (unless exception rule applies)\n"
                "   - If NOT holding and analysts are NEUTRAL → HOLD (no action) - MANDATORY\n"
                "   - If NOT holding and analysts are BEARISH → SHORT or HOLD (avoid buying)\n"
                "   - If ALREADY holding and analysts are BULLISH → HOLD or BUY more (increase position)\n"
                "   - If ALREADY holding and analysts are NEUTRAL → HOLD (maintain position) - MANDATORY, DO NOT SELL\n"
                "   - If ALREADY holding and analysts are BEARISH → SELL (reduce or exit position)\n\n"
                "⚠️ ABSOLUTE RULE: When analysts are NEUTRAL, the action MUST be HOLD. Selling on neutral signals is FORBIDDEN.\n\n"
                "Guidelines:\n"
                "- Pick one allowed action per ticker and a quantity ≤ the max allowed\n"
                "- Your reasoning should be detailed (200-500 characters), providing complete analysis basis and conclusion\n"
                "- Reference specific analyst signals and their confidence levels in your reasoning\n"
                "- Always mention current position status (if holding, state the quantity)\n"
                "- Explain why you chose this action over alternatives\n"
                "- Include quantitative support when available (e.g., '3 out of 5 analysts are bullish with avg confidence 75%')\n"
                "- No cash or margin calculations needed (already handled)\n"
                "- Return JSON only with the specified format"
            ),
            (
                "human",
                "Analyst Signals for each ticker:\n{signals}\n\n"
                "Current Portfolio Positions:\n{positions}\n\n"
                "Allowed Actions and Maximum Quantities:\n{allowed}\n\n"
                "Decision Process for each ticker:\n"
                "STEP 1: Calculate analyst signal consensus:\n"
                "   - Count bullish vs bearish vs neutral signals\n"
                "   - Calculate weighted average confidence (weight by confidence level)\n"
                "   - Determine majority signal (bullish/bearish/neutral)\n\n"
                "STEP 2: Check current position:\n"
                "   - If NOT holding: Follow signal-to-action mapping (bullish→buy, neutral→hold, bearish→short/hold)\n"
                "   - If ALREADY holding: Adjust based on signal (bullish→hold/buy more, neutral→hold, bearish→sell)\n\n"
                "STEP 3: Only deviate if you have STRONG, SPECIFIC reasons (see exception rule above)\n\n"
                "For each ticker, provide:\n"
                "1. A trading action (buy/sell/short/cover/hold) - MUST align with analyst signals unless exception applies\n"
                "2. The quantity (must be ≤ max allowed)\n"
                "3. Your confidence level (0-100)\n"
                "4. Detailed reasoning explaining:\n"
                "   - Analyst signal consensus (e.g., '3 out of 5 analysts are bullish with avg confidence 75%')\n"
                "   - How you applied the signal-to-action mapping rules\n"
                "   - Current position status and its impact on your decision\n"
                "   - If you deviated from the primary rule, the STRONG, SPECIFIC reason why\n"
                "   - Key factors supporting your decision\n"
                "   - Risk considerations\n\n"
                "Return JSON format:\n"
                "{{\n"
                '  "decisions": {{\n'
                '    "TICKER": {{\n'
                '      "action": "buy|sell|short|cover|hold",\n'
                '      "quantity": int,\n'
                '      "confidence": int (0-100),\n'
                '      "reasoning": "detailed analysis with complete basis and conclusion (200-500 chars)"\n'
                "    }}\n"
                "  }}\n"
                "}}"
            ),
        ]
    )

    prompt_data = {
        "signals": json.dumps(compact_signals, separators=(",", ":"), ensure_ascii=False),
        "positions": json.dumps(compact_positions, separators=(",", ":"), ensure_ascii=False),
        "allowed": json.dumps(compact_allowed, separators=(",", ":"), ensure_ascii=False),
    }
    prompt = template.invoke(prompt_data)

    # Default factory fills remaining tickers as hold if the LLM fails
    def create_default_portfolio_output():
        # start from prefilled
        decisions = dict(prefilled_decisions)
        for t in tickers_for_llm:
            decisions[t] = PortfolioDecision(
                action="hold", quantity=0, confidence=0.0, reasoning="Default decision: hold"
            )
        return PortfolioManagerOutput(decisions=decisions)

    llm_out = call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_portfolio_output,
    )

    # Merge prefilled holds with LLM results
    merged = dict(prefilled_decisions)
    merged.update(llm_out.decisions)
    
    # Post-process: Enforce strict rule that NEUTRAL signals must result in HOLD
    # This ensures consistency even if LLM doesn't follow the rules perfectly
    for ticker in tickers_for_llm:
        if ticker not in merged:
            continue
            
        # Get analyst signals for this ticker
        ticker_signals = signals_by_ticker.get(ticker, {})
        if not ticker_signals:
            continue
        
        # Count signal types
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        for agent, signal_data in ticker_signals.items():
            sig = signal_data.get("sig") or signal_data.get("signal")
            if sig:
                sig_lower = sig.lower()
                if sig_lower == "bullish":
                    bullish_count += 1
                elif sig_lower == "bearish":
                    bearish_count += 1
                elif sig_lower == "neutral":
                    neutral_count += 1
        
        total_signals = bullish_count + bearish_count + neutral_count
        
        # If all signals are neutral, MUST hold regardless of current position
        if total_signals > 0 and neutral_count == total_signals and bullish_count == 0 and bearish_count == 0:
            current_decision = merged[ticker]
            if current_decision.action != "hold":
                # Override the decision to hold
                merged[ticker] = PortfolioDecision(
                    action="hold",
                    quantity=0,
                    confidence=current_decision.confidence,
                    reasoning=f"All {neutral_count} analyst(s) are NEUTRAL. Following rule: NEUTRAL signals → HOLD. Original decision was {current_decision.action}, but corrected to HOLD per system rules."
                )
    
    return PortfolioManagerOutput(decisions=merged)
