#!/usr/bin/env python3
"""
Sell Put Ranking v5.0 - Core Calculation Engine
嚴格依照 v5.0 評分公式計算，不做任何人為判斷

功能：
- 計算年化收益率、風險/回報評級、持倉建議
- 排名變化、進入時機、財報日曆、板塊熱度
"""

import yfinance as yf
import numpy as np
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# =============================================================================
# 股票列表（16檔）
# =============================================================================
STOCKS = [
    "TSM", "GOOGL", "NVDA", "AMZN", "VST", "AAPL", "ALAB", "ARM",
    "AVGO", "MRVL", "MSFT", "TSLA", "QQQ", "MU", "INTC", "AMD"
]

# IV data (from alphaquery 30-Day IV Mean)
IV_DATA = {
    "TSM": 46.06,
    "GOOGL": 37.67,
    "NVDA": 36.67,
    "AMZN": 43.65,
    "VST": 57.34,
    "AAPL": 29.90,
    "ALAB": 80.70,
    "ARM": 61.30,
    "AVGO": 45.66,
    "MRVL": 59.40,
    "MSFT": 36.10,
    "TSLA": 45.60,
    "QQQ": 24.50,
    "MU": 70.10,
    "INTC": 70.40,
    "AMD": 65.00,  # 估算值
}

# 板塊映射
SECTOR_MAP = {
    "TSM": ("半導體", "🔴"),
    "AVGO": ("半導體", "🔴"),
    "MU": ("半導體", "🔴"),
    "INTC": ("半導體", "🔴"),
    "AMD": ("半導體", "🔴"),
    "NVDA": ("AI/晶片", "🟠"),
    "ALAB": ("AI/晶片", "🟠"),
    "ARM": ("AI/晶片", "🟠"),
    "MRVL": ("AI/晶片", "🟠"),
    "MSFT": ("雲端", "🔵"),
    "GOOGL": ("雲端", "🔵"),
    "AMZN": ("雲端", "🔵"),
    "VST": ("雲端", "🔵"),
    "AAPL": ("消費", "🟢"),
    "TSLA": ("電動車", "🟡"),
    "QQQ": ("ETF", "⚪"),
}

# 預設 DTE (Days To Expiration)
DEFAULT_DTE = 30


def get_historical_data(symbol):
    """取得完整歷史數據，使用1年周期計算真實52W high/low、RSI"""
    try:
        stock = yf.Ticker(symbol)
        hist_1y = stock.history(period="1y")
        hist_120d = stock.history(period="120d")

        if len(hist_1y) < 50 or len(hist_120d) < 50:
            return None

        current = float(hist_1y["Close"].iloc[-1])
        high_52w = float(hist_1y["High"].max())
        low_52w = float(hist_1y["Low"].min())

        # HV (20日) from 120d data
        closes_120 = hist_120d["Close"].values
        hv_20 = float(np.log(closes_120[-20:] / closes_120[-21:-1]).std() * np.sqrt(252) * 100)

        # MA20, MA50 from 120d data
        ma20 = float(np.mean(closes_120[-20:]))
        ma50 = float(np.mean(closes_120[-50:]))

        # RSI (14日)
        delta = hist_120d["Close"].diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        return {
            "price": current,
            "hv_20": hv_20,
            "ma20": ma20,
            "ma50": ma50,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "rsi": rsi,
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}", file=sys.stderr)
        return None


def get_iv(symbol):
    return IV_DATA.get(symbol, None)


def get_pe(symbol):
    """取得 PE Ratio"""
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        return info.get("trailingPE", None) or info.get("forwardPE", None)
    except:
        return None


def get_earnings_date(symbol):
    """取得下次財報日期"""
    try:
        stock = yf.Ticker(symbol)
        # yfinance 有 earnings_dates，但可能為空
        ed = stock.earnings_dates
        if ed is not None and len(ed) > 0:
            # 找到未來的日期
            now = datetime.now()
            future = ed[ed.index > now]
            if len(future) > 0:
                next_er = future.index[0]
                return next_er.strftime("%m/%d")
    except:
        pass
    return None


