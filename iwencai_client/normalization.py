"""可选的 API 记录标准化。"""

from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd


_NUMERIC_TAGS = (
    "涨跌幅", "涨幅", "跌幅", "成交额", "净额", "金额", "量比",
    "封单量", "成交量", "换手", "市盈率", "市净率", "封单额",
    "封流比", "封成比", "封耗比",
)


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) else result


def clean_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """保留全部字段，并标准化常见数值字段。"""
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        if key == "所属申万行业" and isinstance(value, list):
            for index, column in enumerate(("申万一级行业", "申万二级行业", "申万三级行业")):
                cleaned[column] = value[index] if index < len(value) else ""
            continue
        if key == "最新价" or any(tag in key for tag in _NUMERIC_TAGS):
            numeric = _to_float(value)
            cleaned[key] = numeric if numeric is not None else value
            continue
        if isinstance(value, float) and math.isnan(value):
            cleaned[key] = None
            continue
        cleaned[key] = value
    return cleaned


def records_to_dataframe(
    rows: list[Mapping[str, Any]], *, normalize: bool = True
) -> pd.DataFrame:
    """将 API 记录转换为 DataFrame，保留动态字段。"""
    if not rows:
        return pd.DataFrame()
    values = [clean_record(row) for row in rows] if normalize else list(rows)
    return pd.DataFrame(values)