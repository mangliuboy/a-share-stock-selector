#!/usr/bin/env python3
"""
A股多维度选股系统 - 主入口（牛市版）
功能：交互式菜单，按板块选股，融合基本面+技术面+消息面分析
数据源：同花顺 SkillHub API
权重：基本面20% | 技术面45% | 消息面35%
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECTOR_MAPPING
from engine import run_sector_analysis, save_report, save_sector_summary


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║      A股多维度选股系统 v2.0（牛市版）                  ║
║      基本面(巴菲特/段永平/冯柳/戴维斯双击) 20%          ║
║      技术面(CANSLIM + 动量) 45%                        ║
║      消息面(SkillHub) 35%                              ║
║      聚焦: AI | 锂电池锂矿 | 机器人 | 电力 | 光伏       ║
║      数据源: 同花顺 SkillHub API                        ║
╚══════════════════════════════════════════════════════╝
""")


def print_menu():
    print("\n请选择操作:")
    print("  1. AI 人工智能板块选股")
    print("  2. 锂电池及锂矿板块选股")
    print("  3. 机器人板块选股")
    print("  4. 电力板块选股")
    print("  5. 光伏板块选股")
    print("  6. 全部板块一键扫描")
    print("  q. 退出")
    return input("\n请输入选项: ").strip()


def run_single_sector(sector_key: str):
    """运行单板块分析并保存报告"""
    print(f"\n开始分析 {sector_key} 板块...")
    results = run_sector_analysis(sector_key)

    if not results:
        print(f"\n{sector_key} 板块无符合条件的股票。")
        return

    # 保存Top 5详细报告
    for r in results[:5]:
        filepath = save_report(r)
        print(f"  详细报告已保存: {filepath}")

    # 保存板块汇总
    summary_path = save_sector_summary(sector_key, results)
    print(f"  板块汇总已保存: {summary_path}")

    print(f"\n{sector_key} 板块分析完成！")


def run_all_sectors():
    """一键扫描所有5个板块"""
    sectors = list(SECTOR_MAPPING.keys())
    for i, sector_key in enumerate(sectors, 1):
        print(f"\n{'*'*60}")
        print(f"*  [{i}/{len(sectors)}] 正在分析: {sector_key}")
        print(f"{'*'*60}")
        run_single_sector(sector_key)

    print(f"\n{'='*60}")
    print("全部板块扫描完成！结果保存在 output/ 目录下")
    print(f"{'='*60}")


def main():
    print_banner()

    # 检查 API Key
    api_key = os.environ.get("IWENCAI_API_KEY", "")
    if not api_key:
        print("错误: 请先设置 IWENCAI_API_KEY 环境变量")
        print("  export IWENCAI_API_KEY='your_api_key_here'")
        print("获取方式: https://www.iwencai.com/skillhub → 登录 → 复制API Key")
        sys.exit(1)
    print(f"API Key 已配置: {api_key[:20]}...")

    # 创建输出目录
    os.makedirs("output", exist_ok=True)

    sector_key_map = {
        "1": "AI",
        "2": "锂电池及锂矿",
        "3": "机器人",
        "4": "电力",
        "5": "光伏",
    }

    while True:
        choice = print_menu()

        if choice == "q":
            print("再见！")
            break
        elif choice == "6":
            run_all_sectors()
        elif choice in sector_key_map:
            run_single_sector(sector_key_map[choice])
        else:
            print("无效选项，请重新选择")


if __name__ == "__main__":
    main()
