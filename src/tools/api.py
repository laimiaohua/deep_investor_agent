import datetime
import os
import pandas as pd
import requests
import time
from typing import Optional
from requests.exceptions import RequestException, Timeout, ConnectionError as RequestsConnectionError
from datetime import datetime as dt

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)
from src.tools.deepalpha import (
    get_deepalpha_client,
    get_balance_sheet_raw,
    get_income_statement_raw,
    get_cash_flow_raw,
    get_daily_price_raw,
    get_financial_indicators_raw,
    get_latest_valuation,
    _is_hk_stock,
)

# Global cache instance
_cache = get_cache()

# Polygon.io API base URL
POLYGON_API_BASE_URL = "https://api.polygon.io"


def _get_us_stock_api_key(api_key: str = None, massive_api_key: str = None) -> tuple[str | None, str | None]:
    """
    获取美股数据 API key，返回主要 API key 和备用 API key。
    
    Args:
        api_key: 直接传入的 API key（优先）
        massive_api_key: Massive 数据源的 API key
    
    Returns:
        (primary_api_key, backup_api_key) 元组
        - primary_api_key: 主要 API key（优先使用）
        - backup_api_key: 备用 API key（当主要 API key 失败时使用）
    """
    # 确定主要 API key
    primary = None
    if api_key:
        primary = api_key
    else:
        primary = os.environ.get("FINANCIAL_DATASETS_API_KEY")
    
    # 确定备用 API key
    backup = None
    if massive_api_key:
        backup = massive_api_key
    else:
        backup = os.environ.get("MASSIVE_API_KEY")
    
    # 如果主要和备用是同一个，则不设置备用
    if primary == backup:
        backup = None
    
    return (primary, backup)


def _get_primary_api_key(api_key: str = None, massive_api_key: str = None) -> str | None:
    """
    获取主要 API key（简化版本，用于不需要自动切换的场景）。
    
    Args:
        api_key: 直接传入的 API key（优先）
        massive_api_key: Massive 数据源的 API key
    
    Returns:
        主要 API key 字符串，如果都没有则返回 None
    """
    primary, _ = _get_us_stock_api_key(api_key=api_key, massive_api_key=massive_api_key)
    return primary


def _make_api_request_with_fallback(
    url: str,
    api_key: str = None,
    massive_api_key: str = None,
    method: str = "GET",
    json_data: dict = None,
    timeout: int = 30,
    operation: str = "API 请求",
    ticker: str = None,
) -> requests.Response:
    """
    发送 API 请求，支持自动切换到备用 API key（当主要 API key 返回 402 错误时）。
    
    Args:
        url: 请求 URL
        api_key: 主要 API key
        massive_api_key: 备用 API key
        method: HTTP 方法
        json_data: POST 请求的 JSON 数据
        timeout: 超时时间
        operation: 操作描述（用于错误信息）
        ticker: 股票代码（用于错误信息）
    
    Returns:
        requests.Response: 响应对象
    
    Raises:
        APIError: 如果所有 API key 都失败
    """
    primary_key, backup_key = _get_us_stock_api_key(api_key=api_key, massive_api_key=massive_api_key)
    
    last_error = None
    response = None
    
    for attempt_key in [primary_key, backup_key]:
        if attempt_key is None:
            continue
        
        headers = {}
        headers["X-API-KEY"] = attempt_key
        
        try:
            response = _make_api_request(url, headers, method=method, json_data=json_data, timeout=timeout)
            
            # 如果返回 402（余额不足）且有备用 key，尝试备用 key
            if response.status_code == 402 and backup_key and attempt_key == primary_key:
                print(f"Warning: Primary API key returned 402 (insufficient credits) for {ticker or 'request'}, trying backup API key...")
                last_error = APIError(f"主要 API key 余额不足", status_code=402, ticker=ticker, recoverable=True)
                continue  # 尝试备用 key
            
            # 检查响应状态 - 成功则返回
            if response.status_code == 200:
                return response
            
            # 如果不是 200，处理错误（会抛出异常）
            _handle_api_response(response, ticker or "", operation)
            # 如果到这里说明处理成功（虽然不太可能）
            return response
            
        except APIError as e:
            # 如果是 402 错误且有备用 key，尝试备用 key
            if e.status_code == 402 and backup_key and attempt_key == primary_key:
                print(f"Warning: Primary API key returned 402 (insufficient credits) for {ticker or 'request'}, trying backup API key...")
                last_error = e
                continue  # 尝试备用 key
            # 其他错误直接抛出
            raise
        except Exception as e:
            # 如果是最后一次尝试，抛出异常
            if attempt_key == backup_key or backup_key is None:
                raise APIError(f"{operation}失败: {str(e)}", ticker=ticker, recoverable=True)
            last_error = e
            continue
    
    # 所有尝试都失败了
    if last_error:
        raise last_error
    if response:
        _handle_api_response(response, ticker or "", operation)
        return response
    raise APIError(f"{operation}失败: 所有 API key 都不可用", ticker=ticker, recoverable=False)


