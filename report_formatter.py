#!/usr/bin/env python3
"""
Report Formatter: 將 JSON 輸出格式化為原始完整報告
支援所有 16 檔股票的完整表格輸出
"""

import json
import sys
import os
from datetime import datetime

def format_report(data, today):
    """將 JSON 資料格式化為原始完整報告"""
    
    SECTOR_EMOJI = {
        'Semiconductor': '🔴', 'AI/Tech': '🟠', 'Cloud/AI': '🟠',
        'Cloud': '🔵', 'Biotech': '🟣', 'Consumer': '🟤', 'EV': '🟡',
        'Utilities': '⚫', 'ETF': '⚪', 'Unknown': '⬜'
    }
    
    lines = []
    lines.append("=" * 60)
    lines.append("Sell Put 評分模型 v5.0 Skill")
    lines.append("=" * 60)
    lines.append(f"執行日期: {today.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"股票數量: {len(data['stocks'])} 檔")
    lines.append("")
    
    # 完整排名表格（所有 16 檔）
    lines.append("【排名報告 v5.0】")
    header = f"{'#':<3} {'代碼':<6} {'等':<2} {'總分':>5} {'現價':>7} {'IV%':>5} {'HV%':>5} {'PE':>5} {'RSI':>5} {'距低%':>6} {'DTE':>8} {'履約價':>8} {'年化%':>7} {'倉位':>5} {'時機':<5} {'⚠️'}"
    lines.append(header)
    lines.append("-" * 150)
    
    def calc_position(r):
        adj = r['adj_total']
        ann = r.get('annual_return', 0) or 0
        if adj >= 80 and ann >= 80: return "5%"
        elif adj >= 80: return "4%"
        elif adj >= 70: return "4%" if ann >= 80 else "3%"
        elif adj >= 60: return "3%" if ann >= 80 else "2%"
        elif adj >= 50: return "2%"
        return "1%"
    
    def dte_display(r, today):
        opt = r.get('option', {})
        # 有財報：顯示距財報天數
        earnings_days = r.get('days_to_earnings', 999)
        if earnings_days < 0:
            return "財報已過"
        elif 0 <= earnings_days < 999:
            return f"財{int(earnings_days)}天"
        # 無財報：顯示 DTE
        if opt.get('dte', 0) > 0:
            return f"{opt['dte']}D"
        return "(無財報)"
    
    def pe_display(r):
        fwd = r.get('fwd_pe')
        ttm = r.get('ttm_pe')
        if fwd and (fwd < 10 or fwd > 50):
            if ttm and ttm > 0:
                return f"{fwd:.0f}*/{ttm:.0f}"
            return f"{fwd:.0f}*"
        if fwd and fwd > 0:
            return f"{fwd:.0f}"
        if ttm and ttm > 0:
            return f"{ttm:.0f}†"
        return "N/A"
    
    def build_warnings(r):
        parts = []
        metrics = r.get('metrics', {})
        scores = r.get('scores', {})
        
        if r.get('stock', {}).get('rsi', 0) > 70:
            parts.append("過熱")
        
        iv = r.get('option', {}).get('iv', 0)
        mkt_cap = r.get('metrics', {}).get('mkt_cap', 0)
        if iv > 80 and mkt_cap < 100e9:
            parts.append("高IV低流動")
        
        if r.get('days_to_earnings', 999) <= 7:
            parts.append("財報")
        
        return " / ".join(parts) if parts else ""
    
    for i, r in enumerate(data['stocks'], 1):
        stock = r.get('stock', {})
        opt = r.get('option', {})
        metrics = r.get('metrics', {})
        scores = r.get('scores', {})
        
        price = r.get('price', 0)
        price_str = f"{price:.2f}" if price and price > 0 else "N/A"
        
        # PE
        pe_str = pe_display(r)
        
        # RSI
        rsi_str = f"{r.get('rsi', 0) or 0:.0f}"
        
        # 距低%
        dist_low = r.get('dist_low', 0) or 0 or 0
        
        # DTE
        dte_str = dte_display(r, today)
        
        # 履約價
        strike = opt.get('strike', 0)
        strike_str = f"{strike:.0f}" if strike else "N/A"
        
        # 年化%
        ann = r.get('annual_return', 0) or 0
        ann_str = f"{ann:.1f}"
        
        # 倉位
        pos_str = calc_position(r)
        
        # 時機
        timing_str = r.get('timing', 'N/A') or 'N/A'
        
        # 警告
        warn_str = build_warnings(r)
        
        # tier
        tier = opt.get('tier', 'unknown')
        tier_mark = "" if tier == 'real' else f"⚠️t{{tier}}"
        
        forbid_mark = "🚫" if r.get('is_forbidden') else ""
        
        iv_val = opt.get('iv', 0)
        iv_str = f"{iv_val:.1f}" if iv_val > 0 else "N/A"
        hv_val = r.get('hv', 0)
        
        lines.append(f"{i:<3} {r['ticker']:<6} {r['grade']:<2} {r['adj_total']:>5.1f} {price_str:>7} {iv_str:>5} {hv_val:>5.1f} {pe_str:>6} {rsi_str:>5} {dist_low:>6.1f} {dte_str:>8} {strike_str:>8} {ann_str:>7} {pos_str:>5} {timing_str:<5} {warn_str}{forbid_mark}{tier_mark}")
    
    lines.append("─" * 150)
    lines.append("📌 過熱 = RSI>70，短線回檔風險高")
    lines.append("📌 PE* = Forward PE，可能失真（<10=極低預期成長，>50=虧損或週期股）")
    lines.append("📌 PE† = TTM PE（Forward N/A）")
    lines.append("📌 高IV低流動 = IV>80% 且市值<$100B，流動性風險高")
    lines.append("📌 履約價 = 現價 × 0.92（8% OTM）")
    lines.append("📌 年化% ≈ IV×0.05×√(DTE/365)×100（實際權利金約為理論最大值的 10-15%）")
    lines.append("📌 倉位% = 根據總分(A/B/C/D)與年化%連動計算，1-5%")
    lines.append("📌 時機：短線(DTE<14+RSI>60) / 波段(DTE 14-45) / 長期(DTE>45)")
    lines.append("📌 ⚠️t2 = lastPrice BSM回算 / ⚠️t3 = HV×1.3估算（t1=真實報價，正常顯示）")
    lines.append("")
    
    # VIX info
    lines.append(f"VIX: {data['vix']:.1f}（{data['vix_label']}）")
    lines.append("")
    
    # ============ 微信通知格式（還原）============
    lines.append("=" * 60)
    lines.append("【微信通知格式】")
    lines.append("=" * 60)
    
    a_stocks = [s for s in data['stocks'] if s['grade'] == 'A'][:8]
    lines.append(f"📊 Sell Put v5.0 | {today.strftime('%Y-%m-%d')} | VIX={data['vix']:.1f}")
    lines.append("")
    lines.append(f"A級 TOP {len(a_stocks)}:")
    
    for i, s in enumerate(a_stocks, 1):
        forbid = "🚫" if s['is_forbidden'] else ""
        # IV/HV：優先用 metrics，否則從表格欄位反算
        iv_hv_ratio = s.get('metrics', {}).get('iv_hv_ratio', 0)
        if not iv_hv_ratio:
            opt_iv = s.get('option', {}).get('iv', 0)
            hv_val = s.get('hv', 0)
            if hv_val > 0 and opt_iv > 0:
                iv_hv_ratio = opt_iv / hv_val
            elif hv_val > 0:
                iv_hv_ratio = s.get('metrics', {}).get('iv_hv_ratio', 0)
        lines.append(f"{i}. {s['ticker']} {s['sector'][:4]} {s['grade']} {s['adj_total']:.0f}分 IV/HV={iv_hv_ratio:.2f} {forbid}")
    
    # Forbidden
    forbidden = [s for s in data['stocks'] if s['is_forbidden']]
    if forbidden:
        lines.append("")
        lines.append(f"🚫 禁止新倉: {', '.join(s['ticker'] for s in forbidden)}")
    
    # Low fundamental
    low_fund = [s for s in data['stocks'] if s.get('scores', {}).get('s3', 0) < 10]
    if low_fund:
        lines.append("")
        lines.append(f"⚠️ 基本面<10分: {', '.join(s['ticker'] for s in low_fund)}")
    
    return "\n".join(lines)


def main():
    """主入口：執行報告生成（JSON 模式）"""
    import subprocess
    result = subprocess.run(
        ['python3', 'run.py', '--json'],
        capture_output=True, text=True, timeout=300,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env={**os.environ, "PYTHONPATH": os.path.dirname(os.path.abspath(__file__))}
    )
    if result.returncode != 0:
        print(f"❌ 執行失敗: {result.stderr}")
        sys.exit(1)
    try:
        data = json.loads(result.stdout)
        today = datetime.now()
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失敗: {e}")
        sys.exit(1)
    print(format_report(data, today))

if __name__ == "__main__":
    main()
