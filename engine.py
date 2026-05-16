"""
推荐引擎：整合基本面+技术面+消息面，生成结构化选股报告
牛市版：技术面权重最高（45%），消息面其次（35%），基本面最低（20%）
"""
import os
from datetime import datetime
from config import (
    SECTOR_MAPPING, COMPREHENSIVE_WEIGHTS,
    RECOMMENDATION_THRESHOLDS,
)
from data_fetcher import (
    quick_filter, get_stock_financial, get_market_data,
    get_market_index_status,
)
from fundamental import score_fundamental
from technical import score_technical
from research import score_news


def get_recommendation(score: float) -> str:
    """根据综合评分返回推荐等级"""
    thresholds = RECOMMENDATION_THRESHOLDS
    if score >= thresholds["strong_buy"]:
        return "强烈推荐买入"
    elif score >= thresholds["buy"]:
        return "推荐买入"
    elif score >= thresholds["hold"]:
        return "观望"
    else:
        return "回避"


def analyze_stock(candidate: dict, market_status: dict) -> dict:
    """对单只候选股执行完整分析"""
    code = candidate["code"]
    name = candidate["name"]
    sector_key = candidate["sector_key"]

    print(f"\n  --- 深度分析: {code} {name} ---")

    # 获取最新数据
    fin = get_stock_financial(code, name)
    mkt = get_market_data(code, name)
    cand = {**candidate, **fin}

    # 基本面评分
    fundamental = score_fundamental(code, name, fin, cand)
    print(f"    基本面: {fundamental['total_score']}/100")

    # 技术面评分
    technical = score_technical(code, name, fin, cand, market_status)
    print(f"    技术面: {technical['total_score']}/100")

    # 消息面评分
    news = score_news(code, name, sector_key)
    print(f"    消息面: {news['total_score']}/100")

    # 综合评分（牛市权重）
    weights = COMPREHENSIVE_WEIGHTS
    comprehensive = (
        fundamental["total_score"] * weights["fundamental"] +
        technical["total_score"] * weights["technical"] +
        news["total_score"] * weights["news"]
    )
    recommendation = get_recommendation(comprehensive)

    print(f"    综合评分: {comprehensive:.1f}/100 -> {recommendation}")

    return {
        "code": code,
        "name": name,
        "sector_key": sector_key,
        "sub_sector": candidate.get("sub_sector", ""),
        "comprehensive_score": round(comprehensive, 1),
        "recommendation": recommendation,
        "fundamental": fundamental,
        "technical": technical,
        "news": news,
        "key_metrics": {
            "roe": fin.get("roe"),
            "gross_margin": fin.get("gross_margin"),
            "profit_growth": fin.get("profit_growth"),
            "pe": fin.get("pe"),
            "pb": fin.get("pb"),
            "debt_ratio": fin.get("debt_ratio"),
            "latest_price": cand.get("latest_price"),
            "market_value": fin.get("total_market_value"),
        },
    }


def generate_report(result: dict) -> str:
    """生成结构化 Markdown 报告"""
    code = result["code"]
    name = result["name"]
    score = result["comprehensive_score"]
    rec = result["recommendation"]
    fund = result["fundamental"]
    tech = result["technical"]
    news = result["news"]
    km = result["key_metrics"]

    lines = []
    lines.append(f"# {name}（{code}）选股分析报告")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**所属板块**: {result['sector_key']}")
    lines.append("")

    # 综合评分
    lines.append("## 综合评分")
    lines.append(f"| 维度 | 得分 | 权重 |")
    lines.append(f"|------|------|------|")
    lines.append(f"| 基本面 | {fund['total_score']}/100 | 20% |")
    lines.append(f"| 技术面 | {tech['total_score']}/100 | 45% |")
    lines.append(f"| 消息面 | {news['total_score']}/100 | 35% |")
    lines.append(f"| **综合** | **{score}/100** | - |")
    lines.append(f"")
    lines.append(f"**推荐等级**: {rec}")
    lines.append("")

    # 第一性原理分析
    lines.append("## 第一性原理分析")
    lines.append("### 需求端")
    lines.append(f"  行业属于{result['sector_key']}板块，{SECTOR_MAPPING.get(result['sector_key'], {}).get('description', '')}")
    growth = km.get("profit_growth") or 0
    if growth >= 20:
        lines.append(f"  净利润增速 {growth}%，需求旺盛，行业景气度较高")
    elif growth >= 5:
        lines.append(f"  净利润增速 {growth}%，需求稳定增长")
    else:
        lines.append(f"  净利润增速 {growth}%，需求端有待观察")
    lines.append("")

    lines.append("### 供给端")
    margin = km.get("gross_margin") or 0
    if margin >= 40:
        lines.append(f"  毛利率 {margin}%，竞争格局优良，有护城河")
    elif margin >= 20:
        lines.append(f"  毛利率 {margin}%，竞争格局尚可")
    else:
        lines.append(f"  毛利率 {margin}%，竞争激烈，需关注差异化能力")
    lines.append("")

    lines.append("### 成长驱动力")
    catalysts = news.get("catalysts", [])
    if catalysts:
        for cat in catalysts[:3]:
            lines.append(f"  - {cat}")
    else:
        lines.append(f"  - 行业趋势 + 公司基本面改善")
    lines.append("")

    # 基本面详情
    lines.append("## 基本面分析（权重20%）")
    lines.append(f"**总分: {fund['total_score']}/100**")
    lines.append("")
    for framework in ["buffett", "duan", "feng", "davis"]:
        fw = fund[framework]
        lines.append(f"### {framework.upper()} 维度 ({fw['score']}/100)")
        for k, v in fw.items():
            if k != "score":
                lines.append(f"  - {k}: {v}")
        lines.append("")

    # 技术面详情
    lines.append("## 技术面分析（权重45%）")
    lines.append(f"**总分: {tech['total_score']}/100**")
    lines.append(f"**CANSLIM得分: {tech['canslim_score']}/70**")
    lines.append(f"**技术指标得分: {tech['indicator_score']}/30**")
    lines.append("")
    for letter in ["C", "A", "N", "S", "L", "I", "M"]:
        tl = tech[letter]
        lines.append(f"- **{letter} - {tl['label']}**: {tl['score']}/10")
        for k, v in tl.items():
            if k not in ("score", "label"):
                lines.append(f"  - {k}: {v}")
    lines.append("")

    # 消息面详情
    lines.append("## 消息面分析（权重35%）")
    lines.append(f"**总分: {news['total_score']}/100**")
    lines.append("")
    if news.get("catalysts"):
        lines.append("### 近期催化剂")
        for c in news["catalysts"]:
            lines.append(f"  - {c}")
        lines.append("")
    if news.get("risks"):
        lines.append("### 风险提示")
        for r in news["risks"]:
            lines.append(f"  - {r}")
        lines.append("")

    # 关键指标
    lines.append("## 关键指标一览")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| ROE | {km.get('roe', 'N/A')}% |")
    lines.append(f"| 毛利率 | {km.get('gross_margin', 'N/A')}% |")
    lines.append(f"| 净利润增速 | {km.get('profit_growth', 'N/A')}% |")
    lines.append(f"| PE | {km.get('pe', 'N/A')} |")
    lines.append(f"| PB | {km.get('pb', 'N/A')} |")
    lines.append(f"| 资产负债率 | {km.get('debt_ratio', 'N/A')}% |")
    lines.append(f"| 最新价 | {km.get('latest_price', 'N/A')} |")
    lines.append(f"| 总市值 | {km.get('market_value', 'N/A')} |")
    lines.append("")

    # 投资建议
    lines.append("## 投资建议")
    lines.append(f"**{rec}**")
    lines.append("")
    lines.append("> 免责声明：本报告由AI生成，仅供参考，不构成投资建议。"
                  "投资有风险，入市需谨慎。数据来源于同花顺问财。")

    return "\n".join(lines)