def _make_api_request(
    url: str, 
    headers: dict, 
    method: str = "GET", 
    json_data: dict = None, 
    max_retries: int = 3,
    timeout: int = 30,
    retry_on_timeout: bool = True,
    retry_on_connection_error: bool = True
) -> requests.Response:
    """
    Make an API request with comprehensive error handling and retry logic.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
        timeout: Request timeout in seconds (default: 30)
        retry_on_timeout: Whether to retry on timeout errors (default: True)
        retry_on_connection_error: Whether to retry on connection errors (default: True)
    
    Returns:
        requests.Response: The response object
    
    Raises:
        Exception: If the request fails after all retries
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
            else:
                response = requests.get(url, headers=headers, timeout=timeout)
            
            # Handle rate limiting (429)
            if response.status_code == 429 and attempt < max_retries:
                # Exponential backoff: 2s, 4s, 8s...
                delay = min(2 ** attempt, 60)  # Cap at 60 seconds
                print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
                time.sleep(delay)
                continue
            
            # Handle server errors (5xx) - retry with exponential backoff
            if 500 <= response.status_code < 600 and attempt < max_retries:
                delay = min(2 ** attempt, 30)  # Cap at 30 seconds
                print(f"Server error ({response.status_code}). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
                time.sleep(delay)
                continue
            
            # Return the response (success or non-retryable errors)
            return response
            
        except Timeout as e:
            last_exception = e
            if retry_on_timeout and attempt < max_retries:
                delay = min(2 ** attempt, 30)
                print(f"Request timeout. Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
                time.sleep(delay)
                continue
            else:
                raise Exception(f"Request timeout after {max_retries + 1} attempts: {str(e)}")
                
        except RequestsConnectionError as e:
            last_exception = e
            if retry_on_connection_error and attempt < max_retries:
                delay = min(2 ** attempt, 30)
                print(f"Connection error. Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
                time.sleep(delay)
                continue
            else:
                raise Exception(f"Connection error after {max_retries + 1} attempts: {str(e)}")
                
        except RequestException as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(2 ** attempt, 30)
                print(f"Request error: {str(e)}. Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
                time.sleep(delay)
                continue
            else:
                raise Exception(f"Request failed after {max_retries + 1} attempts: {str(e)}")
    
    # If we get here, all retries failed
    if last_exception:
        raise Exception(f"Request failed after {max_retries + 1} attempts: {str(last_exception)}")
    else:
        raise Exception(f"Request failed after {max_retries + 1} attempts")


class APIError(Exception):
    """Custom exception for API errors with detailed information."""
    def __init__(self, message: str, status_code: Optional[int] = None, ticker: Optional[str] = None, recoverable: bool = False):
        self.message = message
        self.status_code = status_code
        self.ticker = ticker
        self.recoverable = recoverable  # Whether this error can be recovered from
        super().__init__(self.message)
    
    def __str__(self):
        base_msg = self.message
        if self.ticker:
            base_msg = f"[{self.ticker}] {base_msg}"
        if self.status_code:
            base_msg = f"HTTP {self.status_code}: {base_msg}"
        return base_msg


def _handle_api_response(response: requests.Response, ticker: str, operation: str) -> None:
    """
    Handle API response and raise appropriate errors.
    
    Args:
        response: The response object
        ticker: The ticker symbol
        operation: Description of the operation (e.g., "fetching financial metrics")
    
    Raises:
        APIError: With appropriate error details
    """
    if response.status_code == 200:
        return
    
    # Parse error message from response
    error_msg = "Unknown error"
    try:
        error_data = response.json()
        if isinstance(error_data, dict):
            error_msg = error_data.get("error", error_data.get("message", str(error_data)))
    except:
        error_msg = response.text[:200]  # Limit error message length
    
    # Determine if error is recoverable
    recoverable = False
    if response.status_code == 429:  # Rate limit - recoverable
        recoverable = True
    elif 500 <= response.status_code < 600:  # Server errors - recoverable
        recoverable = True
    elif response.status_code == 402:  # Insufficient credits - not recoverable
        recoverable = False
    elif response.status_code == 401:  # Unauthorized - not recoverable
        recoverable = False
    
    # Build user-friendly error message
    if response.status_code == 402:
        user_msg = f"无法{operation} {ticker}: API 余额不足。请充值后重试。"
    elif response.status_code == 401:
        user_msg = f"无法{operation} {ticker}: API 密钥无效。请检查 API 密钥配置。"
    elif response.status_code == 429:
        user_msg = f"无法{operation} {ticker}: API 请求频率过高，请稍后重试。"
    elif 500 <= response.status_code < 600:
        user_msg = f"无法{operation} {ticker}: API 服务器错误 ({response.status_code})，请稍后重试。"
    else:
        user_msg = f"无法{operation} {ticker}: API 错误 ({response.status_code}): {error_msg}"
    
    raise APIError(user_msg, status_code=response.status_code, ticker=ticker, recoverable=recoverable)


def _make_polygon_api_request(
    endpoint: str,
    api_key: str,
    params: dict = None,
    timeout: int = 30,
    max_retries: int = 3
) -> requests.Response:
    """
    使用Polygon.io API发送请求。
    
    Args:
        endpoint: API端点路径（例如：/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-12-31）
        api_key: Polygon.io API密钥
        params: 额外的查询参数
        timeout: 请求超时时间
        max_retries: 最大重试次数
    
    Returns:
        requests.Response: 响应对象
    
    Raises:
        APIError: 如果请求失败
    """
    url = f"{POLYGON_API_BASE_URL}{endpoint}"
    
    # Polygon.io使用query参数认证
    query_params = params or {}
    query_params["apikey"] = api_key
    
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=query_params, timeout=timeout)
            
            # 处理速率限制（429）
            if response.status_code == 429 and attempt < max_retries:
                delay = min(2 ** attempt, 60)
                print(f"Polygon.io rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s...")
                time.sleep(delay)
                continue
            
            # 处理服务器错误（5xx）
            if 500 <= response.status_code < 600 and attempt < max_retries:
                delay = min(2 ** attempt, 30)
                print(f"Polygon.io server error ({response.status_code}). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s...")
                time.sleep(delay)
                continue
            
            return response
            
        except (Timeout, RequestsConnectionError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(2 ** attempt, 30)
                print(f"Polygon.io request error: {str(e)}. Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s...")
                time.sleep(delay)
                continue
            else:
                raise APIError(f"Polygon.io API请求失败: {str(e)}", recoverable=True)
        except RequestException as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(2 ** attempt, 30)
                print(f"Polygon.io request error: {str(e)}. Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s...")
                time.sleep(delay)
                continue
            else:
                raise APIError(f"Polygon.io API请求失败: {str(e)}", recoverable=True)
    
    if last_exception:
        raise APIError(f"Polygon.io API请求失败: {str(last_exception)}", recoverable=True)
    else:
        raise APIError(f"Polygon.io API请求失败")


def _convert_polygon_price_to_price(polygon_data: dict, ticker: str) -> Price:
    """
    将Polygon.io聚合数据转换为Price对象。
    
    Args:
        polygon_data: Polygon.io返回的聚合数据项
        ticker: 股票代码
    
    Returns:
        Price对象
    """
    # Polygon.io时间戳是毫秒，需要转换为日期字符串
    timestamp_ms = polygon_data.get("t", 0)
    date_str = dt.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")
    
    return Price(
        open=float(polygon_data.get("o", 0)),
        close=float(polygon_data.get("c", 0)),
        high=float(polygon_data.get("h", 0)),
        low=float(polygon_data.get("l", 0)),
        volume=int(polygon_data.get("v", 0)),
        time=date_str
    )


def get_polygon_prices(ticker: str, start_date: str, end_date: str, api_key: str) -> list[Price]:
    """
    从Polygon.io获取价格数据。
    
    Args:
        ticker: 股票代码
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        api_key: Polygon.io API密钥
    
    Returns:
        Price对象列表
    """
    # 转换日期格式（Polygon.io需要YYYY-MM-DD格式）
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")
    
    # Polygon.io聚合数据端点
    endpoint = f"/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
    
    try:
        response = _make_polygon_api_request(endpoint, api_key)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("status") != "OK":
                error_msg = data.get("error", "Unknown error")
                raise APIError(f"Polygon.io API返回错误: {error_msg}", recoverable=True)
            
            results = data.get("results", [])
            if not results:
                return []
            
            # 转换Polygon.io格式到Price对象
            prices = []
            for result in results:
                try:
                    price = _convert_polygon_price_to_price(result, ticker)
                    prices.append(price)
                except (ValueError, KeyError, TypeError) as e:
                    print(f"Warning: 跳过无效的价格数据: {str(e)}")
                    continue
            
            return prices
        elif response.status_code == 403:
            # 403可能是计划限制，尝试更短的时间范围
            error_data = response.json()
            error_msg = error_data.get("error", error_data.get("message", "Unknown error"))
            if "plan" in error_msg.lower() or "timeframe" in error_msg.lower() or "upgrade" in error_msg.lower():
                print(f"Warning: Polygon.io计划限制，尝试使用最近30天的数据...")
                # 尝试获取最近30天的数据
                try:
                    end_dt = dt.strptime(end_date, "%Y-%m-%d")
                    start_dt = end_dt - datetime.timedelta(days=30)
                    start_short = start_dt.strftime("%Y-%m-%d")
                    start_short_no_dash = start_short.replace("-", "")
                    end_no_dash = end_date.replace("-", "")
                    
                    endpoint_short = f"/v2/aggs/ticker/{ticker}/range/1/day/{start_short_no_dash}/{end_no_dash}"
                    response_short = _make_polygon_api_request(endpoint_short, api_key)
                    
                    if response_short.status_code == 200:
                        data_short = response_short.json()
                        if data_short.get("status") == "OK":
                            results = data_short.get("results", [])
                            if results:
                                prices = []
                                for result in results:
                                    try:
                                        price = _convert_polygon_price_to_price(result, ticker)
                                        prices.append(price)
                                    except (ValueError, KeyError, TypeError):
                                        continue
                                if prices:
                                    print(f"Info: 成功获取最近30天的数据 ({len(prices)} 条记录)")
                                    return prices
                except Exception as e:
                    print(f"Warning: 尝试获取最近30天数据也失败: {str(e)}")
            # 如果无法获取数据，返回空列表而不是抛出错误
            # 这样调用者可以继续使用其他数据源或使用可用数据进行分析
            print(f"Warning: Polygon.io API计划限制，无法获取数据: {error_msg}")
            print(f"Info: 建议升级Polygon.io账户计划或使用其他数据源")
            return []
        else:
            _handle_api_response(response, ticker, "获取价格数据")
            return []
            
    except APIError:
        raise
    except Exception as e:
        raise APIError(f"Polygon.io获取价格数据失败: {str(e)}", recoverable=True)


def get_yfinance_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[FinancialMetrics]:
    """
    使用yfinance获取财务指标。
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        period: 财报周期（yfinance主要支持annual和quarterly）
        limit: 返回记录数
    
    Returns:
        FinancialMetrics对象列表
    """
    try:
        import yfinance as yf
    except ImportError:
        print(f"Warning: yfinance未安装，无法使用yfinance获取财务指标")
        return []
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            return []
        
        # 获取财务报表数据
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow
        
        # 构建FinancialMetrics对象
        metrics = []
        
        # 从info中获取最新数据（这些数据是当前时点的，适用于所有期间）
        market_cap = info.get("marketCap")
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        pb_ratio = info.get("priceToBook")
        ps_ratio = info.get("priceToSalesTrailing12Months")
        gross_margin = info.get("grossMargins")
        operating_margin = info.get("operatingMargins")
        profit_margin = info.get("profitMargins")
        debt_to_equity = info.get("debtToEquity")
        current_ratio = info.get("currentRatio")
        quick_ratio = info.get("quickRatio")
        cash_ratio = info.get("cashRatio")
        revenue_growth = info.get("revenueGrowth")
        earnings_growth = info.get("earningsGrowth")
        earnings_quarterly_growth = info.get("earningsQuarterlyGrowth")
        
        # 为每个历史期间创建FinancialMetrics对象（用于护城河分析）
        if financials is not None and not financials.empty:
            # 遍历所有历史期间（从最新到最旧）
            periods_to_process = min(len(financials.columns), limit)
            
            for period_idx in range(periods_to_process):
                # 获取该期间的报告期
                report_period = financials.columns[-(period_idx + 1)]  # 从最新到最旧
                period_str = str(report_period) if isinstance(report_period, pd.Timestamp) else end_date
                
                # 从财务报表中提取该期间的数据
                try:
                    revenue = financials.loc["Total Revenue"].iloc[-(period_idx + 1)] if "Total Revenue" in financials.index else None
                    net_income = financials.loc["Net Income"].iloc[-(period_idx + 1)] if "Net Income" in financials.index else None
                except (IndexError, KeyError):
                    continue
                
                # 从balance_sheet中提取该期间的数据
                total_assets = None
                total_liabilities = None
                shareholders_equity = None
                if balance_sheet is not None and not balance_sheet.empty and len(balance_sheet.columns) > period_idx:
                    try:
                        if "Total Assets" in balance_sheet.index:
                            total_assets = balance_sheet.loc["Total Assets"].iloc[-(period_idx + 1)]
                        if "Total Liabilities" in balance_sheet.index:
                            total_liabilities = balance_sheet.loc["Total Liabilities"].iloc[-(period_idx + 1)]
                        elif "Total Liab" in balance_sheet.index:
                            total_liabilities = balance_sheet.loc["Total Liab"].iloc[-(period_idx + 1)]
                        if "Stockholders Equity" in balance_sheet.index:
                            shareholders_equity = balance_sheet.loc["Stockholders Equity"].iloc[-(period_idx + 1)]
                        elif "Total Stockholder Equity" in balance_sheet.index:
                            shareholders_equity = balance_sheet.loc["Total Stockholder Equity"].iloc[-(period_idx + 1)]
                    except (IndexError, KeyError):
                        pass
                
                # 从cashflow中提取该期间的数据
                free_cash_flow = None
                operating_cash_flow = None
                if cashflow is not None and not cashflow.empty and len(cashflow.columns) > period_idx:
                    try:
                        if "Free Cash Flow" in cashflow.index:
                            free_cash_flow = cashflow.loc["Free Cash Flow"].iloc[-(period_idx + 1)]
                        if "Operating Cash Flow" in cashflow.index:
                            operating_cash_flow = cashflow.loc["Operating Cash Flow"].iloc[-(period_idx + 1)]
                    except (IndexError, KeyError):
                        pass
                
                # 如果是第一个期间（最新），尝试从info获取补充数据
                if period_idx == 0:
                    if free_cash_flow is None:
                        free_cash_flow = info.get("freeCashflow")
                    if operating_cash_flow is None:
                        operating_cash_flow = info.get("operatingCashflow")
                
                # 计算该期间的财务指标
                # ROE和ROA（每个期间独立计算）
                roe = None
                if net_income and shareholders_equity and shareholders_equity > 0:
                    roe = net_income / shareholders_equity
                
                roa = None
                if net_income and total_assets and total_assets > 0:
                    roa = net_income / total_assets
                
                # 计算该期间的债务权益比（如果该期间有数据）
                period_debt_to_equity = None
                if total_liabilities and shareholders_equity and shareholders_equity > 0:
                    period_debt_to_equity = total_liabilities / shareholders_equity
                elif period_idx == 0:  # 最新期间使用info中的数据
                    period_debt_to_equity = debt_to_equity
                
                # 计算该期间的债务资产比
                period_debt_to_assets = None
                if total_liabilities and total_assets and total_assets > 0:
                    period_debt_to_assets = total_liabilities / total_assets
                
                # 计算该期间的增长率（相对于前一个期间）
                period_revenue_growth = None
                period_earnings_growth = None
                period_book_value_growth = None
                period_free_cash_flow_growth = None
                
                if period_idx < len(financials.columns) - 1:  # 不是最旧的期间
                    try:
                        # 收入增长率
                        if revenue and "Total Revenue" in financials.index:
                            prev_revenue = financials.loc["Total Revenue"].iloc[-(period_idx + 2)]
                            if prev_revenue and prev_revenue > 0:
                                period_revenue_growth = (revenue - prev_revenue) / prev_revenue
                        
                        # 盈利增长率
                        if net_income and "Net Income" in financials.index:
                            prev_earnings = financials.loc["Net Income"].iloc[-(period_idx + 2)]
                            if prev_earnings and prev_earnings > 0:
                                period_earnings_growth = (net_income - prev_earnings) / prev_earnings
                        
                        # 账面价值增长率
                        if shareholders_equity and balance_sheet is not None and not balance_sheet.empty:
                            equity_key = None
                            if "Stockholders Equity" in balance_sheet.index:
                                equity_key = "Stockholders Equity"
                            elif "Total Stockholder Equity" in balance_sheet.index:
                                equity_key = "Total Stockholder Equity"
                            
                            if equity_key and len(balance_sheet.columns) > period_idx + 1:
                                prev_equity = balance_sheet.loc[equity_key].iloc[-(period_idx + 2)]
                                if prev_equity and prev_equity > 0:
                                    period_book_value_growth = (shareholders_equity - prev_equity) / prev_equity
                        
                        # 自由现金流增长率
                        if free_cash_flow and cashflow is not None and not cashflow.empty and "Free Cash Flow" in cashflow.index and len(cashflow.columns) > period_idx + 1:
                            prev_fcf = cashflow.loc["Free Cash Flow"].iloc[-(period_idx + 2)]
                            if prev_fcf and prev_fcf > 0:
                                period_free_cash_flow_growth = (free_cash_flow - prev_fcf) / prev_fcf
                    except (IndexError, KeyError):
                        pass
                
                # 对于最新期间，使用info中的增长率
                if period_idx == 0:
                    if period_revenue_growth is None:
                        period_revenue_growth = revenue_growth
                    if period_earnings_growth is None:
                        period_earnings_growth = earnings_growth
                
                # 计算每股自由现金流和自由现金流收益率（仅对最新期间）
                period_free_cash_flow_per_share = None
                period_free_cash_flow_yield = None
                if period_idx == 0:
                    if free_cash_flow:
                        shares_outstanding = info.get("sharesOutstanding")
                        if shares_outstanding and shares_outstanding > 0:
                            period_free_cash_flow_per_share = free_cash_flow / shares_outstanding
                    if free_cash_flow and market_cap and market_cap > 0:
                        period_free_cash_flow_yield = free_cash_flow / market_cap
                
                # 为该期间创建FinancialMetrics对象
                period_metric = FinancialMetrics(
                    ticker=ticker,
                    report_period=period_str,
                    period=period,
                    currency=info.get("currency", "USD"),
                    # 估值指标（仅最新期间有市值相关数据）
                    market_cap=float(market_cap) if market_cap and period_idx == 0 else None,
                    enterprise_value=None,
                    price_to_earnings_ratio=float(pe_ratio) if pe_ratio and period_idx == 0 else None,
                    price_to_book_ratio=float(pb_ratio) if pb_ratio and period_idx == 0 else None,
                    price_to_sales_ratio=float(ps_ratio) if ps_ratio and period_idx == 0 else None,
                    enterprise_value_to_ebitda_ratio=None,
                    enterprise_value_to_revenue_ratio=None,
                    free_cash_flow_yield=float(period_free_cash_flow_yield) if period_free_cash_flow_yield else None,
                    peg_ratio=info.get("pegRatio") if period_idx == 0 else None,
                    # 盈利能力指标
                    gross_margin=float(gross_margin) if gross_margin and period_idx == 0 else None,
                    operating_margin=float(operating_margin) if operating_margin and period_idx == 0 else None,
                    net_margin=float(profit_margin) if profit_margin and period_idx == 0 else None,
                    return_on_equity=float(roe) if roe else None,
                    return_on_assets=float(roa) if roa else None,
                    return_on_invested_capital=None,
                    # 效率指标
                    asset_turnover=None,
                    inventory_turnover=None,
                    receivables_turnover=None,
                    days_sales_outstanding=None,
                    operating_cycle=None,
                    working_capital_turnover=None,
                    # 流动性指标（仅最新期间）
                    current_ratio=float(current_ratio) if current_ratio and period_idx == 0 else None,
                    quick_ratio=float(quick_ratio) if quick_ratio and period_idx == 0 else None,
                    cash_ratio=float(cash_ratio) if cash_ratio and period_idx == 0 else None,
                    operating_cash_flow_ratio=None,
                    # 杠杆指标
                    debt_to_equity=float(period_debt_to_equity) if period_debt_to_equity else None,
                    debt_to_assets=float(period_debt_to_assets) if period_debt_to_assets else None,
                    interest_coverage=None,
                    # 增长指标
                    revenue_growth=float(period_revenue_growth) if period_revenue_growth is not None else None,
                    earnings_growth=float(period_earnings_growth) if period_earnings_growth is not None else None,
                    book_value_growth=float(period_book_value_growth) if period_book_value_growth is not None else None,
                    earnings_per_share_growth=float(earnings_quarterly_growth) if earnings_quarterly_growth is not None and period_idx == 0 else None,
                    free_cash_flow_growth=float(period_free_cash_flow_growth) if period_free_cash_flow_growth is not None else None,
                    operating_income_growth=None,
                    ebitda_growth=None,
                    payout_ratio=info.get("payoutRatio") if period_idx == 0 else None,
                    # 每股指标（仅最新期间）
                    earnings_per_share=float(info.get("trailingEps") or info.get("forwardEps") or 0) if (info.get("trailingEps") or info.get("forwardEps")) and period_idx == 0 else None,
                    book_value_per_share=float(info.get("bookValue")) if info.get("bookValue") and period_idx == 0 else None,
                    free_cash_flow_per_share=float(period_free_cash_flow_per_share) if period_free_cash_flow_per_share else None,
                )
                metrics.append(period_metric)
        
        return metrics[:limit]
        
    except Exception as e:
        print(f"Warning: yfinance获取财务指标失败 ({ticker}): {str(e)}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return []


def get_yfinance_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """
    使用yfinance获取财务项目数据。
    
    Args:
        ticker: 股票代码
        line_items: 要获取的财务项目列表
        end_date: 结束日期
        period: 财报周期
        limit: 返回记录数
    
    Returns:
        LineItem对象列表
    """
    try:
        import yfinance as yf
    except ImportError:
        print(f"Warning: yfinance未安装，无法使用yfinance获取财务项目")
        return []
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            return []
        
        # 获取财务报表数据
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow
        
        line_items_list = []
        
        # 为每个历史期间创建LineItem对象
        if financials is not None and not financials.empty:
            periods_to_process = min(len(financials.columns), limit)
            
            for period_idx in range(periods_to_process):
                report_period = financials.columns[-(period_idx + 1)]
                period_str = str(report_period) if isinstance(report_period, pd.Timestamp) else end_date
                
                # 创建LineItem对象，包含所有请求的财务项目
                line_item_data = {
                    "ticker": ticker,
                    "report_period": period_str,
                    "period": period,
                    "currency": info.get("currency", "USD"),
                }
                
                # 从财务报表中提取数据
                # 利润表数据
                if financials is not None and not financials.empty and len(financials.columns) > period_idx:
                    try:
                        if "revenue" in [li.lower() for li in line_items] and "Total Revenue" in financials.index:
                            line_item_data["revenue"] = float(financials.loc["Total Revenue"].iloc[-(period_idx + 1)])
                        if "net_income" in [li.lower() for li in line_items] and "Net Income" in financials.index:
                            line_item_data["net_income"] = float(financials.loc["Net Income"].iloc[-(period_idx + 1)])
                        if "gross_profit" in [li.lower() for li in line_items] and "Gross Profit" in financials.index:
                            line_item_data["gross_profit"] = float(financials.loc["Gross Profit"].iloc[-(period_idx + 1)])
                    except (IndexError, KeyError, ValueError):
                        pass
                
                # 资产负债表数据
                if balance_sheet is not None and not balance_sheet.empty and len(balance_sheet.columns) > period_idx:
                    try:
                        if "total_assets" in [li.lower() for li in line_items]:
                            if "Total Assets" in balance_sheet.index:
                                line_item_data["total_assets"] = float(balance_sheet.loc["Total Assets"].iloc[-(period_idx + 1)])
                        if "total_liabilities" in [li.lower() for li in line_items]:
                            if "Total Liabilities" in balance_sheet.index:
                                line_item_data["total_liabilities"] = float(balance_sheet.loc["Total Liabilities"].iloc[-(period_idx + 1)])
                            elif "Total Liab" in balance_sheet.index:
                                line_item_data["total_liabilities"] = float(balance_sheet.loc["Total Liab"].iloc[-(period_idx + 1)])
                        if "shareholders_equity" in [li.lower() for li in line_items]:
                            if "Stockholders Equity" in balance_sheet.index:
                                line_item_data["shareholders_equity"] = float(balance_sheet.loc["Stockholders Equity"].iloc[-(period_idx + 1)])
                            elif "Total Stockholder Equity" in balance_sheet.index:
                                line_item_data["shareholders_equity"] = float(balance_sheet.loc["Total Stockholder Equity"].iloc[-(period_idx + 1)])
                    except (IndexError, KeyError, ValueError):
                        pass
                
                # 现金流表数据（用于管理层质量分析）
                if cashflow is not None and not cashflow.empty and len(cashflow.columns) > period_idx:
                    try:
                        # 自由现金流
                        if "free_cash_flow" in [li.lower() for li in line_items] and "Free Cash Flow" in cashflow.index:
                            line_item_data["free_cash_flow"] = float(cashflow.loc["Free Cash Flow"].iloc[-(period_idx + 1)])
                        
                        # 资本支出
                        if "capital_expenditure" in [li.lower() for li in line_items] and "Capital Expenditure" in cashflow.index:
                            line_item_data["capital_expenditure"] = float(cashflow.loc["Capital Expenditure"].iloc[-(period_idx + 1)])
                        
                        # 折旧和摊销
                        if "depreciation_and_amortization" in [li.lower() for li in line_items]:
                            if "Depreciation And Amortization" in cashflow.index:
                                line_item_data["depreciation_and_amortization"] = float(cashflow.loc["Depreciation And Amortization"].iloc[-(period_idx + 1)])
                            elif "Depreciation" in cashflow.index:
                                line_item_data["depreciation_and_amortization"] = float(cashflow.loc["Depreciation"].iloc[-(period_idx + 1)])
                        
                        # 股票回购/发行（用于管理层质量分析）
                        if "issuance_or_purchase_of_equity_shares" in [li.lower() for li in line_items]:
                            # 计算净股票发行（负数表示回购，正数表示发行）
                            repurchase = 0.0
                            issuance = 0.0
                            
                            if "Repurchase Of Capital Stock" in cashflow.index:
                                repurchase = float(cashflow.loc["Repurchase Of Capital Stock"].iloc[-(period_idx + 1)]) or 0.0
                            if "Issuance Of Capital Stock" in cashflow.index:
                                issuance = float(cashflow.loc["Issuance Of Capital Stock"].iloc[-(period_idx + 1)]) or 0.0
                            elif "Net Common Stock Issuance" in cashflow.index:
                                issuance = float(cashflow.loc["Net Common Stock Issuance"].iloc[-(period_idx + 1)]) or 0.0
                            
                            # 净股票发行 = 发行 - 回购（负数表示净回购）
                            net_issuance = issuance - repurchase
                            if pd.notna(net_issuance):
                                line_item_data["issuance_or_purchase_of_equity_shares"] = float(net_issuance)
                        
                        # 分红（用于管理层质量分析）
                        if "dividends_and_other_cash_distributions" in [li.lower() for li in line_items]:
                            # yfinance可能没有直接的dividend字段，需要从其他字段计算
                            # 通常分红在Financing Cash Flow中
                            if "Common Stock Dividends Paid" in cashflow.index:
                                line_item_data["dividends_and_other_cash_distributions"] = -float(cashflow.loc["Common Stock Dividends Paid"].iloc[-(period_idx + 1)])  # 负数表示现金流出
                            elif "Dividends Paid" in cashflow.index:
                                line_item_data["dividends_and_other_cash_distributions"] = -float(cashflow.loc["Dividends Paid"].iloc[-(period_idx + 1)])
                        
                        # 流通股数（从info获取，适用于所有期间）
                        if "outstanding_shares" in [li.lower() for li in line_items] and period_idx == 0:
                            shares_outstanding = info.get("sharesOutstanding")
                            if shares_outstanding:
                                line_item_data["outstanding_shares"] = float(shares_outstanding)
                    except (IndexError, KeyError, ValueError, TypeError):
                        pass
                
                # 创建LineItem对象
                if len(line_item_data) > 4:  # 至少有ticker, report_period, period, currency之外的数据
                    line_item = LineItem(**line_item_data)
                    line_items_list.append(line_item)
        
        return line_items_list[:limit]
        
    except Exception as e:
        print(f"Warning: yfinance获取财务项目失败 ({ticker}): {str(e)}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return []


def _looks_like_cn_or_hk_ticker(ticker: str) -> bool:
    """
    粗略判断是否是 A 股 / 港股代码：
    - 纯数字（如 600000, 000001）
    - 以 .SH / .SZ / .HK 结尾
    """
    t = ticker.upper()
    if t.endswith((".SH", ".SZ", ".HK")):
        return True
    # 去掉后缀后如果是纯数字，也认为是 A 股
    base = t.split(".")[0]
    return base.isdigit() and len(base) >= 4


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None, cn_api_key: str = None, massive_api_key: str = None, use_openbb: bool = False) -> list[Price]:
    """
    Fetch price data from cache or API.
    
    自动识别 A 股/港股代码，优先使用 DeepAlpha 接口；否则使用美股数据源。
    支持多个美股数据源：OpenBB（免费）、Financial Datasets API、Massive API（备用）。
    
    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        api_key: 用于美股数据的 API key (FINANCIAL_DATASETS_API_KEY)
        cn_api_key: 用于 A 股/港股数据的 API key (DEEPALPHA_API_KEY)
        massive_api_key: Massive 数据源的 API key（备用美股数据源）
        use_openbb: 是否优先使用 OpenBB（免费，无需 API key）
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # 如果是 A 股/港股代码，优先使用 DeepAlpha（使用 cn_api_key）
    if _looks_like_cn_or_hk_ticker(ticker):
        try:
            prices = get_cn_prices(ticker, start_date, end_date, api_key=cn_api_key)
            if prices:
                return prices
            else:
                # 如果返回空列表，可能是数据不存在或日期范围问题
                # 对于 A 股/港股，不 fallback 到美股数据源，直接返回空列表
                print(f"Warning: DeepAlpha returned no price data for {ticker} ({start_date} to {end_date}). "
                      f"Please check if the ticker is valid and the date range is correct.")
                return []  # 直接返回空列表，不 fallback 到美股数据源
        except Exception as e:
            # 区分不同类型的错误
            error_type = type(e).__name__
            error_msg = str(e)
            
            # 如果是配置错误（API key 缺失），给出明确提示
            if "DeepAlphaConfigError" in error_type or "Missing DeepAlpha API key" in error_msg:
                raise Exception(
                    f"无法获取 A 股数据 {ticker}: DeepAlpha API key 未配置。"
                    f"请在 .env 文件中设置 DEEPALPHA_API_KEY，或通过参数传入 api_key。"
                    f"错误详情: {error_msg}"
                )
            # 如果是网络或API错误，给出详细错误信息
            elif "requests" in error_msg.lower() or "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                raise Exception(
                    f"无法获取 A 股数据 {ticker}: DeepAlpha API 网络请求失败。"
                    f"请检查网络连接和 API 服务状态。错误详情: {error_msg}"
                )
            # 其他错误：对于 A 股/港股，不 fallback 到美股数据源，直接抛出异常
            else:
                raise Exception(
                    f"无法获取 A 股数据 {ticker}: DeepAlpha API 调用失败。"
                    f"错误类型: {error_type}, 错误详情: {error_msg}"
                )

    # 美股数据源：优先使用 OpenBB（如果启用且可用）
    if use_openbb:
        try:
            from src.tools.openbb import get_openbb_prices, OPENBB_AVAILABLE
            if OPENBB_AVAILABLE:
                prices = get_openbb_prices(ticker, start_date, end_date)
                if prices:
                    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
                    return prices
        except ImportError:
            # OpenBB 未安装，继续使用其他数据源
            print(f"Warning: OpenBB 未安装，切换到其他数据源")
        except Exception as e:
            # OpenBB 获取失败，继续使用其他数据源
            print(f"Warning: OpenBB 获取价格数据失败，切换到其他数据源: {str(e)}")
    
    # Fallback to US data source (Financial Datasets API 或 Massive API/Polygon.io)
    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    
    try:
        response = _make_api_request_with_fallback(
            url=url,
            api_key=api_key,
            massive_api_key=massive_api_key,
            timeout=30,
            operation="获取价格数据",
            ticker=ticker,
        )
    except APIError as e:
        # 如果主要API失败，尝试使用Polygon.io（Massive API）
        if massive_api_key and (e.status_code in [401, 402] or e.recoverable):
            print(f"Warning: Financial Datasets API失败，尝试使用Polygon.io (Massive API)...")
            try:
                polygon_prices = get_polygon_prices(ticker, start_date, end_date, massive_api_key)
                if polygon_prices:
                    # Cache the results
                    _cache.set_prices(cache_key, [p.model_dump() for p in polygon_prices])
                    return polygon_prices
                else:
                    # Polygon.io返回空列表（可能是计划限制），返回空列表而不是抛出错误
                    print(f"Info: Polygon.io无法获取数据（可能是计划限制），返回空列表")
                    return []
            except APIError as polygon_error:
                # 如果是403错误（计划限制），返回空列表，不抛出错误
                if polygon_error.status_code == 403:
                    print(f"Warning: Polygon.io计划限制: {polygon_error.message}")
                    print(f"Info: 返回空列表，系统将使用其他可用数据源或继续分析")
                    # 返回空列表，让调用者继续（不抛出错误）
                    return []
                else:
                    print(f"Warning: Polygon.io也失败: {str(polygon_error)}")
                    # 如果Polygon.io也失败，抛出原始错误
                    raise e
            except Exception as polygon_error:
                print(f"Warning: Polygon.io也失败: {str(polygon_error)}")
                # 如果Polygon.io也失败，抛出原始错误
                raise e
        # 如果没有Massive API密钥或Polygon.io也失败，抛出原始错误
        raise
    except Exception as e:
        # 如果主要API失败，尝试使用Polygon.io（Massive API）
        if massive_api_key:
            print(f"Warning: Financial Datasets API失败，尝试使用Polygon.io (Massive API)...")
            try:
                polygon_prices = get_polygon_prices(ticker, start_date, end_date, massive_api_key)
                if polygon_prices:
                    # Cache the results
                    _cache.set_prices(cache_key, [p.model_dump() for p in polygon_prices])
                    return polygon_prices
            except Exception as polygon_error:
                print(f"Warning: Polygon.io也失败: {str(polygon_error)}")
        raise APIError(f"获取价格数据失败: {str(e)}", ticker=ticker, recoverable=True)

    # Parse response with Pydantic model
    price_response = PriceResponse(**response.json())
    prices = price_response.prices

    if not prices:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
    cn_api_key: str = None,
    massive_api_key: str = None,
    use_openbb: bool = False,
) -> list[FinancialMetrics]:
    """
    Fetch financial metrics from cache or API.
    
    自动识别 A 股/港股代码，优先使用 DeepAlpha 接口；否则使用美股数据源。
    
    美股数据源优先级：
    1. OpenBB（如果启用且可用）
    2. yfinance（免费，主要数据源，无需API密钥）
    3. Financial Datasets API（付费，备用）
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        period: 财报周期
        limit: 返回记录数
        api_key: 用于美股数据的 API key (FINANCIAL_DATASETS_API_KEY)
        cn_api_key: 用于 A 股/港股数据的 API key (DEEPALPHA_API_KEY)
        massive_api_key: Massive API key（备用，目前仅用于价格数据）
        use_openbb: 是否优先使用 OpenBB
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # 如果是 A 股/港股代码，优先使用 DeepAlpha（使用 cn_api_key）
    if _looks_like_cn_or_hk_ticker(ticker):
        # 调试信息：检查 API key 是否传递
        if not cn_api_key:
            print(f"Warning: DEEPALPHA_API_KEY not found in state for ticker {ticker}, will try to use environment variable")
        
        try:
            metrics = get_cn_financial_metrics(ticker, end_date, period=period, limit=limit, api_key=cn_api_key)
            if metrics:
                return metrics
            else:
                # 如果返回空列表，可能是数据不存在
                print(f"Warning: DeepAlpha returned no financial metrics for {ticker} (end_date: {end_date}). "
                      f"Please check if the ticker is valid.")
                # 返回空列表，让智能体继续分析（使用可用数据生成中性信号）
                return []
        except Exception as e:
            # 区分不同类型的错误
            error_type = type(e).__name__
            error_msg = str(e)
            
            # 打印详细错误信息到控制台（用于调试）
            print(f"ERROR: Failed to get financial metrics for {ticker}")
            print(f"  Error type: {error_type}")
            print(f"  Error message: {error_msg}")
            print(f"  cn_api_key provided: {'Yes' if cn_api_key else 'No'}")
            
            # 如果是配置错误（API key 缺失），给出明确提示并抛出异常
            if "DeepAlphaConfigError" in error_type or "Missing DeepAlpha API key" in error_msg:
                raise Exception(
                    f"无法获取 A 股财务指标 {ticker}: DeepAlpha API key 未配置。"
                    f"请在设置界面配置 DEEPALPHA_API_KEY，或在 .env 文件中设置，或通过参数传入 api_key。"
                    f"错误详情: {error_msg}"
                )
            # 如果是数据缺失错误（港股接口不支持或数据不存在），返回空列表而不是抛出异常
            # 这样智能体可以继续分析，使用可用数据生成中性信号
            elif "all hk function formats failed" in error_msg.lower() or "不支持" in error_msg or "not found" in error_msg.lower():
                print(f"Info: 港股 {ticker} 财务指标数据不可用，返回空列表: {error_msg}")
                return []
            # 如果是网络或API错误，给出详细错误信息并抛出异常
            elif "requests" in error_msg.lower() or "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                raise Exception(
                    f"无法获取 A 股财务指标 {ticker}: DeepAlpha API 网络请求失败。"
                    f"请检查网络连接和 API 服务状态。错误详情: {error_msg}"
                )
            # 其他错误：对于数据缺失的情况，返回空列表；其他情况抛出异常
            else:
                # 检查是否是数据缺失相关的错误
                if "数据不可用" in error_msg or "no data" in error_msg.lower() or "empty" in error_msg.lower():
                    print(f"Info: {ticker} 财务指标数据不可用，返回空列表: {error_msg}")
                    return []
                # 其他错误抛出异常
                raise Exception(
                    f"无法获取 A 股财务指标 {ticker}: DeepAlpha API 调用失败。"
                    f"错误类型: {error_type}, 错误详情: {error_msg}"
                )

    # 美股数据源：优先使用 OpenBB（如果启用且可用）
    if use_openbb:
        try:
            from src.tools.openbb import get_openbb_financial_metrics, OPENBB_AVAILABLE
            if OPENBB_AVAILABLE:
                metrics = get_openbb_financial_metrics(ticker, end_date, period=period, limit=limit)
                if metrics:
                    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])
                    return metrics
        except ImportError:
            print(f"Warning: OpenBB 未安装，切换到其他数据源")
        except Exception as e:
            print(f"Warning: OpenBB 获取财务指标失败，切换到其他数据源: {str(e)}")
    
    # 美股数据源：优先使用 yfinance（免费，主要数据源）
    try:
        print(f"Info: 使用yfinance获取 {ticker} 的财务指标数据...")
        yfinance_metrics = get_yfinance_financial_metrics(ticker, end_date, period=period, limit=limit)
        if yfinance_metrics:
            _cache.set_financial_metrics(cache_key, [m.model_dump() for m in yfinance_metrics])
            return yfinance_metrics
        else:
            print(f"Info: yfinance无法获取财务指标数据，切换到备用数据源")
    except Exception as yf_error:
        print(f"Warning: yfinance获取财务指标失败，切换到备用数据源: {str(yf_error)}")
    
    # Fallback to US data source (Financial Datasets API 或 Massive API/Polygon.io)
    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    try:
        response = _make_api_request_with_fallback(
            url=url,
            api_key=api_key,
            massive_api_key=massive_api_key,
            timeout=30,
            operation="获取财务指标",
            ticker=ticker,
        )
    except APIError as e:
        # 如果Financial Datasets API失败，返回空列表
        # 注意：yfinance已经在前面尝试过了，如果yfinance也失败，说明数据不可用
        print(f"Info: Financial Datasets API失败，yfinance也已尝试，返回空列表")
        return []
    except Exception as e:
        # 如果Financial Datasets API失败，返回空列表
        # 注意：yfinance已经在前面尝试过了，如果yfinance也失败，说明数据不可用
        print(f"Info: Financial Datasets API失败，yfinance也已尝试，返回空列表")
        return []

    # Parse response with Pydantic model
    metrics_response = FinancialMetricsResponse(**response.json())
    financial_metrics = metrics_response.financial_metrics

    if not financial_metrics:
        return []

    # Cache the results as dicts using the comprehensive cache key
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
    cn_api_key: str = None,
    massive_api_key: str = None,
    use_openbb: bool = False,
) -> list[LineItem]:
    """
    Fetch line items from API.

    自动识别 A 股/港股代码，优先使用 DeepAlpha 接口获取财务数据；否则使用美股数据源。
    
    Args:
        ticker: 股票代码
        line_items: 要获取的财务项目列表
        end_date: 结束日期
        period: 报告期类型（ttm/quarterly/annual）
        limit: 返回的最大记录数
        api_key: 美股数据源的 API key (FINANCIAL_DATASETS_API_KEY)
        cn_api_key: A 股/港股数据源的 API key (DEEPALPHA_API_KEY)
    """
    # 如果是 A 股/港股代码，优先使用 DeepAlpha
    if _looks_like_cn_or_hk_ticker(ticker):
        try:
            # 使用 cn_api_key 作为 DeepAlpha API key，如果没有则使用 api_key，最后从环境变量读取
            deepalpha_key = cn_api_key or api_key
            cn_line_items = get_cn_all_line_items(ticker, api_key=deepalpha_key)
            if cn_line_items:
                return cn_line_items[:limit]
            else:
                # 如果返回空列表，可能是数据不存在
                # 对于 A 股/港股，不 fallback 到美股数据源，直接返回空列表
                print(f"Warning: DeepAlpha returned no line items for {ticker}. "
                      f"Please check if the ticker is valid.")
                return []  # 直接返回空列表，不 fallback 到美股数据源
        except Exception as e:
            # 区分不同类型的错误
            error_type = type(e).__name__
            error_msg = str(e)
            
            # 如果是配置错误（API key 缺失），给出明确提示
            if "DeepAlphaConfigError" in error_type or "Missing DeepAlpha API key" in error_msg:
                raise Exception(
                    f"无法获取 A 股财务数据 {ticker}: DeepAlpha API key 未配置。"
                    f"请在 .env 文件中设置 DEEPALPHA_API_KEY，或通过参数传入 api_key。"
                    f"错误详情: {error_msg}"
                )
            # 如果是网络或API错误，给出详细错误信息
            elif "requests" in error_msg.lower() or "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                raise Exception(
                    f"无法获取 A 股财务数据 {ticker}: DeepAlpha API 网络请求失败。"
                    f"请检查网络连接和 API 服务状态。错误详情: {error_msg}"
                )
            # 其他错误：对于 A 股/港股，不 fallback 到美股数据源，直接抛出异常
            else:
                raise Exception(
                    f"无法获取 A 股财务数据 {ticker}: DeepAlpha API 调用失败。"
                    f"错误类型: {error_type}, 错误详情: {error_msg}"
                )

    # 美股数据源：优先使用 OpenBB（如果启用且可用）
    if use_openbb:
        try:
            from src.tools.openbb import get_openbb_line_items, OPENBB_AVAILABLE
            if OPENBB_AVAILABLE:
                line_items_list = get_openbb_line_items(ticker, line_items, end_date, period=period, limit=limit)
                if line_items_list:
                    return line_items_list
        except ImportError:
            print(f"Warning: OpenBB 未安装，切换到其他数据源")
        except Exception as e:
            print(f"Warning: OpenBB 获取财务数据失败，切换到其他数据源: {str(e)}")
    
    # 美股数据源：优先使用 yfinance（免费，主要数据源）
    try:
        yfinance_line_items = get_yfinance_line_items(ticker, line_items, end_date, period=period, limit=limit)
        if yfinance_line_items:
            return yfinance_line_items
    except Exception as yf_error:
        print(f"Warning: yfinance获取财务项目失败，切换到备用数据源: {str(yf_error)}")
    
    # Fallback to US data source (Financial Datasets API 或 Massive API) - 仅用于美股代码
    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    try:
        response = _make_api_request_with_fallback(
            url=url,
            api_key=api_key,
            massive_api_key=massive_api_key,
            method="POST",
            json_data=body,
            timeout=30,
            operation="获取财务项目",
            ticker=ticker,
        )
    except APIError as e:
        # Re-raise APIError as-is
        raise
    except Exception as e:
        # Wrap other exceptions
        raise APIError(f"获取财务项目失败: {str(e)}", ticker=ticker, recoverable=True)
    data = response.json()
    response_model = LineItemResponse(**data)
    search_results = response_model.search_results
    if not search_results:
        return []

    # Cache the results
    return search_results[:limit]


def get_cn_all_line_items(
    ticker: str,
    api_key: str | None = None,
) -> list[LineItem]:
    """
    获取 A 股/港股的所有财务数据（合并资产负债表、利润表、现金流量表）。
    
    这是一个便捷函数，将三张财务报表的数据合并后返回。
    """
    all_items: list[LineItem] = []
    
    try:
        # 获取资产负债表数据
        balance_items = get_cn_balance_sheet_line_items(ticker, api_key=api_key)
        all_items.extend(balance_items)
    except Exception as e:
        print(f"Warning: Failed to fetch balance sheet for {ticker}: {e}")
    
    try:
        # 获取利润表数据
        income_items = get_cn_income_statement_line_items(ticker, api_key=api_key)
        # 合并到同一报告期的数据中
        for income_item in income_items:
            # 查找是否有相同报告期的 balance_item
            found = False
            for i, item in enumerate(all_items):
                if hasattr(item, 'report_period') and hasattr(income_item, 'report_period'):
                    if item.report_period == income_item.report_period:
                        # 合并字段
                        merged_data = item.model_dump()
                        income_data = income_item.model_dump()
                        for key, value in income_data.items():
                            if key not in merged_data or merged_data[key] is None:
                                merged_data[key] = value
                        # 确保 currency 不为 None
                        if not merged_data.get("currency"):
                            merged_data["currency"] = "CNY"
                        all_items[i] = LineItem(**merged_data)
                        found = True
                        break
            if not found:
                all_items.append(income_item)
    except Exception as e:
        print(f"Warning: Failed to fetch income statement for {ticker}: {e}")
    
    try:
        # 获取现金流量表数据
        cash_flow_items = get_cn_cash_flow_line_items(ticker, api_key=api_key)
        # 合并到同一报告期的数据中
        for cf_item in cash_flow_items:
            found = False
            for i, item in enumerate(all_items):
                if hasattr(item, 'report_period') and hasattr(cf_item, 'report_period'):
                    if item.report_period == cf_item.report_period:
                        # 合并字段
                        merged_data = item.model_dump()
                        cf_data = cf_item.model_dump()
                        for key, value in cf_data.items():
                            if key not in merged_data or merged_data[key] is None:
                                merged_data[key] = value
                        # 确保 currency 不为 None
                        if not merged_data.get("currency"):
                            merged_data["currency"] = "CNY"
                        all_items[i] = LineItem(**merged_data)
                        found = True
                        break
            if not found:
                all_items.append(cf_item)
    except Exception as e:
        print(f"Warning: Failed to fetch cash flow for {ticker}: {e}")
    
    # 按报告期排序
    try:
        all_items.sort(key=lambda x: getattr(x, 'report_period', ''), reverse=True)
    except Exception:
        pass
    
    return all_items


def get_cn_balance_sheet_line_items(
    ticker: str,
    api_key: str | None = None,
) -> list[LineItem]:
    """
    使用 DeepAlpha BALANCE_SHEET 接口，将 A 股 / 港股资产负债表转换为 LineItem 列表。

    说明：
    - 适合在中国投资大师 Agent 中直接调用，用于对银行/金融等 A 股标的做更细致分析。
    - 这里不做字段过滤，直接把接口返回的所有字段塞进 LineItem.extra 中，保证信息不丢。
    - report_period 从类似 "20250930" 的字符串转换而来，period 暂定为 "annual"。
    """
    # 注意：对于 A 股数据，应该传入 DEEPALPHA_API_KEY（如果 api_key 为 None，则从环境变量读取）
    try:
        client = get_deepalpha_client(api_key=api_key)
        raw = get_balance_sheet_raw(symbol=ticker, client=client)
    except Exception as e:
        # 对于港股数据缺失的情况，返回空列表而不是抛出异常
        # 这样智能体可以继续分析，使用可用数据生成中性信号
        error_msg = str(e).lower()
        if "all hk function formats failed" in error_msg or "不支持" in error_msg or "not found" in error_msg:
            print(f"Info: 港股 {ticker} 资产负债表数据不可用，返回空列表: {str(e)}")
            return []
        # 其他错误（如网络错误、配置错误）仍然抛出异常
        raise

    line_items: list[LineItem] = []
    for report_period, fields in raw.items():
        if not isinstance(fields, dict):
            continue

        # DeepAlpha 返回的数据里已经包含了很多字段，我们全部打平放入 LineItem
        # 确保 currency 不为 None
        currency = fields.get("currency") or "CNY"
        if currency is None:
            currency = "CNY"
        # 确保常用字段存在（即使为 None，也保证属性存在）
        # 这些字段可能在不同报表中，但代码中会访问，所以需要确保属性存在
        item_data: dict[str, any] = {
            "ticker": ticker,
            "report_period": str(report_period),
            "period": "annual",
            "currency": currency,
            "net_income": fields.get("net_income"),
            "depreciation_and_amortization": fields.get("depreciation_and_amortization") or fields.get("depreciation") or fields.get("amortization"),
            "capital_expenditure": fields.get("capital_expenditure") or fields.get("capex"),
            "free_cash_flow": fields.get("free_cash_flow") or fields.get("fcf"),
            "revenue": fields.get("revenue") or fields.get("total_revenue"),
            "operating_income": fields.get("operating_income") or fields.get("operating_profit"),
            "ebit": fields.get("ebit"),
            "ebitda": fields.get("ebitda"),
            "total_debt": fields.get("total_debt") or fields.get("debt"),
            "cash_and_equivalents": fields.get("cash_and_equivalents") or fields.get("cash"),
            "working_capital": fields.get("working_capital"),
            "interest_expense": fields.get("interest_expense") or fields.get("interest"),
        }
        # 其余字段原样附加，LineItem.extra = "allow" 可以接受
        item_data.update(fields)
        # 确保 currency 不为 None（update 可能会覆盖 currency 为 None）
        if not item_data.get("currency"):
            item_data["currency"] = "CNY"

        line_items.append(LineItem(**item_data))

    # 按报告期从新到旧排序，方便上层逻辑直接用 line_items[0] 作为最近一期
    try:
        line_items.sort(key=lambda x: x.report_period, reverse=True)  # type: ignore[attr-defined]
    except Exception:
        # 如果排序失败，就保持原顺序
        pass

    return line_items[:10]


def get_cn_income_statement_line_items(
    ticker: str,
    api_key: str | None = None,
) -> list[LineItem]:
    """
    使用 DeepAlpha INCOME_STATEMENT 接口，将 A 股 / 港股利润表转换为 LineItem 列表。
    
    返回的 LineItem 包含收入、成本、利润等所有利润表科目。
    """
    # 注意：对于 A 股数据，应该传入 DEEPALPHA_API_KEY（如果 api_key 为 None，则从环境变量读取）
    client = get_deepalpha_client(api_key=api_key)
    raw = get_income_statement_raw(symbol=ticker, client=client)

    line_items: list[LineItem] = []
    for report_period, fields in raw.items():
        if not isinstance(fields, dict):
            continue

        # 确保 currency 不为 None
        currency = fields.get("currency") or "CNY"
        if currency is None:
            currency = "CNY"
        # 确保常用字段存在（即使为 None，也保证属性存在）
        net_income = fields.get("net_income")

        item_data: dict[str, any] = {
            "ticker": ticker,
            "report_period": str(report_period),
            "period": "annual",
            "currency": currency,
            "net_income": net_income,
        }
        item_data.update(fields)
        # 确保 currency 不为 None（update 可能会覆盖 currency 为 None）
        if not item_data.get("currency"):
            item_data["currency"] = "CNY"

        line_items.append(LineItem(**item_data))

    try:
        line_items.sort(key=lambda x: x.report_period, reverse=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    return line_items[:10]


def get_cn_cash_flow_line_items(
    ticker: str,
    api_key: str | None = None,
) -> list[LineItem]:
    """
    使用 DeepAlpha CASH_FLOW 接口，将 A 股 / 港股现金流量表转换为 LineItem 列表。
    
    返回的 LineItem 包含经营、投资、筹资活动现金流等所有现金流量表科目。
    """
    # 注意：对于 A 股数据，应该传入 DEEPALPHA_API_KEY（如果 api_key 为 None，则从环境变量读取）
    client = get_deepalpha_client(api_key=api_key)
    raw = get_cash_flow_raw(symbol=ticker, client=client)

    line_items: list[LineItem] = []
    for report_period, fields in raw.items():
        if not isinstance(fields, dict):
            continue

        # 确保 currency 不为 None
        currency = fields.get("currency") or "CNY"
        if currency is None:
            currency = "CNY"
        # 确保常用字段存在（即使为 None，也保证属性存在）
        # 这些字段可能在不同报表中，但代码中会访问，所以需要确保属性存在
        item_data: dict[str, any] = {
            "ticker": ticker,
            "report_period": str(report_period),
            "period": "annual",
            "currency": currency,
            "net_income": fields.get("net_income"),
            "depreciation_and_amortization": fields.get("depreciation_and_amortization") or fields.get("depreciation") or fields.get("amortization"),
            "capital_expenditure": fields.get("capital_expenditure") or fields.get("capex"),
            "free_cash_flow": fields.get("free_cash_flow") or fields.get("fcf"),
            "revenue": fields.get("revenue") or fields.get("total_revenue"),
            "operating_income": fields.get("operating_income") or fields.get("operating_profit"),
            "ebit": fields.get("ebit"),
            "ebitda": fields.get("ebitda"),
            "total_debt": fields.get("total_debt") or fields.get("debt"),
            "cash_and_equivalents": fields.get("cash_and_equivalents") or fields.get("cash"),
            "working_capital": fields.get("working_capital"),
            "interest_expense": fields.get("interest_expense") or fields.get("interest"),
        }
        item_data.update(fields)
        # 确保 currency 不为 None（update 可能会覆盖 currency 为 None）
        if not item_data.get("currency"):
            item_data["currency"] = "CNY"

        line_items.append(LineItem(**item_data))

    try:
        line_items.sort(key=lambda x: x.report_period, reverse=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    return line_items[:10]


def get_cn_prices(
    ticker: str,
    start_date: str,
    end_date: str,
    api_key: str = None,
) -> list[Price]:
    """
    使用 DeepAlpha DAILY_PRICE 接口，获取 A 股 / 港股日线行情数据。
    
    返回格式与 get_prices 一致，可直接被技术分析 Agent 使用。
    
    Raises:
        DeepAlphaConfigError: 如果 API key 未配置
        Exception: 如果 API 调用失败或数据格式错误
    """
    cache_key = f"cn_{ticker}_{start_date}_{end_date}"
    
    # Check cache first
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # Fetch from DeepAlpha
    # 注意：对于 A 股数据，应该传入 DEEPALPHA_API_KEY（如果 api_key 为 None，则从环境变量读取）
    try:
        client = get_deepalpha_client(api_key=api_key)
    except Exception as e:
        # 重新抛出配置错误，让上层处理
        raise
    
    try:
        raw_prices = get_daily_price_raw(
            symbol=ticker,
            start_date=start_date,
            end_date=end_date,
            client=client,
        )
    except Exception as e:
        # 重新抛出 API 调用错误，让上层处理
        raise Exception(
            f"DeepAlpha API 调用失败 (ticker: {ticker}, start_date: {start_date}, end_date: {end_date}): {str(e)}"
        )

    if not raw_prices:
        # 返回空列表而不是抛出异常，因为可能是数据不存在
        print(f"Info: DeepAlpha returned no price data for {ticker} ({start_date} to {end_date})")
        return []

    # Convert to Price objects
    prices: list[Price] = []
    conversion_errors = []
    for raw in raw_prices:
        try:
            # DeepAlpha 可能返回的字段名略有不同，需要适配
            price = Price(
                open=float(raw.get("open", raw.get("open_price", 0))),
                close=float(raw.get("close", raw.get("close_price", 0))),
                high=float(raw.get("high", raw.get("high_price", 0))),
                low=float(raw.get("low", raw.get("low_price", 0))),
                volume=int(raw.get("volume", raw.get("vol", 0))),
                time=raw.get("time", raw.get("date", raw.get("trade_date", ""))),
            )
            prices.append(price)
        except (ValueError, KeyError, TypeError) as e:
            conversion_errors.append(str(e))
            continue

    if not prices:
        if conversion_errors:
            raise Exception(
                f"无法转换 DeepAlpha 价格数据为 Price 对象 (ticker: {ticker}): "
                f"数据格式可能不正确。错误示例: {conversion_errors[0] if conversion_errors else 'unknown'}"
            )
        return []

    # Cache the results
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_cn_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """
    使用 DeepAlpha FINANALYSIS_MAIN 接口，获取 A 股 / 港股财务指标。
    
    返回格式与 get_financial_metrics 一致，可直接被估值/基本面 Agent 使用。
    """
    cache_key = f"cn_{ticker}_{period}_{end_date}_{limit}"
    
    # Check cache first
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # Fetch from DeepAlpha
    # 注意：对于 A 股数据，应该传入 DEEPALPHA_API_KEY（如果 api_key 为 None，则从环境变量读取）
    try:
        client = get_deepalpha_client(api_key=api_key)
    except Exception as e:
        # 重新抛出配置错误，让上层处理
        raise
    
    try:
        raw_indicators = get_financial_indicators_raw(symbol=ticker, client=client)
    except Exception as e:
        # 对于港股数据缺失的情况，返回空列表而不是抛出异常
        # 这样智能体可以继续分析，使用可用数据生成中性信号
        error_msg = str(e).lower()
        if "all hk function formats failed" in error_msg or "不支持" in error_msg or "not found" in error_msg:
            print(f"Info: 港股 {ticker} 财务指标数据不可用，返回空列表: {str(e)}")
            return []
        # 其他错误（如网络错误、配置错误）仍然抛出异常
        raise Exception(
            f"DeepAlpha API 调用失败 (ticker: {ticker}, function: FINANALYSIS_MAIN): {str(e)}"
        )

    if not raw_indicators:
        print(f"Info: DeepAlpha returned no financial indicators for {ticker}")
        return []

    # 调试：打印港股返回的所有字段（仅对港股）
    if _looks_like_cn_or_hk_ticker(ticker) and _is_hk_stock(ticker):
        print(f"Debug: 港股 {ticker} HKSTK_FINRPT_DER 财务指标字段:")
        for report_period, fields in list(raw_indicators.items())[:1]:  # 只打印第一条
            print(f"  报告期: {report_period}")
            print(f"  所有字段（共 {len(fields)} 个）: {sorted(list(fields.keys()))}")
            # 打印关键字段的值（港股实际字段名）
            key_fields = [
                "debtequ_rt", "current_rt", "operprof_tocl",  # 港股实际字段名
                "roe", "roa", "roic",  # ROE/ROA/ROIC 可能字段名
                "debtequityratio", "debt_to_equity", "operating_margin", 
                "currentratio", "current_ratio", "流动比率", "营业利润率", "资产负债率"
            ]
            found_key_fields = {}
            for key in key_fields:
                if key in fields:
                    found_key_fields[key] = fields[key]
            if found_key_fields:
                print(f"  找到的关键字段: {found_key_fields}")
            else:
                print(f"  未找到预期的关键字段")

    # 额外获取最新估值数据（VALUATNANALYD）
    latest_valuation: dict | None = None
    try:
        latest_valuation = get_latest_valuation(ticker, client=client)
        if latest_valuation:
            print(f"[DEBUG] 成功获取 VALUATNANALYD 估值数据（ticker={ticker}）:")
            print(f"  估值数据字段: {list(latest_valuation.keys())[:30]}")  # 只打印前30个字段
            # 特别检查关键估值字段
            val_key_fields = ["totsec_mv", "pe_ttm", "pe_lyr", "pb", "ps_ttm", "ps", "dividrt_ttm", "dividrt_lyr", 
                            "entpv_wth", "entpv_non", "market_cap", "pe", "pb_ratio", "ps_ratio"]
            found_val_fields = {k: latest_valuation.get(k) for k in val_key_fields if k in latest_valuation}
            if found_val_fields:
                print(f"  找到的关键估值字段: {found_val_fields}")
        else:
            print(f"[DEBUG] VALUATNANALYD 返回空数据（ticker={ticker}）")
    except Exception as e:
        print(f"Warning: 获取 VALUATNANALYD 估值数据失败 ({ticker}): {e}")
        import traceback
        print(f"  详细错误: {traceback.format_exc()}")

    # Convert to FinancialMetrics objects
    metrics: list[FinancialMetrics] = []
    for report_period, fields in raw_indicators.items():
        if not isinstance(fields, dict):
            continue
        
        # 调试：打印第一个报告期的所有字段名（仅打印一次）
        if not metrics and fields:
            print(f"[DEBUG] DeepAlpha FINANALYSIS_MAIN 返回的字段名（ticker={ticker}, report_period={report_period}）:")
            print(f"  所有字段: {list(fields.keys())[:50]}")  # 只打印前50个字段
            # 特别检查关键字段（使用 DeepAlpha 实际返回的字段名）
            key_fields = ["debt_to_equity", "d_e", "debt_equity", "debtequityratio",  # 债务权益比
                         "operating_margin", "operating_profit_rate",  # 营业利润率
                         "current_ratio", "currentratio", "流动比率",  # 流动比率
                         "netprofitratio", "netprofitratiottm",  # 净利率
                         "grossincomeratio", "grossincomeratiottm",  # 毛利率
                         "roe", "roettm", "roa", "roattm", "roic", "roicttm"]  # ROE/ROA/ROIC
            found_fields = {k: fields.get(k) for k in key_fields if k in fields}
            if found_fields:
                print(f"  找到的关键字段: {found_fields}")
            else:
                print(f"  未找到预期的关键字段，请检查字段映射")
        
        # 如果有估值数据，则优先使用 VALUATNANALYD 中的字段
        valuation = latest_valuation or {}
        # 市值：可能的中文字段名或英文变体
        val_market_cap = (valuation.get("totsec_mv") or valuation.get("market_cap") or 
                         valuation.get("market_value") or valuation.get("总市值") or 
                         valuation.get("total_market_value"))
        # PE 比率：可能的中文字段名或英文变体
        val_pe_ttm = (valuation.get("pe_ttm") or valuation.get("pe_ttm_ratio") or 
                     valuation.get("市盈率TTM") or valuation.get("市盈率_ttm"))
        val_pe_lyr = (valuation.get("pe_lyr") or valuation.get("pe_lyr_ratio") or 
                     valuation.get("pe") or valuation.get("市盈率") or 
                     valuation.get("市盈率LYR") or valuation.get("市盈率_lyr"))
        # PB 比率：可能的中文字段名或英文变体
        val_pb = (valuation.get("pb") or valuation.get("pb_ratio") or 
                 valuation.get("市净率") or valuation.get("price_to_book"))
        # PS 比率：可能的中文字段名或英文变体
        val_ps_ttm = (valuation.get("ps_ttm") or valuation.get("ps_ttm_ratio") or 
                     valuation.get("市销率TTM") or valuation.get("市销率_ttm"))
        val_ps = (valuation.get("ps") or valuation.get("ps_ratio") or 
                 valuation.get("市销率") or valuation.get("price_to_sales"))
        # 股息率：可能的中文字段名或英文变体
        val_div_yield = (valuation.get("dividrt_ttm") or valuation.get("dividrt_lyr") or 
                        valuation.get("dividend_yield") or valuation.get("dividend_rate") or
                        valuation.get("股息率") or valuation.get("dividend_yield_ttm") or
                        valuation.get("dividend_yield_lyr"))
        # 企业价值：可能的中文字段名或英文变体
        val_ev = (valuation.get("entpv_wth") or valuation.get("entpv_non") or 
                 valuation.get("enterprise_value") or valuation.get("ev") or
                 valuation.get("企业价值"))

        # 辅助函数：将百分比字段从百分比形式转换为小数形式
        # DeepAlpha API 返回的百分比字段可能是百分比形式（如 15.5 表示 15.5%）
        # 但代码中期望的是小数形式（如 0.155 表示 15.5%）
        def convert_percentage(value):
            """如果值大于 1 或小于 -1，说明是百分比形式，需要除以 100"""
            if value is None:
                return None
            try:
                num_value = float(value)
                # 如果绝对值大于 1，说明是百分比形式，除以 100
                if abs(num_value) > 1.0:
                    return num_value / 100.0
                # 否则已经是小数形式，直接返回
                return num_value
            except (ValueError, TypeError):
                return None

        try:
            # 字段映射：DeepAlpha 的字段名可能和 FinancialMetrics 不完全一致，需要适配
            metric = FinancialMetrics(
                ticker=ticker,
                report_period=str(report_period),
                period=period,
                currency=fields.get("currency") or "CNY",
                # 市值 / 企业价值
                market_cap=val_market_cap or fields.get("market_cap") or fields.get("market_value"),
                enterprise_value=val_ev or fields.get("enterprise_value") or fields.get("ev"),
                # 估值倍数（这些不是百分比，不需要转换）
                price_to_earnings_ratio=val_pe_ttm or val_pe_lyr or fields.get("pe") or fields.get("pe_ratio"),
                price_to_book_ratio=val_pb or fields.get("pb") or fields.get("pb_ratio"),
                price_to_sales_ratio=val_ps_ttm or val_ps or fields.get("ps") or fields.get("ps_ratio"),
                enterprise_value_to_ebitda_ratio=fields.get("ev_ebitda"),
                enterprise_value_to_revenue_ratio=fields.get("ev_revenue"),
                free_cash_flow_yield=convert_percentage(fields.get("fcf_yield") or val_div_yield),
                peg_ratio=fields.get("peg") or valuation.get("peg"),
                # 百分比字段：需要转换为小数形式
                # 根据实际返回的字段名：grossincomeratio, netprofitratio, roe, roa, roic
                gross_margin=convert_percentage(
                    fields.get("gross_margin") or fields.get("gross_profit_rate") or 
                    fields.get("毛利率") or fields.get("grossmargin") or
                    fields.get("grossincomeratio") or fields.get("grossincomeratiottm")  # DeepAlpha 实际字段名
                ),
                operating_margin=convert_percentage(
                    fields.get("operprof_tocl") or  # 港股 HKSTK_FINRPT_DER 实际字段名（营业利润率）
                    fields.get("operating_margin") or fields.get("operating_profit_rate") or 
                    fields.get("营业利润率") or fields.get("operatingmargin") or 
                    fields.get("operating_profit_margin") or
                    fields.get("operating_margin_ttm") or fields.get("operating_profit_margin_ttm") or
                    fields.get("operating_profit_ratio") or fields.get("operating_profit_ratio_ttm")
                    # 注意：DeepAlpha FINANALYSIS_MAIN 可能没有单独的 operating_margin 字段
                    # 港股 HKSTK_FINRPT_DER 使用 operprof_tocl
                ),
                net_margin=convert_percentage(
                    fields.get("net_margin") or fields.get("net_profit_rate") or 
                    fields.get("净利率") or fields.get("netmargin") or 
                    fields.get("net_profit_margin") or
                    fields.get("netprofitratio") or fields.get("netprofitratiottm")  # DeepAlpha 实际字段名
                ),
                return_on_equity=convert_percentage(
                    fields.get("roe") or fields.get("roettm") or fields.get("roeavg") or 
                    fields.get("roeweighted") or  # DeepAlpha A股实际字段名
                    fields.get("roe_ttm") or fields.get("roe_lyr") or  # 港股可能使用的字段名
                    fields.get("return_on_equity") or fields.get("return_on_equity_ttm")
                ),
                return_on_assets=convert_percentage(
                    fields.get("roa") or fields.get("roattm") or fields.get("roa_ebit") or 
                    fields.get("roa_ebitttm")  # DeepAlpha 实际字段名
                ),
                return_on_invested_capital=convert_percentage(
                    fields.get("roic") or fields.get("roicttm")  # DeepAlpha 实际字段名
                ),
                asset_turnover=fields.get("asset_turnover"),
                inventory_turnover=fields.get("inventory_turnover"),
                receivables_turnover=fields.get("receivables_turnover"),
                days_sales_outstanding=fields.get("dso"),
                operating_cycle=fields.get("operating_cycle"),
                working_capital_turnover=fields.get("working_capital_turnover"),
                # 流动比率：可能的中文字段名或英文变体
                # A股 FINANALYSIS_MAIN: currentratio, current_ratio
                # 港股 HKSTK_FINRPT_DER: current_rt
                current_ratio=(
                    fields.get("current_rt") or  # 港股 HKSTK_FINRPT_DER 实际字段名
                    fields.get("current_ratio") or fields.get("currentratio") or 
                    fields.get("流动比率") or fields.get("current_ratio_ttm") or
                    fields.get("current_ratio_lyr") or fields.get("currentratio_ttm")
                ),
                quick_ratio=fields.get("quick_ratio") or fields.get("quickratio") or fields.get("速动比率"),
                cash_ratio=fields.get("cash_ratio") or fields.get("cashratio") or fields.get("现金比率"),
                operating_cash_flow_ratio=fields.get("ocf_ratio") or fields.get("ocfratio") or fields.get("经营现金流比率"),
                # 债务权益比：根据实际返回的字段名
                # A股 FINANALYSIS_MAIN: debtequityratio
                # 港股 HKSTK_FINRPT_DER: debtequ_rt
                debt_to_equity=(
                    fields.get("debtequ_rt") or  # 港股 HKSTK_FINRPT_DER 实际字段名
                    fields.get("debt_to_equity") or fields.get("d_e") or 
                    fields.get("debttoequity") or fields.get("资产负债率") or 
                    fields.get("debt_equity_ratio") or fields.get("debt_equity") or
                    fields.get("debtequityratio") or  # DeepAlpha A股实际字段名
                    fields.get("d_e_ratio") or
                    fields.get("debt_equity_ratio_ttm")
                ),
                debt_to_assets=fields.get("debt_to_assets") or fields.get("d_a") or fields.get("debttoassets") or fields.get("债务资产比") or fields.get("debt_assets_ratio"),
                interest_coverage=fields.get("interest_coverage"),
                # 增长率字段：也是百分比，需要转换
                revenue_growth=convert_percentage(fields.get("revenue_growth")),
                earnings_growth=convert_percentage(fields.get("earnings_growth") or fields.get("net_profit_growth")),
                book_value_growth=convert_percentage(fields.get("book_value_growth")),
                earnings_per_share_growth=convert_percentage(fields.get("eps_growth")),
                free_cash_flow_growth=convert_percentage(fields.get("fcf_growth")),
                operating_income_growth=convert_percentage(fields.get("operating_income_growth")),
                ebitda_growth=convert_percentage(fields.get("ebitda_growth")),
                payout_ratio=convert_percentage(fields.get("payout_ratio") or fields.get("dividend_payout_ratio")),
                earnings_per_share=fields.get("eps") or fields.get("earnings_per_share"),
                book_value_per_share=fields.get("bvps") or fields.get("book_value_per_share"),
                free_cash_flow_per_share=fields.get("fcf_per_share"),
            )
            metrics.append(metric)
        except (ValueError, TypeError) as e:
            # 如果某个字段转换失败，跳过这一期
            continue

    if not metrics:
        return []

    # Sort by report_period descending
    try:
        metrics.sort(key=lambda x: x.report_period, reverse=True)
    except Exception:
        pass

    # Cache the results
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics[:limit]])
    return metrics[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
    massive_api_key: str = None,
    use_openbb: bool = False,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API.
    
    注意：A股/港股暂不支持内幕交易数据，会返回空列表。
    支持多个美股数据源：OpenBB（免费）、Financial Datasets API、Massive API（备用）。
    """
    # A股/港股暂不支持内幕交易数据
    if _looks_like_cn_or_hk_ticker(ticker):
        print(f"Info: Insider trades data not available for A-share/HK stock {ticker}")
        return []
    
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # 美股数据源：优先使用 OpenBB（如果启用且可用）
    if use_openbb:
        try:
            from src.tools.openbb import get_openbb_insider_trades, OPENBB_AVAILABLE
            if OPENBB_AVAILABLE:
                trades = get_openbb_insider_trades(ticker, limit=limit)
                if trades:
                    _cache.set_insider_trades(cache_key, [t.model_dump() for t in trades])
                    return trades
        except ImportError:
            print(f"Warning: OpenBB 未安装，切换到其他数据源")
        except Exception as e:
            print(f"Warning: OpenBB 获取内幕交易数据失败，切换到其他数据源: {str(e)}")

    # If not in cache, fetch from API
    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        try:
            response = _make_api_request_with_fallback(
                url=url,
                api_key=api_key,
                massive_api_key=massive_api_key,
                timeout=30,
                operation="获取内部交易数据",
                ticker=ticker,
            )
        except APIError as e:
            raise
        except Exception as e:
            raise APIError(f"获取内部交易数据失败: {str(e)}", ticker=ticker, recoverable=True)

        data = response.json()
        response_model = InsiderTradeResponse(**data)
        insider_trades = response_model.insider_trades

        if not insider_trades:
            break

        all_trades.extend(insider_trades)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(insider_trades) < limit:
            break

        # Update end_date to the oldest filing date from current batch for next iteration
        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_trades:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
    massive_api_key: str = None,
    use_openbb: bool = False,
) -> list[CompanyNews]:
    """Fetch company news from cache or API.
    
    注意：A股/港股暂不支持新闻数据，会返回空列表。
    支持多个美股数据源：OpenBB（免费）、Financial Datasets API、Massive API（备用）。
    """
    # A股/港股暂不支持新闻数据
    if _looks_like_cn_or_hk_ticker(ticker):
        print(f"Info: Company news data not available for A-share/HK stock {ticker}")
        return []
    
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # 美股数据源：优先使用 OpenBB（如果启用且可用）
    if use_openbb:
        try:
            from src.tools.openbb import get_openbb_company_news, OPENBB_AVAILABLE
            if OPENBB_AVAILABLE:
                news_list = get_openbb_company_news(ticker, limit=limit)
                if news_list:
                    _cache.set_company_news(cache_key, [n.model_dump() for n in news_list])
                    return news_list
        except ImportError:
            print(f"Warning: OpenBB 未安装，切换到其他数据源")
        except Exception as e:
            print(f"Warning: OpenBB 获取公司新闻失败，切换到其他数据源: {str(e)}")

    # If not in cache, fetch from API
    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        try:
            response = _make_api_request_with_fallback(
                url=url,
                api_key=api_key,
                massive_api_key=massive_api_key,
                timeout=30,
                operation="获取公司新闻",
                ticker=ticker,
            )
        except APIError as e:
            raise
        except Exception as e:
            raise APIError(f"获取公司新闻失败: {str(e)}", ticker=ticker, recoverable=True)

        data = response.json()
        response_model = CompanyNewsResponse(**data)
        company_news = response_model.news

        if not company_news:
            break

        all_news.extend(company_news)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(company_news) < limit:
            break

        # Update end_date to the oldest date from current batch for next iteration
        current_end_date = min(news.date for news in company_news).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_news:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
    massive_api_key: str = None,
    use_openbb: bool = False,
) -> float | None:
    """Fetch market cap from the API.
    
    自动识别 A 股/港股代码，使用 DeepAlpha 接口；否则使用美股数据源。
    支持多个美股数据源：OpenBB（免费）、Financial Datasets API、Massive API（备用）。
    """
    # A股/港股直接从财务指标获取市值
    if _looks_like_cn_or_hk_ticker(ticker):
        try:
            financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key, use_openbb=use_openbb)
            if not financial_metrics:
                return None
            market_cap = financial_metrics[0].market_cap
            return market_cap if market_cap else None
        except Exception as e:
            # 如果获取财务指标失败，返回 None 而不是抛出异常
            print(f"Warning: Failed to get market cap for {ticker} via financial metrics: {str(e)}")
            return None
    
    # 美股：优先使用 OpenBB（如果启用且可用）
    if use_openbb:
        try:
            from src.tools.openbb import get_openbb_financial_metrics, OPENBB_AVAILABLE
            if OPENBB_AVAILABLE:
                metrics = get_openbb_financial_metrics(ticker, end_date, limit=1)
                if metrics and metrics[0].market_cap:
                    return metrics[0].market_cap
        except ImportError:
            print(f"Warning: OpenBB 未安装，切换到其他数据源")
        except Exception as e:
            print(f"Warning: OpenBB 获取市值失败，切换到其他数据源: {str(e)}")
    
    # 美股：Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        try:
            response = _make_api_request_with_fallback(
                url=url,
                api_key=api_key,
                massive_api_key=massive_api_key,
                timeout=30,
                operation="获取公司信息",
                ticker=ticker,
            )
            data = response.json()
            response_model = CompanyFactsResponse(**data)
            return response_model.company_facts.market_cap
        except APIError as e:
            print(f"Warning: Failed to get market cap for {ticker} via company facts: {str(e)}")
            return None
        except Exception as e:
            print(f"Warning: Failed to get market cap for {ticker} via company facts: {str(e)}")
            return None

    try:
        financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key, massive_api_key=massive_api_key, use_openbb=use_openbb)
        if not financial_metrics:
            return None

        market_cap = financial_metrics[0].market_cap

        if not market_cap:
            return None

        return market_cap
    except Exception as e:
        print(f"Warning: Failed to get market cap for {ticker} via financial metrics: {str(e)}")
        return None


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
