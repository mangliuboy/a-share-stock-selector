
## 一句话概括

覆盖5大热门赛道（AI/锂电池/机器人/电力/光伏）的多因子选股系统，融合巴菲特+段永平+冯柳+戴维斯双击+欧奈尔CANSLIM五套框架，数据源为同花顺SkillHub API，输出结构化Markdown选股报告。**零外部依赖，纯Python标准库。**

## 系统架构

```
LLM投资分析/
├── config.py              # 所有可调参数（权重/阈值/关键词/板块映射）
├── skillhub_client.py     # SkillHub API 统一客户端（174行）
│                           #   - /v1/query2data（hithink-* 技能）
│                           #   - /v1/comprehensive/search（公告/新闻/研报）
├── data_fetcher.py        # 数据获取层（361行）
│                           #   - 板块成分股 / 财务数据 / 行情数据
│                           #   - 公告 / 新闻 / 研报 / 事件 / 行业动态
│                           #   - 快速初筛漏斗
├── fundamental.py         # 基本面评分（418行，100分制）
│                           #   - 巴菲特维度（ROE/毛利率/负债率/现金流）
│                           #   - 段永平维度（商业模式/PEG合理性）
│                           #   - 冯柳维度（业绩拐点/赔率/52周位置）
│                           #   - 戴维斯双击维度（盈利增速+估值扩张）
├── technical.py           # 技术面评分（343行，100分制）
│                           #   - CANSLIM 7维度（C/A/N/S/L/I/M）
│                           #   - 技术指标补充（均线/MACD/RSI）
├── research.py            # 消息面评分（157行，100分制）
│                           #   - 公告情绪 / 新闻情绪 / 研报情绪
│                           #   - 事件风险 / 行业动态
├── engine.py              # 推荐引擎（303行）
│                           #   - 单股深度分析 / 板块排名
│                           #   - 结构化报告生成 / 汇总报告
├── main.py                # 交互式菜单入口（115行）
├── skills/                # SkillHub 技能（gitignore，15个技能）
├── 基本面参考文档/          # 参考资料 PDF（gitignore）
├── 技术面参考文档/          # 参考资料 PDF（gitignore）
└── output/                # 输出报告（gitignore）
```

## 牛市版核心配置

### 综合权重

| 维度   | 权重 | 牛市逻辑                  |
| ------ | ---- | ------------------------- |
| 基本面 | 20%  | 趋势>估值，降低纯价值标准 |
| 技术面 | 45%  | 动量+领涨+新高=牛市核心   |
| 消息面 | 35%  | 催化剂敏感，正面情绪放大  |

### 基本面四框架内部分配（权重20%中的子分配）

| 框架           | 内占比  | 牛市逻辑                 |
| -------------- | ------- | ------------------------ |
| 巴菲特（价值） | 15%     | 降权：纯价值在牛市中跑输 |
| 段永平（生意） | 20%     | 商业模式质量仍有参考意义 |
| 冯柳（拐点）   | **30%** | 升权：弱转强弹性最大     |
| 戴维斯双击     | **35%** | 升权：盈利+估值双扩张    |

### CANSLIM 7维度内部分配（权重45%中的子分配）

| 维度       | 内占比  | 牛市逻辑                    |
| ---------- | ------- | --------------------------- |
| C 当期盈利 | 10%     |                             |
| A 年度盈利 | 10%     |                             |
| N 新高     | **20%** | 升权：创52周新高是牛市买点  |
| S 量价     | 15%     |                             |
| L 领涨/RS  | **20%** | 升权：相对强度>80是领涨信号 |
| I 机构认同 | 10%     |                             |
| M 大盘方向 | 15%     |                             |

### 基本面筛选阈值（牛市放宽）

| 指标         | 阈值 | vs 非牛市 |
| ------------ | ---- | --------- |
| 最低ROE      | 8%   | 10%→8%    |
| 最低营收增长 | 0%   | 不变      |
| 最高负债率   | 75%  | 70%→75%   |
| 最低毛利率   | 12%  | 15%→12%   |

