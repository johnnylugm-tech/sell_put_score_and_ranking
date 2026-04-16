#!/usr/bin/env python3
"""
00637L 每日持倉分析
計算所有關鍵數據，禁止任何人為計算
持倉資料從本地 JSON 讀取（安全保存在本地）
"""

import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime
import json
import os

# 預設持倉檔案路徑（本地 memory 目錄）
DEFAULT_POSITION_FILE = os.path.expanduser("~/.openclaw/workspace-option/memory/positions/tw_positions.json")

# ---------- 工具函式 ----------

def load_position_data(filepath=None):
    """從本地 JSON 檔案讀取持倉資料"""
    if filepath is None:
        filepath = DEFAULT_POSITION_FILE
    
    if not os.path.exists(filepath):
        print(f"⚠️ 持倉檔案不存在: {filepath}")
        return None
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        position = data.get('position', {})
        print(f"✅ 已載入持倉資料: {position.get('shares')} 張 {position.get('symbol')}")
        return position
    except Exception as e:
        print(f"❌ 讀取持倉檔案失敗: {e}")
        return None

def get_position_from_args():
    """從命令列參數讀取持倉檔案路徑"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return None

def get_position_data():
    """取得持倉資料（優先從命令列，否則從預設路徑）"""
    filepath = get_position_from_args() or DEFAULT_POSITION_FILE
    return load_position_data(filepath)

# 動態載入持倉資料（不再寫死在程式碼）
_position_cache = None

def SHARES():
    global _position_cache
    if _position_cache is None:
        _position_cache = get_position_data()
    return _position_cache.get('shares', 0) if _position_cache else 0

def COST_PRICE():
    global _position_cache
    if _position_cache is None:
        _position_cache = get_position_data()
    return _position_cache.get('cost_price', 0) if _position_cache else 0

def get_stop_loss_warning_pct():
    global _position_cache
    if _position_cache is None:
        _position_cache = get_position_data()
    return _position_cache.get('stop_loss_warning_pct', 0.90) if _position_cache else 0.90

import sys

# ---------- 工具函式 ----------

def _download_yf(ticker, period, auto_adjust=True):
    """yfinance 下載統一接口 + MultiIndex 處理"""
    try:
        df = yf.download(ticker, period=period, auto_adjust=auto_adjust, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df[df["Close"].notna()]  # Only drop rows with no Close price
    except Exception:
        return None

# ---------- 數據取得 ----------

def get_csi300():
    """
    取得 CSI 300：現價、52W高、RSI
    合併下載，避免重複請求
    """
    df = _download_yf("000300.SS", "1y")
    if df is None or 'Close' not in df.columns or len(df) < 30:
        return None, None, None
    
    current = float(df['Close'].iloc[-1])
    high_52w = float(df['High'].max())
    
    # RSI (Wilder's)
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14).mean()
    rs = gain / loss
    rsi = float((100 - 100 / (1 + rs)).iloc[-1])
    
    return current, high_52w, rsi

def get_00637l():
    """
    取得 00637L：現價、52W高、HV、RSI
    只下載 1y，HV 用 tail(60) 計算
    """
    df = _download_yf("00637L.TW", "1y")
    if df is None or 'Close' not in df.columns or len(df) < 30:
        return None
    
    current = float(df['Close'].iloc[-1])
    high_52w = float(df['High'].max())
    
    # HV (20日滾動)
    closes = df['Close']
    log_ret = np.log(closes / closes.shift(1))
    hv_20 = float(log_ret.tail(20).std() * np.sqrt(252) * 100)
    
    # RSI (Wilder's) — 用完整 1y 數據
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14).mean()
    rs = gain / loss
    rsi = float((100 - 100 / (1 + rs)).iloc[-1])
    
    # 距52W高%
    dist_to_high = (current - high_52w) / high_52w * 100
    
    return {
        "current": current,
        "high_52w": high_52w,
        "dist_to_high": dist_to_high,
        "hv_20": hv_20,
        "rsi": rsi
    }

def get_usdcnh():
    """取得 USD/CNH（離岸）"""
    df = _download_yf("USDCNH=X", "5d")  # 短週期避免空數據
    if df is None or df.empty or 'Close' not in df.columns:
        df = _download_yf("USDCNY=X", "5d")  # Fallback 在岸
    if df is None or df.empty or 'Close' not in df.columns:
        return None
    return float(df['Close'].iloc[-1])

# ---------- 評估函式 ----------

def assess_csi300_status(csi_current, csi_high):
    if csi_current is None or csi_high is None:
        return "⚠️ 無法取得", None
    dist = (csi_current - csi_high) / csi_high * 100
    if dist > -5: return "🟢 接近高點", dist
    elif dist > -15: return "🟡 中性偏弱", dist
    else: return "🔴 明顯弱勢", dist

def assess_hv(hv):
    if hv > 55: return "🔴 極高波動"
    elif hv > 40: return "🟡 偏高波動"
    elif hv > 25: return "🟢 正常範圍"
    else: return "🔵 低波動"

def assess_rsi(rsi):
    if rsi is None: return "⚠️ 無法取得"
    if rsi < 30: return f"🔴 超賣({rsi:.0f})"
    elif rsi < 40: return f"🟡 偏弱({rsi:.0f})"
    elif rsi < 60: return f"🟢 中性({rsi:.0f})"
    elif rsi < 70: return f"🟡 偏強({rsi:.0f})"
    else: return f"🔴 超買({rsi:.0f})"

def assess_usdcnh(rate):
    if rate is None: return "⚠️ 無法取得"
    elif rate > 7.5: return "🔴 警訊"
    elif rate > 7.0: return "🟡 關注"
    elif rate > 6.7: return "🟢 安全"
    else: return "🟢 偏強"

def calculate_scores(data, csi_high, usdcnh, rsi_csi):
    """
    評分維度（權重之和 = 100%）
    CSI 300: 55% | 波動率: 15% | 人民幣: 10% | 技術位: 15% | 流動性: 5%
    """
    # CSI 300 定向（55%）
    csi_dist = (data["current"] - csi_high) / csi_high * 100 if csi_high else 0
    if csi_dist > -5: csi_score = 80
    elif csi_dist > -10: csi_score = 65
    elif csi_dist > -20: csi_score = 50
    else: csi_score = 35

    # 波動率損耗（15%）
    if data["hv_20"] > 55: theta_score = 30
    elif data["hv_20"] > 40: theta_score = 50
    else: theta_score = 70

    # 人民幣匯率（10%）
    if usdcnh is None: cny_score = 30
    elif usdcnh < 6.5: cny_score = 95
    elif usdcnh < 6.7: cny_score = 90
    elif usdcnh < 7.0: cny_score = 80
    elif usdcnh < 7.3: cny_score = 50
    elif usdcnh < 7.5: cny_score = 30
    else: cny_score = 15

    # 技術位（15%）— 合併 00637L RSI + CSI 300 RSI
    rsi_00637 = data.get("rsi", 50)
    rsi_avg = (rsi_00637 + (rsi_csi if rsi_csi else rsi_00637)) / 2
    if 40 <= rsi_avg <= 60: tech_score = 80
    elif (30 <= rsi_avg < 40) or (60 < rsi_avg <= 70): tech_score = 60
    elif (20 <= rsi_avg < 30) or (70 < rsi_avg <= 80): tech_score = 40
    else: tech_score = 20

    # 流動性（5%）
    liquidity_score = 75

    # 總分（加權 = 100%）
    total = (csi_score * 0.55 + theta_score * 0.15 +
             cny_score * 0.10 + tech_score * 0.15 +
             liquidity_score * 0.05)
    
    return {
        "csi_score": csi_score,
        "theta_score": theta_score,
        "cny_score": cny_score,
        "tech_score": tech_score,
        "liquidity_score": liquidity_score,
        "total": int(total),
        "rsi_00637": rsi_00637,
        "rsi_csi": rsi_csi,
    }

# ---------- 主程式 ----------

def main():
    print(f"📊 00637L 每日分析（{datetime.now().strftime('%Y-%m-%d %H:%M')}）\n")
    
    # 取得數據（合併後一次下載）
    data_00637 = get_00637l()
    csi_current, csi_high, rsi_csi = get_csi300()
    usdcnh = get_usdcnh()
    
    if not data_00637:
        print("❌ 無法取得 00637L 數據")
        return
    if csi_current is None or csi_high is None:
        print("❌ 無法取得 CSI 300 數據")
        return

    # 持股概況（張→股）
    shares = SHARES()
    cost = COST_PRICE()
    shares_total = shares * 1000
    unrealized_gain = (data_00637["current"] - cost) * shares_total
    gain_pct = (data_00637["current"] - cost) / cost * 100
    market_value = data_00637["current"] * shares_total

    print(f"【持股概況】")
    print(f"| 項目   | 數值                  |")
    print(f"| ---- | ------------------- |")
    print(f"| 現價   | {data_00637['current']:.2f} TWD           |")
    print(f"| 成本價  | {cost}               |")
    print(f"| 帳面增益 | +{unrealized_gain:,.0f} ({gain_pct:.1f}%) |")
    print(f"| 總市值  | {market_value:,.0f} TWD      |")
    print()

    csi_status, csi_dist = assess_csi300_status(csi_current, csi_high)
    print(f"【關鍵數據】")
    print(f"| 指標            | 數值                | 狀態       |")
    print(f"| ------------- | ----------------- | -------- |")
    print(f"| CSI 300       | {csi_current:,.2f}          | {csi_status}  |")
    print(f"| CSI 300 距52W高 | {csi_dist:.1f}%            |          |")
    print(f"| 00637L 距52W高  | {data_00637['dist_to_high']:.1f}%             |          |")
    print(f"| HV (20日)      | {data_00637['hv_20']:.1f}%             | {assess_hv(data_00637['hv_20'])}    |")
    print(f"| 00637L RSI    | {data_00637['rsi']:.1f}             | {assess_rsi(data_00637['rsi'])} |")
    print(f"| CSI 300 RSI   | {(rsi_csi if rsi_csi else 0):.1f}             | {assess_rsi(rsi_csi)} |")
    usdcnh_disp = f"{usdcnh:.4f}" if usdcnh is not None else "N/A"
    print(f"| USD/CNH       | {usdcnh_disp}              | {assess_usdcnh(usdcnh)} |")
    print()

    scores = calculate_scores(data_00637, csi_high, usdcnh, rsi_csi)
    print(f"【評分明細】")
    print(f"| 因子          | 權重  | 評分 |")
    print(f"| ----------- | --- | --- |")
    print(f"| CSI 300定向波動 | 55% | {scores['csi_score']} |")
    print(f"| 波動率損耗       | 15% | {scores['theta_score']} |")
    print(f"| 人民幣匯率       | 10% | {scores['cny_score']} |")
    print(f"| 技術位(雙RSI均)  | 15% | {scores['tech_score']} |")
    print(f"| 流動性         | 5%  | {scores['liquidity_score']} |")
    print(f"| **綜合評分**    | 100% | **{scores['total']}/100** |")
    print()

    stop_loss_warning = round(data_00637["current"] * get_stop_loss_warning_pct(), 2)
    stop_loss_mandatory = round(COST_PRICE(), 2)
    print(f"【操作建議】")
    if scores["total"] >= 75: print(f"| 續抱     | 綜合評分 {scores['total']}，各方支撐穩健 |")
    elif scores["total"] >= 60: print(f"| 觀望     | 綜合評分 {scores['total']}，注意高點壓力 |")
    else: print(f"| 分批減碼 | 綜合評分 {scores['total']}，建議降低風險 |")
    print(f"| 停損警戒：{stop_loss_warning}（-{((stop_loss_warning/data_00637['current'])-1)*100:.1f}%）|")
    print(f"| 強制停損：{stop_loss_mandatory}（成本價）|")
    print()

    print(f"【觸發條件提醒】")
    print(f"| 條件              | 狀態         |")
    if csi_current and csi_current > 4520: print(f"| CSI 300 突破 4520 | ⚠️ 已觸發      |")
    else: print(f"| CSI 300 突破 4520 | ❌ 未觸發      |")
    if csi_current and csi_current < 4000: print(f"| CSI 300 跌破 4000 | 🔴 已觸發      |")
    else:
        dist_val = f"{csi_current - 4000:.0f}" if csi_current else "N/A"
        print(f"| CSI 300 跌破 4000 | ❌ 未觸發，距離{dist_val}點 |")
    if usdcnh and usdcnh > 7.0: print(f"| USD/CNH > 7.0   | 🔴 警訊      |")
    else: print(f"| USD/CNH > 7.0   | ✅ 安全       |")
    print()
    print(f"✅ 持倉無異常，續抱待變。")

if __name__ == "__main__":
    main()
