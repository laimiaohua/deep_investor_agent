import math

from langchain_core.messages import HumanMessage

from src.graph.state import AgentState, show_agent_reasoning
from src.utils.api_key import get_api_key_from_state
import json
import pandas as pd
import numpy as np

from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress


def safe_float(value, default=0.0):
    """
    Safely convert a value to float, handling NaN cases
    
    Args:
        value: The value to convert (can be pandas scalar, numpy value, etc.)
        default: Default value to return if the input is NaN or invalid
    
    Returns:
        float: The converted value or default if NaN/invalid
    """
    try:
        if pd.isna(value) or np.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


##### Technical Analyst #####
def technical_analyst_agent(state: AgentState, agent_id: str = "technical_analyst_agent"):
    """
    Sophisticated technical analysis system that combines multiple trading strategies for multiple tickers:
    1. Trend Following
    2. Mean Reversion
    3. Momentum
    4. Volatility Analysis
    5. Statistical Arbitrage Signals
    """
    progress.set_language(state.get("metadata", {}).get("language") or "en")
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    # Initialize analysis for each ticker
    technical_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Analyzing price data")

        # Get the historical price data
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )

        if not prices:
            progress.update_status(agent_id, ticker, "Failed: No price data found")
            continue

        # Convert prices to a DataFrame
        prices_df = prices_to_df(prices)

        progress.update_status(agent_id, ticker, "Calculating trend signals")
        trend_signals = calculate_trend_signals(prices_df)

        progress.update_status(agent_id, ticker, "Calculating mean reversion")
        mean_reversion_signals = calculate_mean_reversion_signals(prices_df)

        progress.update_status(agent_id, ticker, "Calculating momentum")
        momentum_signals = calculate_momentum_signals(prices_df)

        progress.update_status(agent_id, ticker, "Analyzing volatility")
        volatility_signals = calculate_volatility_signals(prices_df)

        progress.update_status(agent_id, ticker, "Statistical analysis")
        stat_arb_signals = calculate_stat_arb_signals(prices_df)

        # Combine all signals using a weighted ensemble approach
        strategy_weights = {
            "trend": 0.25,
            "mean_reversion": 0.20,
            "momentum": 0.25,
            "volatility": 0.15,
            "stat_arb": 0.15,
        }

        progress.update_status(agent_id, ticker, "Combining signals")
        combined_signal = weighted_signal_combination(
            {
                "trend": trend_signals,
                "mean_reversion": mean_reversion_signals,
                "momentum": momentum_signals,
                "volatility": volatility_signals,
                "stat_arb": stat_arb_signals,
            },
            strategy_weights,
        )

        # Generate detailed analysis report for this ticker
        reasoning_data = {
            "trend_following": {
                "signal": trend_signals["signal"],
                "confidence": round(trend_signals["confidence"] * 100),
                "metrics": normalize_pandas(trend_signals["metrics"]),
            },
            "mean_reversion": {
                "signal": mean_reversion_signals["signal"],
                "confidence": round(mean_reversion_signals["confidence"] * 100),
                "metrics": normalize_pandas(mean_reversion_signals["metrics"]),
            },
            "momentum": {
                "signal": momentum_signals["signal"],
                "confidence": round(momentum_signals["confidence"] * 100),
                "metrics": normalize_pandas(momentum_signals["metrics"]),
            },
            "volatility": {
                "signal": volatility_signals["signal"],
                "confidence": round(volatility_signals["confidence"] * 100),
                "metrics": normalize_pandas(volatility_signals["metrics"]),
            },
            "statistical_arbitrage": {
                "signal": stat_arb_signals["signal"],
                "confidence": round(stat_arb_signals["confidence"] * 100),
                "metrics": normalize_pandas(stat_arb_signals["metrics"]),
            },
        }
        
        # Generate human-readable reasoning text
        reasoning_text = generate_technical_reasoning(
            ticker=ticker,
            combined_signal=combined_signal,
            reasoning_data=reasoning_data,
            state=state
        )
        
        technical_analysis[ticker] = {
            "signal": combined_signal["signal"],
            "confidence": round(combined_signal["confidence"] * 100),
            "reasoning": reasoning_text,  # Use text instead of JSON
        }
        progress.update_status(agent_id, ticker, "Done", analysis=reasoning_text)

    # Create the technical analyst message
    message = HumanMessage(
        content=json.dumps(technical_analysis),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(technical_analysis, "Technical Analyst")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = technical_analysis

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": data,
    }


