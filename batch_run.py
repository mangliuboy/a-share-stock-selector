#!/usr/bin/env python3
"""
批量执行全部5个板块选股扫描（免交互式菜单）
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECTOR_MAPPING
from engine import run_sector_analysis, save_report, save_sector_summary

def run_all_sectors():
    sectors = list(SECTOR_MAPPING.keys())
    all_results = {}
    total_start = time.time()

    for i, sector_key in enumerate(sectors, 1):
        print(f"\n{'*'*60}")
        print(f"*  [{i}/{len(sectors)}] 正在分析: {sector_key}")
        print(f"{'*'*60}")

        sector_start = time.time()
        try:
            results = run_sector_analysis(sector_key)
            elapsed = time.time() - sector_start
            print(f"\n## {sector_key} 板块完成！耗时 {elapsed:.1f}秒，共 {len(results)} 只候选股")

            if results:
                # 保存Top 5详细报告
                for r in results[:5]:
                    filepath = save_report(r)
                    print(f"  详细报告: {filepath}")

                # 保存板块汇总
                summary_path = save_sector_summary(sector_key, results)
                print(f"  板块汇总: {summary_path}")

                all_results[sector_key] = {
                    "count": len(results),
                    "top": [
                        {"code": r["code"], "name": r["name"],
                         "score": r["comprehensive_score"],
                         "rec": r["recommendation"]}
                        for r in results[:3]
                    ]
                }
            else:
                print(f"  无符合条件的股票")
                all_results[sector_key] = {"count": 0, "top": []}

        except Exception as e:
            elapsed = time.time() - sector_start
            print(f"\n## {sector_key} 板块分析失败！耗时 {elapsed:.1f}秒")
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()
            all_results[sector_key] = {"count": 0, "top": [], "error": str(e)}

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  全部板块扫描完成！总耗时: {total_elapsed:.1f}秒")
    print(f"{'='*60}")

    # 打印总览
    print("\n## 扫描总结\n")
    for sector_key, info in all_results.items():
        print(f"  {sector_key}: {info['count']}只候选股")
        for t in info["top"]:
            print(f"    {t['code']} {t['name']} - {t['score']}分 [{t['rec']}]")

    print(f"\n报告保存在 output/ 目录下")

if __name__ == "__main__":
    run_all_sectors()