def run_sector_analysis(sector_key: str) -> list[dict]:
    """运行单板块完整分析"""
    print(f"\n{'#'*60}")
    print(f"#  {sector_key} 板块选股分析（牛市版）")
    print(f"{'#'*60}")

    # Step 1: 快速初筛
    candidates = quick_filter(sector_key)
    if not candidates:
        print(f"\n  {sector_key} 板块无符合条件的候选股")
        return []

    # Step 2: 获取大盘状态
    print(f"\n  获取大盘状态...")
    market_status = get_market_index_status()
    print(f"  大盘趋势: {market_status.get('trend', 'unknown')}")

    # Step 3: 深度分析每只候选股
    results = []
    for i, cand in enumerate(candidates):
        print(f"\n--- [{i+1}/{len(candidates)}] ---")
        try:
            result = analyze_stock(cand, market_status)
            results.append(result)
        except Exception as e:
            print(f"  分析失败: {e}")

    # Step 4: 按综合评分排序
    results.sort(key=lambda r: r["comprehensive_score"], reverse=True)

    print(f"\n{'='*60}")
    print(f"  {sector_key} 板块排名结果（Top 10）:")
    print(f"{'='*60}")
    for i, r in enumerate(results[:10]):
        print(f"  {i+1}. {r['code']} {r['name']} | "
              f"综合: {r['comprehensive_score']} | "
              f"基本面: {r['fundamental']['total_score']} | "
              f"技术面: {r['technical']['total_score']} | "
              f"消息面: {r['news']['total_score']}")

    return results


def save_report(result: dict) -> str:
    """保存单只股票详细报告"""
    os.makedirs("output", exist_ok=True)
    code = result["code"]
    filename = f"output/{code}_{result['name']}_report.md"
    content = generate_report(result)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def save_sector_summary(sector_key: str, results: list[dict]) -> str:
    """保存板块汇总报告"""
    os.makedirs("output", exist_ok=True)
    filename = f"output/{sector_key}_summary.md"
    lines = []
    lines.append(f"# {sector_key} 板块选股汇总（牛市版）")
    lines.append(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**候选股数量**: {len(results)}")
    lines.append("")
    lines.append("## 排名")
    lines.append("| 排名 | 代码 | 名称 | 综合 | 基本面 | 技术面 | 消息面 | 推荐 |")
    lines.append("|------|------|------|------|--------|--------|--------|------|")
    for i, r in enumerate(results):
        lines.append(
            f"| {i+1} | {r['code']} | {r['name']} | "
            f"{r['comprehensive_score']} | "
            f"{r['fundamental']['total_score']} | "
            f"{r['technical']['total_score']} | "
            f"{r['news']['total_score']} | "
            f"{r['recommendation']} |"
        )
    lines.append("")
    lines.append("## 前3名详细报告")
    for r in results[:3]:
        lines.append(f"- [{r['code']} {r['name']}]({r['code']}_{r['name']}_report.md) - {r['comprehensive_score']}分")
    lines.append("")
    lines.append("> 数据来源：同花顺问财 SkillHub")

    content = "\n".join(lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename
