"""
基本面分析模块（牛市版）
融合4套框架：巴菲特（价值）、段永平（生意）、冯柳（拐点）、戴维斯双击（成长）
牛市调整：降低纯价值权重，提高拐点和双击权重
"""
from config import (
    FUNDAMENTAL_FILTER, FUNDAMENTAL_WEIGHTS,
    TECHNICAL_PARAMS,
)


def _safe_score(val, max_val=10):
    """安全评分，将数值映射到 0-max_val"""
    if val is None:
        return 5
    return max(0, min(max_val, val))


def _score_buffett(fin: dict, mkt: dict) -> tuple:
    """
    巴菲特维度：ROE、毛利率稳定性、负债率
    牛市放宽标准：ROE>8%即可获基本分
    满分 100，归一化到 0-100
    """
    details = {}
    score = 0

    # ROE（满分40）
    roe = fin.get("roe") or 0
    if roe >= 20:
        roe_score = 40
        details["roe_grade"] = "优秀"
    elif roe >= 15:
        roe_score = 32
        details["roe_grade"] = "良好"
    elif roe >= 10:
        roe_score = 24
        details["roe_grade"] = "合格"
    elif roe >= 8:
        roe_score = 16
        details["roe_grade"] = "一般"
    else:
        roe_score = 5
        details["roe_grade"] = "较低"
    score += roe_score
    details["roe"] = roe
    details["roe_score"] = roe_score

    # 毛利率（满分25，牛市放宽）
    gross_margin = fin.get("gross_margin") or 0
    if gross_margin >= 40:
        gm_score = 25
    elif gross_margin >= 25:
        gm_score = 20
    elif gross_margin >= 15:
        gm_score = 15
    elif gross_margin >= 12:
        gm_score = 10
    else:
        gm_score = 5
    score += gm_score
    details["gross_margin"] = gross_margin
    details["gm_score"] = gm_score

    # 资产负债率（满分20，牛市放宽到75%）
    debt = fin.get("debt_ratio") or 50
    if debt <= 30:
        debt_score = 20
        details["debt_grade"] = "低负债"
    elif debt <= 50:
        debt_score = 16
        details["debt_grade"] = "适中"
    elif debt <= 65:
        debt_score = 12
        details["debt_grade"] = "偏高"
    elif debt <= 75:
        debt_score = 8
        details["debt_grade"] = "较高"
    else:
        debt_score = 3
        details["debt_grade"] = "过高"
    score += debt_score
    details["debt_ratio"] = debt
    details["debt_score"] = debt_score

    # 现金流/每股收益质量（满分15）
    eps = fin.get("eps") or 0
    bvps = fin.get("bvps") or 0
    if eps > 0 and bvps > 0:
        cash_score = 12 if eps > bvps * 0.1 else 8
    else:
        cash_score = 5
    score += cash_score
    details["cash_quality_score"] = cash_score

    return score, details


def _score_duan(fin: dict, mkt: dict) -> tuple:
    """
    段永平维度：商业模式质量、PE合理性
    牛市放宽PE容忍度
    满分 100
    """
    details = {}
    score = 0

    # 毛利率稳定性代表商业模式（满分30）
    gross_margin = fin.get("gross_margin") or 0
    net_margin = fin.get("net_margin") or 0
    biz_score = 0
    if gross_margin >= 50:
        biz_score = 30
        details["biz_quality"] = "优秀（高毛利）"
    elif gross_margin >= 30:
        biz_score = 24
        details["biz_quality"] = "良好"
    elif gross_margin >= 15:
        biz_score = 15
        details["biz_quality"] = "一般"
    else:
        biz_score = 8
        details["biz_quality"] = "较弱"
    score += biz_score
    details["biz_score"] = biz_score

    # PE合理性（满分35，牛市放宽）
    pe = fin.get("pe") or 0
    profit_growth = fin.get("profit_growth") or 0
    if pe > 0 and profit_growth > 0:
        peg = pe / profit_growth if profit_growth > 1 else pe
        if peg < 0.5:
            pe_score = 35
            details["peg_grade"] = "极度低估"
        elif peg < 1.0:
            pe_score = 30
            details["peg_grade"] = "合理偏低"
        elif peg < 1.5:
            pe_score = 25
            details["peg_grade"] = "合理"
        elif peg < 2.5:
            pe_score = 18
            details["peg_grade"] = "偏高（牛市中可接受）"
        else:
            pe_score = 10
            details["peg_grade"] = "过高"
        details["peg"] = round(peg, 2)
    elif pe > 0:
        pe_score = 15
        details["peg_grade"] = "无增长参考"
    else:
        pe_score = 5
        details["peg_grade"] = "亏损"
    score += pe_score
    details["pe"] = pe
    details["profit_growth"] = profit_growth
    details["pe_score"] = pe_score

    # 净利润持续增长（满分20）
    if profit_growth >= 30:
        growth_score = 20
        details["growth_grade"] = "高增长"
    elif profit_growth >= 15:
        growth_score = 16
        details["growth_grade"] = "稳定增长"
    elif profit_growth >= 5:
        growth_score = 12
        details["growth_grade"] = "低速增长"
    else:
        growth_score = 5
        details["growth_grade"] = "增长停滞"
    score += growth_score
    details["growth_score"] = growth_score

    # ROE质量（满分15）
    roe = fin.get("roe") or 0
    if roe >= 20:
        roe_quality = 15
    elif roe >= 12:
        roe_quality = 12
    elif roe >= 8:
        roe_quality = 8
    else:
        roe_quality = 4
    score += roe_quality
    details["roe_quality_score"] = roe_quality

    return score, details


