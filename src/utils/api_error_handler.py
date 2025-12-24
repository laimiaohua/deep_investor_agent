"""
API 错误处理和容错工具模块

提供通用的 API 错误处理函数，确保单个 API 失败不会中断整个流程。
"""
from typing import Callable, TypeVar, Optional, Any
from src.tools.api import APIError

T = TypeVar('T')


def safe_api_call(
    func: Callable[..., T],
    *args,
    default_value: Optional[T] = None,
    error_message: Optional[str] = None,
    **kwargs
) -> Optional[T]:
    """
    安全地调用 API 函数，捕获异常并返回默认值或 None。
    
    Args:
        func: 要调用的 API 函数
        *args: 位置参数
        default_value: 发生错误时返回的默认值
        error_message: 自定义错误消息前缀
        **kwargs: 关键字参数
    
    Returns:
        函数返回值，或发生错误时的默认值/None
    """
    try:
        return func(*args, **kwargs)
    except APIError as e:
        # APIError 包含详细信息，打印并返回默认值
        error_prefix = error_message or f"调用 {func.__name__} 失败"
        print(f"Warning: {error_prefix}: {str(e)}")
        return default_value
    except Exception as e:
        # 其他异常也捕获
        error_prefix = error_message or f"调用 {func.__name__} 失败"
        print(f"Warning: {error_prefix}: {str(e)}")
        return default_value


def safe_api_call_with_fallback(
    primary_func: Callable[..., T],
    fallback_func: Optional[Callable[..., T]] = None,
    *args,
    default_value: Optional[T] = None,
    **kwargs
) -> Optional[T]:
    """
    安全地调用 API 函数，如果主函数失败，尝试备用函数。
    
    Args:
        primary_func: 主要 API 函数
        fallback_func: 备用 API 函数（可选）
        *args: 位置参数
        default_value: 所有函数都失败时返回的默认值
        **kwargs: 关键字参数
    
    Returns:
        函数返回值，或发生错误时的默认值/None
    """
    # 尝试主函数
    result = safe_api_call(primary_func, *args, default_value=None, **kwargs)
    if result is not None:
        return result
    
    # 如果主函数失败且有备用函数，尝试备用函数
    if fallback_func:
        result = safe_api_call(fallback_func, *args, default_value=None, **kwargs)
        if result is not None:
            return result
    
    # 所有函数都失败，返回默认值
    return default_value

