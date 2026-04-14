#!/usr/bin/env python3
"""
Sell Put Ranking v5.0 - CLI Entry Point
增強版顯示報告（8大新功能）

使用方法：
python3 run.py
python3 run.py TSLA,NVDA,AMD
"""

import sys
import os
from datetime import datetime

# 添加父目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import main, calculate_all, STOCKS


def format_report(results):
    """格式化輸出 v5.0 增強報告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # === Header ===
    header = f"📊 Sell Put 候選排名 v5.0（{now}）\n"

    # === 欄位說明 ===
    # 代碼 等 總分 現價 IV% HV% PE RSI 距低% DTE 履約價 ⚠️ 年化% 倉位 趨 板塊 時機 財報
    header += "\n"
    header += "| 代碼   |等| 總分 |   現價 | IV% | HV% |   PE |  RSI | 距低% |DTE|   履約價 | ⚠️ | 年化% | 倉位 | 趨 | 板塊 | 時機 |  財報 |\n"
    header += "|------|--|----|------|----|----|------|------|------|---|--------|---|------|----|---|----|------|------|\n"

    rows = []
    for r in results:
        # 等級 emoji
        eq_map = {"A+": "⭐", "A": "✅", "B": "🟡", "C": "⚠️", "D": "❌"}
        eq = eq_map.get(r["risk_rating"], "❓")

        # 排名趨勢
        trend = r["rank_change"]

        # PE 顯示
        pe_str = f"{r['pe']:.0f}" if r["pe"] else "N/A"

        # 財報日期
        earnings = r["earnings_date"] if r["earnings_date"] else "-"

        # 倉位
        pos = f"{r['position_size']}%"

        row = f"| {r['symbol']:<5} | {eq:2} | **{r['score']['total']:>3}** | ${r['price']:>6.2f} | {r['iv']:>4.1f}% | {r['hv']:>4.1f}% | {pe_str:>5} | {r['rsi']:>5.1f} | {r['dist_52w_low_pct']:>5.1f}% | {r['dte']:>3} | ${r['strike']:>6.2f} | ⚠️ | {r['annualized']:>5.1f}% | {pos:>4} | {trend:>3} | {r['sector_emoji']}  | {r['entry_timing']:>4} | {earnings:>6} |"
        rows.append(row)

    body = "\n".join(rows)

    # === 評分明細 ===
    detail_header = "\n\n【評分明細】"
    detail_rows = []
    for r in results:
        s = r["score"]
        detail = f"  {r['rank']:2}. {r['symbol']:<5} | 總分 {s['total']:3} | 距低={s['①距低點']:2} IV/HV={s['②IV/HV']:2} 基本面={s['③基本面']:2} RSI={s['④RSI']:2} 流動={s['⑤流動性']:2} 期權={s['⑥期權流']:2} 事件={s['⑦事件']:2} 效率={s['⑧效率']:2} 位置={s['⑨位置']:2} Skew={s['⑩Skew']:2}"
        detail_rows.append(detail)
    detail_body = "\n".join(detail_rows)

    # === 底部說明 ===
    explanation = f"""
【新增功能說明】

📌 履約價計算：履約價 = 現價 × 0.92（8% OTM）
📈 年化%：(權利金/履約價) / (DTE/365) × 100
🎯 評級：A+=年化/IV≥3.0 / A≥2.0 / B≥1.0 / C≥0.5 / D<0.5
📊 倉位：根據 VIX 和總分調整（1-5%）
🔄 趨勢：↑排名上升 / ↓排名下降 / →排名不變
⏱️ 時機：短線(DTE<14+RSI>60) / 波段(DTE 14-45) / 長期(DTE>45)
📅 財報：下次財報日期（mm/dd 格式）
🔴 半導體 🟠 AI/晶片 🔵 雲端 🟢 消費 🟡 電動車 ⚪ ETF

【v5.0 評分結構（100分）】
①距低點(23) + ②IV/HV(18) + ③基本面(28) + ④RSI(9) + ⑤流動性(8)
+ ⑥期權流(9) + ⑦事件(5) + ⑧效率(9) + ⑨位置(4) + ⑩Skew(4) = 100

⚠️ 注意：此報告僅供參考，不構成投資建議。選擇權交易風險極高。
"""

    return header + "\n" + body + detail_header + "\n" + detail_body + explanation


def main_cli():
    if len(sys.argv) > 1:
        stocks = [s.strip().upper() for s in sys.argv[1].split(",")]
        results = []
        for symbol in stocks:
            if symbol in STOCKS:
                result = calculate_all(symbol)
                if result:
                    results.append(result)
            else:
                print(f"⚠️ 股票 {symbol} 不在清單中")
    else:
        results = main()

    if not results:
        print("❌ 沒有可顯示的結果")
        return

    # 按總分排序
    results.sort(key=lambda x: x["score"]["total"], reverse=True)

    # 重新計算排名
    for i, r in enumerate(results):
        r["rank"] = i + 1

    print(format_report(results))


if __name__ == "__main__":
    main_cli()
