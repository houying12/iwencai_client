"""增强 OpenAPI 客户端使用的异常类型。"""

from typing import Any


class IWencaiError(Exception):
    """增强客户端异常基类。"""


class ConfigurationError(IWencaiError):
    """客户端配置缺失或无效。"""


class InvalidResponseError(IWencaiError):
    """网关响应不符合预期结构。"""


class PaginationLimitError(IWencaiError):
    """达到最大页数但结果仍未获取完整。"""

    def __init__(self, message: str, *, partial_result: Any) -> None:
        super().__init__(message)
        self.partial_result = partial_result