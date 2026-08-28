# iwencai-client

问财（iWencai）A 股智能选股客户端 —— 基于**同花顺问财官方 OpenAPI**，用自然语言查询即可筛选 A 股股票，自动翻页拉全量，返回规整的 **pandas DataFrame**。

## 特性

- **自然语言选股**：如 `"今日涨停，所属申万行业，非ST"`、`"流通市值>100亿且PE<20的医药股"`，无需拼 SQL
- **官方 OpenAPI 网关**：API Key 鉴权（`Authorization: Bearer`），非爬虫实现，稳定且符合规范
- **自动翻页拉全量**：按命中总数精确停止，不多拉、不漏拉
- **通用字段清洗**：数值列自动转 `float`，申万行业列表拆分为 一级/二级/三级行业，其余字段原样保留（不丢任何列）
- **健壮性**：429/5xx 指数退避重试、参数校验、空数据返回空 DataFrame 不抛错
- **轻量**：仅依赖 `requests` 与 `pandas`

## 安装

```bash
# 1. 获取代码
git clone https://github.com/houying12/iwencai_client.git

# 2. 安装依赖（仅 requests 和 pandas）
pip install requests pandas
```

**使用方式**：clone 后，把仓库中 `iwencai_client` 包目录（内含 `__init__.py`、`client.py`、`_api.py`、`_utils.py`）整体复制到你的项目目录下（与你的脚本同级），即可直接 `import` 使用。

## 快速开始

```python
from iwencai_client import IWencaiClient

client = IWencaiClient()

df = client.get(
    query="今日涨停，所属申万行业，非ST",
    api_key="sk-proj-xxxx",     # 必填
    sort_key="最新涨跌幅",        # 可选：排序字段（返回结果列名）
    sort_order="desc",          # 可选：asc / desc
    perpage=100,                # 可选：每页条数，默认 100，上限 100
)
print(df)
```

## API 文档

使用方法可参考`demo.py` 文件

### `get()`

```python
get(query, api_key, sort_key=None, sort_order="asc", page=1, perpage=100) -> pd.DataFrame
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `query` | ✅ | 自然语言查询问句，如 `"今日涨停，所属申万行业，非ST"` |
| `api_key` | ✅ | 问财 API Key，用于 `Authorization: Bearer` 鉴权 |
| `sort_key` | ❌ | 排序字段，值为返回结果的列名（如 `"最新涨跌幅"`） |
| `sort_order` | ❌ | `"asc"` 升序 / `"desc"` 降序，默认 `"asc"` |
| `page` | ❌ | 查询页数，默认 1（保留参数，当前实现为全量拉取） |
| `perpage` | ❌ | 每页条数，默认 100；问财上限 100，超限自动钳制 |

**返回值**：清洗后的 `pandas.DataFrame`（全量结果，可按 `sort_key`/`sort_order` 排序）。

**异常**：`ValueError`（参数不合法）、`KeyError`（`sort_key` 不是返回列名，错误信息会列出可用列）、`IWencaiAPIError`（网关/网络错误）。

### 排序说明

`sort_key` 使用**返回结果的真实列名**（如 `最新涨跌幅`、`申万一级行业`）。列名随查询条件动态变化，不确定时先不传 `sort_key` 跑一次，打印返回的列清单即可。

## 获取 API Key

> 1、先打开同花顺问财官网：https://www.iwencai.com/screener
> 2、点击**SkillHub**
> 3、找到**问财选 A 股**点击
> 4、在弹出的卡片中找到**IWENCAI_API_KEY=**，后续内容就是所需要用到的Key

## 与 pywencai 的区别

| | iwencai-client | pywencai |
|---|---|---|
| 数据通道 | 同花顺问财**官方 OpenAPI**（API Key 鉴权） | 问财 Web 接口（爬虫式） |
| 稳定性 | 官方网关，规范稳定 | 依赖网页接口，可能受调整影响 |
| 返回 | 规整 DataFrame + 全量翻页 + 字段清洗 | DataFrame |
| 依赖 | `requests` + `pandas` |  |

## 数据来源与免责声明

- 数据来源于**同花顺问财**（https://www.iwencai.com/unifiedwap/chat）
- 本工具仅供学习、研究使用，不构成任何投资建议；据此操作，风险自负

## License

待补充（作者确认后添加 LICENSE 文件）。
