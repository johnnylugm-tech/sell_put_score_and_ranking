#!/usr/bin/env python3
"""
A50 期指每日分析 v2.0
使用 openclaw-data-china-stock plugin 獲取真實數據
所有支撐/阻力/均線均從歷史數據計算，拒絕估算
"""

import subprocess
import json
from datetime import datetime, timedelta

VENV_PYTHON = "/Users/johnny/.openclaw/venv/bin/python3"
PLUGIN_PATH = "/Users/johnny/.openclaw/extensions/openclaw-data-china-stock/tool_runner.py"

def fetch_a50_realtime():
    """獲取 A50 期指即時數據"""
    cmd = [
        VENV_PYTHON, PLUGIN_PATH,
        "tool_fetch_a50_data",
        '{"data_type":"realtime"}'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)

def fetch_a50_historical(start_date, end_date):
    """獲取 A50 期指歷史數據"""
    data = {
        "data_type": "historical",
        "start_date": start_date,
        "end_date": end_date
    }
    cmd = [
        VENV_PYTHON, PLUGIN_PATH,
        "tool_fetch_a50_data",
        json.dumps(data)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)

def calculate_ma(prices, period):
    """計算移動平均"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def get_a50_analysis():
    """生成 A50 期指分析報告"""
    
    # 獲取即時數據
    realtime = fetch_a50_realtime()
    
    if not realtime.get("success"):
        return f"❌ 無法取得 A50 數據: {realtime.get('message', 'Unknown error')}"
    
    spot = realtime.get("spot_data", {})
    current_price = spot.get("current_price", 0)
    change_pct = spot.get("change_pct", 0)
    volume = spot.get("volume", 0)
    
    # 獲取歷史數據計算真實支撐/阻力
    # 52W = 365天，但A50期指歷史數據從2025-01-01開始
    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    hist_data = fetch_a50_historical("20250101", end_date)
    
    if hist_data.get("success") and hist_data.get("hist_data"):
        klines = hist_data["hist_data"]["klines"]
        
        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]
        
        # 52W high/low（全部歷史數據）
        high_52w = max(highs)
        low_52w = min(lows)
        
        # 真實均線計算
        ma5 = calculate_ma(closes, 5)
        ma10 = calculate_ma(closes, 10)
        ma20 = calculate_ma(closes, 20)
        ma60 = calculate_ma(closes, 60)
        ma120 = calculate_ma(closes, 120) if len(closes) >= 120 else None
        
        # 真實支撐/阻力（最近20日）
        resistance_1 = max(highs[-5:])   # 5日高
        resistance_2 = max(highs[-20:])  # 20日高
        support_1 = min(lows[-5:])       # 5日低
        support_2 = min(lows[-20:])      # 20日低
        
        # 均線狀態（根據現價與均線關係）
        ma_status = {
            "MA5": "✅ 上方" if ma5 and current_price > ma5 else "❌ 下方",
            "MA10": "✅ 上方" if ma10 and current_price > ma10 else "❌ 下方",
            "MA20": "✅ 上方" if ma20 and current_price > ma20 else "❌ 下方",
            "MA60": "✅ 上方" if ma60 and current_price > ma60 else "❌ 下方",
            "MA120": "✅ 上方" if ma120 and current_price > ma120 else "❌ 下方",
        }
        
        # 與52W的距離
        dist_from_high = (current_price / high_52w - 1) * 100
        dist_from_low = (current_price / low_52w - 1) * 100
        
        # 趨勢判斷
        if current_price > ma20 > ma60:
            trend = "📈 上升趨勢"
        elif current_price < ma20 < ma60:
            trend = "📉 下降趨勢"
        else:
            trend = "🔄 區間震盪"
        
        # RSI 簡單計算（使用5日）
        if len(closes) >= 6:
            gains = []
            losses = []
            for i in range(-5, 0):
                change = closes[i+1] - closes[i]
                gains.append(max(change, 0))
                losses.append(max(-change, 0))
            avg_gain = sum(gains) / 5
            avg_loss = sum(losses) / 5
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 50
        
        output = f"""📊 A50 期指每日分析（{klines[-1]['date']}）

【即時數據】
| 項目 | 數值 |
|------|------|
| 現價 | {current_price:,.0f} |
| 漲跌 | {change_pct:+.1f}% |
| 成交量 | {volume:,.0f} 手 |

【52週區間】
| 項目 | 數值 | 距現價 |
|------|------|--------|
| 52W 高 | {high_52w:,.0f} | {dist_from_high:+.1f}% |
| 52W 低 | {low_52w:,.0f} | {dist_from_low:+.1f}% |

【真實均線】（從歷史數據計算）
| 均線 | 數值 | 現價相對 |
|------|------|---------|
| MA5 | {ma5:,.0f} | {ma_status['MA5']} |
| MA10 | {ma10:,.0f} | {ma_status['MA10']} |
| MA20 | {ma20:,.0f} | {ma_status['MA20']} |
| MA60 | {ma60:,.0f} | {ma_status['MA60']} |
| MA120 | {f"{ma120:,.0f}" if ma120 else 'N/A'} | {ma_status['MA120'] if ma120 else 'N/A'} |

【真實支撐/阻力】（從最近20日數據計算）
| 類型 | 位階 | 說明 |
|------|------|------|
| 阻力1 | {resistance_1:,.0f} | 5日高點 |
| 阻力2 | {resistance_2:,.0f} | 20日高點 |
| 支撐1 | {support_1:,.0f} | 5日低點 |
| 支撐2 | {support_2:,.0f} | 20日低點 |

【技術信號】
| 信號 | 狀態 |
|------|------|
| 趨勢 | {trend} |
| RSI(5) | {rsi:.0f} |

【操作建議】
• 突破 {resistance_1:,.0f}（5日高）→ 短線積極信號
• 跌破 {support_1:,.0f}（5日低）→ 警惕信號
• 跌破 {support_2:,.0f}（20日低）→ 系統性風險"""
        
        return output
    else:
        return f"❌ 無法取得歷史數據: {hist_data.get('message', 'Unknown error')}"

if __name__ == "__main__":
    print(get_a50_analysis())
