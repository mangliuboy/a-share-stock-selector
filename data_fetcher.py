"""
数据获取层：通过 SkillHub 技能获取同花顺数据
完全替代 akshare/pywencai，用 SkillHub API 获取所有数据

注意：API 返回的字段名带有日期后缀 [YYYYMMDD]、大小写不一致、
      字段名不同于中文名称等问题，本模块统一做了模糊匹配处理。
"""
import re
import time
from skillhub_client import (
    query_finance, query_business, query_market, query_stocks,
    query_announcements, query_news, query_reports,
    query_industry, query_events, query,
)
from config import (
    SECTOR_MAPPING, DATA_CONFIG, FUNDAMENTAL_FILTER, SECTOR_ROE_THRESHOLDS,
)


def _parse_number(value) -> float:
    """将 SkillHub 返回的各种数值格式转为 float"""
    if value is None:
        return 0.0
    try:
        s = str(value).replace(",", "").replace("%", "").replace("亿", "e8").replace("万", "e4")
        if "e8" in s:
            return float(s.replace("e8", "")) * 1e8
        if "e4" in s:
            return float(s.replace("e4", "")) * 1e4
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _find_value(item: dict, *patterns: str, default=None):
    """
    模糊匹配字段值。按优先级从高到低：
    1. 精确 key 匹配
    2. 去除日期后缀精确匹配
    3. 相等长度优先的包含匹配（避免 "营业收入" 误匹配 "营业收入同比增长率"）
    4. 中文近义匹配
    """
    date_suffix = re.compile(r'\[\d{8}\]$')

    # 1. 精确匹配
    for p in patterns:
        if p in item:
            return item[p]

    # 2. 忽略日期后缀 [YYYYMMDD] 精确匹配 —— 按 pattern 优先级顺序
    for p in patterns:
        for key, val in item.items():
            clean_key = date_suffix.sub('', key)
            if clean_key == p or clean_key.lower() == p.lower():
                return val

    # 3. 模糊包含匹配 —— 优先最短匹配，避免 "营业收入" 误命中 "营业收入同比增长率"
    #    评分 = (clean_key长度 - pattern长度)，最短者最优
    best_match = None
    best_score = float('inf')
    for key, val in item.items():
        clean_key = date_suffix.sub('', key).lower()
        for p in patterns:
            p_lower = p.lower()
            if p_lower in clean_key:
                score = len(clean_key) - len(p_lower)
                if score < best_score:
                    best_score = score
                    best_match = val
    if best_match is not None:
        return best_match

    # 4. 中文近义匹配（特例处理）
    synonym_map = {
        "主力资金净流入": ["主力资金流向", "主力净流入", "主力资金"],
        "主力净流入": ["主力资金流向", "主力净流入", "主力资金"],
        "总市值": ["流通市值", "a股流通市值", "a股总市值", "市值"],
        "52周最高": ["52周最高价", "最高价", "年内最高"],
        "52周最低": ["52周最低价", "最低价", "年内最低"],
        "净利润": ["归母净利润", "净利润"],
        "营业总收入": ["营业总收入", "营业收入"],
        "营业收入": ["营业总收入", "营业收入"],
    }
    for p in patterns:
        synonyms = synonym_map.get(p, [])
        for syn in synonyms:
            for key, val in item.items():
                clean_key = date_suffix.sub('', key).lower()
                if syn.lower() in clean_key:
                    return val

    return default


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
                code = str(item.get("股票代码", "")).replace(".SZ", "").replace(".SH", "")
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
    API 返回字段带日期后缀如 净资产收益率[20260331]
    PE 返回为 最新市盈率ttm, PB 返回为 最新市净率
    """
    result = {
        "roe": None, "gross_margin": None, "net_margin": None,
        "debt_ratio": None, "revenue_growth": None, "profit_growth": None,
        "eps": None, "bvps": None, "pe": None, "pb": None,
        "total_market_value": None, "revenue": None, "net_profit": None,
    }

    try:
        # 分两批查询，确保获取完整数据
        # 第一批：盈利能力 + 估值指标
        datas1 = query_business(
            f"{name} ROE 销售毛利率 销售净利率 PE 市净率 总市值 基本每股收益ttm 每股净资产",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        # 第二批：成长性 + 实际营收利润 + 资产负债率
        datas2 = query_business(
            f"{name} 营业总收入 归母净利润 营业收入同比增长率 归母净利润同比增长率 资产负债率",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )

        # 合并两个结果（取第一条数据）
        item = {}
        if datas1:
            item.update(datas1[0])
        if datas2:
            item.update(datas2[0])
        if not item:
            return result

        # 使用模糊匹配获取各字段
        result["roe"] = _parse_number(_find_value(item, "净资产收益率", "ROE"))
        result["gross_margin"] = _parse_number(_find_value(item, "销售毛利率", "毛利率"))
        result["net_margin"] = _parse_number(_find_value(item, "销售净利率", "净利率"))
        result["debt_ratio"] = _parse_number(_find_value(item, "资产负债率"))
        result["revenue_growth"] = _parse_number(_find_value(item, "营业收入同比增长率", "营收同比增长", "营收增长率"))
        result["profit_growth"] = _parse_number(_find_value(item, "净利润同比增长率", "归母净利润同比增长率"))
        result["eps"] = _parse_number(_find_value(item, "基本每股收益ttm", "基本每股收益", "每股收益"))
        result["bvps"] = _parse_number(_find_value(item, "每股净资产"))
        result["pe"] = _parse_number(_find_value(item, "市盈率(pe,ttm)", "市盈率ttm", "市盈率", "PE"))
        result["pb"] = _parse_number(_find_value(item, "市净率", "PB"))
        result["total_market_value"] = _parse_number(_find_value(item, "总市值"))
        result["revenue"] = _parse_number(_find_value(item, "营业总收入"))
        result["net_profit"] = _parse_number(_find_value(item, "归母净利润"))
    except Exception as e:
        print(f"    财务数据异常 ({code}): {e}")

    return result


def get_quarterly_eps_growth(code: str, name: str) -> float:
    """获取近2季度EPS同比增长率（CANSLIM C维度）"""
    try:
        datas = query_business(
            f"{name} 近2季度净利润同比增长率",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if datas:
            item = datas[0]
            return _parse_number(_find_value(item, "净利润同比增长率"))
    except Exception:
        pass
    return 0.0


def get_annual_eps_growth(code: str, name: str) -> float:
    """获取近3年EPS复合增长率（CANSLIM A维度）"""
    try:
        datas = query_business(
            f"{name} 近3年净利润复合增长率",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if datas:
            item = datas[0]
            return _parse_number(_find_value(item, "净利润复合增长率"))
    except Exception:
        pass
    return 0.0


# ---- 行情数据 ----

def get_market_data(code: str, name: str) -> dict:
    """
    获取个股行情数据。
    使用 hithink-market-query 技能。
    API 返回字段带日期后缀如 ma5[20260515]，且为小写。
    52周最高/最低 和 MA120/MA250 可能不可用，通过额外查询补充。
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
            f"{name} 最新价 涨跌幅 成交量 换手率 "
            f"主力资金净流入 MA5 MA10 MA20 MA60 MACD RSI 振幅",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if not datas:
            return result

        item = datas[0]
        result["latest_price"] = _parse_number(_find_value(item, "最新价"))
        result["pct_change"] = _parse_number(_find_value(item, "涨跌幅"))
        result["volume"] = _parse_number(_find_value(item, "成交量"))
        result["turnover_rate"] = _parse_number(_find_value(item, "换手率"))
        result["main_net_inflow"] = _parse_number(_find_value(item, "主力资金净流入", "主力净流入"))
        result["ma5"] = _parse_number(_find_value(item, "ma5", "MA5"))
        result["ma10"] = _parse_number(_find_value(item, "ma10", "MA10"))
        result["ma20"] = _parse_number(_find_value(item, "ma20", "MA20"))
        result["ma60"] = _parse_number(_find_value(item, "ma60", "MA60"))
        result["macd"] = _parse_number(_find_value(item, "macd", "MACD"))
        result["rsi"] = _parse_number(_find_value(item, "rsi", "RSI"))
        result["amplitude"] = _parse_number(_find_value(item, "振幅"))

        # 52周高低：单独查询
        result["high_52w"] = _parse_number(_find_value(item, "52周最高"))
        result["low_52w"] = _parse_number(_find_value(item, "52周最低"))
    except Exception as e:
        print(f"    行情数据异常 ({code}): {e}")

    # 补充 MA120/MA250（需要额外查询）
    try:
        ma_datas = query_market(
            f"{name} MA120 MA250",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if ma_datas:
            ma_item = ma_datas[0]
            result["ma120"] = _parse_number(_find_value(ma_item, "ma120", "MA120"))
            result["ma250"] = _parse_number(_find_value(ma_item, "ma250", "MA250"))
    except Exception:
        pass

    return result


def get_market_index_status() -> dict:
    """获取大盘状态（上证指数）"""
    result = {
        "trend": "unknown", "above_ma60": False,
        "above_ma200": False, "index_price": None,
        "index_pct_change": None,
    }
    try:
        # 基本行情
        datas = query_market(
            "上证指数 最新价 涨跌幅",
            max_pages=1, limit=5, delay=0,
        )
        if datas:
            item = datas[0]
            result["index_price"] = _parse_number(_find_value(item, "最新价"))
            result["index_pct_change"] = _parse_number(_find_value(item, "涨跌幅"))

        # 均线位置
        ma_datas = query_market(
            "上证指数 MA60 MA250",
            max_pages=1, limit=5, delay=DATA_CONFIG["request_delay"],
        )
        if ma_datas:
            ma_item = ma_datas[0]
            price = result["index_price"] or 0
            ma60 = _parse_number(_find_value(ma_item, "ma60", "MA60"))
            ma250 = _parse_number(_find_value(ma_item, "ma250", "MA250"))
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

        min_roe = SECTOR_ROE_THRESHOLDS.get(sector_key, FUNDAMENTAL_FILTER["min_roe"])
        if roe < min_roe:
            print(f"    -> ROE={roe}% < 行业标准{min_roe}%，跳过")
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