def _score_feng(fin: dict, mkt: dict) -> tuple:
    """
    冯柳维度：弱转强、业绩拐点、预期差、赔率
    牛市核心：寻找从弱转强的拐点股，弹性最大
    满分 100
    """
    details = {}
    score = 0

    # 业绩拐点判断（满分40，牛市提高权重）
    profit_growth = fin.get("profit_growth") or 0
    rev_growth = fin.get("revenue_growth") or 0

    # 拐点信号：利润/营收由负转正 或 加速增长
    inflection_signal = 0
    if profit_growth > 0 and rev_growth > 0:
        if profit_growth >= 30:
            inflection_signal = 40  # 强拐点
            details["inflection"] = "强拐点（高增长）"
        elif profit_growth >= 15:
            inflection_signal = 32
            details["inflection"] = "中等拐点"
        else:
            inflection_signal = 20
            details["inflection"] = "弱拐点"
    elif profit_growth > 0 and rev_growth <= 0:
        inflection_signal = 24
        details["inflection"] = "利润拐点（营收待确认）"
    elif profit_growth <= 0 and rev_growth > 0:
        inflection_signal = 16
        details["inflection"] = "营收增长（利润待释放）"
    else:
        inflection_signal = 5
        details["inflection"] = "无明显拐点"
    score += inflection_signal
    details["inflection_score"] = inflection_signal

    # 赔率判断：PB + 52周位置（满分30）
    pb = fin.get("pb") or 0
    high_52w = mkt.get("mkt_high_52w") or 0
    low_52w = mkt.get("mkt_low_52w") or 0
    price = mkt.get("latest_price") or 0

    odds_score = 0
    if high_52w > 0 and price > 0:
        pct_from_high = (high_52w - price) / high_52w * 100
        details["pct_from_52w_high"] = round(pct_from_high, 1)

        if pct_from_high <= 5:
            odds_score = 30  # 接近新高，赔率最高（牛市逻辑）
            details["odds_level"] = "接近新高（牛市强势）"
        elif pct_from_high <= 15:
            odds_score = 24
            details["odds_level"] = "距新高较近"
        elif pct_from_high <= 30:
            odds_score = 16
            details["odds_level"] = "中等空间"
        else:
            odds_score = 8
            details["odds_level"] = "大幅回调中"
    else:
        odds_score = 15
    score += odds_score
    details["odds_score"] = odds_score

    # PB估值参考（满分15）
    if pb > 0:
        if pb <= 2:
            pb_score = 15
            details["pb_level"] = "低PB"
        elif pb <= 5:
            pb_score = 12
            details["pb_level"] = "中等PB"
        elif pb <= 10:
            pb_score = 8
            details["pb_level"] = "偏高PB"
        else:
            pb_score = 4
            details["pb_level"] = "高PB"
    else:
        pb_score = 5
    score += pb_score
    details["pb"] = pb
    details["pb_score"] = pb_score

    # ROE边际变化（满分15）
    roe = fin.get("roe") or 0
    if roe >= 15:
        roe_margin = 15
    elif roe >= 10:
        roe_margin = 12
    elif roe >= 8:
        roe_margin = 8
    else:
        roe_margin = 4
    score += roe_margin
    details["roe_marginal_score"] = roe_margin

    return score, details


