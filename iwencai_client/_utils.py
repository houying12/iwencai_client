# -*- coding: utf-8 -*-
"""通用字段清洗工具: 不绑定任何具体选股场景, 任意 query 返回的字段都能完整保留。"""
import math
from typing import Any, Dict, List

import pandas as pd


def pick(d: Dict[str, Any], prefix: str) -> Any:
    """按前缀取字段, 兼容带日期后缀的动态列名(如 '涨停原因[20260827]')。"""
    for k, v in d.items():
        if k.startswith(prefix):
            return v
    return None


def to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def round2(v, n: int = 2):
    """数值字符串(含科学计数法) -> float, 保留 n 位小数; 无法转换返回 None。"""
    f = to_float(v)
    return round(f, n) if f is not None else None


# 数值特征字段: 命中这些标签的列尝试转 float
_NUMERIC_TAGS = (
    "涨跌幅", "涨幅", "跌幅",
    "成交额", "净额", "金额", "量比",
    "封单量", "成交量", "换手", "市盈率", "市净率",
    "封单额", "封流比", "封成比", "封耗比",
)


def clean_record(d: Dict[str, Any]) -> Dict[str, Any]:
    """清洗单条记录:
    - 所属申万行业(list) 拆分为 申万一级/二级/三级行业
    - 数值特征字段转 float
    - NaN(float) 转 None
    - 其余字段(含动态日期后缀列名) 原样保留
    """
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if k == "所属申万行业" and isinstance(v, list):
            for i, col in enumerate(("申万一级行业", "申万二级行业", "申万三级行业")):
                out[col] = v[i] if i < len(v) else ""
            continue
        if k == "最新价":
            out[k] = round2(v)
            continue
        if any(tag in k for tag in _NUMERIC_TAGS):
            out[k] = round2(v)
            continue
        if isinstance(v, float) and math.isnan(v):
            out[k] = None
            continue
        out[k] = v
    return out


def records_to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """原始记录列表 -> 清洗后的 DataFrame。空数据返回空 DataFrame(保留零行)。"""
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([clean_record(r) for r in rows])