def calculate_v5_score(iv, hv, price, low_52w, high_52w, rsi, pe, above_ma20, above_ma50, market_cap=None):
    """
    v5.0 評分公式（總分 100）
    ①距低點 23分 + ②IV/HV 18分 + ③基本面 28分 + ④RSI 9分
    + ⑤流動性 8分 + ⑥期權流 9分 + ⑦事件 5分 + ⑧效率 9分 + ⑨位置 4分 + ⑩Skew 4分
    """
    # === ①距52W低點 (23分) ===
    dist_52w_low_pct = (price - low_52w) / low_52w * 100
    if dist_52w_low_pct >= 100:
        score_dist = 23
    elif dist_52w_low_pct >= 50:
        score_dist = 20
    elif dist_52w_low_pct >= 30:
        score_dist = 15
    elif dist_52w_low_pct >= 15:
        score_dist = 10
    elif dist_52w_low_pct >= 5:
        score_dist = 5
    else:
        score_dist = 2

    # === ②IV/HV (18分) ===
    iv_hv_ratio = (iv / hv) if (iv and hv > 0) else 0.0
    if iv_hv_ratio >= 1.5:
        score_ivhv = 18
    elif iv_hv_ratio >= 1.3:
        score_ivhv = 15
    elif iv_hv_ratio >= 1.1:
        score_ivhv = 12
    elif iv_hv_ratio >= 0.9:
        score_ivhv = 8
    elif iv_hv_ratio >= 0.7:
        score_ivhv = 4
    else:
        score_ivhv = 1

    # === ③基本面 (28分) - PE 評分 ===
    score_pe = 0
    if pe is not None and pe > 0:
        if pe < 15:
            score_pe = 28
        elif pe < 20:
            score_pe = 24
        elif pe < 25:
            score_pe = 20
        elif pe < 30:
            score_pe = 15
        elif pe < 40:
            score_pe = 8
        else:
            score_pe = 3
    else:
        score_pe = 10  # 無數據默認中等

    # === ④RSI (9分) ===
    if rsi < 30:
        score_rsi = 9  # 超賣，理想
    elif rsi < 40:
        score_rsi = 7
    elif rsi < 50:
        score_rsi = 5
    elif rsi < 60:
        score_rsi = 4
    elif rsi < 70:
        score_rsi = 3
    else:
        score_rsi = 1  # 過熱

    # === ⑤流動性 (8分) - 簡化用市值/IV proxy ===
    score_liq = 4  # 默認中等

    # === ⑥期權流 (9分) - 用 IV 作為流動性 proxy ===
    if iv and iv > 50:
        score_opt = 9
    elif iv and iv > 35:
        score_opt = 7
    elif iv and iv > 25:
        score_opt = 5
    else:
        score_opt = 3

    # === ⑦事件 (5分) - 財報風險 ===
    score_event = 3  # 默認無事件

    # === ⑧效率 (9分) - ROCC×PoP 簡化 ===
    score_eff = 5  # 默認中等

    # === ⑨52W位置 (4分) ===
    pos_52w = (price - low_52w) / (high_52w - low_52w) * 100
    if pos_52w < 30:
        score_pos = 4  # 近低點
    elif pos_52w < 50:
        score_pos = 3
    elif pos_52w < 70:
        score_pos = 2
    else:
        score_pos = 1  # 近高點

    # === ⑩Skew (4分) - 簡化 ===
    score_skew = 2  # 默認中等

    total = score_dist + score_ivhv + score_pe + score_rsi + score_liq + score_opt + score_event + score_eff + score_pos + score_skew

    return {
        "①距低點": score_dist,
        "②IV/HV": score_ivhv,
        "③基本面": score_pe,
        "④RSI": score_rsi,
        "⑤流動性": score_liq,
        "⑥期權流": score_opt,
        "⑦事件": score_event,
        "⑧效率": score_eff,
        "⑨位置": score_pos,
        "⑩Skew": score_skew,
        "total": total,
        "dist_52w_low_pct": round(dist_52w_low_pct, 1),
        "iv_hv_ratio": round(iv_hv_ratio, 2),
        "rsi": round(rsi, 1),
        "pos_52w": round(pos_52w, 1),
    }


