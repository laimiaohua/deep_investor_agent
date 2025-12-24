from datetime import datetime, timezone
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.style import Style
from rich.text import Text
from typing import Dict, Optional, Callable, List

console = Console()


class AgentProgress:
    """Manages progress tracking for multiple agents."""

    def __init__(self):
        self.agent_status: Dict[str, Dict[str, str]] = {}
        self.language: str = "en"
        self.table = Table(show_header=False, box=None, padding=(0, 1))
        self.live = Live(self.table, console=console, refresh_per_second=4)
        self.started = False
        self.update_handlers: List[Callable[[str, Optional[str], str], None]] = []

    def register_handler(self, handler: Callable[[str, Optional[str], str], None]):
        """Register a handler to be called when agent status updates."""
        self.update_handlers.append(handler)
        return handler  # Return handler to support use as decorator

    def unregister_handler(self, handler: Callable[[str, Optional[str], str], None]):
        """Unregister a previously registered handler."""
        if handler in self.update_handlers:
            self.update_handlers.remove(handler)

    def set_language(self, language: Optional[str]):
        """Set target language for status display (e.g., 'zh-CN', 'zh', 'en')."""
        if language:
            self.language = language

    def _translate_status(self, status: str, ticker: Optional[str]) -> str:
        """Complete status translation for UI display."""
        if not status or not self.language:
            return status

        lang = self.language.lower()
        if not lang.startswith("zh"):
            return status

        # Complete translation mapping for all status messages
        status_translations = {
            # Common statuses
            "Done": "完成",
            "Error": "错误",
            "Failed": "失败",
            "Warning": "警告",
            
            # Data fetching statuses
            "Fetching financial metrics": "正在获取财务指标",
            "Fetching financial data": "正在获取财务数据",
            "Gathering financial line items": "正在收集财务项目",
            "Gathering comprehensive line items": "正在收集综合财务项目",
            "Getting market cap": "正在获取市值",
            "Fetching market cap": "正在获取市值",
            "Fetching insider trades": "正在获取内部交易数据",
            "Fetching company news": "正在获取公司新闻",
            "Fetching price data": "正在获取价格数据",
            "Fetching recent price data for momentum": "正在获取近期价格数据（动量分析）",
            "Fetching CN/HK balance sheet (DeepAlpha)": "正在获取A股/港股资产负债表",
            
            # Analysis statuses
            "Analyzing fundamentals": "正在分析基本面",
            "Analyzing consistency": "正在分析一致性",
            "Analyzing competitive moat": "正在分析竞争护城河",
            "Analyzing moat strength": "正在分析护城河强度",
            "Analyzing pricing power": "正在分析定价能力",
            "Analyzing book value growth": "正在分析账面价值增长",
            "Analyzing management quality": "正在分析管理层质量",
            "Analyzing business predictability": "正在分析业务可预测性",
            "Analyzing growth & momentum": "正在分析增长和动量",
            "Analyzing growth": "正在分析增长",
            "Analyzing profitability": "正在分析盈利能力",
            "Analyzing balance sheet": "正在分析资产负债表",
            "Analyzing balance sheet and capital structure": "正在分析资产负债表和资本结构",
            "Analyzing sentiment": "正在分析市场情绪",
            "Analyzing contrarian sentiment": "正在分析逆向情绪",
            "Analyzing insider activity": "正在分析内部交易活动",
            "Analyzing trading patterns": "正在分析交易模式",
            "Analyzing price data": "正在分析价格数据",
            "Analyzing volatility": "正在分析波动率",
            "Analyzing risk-reward": "正在分析风险收益比",
            "Analyzing downside protection": "正在分析下行保护",
            "Analyzing cash yield and valuation": "正在分析现金收益率和估值",
            "Analyzing growth and reinvestment": "正在分析增长和再投资",
            "Analyzing risk profile": "正在分析风险特征",
            "Analyzing activism potential": "正在分析维权潜力",
            "Analyzing capital structure": "正在分析资本结构",
            "Analyzing value": "正在分析价值",
            
            # Calculation statuses
            "Calculating intrinsic value": "正在计算内在价值",
            "Calculating Munger-style valuation": "正在计算芒格风格估值",
            "Calculating WACC and enhanced DCF": "正在计算WACC和增强DCF",
            "Calculating trend signals": "正在计算趋势信号",
            "Calculating mean reversion": "正在计算均值回归",
            "Calculating momentum": "正在计算动量",
            "Calculating volatility- and correlation-adjusted limits": "正在计算波动率和相关性调整限制",
            "Calculating technical indicators": "正在计算技术指标",
            "Performing Druckenmiller-style valuation": "正在执行德鲁肯米勒风格估值",
            
            # Assessment statuses
            "Assessing relative valuation": "正在评估相对估值",
            "Assessing potential to double": "正在评估翻倍潜力",
            
            # Processing statuses
            "Processing analyst signals": "正在处理分析师信号",
            "Combining signals": "正在合并信号",
            "Statistical analysis": "正在统计分析",
            "Fetching price data and calculating volatility": "正在获取价格数据并计算波动率",
            
            # Generation statuses
            "Generating Warren Buffett analysis": "正在生成巴菲特风格分析",
            "Generating Charlie Munger analysis": "正在生成芒格风格分析",
            "Generating Duan Yongping analysis": "正在生成段永平风格分析",
            "Generating Zhang Lei analysis": "正在生成张磊风格分析",
            "Generating Qiu Guolu analysis": "正在生成邱国鹭风格分析",
            "Generating Feng Liu analysis": "正在生成冯柳风格分析",
            "Generating Dan Bin analysis": "正在生成但斌风格分析",
            "Generating Bill Ackman analysis": "正在生成比尔·阿克曼风格分析",
            "Generating Pabrai analysis": "正在生成帕伯莱风格分析",
            "Generating analysis": "正在生成分析",
            "Generating LLM output": "正在生成分析结论",
            "Generating trading decisions": "正在生成交易决策",
            
            # Error messages
            "Failed: No financial metrics found": "失败：未找到财务指标",
            "Failed: Not enough financial metrics": "失败：财务指标数据不足",
            "Failed: No financial metrics": "失败：未找到财务指标",
            "Failed: Insufficient financial line items": "失败：财务项目数据不足",
            "Failed: Market cap unavailable": "失败：市值数据不可用",
            "Failed: All valuation methods zero": "失败：所有估值方法结果为零",
            "Warning: No price data found": "警告：未找到价格数据",
            "Warning: Insufficient price data": "警告：价格数据不足",
            
            # Portfolio statuses
            "Total portfolio value": "投资组合总价值",
        }
        
        # Try exact match first
        if status in status_translations:
            translated = status_translations[status]
        else:
            # Fallback: try partial matching for dynamic messages
            translated = status
            # Replace common patterns
            for key, value in status_translations.items():
                if key in translated:
                    translated = translated.replace(key, value)
                    break
            
            # If still not translated, try word-by-word replacement
            if translated == status:
                word_replacements = {
                    "Fetching": "正在获取",
                    "Gathering": "正在收集",
                    "Getting": "正在获取",
                    "Analyzing": "正在分析",
                    "Calculating": "正在计算",
                    "Assessing": "正在评估",
                    "Processing": "正在处理",
                    "Generating": "正在生成",
                    "Performing": "正在执行",
                    "Combining": "正在合并",
                    "Done": "完成",
                    "Failed": "失败",
                    "Warning": "警告",
                    "Error": "错误",
                }
                for eng, chn in word_replacements.items():
                    if translated.startswith(eng):
                        translated = translated.replace(eng, chn, 1)
                        break

        return translated

    def start(self):
        """Start the progress display."""
        if not self.started:
            self.live.start()
            self.started = True

    def stop(self):
        """Stop the progress display."""
        if self.started:
            self.live.stop()
            self.started = False

    def update_status(self, agent_name: str, ticker: Optional[str] = None, status: str = "", analysis: Optional[str] = None):
        """Update the status of an agent."""
        if agent_name not in self.agent_status:
            self.agent_status[agent_name] = {"status": "", "ticker": None}

        status = self._translate_status(status, ticker)

        if ticker:
            self.agent_status[agent_name]["ticker"] = ticker
        if status:
            self.agent_status[agent_name]["status"] = status
        if analysis:
            self.agent_status[agent_name]["analysis"] = analysis
        
        # Set the timestamp as UTC datetime
        timestamp = datetime.now(timezone.utc).isoformat()
        self.agent_status[agent_name]["timestamp"] = timestamp

        # Notify all registered handlers
        for handler in self.update_handlers:
            handler(agent_name, ticker, status, analysis, timestamp)

        self._refresh_display()
    
    def update_streaming_content(self, agent_name: str, ticker: Optional[str], content: str):
        """
        Update with streaming LLM content.
        
        Args:
            agent_name: Name of the agent
            ticker: Stock ticker
            content: Streamed content chunk
        """
        if agent_name not in self.agent_status:
            self.agent_status[agent_name] = {"status": "", "ticker": None}
        
        # Append to existing streaming content
        if "streaming_content" not in self.agent_status[agent_name]:
            self.agent_status[agent_name]["streaming_content"] = ""
        
        self.agent_status[agent_name]["streaming_content"] += content
        
        # Update timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        self.agent_status[agent_name]["timestamp"] = timestamp
        
        print(f"[Progress] Streaming update for {agent_name}, ticker: {ticker}, content length: {len(content)}, total: {len(self.agent_status[agent_name]['streaming_content'])}")
        
        # Notify handlers with special streaming flag
        for handler in self.update_handlers:
            # Pass streaming content via the analysis parameter
            print(f"[Progress] Calling handler with streaming content")
            handler(agent_name, ticker, "streaming", content, timestamp)

    def get_all_status(self):
        """Get the current status of all agents as a dictionary."""
        return {agent_name: {"ticker": info["ticker"], "status": info["status"], "display_name": self._get_display_name(agent_name)} for agent_name, info in self.agent_status.items()}

    def _get_display_name(self, agent_name: str) -> str:
        """Convert agent_name to a display-friendly format."""
        return agent_name.replace("_agent", "").replace("_", " ").title()

    def _refresh_display(self):
        """Refresh the progress display."""
        self.table.columns.clear()
        self.table.add_column(width=100)

        # Sort agents with Risk Management and Portfolio Management at the bottom
        def sort_key(item):
            agent_name = item[0]
            if "risk_management" in agent_name:
                return (2, agent_name)
            elif "portfolio_management" in agent_name:
                return (3, agent_name)
            else:
                return (1, agent_name)

        for agent_name, info in sorted(self.agent_status.items(), key=sort_key):
            status = info["status"]
            ticker = info["ticker"]
            # Create the status text with appropriate styling
            if status.lower() == "done":
                style = Style(color="green", bold=True)
                symbol = "✓"
            elif status.lower() == "error":
                style = Style(color="red", bold=True)
                symbol = "✗"
            else:
                style = Style(color="yellow")
                symbol = "⋯"

            agent_display = self._get_display_name(agent_name)
            status_text = Text()
            status_text.append(f"{symbol} ", style=style)
            status_text.append(f"{agent_display:<20}", style=Style(bold=True))

            if ticker:
                status_text.append(f"[{ticker}] ", style=Style(color="cyan"))
            status_text.append(status, style=style)

            self.table.add_row(status_text)


# Create a global instance
progress = AgentProgress()
