#!/usr/bin/env python3
"""
单板块执行脚本 - 用于调试和测试
用法: python3 run_one.py [板块key]
示例: python3 run_one.py AI
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECTOR_MAPPING
from engine import run_sector_analysis, save_report, save_sector_summary

sector_key = sys.argv[1] if len(sys.argv) > 1 else "AI"

if sector_key not in SECTOR_MAPPING:
    print(f"未知板块: {sector_key}")
    print(f"可选: {list(SECTOR_MAPPING.keys())}")
    sys.exit(1)

results = run_sector_analysis(sector_key)

if not results:
    print(f"\n{sector_key} 板块无符合条件的股票。")
else:
    for r in results[:5]:
        filepath = save_report(r)
        print(f"  详细报告已保存: {filepath}")

    summary_path = save_sector_summary(sector_key, results)
    print(f"  板块汇总已保存: {summary_path}")

print(f"\n{sector_key} 板块分析完成！")
