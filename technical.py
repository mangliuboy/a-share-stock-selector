"""
技术面分析模块（牛市版）
CANSLIM 7维度 + MACD/KDJ/均线/量价指标
牛市调整：加大N(新高)、L(领涨)、S(量价)权重
"""
import math
from config import CANSLIM_CONFIG, TECHNICAL_PARAMS


def _safe(v, default=0):
    return v if v is not None else default


def _score_C(fin: dict) -> tuple:
    """C - 当期盈利增长（满分10）"""
    profit_growth = _safe(fin.get("profit_growth"), 0)
    ideal = CANSLIM_CONFIG["C"]["ideal_pct"]

    if profit_growth >= ideal * 2:
        s = 10
    elif profit_growth >= ideal:
        s = 8 + 2 * (profit_growth - ideal) / ideal
    elif profit_growth >= ideal * 0.5:
        s = 5 + 3 * (profit_growth - ideal * 0.5) / (ideal * 0.5)
    elif profit_growth > 0:
        s = 3 + 2 * profit_growth / (ideal * 0.5)
    else:
        s = 1

    detail = {"profit_growth_q": profit_growth}
    return min(10, max(0, round(s, 1))), detail


def _score_A(fin: dict) -> tuple:
    """A - 年度盈利增长（满分10）"""
    profit_growth = _safe(fin.get("profit_growth"), 0)
    ideal = CANSLIM_CONFIG["A"]["ideal_pct"]

    if profit_growth >= ideal * 2:
        s = 10
    elif profit_growth >= ideal:
        s = 8 + 2 * (profit_growth - ideal) / ideal
    elif profit_growth >= ideal * 0.5:
        s = 5 + 3 * (profit_growth - ideal * 0.5) / (ideal * 0.5)
    elif profit_growth > 0:
        s = 2 + 3 * profit_growth / (ideal * 0.5)
    else:
        s = 1

    detail = {"profit_growth_annual": profit_growth}
    return min(10, max(0, round(s, 1))), detail


def _score_N(mkt: dict) -> tuple:
    """N - 新事物/新高（牛市加大权重，满分10）"""
    price = _safe(mkt.get("latest_price"), 0)
    high_52w = _safe(mkt.get("mkt_high_52w"), 0)
    max_drawdown = CANSLIM_CONFIG["N"]["pct_from_high_max"]

    detail = {}
    if high_52w > 0 and price > 0:
        pct_from_high = (high_52w - price) / high_52w * 100

        if pct_from_high <= 0:
            s = 10  # 创52周新高！
            detail["status"] = "创52周新高"
        elif pct_from_high <= 3:
            s = 9
            detail["status"] = "逼近新高"
        elif pct_from_high <= 5:
            s = 8
            detail["status"] = "非常接近新高"
        elif pct_from_high <= 10:
            s = 7
            detail["status"] = "接近新高"
        elif pct_from_high <= max_drawdown:
            s = 5 + 2 * (max_drawdown - pct_from_high) / max_drawdown
            detail["status"] = "距新高较近"
        elif pct_from_high <= 25:
            s = 4
            detail["status"] = "中期调整中"
        else:
            s = 2
            detail["status"] = "深度回调"
        detail["pct_from_52w_high"] = round(pct_from_high, 1)
    else:
        s = 5
        detail["status"] = "数据不足"

    return min(10, max(0, round(s, 1))), detail


def _score_S(mkt: dict) -> tuple:
    """S - 供需关系/量价配合（满分10）"""
    detail = {}

    # 量价配合判断
    pct_change = _safe(mkt.get("mkt_pct_change"), 0)
    volume = _safe(mkt.get("mkt_volume"), 0)
    amplitude = _safe(mkt.get("mkt_amplitude"), 0)
    turnover = _safe(mkt.get("mkt_turnover_rate"), 0)

    s = 5  # 基础分

    # 换手率活跃（牛市中高换手意味着交投活跃）
    if turnover >= 5:
        s += 2
        detail["turnover_level"] = "高换手（活跃）"
    elif turnover >= 2:
        s += 1
        detail["turnover_level"] = "中等换手"
    else:
        detail["turnover_level"] = "低换手"

    # 价格位置与成交量配合
    if pct_change > 2 and volume > 0:
        s += 1.5  # 放量上涨
        detail["volume_price"] = "放量上涨"
    elif pct_change > 0:
        s += 0.5
        detail["volume_price"] = "温和上涨"
    elif pct_change < -2:
        s -= 1
        detail["volume_price"] = "明显下跌"

    # 振幅（牛市中适度振幅是健康的）
    if 3 <= amplitude <= 8:
        s += 0.5
        detail["amplitude"] = "健康振幅"
    elif amplitude > 8:
        s -= 0.5
        detail["amplitude"] = "振幅过大"

    detail["pct_change"] = pct_change
    detail["turnover"] = turnover

    return min(10, max(0, round(s, 1))), detail


