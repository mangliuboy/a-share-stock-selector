"""
SkillHub API 统一客户端
通过调用同花顺问财 OpenAPI 获取各类金融数据
支持两种 API 端点：
  - /v1/query2data       用于 hithink-* 技能（股票、财务、行情等）
  - /v1/comprehensive/search  用于 search 类技能（公告、新闻、研报）
"""
import os
import json
import secrets
import time
import urllib.request
import urllib.error
from typing import Optional

API_QUERY2DATA = "https://openapi.iwencai.com/v1/query2data"
API_COMPREHENSIVE = "https://openapi.iwencai.com/v1/comprehensive/search"

# 技能名 -> (skill_id, endpoint_type, version)
SKILL_REGISTRY = {
    "stock_selector":    ("hithink-astock-selector",  "query2data", "1.0.0"),
    "finance":           ("hithink-finance-query",    "query2data", "1.0.0"),
    "market":            ("hithink-market-query",     "query2data", "1.0.0"),
    "industry":          ("hithink-industry-query",   "query2data", "1.0.0"),
    "business":          ("hithink-business-query",   "query2data", "1.0.0"),
    "event":             ("hithink-event-query",      "query2data", "1.0.0"),
    "management":        ("hithink-management-query", "query2data", "1.0.0"),
    "macro":             ("hithink-macro-query",      "query2data", "1.0.0"),
    "insresearch":       ("hithink-insresearch-query","query2data", "1.0.0"),
    "sector_selector":   ("hithink-sector-selector",  "query2data", "1.0.0"),
    "basicinfo":         ("hithink-basicinfo-query",  "query2data", "1.0.0"),
    "announcement":      ("announcement-search",      "comprehensive", "1.0.0"),
    "news":              ("news-search",              "comprehensive", "1.0.0"),
    "report":            ("report-search",            "comprehensive", "2.0.0"),
}


def _get_api_key() -> str:
    key = os.environ.get("IWENCAI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "IWENCAI_API_KEY 未设置。请在终端执行:\n"
            "export IWENCAI_API_KEY='your_api_key_here'\n"
            "获取方式: https://www.iwencai.com/skillhub → 登录 → 点击Skill → 复制API Key"
        )
    return key


def _build_headers(skill_id: str, skill_version: str,
                   call_type: str = "normal") -> dict:
    trace_id = secrets.token_hex(32)
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": skill_id,
        "X-Claw-Skill-Version": skill_version,
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": trace_id,
    }


def query(skill_type: str, query_str: str, page: int = 1,
          limit: int = 20, call_type: str = "normal",
          timeout: int = 30) -> dict:
    """
    统一查询接口。

    Args:
        skill_type: 技能类型（如 'finance', 'market', 'announcement' 等）
        query_str: 自然语言查询字符串
        page: 页码
        limit: 每页条数
        call_type: normal 或 retry
        timeout: 超时秒数

    Returns:
        {"datas": [...], "code_count": N, "chunks_info": {...}}
    """
    skill_id, endpoint_type, version = SKILL_REGISTRY.get(
        skill_type, (skill_type, "query2data", "1.0.0")
    )

    if endpoint_type == "comprehensive":
        url = API_COMPREHENSIVE
        payload = {
            "channels": [skill_type],
            "app_id": "AIME_SKILL",
            "query": query_str,
        }
    else:
        url = API_QUERY2DATA
        payload = {
            "query": query_str,
            "page": str(page),
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true",
        }

    headers = _build_headers(skill_id, version, call_type)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            if isinstance(result, dict):
                if "datas" in result:
                    return result
                # comprehensive/search 返回的是 data 字段
                if "data" in result:
                    return {"datas": result["data"], "code_count": len(result["data"])}
            return {"datas": [], "code_count": 0, "error": str(result)}
    except urllib.error.HTTPError as e:
        return {"datas": [], "code_count": 0, "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"datas": [], "code_count": 0, "error": f"网络错误: {e.reason}"}
    except Exception as e:
        return {"datas": [], "code_count": 0, "error": str(e)}


def query_all_pages(skill_type: str, query_str: str,
                    max_pages: int = 3, limit: int = 20,
                    delay: float = 0.5) -> list:
    """
    自动翻页查询，返回全部数据。
    """
    all_datas = []
    for page in range(1, max_pages + 1):
        result = query(skill_type, query_str, page=page, limit=limit)
        datas = result.get("datas", [])
        code_count = int(result.get("code_count", 0))

        if not datas:
            break

        all_datas.extend(datas)

        if code_count > 0 and len(all_datas) >= code_count:
            break

        time.sleep(delay)

    return all_datas


# ---- 便捷函数 ----

def query_finance(query_str: str, **kwargs) -> list:
    """finance 接口（当前 API Key 无权限，请使用 query_business 替代）"""
    return query_all_pages("finance", query_str, **kwargs)

def query_business(query_str: str, **kwargs) -> list:
    """经营数据接口（替代 finance，提供 ROE/毛利率/PE/PB/营收增长等）"""
    return query_all_pages("business", query_str, **kwargs)

def query_market(query_str: str, **kwargs) -> list:
    return query_all_pages("market", query_str, **kwargs)

def query_stocks(query_str: str, **kwargs) -> list:
    return query_all_pages("stock_selector", query_str, **kwargs)

def query_announcements(query_str: str, **kwargs) -> list:
    return query_all_pages("announcement", query_str, **kwargs)

def query_news(query_str: str, **kwargs) -> list:
    return query_all_pages("news", query_str, **kwargs)

def query_reports(query_str: str, **kwargs) -> list:
    return query_all_pages("report", query_str, **kwargs)

def query_industry(query_str: str, **kwargs) -> list:
    return query_all_pages("industry", query_str, **kwargs)

def query_events(query_str: str, **kwargs) -> list:
    return query_all_pages("event", query_str, **kwargs)
