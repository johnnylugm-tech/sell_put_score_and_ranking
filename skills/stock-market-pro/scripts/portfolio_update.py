#!/usr/bin/env python3
"""
持倉操作策略更新 v3.0
使用 yfinance 數據 + blackscholes 計算真實 Greeks

⚠️ 核心原則：
1. 數據來源：yfinance（即時市場數據）
2. Greeks 計算：blackscholes（用 HV 代替 IV，避免 yfinance IV 錯誤問題）
3. 持倉資料從本地 JSON 讀取（安全保存在本地）
4. 拒絕估算，拒絕幻覺
"""

import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, date
from blackscholes import BlackScholesPut, BlackScholesCall
import sys
import math
import json
import os

# 預設持倉檔案路徑（本地 memory 目錄）
DEFAULT_POSITIONS_FILE = os.path.expanduser("~/.openclaw/workspace-option/memory/positions/us_positions.json")

def load_positions(filepath=None):
    """從本地 JSON 檔案讀取持倉資料"""
    if filepath is None:
        filepath = DEFAULT_POSITIONS_FILE
    
    if not os.path.exists(filepath):
        print(f"⚠️ 持倉檔案不存在: {filepath}")
        print("請建立持倉檔案或指定正確路徑")
        return []
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        positions = data.get('positions', [])
        print(f"✅ 已載入 {len(positions)} 筆持倉資料")
        return positions
    except Exception as e:
        print(f"❌ 讀取持倉檔案失敗: {e}")
        return []

def get_positions_from_args():
    """從命令列參數讀取持倉檔案路徑"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return None

POSITIONS = []  # 初始化為空，main() 中從檔案載入

def norm_cdf(x):
    """標準常態分佈累積分佈函數近似 (Abramowitz and Stegun)"""
    if x < 0:
        return 1 - norm_cdf(-x)
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + y)

def bs_itm_probability(S, K, T, r, sigma):
    """Black-Scholes 模型計算 Put 到期 ITM 機率"""
    if T <= 0:
        return 0
    d2 = (math.log(S / K) + (r - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(-d2)  # Put ITM = S < K = N(-d2)

# 當前持倉（手動更新）
POSITIONS = []  # 動態載入，見 main()

def get_stock_data(symbol):
    """取得股票即時數據（只用 yfinance）"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history("1y")
        
        if hist.empty:
            return None
        
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not current_price:
            current_price = hist['Close'].iloc[-1]
        
        high_52w = hist['High'].max()
        low_52w = hist['Low'].min()
        
        # HV 計算（滾動20日年化）
        hv = hist['Close'].pct_change().rolling(20).std().iloc[-1] * np.sqrt(252) * 100
        
        return {
            "symbol": symbol,
            "currentPrice": float(current_price),
            "high52w": float(high_52w),
            "low52w": float(low_52w),
            "hv": float(hv),
        }
    except Exception as e:
        print(f"❌ 取得股票數據失敗: {symbol} - {e}")
        return None

def calculate_greeks(symbol, strike, expiry, current_price, hv, risk_free_rate=0.05):
    """
    使用 blackscholes 計算 Greeks
    用 HV 代替 IV（避免 yfinance IV 錯誤問題）
    
    參數：
    - symbol: 股票代碼
    - strike: 履約價
    - expiry: 到期日 (YYYY-MM-DD)
    - current_price: 現價
    - hv: 歷史波動率 (%)
    - risk_free_rate: 無風險利率 (默認 5%)
    """
    try:
        # 計算 DTE (Days to Expiration)
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        dte = (expiry_date - date.today()).days
        
        if dte <= 0:
            return None
        
        T = dte / 365.0
        sigma = hv / 100.0
        
        # 計算 Put Greeks
        put = BlackScholesPut(
            S=current_price,
            K=strike,
            T=T,
            r=risk_free_rate,
            sigma=sigma
        )
        
        return {
            "dte": dte,
            "T": T,
            "sigma": sigma,
            "price": put.price(),
            "delta": put.delta(),
            "gamma": put.gamma(),
            "theta": put.theta(),
            "vega": put.vega(),
            "rho": put.rho(),
        }
    except Exception as e:
        print(f"❌ Greeks 計算失敗: {symbol} - {e}")
        return None

