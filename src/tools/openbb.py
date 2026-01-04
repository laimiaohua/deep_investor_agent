"""
OpenBB 数据源集成模块。

提供使用 OpenBB 获取美股数据的函数，包括：
- 价格数据
- 财务指标
- 财务数据（资产负债表、利润表、现金流量表）
- 公司新闻
- 内幕交易数据

注意：OpenBB 是可选依赖，如果未安装，相关函数会抛出 ImportError。
安装方法：pip install openbb 或 poetry add openbb
"""

from typing import Optional, List
from datetime import datetime
import pandas as pd

# 尝试导入 OpenBB，如果失败则设为 None
try:
    from openbb import obb
    OPENBB_AVAILABLE = True
except ImportError:
    obb = None
    OPENBB_AVAILABLE = False

from src.data.models import (
    Price,
    FinancialMetrics,
    LineItem,
    InsiderTrade,
    CompanyNews,
)


def _check_openbb_available() -> None:
    """检查 OpenBB 是否已安装和配置"""
    if not OPENBB_AVAILABLE:
        raise ImportError(
            "OpenBB 未安装。请运行: pip install openbb 或 poetry add openbb\n"
            "注意：OpenBB 可能与某些依赖存在版本冲突，如果安装失败，"
            "请考虑使用其他数据源（如 Financial Datasets API 或 Massive API）。"
        )


def get_openbb_prices(
    ticker: str,
    start_date: str,
    end_date: str,
) -> List[Price]:
    """
    使用 OpenBB 获取股票价格数据。
    
    Args:
        ticker: 股票代码
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
    
    Returns:
        List[Price]: 价格数据列表
    """
    _check_openbb_available()
    
    try:
        # 使用 OpenBB 获取历史价格数据
        # OpenBB v4+ 使用 obb.equity.price.historical
        result = obb.equity.price.historical(
            symbol=ticker,
            start_date=start_date,
            end_date=end_date,
        )
        
        if result is None or result.to_df().empty:
            return []
        
        df = result.to_df()
        
        # 转换为 Price 对象
        prices = []
        for date, row in df.iterrows():
            # 确保日期格式正确
            if isinstance(date, pd.Timestamp):
                date_str = date.strftime('%Y-%m-%d')
            else:
                date_str = str(date)
            
            price = Price(
                open=float(row.get('open', 0)),
                close=float(row.get('close', 0)),
                high=float(row.get('high', 0)),
                low=float(row.get('low', 0)),
                volume=int(row.get('volume', 0)) if pd.notna(row.get('volume')) else 0,
                time=date_str,
            )
            prices.append(price)
        
        return prices
    except Exception as e:
        raise Exception(f"OpenBB 获取价格数据失败 ({ticker}): {str(e)}")


