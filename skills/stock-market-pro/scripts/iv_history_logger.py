#!/usr/bin/env python3
"""
IV History Logger - 建立並維護 IV 歷史資料庫
從今天起持續記錄，為 52W 後切換 IVR 做準備

用法：
    python3 iv_history_logger.py          # 更新所有股票
    python3 iv_history_logger.py MU      # 只更新指定股票
"""

import yfinance as yf
import json
import os
import sys
import math
import numpy as np
from datetime import datetime, date
from pathlib import Path
from scipy.stats import norm

# 預設資料庫路徑
DB_PATH = os.path.expanduser("~/.openclaw/workspace-option/memory/iv_database.json")

# 追蹤的股票清單
TICKERS = [
    'MU', 'TSM', 'AVGO', 'AMD', 'NVDA', 'MRVL', 'ALAB',
    'GOOGL', 'VST', 'AAPL', 'AMZN', 'ARM', 'MSFT', 'INTC', 'TSLA', 'QQQ'
]

def load_db():
    """載入現有資料庫"""
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"updated": None, "stocks": {}}

def save_db(db):
    """儲存資料庫"""
    db["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def calc_bsm_put_iv(S, K, T, r, market_price, tol=1e-6, max_iter=100):
    """
    Black-Scholes 反算 IV（bisection method）
    """
    if T <= 0 or market_price <= 0:
        return None
    
    # 取得 ATM Put 的內含價值
    intrinsic = max(K - S, 0)
    if market_price < intrinsic:
        return None
    
    # 搜尋範圍
    sigma_low, sigma_high = 0.001, 5.0
    
    for _ in range(max_iter):
        sigma_mid = (sigma_low + sigma_high) / 2
        d1 = (math.log(S / K) + (r + 0.5 * sigma_mid**2) * T) / (sigma_mid * math.sqrt(T))
        d2 = d1 - sigma_mid * math.sqrt(T)
        p_mid = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        if abs(p_mid - market_price) < tol:
            return sigma_mid
        if p_mid < market_price:
            sigma_low = sigma_mid
        else:
            sigma_high = sigma_mid
        if sigma_high - sigma_low < 1e-8:
            break
    
    return (sigma_low + sigma_high) / 2

def get_current_iv(ticker):
    """
    取得股票的當前 IV
    優先用 BSM 反算，fallback 到 yfinance IV
    """
    try:
        tk = yf.Ticker(ticker)
        price = tk.info.get('currentPrice') or tk.info.get('regularMarketPrice')
        if not price:
            hist = tk.history("5d")
            if len(hist) > 0:
                price = float(hist['Close'].iloc[-1])
        
        if not price:
            return None
        
        opt = tk.option_chain()
        if not opt or not hasattr(opt, 'puts'):
            return None
        
        puts = opt.puts
        if puts is None or len(puts) == 0:
            return None
        
        # 找最近 ATM 的 Put（有 bid/ask 或 lastPrice）
        atm_range = price * 0.05  # 5% ATM range
        puts['dist_from_atm'] = abs(puts['strike'] - price)
        candidates = puts[puts['strike'].between(price - atm_range, price + atm_range)]
        
        if candidates.empty:
            candidates = puts
        
        # 優先用有 bid/ask 的，否則用 lastPrice
        active = candidates[candidates['bid'] > 0]
        if not active.empty:
            best = active.loc[active['dist_from_atm'].idxmin()]
            price_for_bsm = (float(best['bid']) + float(best['ask'])) / 2
        else:
            traded = candidates[candidates['lastPrice'] > 0]
            if not traded.empty:
                best = traded.loc[traded['dist_from_atm'].idxmin()]
                price_for_bsm = float(best['lastPrice'])
            else:
                return None
        
        # ATM 履約價
        strike = float(best['strike'])
        
        # 到期日（index 就是合約到期日）
        exp = best.name  # Pandas Series 的 name 就是行的 index
        try:
            exp_date = datetime.strptime(str(exp), '%Y-%m-%d')
            dte = max((exp_date.date() - date.today()).days, 1)
        except:
            dte = 30
        
        T = dte / 365.0
        
        # BSM 反算 IV
        iv = calc_bsm_put_iv(S=price, K=strike, T=T, r=0.045, market_price=price_for_bsm)
        if iv is not None:
            return iv * 100  # 轉換為百分比
        
        # Fallback：yfinance 原生 IV
        iv_raw = best.get('impliedVolatility')
        if iv_raw is not None and iv_raw > 0.001:
            iv = iv_raw * 100 if iv_raw < 1.0 else iv_raw
            return float(iv)
        
        return None
    except Exception as e:
        print(f"  ⚠️ {ticker} IV 取得失敗: {e}")
        return None

def update_ticker(ticker, db):
    """更新單一股票的 IV 資料"""
    today_str = date.today().strftime("%Y-%m-%d")
    today_key = date.today().strftime("%Y-%m-%d")
    
    if ticker not in db["stocks"]:
        db["stocks"][ticker] = {
            "dates": [],
            "iv": [],
            "iv_52w_low": None,
            "iv_52w_high": None,
            "iv_rank": None,
            "iv_percentile": None
        }
    
    stock = db["stocks"][ticker]
    iv = get_current_iv(ticker)
    
    if iv is None:
        print(f"  ⏭ {ticker}: 無法取得 IV，跳過")
        return
    
    # 如果今天已有記錄，更新取代
    if stock["dates"] and stock["dates"][-1] == today_key:
        stock["iv"][-1] = iv
        print(f"  🔄 {ticker}: IV 更新為 {iv:.1f}%")
    else:
        stock["dates"].append(today_key)
        stock["iv"].append(iv)
        print(f"  ✅ {ticker}: IV 記錄 {iv:.1f}%")
    
    # 計算 52W IV 高低點
    if len(stock["iv"]) >= 2:
        # 需要至少 2 天的數據才能計算 52W
        # 52W = 252 個交易日，但一開始我們用可用的數據
        min_iv = min(stock["iv"])
        max_iv = max(stock["iv"])
        stock["iv_52w_low"] = min_iv
        stock["iv_52w_high"] = max_iv
        
        # 計算今日 IVR
        if stock["iv_52w_high"] > stock["iv_52w_low"]:
            current_iv = stock["iv"][-1]
            iv_range = stock["iv_52w_high"] - stock["iv_52w_low"]
            ivr = (current_iv - stock["iv_52w_low"]) / iv_range * 100
            stock["iv_rank"] = round(ivr, 1)
        
        # 計算 IV Percentile（過去 252 天中低於今日的比例）
        if len(stock["iv"]) >= 20:
            current_iv = stock["iv"][-1]
            below_count = sum(1 for v in stock["iv"][:-1] if v < current_iv)
            ivp = below_count / (len(stock["iv"]) - 1) * 100
            stock["iv_percentile"] = round(ivp, 1)

def main():
    today = date.today().strftime("%Y-%m-%d")
    print(f"📊 IV History Logger（{today}）")
    print("=" * 50)
    
    db = load_db()
    print(f"📁 資料庫：{DB_PATH}")
    print(f"📊 已追蹤股票數：{len(db['stocks'])}")
    if db["updated"]:
        print(f"🕐 上次更新：{db['updated']}")
    print()
    
    # 決定要更新的股票
    if len(sys.argv) > 1:
        tickers_to_update = sys.argv[1:]
    else:
        tickers_to_update = TICKERS
    
    # 更新每支股票
    for ticker in tickers_to_update:
        if ticker in TICKERS:
            update_ticker(ticker, db)
    
    # 儲存
    save_db(db)
    
    # 顯示摘要
    print()
    print("=" * 50)
    print("📋 IV 資料庫摘要")
    print("=" * 50)
    for ticker, stock in db["stocks"].items():
        if stock["dates"]:
            days = len(stock["dates"])
            latest_iv = stock["iv"][-1]
            ivr = stock.get("iv_rank")
            ivp = stock.get("iv_percentile")
            ivr_str = f"{ivr:>5.1f}" if ivr is not None else "  N/A"
            ivp_str = f"{ivp:>5.1f}" if ivp is not None else "  N/A"
            print(f"  {ticker:6s}: {latest_iv:6.1f}% | IVR={ivr_str} | IVP={ivp_str} | {days}天資料")
    
    print()
    print("✅ 完成！")

if __name__ == "__main__":
    main()
