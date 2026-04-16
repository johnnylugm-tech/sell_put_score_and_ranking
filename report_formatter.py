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
    header = f"{'#':<3} {'代碼':<6} {'等':<2} {'總分':>5} {'現價':>7} {'IV%':>5} {'HV%':>5} {'IV/HV':>6} {'Delta':>5} {'Theta':>5} {'Gamma':>6} {'Vega':>5} {'Sprd%':>6} {'年化%(理論)':>11} {'MEff':>6} {'PE':>5} {'RSI':>5} {'距低%':>6} {'DTE':>8} {'履約價':>8} {'倉位':>5} {'時機':<5} {'⚠️'}"
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

        # IV低估：IV/HV < 0.2 且 HV > 30（市場定價嚴重偏低）
        hv_val = r.get('hv', 0) or 0
        opt_iv_val = r.get('option', {}).get('iv', 0) or 0
        if hv_val > 30 and 0 < opt_iv_val < hv_val * 0.2:
            parts.append("IV低估")
        # IV異常：IV/HV < 0.1（極度偏離）或 IV > HV×3（估計值疑似錯誤）
        if hv_val > 10 and 0 < opt_iv_val < hv_val * 0.1:
            if "IV低估" not in parts:
                parts.append("IV低估")

        # 數據不穩：tier=t3（HV×1.3估算，非真實報價）
        tier = r.get('option', {}).get('tier', 'unknown')
        if tier == 't3':
            parts.append("數據不穩")

        # Merge with ScoreResult.warnings (板塊集中, Put覆蓋財報, etc.)
        extra_warns = r.get('warnings', [])
        for w in extra_warns:
            # Strip the ⚠️ prefix if present
            w_clean = w.replace('⚠️', '').strip()
            if w_clean and w_clean not in parts:
                parts.append(w_clean)

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
        
        # 年化%（顯示理論值與合理區間；min<1時顯示 <1）
        ann = r.get('annual_return', 0) or 0
        ann_min = round(ann * 0.10, 1)
        ann_max = round(ann * 0.15, 1)
        if ann_min < 1:
            ann_str = f"{ann:.0f}(<1)"
        else:
            ann_str = f"{ann:.0f}({ann_min:.0f}-{ann_max:.0f})"
        
        # 倉位
        pos_str = calc_position(r)
        
        # 時機
        timing_str = r.get('timing', 'N/A') or 'N/A'
        
        # 警告
        warn_str = build_warnings(r)
        
        # tier
        tier = opt.get('tier', 'unknown')
        tier_mark = "" if tier in ('real', 't1') else f"⚠️{tier}"
        
        forbid_mark = "🚫" if r.get('is_forbidden') else ""
        
        iv_val = opt.get('iv', 0)
        iv_str = f"{iv_val:.1f}" if iv_val > 0 else "N/A"
        hv_val = r.get('hv', 0)
        # IV/HV ratio
        opt_iv_val = r.get('option', {}).get('iv', 0) or 0
        if hv_val > 0 and opt_iv_val > 0:
            iv_hv_str = f"{opt_iv_val/hv_val:.2f}"
        else:
            iv_hv_str = "-"

        # Delta
        delta_val = opt.get('delta', 0) or 0
        delta_str = f"{delta_val:.2f}"
        theta_val = opt.get('theta', 0) or 0
        theta_str = f"{theta_val:.2f}" if abs(theta_val) > 0.001 else "0.00"
        vega_val = opt.get('vega', 0) or 0
        vega_str = f"{vega_val:.2f}" if abs(vega_val) > 0.001 else "0.00"
        # Gamma
        gamma_val = opt.get('gamma', 0) or 0
        gamma_str = f"{gamma_val:.4f}" if abs(gamma_val) > 0.0001 else "0.0000"

        # Spread%（若未提供則從 bid/ask 計算）
        spread_val = opt.get('spread', 0) or 0
        if spread_val == 0:
            bid = opt.get('bid', 0) or 0
            ask = opt.get('ask', 0) or 0
            if ask > 0 and bid > 0:
                mid = (bid + ask) / 2
                if mid > 0:
                    spread_val = (ask - bid) / mid * 100
        spread_str = f"{spread_val:.1f}" if spread_val > 0 else "0.0"

        # Margin Efficiency
        margin_eff = r.get('margin_efficiency', 0) or 0
        margin_eff_str = f"{margin_eff:.1f}" if margin_eff > 0 else "0.0"

        # Strike偏離警告
        strike_dev = opt.get('strike_deviation', 0) or 0
        strike_warn = ""
        if strike_dev > 0.02:
            strike_warn = "ITM"
        elif strike_dev < -0.05:
            strike_warn = "深OTM"

        lines.append(f"{i:<3} {r['ticker']:<6} {r['grade']:<2} {r['adj_total']:>5.1f} {price_str:>7} {iv_str:>5} {hv_val:>5.1f} {iv_hv_str:>6} {delta_str:>5} {theta_str:>5} {gamma_str:>6} {vega_str:>5} {spread_str:>6} {ann_str:>11} {margin_eff_str:>6} {pe_str:>5} {rsi_str:>5} {dist_low:>6.1f} {dte_str:>8} {strike_str:>8} {pos_str:>5} {timing_str:<5} {warn_str}{strike_warn}{forbid_mark}{tier_mark}")
    
    lines.append("─" * 250)
    lines.append("📌 過熱 = RSI>70，短線回檔風險高")
    lines.append("📌 PE* = Forward PE，可能失真（<10=極低預期成長，>50=虧損或週期股）")
    lines.append("📌 PE† = TTM PE（Forward N/A）")
    lines.append("📌 高IV低流動 = IV>80% 且市值<$100B，流動性風險高")
    lines.append("📌 履約價 = 現價 × 0.92（8% OTM）")
    lines.append("📌 年化% = IV×0.05×√(DTE/365)×100×(1-Spread%)；>100% 為理論值，括弧內為合理區間（×10-15%）")
    lines.append("📌 倉位% = 根據總分(A/B/C/D)與年化%連動計算，1-5%")
    lines.append("📌 時機：短線(DTE<14+RSI>60) / 波段(DTE 14-45) / 長期(DTE>45)")
    lines.append("📌 ⚠️ = 有警告（過熱/財報🚫/IV低估/IV異常/ITM/數據不穩/板塊集中等）；ITM = 履約價高於現價，Delta>0.55，風險較高")
    lines.append("")
    
    # VIX info
    lines.append(f"VIX: {data['vix']:.1f}（{data['vix_label']}）")
    lines.append("")
    # ============ 組合風險摘要（R-E）============    forbidden_count = sum(1 for r in data["stocks"] if r.get("is_forbidden", False))    high_spread_tickers = [r["ticker"] for r in data["stocks"] if float(r.get("option", {}).get("spread", 0) or 0) > 10 and not r.get("is_forbidden", False)]    lines.append("")    lines.append("【組合風險摘要】")    lines.append(f"🚫 禁止新倉: {forbidden_count} 檔")    if high_spread_tickers:        lines.append(f"⚠️ 高Spread(>10%): {", ".join(high_spread_tickers)}")    
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
        # IV/HV：直接從表格欄位計算（HV 和 IV 都必定存在）
        hv_val = s.get('hv', 0) or 0
        opt_iv_val = s.get('option', {}).get('iv', 0) or 0
        if hv_val > 0 and opt_iv_val > 0:
            iv_hv_ratio = round(opt_iv_val / hv_val, 2)
        else:
            iv_hv_ratio = s.get('metrics', {}).get('iv_hv_ratio', 0) or 0
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
    
    lines.append("📌 最大虧損 ≈ 現價 - 履約價（被指派時）；Delta 為期權價格對標的價格變化的敏感度（賣Put適用範圍 0.2-0.5）")
    lines.append("📌 Delta = 標的+$1 時期權變化；Delta 絕對值越大（→0.5）= ATM/ITM 程度越高，風險越大；Theta = 每日時間衰減（$）；Gamma = Delta對標的$1變化的加速率；Vega = IV+1% 時權利金變化；IV低估 = IV/HV<0.2（市場低估）；IV異常 = IV/HV<0.1（數據可能失效）；Margin_Eff = 年化淨回報相對於20%保證金的效率")
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


