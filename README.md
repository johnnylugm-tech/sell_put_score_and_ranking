# Sell Put Score & Ranking

> **v5.0 Sell Put 評分模型** — 純 Python 自動化實現，脫離 LLM，拒絕幻覺

[![Python 3.14+](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 概述

Sell Put Score & Ranking 是一個**完整的選擇權評分系統**，用於評估股票的 Sell Put 策略適合度。

### 核心理念

- **完全脫離 LLM**：純 Python 執行，杜絕 AI 幻覺
- **數據真實性**：所有數據來自 yfinance 即時市場
- **透明計算**：每個維度的計算鏈完全公開可查

---

## 📊 評分維度（v5.0）

| # | 維度 | 滿分 | 說明 |
|---|------|------|------|
| ① | 距52W低點 | 23 | 距52週低點% — 越大越安全 |
| ② | IV/HV | 18 | 波動率溢價比率 |
| ③ | 基本面 | 28 | PE + FCF + 營收成長 |
| ④ | RSI | 9 | 60日 RSI |
| ⑤ | 流動性+相關性 | 8 | 市值 + Beta |
| ⑥ | 期權流動性 | 9 | Spread + OI |
| ⑦ | 事件風險 | 5 | 距財報天數 |
| ⑧ | PoP×ROCC | 9 | 獲利機率×資金效率 |
| ⑨ | 52W位置 | 4 | 價格在年度區間位置 |
| ⑩ | Skew | 4 | 波動率偏斜 |

**理論滿分：117 分**

### 等級分界

| 等級 | 分數 | 說明 |
|------|------|------|
| **A** | ≥ 80 | 優質標的，優先考慮 |
| **B** | 65-79 | 良好標的，深入分析後可操作 |
| **C** | 50-64 | 一般標的，條件苛刻才執行 |
| **D** | < 50 | 觀望，本週期不建議 |

---

## 🚀 快速開始

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 基本使用

```bash
# 完整執行（評分 + Excel報告）
python3 run.py

# 查看幫助
python3 run.py --help

# JSON 輸出（供自動化使用）
python3 run.py --json
```

### 自動化

crontab 執行：
```bash
# 每週一至五 21:00 台北時間執行
0 21 * * 1-5 cd ~/.qclaw/workspace/skills/sellput-v5-skill && python3 sell_put_report_telegram.py
```

---

## 📁 專案結構

```
sell_put_score_and_ranking/
├── run.py              # CLI 入口（完整排名報告 + Excel）
├── report_formatter.py  # 格式化輸出（自動化使用）
├── sell_put_report_telegram.py  # 直接發送 Telegram（繞過 AI Agent）
├── core.py             # 核心評分邏輯
├── excel_gen.py        # Excel 報告生成
├── cron_run.py         # 定時執行腳本
├── docs/               # 文件
│   └── v5.0_MODEL.md   # 模型設計文件
├── case_studies/       # 案例研究
├── memory/             # 記憶與歸檔
├── skills/             # 技能目錄
│   └── stock-market-pro/
│       └── scripts/    # 額外腳本（A50分析、IV日誌等）
├── requirements.txt
├── install_launchd.sh
└── LICENSE
```

---

## 🔬 維度詳解

### ① 距52W低點（23分）

| 距低點漲幅 | 分數 |
|-----------|------|
| ≥ 200% | 23 |
| 150% – 200% | 20 |
| 100% – 150% | 17 |
| 50% – 100% | 13 |

### ③ 基本面（28分）

```python
# 子分 A：PE（9分）
PE ≤ 20 → 9分
PE 20-30 → 7分
PE 30-50 → 5分

# 子分 B：FCF（10分）
FCF > $10B → 10分
FCF $1B-$10B → 7分

# 子分 C：營收成長（9分）
成長 ≥ 20% → 9分
成長 10-20% → 6分
```

### ⑧ PoP×ROCC 效率分（9分）

```python
# ROCC = 年化回報率
ROCC = (Bid / (Price × 0.20)) × (365 / DTE) × 100

# DTE 效率係數（30-45天最優）
30 ≤ DTE ≤ 45 → ×1.10
21 ≤ DTE < 30 → ×1.00

# PoP（獲利機率）
PoP = 1 - |Delta|

# Efficiency = ROCC × PoP
```

---

## ⚙️ 宏觀體制（VIX）

| 體制 | VIX | 操作建議 |
|------|-----|---------|
| 1 | < 15 | 正常操作 ×1.00 |
| 2 | 15-20 | 標準操作 ×1.00 |
| 3 | 20-25 | 降低Delta ×0.85 |
| 4 | 25-35 | 大幅保守 ×0.70 |
| 5 | > 35 | 🚫 **停止所有新倉** |

---

## 📈 輸出範例

```
============================================================
Sell Put 評分模型 v5.0
============================================================
執行日期: 2026-04-11 00:00:00
股票數量: 16 檔

【排名報告 v5.0】
  # 代碼   等 總分     現價  IV%   HV%    PE   RSI  距低%      DTE     履約價
----------------------------------------------------------------------------------------------------------------------
  1 MU      A  92.0  426.56  38.2  39.8  25.6   55   89.3    38D   392.44
...

生成 Excel: ./sell_put_v5.0_20260411.xlsx
✅ 完成
```

---

## 🔒 數據正確性承諾

1. **所有數據即時從 yfinance 獲取**
2. **禁止估算：不編造任何價格、漲跌幅、財務數據**
3. **期權 Greeks 使用 Black-Scholes 公式計算**
4. **IV Rank 因數據不可得，改用 IV/HV 並明確標示**

---

## ⚠️ 限制與已知問題

| 問題 | 說明 | 解決方案 |
|------|------|---------|
| IVR 無52W歷史 | 無免費 API 提供 IV 52W 歷史 | 使用 IV/HV 比代替 |
| ETF 評分 | ETF 無 PE/FCF 等指標 | 給予基礎分或排除 |
| MU Forward PE 異常 | 市場數據，標記⚠️ | 需人工覆核 |

---

## 📝 授權

MIT License - 詳見 LICENSE 文件

---

## 📚 延伸閱讀

- [v5.0 模型設計文件](./docs/v5.0_MODEL.md)
- [維度評分細則](./docs/scoring_rules.md)
- [Black-Scholes 選擇權定價](https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model)