def calculate_annualized_return(price, iv, dte=DEFAULT_DTE):
    """
    功能1：計算預期年化收益率
    公式：(權利金/履約價) / (DTE/365) * 100
    權利金 ≈ IV% × price × 0.4 (ATM put 約為 IV 的 40%)
    履約價 = price × 0.92 (8% OTM)
    """
    strike = price * 0.92
    # 估算權利金 (使用 IV * price * 0.4)
    premium_pct = iv / 100 * 0.4 if iv else 0.03
    premium = strike * premium_pct
    # 年化
    annualized = (premium / strike) / (dte / 365) * 100
    return round(annualized, 1)


def calculate_risk_reward_rating(annualized_return, iv):
    """
    功能2：風險/回報評級
    公式：年化收益 / IV
    等級：A+ (>=3.0) / A (>=2.0) / B (>=1.0) / C (>=0.5) / D (<0.5)
    """
    if iv and iv > 0:
        ratio = annualized_return / iv
    else:
        ratio = 0.5

    if ratio >= 3.0:
        return "A+", ratio
    elif ratio >= 2.0:
        return "A", ratio
    elif ratio >= 1.0:
        return "B", ratio
    elif ratio >= 0.5:
        return "C", ratio
    else:
        return "D", ratio


def calculate_position_size(total_score, vix=20):
    """
    功能3：持倉建議
    根據總分和 VIX 調整倉位
    VIX < 15: 積極 (+1%)
    VIX 15-25: 正常
    VIX 25-35: 保守 (-1%)
    VIX > 35: 極保守 (-2%)

    總分 >= 80: 進取 (+1%)
    總分 60-80: 正常
    總分 < 60: 保守 (-1%)
    """
    base = 3.0  # 基準倉位 3%

    # VIX 調整
    if vix < 15:
        vix_adj = 2.0
    elif vix < 25:
        vix_adj = 0.0
    elif vix < 35:
        vix_adj = -1.0
    else:
        vix_adj = -2.0

    # 分數調整
    if total_score >= 80:
        score_adj = 1.0
    elif total_score >= 60:
        score_adj = 0.0
    else:
        score_adj = -1.0

    position = base + vix_adj + score_adj
    position = max(1.0, min(5.0, position))  # 限制在 1-5%
    return round(position, 1)


def get_entry_timing(dte, rsi):
    """
    功能5：進入時機
    DTE < 14 AND RSI > 60 → 短線
    DTE 14-45 → 波段
    DTE > 45 → 長期
    """
    if dte < 14 and rsi > 60:
        return "短線"
    elif dte <= 45:
        return "波段"
    else:
        return "長期"


def get_rank_change(symbol, current_rank, data_dir=None):
    """
    功能4：排名變化
    讀取昨日排名數據
    """
    if data_dir is None:
        data_dir = Path(__file__).parent.parent.parent.parent / "memory"
    else:
        data_dir = Path(data_dir)

    # 嘗試讀取昨天的數據
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    ranking_file = data_dir / f"ranking_{yesterday}.json"

    if not ranking_file.exists():
        # 嘗試更早的日期
        for i in range(2, 8):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            ranking_file = data_dir / f"ranking_{date}.json"
            if ranking_file.exists():
                break

    if ranking_file.exists():
        try:
            with open(ranking_file) as f:
                data = json.load(f)
            for item in data:
                if item.get("symbol") == symbol:
                    prev_rank = item.get("rank", current_rank)
                    change = prev_rank - current_rank
                    if change > 0:
                        return "↑", change
                    elif change < 0:
                        return "↓", abs(change)
                    else:
                        return "→", 0
        except:
            pass

    return "→", 0


