# 長期記憶庫

## 當前持倉

**美股：** 空倉觀望中

**台股：** 00637L（滬深300 ETF）
- 960張，成本 $15.20
- 目標：分批減碼
- 停損：$18.04

## Sell Put 系統

這是我們的核心交易系統。

**每天早上 09:00（Taipei）** 收到一份 16 檔股票的評估報告，用於判斷要不要開新倉。

**終極問題：** 如果被行權，我願意以這個履約價長期持有這檔股票嗎？

**模型版本：** v5.0_FINAL（`51ed4c8`）
- 代碼：`~/.qclaw/workspace/skills/sellput-v5-skill/`
- GitHub：`https://github.com/johnnylugm-tech/sell_put_score_and_ranking`
- 評估分數：87.2/100（5份外部評估平均）

**當前狀態：** ✅ 代碼、Doc、GitHub 三方一致（2026-04-24 `508326b` 審計修復）
- 新增：IV被高估警告（IV/HV>1.5）
- 新增：IV數據可疑警告（tier=t2+IV<10%）
- 修復：report_formatter timing 直接由 DTE+RSI 重新計算

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

## 技術規定（已移至 AGENTS.md §7）

---

## 檔案位置（已移至各技能 SKILL.md）

---

## 歷史記錄（已移至 archive）

---

最後更新：2026-04-22
