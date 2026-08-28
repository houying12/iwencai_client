# -*- coding: utf-8 -*-
"""底层 HTTP 请求层: 请求头构造 / 单页请求 / 失败重试 / 自动翻页。
不依赖任何业务逻辑, 纯 API 通讯。
"""
import json
import logging
import secrets
import time

import requests

logger = logging.getLogger(__name__)

SKILL_ID = "hithink-astock-selector"
SKILL_VERSION = "1.0.0"
DEFAULT_API_PATH = "/v1/query2data"

# 这些 HTTP 状态码需要重试(瞬时错误/限流), 其余直接抛错
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class IWencaiAPIError(Exception):
    """问财网关/网络错误。

    Attributes:
        message: 错误描述
        status_code: HTTP 状态码(网络错误时为 None)
        response: 网关原始响应(JSON dict 或文本)
    """

    def __init__(self, message: str, status_code: int = None, response=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


def build_headers(api_key: str, call_type: str = "normal") -> dict:
    """构造问财网关要求的 8 个 X-Claw-* 请求头。"""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": SKILL_ID,
        "X-Claw-Skill-Version": SKILL_VERSION,
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),  # 64位唯一ID, 每次请求重新生成
    }


def fetch_page(api_key: str, query: str, page: int, perpage: int,
               base_url: str, timeout: int, call_type: str = "normal") -> dict:
    """请求单页数据, 返回网关 JSON。"""
    url = base_url.rstrip("/") + DEFAULT_API_PATH
    payload = {
        "query": query,
        "page": str(page),
        "limit": str(perpage),
        "is_cache": "1",
        "expand_index": "true",
    }
    try:
        resp = requests.post(
            url, json=payload, headers=build_headers(api_key, call_type), timeout=timeout
        )
    except requests.RequestException as e:
        raise IWencaiAPIError(f"网络错误: {e}") from e

    if resp.status_code != 200:
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        raise IWencaiAPIError(
            f"HTTP {resp.status_code}: {resp.reason}",
            status_code=resp.status_code,
            response=body,
        )

    try:
        return resp.json()
    except ValueError as e:
        raise IWencaiAPIError("网关响应不是合法 JSON", response=resp.text[:500]) from e


def _request_with_retry(api_key: str, query: str, page: int, perpage: int,
                        base_url: str, timeout: int, retries: int,
                        call_type: str = "normal") -> dict:
    """带指数退避重试的单页请求。"""
    last_err: IWencaiAPIError = None
    for attempt in range(1, retries + 1):
        try:
            return fetch_page(api_key, query, page, perpage, base_url, timeout, call_type)
        except IWencaiAPIError as e:
            last_err = e
            if attempt < retries and e.status_code in RETRYABLE_STATUS:
                wait = 0.5 * (2 ** (attempt - 1))  # 0.5s, 1s, 2s
                logger.warning(
                    "请求失败(%s), %.1fs 后重试(%d/%d): %s",
                    e.status_code or "网络错误", wait, attempt, retries, e.message,
                )
                time.sleep(wait)
            else:
                raise
    raise last_err  # pragma: no cover


def fetch_all(api_key: str, query: str, perpage: int, base_url: str,
              max_pages: int, timeout: int, retries: int, sleep: float = 0.3):
    """自动翻页拉全量, 返回 (rows, code_count)。

    停止条件(三重保险): 网关无 datas / 当前页为空 / page*perpage >= code_count。
    """
    all_rows, page, code_count = [], 1, 0
    while page <= max_pages:
        data = _request_with_retry(api_key, query, page, perpage, base_url, timeout, retries)
        rows = data.get("datas")
        if rows is None:
            logger.info("网关未返回 datas, 提前停止: %s", json.dumps(data, ensure_ascii=False)[:300])
            break
        code_count = int(data.get("code_count", 0) or 0)
        all_rows.extend(rows)
        logger.info("第%d页 获取%d条, 累计%d条, 总命中%d", page, len(rows), len(all_rows), code_count)
        if not rows or page * perpage >= code_count:
            break
        page += 1
        time.sleep(sleep)
    return all_rows, code_count
