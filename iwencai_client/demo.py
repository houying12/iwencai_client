# -*- coding: utf-8 -*-
"""iwencai_client 用法示例: 复制到你的项目后, 修改 API_KEY 即可运行。"""
import logging
import os

from iwencai_client import IWencaiClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# 推荐从环境变量读取; 临时用可改为 API_KEY = "sk-proj-xxxx"(勿提交 git)
API_KEY = os.environ["IWENCAI_API_KEY"]

if __name__ == "__main__":
    client = IWencaiClient()  # timeout/max_pages/retries 等连接级配置在实例化时设置

    df = client.get(
        query="今日涨停，所属申万行业，非ST",
        api_key=API_KEY,        # 必填
        sort_key="最新涨跌幅",   # 可选: 排序字段(用返回结果的实际列名, 可用列见 KeyError 提示)
        sort_order="desc",      # 可选: asc / desc
        page=1,                 # 可选: 保留参数(当前为全量拉取)
        perpage=100,            # 可选: 每页条数, 默认100, 上限100
    )

    print(f"\n共 {len(df)} 条, 列: {list(df.columns)}")
    print(df.head(10).to_string(index=False))