def get_openbb_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> List[FinancialMetrics]:
    """
    使用 OpenBB 获取财务指标。
    
    注意：OpenBB 的财务指标 API 可能需要不同的参数，这里提供一个基础实现。
    实际使用时可能需要根据 OpenBB 的文档进行调整。
    
    Args:
        ticker: 股票代码
        end_date: 结束日期
        period: 报告期类型 (ttm/quarterly/annual)
        limit: 返回记录数
    
    Returns:
        List[FinancialMetrics]: 财务指标列表
    """
    _check_openbb_available()
    
    try:
        # OpenBB 获取财务指标的方式可能不同
        # 这里提供一个基础实现，可能需要根据实际 API 调整
        metrics_data = obb.equity.fundamental.metrics(
            symbol=ticker,
        )
        
        if metrics_data is None:
            return []
        
        df = metrics_data.to_df()
        
        if df.empty:
            return []
        
        # 转换为 FinancialMetrics 对象
        metrics = []
        # 注意：这里需要根据 OpenBB 实际返回的数据结构进行适配
        # 以下是一个示例实现，可能需要根据实际情况调整字段映射
        
        for _, row in df.iterrows():
            metric = FinancialMetrics(
                ticker=ticker,
                report_period=str(row.get('date', end_date)) if 'date' in row else end_date,
                period=period,
                currency=row.get('currency', 'USD'),
                market_cap=float(row.get('market_cap', 0)) if pd.notna(row.get('market_cap')) else None,
                enterprise_value=float(row.get('enterprise_value', 0)) if pd.notna(row.get('enterprise_value')) else None,
                price_to_earnings_ratio=float(row.get('pe_ratio', 0)) if pd.notna(row.get('pe_ratio')) else None,
                price_to_book_ratio=float(row.get('pb_ratio', 0)) if pd.notna(row.get('pb_ratio')) else None,
                price_to_sales_ratio=float(row.get('ps_ratio', 0)) if pd.notna(row.get('ps_ratio')) else None,
                enterprise_value_to_ebitda_ratio=float(row.get('ev_ebitda', 0)) if pd.notna(row.get('ev_ebitda')) else None,
                enterprise_value_to_revenue_ratio=float(row.get('ev_revenue', 0)) if pd.notna(row.get('ev_revenue')) else None,
                free_cash_flow_yield=float(row.get('fcf_yield', 0)) if pd.notna(row.get('fcf_yield')) else None,
                peg_ratio=float(row.get('peg_ratio', 0)) if pd.notna(row.get('peg_ratio')) else None,
                gross_margin=float(row.get('gross_margin', 0)) if pd.notna(row.get('gross_margin')) else None,
                operating_margin=float(row.get('operating_margin', 0)) if pd.notna(row.get('operating_margin')) else None,
                net_margin=float(row.get('net_margin', 0)) if pd.notna(row.get('net_margin')) else None,
                return_on_equity=float(row.get('roe', 0)) if pd.notna(row.get('roe')) else None,
                return_on_assets=float(row.get('roa', 0)) if pd.notna(row.get('roa')) else None,
                return_on_invested_capital=float(row.get('roic', 0)) if pd.notna(row.get('roic')) else None,
                # 其他字段可以根据需要添加
            )
            metrics.append(metric)
        
        return metrics[:limit]
    except Exception as e:
        # 如果 OpenBB 的财务指标 API 不可用，返回空列表
        print(f"Warning: OpenBB 获取财务指标失败 ({ticker}): {str(e)}")
        return []