def _score_L(mkt: dict, market_status: dict) -> tuple:
    """L - 领涨股/相对强度（牛市重点，满分10）"""
    detail = {}
    pct_change = _safe(mkt.get("mkt_pct_change"), 0)
    index_pct = _safe(market_status.get("index_pct_change"), 0)

    # 相对强度：个股涨幅 - 大盘涨幅
    rs = pct_change - index_pct

    if rs >= 5:
        s = 10
        detail["rs_level"] = "极强领涨"
    elif rs >= 3:
        s = 9
        detail["rs_level"] = "强势领涨"
    elif rs >= 2:
        s = 8
        detail["rs_level"] = "领涨"
    elif rs >= 1:
        s = 7
        detail["rs_level"] = "略微领先"
    elif rs >= 0:
        s = 6
        detail["rs_level"] = "同步大盘"
    elif rs >= -1:
        s = 4
        detail["rs_level"] = "略弱于大盘"
    elif rs >= -3:
        s = 2
        detail["rs_level"] = "明显落后"
    else:
        s = 1
        detail["rs_level"] = "严重落后"

    detail["rs"] = round(rs, 2)
    detail["stock_pct"] = pct_change
    detail["index_pct"] = index_pct

    return min(10, max(0, round(s, 1))), detail


def _score_I(mkt: dict) -> tuple:
    """I - 机构认同（满分10）"""
    detail = {}
    main_inflow = _safe(mkt.get("mkt_main_net_inflow"), 0)

    # 主力资金净流入代表机构态度
    if main_inflow > 1e8:  # >1亿
        s = 9
        detail["institution_signal"] = "主力大幅流入"
    elif main_inflow > 5e7:
        s = 8
        detail["institution_signal"] = "主力明显流入"
    elif main_inflow > 1e7:
        s = 7
        detail["institution_signal"] = "主力小幅流入"
    elif main_inflow > 0:
        s = 6
        detail["institution_signal"] = "主力微幅流入"
    elif main_inflow > -5e7:
        s = 5
        detail["institution_signal"] = "主力小幅流出"
    elif main_inflow > -1e8:
        s = 3
        detail["institution_signal"] = "主力明显流出"
    else:
        s = 1
        detail["institution_signal"] = "主力大幅流出"

    detail["main_net_inflow"] = main_inflow
    return min(10, max(0, round(s, 1))), detail


def _score_M(market_status: dict) -> tuple:
    """M - 大盘方向（牛市重点，满分10）"""
    detail = {}
    trend = market_status.get("trend", "unknown")

    if "牛市" in trend or "上升" in trend:
        s = 10
        detail["market"] = "牛市/上升趋势（全力做多）"
    elif "震荡偏强" in trend:
        s = 8
        detail["market"] = "震荡偏强（积极选股）"
    elif "震荡" in trend:
        s = 6
        detail["market"] = "震荡市（精选个股）"
    elif "弱势" in trend:
        s = 3
        detail["market"] = "弱势（谨慎）"
    else:
        s = 5
        detail["market"] = "趋势不明"

    detail["trend"] = trend
    return min(10, max(0, round(s, 1))), detail


