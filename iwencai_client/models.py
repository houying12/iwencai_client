"""增强 OpenAPI 客户端的公共结果模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class QueryResult:
    """一次查询的完整结果，或明确标记为不完整的部分结果。"""

    query: str
    rows: tuple[Mapping[str, Any], ...]
    code_count: int
    pages_fetched: int
    complete: bool
    chunks_info: Any = None
    raw_pages: tuple[Mapping[str, Any], ...] = ()

    def to_dataframe(
        self,
        *,
        normalize: bool = True,
        sort_by: str | None = None,
        ascending: bool = True,
    ):
        """将结果转换为 pandas DataFrame。"""
        from .normalization import records_to_dataframe

        dataframe = records_to_dataframe(list(self.rows), normalize=normalize)
        if sort_by is not None:
            if sort_by not in dataframe.columns:
                raise KeyError(
                    f"sort_by {sort_by!r} 不是返回列；可用列：{list(dataframe.columns)}"
                )
            dataframe = dataframe.sort_values(
                by=sort_by, ascending=ascending, ignore_index=True
            )
        return dataframe

    def __len__(self) -> int:
        return len(self.rows)