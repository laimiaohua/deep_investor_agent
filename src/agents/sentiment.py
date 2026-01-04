from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
import pandas as pd
import numpy as np
import json
from src.utils.api_key import get_api_key_from_state, get_use_openbb_from_state
from src.tools.api import get_insider_trades, get_company_news


##### Sentiment Agent #####
def sentiment_analyst_agent(state: AgentState, agent_id: str = "sentiment_analyst_agent"):
    """Analyzes market sentiment and generates trading signals for multiple tickers."""
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    massive_api_key = get_api_key_from_state(state, "MASSIVE_API_KEY")
    use_openbb = get_use_openbb_from_state(state)
    # Initialize sentiment analysis for each ticker
    sentiment_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching insider trades")

        # Get the insider trades
        insider_trades = get_insider_trades(
            ticker=ticker,
            end_date=end_date,
            limit=1000,
            api_key=api_key,
            massive_api_key=massive_api_key,
        )

        progress.update_status(agent_id, ticker, "Analyzing trading patterns")

        # Get the signals from the insider trades
        transaction_shares = pd.Series([t.transaction_shares for t in insider_trades]).dropna()
        insider_signals = np.where(transaction_shares < 0, "bearish", "bullish").tolist()

        progress.update_status(agent_id, ticker, "Fetching company news")

        # Get the company news
        company_news = get_company_news(ticker, end_date, limit=100, api_key=api_key, massive_api_key=massive_api_key, use_openbb=use_openbb)

        # Get the sentiment from the company news
        sentiment = pd.Series([n.sentiment for n in company_news]).dropna()
        news_signals = np.where(sentiment == "negative", "bearish", 
                              np.where(sentiment == "positive", "bullish", "neutral")).tolist()
        
        progress.update_status(agent_id, ticker, "Combining signals")
        # Combine signals from both sources with weights
        insider_weight = 0.3
        news_weight = 0.7
        
        # Calculate weighted signal counts
        bullish_signals = (
            insider_signals.count("bullish") * insider_weight +
            news_signals.count("bullish") * news_weight
        )
        bearish_signals = (
            insider_signals.count("bearish") * insider_weight +
            news_signals.count("bearish") * news_weight
        )

        if bullish_signals > bearish_signals:
            overall_signal = "bullish"
        elif bearish_signals > bullish_signals:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        # Calculate confidence level based on the weighted proportion
        total_weighted_signals = len(insider_signals) * insider_weight + len(news_signals) * news_weight
        confidence = 0  # Default confidence when there are no signals
        if total_weighted_signals > 0:
            confidence = round((max(bullish_signals, bearish_signals) / total_weighted_signals) * 100, 2)
        
        # Create structured reasoning similar to technical analysis
        reasoning = {
            "insider_trading": {
                "signal": "bullish" if insider_signals.count("bullish") > insider_signals.count("bearish") else 
                         "bearish" if insider_signals.count("bearish") > insider_signals.count("bullish") else "neutral",
                "confidence": round((max(insider_signals.count("bullish"), insider_signals.count("bearish")) / max(len(insider_signals), 1)) * 100),
                "metrics": {
                    "total_trades": len(insider_signals),
                    "bullish_trades": insider_signals.count("bullish"),
                    "bearish_trades": insider_signals.count("bearish"),
                    "weight": insider_weight,
                    "weighted_bullish": round(insider_signals.count("bullish") * insider_weight, 1),
                    "weighted_bearish": round(insider_signals.count("bearish") * insider_weight, 1),
                }
            },
            "news_sentiment": {
                "signal": "bullish" if news_signals.count("bullish") > news_signals.count("bearish") else 
                         "bearish" if news_signals.count("bearish") > news_signals.count("bullish") else "neutral",
                "confidence": round((max(news_signals.count("bullish"), news_signals.count("bearish")) / max(len(news_signals), 1)) * 100),
                "metrics": {
                    "total_articles": len(news_signals),
                    "bullish_articles": news_signals.count("bullish"),
                    "bearish_articles": news_signals.count("bearish"),
                    "neutral_articles": news_signals.count("neutral"),
                    "weight": news_weight,
                    "weighted_bullish": round(news_signals.count("bullish") * news_weight, 1),
                    "weighted_bearish": round(news_signals.count("bearish") * news_weight, 1),
                }
            },
            "combined_analysis": {
                "total_weighted_bullish": round(bullish_signals, 1),
                "total_weighted_bearish": round(bearish_signals, 1),
                "signal_determination": f"{'Bullish' if bullish_signals > bearish_signals else 'Bearish' if bearish_signals > bullish_signals else 'Neutral'} based on weighted signal comparison"
            }
        }

        # Generate human-readable reasoning text
        reasoning_text = generate_sentiment_reasoning(
            ticker=ticker,
            overall_signal=overall_signal,
            confidence=confidence,
            reasoning=reasoning,
            state=state
        )
        
        sentiment_analysis[ticker] = {
            "signal": overall_signal,
            "confidence": confidence,
            "reasoning": reasoning_text,  # Use text instead of JSON
        }

        progress.update_status(agent_id, ticker, "Done", analysis=reasoning_text)

    # Create the sentiment message
    message = HumanMessage(
        content=json.dumps(sentiment_analysis),
        name=agent_id,
    )

    # Print the reasoning if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(sentiment_analysis, "Sentiment Analysis Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = sentiment_analysis

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": [message],
        "data": data,
    }