def _score_indicators(mkt: dict) -> tuple:
    """补充技术指标评分：均线、MACD（满分20）"""
    detail = {}
    s = 0

    price = _safe(mkt.get("latest_price"), 0)
    if price <= 0:
        return 10, detail

    # 均线多头排列（满分10）
    ma_scores = []
    for period in ["ma5", "ma10", "ma20", "ma60"]:
        ma_val = _safe(mkt.get(f"mkt_{period}"), 0)
        if ma_val > 0 and price > ma_val:
            ma_scores.append(2.5)
        elif ma_val > 0:
            ma_scores.append(1)
        else:
            ma_scores.append(1)
    ma_score = sum(ma_scores)
    s += ma_score
    detail["ma_score"] = round(ma_score, 1)

    # MACD金叉/死叉（满分5）
    macd_val = _safe(mkt.get("mkt_macd"), 0)
    if macd_val > 0.5:
        macd_score = 5
        detail["macd_signal"] = "MACD金叉多头"
    elif macd_val > 0:
        macd_score = 4
        detail["macd_signal"] = "MACD偏多"
    elif macd_val > -0.5:
        macd_score = 2
        detail["macd_signal"] = "MACD偏空"
    else:
        macd_score = 1
        detail["macd_signal"] = "MACD死叉空头"
    s += macd_score
    detail["macd"] = macd_val

    # RSI（满分5）
    rsi = _safe(mkt.get("mkt_rsi"), 50)
    if 50 <= rsi <= 80:
        rsi_score = 5
        detail["rsi_signal"] = "RSI强势区间"
    elif rsi > 80:
        rsi_score = 3
        detail["rsi_signal"] = "RSI超买"
    elif 30 <= rsi < 50:
        rsi_score = 3
        detail["rsi_signal"] = "RSI偏弱"
    else:
        rsi_score = 2
        detail["rsi_signal"] = "RSI超卖"
    s += rsi_score
    detail["rsi"] = rsi

    return min(20, max(0, round(s, 1))), detail


def score_technical(code: str, name: str, fin: dict, mkt: dict,
                    market_status: dict) -> dict:
    """
    CANSLIM 技术面综合评分（满分100）
    总分 = 7维度得分 * 权重 + 技术指标
    """
    c_score, c_detail = _score_C(fin)
    a_score, a_detail = _score_A(fin)
    n_score, n_detail = _score_N(mkt)
    s_score, s_detail = _score_S(mkt)
    l_score, l_detail = _score_L(mkt, market_status)
    i_score, i_detail = _score_I(mkt)
    m_score, m_detail = _score_M(market_status)
    ind_score, ind_detail = _score_indicators(mkt)

    # CANSLIM 7维度加权（总分70）
    canslim_raw = (
        c_score * CANSLIM_CONFIG["C"]["weight"] +
        a_score * CANSLIM_CONFIG["A"]["weight"] +
        n_score * CANSLIM_CONFIG["N"]["weight"] +
        s_score * CANSLIM_CONFIG["S"]["weight"] +
        l_score * CANSLIM_CONFIG["L"]["weight"] +
        i_score * CANSLIM_CONFIG["I"]["weight"] +
        m_score * CANSLIM_CONFIG["M"]["weight"]
    ) * 10  # 每项0-10分，权重和为1，所以 raw 是0-10，乘以10变0-100

    # 归一化到70满分
    canslim_score = min(70, canslim_raw)

    # 技术指标补充（0-20分）+ MA均线系统（0-10分）
    technical_total = canslim_score + ind_score
    technical_total = min(100, max(0, technical_total))

    return {
        "total_score": round(technical_total, 1),
        "canslim_score": round(canslim_score, 1),
        "indicator_score": round(ind_score, 1),
        "C": {"score": c_score, "label": CANSLIM_CONFIG["C"]["label"], **c_detail},
        "A": {"score": a_score, "label": CANSLIM_CONFIG["A"]["label"], **a_detail},
        "N": {"score": n_score, "label": CANSLIM_CONFIG["N"]["label"], **n_detail},
        "S": {"score": s_score, "label": CANSLIM_CONFIG["S"]["label"], **s_detail},
        "L": {"score": l_score, "label": CANSLIM_CONFIG["L"]["label"], **l_detail},
        "I": {"score": i_score, "label": CANSLIM_CONFIG["I"]["label"], **i_detail},
        "M": {"score": m_score, "label": CANSLIM_CONFIG["M"]["label"], **m_detail},
        "indicators": {"score": ind_score, **ind_detail},
    }
