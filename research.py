"""
消息面分析模块（牛市版）
通过 SkillHub 获取公告、新闻、研报、事件数据
关键词匹配 + 情绪打分
牛市调整：更重视催化剂和正面动量
"""
from config import NEWS_SCORING
from data_fetcher import (
    get_stock_announcements, get_stock_news,
    get_stock_reports, get_stock_events, get_sector_news,
)


def _keyword_score(text: str) -> int:
    """对文本进行关键词扫描，返回情绪分"""
    if not text:
        return 0
    text_lower = text.lower()

    pos = sum(1 for kw in NEWS_SCORING["positive_keywords"] if kw in text)
    neg = sum(1 for kw in NEWS_SCORING["negative_keywords"] if kw in text)

    return pos - neg


def _analyze_texts(datas: list, text_fields: list = None) -> dict:
    """分析 SkillHub 返回的数据，提取情绪和关键词"""
    if text_fields is None:
        text_fields = ["title", "summary", "内容", "标题", "摘要"]

    result = {
        "count": len(datas),
        "sentiment_score": 50,  # 基准50分
        "positive_hits": [],
        "negative_hits": [],
    }

    total_sent = 0
    for item in datas:
        # 拼接所有文本字段
        full_text = ""
        for field in text_fields:
            full_text += str(item.get(field, "")) + " "

        sent = _keyword_score(full_text)
        total_sent += sent

        if sent > 0:
            title = item.get("title", item.get("标题", ""))
            if title:
                result["positive_hits"].append(title[:80])
        elif sent < 0:
            title = item.get("title", item.get("标题", ""))
            if title:
                result["negative_hits"].append(title[:80])

    # 计算情绪分（50基准，正向加分，负向减分）
    if datas:
        avg_sent = total_sent / len(datas)
        result["sentiment_score"] = min(100, max(0, 50 + avg_sent * 15))

    return result


def score_news(code: str, name: str, sector_key: str) -> dict:
    """
    综合消息面评分（满分100）
    包含：公告、新闻、研报、事件、行业动态
    """
    print(f"    获取 {name} 消息面数据...")

    # 1. 公告
    announcements = get_stock_announcements(name)
    ann_analysis = _analyze_texts(announcements)
    print(f"      公告: {ann_analysis['count']} 条, 情绪: {ann_analysis['sentiment_score']}")

    # 2. 新闻
    news = get_stock_news(name)
    news_analysis = _analyze_texts(news)
    print(f"      新闻: {news_analysis['count']} 条, 情绪: {news_analysis['sentiment_score']}")

    # 3. 研报
    reports = get_stock_reports(name)
    report_analysis = _analyze_texts(reports)
    print(f"      研报: {report_analysis['count']} 条, 情绪: {report_analysis['sentiment_score']}")

    # 4. 事件（业绩预告、解禁、质押等）
    events = get_stock_events(name)
    event_analysis = _analyze_texts(events)

    # 5. 行业动态
    sector_news = get_sector_news(sector_key)
    sector_analysis = _analyze_texts(sector_news)

    # 综合评分：公告25% + 新闻25% + 研报20% + 事件10% + 行业20%
    total = (
        ann_analysis["sentiment_score"] * 0.25 +
        news_analysis["sentiment_score"] * 0.25 +
        report_analysis["sentiment_score"] * 0.20 +
        event_analysis["sentiment_score"] * 0.10 +
        sector_analysis["sentiment_score"] * 0.20
    )

    # 汇总正面/负面关键词
    all_positive = (
        ann_analysis["positive_hits"][:3] +
        news_analysis["positive_hits"][:3] +
        report_analysis["positive_hits"][:2]
    )
    all_negative = (
        ann_analysis["negative_hits"][:2] +
        news_analysis["negative_hits"][:2] +
        report_analysis["negative_hits"][:1]
    )

    # 催化剂判断
    catalysts = []
    if ann_analysis["sentiment_score"] >= 65:
        catalysts.append("近期有利好公告")
    if report_analysis["sentiment_score"] >= 65:
        catalysts.append("券商研报偏正面")
    if sector_analysis["sentiment_score"] >= 60:
        catalysts.append("行业处于景气周期")
    if news_analysis["count"] >= 3 and news_analysis["sentiment_score"] >= 60:
        catalysts.append("媒体报道活跃且偏正面")

    risks = []
    if ann_analysis["sentiment_score"] <= 35:
        risks.append("公告信息偏负面")
    if event_analysis["sentiment_score"] <= 40:
        risks.append("有负面事件（减持/质押/处罚等）")
    if news_analysis["sentiment_score"] <= 40:
        risks.append("舆论偏负面")

    return {
        "total_score": round(total, 1),
        "announcements": {
            "count": ann_analysis["count"],
            "sentiment": ann_analysis["sentiment_score"],
            "highlights": all_positive[:3],
        },
        "news": {
            "count": news_analysis["count"],
            "sentiment": news_analysis["sentiment_score"],
        },
        "reports": {
            "count": report_analysis["count"],
            "sentiment": report_analysis["sentiment_score"],
        },
        "sector": {
            "sentiment": sector_analysis["sentiment_score"],
        },
        "catalysts": catalysts,
        "risks": risks,
        "positive_hits": all_positive[:5],
        "negative_hits": all_negative[:3],
    }