def calculate_trend_signals(prices_df):
    """
    Advanced trend following strategy using multiple timeframes and indicators
    """
    # Calculate EMAs for multiple timeframes
    ema_8 = calculate_ema(prices_df, 8)
    ema_21 = calculate_ema(prices_df, 21)
    ema_55 = calculate_ema(prices_df, 55)

    # Calculate ADX for trend strength
    adx = calculate_adx(prices_df, 14)

    # Determine trend direction and strength
    short_trend = ema_8 > ema_21
    medium_trend = ema_21 > ema_55

    # Combine signals with confidence weighting
    trend_strength = adx["adx"].iloc[-1] / 100.0

    if short_trend.iloc[-1] and medium_trend.iloc[-1]:
        signal = "bullish"
        confidence = trend_strength
    elif not short_trend.iloc[-1] and not medium_trend.iloc[-1]:
        signal = "bearish"
        confidence = trend_strength
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "adx": safe_float(adx["adx"].iloc[-1]),
            "trend_strength": safe_float(trend_strength),
        },
    }


def calculate_mean_reversion_signals(prices_df):
    """
    Mean reversion strategy using statistical measures and Bollinger Bands
    """
    # Calculate z-score of price relative to moving average
    ma_50 = prices_df["close"].rolling(window=50).mean()
    std_50 = prices_df["close"].rolling(window=50).std()
    z_score = (prices_df["close"] - ma_50) / std_50

    # Calculate Bollinger Bands
    bb_upper, bb_lower = calculate_bollinger_bands(prices_df)

    # Calculate RSI with multiple timeframes
    rsi_14 = calculate_rsi(prices_df, 14)
    rsi_28 = calculate_rsi(prices_df, 28)

    # Mean reversion signals
    price_vs_bb = (prices_df["close"].iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])

    # Combine signals
    if z_score.iloc[-1] < -2 and price_vs_bb < 0.2:
        signal = "bullish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    elif z_score.iloc[-1] > 2 and price_vs_bb > 0.8:
        signal = "bearish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "z_score": safe_float(z_score.iloc[-1]),
            "price_vs_bb": safe_float(price_vs_bb),
            "rsi_14": safe_float(rsi_14.iloc[-1]),
            "rsi_28": safe_float(rsi_28.iloc[-1]),
        },
    }


def calculate_momentum_signals(prices_df):
    """
    Multi-factor momentum strategy
    """
    # Price momentum
    returns = prices_df["close"].pct_change()
    mom_1m = returns.rolling(21).sum()
    mom_3m = returns.rolling(63).sum()
    mom_6m = returns.rolling(126).sum()

    # Volume momentum
    volume_ma = prices_df["volume"].rolling(21).mean()
    volume_momentum = prices_df["volume"] / volume_ma

    # Relative strength
    # (would compare to market/sector in real implementation)

    # Calculate momentum score
    momentum_score = (0.4 * mom_1m + 0.3 * mom_3m + 0.3 * mom_6m).iloc[-1]

    # Volume confirmation
    volume_confirmation = volume_momentum.iloc[-1] > 1.0

    if momentum_score > 0.05 and volume_confirmation:
        signal = "bullish"
        confidence = min(abs(momentum_score) * 5, 1.0)
    elif momentum_score < -0.05 and volume_confirmation:
        signal = "bearish"
        confidence = min(abs(momentum_score) * 5, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "momentum_1m": safe_float(mom_1m.iloc[-1]),
            "momentum_3m": safe_float(mom_3m.iloc[-1]),
            "momentum_6m": safe_float(mom_6m.iloc[-1]),
            "volume_momentum": safe_float(volume_momentum.iloc[-1]),
        },
    }


def calculate_volatility_signals(prices_df):
    """
    Volatility-based trading strategy
    """
    # Calculate various volatility metrics
    returns = prices_df["close"].pct_change()

    # Historical volatility
    hist_vol = returns.rolling(21).std() * math.sqrt(252)

    # Volatility regime detection
    vol_ma = hist_vol.rolling(63).mean()
    vol_regime = hist_vol / vol_ma

    # Volatility mean reversion
    vol_z_score = (hist_vol - vol_ma) / hist_vol.rolling(63).std()

    # ATR ratio
    atr = calculate_atr(prices_df)
    atr_ratio = atr / prices_df["close"]

    # Generate signal based on volatility regime
    current_vol_regime = vol_regime.iloc[-1]
    vol_z = vol_z_score.iloc[-1]

    if current_vol_regime < 0.8 and vol_z < -1:
        signal = "bullish"  # Low vol regime, potential for expansion
        confidence = min(abs(vol_z) / 3, 1.0)
    elif current_vol_regime > 1.2 and vol_z > 1:
        signal = "bearish"  # High vol regime, potential for contraction
        confidence = min(abs(vol_z) / 3, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "historical_volatility": safe_float(hist_vol.iloc[-1]),
            "volatility_regime": safe_float(current_vol_regime),
            "volatility_z_score": safe_float(vol_z),
            "atr_ratio": safe_float(atr_ratio.iloc[-1]),
        },
    }


def calculate_stat_arb_signals(prices_df):
    """
    Statistical arbitrage signals based on price action analysis
    """
    # Calculate price distribution statistics
    returns = prices_df["close"].pct_change()

    # Skewness and kurtosis
    skew = returns.rolling(63).skew()
    kurt = returns.rolling(63).kurt()

    # Test for mean reversion using Hurst exponent
    hurst = calculate_hurst_exponent(prices_df["close"])

    # Correlation analysis
    # (would include correlation with related securities in real implementation)

    # Generate signal based on statistical properties
    if hurst < 0.4 and skew.iloc[-1] > 1:
        signal = "bullish"
        confidence = (0.5 - hurst) * 2
    elif hurst < 0.4 and skew.iloc[-1] < -1:
        signal = "bearish"
        confidence = (0.5 - hurst) * 2
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "hurst_exponent": safe_float(hurst),
            "skewness": safe_float(skew.iloc[-1]),
            "kurtosis": safe_float(kurt.iloc[-1]),
        },
    }


def weighted_signal_combination(signals, weights):
    """
    Combines multiple trading signals using a weighted approach
    """
    # Convert signals to numeric values
    signal_values = {"bullish": 1, "neutral": 0, "bearish": -1}

    weighted_sum = 0
    total_confidence = 0

    for strategy, signal in signals.items():
        numeric_signal = signal_values[signal["signal"]]
        weight = weights[strategy]
        confidence = signal["confidence"]

        weighted_sum += numeric_signal * weight * confidence
        total_confidence += weight * confidence

    # Normalize the weighted sum
    if total_confidence > 0:
        final_score = weighted_sum / total_confidence
    else:
        final_score = 0

    # Convert back to signal
    if final_score > 0.2:
        signal = "bullish"
    elif final_score < -0.2:
        signal = "bearish"
    else:
        signal = "neutral"

    return {"signal": signal, "confidence": abs(final_score)}