def save_ranking_data(results, data_dir=None):
    """保存今日排名數據用於明日比較"""
    if data_dir is None:
        data_dir = Path(__file__).parent.parent.parent.parent / "memory"
    else:
        data_dir = Path(data_dir)

    today = datetime.now().strftime("%Y-%m-%d")
    ranking_file = data_dir / f"ranking_{today}.json"

    save_data = [{"symbol": r["symbol"], "rank": r["rank"], "total": r["score"]["total"]} for r in results]

    with open(ranking_file, "w") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)


def get_rating_text(total):
    if total >= 80:
        return "✅ 強烈建議建倉"
    elif total >= 65:
        return "👍 穩健可考慮"
    elif total >= 50:
        return "⚠️ 謹慎，須嚴格停損"
    else:
        return "❌ 不建議"


def calculate_all(symbol, dte=DEFAULT_DTE, vix=20):
    """計算單一股票的所有指標"""
    data = get_historical_data(symbol)
    if data is None:
        return None

    iv = get_iv(symbol)
    pe = get_pe(symbol)
    earnings_date = get_earnings_date(symbol)

    # v5.0 評分
    above_ma20 = data["price"] > data["ma20"]
    above_ma50 = data["price"] > data["ma50"]

    score = calculate_v5_score(
        iv=iv,
        hv=data["hv_20"],
        price=data["price"],
        low_52w=data["low_52w"],
        high_52w=data["high_52w"],
        rsi=data["rsi"],
        pe=pe,
        above_ma20=above_ma20,
        above_ma50=above_ma50,
    )

    # 新功能計算
    annualized = calculate_annualized_return(data["price"], iv, dte)
    risk_rating, risk_ratio = calculate_risk_reward_rating(annualized, iv)
    position_size = calculate_position_size(score["total"], vix)
    entry_timing = get_entry_timing(dte, data["rsi"])

    # 板塊
    sector_info = SECTOR_MAP.get(symbol, ("其他", "⚪"))

    # 履約價
    strike = round(data["price"] * 0.92, 2)

    return {
        "symbol": symbol,
        "price": round(data["price"], 2),
        "hv": round(data["hv_20"], 1),
        "iv": round(iv, 1) if iv else 0.0,
        "pe": round(pe, 1) if pe else 0.0,
        "rsi": round(data["rsi"], 1),
        "dist_52w_low_pct": score["dist_52w_low_pct"],
        "dte": dte,
        "strike": strike,
        "annualized": annualized,
        "risk_rating": risk_rating,
        "risk_ratio": round(risk_ratio, 2),
        "position_size": position_size,
        "entry_timing": entry_timing,
        "earnings_date": earnings_date,
        "sector": sector_info[0],
        "sector_emoji": sector_info[1],
        "high_52w": round(data["high_52w"], 2),
        "low_52w": round(data["low_52w"], 2),
        "score": score,
        "rating": get_rating_text(score["total"]),
    }


def main():
    """主函數：計算所有股票"""
    stocks = STOCKS
    results = []

    for symbol in stocks:
        result = calculate_all(symbol)
        if result:
            results.append(result)

    # 按總分排序
    results.sort(key=lambda x: x["score"]["total"], reverse=True)

    # 添加排名和排名變化
    for i, r in enumerate(results):
        r["rank"] = i + 1
        arrow, change = get_rank_change(r["symbol"], r["rank"])
        r["rank_change"] = arrow
        r["rank_change_val"] = change

    # 保存今日數據
    save_ranking_data(results)

    return results


if __name__ == "__main__":
    results = main()
    print(json.dumps(results, indent=2, ensure_ascii=False))