def generate_sentiment_reasoning(
    ticker: str,
    overall_signal: str,
    confidence: float,
    reasoning: dict,
    state: AgentState,
) -> str:
    """
    Generate human-readable reasoning text from sentiment analysis data.
    
    Args:
        ticker: Stock ticker symbol
        overall_signal: Overall signal (bullish/bearish/neutral)
        confidence: Confidence level (0-100)
        reasoning: Dictionary containing all sentiment analysis signals
        state: Agent state for language settings
    
    Returns:
        str: Human-readable reasoning text
    """
    language = state.get("metadata", {}).get("language") or "en"
    is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw"])
    
    if is_chinese:
        # 中文描述
        lines = [
            f"【{ticker} 情绪分析摘要】",
            f"综合信号: {overall_signal.upper()} (置信度: {confidence}%)",
            "",
            "数据源分析:",
        ]
        
        # 内部人交易
        if "insider_trading" in reasoning:
            insider = reasoning["insider_trading"]
            insider_sig = insider.get("signal", "neutral")
            insider_conf = insider.get("confidence", 0)
            insider_metrics = insider.get("metrics", {})
            total_trades = insider_metrics.get("total_trades", 0)
            bullish_trades = insider_metrics.get("bullish_trades", 0)
            bearish_trades = insider_metrics.get("bearish_trades", 0)
            lines.append(f"• 内部人交易: {insider_sig.upper()} (置信度: {insider_conf}%)")
            lines.append(f"  - 总交易数: {total_trades}, 看涨: {bullish_trades}, 看跌: {bearish_trades}")
        
        # 新闻情绪
        if "news_sentiment" in reasoning:
            news = reasoning["news_sentiment"]
            news_sig = news.get("signal", "neutral")
            news_conf = news.get("confidence", 0)
            news_metrics = news.get("metrics", {})
            total_articles = news_metrics.get("total_articles", 0)
            bullish_articles = news_metrics.get("bullish_articles", 0)
            bearish_articles = news_metrics.get("bearish_articles", 0)
            neutral_articles = news_metrics.get("neutral_articles", 0)
            lines.append(f"• 新闻情绪: {news_sig.upper()} (置信度: {news_conf}%)")
            lines.append(f"  - 总文章数: {total_articles}, 看涨: {bullish_articles}, 看跌: {bearish_articles}, 中性: {neutral_articles}")
        
        # 综合分析
        if "combined_analysis" in reasoning:
            combined = reasoning["combined_analysis"]
            total_bullish = combined.get("total_weighted_bullish", 0)
            total_bearish = combined.get("total_weighted_bearish", 0)
            lines.append(f"• 加权综合: 看涨信号 {total_bullish:.1f}, 看跌信号 {total_bearish:.1f}")
        
        lines.append("")
        lines.append(f"结论: 基于内部人交易和新闻情绪的综合分析，{ticker}当前市场情绪呈现{overall_signal.upper()}信号，综合置信度为{confidence}%。")
        
        return "\n".join(lines)
    else:
        # English description
        lines = [
            f"【{ticker} Sentiment Analysis Summary】",
            f"Combined Signal: {overall_signal.upper()} (Confidence: {confidence}%)",
            "",
            "Data Source Analysis:",
        ]
        
        # Insider Trading
        if "insider_trading" in reasoning:
            insider = reasoning["insider_trading"]
            insider_sig = insider.get("signal", "neutral")
            insider_conf = insider.get("confidence", 0)
            insider_metrics = insider.get("metrics", {})
            total_trades = insider_metrics.get("total_trades", 0)
            bullish_trades = insider_metrics.get("bullish_trades", 0)
            bearish_trades = insider_metrics.get("bearish_trades", 0)
            lines.append(f"• Insider Trading: {insider_sig.upper()} (Confidence: {insider_conf}%)")
            lines.append(f"  - Total Trades: {total_trades}, Bullish: {bullish_trades}, Bearish: {bearish_trades}")
        
        # News Sentiment
        if "news_sentiment" in reasoning:
            news = reasoning["news_sentiment"]
            news_sig = news.get("signal", "neutral")
            news_conf = news.get("confidence", 0)
            news_metrics = news.get("metrics", {})
            total_articles = news_metrics.get("total_articles", 0)
            bullish_articles = news_metrics.get("bullish_articles", 0)
            bearish_articles = news_metrics.get("bearish_articles", 0)
            neutral_articles = news_metrics.get("neutral_articles", 0)
            lines.append(f"• News Sentiment: {news_sig.upper()} (Confidence: {news_conf}%)")
            lines.append(f"  - Total Articles: {total_articles}, Bullish: {bullish_articles}, Bearish: {bearish_articles}, Neutral: {neutral_articles}")
        
        # Combined Analysis
        if "combined_analysis" in reasoning:
            combined = reasoning["combined_analysis"]
            total_bullish = combined.get("total_weighted_bullish", 0)
            total_bearish = combined.get("total_weighted_bearish", 0)
            lines.append(f"• Weighted Combined: Bullish Signals {total_bullish:.1f}, Bearish Signals {total_bearish:.1f}")
        
        lines.append("")
        lines.append(f"Conclusion: Based on insider trading and news sentiment analysis, {ticker} shows a {overall_signal.upper()} sentiment signal with {confidence}% confidence.")
        
        return "\n".join(lines)
