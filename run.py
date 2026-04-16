#!/usr/bin/env python3
"""
Sell Put v5.0 Skill CLI 入口
執行完整評分流程並生成 Excel
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from core import SellPutV5Skill
from excel_gen import generate_excel

# 預設股票清單
DEFAULT_TICKERS = ['MU','TSM','AVGO','AMD','NVDA','MRVL','ALAB','GOOGL','VST','AAPL','AMZN','ARM','MSFT','INTC','TSLA','QQQ']


def to_dict(r, today):
    """將 ScoreResult 攤平為 report_formatter.py 所需的格式"""
    return {
        'ticker': r.ticker,
        'grade': r.grade,
        'adj_total': r.adj_total,
        'raw_total': r.raw_total,
        'scores': r.scores,
        'price': r.stock.price,
        'hv': r.stock.hv,
        'fwd_pe': r.stock.fwd_pe,
        'ttm_pe': r.stock.ttm_pe,
        'rsi': r.stock.rsi,
        'dist_low': r.metrics.get('dist_low', 0) if r.metrics else 0,
        'timing': r.metrics.get('timing', 'N/A') if r.metrics else 'N/A',
        'is_forbidden': r.is_forbidden,
        'annual_return': r.metrics.get('annual_return', 0) if r.metrics else 0,
        'suggested_strike': r.suggested_strike,
        'sector': r.sector,
        'days_to_earnings': r.metrics.get('days_to_earnings', 999) if r.metrics else 999,
        'iv_hv_ratio': r.metrics.get('iv_hv_ratio', 0) if r.metrics else 0,
        'rocc_raw': r.metrics.get('rocc_raw', 0) if r.metrics else 0,
        'rocc_adj': r.metrics.get('rocc_adj', 0) if r.metrics else 0,
        'pop': r.metrics.get('pop', 0) if r.metrics else 0,
        'efficiency': r.metrics.get('efficiency', 0) if r.metrics else 0,
        'stock': {
            'price': r.stock.price,
            'rsi': r.stock.rsi,
            'mkt_cap': r.stock.mkt_cap,
            'earnings_date': r.stock.earnings_date.isoformat() if r.stock.earnings_date else None,
        },
        'option': {
            'iv': r.option.iv if r.option else 0,
            'tier': getattr(r.option, 'tier', 'unknown') if r.option else 'unknown',
            'strike': r.option.strike if r.option else 0,
            'dte': r.option.dte if r.option else 0,
            'exp': r.option.exp if r.option else None,
            'bid': r.option.bid if r.option else 0,
            'ask': r.option.ask if r.option else 0,
            'delta': getattr(r.option, 'delta', 0) if r.option else 0,
            'theta': getattr(r.option, 'theta', 0) if r.option else 0,
            'vega': getattr(r.option, 'vega', 0) if r.option else 0,
            'strike_deviation': getattr(r.option, 'strike_deviation', 0) if r.option else 0,
        },
    }


def main():
    """主入口"""
    # 解析參數
    json_mode = '--json' in sys.argv
    tickers = [a for a in sys.argv[1:] if not a.startswith('--') and a not in ['run.py', 'main.py']]
    if not tickers:
        tickers = DEFAULT_TICKERS

    today = datetime.now()

    # 執行評分
    skill = SellPutV5Skill(tickers, today)
    results = skill.run()

    if json_mode:
        # JSON 模式：供 report_formatter.py 使用
        output = {
            'vix': skill.vix,
            'vix_label': skill.vix_label,
            'vix_reg': skill.vix_reg,
            'vix_adj': skill.vix_adj,
            'pos_scale': skill.pos_scale,
            'date': today.strftime('%Y-%m-%d'),
            'stocks': [to_dict(r, today) for r in results],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 純文字模式
    print("="*60)
    print("Sell Put 評分模型 v5.0 Skill")
    print("="*60)
    print(f"執行日期: {today.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"股票數量: {len(results)} 檔")
    print()
    print(f"\n評分完成: {len(results)} 檔")
    print()

    def _build_warnings(r):
        parts = []
        if r.stock.rsi > 70:
            parts.append("過熱")
        if r.metrics and r.metrics.get('days_to_earnings', 999) <= 7:
            parts.append("財報")
        iv_val = r.option.iv if r.option else 0
        if iv_val > 80 and r.stock.mkt_cap < 100e9:
            parts.append("高IV低流動")
        return " / ".join(parts) if parts else ""

    def _dte_display(r):
        if r.stock.earnings_date:
            days_to_earn = (r.stock.earnings_date - today).days
            if days_to_earn >= 0:
                return f"財{days_to_earn}天"
        if r.option and r.option.exp:
            return f"{r.option.dte}D"
        return "(無財報)"

    # 顯示完整排名（所有 16 檔）
    print("【排名報告 v5.0】")
    header = f"{'#':<3} {'代碼':<6} {'等':<2} {'總分':>5} {'現價':>7} {'IV%':>5} {'HV%':>5} {'PE':>5} {'RSI':>5} {'距低%':>6} {'DTE':>8} {'履約價':>8} ⚠️"
    print(header)
    print("-" * 120)
    for i, r in enumerate(results, 1):
        price = r.stock.price
        price_str = f"{price:.2f}" if price and price > 0 else "N/A"

        fwd_pe = r.stock.fwd_pe
        ttm_pe = r.stock.ttm_pe
        pe_anomaly = fwd_pe and (fwd_pe < 10 or fwd_pe > 50)
        if fwd_pe and fwd_pe > 0:
            if pe_anomaly and ttm_pe and ttm_pe > 0:
                pe_str = f"{fwd_pe:.0f}*/{ttm_pe:.0f}"
            elif pe_anomaly:
                pe_str = f"{fwd_pe:.0f}*"
            else:
                pe_str = f"{fwd_pe:.0f}"
        elif ttm_pe and ttm_pe > 0:
            pe_str = f"{ttm_pe:.0f}†"
        else:
            pe_str = "N/A"

        rsi_str = f"{r.stock.rsi:.0f}"
        dist_low = r.metrics.get('dist_low', 0) if r.metrics else 0
        dte_str = _dte_display(r)
        strike_str = f"{r.suggested_strike:.0f}" if r.suggested_strike else "N/A"
        warn_str = _build_warnings(r)
        forbid_mark = "🚫" if r.is_forbidden else ""

        iv_val = r.option.iv if r.option else 0
        iv_str = f"{iv_val:.1f}" if iv_val > 0 else "N/A"
        hv_val = r.stock.hv

        print(f"{i:<3} {r.ticker:<6} {r.grade:<2} {r.adj_total:>5.1f} {price_str:>7} {iv_str:>5} {hv_val:>5.1f} {pe_str:>6} {rsi_str:>5} {dist_low:>6.1f} {dte_str:>8} {strike_str:>8} {warn_str}{forbid_mark}")

    print("─" * 120)
    print("📌 過熱 = RSI>70，短線回檔風險高")
    print("📌 PE* = Forward PE，可能失真（<10=極低預期成長，>50=虧損或週期股）")
    print("📌 PE† = TTM PE（Forward N/A）")
    print("📌 高IV低流動 = IV>80% 且市值<$100B，流動性風險高")
    print()

    # 生成 Excel
    output_dir = os.path.expanduser('~/.qclaw/workspace')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'sell_put_v5.0_{today.strftime("%Y%m%d")}.xlsx')

    print(f"生成 Excel: {output_path}")
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

    forbidden = [r for r in results if r.is_forbidden]
    if forbidden:
        print(f"\n🚫 禁止新倉: {', '.join(r.ticker for r in forbidden)}")

    low_fundamental = [r for r in results if r.scores['s3'] < 10]
    if low_fundamental:
        print(f"⚠️ 基本面<10分: {', '.join(r.ticker for r in low_fundamental)}")

    return output_path


if __name__ == '__main__':
    main()
