# 長期記憶庫

## 關於 Johnny

我是他的 AI 助理，專門幫他處理選擇權交易和美股分析。

- 時區：台北（Asia/Taipei）
- 平台：Mac mini + Telegram
- 喜歡：直接、有數據、硬核風格
- 語言：繁體中文

---

## 核心原則

遇到問題就修，不要等。數學交給 Python，不要自己算。

---

## 當前持倉

**美股：** 空倉觀望中

**台股：** 00637L（滬深300 ETF）
- 960張，成本 $15.20
- 目標：分批減碼
- 停損：$18.04

## Sell Put v5.0 系統狀態（2026-04-17）

**版本：v5.0_FINAL（`8f5e36d`）**
本地端代碼、GitHub、v5.0_MODEL_REVISED.md 三方一致。

**修復歷史：**
- 2026-04-16 晚間：收到 5 份外部評估報告，修復 22 個問題（`12e3a83`）
- 2026-04-17：完整審計修復（10 項）+ 第二輪審計修復（s7邏輯 + Doc矛盾 3 處）

---

## Sell Put 系統

這是我們的核心交易系統。

**每天早上 09:00（Taipei）** 收到一份 16 檔股票的評估報告，用於判斷要不要開新倉。

**終極問題：** 如果被行權，我願意以這個履約價長期持有這檔股票嗎？

**模型版本：** v5.0_FINAL（`8f5e36d`）
- 代碼：`~/.qclaw/workspace/skills/sellput-v5-skill/`
- GitHub：`https://github.com/johnnylugm-tech/sell_put_score_and_ranking`
- 評估分數：87.2/100（5份外部評估平均）

**當前狀態：** ✅ 代碼、Doc、GitHub 三方一致（2026-04-17 `8f5e36d`）

**進場信號（三選一）：**
1. Gap 大跌（< 履約價 + 5%）
2. VIX > 35 或單日飆 +10
3. 財報 < 7 天

**模型版本：**
- v5.0：用於每天 cron 排名
- v2.1：用於深度分析

**16 檔觀察名單：**
半導體：MU, TSM, AVGO, AMD, NVDA, MRVL, INTC
科技：GOOGL, AAPL, MSFT, AMZN
其他：ALAB, VST, ARM, TSLA, QQQ

⚠️ 半導體佔 7/16，太集中會有系統性風險

---

## Cron Jobs

| 時間 | 功用 |
|------|------|
| 12:00 Mon-Fri | 盤前快報（VIX、隔夜行情） |
| 21:00 Mon-Fri | 每日排名報告（完整 16 檔） |
| 22:00 Mon-Fri | IV 日誌（累積歷史數據） |
| 每週一 09:00 | IV 週報 |
| 09:35 Mon-Fri | 00637L 分析 |

---

## 技術規定

- 所有股價/IV/HV 查詢：統一用 `stock-market-pro` skill
- Python 腳本算數學，禁止 LLM 自己算
- `sell_put_ranking.py` 是強制計算工具，不可篡改

---

## 待修復

- Gemini API Key（image 分析功能受影響）

---

## 檔案位置

- Sell Put 模型：`~/.qclaw/workspace/skills/sellput-v5-skill/`
- 00637L 分析：`~/.openclaw/workspace-option/skills/00637l-analysis/`
- IV 資料庫：`memory/iv_database.json`

---

## 歷史記錄

2026-03 的詳細記錄在 `memory/archive/2026-03/`
2026-04 前半的記錄在 `memory/archive/2026-04-early/`

---

最後更新：2026-04-15
