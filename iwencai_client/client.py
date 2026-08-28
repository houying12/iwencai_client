# -*- coding: utf-8 -*-
"""IWencaiClient 主类: 对外唯一入口 get()。

设计约定(经用户确认):
- get() 始终全量拉取(自动翻页)后, 再做本地排序
- api_key 作为 get() 的必填参数显式传入
- 返回类型固定为 pandas.DataFrame
- page 参数保留在签名中(兼容接口设计); 当前实现为全量拉取, page 未启用
"""
import logging
from typing import Optional

import pandas as pd

from ._api import fetch_all, IWencaiAPIError
from ._utils import records_to_dataframe

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openapi.iwencai.com"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_PAGES = 10
DEFAULT_RETRIES = 3
DEFAULT_SLEEP = 0.3
PERPAGE_MAX = 100   # 问财单页上限


class IWencaiClient:
    """问财(iWencai) A股选股客户端。

    用法:
        from iwencai_client import IWencaiClient

        client = IWencaiClient()          # 连接级配置在实例化时设置
        df = client.get(
            query="今日涨停，所属申万行业，非ST",
            api_key="sk-proj-xxxx",        # 必填
            sort_key="涨跌幅%",             # 可选: 返回结果列名
            sort_order="desc",             # 可选: asc/desc
        )
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT,
                 max_pages: int = DEFAULT_MAX_PAGES, retries: int = DEFAULT_RETRIES,
                 sleep: float = DEFAULT_SLEEP):
        """
        Args:
            base_url: 网关地址, 默认 https://openapi.iwencai.com
            timeout: 单次请求超时秒数
            max_pages: 最大翻页数(保护, 防止异常死循环)
            retries: 瞬时错误重试次数
            sleep: 翻页间隔秒数(节流, 避免触发限流)
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_pages = max_pages
        self.retries = retries
        self.sleep = sleep

    def get(self, query: str, api_key: str, sort_key: Optional[str] = None,
            sort_order: str = "asc", page: int = 1, perpage: int = 100) -> pd.DataFrame:
        """执行选股查询: 全量拉取 -> 清洗 -> 排序, 返回 DataFrame。

        Args:
            query: 必填, 自然语言查询问句(如 "今日涨停，所属申万行业，非ST")
            api_key: 必填, 问财 API Key(用于 Authorization: Bearer)
            sort_key: 可选, 排序字段, 值为返回结果的列名(如 "涨跌幅%")
            sort_order: 可选, "asc" 升序 / "desc" 降序, 默认 "asc"
            page: 可选, 查询页数, 默认 1(保留参数; 当前实现为全量拉取, 未启用)
            perpage: 可选, 每页条数, 默认 100; 问财上限 100, 超过自动钳制为 100

        Returns:
            清洗后的 pandas.DataFrame(全量结果, 已按 sort_key/sort_order 排序)

        Raises:
            ValueError: 参数不合法
            KeyError: sort_key 不是返回结果的列名(会附带可用列清单)
            IWencaiAPIError: 网关/网络错误
        """
        perpage = self._validate(query, api_key, sort_order, page, perpage)

        rows, code_count = fetch_all(
            api_key=api_key,
            query=query,
            perpage=perpage,
            base_url=self.base_url,
            max_pages=self.max_pages,
            timeout=self.timeout,
            retries=self.retries,
            sleep=self.sleep,
        )
        df = records_to_dataframe(rows)
        logger.info("命中%d只, 实际获取%d条", code_count, len(df))

        if df.empty:
            logger.warning("未获取到数据(query=%s), 请检查查询条件或放宽后重试", query)
            return df

        if sort_key is not None:
            if sort_key not in df.columns:
                raise KeyError(
                    f"sort_key '{sort_key}' 不是返回结果的列名。可用列: {list(df.columns)}"
                )
            df = df.sort_values(by=sort_key, ascending=(sort_order == "asc")).reset_index(drop=True)
        return df

    @staticmethod
    def _validate(query: str, api_key: str, sort_order: str, page: int, perpage: int) -> int:
        """参数校验, 返回钳制后的 perpage。"""
        if not query or not isinstance(query, str):
            raise ValueError("query 必填, 且必须是非空字符串")
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key 必填")
        if sort_order not in ("asc", "desc"):
            raise ValueError("sort_order 只能为 'asc'(升序) 或 'desc'(降序)")
        if not isinstance(page, int) or page < 1:
            raise ValueError("page 必须为正整数")
        if not isinstance(perpage, int) or perpage < 1:
            raise ValueError("perpage 必须为正整数")
        if perpage > PERPAGE_MAX:
            logger.warning("perpage=%d 超过问财上限%d, 已钳制为%d", perpage, PERPAGE_MAX, PERPAGE_MAX)
            perpage = PERPAGE_MAX
        return perpage