## 数据流

```
用户选择板块（main.py）
    │
    ▼
quick_filter()  ──→  get_sector_stocks()    hithink-astock-selector 查概念成分股
    │                  get_stock_financial()  hithink-finance-query 查财务指标
    │                  get_market_data()     hithink-market-query 查行情数据
    │                  ROE筛选 + MA60筛选
    │
    ▼
深度分析每只候选股（engine.py → analyze_stock）
    │
    ├── score_fundamental()  → 四框架打分 × 权重 → 基本面得分
    ├── score_technical()    → CANSLIM×7 + 指标   → 技术面得分
    └── score_news()         → 公告+新闻+研报+事件+行业 → 消息面得分
    │
    ▼
加权综合(20/45/35) → 排名 → generate_report() → output/*.md
```

## 数据源：SkillHub API

全部通过 **同花顺 SkillHub OpenAPI**（`openapi.iwencai.com`）：

| 技能                    | 端点                     | 用途                      |
| ----------------------- | ------------------------ | ------------------------- |
| hithink-astock-selector | /v1/query2data           | 板块成分股筛选            |
| hithink-finance-query   | /v1/query2data           | ROE/PE/PB/增速/毛利率     |
| hithink-market-query    | /v1/query2data           | 价格/均线/资金流/RSI/MACD |
| hithink-event-query     | /v1/query2data           | 业绩预告/解禁/质押        |
| announcement-search     | /v1/comprehensive/search | 公告搜索                  |
| news-search             | /v1/comprehensive/search | 财经新闻                  |
| report-search           | /v1/comprehensive/search | 券商研报                  |

鉴权：Bearer Token（`IWENCAI_API_KEY` 环境变量）+ 7个 Claw Headers

## 运行方式

```bash
cd /Users/wutongqing/Desktop/LLM投资分析
python3 main.py
# 选择 1-5 单板块，或 6 全扫描
```

**零外部依赖**，仅需 Python 3 标准库 + `IWENCAI_API_KEY` 环境变量。

> Claude Code 沙箱阻止访问 openapi.iwencai.com，需在终端或 WorkBuddy 中运行。WorkBuddy 已验证可正常调API。

## 修改指南

| 需求                | 改哪里                                   | 示例            |
| ------------------- | ---------------------------------------- | --------------- |
| 调整三大块权重      | `config.py` → `COMPREHENSIVE_WEIGHTS`    | 基本面提到30%   |
| 调ROE门槛           | `config.py` → `FUNDAMENTAL_FILTER`       | min_roe 改到12  |
| 调基本面四框架占比  | `config.py` → `FUNDAMENTAL_WEIGHTS`      | buffett提到30%  |
| 调CANSLIM内部权重   | `config.py` → `CANSLIM_CONFIG`           | N权重降到10%    |
| 新增板块            | `config.py` → `SECTOR_MAPPING`           | 加"半导体"      |
| 修改正面/负面关键词 | `config.py` → `NEWS_SCORING`             | 加"AI赋能"      |
| 改评分公式          | `fundamental.py` / `technical.py`        | 某框架打分逻辑  |
| 加新数据源          | `data_fetcher.py` + `skillhub_client.py` | 加宏观/行业对比 |
| 改报告格式          | `engine.py` → `generate_report()`        | 加风险分析章节  |

## Git 工作流

```bash
# 改完代码后
git add -u && git commit -m "说明改了什么" && git push
```

## 验证方式

1. 单板块测试：`python3 main.py` 选 3（机器人），验证端到端
2. 检查 `output/` 目录下报告+汇总
3. 确认评分有区分度（Top3 >65分，末尾 <50分）
4. 全量5板块扫描预计 5-10 分钟

## 免责

本系统为AI辅助决策工具，不构成投资建议。投资有风险，入市需谨慎。数据来源于同花顺问财。
