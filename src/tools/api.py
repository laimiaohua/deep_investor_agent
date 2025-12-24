import datetime
import os
import pandas as pd
import requests
import time
from typing import Optional
from requests.exceptions import RequestException, Timeout, ConnectionError as RequestsConnectionError

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
)

# Global cache instance
_cache = get_cache()


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


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None, cn_api_key: str = None) -> list[Price]:
    """
    Fetch price data from cache or API.
    
    自动识别 A 股/港股代码，优先使用 DeepAlpha 接口；否则使用美股数据源。
    
    Args:
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        api_key: 用于美股数据的 API key (FINANCIAL_DATASETS_API_KEY)
        cn_api_key: 用于 A 股/港股数据的 API key (DEEPALPHA_API_KEY)
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
                print(f"Warning: DeepAlpha returned no price data for {ticker} ({start_date} to {end_date}). "
                      f"Please check if the ticker is valid and the date range is correct.")
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
            # 其他错误
            else:
                raise Exception(
                    f"无法获取 A 股数据 {ticker}: DeepAlpha API 调用失败。"
                    f"错误类型: {error_type}, 错误详情: {error_msg}"
                )

    # Fallback to US data source (original logic)
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    try:
        response = _make_api_request(url, headers, timeout=30)
        _handle_api_response(response, ticker, "获取价格数据")
    except APIError as e:
        raise
    except Exception as e:
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
) -> list[FinancialMetrics]:
    """
    Fetch financial metrics from cache or API.
    
    自动识别 A 股/港股代码，优先使用 DeepAlpha 接口；否则使用美股数据源。
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        period: 财报周期
        limit: 返回记录数
        api_key: 用于美股数据的 API key (FINANCIAL_DATASETS_API_KEY)
        cn_api_key: 用于 A 股/港股数据的 API key (DEEPALPHA_API_KEY)
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
        except Exception as e:
            # 区分不同类型的错误
            error_type = type(e).__name__
            error_msg = str(e)
            
            # 打印详细错误信息到控制台（用于调试）
            print(f"ERROR: Failed to get financial metrics for {ticker}")
            print(f"  Error type: {error_type}")
            print(f"  Error message: {error_msg}")
            print(f"  cn_api_key provided: {'Yes' if cn_api_key else 'No'}")
            
            # 如果是配置错误（API key 缺失），给出明确提示
            if "DeepAlphaConfigError" in error_type or "Missing DeepAlpha API key" in error_msg:
                raise Exception(
                    f"无法获取 A 股财务指标 {ticker}: DeepAlpha API key 未配置。"
                    f"请在设置界面配置 DEEPALPHA_API_KEY，或在 .env 文件中设置，或通过参数传入 api_key。"
                    f"错误详情: {error_msg}"
                )
            # 如果是网络或API错误，给出详细错误信息
            elif "requests" in error_msg.lower() or "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                raise Exception(
                    f"无法获取 A 股财务指标 {ticker}: DeepAlpha API 网络请求失败。"
                    f"请检查网络连接和 API 服务状态。错误详情: {error_msg}"
                )
            # 其他错误
            else:
                raise Exception(
                    f"无法获取 A 股财务指标 {ticker}: DeepAlpha API 调用失败。"
                    f"错误类型: {error_type}, 错误详情: {error_msg}"
                )

    # Fallback to US data source (original logic)
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    try:
        response = _make_api_request(url, headers, timeout=30)
        _handle_api_response(response, ticker, "获取财务指标")
    except APIError as e:
        # Re-raise APIError as-is
        raise
    except Exception as e:
        # Wrap other exceptions
        raise APIError(f"获取财务指标失败: {str(e)}", ticker=ticker, recoverable=True)

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
) -> list[LineItem]:
    """
    Fetch line items from API.

    自动识别 A 股/港股代码，优先使用 DeepAlpha 接口获取财务数据；否则使用美股数据源。
    """
    # 如果是 A 股/港股代码，优先使用 DeepAlpha
    if _looks_like_cn_or_hk_ticker(ticker):
        try:
            cn_line_items = get_cn_all_line_items(ticker, api_key=api_key)
            if cn_line_items:
                return cn_line_items[:limit]
            else:
                # 如果返回空列表，可能是数据不存在
                print(f"Warning: DeepAlpha returned no line items for {ticker}. "
                      f"Please check if the ticker is valid.")
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
            # 其他错误
            else:
                raise Exception(
                    f"无法获取 A 股财务数据 {ticker}: DeepAlpha API 调用失败。"
                    f"错误类型: {error_type}, 错误详情: {error_msg}"
                )

    # Fallback to US data source (original logic)
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    try:
        response = _make_api_request(url, headers, method="POST", json_data=body, timeout=30)
        _handle_api_response(response, ticker, "获取财务项目")
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
    client = get_deepalpha_client(api_key=api_key)
    raw = get_balance_sheet_raw(symbol=ticker, client=client)

    line_items: list[LineItem] = []
    for report_period, fields in raw.items():
        if not isinstance(fields, dict):
            continue

        # DeepAlpha 返回的数据里已经包含了很多字段，我们全部打平放入 LineItem
        item_data: dict[str, any] = {
            "ticker": ticker,
            "report_period": str(report_period),
            "period": "annual",
            "currency": fields.get("currency", "CNY"),
        }
        # 其余字段原样附加，LineItem.extra = "allow" 可以接受
        item_data.update(fields)

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

        item_data: dict[str, any] = {
            "ticker": ticker,
            "report_period": str(report_period),
            "period": "annual",
            "currency": fields.get("currency", "CNY"),
        }
        item_data.update(fields)

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

        item_data: dict[str, any] = {
            "ticker": ticker,
            "report_period": str(report_period),
            "period": "annual",
            "currency": fields.get("currency", "CNY"),
        }
        item_data.update(fields)

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
        # 重新抛出 API 调用错误，让上层处理
        raise Exception(
            f"DeepAlpha API 调用失败 (ticker: {ticker}, function: FINANALYSIS_MAIN): {str(e)}"
        )

    if not raw_indicators:
        print(f"Info: DeepAlpha returned no financial indicators for {ticker}")
        return []

    # 额外获取最新估值数据（VALUATNANALYD）
    latest_valuation: dict | None = None
    try:
        latest_valuation = get_latest_valuation(ticker, client=client)
    except Exception as e:
        print(f"Warning: 获取 VALUATNANALYD 估值数据失败 ({ticker}): {e}")

    # Convert to FinancialMetrics objects
    metrics: list[FinancialMetrics] = []
    for report_period, fields in raw_indicators.items():
        if not isinstance(fields, dict):
            continue
        
        # 如果有估值数据，则优先使用 VALUATNANALYD 中的字段
        valuation = latest_valuation or {}
        val_market_cap = valuation.get("totsec_mv")
        val_pe_ttm = valuation.get("pe_ttm")
        val_pe_lyr = valuation.get("pe_lyr")
        val_pb = valuation.get("pb")
        val_ps_ttm = valuation.get("ps_ttm")
        val_ps = valuation.get("ps")
        val_div_yield = valuation.get("dividrt_ttm") or valuation.get("dividrt_lyr")
        val_ev = valuation.get("entpv_wth") or valuation.get("entpv_non")

        try:
            # 字段映射：DeepAlpha 的字段名可能和 FinancialMetrics 不完全一致，需要适配
            metric = FinancialMetrics(
                ticker=ticker,
                report_period=str(report_period),
                period=period,
                currency=fields.get("currency", "CNY"),
                # 市值 / 企业价值
                market_cap=val_market_cap or fields.get("market_cap") or fields.get("market_value"),
                enterprise_value=val_ev or fields.get("enterprise_value") or fields.get("ev"),
                # 估值倍数
                price_to_earnings_ratio=val_pe_ttm or val_pe_lyr or fields.get("pe") or fields.get("pe_ratio"),
                price_to_book_ratio=val_pb or fields.get("pb") or fields.get("pb_ratio"),
                price_to_sales_ratio=val_ps_ttm or val_ps or fields.get("ps") or fields.get("ps_ratio"),
                enterprise_value_to_ebitda_ratio=fields.get("ev_ebitda"),
                enterprise_value_to_revenue_ratio=fields.get("ev_revenue"),
                free_cash_flow_yield=fields.get("fcf_yield") or val_div_yield,
                peg_ratio=fields.get("peg") or valuation.get("peg"),
                gross_margin=fields.get("gross_margin") or fields.get("gross_profit_rate"),
                operating_margin=fields.get("operating_margin") or fields.get("operating_profit_rate"),
                net_margin=fields.get("net_margin") or fields.get("net_profit_rate"),
                return_on_equity=fields.get("roe"),
                return_on_assets=fields.get("roa"),
                return_on_invested_capital=fields.get("roic"),
                asset_turnover=fields.get("asset_turnover"),
                inventory_turnover=fields.get("inventory_turnover"),
                receivables_turnover=fields.get("receivables_turnover"),
                days_sales_outstanding=fields.get("dso"),
                operating_cycle=fields.get("operating_cycle"),
                working_capital_turnover=fields.get("working_capital_turnover"),
                current_ratio=fields.get("current_ratio"),
                quick_ratio=fields.get("quick_ratio"),
                cash_ratio=fields.get("cash_ratio"),
                operating_cash_flow_ratio=fields.get("ocf_ratio"),
                debt_to_equity=fields.get("debt_to_equity") or fields.get("d_e"),
                debt_to_assets=fields.get("debt_to_assets") or fields.get("d_a"),
                interest_coverage=fields.get("interest_coverage"),
                revenue_growth=fields.get("revenue_growth"),
                earnings_growth=fields.get("earnings_growth") or fields.get("net_profit_growth"),
                book_value_growth=fields.get("book_value_growth"),
                earnings_per_share_growth=fields.get("eps_growth"),
                free_cash_flow_growth=fields.get("fcf_growth"),
                operating_income_growth=fields.get("operating_income_growth"),
                ebitda_growth=fields.get("ebitda_growth"),
                payout_ratio=fields.get("payout_ratio") or fields.get("dividend_payout_ratio"),
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
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API.
    
    注意：A股/港股暂不支持内幕交易数据，会返回空列表。
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

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        try:
            _handle_api_response(response, ticker, "获取内部交易数据")
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
) -> list[CompanyNews]:
    """Fetch company news from cache or API.
    
    注意：A股/港股暂不支持新闻数据，会返回空列表。
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

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        try:
            _handle_api_response(response, ticker, "获取公司新闻")
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
) -> float | None:
    """Fetch market cap from the API.
    
    自动识别 A 股/港股代码，使用 DeepAlpha 接口；否则使用美股数据源。
    """
    # A股/港股直接从财务指标获取市值
    if _looks_like_cn_or_hk_ticker(ticker):
        try:
            financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
            if not financial_metrics:
                return None
            market_cap = financial_metrics[0].market_cap
            return market_cap if market_cap else None
        except Exception as e:
            # 如果获取财务指标失败，返回 None 而不是抛出异常
            print(f"Warning: Failed to get market cap for {ticker} via financial metrics: {str(e)}")
            return None
    
    # 美股：Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        try:
            response = _make_api_request(url, headers, timeout=30)
            _handle_api_response(response, ticker, "获取公司信息")
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
        financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
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
