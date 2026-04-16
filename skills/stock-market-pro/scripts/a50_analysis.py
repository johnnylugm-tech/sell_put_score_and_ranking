#!/usr/bin/env python3
"""
A50 期指每日分析 v5.0
充分利用 China Stock Plugin + yfinance
"""

import subprocess
import json
import math
import os
from datetime import datetime, timedelta

VENV_PYTHON = "/Users/johnny/.openclaw/venv/bin/python3"
PLUGIN      = "/Users/johnny/.openclaw/extensions/openclaw-data-china-stock/tool_runner.py"
CACHE       = os.path.expanduser("~/.openclaw/workspace-option/memory/northbound_5d.json")


# ─── Plugin 工具 ───────────────────────────────────────────

def call_plugin(name, args=None):
    args = args or {}
    r = subprocess.run(
        [VENV_PYTHON, PLUGIN, name, json.dumps(args)],
        capture_output=True, text=True, timeout=30
    )
    try:
        return json.loads(r.stdout)
    except:
        return {"success": False, "error": r.stdout[:200]}


def fetch_a50():
    h = call_plugin("tool_fetch_a50_data", {
        "data_type": "historical",
        "start_date": (datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
        "end_date":   (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    })
    r = call_plugin("tool_fetch_a50_data", {"data_type": "realtime"})
    return r, h


def fetch_csi300():
    return call_plugin("tool_fetch_index_realtime", {"index_code": "000300"})


def fetch_commodities():
    return call_plugin("tool_fetch_macro_commodities", {"disable_network": False})


def fetch_northbound_today():
    """Plugin 即時數據（當日口徑，可能 ≈0）"""
    return call_plugin("tool_fetch_northbound_flow", {"lookback_days": 1})


# ─── USD/CNY（yfinance）─────────────────────────────────

def fetch_usdcny():
    try:
        import yfinance as yf
        t = yf.Ticker("USDCNY=X")
        hist = t.history(period="5d", auto_adjust=True)
        if hist is None or hist.empty:
            return None, None
        curr = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2] if len(hist) >= 2 else curr
        chg  = (curr - prev) / prev * 100
        return curr, chg
    except:
        return None, None


# ─── 北向資金 Rolling Cache ───────────────────────────────

def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def load_nb_cache():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    return {}


def save_nb_cache(data):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_nb_cache():
    """
    嘗試從 push2his（快）拉當日口徑，並更新 rolling cache。
    若當日北向口徑仍 ≈0（市場仍在交易），則寫入快取為當日參考值。
    """
    try:
        import akshare as ak, warnings
        warnings.filterwarnings('ignore')
        df = ak.stock_hsgt_fund_flow_summary_em()
        # 找北向（沪股通+深股通，方向=北向）
        nb = df[df['资金方向'] == '北向']
        if nb.empty:
            return
        trade_date = nb.iloc[0]['交易日']  # e.g. "2026-04-16"
        total_net  = nb['成交净买额'].sum()  # 可能 = 0（盤中口徑）
        cache = load_nb_cache()
        # 寫入（若當日已有且非零，不覆蓋）
        if trade_date not in cache:
            cache[trade_date] = round(float(total_net), 2)
        # 只保留最近30天
        cache = dict(sorted(cache.items())[-30:])
        save_nb_cache(cache)
    except Exception:
        pass  # 網路/解析失敗，跳過


# ─── 技術指標 ───────────────────────────────────────────

def calc_ma(p, n):
    return sum(p[-n:]) / n if len(p) >= n else None

def ma_dir(p, n):
    if len(p) < n + 5:
        return None
    old = sum(p[-(n+5):-5]) / n
    new = sum(p[-n:]) / n
    return (new - old) / old * 100

def calc_rsi(p, n=14):
    if len(p) < n + 1:
        return None
    deltas = [p[i] - p[i-1] for i in range(1, len(p))]
    gains  = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    ag = sum(gains[-n:]) / n
    al = sum(losses[-n:]) / n
    return 100 - (100 / (1 + ag / al)) if al else 100

def calc_boll(p, n=20):
    if len(p) < n:
        return None, None, None
    ma  = sum(p[-n:]) / n
    std = math.sqrt(sum((x - ma)**2 for x in p[-n:]) / n)
    return ma, ma + 2*std, ma - 2*std

def calc_macd(p, f=12, s=26):
    if len(p) < s:
        return None, None, None
    def ema(d, n):
        k = 2 / (n + 1)
        e = d[0]
        for x in d[1:]:
            e = x * k + e * (1 - k)
        return e
    ef = ema(p, f)
    es = ema(p, s)
    dif = ef - es
    return dif, dif, 0  # simplified histogram


# ─── 格式化工具 ──────────────────────────────────────────

def arrow(v):
    if v is None:    return "—"
    return "↗" if v > 0.1 else ("↘" if v < -0.1 else "→")

def rsi_label(v):
    if v is None:  return "—"
    if v > 70:      return f"🔴{v:.0f} 超買"
    if v < 30:      return f"🟢{v:.0f} 超賣"
    if v > 60:      return f"🟡{v:.0f} 偏強"
    if v < 40:      return f"🟡{v:.0f} 偏弱"
    return f"⚪{v:.0f}"


# ─── 主報告 ─────────────────────────────────────────────

def get_a50_analysis():
    # 嘗試更新北向 cache（背景）
    update_nb_cache()

    # 數據獲取
    a50_rt, a50_h  = fetch_a50()
    csi             = fetch_csi300()
    comm            = fetch_commodities()
    nb_today        = fetch_northbound_today()
    usdcny, usdcny_chg = fetch_usdcny()
    nb_cache        = load_nb_cache()

    # A50 即時
    if not a50_rt.get("success"):
        return f"❌ A50 數據失敗: {a50_rt.get('message')}"
    spot      = a50_rt.get("spot_data", {})
    a50_price = spot.get("current_price", 0)
    a50_chg   = spot.get("change_pct", 0)
    a50_vol   = spot.get("volume", 0)

    # A50 歷史
    if a50_h.get("success") and a50_h.get("hist_data"):
        klines = a50_h["hist_data"]["klines"]
        closes = [k["close"] for k in klines]
        highs  = [k["high"]  for k in klines]
        lows   = [k["low"]   for k in klines]
    else:
        closes, highs, lows = [a50_price], [a50_price], [a50_price]

    # CSI 300
    csi_p = csi.get("data", {}).get("current_price") if csi.get("success") else None
    csi_c = csi.get("data", {}).get("change_percent") if csi.get("success") else None

    # 商品
    commodities = {}
    if comm.get("success"):
        for item in comm.get("data", {}).get("items", []):
            chg = item.get("change_pct", 0) or 0
            for key, label in [("WTI","WTI原油"), ("GOLD","黃金"), ("COPPER","銅")]:
                if key not in commodities and (key in item.get("name","") or label in item.get("name","")):
                    commodities[key] = chg

    # 北向資金（當日信號）
    nb_signal_desc = "無數據"
    nb_action      = "—"
    nb_today_net   = None
    if nb_today.get("status") == "success" and nb_today.get("data"):
        d = nb_today["data"][0] if isinstance(nb_today["data"], list) else nb_today["data"]
        nb_today_net = d.get("total_net") or d.get("sh_net", 0) + d.get("sz_net", 0)
    sig = nb_today.get("signal", {})
    nb_signal_desc = sig.get("description", nb_signal_desc)
    nb_action      = sig.get("action", nb_action)

    # 北向 Rolling Cache（過去5日）
    sorted_dates = sorted(nb_cache.keys())[-5:]
    nb_5d = [(d, nb_cache[d]) for d in sorted_dates]
    nb_avg  = sum(v for _, v in nb_5d) / len(nb_5d) if nb_5d else 0
    nb_total = sum(v for _, v in nb_5d)

    # 52W
    high_52w = max(highs)
    low_52w  = min(lows)
    range_pct = (a50_price - low_52w) / (high_52w - low_52w) * 100 if high_52w > low_52w else 50

    # 技術
    ma5  = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)
    ma120 = calc_ma(closes, 120) if len(closes) >= 120 else None
    m5d  = ma_dir(closes, 5)
    m10d = ma_dir(closes, 10)
    m20d = ma_dir(closes, 20)
    rsi14 = calc_rsi(closes, 14)
    bb_m, bb_u, bb_l = calc_boll(closes, 20)
    bb_w  = (bb_u - bb_l) / bb_m * 100 if bb_m else 0
    dif, dea, macd_h = calc_macd(closes)

    # 布林位置
    if   a50_price >= bb_u: bb_pos = "🔴 突破上軌（超買）"
    elif a50_price <= bb_l: bb_pos = "🟢 跌破下軌（超賣）"
    elif a50_price > bb_m:  bb_pos = "🟡 中上軌"
    else:                    bb_pos = "🟡 中下軌"

    # 趨勢
    if   a50_price > ma20 > ma60:   trend = "📈 上升"
    elif a50_price < ma20 < ma60:   trend = "📉 下降"
    elif ma5 > ma10 > ma20:         trend = "↗ 短多排列"
    elif ma5 < ma10 < ma20:         trend = "↘ 短空排列"
    else:                            trend = "🔄 區間整理"

    # 支撐阻力
    r1, r2 = max(highs[-5:]), max(highs[-20:])
    s1, s2 = min(lows[-5:]),  min(lows[-20:])

    # 綜合情緒
    b = n = 0
    if rsi14 and rsi14 > 55: b += 1
    if rsi14 and rsi14 < 45: n += 1
    if dif   and dif   > 0: b += 1
    if dif   and dif   < 0: n += 1
    if a50_price > ma20:    b += 1
    if a50_price < ma20:    n += 1
    if m5d  and m5d  > 0:  b += 1
    if m5d  and m5d  < 0:  n += 1
    if csi_c and csi_c > 0.5: b += 1
    if csi_c and csi_c < -0.5: n += 1
    if   b > n + 2: overall = "🟢 偏多"
    elif n > b + 2: overall = "🔴 偏空"
    elif b > n:       overall = "🟡 中性偏多"
    elif n > b:       overall = "🟡 中性偏空"
    else:             overall = "⚪ 中性"

    # ── 建構輸出 ──
    L = []
    L.append("═" * 50)
    L.append("📊 A50 期指深度分析 v5.0")
    L.append("═" * 50)
    L.append(f"現價 {a50_price:,.0f}｜{a50_chg:+.1f}%｜{'放量' if a50_vol > 150000 else '縮量' if a50_vol < 100000 else '常量'}")

    # 全球宏觀
    L.append("")
    L.append("【全球宏觀】")
    L.append(f"  CSI 300  {csi_p:>10,.0f}  ({csi_c:+.2f}%)" if csi_p else "  CSI 300  —")
    L.append(f"  WTI原油        {commodities.get('WTI',0):+.2f}%")
    L.append(f"  黃金          {commodities.get('GOLD',0):+.2f}%")
    L.append(f"  銅            {commodities.get('COPPER',0):+.2f}%")
    if usdcny:
        cny_chg_str = f"{usdcny_chg:+.3f}%" if usdcny_chg is not None else ""
        if usdcny_chg is not None and usdcny_chg < -0.1:
            cny_sig = "🟢 CNY升值（利多A股）"
        elif usdcny_chg is not None and usdcny_chg > 0.1:
            cny_sig = "🔴 CNY貶值（利空A股）"
        else:
            cny_sig = "⚪ 匯率穩定"
        L.append(f"  USD/CNY  {usdcny:.4f}  {cny_chg_str}  {cny_sig}")

    # 北向資金
    L.append("")
    L.append("【北向資金】（北上資金，滬深港通）")
    today_str = nb_today_net if nb_today_net is not None else "—"
    emoji = "🟢" if (isinstance(today_str, (int,float)) and today_str > 0) else ("🔴" if isinstance(today_str, (int,float)) and today_str < 0 else "⚪")
    L.append(f"  {emoji} 當日凈流入  {today_str:>+10} 億（口徑：當日估算，收盤確認）" if isinstance(today_str,(int,float)) else f"  ⚪ 當日凈流入  {today_str}")
    if nb_5d:
        L.append(f"  📈 5日均值  {nb_avg:>+7.1f} 億/日")
        L.append(f"  📊 5日合計  {nb_total:>+7.1f} 億")
        for d, v in nb_5d:
            e = "🟢" if v > 0 else "🔴"
            L.append(f"    {e} {d[-5:]}:  {v:>+8.1f} 億")
    L.append(f"  信號：{nb_signal_desc} → {nb_action}")

    # A50 技術
    L.append("")
    L.append("【A50 技術】")
    L.append(f"  均線態勢：{trend}")
    L.append(f"  綜合判斷：{overall}（多{b}:空{n}）")
    L.append(f"  RSI(14)：{rsi_label(rsi14)}")
    L.append(f"  MACD：{'📈' if macd_h and macd_h > 0 else '📉'} DIF={dif:.0f} 柱={'+' if macd_h and macd_h > 0 else ''}{macd_h:.0f}" if dif else "  MACD：—")
    L.append(f"  布林帶：{bb_pos}（寬度{bb_w:.1f}%）")

    # 均線
    L.append("")
    L.append("【均線方向】")
    L.append(f"  MA5   {ma5:>7,.0f}  {arrow(m5d)}  {f'{m5d:+.2f}%' if m5d else ''}")
    L.append(f"  MA10  {ma10:>7,.0f}  {arrow(m10d)}")
    L.append(f"  MA20  {ma20:>7,.0f}  {arrow(m20d)}")
    L.append(f"  MA60  {ma60:>7,.0f}")
    if ma120: L.append(f"  MA120 {ma120:>7,.0f}")

    # 位階
    L.append("")
    L.append("【關鍵位階】")
    L.append(f"  🔴 5日高  {r1:>7,.0f}  20日高 {r2:>7,.0f}")
    if bb_u: L.append(f"  🔴 BB上軌 {bb_u:>7,.0f}")
    L.append(f"  🟢 5日低  {s1:>7,.0f}  20日低 {s2:>7,.0f}")
    if bb_l: L.append(f"  🟢 BB下軌 {bb_l:>7,.0f}")

    # 52W
    L.append("")
    L.append("【52W區間】")
    L.append(f"  高點 {high_52w:,.0f}（現價距高 {((a50_price/high_52w)-1)*100:.1f}%）")
    L.append(f"  低點 {low_52w:,.0f}（現價距低 +{((a50_price/low_52w)-1)*100:.1f}%）")
    L.append(f"  區間 {range_pct:.0f}% 位置（低→現→高）")

    # 操作
    L.append("")
    L.append("【操作參考】")
    if overall.startswith("🟢"):
        L.append(f"  → 偏多：{s1:,.0f} 附近可試多")
        L.append(f"  → 跌破 {s2:,.0f} 確認回調，減倉")
    elif overall.startswith("🔴"):
        L.append(f"  → 偏空：反彈至 {r1:,.0f} 受阻可試空")
        L.append(f"  → 突破 {r2:,.0f} 確認反彈，止損")
    else:
        L.append(f"  → 區間：突破 {r1:,.0f} 做多 / 跌破 {s1:,.0f} 做空")

    L.append("")
    L.append(f"生成時間：{datetime.now().strftime('%H:%M:%S')}")

    return "\n".join(L)


if __name__ == "__main__":
    print(get_a50_analysis())
