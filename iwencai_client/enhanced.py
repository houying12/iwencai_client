"""在原有 ``get()`` 客户端旁新增的可测试 OpenAPI 客户端。"""

from __future__ import annotations

import os
import secrets
import time
from collections.abc import Callable
from typing import Any

import requests

from ._api import IWencaiAPIError
from .errors import ConfigurationError, InvalidResponseError, PaginationLimitError
from .models import QueryResult

DEFAULT_BASE_URL = "https://openapi.iwencai.com"
DEFAULT_API_PATH = "/v1/query2data"
DEFAULT_SKILL_ID = "hithink-astock-selector"
DEFAULT_SKILL_VERSION = "1.0.0"
PER_PAGE_MAX = 100
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class OpenAPIClient:
    """新增的增强客户端；原有 ``IWencaiClient.get()`` 保持不变。"""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        page_size: int = 100,
        max_pages: int = 100,
        retries: int = 3,
        backoff_factor: float = 0.5,
        page_delay: float = 0.3,
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._validate_configuration(
            api_key, base_url, timeout, page_size, max_pages,
            retries, backoff_factor, page_delay,
        )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.page_size = page_size
        self.max_pages = max_pages
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.page_delay = page_delay
        self.session = session or requests.Session()
        self._sleeper = sleeper

    @classmethod
    def from_env(cls, *, dotenv_path: str | None = None, **kwargs: Any) -> "OpenAPIClient":
        """从 ``IWENCAI_*`` 环境变量创建客户端。"""
        if dotenv_path is not None:
            try:
                from dotenv import load_dotenv
            except ImportError as exc:
                raise ConfigurationError(
                    "dotenv_path 需要安装可选依赖 python-dotenv"
                ) from exc
            load_dotenv(dotenv_path, override=False)

        api_key = kwargs.pop("api_key", None) or os.getenv("IWENCAI_API_KEY")
        base_url = kwargs.pop("base_url", None) or os.getenv(
            "IWENCAI_BASE_URL", DEFAULT_BASE_URL
        )
        if not api_key:
            raise ConfigurationError(
                "需要 IWENCAI_API_KEY，请设置环境变量或显式传入 api_key"
            )
        return cls(api_key=api_key, base_url=base_url, **kwargs)

    def query(
        self,
        query: str,
        *,
        page_size: int | None = None,
        max_pages: int | None = None,
        call_type: str = "normal",
    ) -> QueryResult:
        """查询并自动翻页，达到 ``code_count`` 后停止。"""
        page_size = self.page_size if page_size is None else page_size
        max_pages = self.max_pages if max_pages is None else max_pages
        self._validate_query_options(query, page_size, max_pages, call_type)

        rows: list[dict[str, Any]] = []
        raw_pages: list[dict[str, Any]] = []
        total_count: int | None = None
        chunks_info: Any = None

        for page in range(1, max_pages + 1):
            response = self._request_page(query, page, page_size, call_type)
            page_total = self._parse_code_count(response)
            page_rows = response["datas"]
            if total_count is None:
                total_count = page_total
                chunks_info = response.get("chunks_info")
            elif page_total != total_count:
                raise InvalidResponseError(
                    f"分页期间 code_count 发生变化：{total_count} -> {page_total}"
                )

            rows.extend(page_rows)
            raw_pages.append(response)
            if len(rows) >= total_count:
                return QueryResult(
                    query, tuple(rows), total_count, page, True,
                    chunks_info, tuple(raw_pages),
                )
            if not page_rows:
                raise InvalidResponseError("code_count 尚未达到时网关返回了空页")
            if page < max_pages and self.page_delay:
                self._sleeper(self.page_delay)

        partial = QueryResult(
            query, tuple(rows), total_count or 0, max_pages, False,
            chunks_info, tuple(raw_pages),
        )
        raise PaginationLimitError(
            f"达到 max_pages={max_pages}，已获取 {len(rows)}/{total_count} 条",
            partial_result=partial,
        )

    def _request_page(
        self, query: str, page: int, page_size: int, call_type: str
    ) -> dict[str, Any]:
        payload = {
            "query": query, "page": str(page), "limit": str(page_size),
            "is_cache": "1", "expand_index": "true",
        }
        last_error: IWencaiAPIError | None = None
        for attempt in range(1, self.retries + 2):
            trace_id = secrets.token_hex(32)
            headers = self._build_headers(trace_id, "normal" if attempt == 1 else "retry")
            try:
                response = self.session.post(
                    self.base_url + DEFAULT_API_PATH,
                    json=payload, headers=headers, timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = IWencaiAPIError(
                    f"网络错误：{exc}", trace_id=trace_id, retryable=True
                )
                if attempt <= self.retries:
                    self._sleep_before_retry(attempt, None)
                    continue
                raise last_error from exc

            body = self._response_body(response)
            if response.status_code != 200:
                last_error = IWencaiAPIError(
                    f"HTTP {response.status_code}: {response.reason}",
                    status_code=response.status_code, response=body,
                    trace_id=trace_id,
                    retryable=response.status_code in RETRYABLE_STATUS_CODES,
                )
                if last_error.retryable and attempt <= self.retries:
                    self._sleep_before_retry(attempt, response.headers.get("Retry-After"))
                    continue
                raise last_error
            if not isinstance(body, dict):
                raise InvalidResponseError(f"网关响应必须是对象，而不是 {type(body).__name__}")
            self._validate_business_status(body, trace_id)
            if not isinstance(body.get("datas"), list):
                raise InvalidResponseError("网关响应缺少列表类型的 datas 字段")
            return body
        raise last_error or IWencaiAPIError("请求失败")

    def _build_headers(self, trace_id: str, call_type: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Claw-Call-Type": call_type,
            "X-Claw-Skill-Id": DEFAULT_SKILL_ID,
            "X-Claw-Skill-Version": DEFAULT_SKILL_VERSION,
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": trace_id,
        }

    @staticmethod
    def _response_body(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:1000]

    @staticmethod
    def _parse_code_count(response: dict[str, Any]) -> int:
        try:
            count = int(response.get("code_count"))
        except (TypeError, ValueError) as exc:
            raise InvalidResponseError("code_count 必须是整数") from exc
        if count < 0:
            raise InvalidResponseError("code_count 不能为负数")
        return count

    @staticmethod
    def _validate_business_status(response: dict[str, Any], trace_id: str) -> None:
        if "status_code" not in response:
            return
        try:
            status_code = int(response["status_code"])
        except (TypeError, ValueError) as exc:
            raise InvalidResponseError("业务 status_code 必须是整数") from exc
        if status_code != 0:
            raise IWencaiAPIError(
                f"问财业务错误：status_code={status_code}",
                response=response, trace_id=trace_id,
            )

    def _sleep_before_retry(self, attempt: int, retry_after: str | None) -> None:
        try:
            delay = float(retry_after) if retry_after else self.backoff_factor * 2 ** (attempt - 1)
        except (TypeError, ValueError):
            delay = self.backoff_factor * 2 ** (attempt - 1)
        self._sleeper(max(0.0, delay))

    @staticmethod
    def _validate_configuration(
        api_key: str, base_url: str, timeout: float, page_size: int,
        max_pages: int, retries: int, backoff_factor: float, page_delay: float,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ConfigurationError("api_key 不能为空")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise ConfigurationError("base_url 必须以 http:// 或 https:// 开头")
        if timeout <= 0:
            raise ConfigurationError("timeout 必须为正数")
        if not isinstance(page_size, int) or not 1 <= page_size <= PER_PAGE_MAX:
            raise ConfigurationError(f"page_size 必须在 1 到 {PER_PAGE_MAX} 之间")
        if not isinstance(max_pages, int) or max_pages < 1:
            raise ConfigurationError("max_pages 必须为正整数")
        if not isinstance(retries, int) or retries < 0:
            raise ConfigurationError("retries 必须为非负整数")
        if backoff_factor < 0 or page_delay < 0:
            raise ConfigurationError("backoff_factor 和 page_delay 不能为负数")

    @staticmethod
    def _validate_query_options(
        query: str, page_size: int, max_pages: int, call_type: str
    ) -> None:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query 必须是非空字符串")
        if not isinstance(page_size, int) or not 1 <= page_size <= PER_PAGE_MAX:
            raise ValueError(f"page_size 必须在 1 到 {PER_PAGE_MAX} 之间")
        if not isinstance(max_pages, int) or max_pages < 1:
            raise ValueError("max_pages 必须为正整数")
        if call_type not in {"normal", "retry"}:
            raise ValueError("call_type 只能是 normal 或 retry")