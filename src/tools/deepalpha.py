"""
DeepAlpha / Gravitech A-share & H-share data client.

本模块封装了对 DeepAlpha 风格接口的访问逻辑，例如：
- https://deepalpha.gravitechinnovations.com/api/data_query?function=BALANCE_SHEET&security_code=600000&apikey=...

设计目标：
- 统一从环境变量中读取 base_url 和 api_key
- 提供一个通用 query 方法
- 提供常用函数：获取资产负债表，并转换为方便后续分析的结构

注意：
- 这里不直接依赖上层智能体逻辑，仅做"数据获取 + 基础整理"
- 和现有的 `src/tools/api.py` 可以并行使用：美股仍用 financialdatasets.ai，A 股/港股用 DeepAlpha
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, Mapping

import pandas as pd
import requests


DEFAULT_DEEPALPHA_BASE_URL = "https://deepalpha.gravitechinnovations.com/api/data_query"


class DeepAlphaConfigError(RuntimeError):
    """Raised when DeepAlpha configuration (base_url / api_key) is missing or invalid."""


@dataclass
class DeepAlphaClient:
    """
    轻量级 DeepAlpha 客户端。

    Attributes:
        base_url: 接口基础地址，例如 http://124.220.26.201:20070/api/data_query
        api_key: 访问密钥
        timeout: 请求超时时间（秒）
    """

    base_url: str
    api_key: str
    timeout: int = 30

    def query(self, function: str, **params: Any) -> Dict[str, Any]:
        """
        调用 DeepAlpha 通用查询接口。

        Args:
            function: 功能名，例如 "BALANCE_SHEET"
            **params: 其他查询参数，例如 security_code="600000"

        Returns:
            解析后的 JSON 字典，一般结构为：
            {
              "code": 200,
              "message": "success",
              "data": {...},
              "timestamp": "..."
            }
        """
        if not self.base_url or not self.api_key:
            raise DeepAlphaConfigError("DeepAlpha base_url or api_key is not configured")

        query_params: Dict[str, Any] = {"function": function, "apikey": self.api_key}
        query_params.update(params)

        try:
            resp = requests.get(self.base_url, params=query_params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            # 网络请求错误
            raise RuntimeError(f"DeepAlpha API request failed: {str(e)}")
        except ValueError as e:
            # JSON 解析错误
            raise RuntimeError(f"DeepAlpha API returned invalid JSON: {str(e)}")

        code = data.get("code")
        if code != 200:
            msg = data.get("message", "Unknown error")
            # 打印详细错误信息用于调试
            print(f"DeepAlpha API error details:")
            print(f"  Function: {function}")
            print(f"  Params: {params}")
            print(f"  Response code: {code}")
            print(f"  Response message: {msg}")
            print(f"  Full response: {data}")
            raise RuntimeError(f"DeepAlpha API error: code={code}, message={msg}")

        return data


def get_deepalpha_client(api_key: str | None = None, base_url: str | None = None) -> DeepAlphaClient:
    """
    从环境变量构造 DeepAlphaClient。

    优先级：
    - 入参 api_key / base_url
    - 环境变量 DEEPALPHA_API_KEY / DEEPALPHA_BASE_URL
    - base_url 默认值 DEFAULT_DEEPALPHA_BASE_URL
    """
    key = api_key or os.environ.get("DEEPALPHA_API_KEY")
    url = base_url or os.environ.get("DEEPALPHA_BASE_URL") or DEFAULT_DEEPALPHA_BASE_URL

    if not key:
        raise DeepAlphaConfigError(
            "Missing DeepAlpha API key. Please set DEEPALPHA_API_KEY in your environment or .env file."
        )

    return DeepAlphaClient(base_url=url, api_key=key)


def _is_hk_stock(symbol: str) -> bool:
    """
    判断是否是港股代码。
    
    港股代码特征：
    - 5位数字，通常以0开头（如00700, 09988）
    - 或者以.HK结尾（如00700.HK）
    
    Args:
        symbol: 股票代码
        
    Returns:
        True if 是港股代码，False otherwise
    """
    s = symbol.upper().strip()
    
    # 如果以.HK结尾，肯定是港股
    if s.endswith(".HK"):
        return True
    
    # 去掉.HK后缀后检查
    base = s.replace(".HK", "")
    
    # 港股通常是5位数字，且以0开头
    if base.isdigit() and len(base) == 5 and base.startswith("0"):
        return True
    
    return False


def _get_function_name(base_function: str, symbol: str) -> str:
    """
    根据股票类型返回正确的function名称。
    
    对于港股，使用HKSTK或HKSHARE开头的function。
    对于A股，使用原始function名称。
    
    Args:
        base_function: 基础function名称，如 "BALANCE_SHEET"
        symbol: 股票代码
        
    Returns:
        正确的function名称（港股默认返回HKSTK格式）
    """
    if _is_hk_stock(symbol):
        # 港股使用HKSTK开头的function（默认）
        return f"HKSTK_{base_function}"
    else:
        # A股使用原始function名称
        return base_function


# 港股function名称映射表
# 根据DeepAlpha文档，所有港股数据接口都使用 HKSTK 或 HKSHARE 前缀
# 这里定义A股function到港股function的映射关系
# 参考文档：https://deepalpha.gravitechinnovations.com/documentation
# 
# 注意：港股接口命名规则：
# - 所有港股接口都以 HKSTK_ 或 HKSHARE_ 开头
# - 如果映射表中没有定义，将使用默认格式：HKSTK_{base_function} 和 HKSHARE_{base_function}
HK_FUNCTION_MAPPING: Dict[str, list[str]] = {
    # 资产负债表：港股接口（仅使用HKSTK系列）
    # - HKSTK_BALANCE_SHEET_GENE: 港股资产负债表（通用版）
    # - HKSTK_BALANCE_BANK: 港股银行资产负债表
    # - HKSTK_BALANCE_INSUR: 港股保险资产负债表
    "BALANCE_SHEET": [
        "HKSTK_BALANCE_SHEET_GENE",
        "HKSTK_BALANCE_BANK",
        "HKSTK_BALANCE_INSUR",
    ],
    # 利润表：港股接口（仅使用HKSTK系列）
    # - HKSTK_INCOME_GENE: 港股利润表（通用版）
    # - HKSTK_INCOME_BANK: 港股银行利润表
    # - HKSTK_INCOME_INSUR: 港股保险利润表
    "INCOME_STATEMENT": [
        "HKSTK_INCOME_GENE",
        "HKSTK_INCOME_BANK",
        "HKSTK_INCOME_INSUR",
    ],
    # 现金流量表：港股接口（仅使用HKSTK系列）
    # - HKSTK_CASHFLOW: 港股现金流量表（通用版）
    "CASH_FLOW": [
        "HKSTK_CASHFLOW",
    ],
    # 日线行情：港股可能使用 MARKET_HISTORICAL_QUOTES 或其他接口
    # 注意：文档中未明确列出港股行情接口，可能需要使用 MARKET_HISTORICAL_QUOTES
    "DAILY_PRICE": [
        "HKSTK_MARKET_DATA",
    ],
    # 财务衍生指标：港股使用 HKSTK_FINRPT_DER
    # 财务比率：港股使用 HKSHARE_FINANCIAL_RATIOS
    "FINANALYSIS_MAIN": [
        "HKSTK_FINRPT_DER",
        "HKSHARE_FINANCIAL_RATIOS",
    ],
    # 估值数据：港股可能没有单独的估值接口
    # 注意：根据文档，港股可能没有 VALUATNANALYD 对应的接口
    # 估值数据可能已经包含在 HKSTK_FINRPT_DER（财务衍生指标）中
    "VALUATNANALYD": [],  # 港股暂不支持，返回空列表表示跳过
}


def _get_hk_function_names(base_function: str) -> list[str]:
    """
    获取港股可能的function名称列表（支持HKSTK和HKSHARE两种格式）。
    
    优先使用映射表中定义的名称，如果没有映射则使用默认的 HKSTK_XXX 和 HKSHARE_XXX 格式。
    
    Args:
        base_function: 基础function名称，如 "BALANCE_SHEET"
        
    Returns:
        function名称列表，按优先级排序
    """
    # 如果映射表中存在，使用映射表中的名称
    if base_function in HK_FUNCTION_MAPPING:
        return HK_FUNCTION_MAPPING[base_function]
    
    # 否则使用默认格式
    return [
        f"HKSTK_{base_function}",
        f"HKSHARE_{base_function}",
    ]


def _query_with_hk_fallback(
    client: DeepAlphaClient,
    base_function: str,
    symbol: str,
    **params: Any
) -> Dict[str, Any]:
    """
    对于港股，尝试使用HKSTK和HKSHARE两种格式调用API。
    先尝试HKSTK格式，如果失败则尝试HKSHARE格式。
    
    Args:
        client: DeepAlphaClient 实例
        base_function: 基础function名称，如 "BALANCE_SHEET"
        symbol: 股票代码
        **params: 其他查询参数
        
    Returns:
        API响应数据
        
    Raises:
        RuntimeError: 如果所有格式都失败
    """
    if _is_hk_stock(symbol):
        # 港股：尝试两种格式
        function_names = _get_hk_function_names(base_function)
        last_error = None
        
        print(f"Debug: 港股 {symbol} 尝试 {base_function} 接口，共 {len(function_names)} 个候选接口: {', '.join(function_names)}")
        
        for function_name in function_names:
            try:
                resp = client.query(function_name, security_code=symbol, **params)
                
                # 检查响应中是否包含错误信息（即使code=200，也可能包含错误）
                # 例如：{"code": 200, "message": "success", "data": {"error": "不支持的功能类型"}}
                if isinstance(resp.get("data"), dict) and "error" in resp.get("data", {}):
                    error_msg = resp["data"].get("error", "Unknown error")
                    error_msg_lower = error_msg.lower()
                    # 检查是否是function不支持的错误
                    is_function_error = (
                        "不支持" in error_msg or
                        "不支持的功能" in error_msg or
                        "invalid" in error_msg_lower or
                        "not found" in error_msg_lower or
                        "unsupported" in error_msg_lower
                    )
                    
                    if is_function_error:
                        last_error = RuntimeError(f"DeepAlpha API returned error: {error_msg}")
                        print(f"Warning: {function_name} failed for {symbol} (error: {error_msg}), trying next format...")
                        continue
                    else:
                        # 其他类型的错误，直接抛出
                        raise RuntimeError(f"DeepAlpha API returned error for {function_name} (symbol={symbol}): {error_msg}")
                
                # 响应正常，返回
                return resp
                
            except RuntimeError as e:
                error_msg = str(e).lower()
                error_msg_full = str(e)
                # 检查是否是function不存在的错误（API返回code!=200的情况）
                # 可能的错误信息包括：Invalid TICKER, Invalid function, function not found等
                is_function_error = (
                    "code=" in error_msg_full or  # API返回了错误码
                    "invalid" in error_msg or  # Invalid function/TICKER
                    "not found" in error_msg or  # Function not found
                    "不存在" in error_msg_full or  # 中文错误信息
                    "不支持" in error_msg_full or  # 中文错误信息：不支持的功能类型
                    "不支持的功能" in error_msg_full or  # 中文错误信息：不支持的功能类型
                    "unsupported" in error_msg  # 英文错误信息
                )
                
                if is_function_error:
                    last_error = e
                    print(f"Warning: {function_name} failed for {symbol} (error: {str(e)[:100]}), trying next format...")
                    continue
                else:
                    # 其他类型的错误（如网络错误、JSON解析错误），直接抛出
                    raise
        
        # 所有格式都失败了
        if last_error:
            print(f"Error: 港股 {symbol} 的所有 {base_function} 接口都失败了。")
            print(f"  尝试的接口列表: {', '.join(function_names)}")
            print(f"  最后一个错误: {str(last_error)}")
            raise RuntimeError(
                f"All HK function formats failed for {symbol} (tried: {', '.join(function_names)}). "
                f"Last error: {str(last_error)}"
            ) from last_error
        else:
            raise RuntimeError(f"All HK function formats failed for {symbol}")
    else:
        # A股：直接使用原始function名称
        return client.query(base_function, security_code=symbol, **params)


def get_balance_sheet_raw(symbol: str, client: DeepAlphaClient | None = None) -> Mapping[str, Dict[str, Any]]:
    """
    获取某个标的的资产负债表原始数据。

    Args:
        symbol: 股票代码，例如 A 股 "600000"、港股 "00700" 或 "00700.HK"
        client: 可选的 DeepAlphaClient 实例；未提供则自动从环境变量创建

    Returns:
        一个 dict[报告期 -> 字段字典]，例如：
        {
          "20250930": { "t_assets": ..., "t_liability": ..., ... },
          "20250630": { ... },
          ...
        }
    """
    client = client or get_deepalpha_client()
    resp = _query_with_hk_fallback(client, "BALANCE_SHEET", symbol)

    # 根据你提供的示例结构：
    # {"code":200,"message":"success","data":{"data":{"data":{"20250930": {...}, ...}},"user_id":...,"api_user_id":...},...}
    try:
        inner_data = resp["data"]["data"]["data"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected BALANCE_SHEET response structure for {symbol}") from exc

    if not isinstance(inner_data, dict):
        raise RuntimeError(f"BALANCE_SHEET 'data.data.data' should be a dict, got {type(inner_data)}")

    # inner_data: Mapping[report_date -> fields]
    return inner_data


def balance_sheet_to_dataframe(balance_sheet: Mapping[str, Dict[str, Any]]) -> pd.DataFrame:
    """
    将资产负债表原始字典转换为 pandas.DataFrame，便于分析。

    - 行索引为报告期（按时间排序）
    - 列为各个科目字段
    """
    if not balance_sheet:
        return pd.DataFrame()

    rows = []
    for report_date, fields in balance_sheet.items():
        if not isinstance(fields, dict):
            continue
        row = dict(fields)
        row["report_period"] = report_date
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 把报告期转成真正的日期索引（如果格式允许）
    if "report_period" in df.columns:
        try:
            df["report_period"] = pd.to_datetime(df["report_period"], format="%Y%m%d", errors="coerce")
            df = df.set_index("report_period").sort_index()
        except Exception:
            # 如果解析失败，就保持 report_period 作为普通列
            df = df.sort_values("report_period")

    return df


def get_balance_sheet_df(symbol: str, client: DeepAlphaClient | None = None) -> pd.DataFrame:
    """
    便捷函数：直接返回某个标的的资产负债表 DataFrame。

    示例用法：

    >>> from src.tools.deepalpha import get_balance_sheet_df
    >>> df = get_balance_sheet_df("600000")
    >>> print(df[["t_assets", "t_liability", "t_equity"]].tail())
    """
    raw = get_balance_sheet_raw(symbol, client=client)
    return balance_sheet_to_dataframe(raw)


def get_income_statement_raw(symbol: str, client: DeepAlphaClient | None = None) -> Mapping[str, Dict[str, Any]]:
    """
    获取某个标的的利润表原始数据。

    Args:
        symbol: 股票代码，例如 A 股 "600000"、港股 "00700" 或 "00700.HK"
        client: 可选的 DeepAlphaClient 实例

    Returns:
        dict[报告期 -> 字段字典]，包含收入、成本、利润等科目
    """
    client = client or get_deepalpha_client()
    resp = _query_with_hk_fallback(client, "INCOME_STATEMENT", symbol)

    try:
        inner_data = resp["data"]["data"]["data"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected INCOME_STATEMENT response structure for {symbol}") from exc

    if not isinstance(inner_data, dict):
        raise RuntimeError(f"INCOME_STATEMENT 'data.data.data' should be a dict, got {type(inner_data)}")

    return inner_data


def get_cash_flow_raw(symbol: str, client: DeepAlphaClient | None = None) -> Mapping[str, Dict[str, Any]]:
    """
    获取某个标的的现金流量表原始数据。

    Args:
        symbol: 股票代码，例如 A 股 "600000"、港股 "00700" 或 "00700.HK"
        client: 可选的 DeepAlphaClient 实例

    Returns:
        dict[报告期 -> 字段字典]，包含经营、投资、筹资活动现金流等科目
    """
    client = client or get_deepalpha_client()
    resp = _query_with_hk_fallback(client, "CASH_FLOW", symbol)

    try:
        inner_data = resp["data"]["data"]["data"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected CASH_FLOW response structure for {symbol}") from exc

    if not isinstance(inner_data, dict):
        raise RuntimeError(f"CASH_FLOW 'data.data.data' should be a dict, got {type(inner_data)}")

    return inner_data


def get_daily_price_raw(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    client: DeepAlphaClient | None = None,
) -> list[Dict[str, Any]]:
    """
    获取某个标的的日线行情数据。

    Args:
        symbol: 股票代码，例如 A 股 "600000"、港股 "00700" 或 "00700.HK"
        start_date: 开始日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"
        end_date: 结束日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"
        client: 可选的 DeepAlphaClient 实例

    Returns:
        list[dict]，每个 dict 包含 open, close, high, low, volume, time 等字段
    """
    client = client or get_deepalpha_client()
    params: Dict[str, Any] = {}
    if start_date:
        params["start_date"] = start_date.replace("-", "")
    if end_date:
        params["end_date"] = end_date.replace("-", "")

    resp = _query_with_hk_fallback(client, "DAILY_PRICE", symbol, **params)

    try:
        # 根据 DeepAlpha 文档，行情数据可能在 data.data.data 或 data.data 中
        inner_data = resp.get("data", {}).get("data", {}).get("data") or resp.get("data", {}).get("data")
    except (KeyError, TypeError):
        inner_data = None

    if inner_data is None:
        return []

    # 如果是字典格式（按日期索引），转换为列表
    if isinstance(inner_data, dict):
        return list(inner_data.values())
    elif isinstance(inner_data, list):
        return inner_data
    else:
        return []


def get_financial_indicators_raw(symbol: str, client: DeepAlphaClient | None = None) -> Mapping[str, Dict[str, Any]]:
    """
    获取某个标的的财务指标原始数据（如 PE、PB、ROE 等）。

    Args:
        symbol: 股票代码，例如 A 股 "600000"、港股 "00700" 或 "00700.HK"
        client: 可选的 DeepAlphaClient 实例

    Returns:
        dict[报告期 -> 指标字典]
        
    注意：
    - A股接口（FINANALYSIS_MAIN）返回 dict[报告期 -> 指标字典]
    - 港股接口（HKSTK_FINRPT_DER）返回 list[指标字典]，需要转换为 dict 格式
    """
    client = client or get_deepalpha_client()
    is_hk = _is_hk_stock(symbol)
    
    try:
        resp = _query_with_hk_fallback(client, "FINANALYSIS_MAIN", symbol)
    except Exception as e:
        # 打印详细错误信息
        function_name = _get_function_name("FINANALYSIS_MAIN", symbol)
        print(f"ERROR: DeepAlpha query failed for {function_name}, symbol={symbol}")
        print(f"  Error: {str(e)}")
        raise

    # 检查 API 是否返回错误
    if isinstance(resp.get("data"), dict) and "error" in resp.get("data", {}):
        error_msg = resp["data"].get("error", "Unknown error")
        function_name = _get_function_name("FINANALYSIS_MAIN", symbol)
        raise RuntimeError(f"DeepAlpha API returned error for {function_name} (symbol={symbol}): {error_msg}")

    try:
        inner_data = resp["data"]["data"]["data"]
    except (KeyError, TypeError) as exc:
        # 打印响应结构用于调试
        function_name = _get_function_name("FINANALYSIS_MAIN", symbol)
        print(f"ERROR: Unexpected {function_name} response structure for {symbol}")
        print(f"  Response keys: {list(resp.keys()) if isinstance(resp, dict) else 'Not a dict'}")
        if isinstance(resp, dict) and "data" in resp:
            print(f"  Response['data'] keys: {list(resp['data'].keys()) if isinstance(resp['data'], dict) else 'Not a dict'}")
            if isinstance(resp["data"], dict) and "data" in resp["data"]:
                print(f"  Response['data']['data'] type: {type(resp['data']['data'])}")
        raise RuntimeError(f"Unexpected {function_name} response structure for {symbol}. Full response: {resp}") from exc

    # 港股接口（HKSTK_FINRPT_DER）返回 list 格式，需要转换为 dict
    if isinstance(inner_data, list):
        if not inner_data:
            return {}
        
        # 将 list 转换为 dict，使用报告期作为 key
        # 港股数据可能使用不同的字段名作为报告期，常见的有：report_date, report_period, end_date, trade_date 等
        result_dict: Dict[str, Dict[str, Any]] = {}
        for item in inner_data:
            if not isinstance(item, dict):
                continue
            
            # 尝试找到报告期字段
            report_period = None
            for key in ["report_period", "report_date", "end_date", "trade_date", "period_end_date"]:
                if key in item and item[key]:
                    report_period = str(item[key])
                    break
            
            # 如果没有找到报告期字段，使用索引作为key
            if not report_period:
                report_period = str(len(result_dict))
            
            # 如果报告期已存在，合并数据（保留最新的）
            if report_period in result_dict:
                # 合并字段，新数据覆盖旧数据
                result_dict[report_period].update(item)
            else:
                result_dict[report_period] = item
        
        return result_dict
    
    # A股接口返回 dict 格式
    if isinstance(inner_data, dict):
        return inner_data
    
    # 其他类型，抛出错误
    raise RuntimeError(
        f"FINANALYSIS_MAIN 'data.data.data' should be a dict or list, got {type(inner_data)}. "
        f"Symbol: {symbol}, Is HK: {is_hk}"
    )


def get_valuation_main_raw(symbol: str, client: DeepAlphaClient | None = None) -> list[Dict[str, Any]]:
    """
    使用 VALUATNANALYD 获取估值数据列表（按交易日降序）。
    
    注意：港股可能没有单独的估值接口，估值数据可能已包含在财务衍生指标中。
    如果港股没有对应的接口，将返回空列表。
    
    Args:
        symbol: 股票代码，例如 A 股 "600000"、港股 "00700" 或 "00700.HK"
        client: 可选的 DeepAlphaClient 实例
        
    Returns:
        估值数据列表，港股如果没有对应接口则返回空列表
    """
    client = client or get_deepalpha_client()
    
    # 检查港股是否有对应的估值接口
    if _is_hk_stock(symbol):
        hk_functions = _get_hk_function_names("VALUATNANALYD")
        # 如果映射表返回空列表，说明港股不支持此接口
        if not hk_functions:
            print(f"Info: 港股 {symbol} 暂不支持 VALUATNANALYD 估值接口，估值数据可能已包含在财务衍生指标中")
            return []
    
    try:
        resp = _query_with_hk_fallback(client, "VALUATNANALYD", symbol)
    except RuntimeError as e:
        # 如果是港股且所有格式都失败，说明港股不支持此接口
        if _is_hk_stock(symbol):
            print(f"Info: 港股 {symbol} 不支持 VALUATNANALYD 估值接口，估值数据可能已包含在财务衍生指标中")
            return []
        # A股失败则抛出异常
        raise

    inner = resp.get("data", {}).get("data", {}).get("data", [])
    if not isinstance(inner, list):
        return []

    # 按 trade_date 从大到小排序，最新的在前面
    return sorted(inner, key=lambda x: x.get("trade_date", 0), reverse=True)


def get_latest_valuation(symbol: str, client: DeepAlphaClient | None = None) -> Dict[str, Any] | None:
    """
    获取最新一条估值数据。
    """
    rows = get_valuation_main_raw(symbol, client=client)
    return rows[0] if rows else None


def _generic_statement_to_dataframe(statement: Mapping[str, Dict[str, Any]]) -> pd.DataFrame:
    """
    通用函数：将任意财务报表（资产负债表、利润表、现金流量表）转换为 DataFrame。
    """
    if not statement:
        return pd.DataFrame()

    rows = []
    for report_date, fields in statement.items():
        if not isinstance(fields, dict):
            continue
        row = dict(fields)
        row["report_period"] = report_date
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "report_period" in df.columns:
        try:
            df["report_period"] = pd.to_datetime(df["report_period"], format="%Y%m%d", errors="coerce")
            df = df.set_index("report_period").sort_index()
        except Exception:
            df = df.sort_values("report_period")

    return df


def get_income_statement_df(symbol: str, client: DeepAlphaClient | None = None) -> pd.DataFrame:
    """便捷函数：直接返回利润表 DataFrame。"""
    raw = get_income_statement_raw(symbol, client=client)
    return _generic_statement_to_dataframe(raw)


def get_cash_flow_df(symbol: str, client: DeepAlphaClient | None = None) -> pd.DataFrame:
    """便捷函数：直接返回现金流量表 DataFrame。"""
    raw = get_cash_flow_raw(symbol, client=client)
    return _generic_statement_to_dataframe(raw)



