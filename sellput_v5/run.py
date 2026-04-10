#!/usr/bin/env python3
"""
Sell Put v5.0 Skill CLI 入口
執行完整評分流程並生成 Excel
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from core import SellPutV5Skill
from excel_gen import generate_excel

# 預設股票清單
DEFAULT_TICKERS = ['MU','TSM','AVGO','AMD','NVDA','MRVL','ALAB','GOOGL','VST','AAPL','AMZN','ARM','MSFT','INTC','TSLA','QQQ']


def main():
    """主入口"""
    print("="*60)
    print("Sell Put 評分模型 v5.0 Skill")
    print("="*60)
    
    today = datetime.now()
    print(f"執行日期: {today.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"股票數量: {len(DEFAULT_TICKERS)} 檔")
    print()
    
    # 執行評分
    skill = SellPutV5Skill(DEFAULT_TICKERS, today)
    results = skill.run()
    
    print(f"\n評分完成: {len(results)} 檔")
    print()
    
    # 顯示排名
    print("【排名】")
    print(f"{'排名':<4} {'Ticker':<7} {'Sector':<14} {'等級':<4} {'總分':>6} {'IV/HV':>7} {'DTE':>4}")
    print("-" * 55)
    for i, r in enumerate(results[:10], 1):
        forbid = "🚫" if r.is_forbidden else ""
        print(f"{i:<4} {r.ticker:<7} {r.sector:<14} {r.grade:<4} {r.adj_total:>6.1f} {r.metrics.get('iv_hv_ratio', 0):>6.2f} {r.option.dte:>4} {forbid}")
    
    # 生成 Excel
    output_dir = os.path.expanduser('~/.qclaw/workspace')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'sell_put_v5.0_{today.strftime("%Y%m%d")}.xlsx')
    
    print(f"\n生成 Excel: {output_path}")
    generate_excel(
        results=results,
        vix=skill.vix,
        vix_reg=skill.vix_reg,
        vix_adj=skill.vix_adj,
        pos_scale=skill.pos_scale,
        vix_label=skill.vix_label,
        today=today,
        output_path=output_path
    )
    
    print(f"✅ 完成: {output_path}")
    
    # 輸出微信通知格式
    print("\n" + "="*60)
    print("【微信通知格式】")
    print("="*60)
    
    a_grade = [r for r in results if r.grade == 'A'][:8]
    print(f"📊 Sell Put v5.0 | {today.strftime('%Y-%m-%d')} | VIX={skill.vix:.1f}")
    print(f"\nA級 TOP {len(a_grade)}:")
    for i, r in enumerate(a_grade, 1):
        forbid = "🚫" if r.is_forbidden else ""
        print(f"{i}. {r.ticker} {r.sector[:4]} {r.grade} {r.adj_total:.0f}分 IV/HV={r.metrics.get('iv_hv_ratio', 0):.2f} {forbid}")
    
    # 風險標記
    forbidden = [r for r in results if r.is_forbidden]
    if forbidden:
        print(f"\n🚫 禁止新倉: {', '.join(r.ticker for r in forbidden)}")
    
    low_fundamental = [r for r in results if r.scores['s3'] < 10]
    if low_fundamental:
        print(f"⚠️ 基本面<10分: {', '.join(r.ticker for r in low_fundamental)}")
    
    return output_path


if __name__ == '__main__':
    main()