def analyze_position(pos):
    """分析單筆持倉"""
    symbol = pos["symbol"]
    strike = pos["strike"]
    expiry = pos["expiry"]
    cost = pos.get("cost", pos.get("premium", 0))
    
    # 取得股票數據
    stock = get_stock_data(symbol)
    if not stock:
        return None
    
    current_price = stock["currentPrice"]
    high_52w = stock["high52w"]
    low_52w = stock["low52w"]
    hv = stock["hv"]
    
    # 計算 Greeks（用 HV）
    greeks = calculate_greeks(symbol, strike, expiry, current_price, hv)
    
    # 計算基本指標
    itm_amount = current_price - strike if current_price > strike else 0
    dist_from_low = (current_price / low_52w - 1) * 100
    
    # 停止條件：跌破52週低 = 交易邏輯失效
    # 停損從持倉檔案讀取（安全保存在本地）
    stop_loss = pos.get("stop_loss", low_52w)  # 預設為52W低
    stop_loss_triggered = current_price < stop_loss
    
    # ITM 機率計算（使用 Black-Scholes）
    if greeks:
        itm_prob = bs_itm_probability(current_price, strike, greeks['T'], 0.05, greeks['sigma'])
        itm_prob_pct = f"{itm_prob*100:.1f}%"
    
    print(f"\n{'='*55}")
    print(f"【{symbol} ${strike} Put ({expiry})】")
    print(f"{'='*55}")
    print(f"| 項目    | 數值 |")
    print(f"| ----- | --- |")
    print(f"| 現價    | ${current_price:.2f} |")
    print(f"| 履約價   | ${strike} |")
    print(f"| 價內/外  | {'+' if itm_amount > 0 else ''}{itm_amount:.2f} ({'價內' if itm_amount > 0 else '價外'}) |")
    print(f"| 距52W低  | {dist_from_low:.1f}% |")
    print(f"| HV      | {hv:.1f}% |")
    
    if greeks:
        print(f"| DTE     | {greeks['dte']} 天 |")
        print(f"| ---------------- |")
        print(f"| Greeks (HV={hv:.1f}%): |")
        print(f"| Delta  | {greeks['delta']:.4f} |")
        print(f"| Gamma  | {greeks['gamma']:.6f} |")
        print(f"| Theta  | {greeks['theta']:.4f} |")
        print(f"| Vega   | {greeks['vega']:.4f} |")
        print(f"| ---------------- |")
        print(f"| 理論價格 | ${greeks['price']:.2f} |")
        
        # 狀態判斷
        status = "🟢 安全"
        if dist_from_low < 10:
            status = "🟡 靠近低點"
        if dist_from_low < 5:
            status = "🔴 跌破低點"
        
        print(f"| 狀態    | {status} |")
        print(f"| ITM機率 | {itm_prob_pct} |")
        
        # 停止條件
        print(f"|")
        print(f"| 停止條件：")
        triggered_str = "❌ 已觸發" if stop_loss_triggered else f"❌ 未觸發（距 ${current_price - stop_loss:.2f}）"
        print(f"| {symbol} 跌破 ${stop_loss:.2f} → {triggered_str} |")
        
        return {
            "symbol": symbol,
            "currentPrice": current_price,
            "strike": strike,
            "expiry": expiry,
            "hv": hv,
            "dte": greeks['dte'],
            "delta": greeks['delta'],
            "gamma": greeks['gamma'],
            "theta": greeks['theta'],
            "vega": greeks['vega'],
            "price": greeks['price'],
            "status": status,
            "stopLossTriggered": stop_loss_triggered,
            "stopLoss": stop_loss,
        }
    else:
        print(f"❌ 無法計算 Greeks")
        return None

def main():
    print(f"📊 持倉操作策略更新 v3.0（{datetime.now().strftime('%Y/%m/%d %H:%M')}）")
    print("⚠️ Greeks 使用 blackscholes + HV 計算，拒絕估算")
    
    # 從本地檔案載入持倉資料
    filepath = get_positions_from_args() or DEFAULT_POSITIONS_FILE
    positions = load_positions(filepath)
    
    if not positions:
        print("❌ 無持倉資料，請確認持倉檔案存在且格式正確")
        return
    
    results = []
    for pos in positions:
        result = analyze_position(pos)
        if result:
            results.append(result)
    
    # 總結
    print(f"\n{'='*55}")
    print("【操作建議】")
    print(f"{'='*55}")
    for r in results:
        action = "續抱到期" if not r["stopLossTriggered"] else "🚨 考慮平倉"
        print(f"| {r['symbol']} | {action} |")
    
    print(f"\n【觸發條件提醒】")
    for r in results:
        triggered = "已觸發" if r["stopLossTriggered"] else "未觸發"
        print(f"| {r['symbol']} 跌破 ${r['stopLoss']:.2f} → ❌ {triggered} |")
    
    if all(not r["stopLossTriggered"] for r in results):
        print("\n✅ 持倉無異常，繼續持有到期。")
    else:
        print("\n🚨 警告：部分持倉已觸發停止條件！")

if __name__ == "__main__":
    main()