def normalize_pandas(obj):
    """Convert pandas Series/DataFrames to primitive Python types"""
    if isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict("records")
    elif isinstance(obj, dict):
        return {k: normalize_pandas(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [normalize_pandas(item) for item in obj]
    return obj


def calculate_rsi(prices_df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = prices_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(prices_df: pd.DataFrame, window: int = 20) -> tuple[pd.Series, pd.Series]:
    sma = prices_df["close"].rolling(window).mean()
    std_dev = prices_df["close"].rolling(window).std()
    upper_band = sma + (std_dev * 2)
    lower_band = sma - (std_dev * 2)
    return upper_band, lower_band


def calculate_ema(df: pd.DataFrame, window: int) -> pd.Series:
    """
    Calculate Exponential Moving Average

    Args:
        df: DataFrame with price data
        window: EMA period

    Returns:
        pd.Series: EMA values
    """
    return df["close"].ewm(span=window, adjust=False).mean()


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX)

    Args:
        df: DataFrame with OHLC data
        period: Period for calculations

    Returns:
        DataFrame with ADX values
    """
    # Calculate True Range
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = abs(df["high"] - df["close"].shift())
    df["low_close"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)

    # Calculate Directional Movement
    df["up_move"] = df["high"] - df["high"].shift()
    df["down_move"] = df["low"].shift() - df["low"]

    df["plus_dm"] = np.where((df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0)
    df["minus_dm"] = np.where((df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0)

    # Calculate ADX
    df["+di"] = 100 * (df["plus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["-di"] = 100 * (df["minus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["dx"] = 100 * abs(df["+di"] - df["-di"]) / (df["+di"] + df["-di"])
    df["adx"] = df["dx"].ewm(span=period).mean()

    return df[["adx", "+di", "-di"]]


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range

    Args:
        df: DataFrame with OHLC data
        period: Period for ATR calculation

    Returns:
        pd.Series: ATR values
    """
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)

    return true_range.rolling(period).mean()


def calculate_hurst_exponent(price_series: pd.Series, max_lag: int = 20) -> float:
    """
    Calculate Hurst Exponent to determine long-term memory of time series
    H < 0.5: Mean reverting series
    H = 0.5: Random walk
    H > 0.5: Trending series

    Args:
        price_series: Array-like price data
        max_lag: Maximum lag for R/S calculation

    Returns:
        float: Hurst exponent
    """
    lags = range(2, max_lag)
    # Add small epsilon to avoid log(0)
    tau = [max(1e-8, np.sqrt(np.std(np.subtract(price_series[lag:], price_series[:-lag])))) for lag in lags]

    # Return the Hurst exponent from linear fit
    try:
        reg = np.polyfit(np.log(lags), np.log(tau), 1)
        return reg[0]  # Hurst exponent is the slope
    except (ValueError, RuntimeWarning):
        # Return 0.5 (random walk) if calculation fails
        return 0.5


def generate_technical_reasoning(
    ticker: str,
    combined_signal: dict,
    reasoning_data: dict,
    state: AgentState,
) -> str:
    """
    Generate human-readable reasoning text from technical analysis data.
    
    Args:
        ticker: Stock ticker symbol
        combined_signal: Combined signal with signal and confidence
        reasoning_data: Dictionary containing all technical analysis signals
        state: Agent state for language settings
    
    Returns:
        str: Human-readable reasoning text
    """
    language = state.get("metadata", {}).get("language") or "en"
    is_chinese = language and ("Chinese" in language or "中文" in language or language.lower() in ["zh", "zh-cn", "zh-tw"])
    
    signal = combined_signal["signal"]
    confidence = round(combined_signal["confidence"] * 100)
    
    # Extract individual signals
    trend = reasoning_data.get("trend_following", {})
    mean_rev = reasoning_data.get("mean_reversion", {})
    momentum = reasoning_data.get("momentum", {})
    volatility = reasoning_data.get("volatility", {})
    stat_arb = reasoning_data.get("statistical_arbitrage", {})
    
    if is_chinese:
        # 中文描述
        lines = [
            f"【{ticker} 技术分析摘要】",
            f"综合信号: {signal.upper()} (置信度: {confidence}%)",
            "",
            "各策略分析结果:",
        ]
        
        # 趋势跟踪
        if trend:
            trend_sig = trend.get("signal", "neutral")
            trend_conf = trend.get("confidence", 0)
            trend_metrics = trend.get("metrics", {})
            adx = trend_metrics.get("adx", 0)
            lines.append(f"• 趋势跟踪: {trend_sig.upper()} (置信度: {trend_conf}%)")
            if adx:
                lines.append(f"  - ADX指标: {adx:.2f} ({'强趋势' if adx > 25 else '弱趋势' if adx < 20 else '中等趋势'})")
        
        # 均值回归
        if mean_rev:
            mean_sig = mean_rev.get("signal", "neutral")
            mean_conf = mean_rev.get("confidence", 0)
            mean_metrics = mean_rev.get("metrics", {})
            z_score = mean_metrics.get("z_score", 0)
            rsi_14 = mean_metrics.get("rsi_14", 0)
            lines.append(f"• 均值回归: {mean_sig.upper()} (置信度: {mean_conf}%)")
            if z_score:
                lines.append(f"  - Z分数: {z_score:.2f} ({'超卖' if z_score < -2 else '超买' if z_score > 2 else '正常区间'})")
            if rsi_14:
                lines.append(f"  - RSI(14): {rsi_14:.2f} ({'超卖' if rsi_14 < 30 else '超买' if rsi_14 > 70 else '中性'})")
        
        # 动量
        if momentum:
            mom_sig = momentum.get("signal", "neutral")
            mom_conf = momentum.get("confidence", 0)
            mom_metrics = momentum.get("metrics", {})
            mom_1m = mom_metrics.get("momentum_1m", 0)
            lines.append(f"• 动量分析: {mom_sig.upper()} (置信度: {mom_conf}%)")
            if mom_1m:
                lines.append(f"  - 1月动量: {mom_1m:.2%} ({'看涨' if mom_1m > 0.05 else '看跌' if mom_1m < -0.05 else '中性'})")
        
        # 波动率
        if volatility:
            vol_sig = volatility.get("signal", "neutral")
            vol_conf = volatility.get("confidence", 0)
            vol_metrics = volatility.get("metrics", {})
            hist_vol = vol_metrics.get("historical_volatility", 0)
            vol_regime = vol_metrics.get("volatility_regime", 1.0)
            lines.append(f"• 波动率分析: {vol_sig.upper()} (置信度: {vol_conf}%)")
            if hist_vol:
                lines.append(f"  - 历史波动率: {hist_vol:.2%} ({'高波动' if vol_regime > 1.2 else '低波动' if vol_regime < 0.8 else '正常波动'})")
        
        # 统计套利
        if stat_arb:
            arb_sig = stat_arb.get("signal", "neutral")
            arb_conf = stat_arb.get("confidence", 0)
            arb_metrics = stat_arb.get("metrics", {})
            hurst = arb_metrics.get("hurst_exponent", 0.5)
            lines.append(f"• 统计套利: {arb_sig.upper()} (置信度: {arb_conf}%)")
            if hurst:
                lines.append(f"  - Hurst指数: {hurst:.3f} ({'趋势性' if hurst > 0.5 else '均值回归' if hurst < 0.5 else '随机游走'})")
        
        lines.append("")
        lines.append(f"结论: 基于多策略综合分析，{ticker}当前技术面呈现{signal.upper()}信号，综合置信度为{confidence}%。")
        
        return "\n".join(lines)
    else:
        # English description
        lines = [
            f"【{ticker} Technical Analysis Summary】",
            f"Combined Signal: {signal.upper()} (Confidence: {confidence}%)",
            "",
            "Individual Strategy Results:",
        ]
        
        # Trend Following
        if trend:
            trend_sig = trend.get("signal", "neutral")
            trend_conf = trend.get("confidence", 0)
            trend_metrics = trend.get("metrics", {})
            adx = trend_metrics.get("adx", 0)
            lines.append(f"• Trend Following: {trend_sig.upper()} (Confidence: {trend_conf}%)")
            if adx:
                lines.append(f"  - ADX: {adx:.2f} ({'Strong trend' if adx > 25 else 'Weak trend' if adx < 20 else 'Moderate trend'})")
        
        # Mean Reversion
        if mean_rev:
            mean_sig = mean_rev.get("signal", "neutral")
            mean_conf = mean_rev.get("confidence", 0)
            mean_metrics = mean_rev.get("metrics", {})
            z_score = mean_metrics.get("z_score", 0)
            rsi_14 = mean_metrics.get("rsi_14", 0)
            lines.append(f"• Mean Reversion: {mean_sig.upper()} (Confidence: {mean_conf}%)")
            if z_score:
                lines.append(f"  - Z-Score: {z_score:.2f} ({'Oversold' if z_score < -2 else 'Overbought' if z_score > 2 else 'Normal range'})")
            if rsi_14:
                lines.append(f"  - RSI(14): {rsi_14:.2f} ({'Oversold' if rsi_14 < 30 else 'Overbought' if rsi_14 > 70 else 'Neutral'})")
        
        # Momentum
        if momentum:
            mom_sig = momentum.get("signal", "neutral")
            mom_conf = momentum.get("confidence", 0)
            mom_metrics = momentum.get("metrics", {})
            mom_1m = mom_metrics.get("momentum_1m", 0)
            lines.append(f"• Momentum: {mom_sig.upper()} (Confidence: {mom_conf}%)")
            if mom_1m:
                lines.append(f"  - 1M Momentum: {mom_1m:.2%} ({'Bullish' if mom_1m > 0.05 else 'Bearish' if mom_1m < -0.05 else 'Neutral'})")
        
        # Volatility
        if volatility:
            vol_sig = volatility.get("signal", "neutral")
            vol_conf = volatility.get("confidence", 0)
            vol_metrics = volatility.get("metrics", {})
            hist_vol = vol_metrics.get("historical_volatility", 0)
            vol_regime = vol_metrics.get("volatility_regime", 1.0)
            lines.append(f"• Volatility: {vol_sig.upper()} (Confidence: {vol_conf}%)")
            if hist_vol:
                lines.append(f"  - Historical Volatility: {hist_vol:.2%} ({'High volatility' if vol_regime > 1.2 else 'Low volatility' if vol_regime < 0.8 else 'Normal volatility'})")
        
        # Statistical Arbitrage
        if stat_arb:
            arb_sig = stat_arb.get("signal", "neutral")
            arb_conf = stat_arb.get("confidence", 0)
            arb_metrics = stat_arb.get("metrics", {})
            hurst = arb_metrics.get("hurst_exponent", 0.5)
            lines.append(f"• Statistical Arbitrage: {arb_sig.upper()} (Confidence: {arb_conf}%)")
            if hurst:
                lines.append(f"  - Hurst Exponent: {hurst:.3f} ({'Trending' if hurst > 0.5 else 'Mean-reverting' if hurst < 0.5 else 'Random walk'})")
        
        lines.append("")
        lines.append(f"Conclusion: Based on multi-strategy analysis, {ticker} shows a {signal.upper()} technical signal with {confidence}% confidence.")
        
        return "\n".join(lines)
