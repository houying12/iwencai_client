# -*- coding: utf-8 -*-
"""iwencai_client: 问财(iWencai) A股选股客户端

用法:
    from iwencai_client import IWencaiClient

    client = IWencaiClient()
    df = client.get(
        query="今日涨停，所属申万行业，非ST",
        api_key="sk-proj-xxxx",
        sort_key="涨跌幅%",
        sort_order="desc",
    )

数据来源: 同花顺问财 OpenAPI (https://openapi.iwencai.com)
"""
from ._api import IWencaiAPIError
from .client import IWencaiClient

__version__ = "0.1.0"
__all__ = ["IWencaiClient", "IWencaiAPIError"]