def _score_davis(fin: dict, mkt: dict) -> tuple:
    """
    戴维斯双击维度：盈利增速 + 估值扩张潜力
    牛市核心框架：盈利加速增长 + PE扩张 = 最大收益
    满分 100
    """
    details = {}
    score = 0

    # 盈利增速（满分40）
    profit_growth = fin.get("profit_growth") or 0
    rev_growth = fin.get("revenue_growth") or 0

    if profit_growth >= 50:
        earning_score = 40
        details["earning_momentum"] = "爆发增长"
    elif profit_growth >= 30:
        earning_score = 35
        details["earning_momentum"] = "高速增长"
    elif profit_growth >= 20:
        earning_score = 28
        details["earning_momentum"] = "快速增长"
    elif profit_growth >= 10:
        earning_score = 20
        details["earning_momentum"] = "稳定增长"
    elif profit_growth >= 5:
        earning_score = 12
        details["earning_momentum"] = "低速增长"
    else:
        earning_score = 4
        details["earning_momentum"] = "增长疲弱"
    score += earning_score
    details["earning_score"] = earning_score

    # 估值扩张潜力（满分30，牛市核心）
    pe = fin.get("pe") or 0
    roe = fin.get("roe") or 0

    expansion_score = 0
    if roe >= 20 and pe > 0:
        # 高ROE可承载更高PE
        if pe < 20:
            expansion_score = 30  # 低PE+高ROE=双击空间大
            details["expansion"] = "极大双击空间"
        elif pe < 30:
            expansion_score = 24
            details["expansion"] = "双击空间良好"
        elif pe < 50:
            expansion_score = 16
            details["expansion"] = "双击空间适中"
        else:
            expansion_score = 8
            details["expansion"] = "估值已较高"
    elif roe >= 10 and pe > 0:
        if pe < 15:
            expansion_score = 24
            details["expansion"] = "合理估值+良好ROE"
        elif pe < 30:
            expansion_score = 18
            details["expansion"] = "估值适中"
        else:
            expansion_score = 10
            details["expansion"] = "估值偏高"
    elif pe > 0:
        expansion_score = 8
        details["expansion"] = "ROE偏低，双击受限"
    else:
        expansion_score = 5
        details["expansion"] = "亏损，无估值参考"
    score += expansion_score
    details["expansion_score"] = expansion_score

    # 营收-利润增速匹配（满分15）
    if rev_growth > 0 and profit_growth > 0:
        ratio = profit_growth / max(rev_growth, 1)
        if ratio >= 1.2:
            match_score = 15
            details["growth_match"] = "利润增速>营收增速（经营杠杆释放）"
        elif ratio >= 0.8:
            match_score = 12
            details["growth_match"] = "利润与营收同步增长"
        else:
            match_score = 8
            details["growth_match"] = "利润增速落后营收"
    else:
        match_score = 5
        details["growth_match"] = "增速不确定"
    score += match_score
    details["match_score"] = match_score

    # 毛利率趋势（满分15）
    gross_margin = fin.get("gross_margin") or 0
    if gross_margin >= 50:
        margin_score = 15
    elif gross_margin >= 30:
        margin_score = 12
    elif gross_margin >= 15:
        margin_score = 8
    else:
        margin_score = 4
    score += margin_score
    details["margin_trend_score"] = margin_score

    return score, details


def score_fundamental(code: str, name: str, fin: dict, mkt: dict) -> dict:
    """综合基本面评分（满分100）"""
    buffett_score, buffett_detail = _score_buffett(fin, mkt)
    duan_score, duan_detail = _score_duan(fin, mkt)
    feng_score, feng_detail = _score_feng(fin, mkt)
    davis_score, davis_detail = _score_davis(fin, mkt)

    total = (
        buffett_score * FUNDAMENTAL_WEIGHTS["buffett_score"] +
        duan_score * FUNDAMENTAL_WEIGHTS["duan_score"] +
        feng_score * FUNDAMENTAL_WEIGHTS["feng_score"] +
        davis_score * FUNDAMENTAL_WEIGHTS["davis_score"]
    )

    return {
        "total_score": round(total, 1),
        "buffett": {"score": round(buffett_score, 1), **buffett_detail},
        "duan": {"score": round(duan_score, 1), **duan_detail},
        "feng": {"score": round(feng_score, 1), **feng_detail},
        "davis": {"score": round(davis_score, 1), **davis_detail},
    }