def get_openbb_line_items(
    ticker: str,
    line_items: List[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> List[LineItem]:
    """
    使用 OpenBB 获取财务数据项。
    
    注意：OpenBB 的财务报表 API 可能需要不同的参数，这里提供一个基础实现。
    
    Args:
        ticker: 股票代码
        line_items: 要获取的财务项目列表
        end_date: 结束日期
        period: 报告期类型
        limit: 返回记录数
    
    Returns:
        List[LineItem]: 财务数据项列表
    """
    _check_openbb_available()
    
    try:
        # OpenBB 获取财务报表数据
        # 可能需要分别获取资产负债表、利润表、现金流量表
        income_data = obb.equity.fundamental.income(
            symbol=ticker,
        )
        
        balance_data = obb.equity.fundamental.balance(
            symbol=ticker,
        )
        
        cashflow_data = obb.equity.fundamental.cash(
            symbol=ticker,
        )
        
        # 合并数据并转换为 LineItem 对象
        line_items_list = []
        
        # 这里需要根据 OpenBB 实际返回的数据结构进行适配
        # 以下是一个示例实现
        
        if income_data is not None:
            income_df = income_data.to_df()
            if not income_df.empty:
                for date, row in income_df.iterrows():
                    line_item_dict = {
                        "ticker": ticker,
                        "report_period": str(date) if isinstance(date, pd.Timestamp) else str(date),
                        "period": period,
                        "currency": "USD",
                    }
                    # 添加财务项目数据
                    for item in line_items:
                        if item in row:
                            line_item_dict[item] = float(row[item]) if pd.notna(row[item]) else None
                    
                    line_item = LineItem(**line_item_dict)
                    line_items_list.append(line_item)
        
        return line_items_list[:limit]
    except Exception as e:
        print(f"Warning: OpenBB 获取财务数据失败 ({ticker}): {str(e)}")
        return []


def get_openbb_company_news(
    ticker: str,
    limit: int = 10,
) -> List[CompanyNews]:
    """
    使用 OpenBB 获取公司新闻。
    
    Args:
        ticker: 股票代码
        limit: 返回记录数
    
    Returns:
        List[CompanyNews]: 公司新闻列表
    """
    _check_openbb_available()
    
    try:
        news_data = obb.equity.news(
            symbol=ticker,
            limit=limit,
        )
        
        if news_data is None:
            return []
        
        df = news_data.to_df()
        
        if df.empty:
            return []
        
        news_list = []
        for _, row in df.iterrows():
            news = CompanyNews(
                ticker=ticker,
                title=str(row.get('title', '')),
                author=str(row.get('author', '')) if pd.notna(row.get('author')) else '',
                source=str(row.get('source', '')) if pd.notna(row.get('source')) else '',
                date=str(row.get('date', '')) if pd.notna(row.get('date')) else '',
                url=str(row.get('url', '')) if pd.notna(row.get('url')) else '',
                sentiment=None,  # OpenBB 可能不提供情感分析
            )
            news_list.append(news)
        
        return news_list[:limit]
    except Exception as e:
        print(f"Warning: OpenBB 获取公司新闻失败 ({ticker}): {str(e)}")
        return []


def get_openbb_insider_trades(
    ticker: str,
    limit: int = 10,
) -> List[InsiderTrade]:
    """
    使用 OpenBB 获取内幕交易数据。
    
    Args:
        ticker: 股票代码
        limit: 返回记录数
    
    Returns:
        List[InsiderTrade]: 内幕交易列表
    """
    _check_openbb_available()
    
    try:
        insider_data = obb.equity.insider.trading(
            symbol=ticker,
        )
        
        if insider_data is None:
            return []
        
        df = insider_data.to_df()
        
        if df.empty:
            return []
        
        trades = []
        for _, row in df.iterrows():
            trade = InsiderTrade(
                ticker=ticker,
                issuer=str(row.get('issuer', '')) if pd.notna(row.get('issuer')) else None,
                name=str(row.get('name', '')) if pd.notna(row.get('name')) else None,
                title=str(row.get('title', '')) if pd.notna(row.get('title')) else None,
                is_board_director=bool(row.get('is_board_director', False)) if pd.notna(row.get('is_board_director')) else None,
                transaction_date=str(row.get('transaction_date', '')) if pd.notna(row.get('transaction_date')) else None,
                transaction_shares=float(row.get('transaction_shares', 0)) if pd.notna(row.get('transaction_shares')) else None,
                transaction_price_per_share=float(row.get('transaction_price_per_share', 0)) if pd.notna(row.get('transaction_price_per_share')) else None,
                transaction_value=float(row.get('transaction_value', 0)) if pd.notna(row.get('transaction_value')) else None,
                shares_owned_before_transaction=float(row.get('shares_owned_before', 0)) if pd.notna(row.get('shares_owned_before')) else None,
                shares_owned_after_transaction=float(row.get('shares_owned_after', 0)) if pd.notna(row.get('shares_owned_after')) else None,
                security_title=str(row.get('security_title', '')) if pd.notna(row.get('security_title')) else None,
                filing_date=str(row.get('filing_date', '')) if pd.notna(row.get('filing_date')) else '',
            )
            trades.append(trade)
        
        return trades[:limit]
    except Exception as e:
        print(f"Warning: OpenBB 获取内幕交易数据失败 ({ticker}): {str(e)}")
        return []

