"""
数据获取层：通过 SkillHub 技能获取同花顺数据
完全替代 akshare/pywencai，用 SkillHub API 获取所有数据
"""
import time
from skillhub_client import (
    query_finance, query_market, query_stocks,
    query_announcements, query_news, query_reports,
    query_industry, query_events, query,
)
from config import (
    SECTOR_MAPPING, DATA_CONFIG, FUNDAMENTAL_FILTER,
)


def _parse_number(value) -> float:
    """将 SkillHub 返回的各种数值格式转为 float"""
    if value is None:
        return 0.0
    try:
        s = str(value).replace(",", "").replace("%", "").replace("亿", "e8").replace("万", "e4")
        # 处理 "123.45亿" 这种格式
        if "e8" in s:
            return float(s.replace("e8", "")) * 1e8
        if "e4" in s:
            return float(s.replace("e4", "")) * 1e4
        return float(s)
    except (ValueError, TypeError):
        return 0.0


# ---- 板块成分股 ----

def get_sector_stocks(sector_key: str) -> list[dict]:
    """
    获取指定板块的成分股列表。
    通过 SkillHub stock_selector 接口查询各概念板块。
    """
    mapping = SECTOR_MAPPING.get(sector_key)
    if not mapping:
        print(f"  未找到板块: {sector_key}")
        return []

    all_stocks = []
    seen_codes = set()

    for concept_name in mapping["concept_names"]:
        print(f"  查询 '{concept_name}' 概念板块...")
        try:
            datas = query_stocks(
                f"属于{concept_name}概念的股票",
                max_pages=2,
                limit=30,
                delay=DATA_CONFIG["request_delay"],
            )
            count = 0
            for item in datas:
                code = item.get("股票代码", "").replace(".SZ", "").replace(".SH", "")
                name = item.get("股票简称", "")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    all_stocks.append({"code": code, "name": name, "sub_sector": concept_name})
                    count += 1
            print(f"    获取到 {count} 只成分股")
        except Exception as e:
            print(f"    '{concept_name}' 获取失败: {e}")

        time.sleep(DATA_CONFIG["request_delay"])

    print(f"  板块 [{sector_key}] 共获取 {len(all_stocks)} 只成分股（去重后）")
    return all_stocks


# ---- 财务数据 ----

