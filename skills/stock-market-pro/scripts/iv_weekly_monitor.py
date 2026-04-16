#!/usr/bin/env python3
"""
IV History Weekly Monitor - 每週監測並總結 IV 資料庫狀態
"""

import yfinance as yf
import json
import os
from datetime import datetime, date, timedelta
from pathlib import Path

DB_PATH = os.path.expanduser("~/.openclaw/workspace-option/memory/iv_database.json")

TICKERS = [
    'MU', 'TSM', 'AVGO', 'AMD', 'NVDA', 'MRVL', 'ALAB',
    'GOOGL', 'VST', 'AAPL', 'AMZN', 'ARM', 'MSFT', 'INTC', 'TSLA', 'QQQ'
]

def load_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'r') as f:
            return json.load(f)
    return {"updated": None, "stocks": {}}

def get_current_price(ticker):
    """取得即時報價"""
    try:
        tk = yf.Ticker(ticker)
        return tk.info.get('currentPrice') or tk.info.get('regularMarketPrice')
    except:
        return None

def get_current_iv(ticker):
    """從資料庫取得最新 IV"""
    db = load_db()
    stock = db.get("stocks", {}).get(ticker)
    if stock and stock.get("iv"):
        return stock["iv"][-1]
    return None

def main():
    print("📊 IV History Weekly Monitor")
    print("=" * 60)
    
    db = load_db()
    
    if not db.get("stocks"):
        print("❌ 資料庫為空，請先執行 IV History Logger")
        return
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    print(f"📅 報告生成：{today.strftime('%Y-%m-%d')}")
    print(f"📁 資料庫更新：{db.get('updated', 'N/A')}")
    print()
    
    # 資料庫狀態摘要
    total_tracked = len(db["stocks"])
    stocks_with_data = {t: s for t, s in db["stocks"].items() if s.get("iv")}
    min_days = min(len(s["iv"]) for s in stocks_with_data.values()) if stocks_with_data else 0
    max_days = max(len(s["iv"]) for s in stocks_with_data.values()) if stocks_with_data else 0
    
    print("📋 資料庫狀態")
    print(f"  追蹤股票：{total_tracked}/16")
    print(f"  資料筆數：{min_days}-{max_days} 天")
    print()
    
    # IV 變化分析
    print("📈 IV 每週變化（top 10 最大變動）")
    print("-" * 60)
    print(f"{'股票':<6} {'上週 IV':>8} {'本週 IV':>8} {'變動':>8} {'狀態':>10}")
    print("-" * 60)
    
    changes = []
    for ticker in TICKERS:
        stock = db.get("stocks", {}).get(ticker)
        if not stock or len(stock.get("iv", [])) < 2:
            continue
        
        ivs = stock["iv"]
        prev_iv = ivs[-2] if len(ivs) >= 2 else None
        curr_iv = ivs[-1]
        
        if prev_iv is not None:
            change = curr_iv - prev_iv
            changes.append((ticker, prev_iv, curr_iv, change))
    
    # 按變動排序
    changes.sort(key=lambda x: abs(x[3]), reverse=True)
    
    for ticker, prev, curr, change in changes[:10]:
        direction = "📈" if change > 0 else "📉"
        print(f"  {ticker:<6} {prev:>7.1f}% {curr:>7.1f}% {direction} {change:>+6.1f}%")
    
    print()
    
    # IVR 摘要（如果有足夠數據）
    ivr_stocks = {t: s for t, s in db["stocks"].items() if s.get("iv_rank") is not None}
    
    if ivr_stocks:
        print("📊 IV Rank 狀態")
        print("-" * 60)
        
        high_ivr = [(t, s["iv_rank"]) for t, s in ivr_stocks.items() if s["iv_rank"] >= 60]
        mid_ivr = [(t, s["iv_rank"]) for t, s in ivr_stocks.items() if 40 <= s["iv_rank"] < 60]
        low_ivr = [(t, s["iv_rank"]) for t, s in ivr_stocks.items() if s["iv_rank"] < 40]
        
        if high_ivr:
            print(f"  🔴 高 IVR (≥60%): {', '.join(f'{t}({r:.0f}%)' for t,r in high_ivr)}")
        if mid_ivr:
            print(f"  🟡 中 IVR (40-60%): {', '.join(f'{t}({r:.0f}%)' for t,r in mid_ivr)}")
        if low_ivr:
            print(f"  🟢 低 IVR (<40%): {', '.join(f'{t}({r:.0f}%)' for t,r in low_ivr)}")
    else:
        est_days = min_days if min_days == max_days else f"{min_days}-{max_days}"
        print(f"⏳ IVR 需要更多歷史數據（目前 {est_days} 天）")
        print("   52W IV Rank 需要 252+ 個交易日數據")
    
    print()
    
    # 距離 52W 的週期評估
    print("📅 52W IV Rank 到期評估")
    print("-" * 60)
    
    # 假設每天記錄一次（交易日）
    # 252 個交易日 ≈ 1 年交易日數
    target_days = 252
    
    for ticker in TICKERS:
        stock = db.get("stocks", {}).get(ticker)
        if stock and stock.get("iv"):
            days = len(stock["iv"])
            remaining = target_days - days
            pct = days / target_days * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"  {ticker:<6} [{bar}] {days}/{target_days} ({pct:.1f}%)")
    
    print()
    print("=" * 60)
    print("✅ 監控完成")

if __name__ == "__main__":
    main()