def get_stock_financial(code: str, name: str) -> dict:
    """
    获取个股核心财务指标。
    使用 hithink-finance-query 技能。
    """
    result = {
        "roe": None, "gross_margin": None, "net_margin": None,
        "debt_ratio": None, "revenue_growth": None, "profit_growth": None,
        "eps": None, "bvps": None, "pe": None, "pb": None,
        "total_market_value": None, "revenue": None, "net_profit": None,
    }

    try:
        datas = query_finance(
            f"{name} ROE 毛利率 净利率 资产负债率 营收增长率 净利润增长率 PE PB 总市值 每股收益",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if not datas:
            return result

        item = datas[0]
        result["roe"] = _parse_number(item.get("净资产收益率", item.get("ROE")))
        result["gross_margin"] = _parse_number(item.get("销售毛利率", item.get("毛利率")))
        result["net_margin"] = _parse_number(item.get("销售净利率", item.get("净利率")))
        result["debt_ratio"] = _parse_number(item.get("资产负债率"))
        result["revenue_growth"] = _parse_number(item.get("营业收入同比增长率", item.get("营收同比增长")))
        result["profit_growth"] = _parse_number(item.get("净利润同比增长率", item.get("净利润同比增长")))
        result["eps"] = _parse_number(item.get("基本每股收益", item.get("每股收益")))
        result["bvps"] = _parse_number(item.get("每股净资产"))
        result["pe"] = _parse_number(item.get("市盈率", item.get("PE")))
        result["pb"] = _parse_number(item.get("市净率", item.get("PB")))
        result["total_market_value"] = _parse_number(item.get("总市值"))
        result["revenue"] = _parse_number(item.get("营业总收入", item.get("营业收入")))
        result["net_profit"] = _parse_number(item.get("净利润"))
    except Exception as e:
        print(f"    财务数据异常 ({code}): {e}")

    return result


def get_quarterly_eps_growth(code: str, name: str) -> float:
    """获取近2季度EPS同比增长率（CANSLIM C维度）"""
    try:
        datas = query_finance(
            f"{name} 近2季度净利润同比增长率",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if datas:
            item = datas[0]
            return _parse_number(item.get("净利润同比增长率"))
    except Exception:
        pass
    return 0.0


def get_annual_eps_growth(code: str, name: str) -> float:
    """获取近3年EPS复合增长率（CANSLIM A维度）"""
    try:
        datas = query_finance(
            f"{name} 近3年净利润复合增长率",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if datas:
            item = datas[0]
            return _parse_number(item.get("净利润复合增长率"))
    except Exception:
        pass
    return 0.0


# ---- 行情数据 ----

def get_market_data(code: str, name: str) -> dict:
    """
    获取个股行情数据。
    使用 hithink-market-query 技能。
    """
    result = {
        "latest_price": None, "pct_change": None, "volume": None,
        "turnover_rate": None, "high_52w": None, "low_52w": None,
        "main_net_inflow": None, "ma5": None, "ma10": None,
        "ma20": None, "ma60": None, "ma120": None, "ma250": None,
        "macd": None, "rsi": None, "amplitude": None,
    }

    try:
        datas = query_market(
            f"{name} 最新价 涨跌幅 成交量 换手率 52周最高 52周最低 "
            f"主力资金净流入 MA5 MA10 MA20 MA60 MA120 MA250 MACD RSI 振幅",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if not datas:
            return result

        item = datas[0]
        result["latest_price"] = _parse_number(item.get("最新价"))
        result["pct_change"] = _parse_number(item.get("涨跌幅"))
        result["volume"] = _parse_number(item.get("成交量"))
        result["turnover_rate"] = _parse_number(item.get("换手率"))
        result["high_52w"] = _parse_number(item.get("52周最高"))
        result["low_52w"] = _parse_number(item.get("52周最低"))
        result["main_net_inflow"] = _parse_number(item.get("主力资金净流入", item.get("主力净流入")))
        result["ma5"] = _parse_number(item.get("MA5"))
        result["ma10"] = _parse_number(item.get("MA10"))
        result["ma20"] = _parse_number(item.get("MA20"))
        result["ma60"] = _parse_number(item.get("MA60"))
        result["ma120"] = _parse_number(item.get("MA120"))
        result["ma250"] = _parse_number(item.get("MA250"))
        result["macd"] = _parse_number(item.get("MACD"))
        result["rsi"] = _parse_number(item.get("RSI"))
        result["amplitude"] = _parse_number(item.get("振幅"))
    except Exception as e:
        print(f"    行情数据异常 ({code}): {e}")

    return result


def get_market_index_status() -> dict:
    """获取大盘状态（上证指数）"""
    result = {
        "trend": "unknown", "above_ma60": False,
        "above_ma200": False, "index_price": None,
        "index_pct_change": None,
    }
    try:
        datas = query_market(
            "上证指数 最新价 涨跌幅",
            max_pages=1, limit=5, delay=0,
        )
        if datas:
            item = datas[0]
            result["index_price"] = _parse_number(item.get("最新价"))
            result["index_pct_change"] = _parse_number(item.get("涨跌幅"))

        # 判断均线位置
        ma_datas = query_market(
            "上证指数 MA60 MA250",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if ma_datas:
            ma_item = ma_datas[0]
            price = result["index_price"] or 0
            ma60 = _parse_number(ma_item.get("MA60"))
            ma250 = _parse_number(ma_item.get("MA250"))
            result["above_ma60"] = price > ma60 if price and ma60 else False
            result["above_ma200"] = price > ma250 if price and ma250 else False

            if result["above_ma60"] and result["above_ma200"]:
                result["trend"] = "上升趋势（牛市）"
            elif result["above_ma60"]:
                result["trend"] = "震荡偏强"
            else:
                result["trend"] = "弱势/调整"
    except Exception as e:
        print(f"    大盘数据异常: {e}")

    return result


# ---- 消息面数据 ----

def get_stock_announcements(name: str, limit: int = 5) -> list[dict]:
    """获取个股最近公告"""
    try:
        return query_announcements(
            f"{name} 公告", max_pages=1, limit=limit,
            delay=DATA_CONFIG["request_delay"],
        )
    except Exception:
        return []


def get_stock_news(name: str, limit: int = 5) -> list[dict]:
    """获取个股相关新闻"""
    try:
        return query_news(
            f"{name}", max_pages=1, limit=limit,
            delay=DATA_CONFIG["request_delay"],
        )
    except Exception:
        return []


def get_stock_reports(name: str, limit: int = 5) -> list[dict]:
    """获取个股相关研报"""
    try:
        return query_reports(
            f"{name}", max_pages=1, limit=limit,
            delay=DATA_CONFIG["request_delay"],
        )
    except Exception:
        return []


def get_stock_events(name: str, limit: int = 5) -> list[dict]:
    """获取个股事件（业绩预告、解禁、质押等）"""
    try:
        return query_events(
            f"{name} 业绩预告 解禁 质押 调研",
            max_pages=1, limit=limit,
            delay=DATA_CONFIG["request_delay"],
        )
    except Exception:
        return []


def get_sector_news(sector_key: str, limit: int = 5) -> list[dict]:
    """获取板块行业新闻"""
    mapping = SECTOR_MAPPING.get(sector_key, {})
    desc = mapping.get("description", sector_key)
    try:
        return query_news(
            f"{desc} 行业政策 产业动态",
            max_pages=1, limit=limit,
            delay=DATA_CONFIG["request_delay"],
        )
    except Exception:
        return []


# ---- 快速初筛 ----

def quick_filter(sector_key: str) -> list[dict]:
    """
    快速初筛：获取板块成分股 -> 基本面过滤 -> 技术面过滤 -> 返回候选列表。
    """
    print(f"\n{'='*60}")
    print(f"  开始筛选板块: {sector_key}")
    print(f"{'='*60}")

    stocks = get_sector_stocks(sector_key)
    if not stocks:
        print(f"  板块 [{sector_key}] 无成分股数据")
        return []

    max_n = DATA_CONFIG["max_stocks_per_sector"]
    if len(stocks) > max_n:
        print(f"  成分股过多 ({len(stocks)}只)，限制到前 {max_n} 只")
        stocks = stocks[:max_n]

    candidates = []
    for i, stock in enumerate(stocks):
        code = stock["code"]
        name = stock["name"]
        print(f"  [{i+1}/{len(stocks)}] {code} {name}")

        # 基本面快筛
        fin = get_stock_financial(code, name)
        roe = fin.get("roe") or 0
        rev_growth = fin.get("revenue_growth") or 0
        debt = fin.get("debt_ratio") or 100

        if roe < FUNDAMENTAL_FILTER["min_roe"]:
            print(f"    -> ROE={roe}% 不满足最低要求，跳过")
            continue
        if rev_growth < FUNDAMENTAL_FILTER["min_revenue_growth"]:
            print(f"    -> 营收增长={rev_growth}% 不满足要求，跳过")
            continue

        # 技术面快筛（站上60日均线）
        mkt = get_market_data(code, name)
        price = mkt.get("latest_price") or 0
        ma60 = mkt.get("ma60") or 0

        if price <= 0:
            print(f"    -> 行情数据缺失，跳过")
            continue

        if ma60 > 0 and price < ma60:
            print(f"    -> 股价 {price:.2f} < MA60 {ma60:.2f}，跳过")
            continue

        print(f"    -> 通过初筛 ✓")
        candidates.append({
            "code": code,
            "name": name,
            "sub_sector": stock.get("sub_sector", ""),
            "sector_key": sector_key,
            **fin,
            **{f"mkt_{k}": v for k, v in mkt.items()},
            "latest_price": price,
            "ma60": ma60,
        })

    print(f"\n  板块 [{sector_key}] 初筛后剩余 {len(candidates)} 只候选股")
    return candidates
