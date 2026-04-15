# 長期記憶庫 (Long-Term Memory)

> 這是經過整理的長期記憶，而非原始對話記錄

---

## 📌 關於用戶 (Johnny Lu)

- **Name:** Johnny Lu (呂小麟)
- **Timezone:** Asia/Taipei
- **平台:** Mac mini, Telegram
- **職業/興趣:** 選擇權交易、美股投資

---

## 🔑 重要偏好

| 項目 | 偏好 |
|------|------|
| 溝通風格 | 直接、硬核、有數據支撐 |
| 回覆長度 | 適中，重點優先 |
| 興趣領域 | 美股、科技股、AI、選擇權、量化交易 |
| 語言 | 中文（繁體） |

---

## ⚡ 核心行為準則

1. **立即修復錯誤** - 不要問！不要等待！
2. **生成子代理執行** - 所有執行任務由子代理處理
3. **專注分析與決策** - 只負責分析、專業決策、向我傳達結果
4. **Git 操作紅線：** 🚫 禁止 force push / 刪除分支 / 重寫歷史

---

## 📈 Sell Put 交易系統（核心）

### 終極決策問題
> 「如果被行權，以這個履約價，我願意長期持有這檔股票嗎？」

### 行動觸發三條件
1. Gap 開盤大跌：現價 < 履約價 + 5%
2. VIX 飆升：> 35 或單日 +10
3. 財報前倒數：< 7 天

### 模型版本（2026-04-14 確認）
| 版本 | 評分 | 應用 |
|------|------|------|
| v2.1 | 95/100 | 深度分析、個別標的評估 |
| **v5.0** | 75/100 | **✅ 每日排名監控（cron job 21:00 Taiwan）** |

### 當前持倉
| 類型 | 標的 | 履約價 | 到期日 | 狀態 |
|------|------|--------|--------|------|
| 美股 | — | — | — | ❌ 空倉觀望中 |
| 台股 | 00637L | 成本$15.20 | — | ✅ 960張，分批減碼中 |

### 16 檔觀察名單（2026-04-15）
**半導體（7檔）：** MU, TSM, AVGO, AMD, NVDA, MRVL, INTC
**科技（4檔）：** GOOGL, AAPL, MSFT, AMZN
**其他（5檔）：** ALAB, VST, ARM, TSLA, QQQ
**⚠️ 半導體集中度 >40% = 系統性風險警告**

### 技術紀律
- **LLM 禁止做數學** — Python 腳本計算，Agent 只呈現
- **stock-market-pro** — 所有股票報價/IV/HV 強制使用此 Skill
- **sell_put_ranking.py** — 強制計算工具，不可篡改

---

## 🔧 系統功能

### Cron Jobs（主要）
| Job | 時間（Taiwan）| 功能 |
|-----|------|--------|
| Sell Put 盤前快速掃描 | 12:00 Mon-Fri | VIX + Gap + 重要事件 |
| Sell Put 每日排名監控 | 21:00 Mon-Fri | 完整16檔排名報告 |
| IV History Logger | 22:00 Mon-Fri | 建立 IV 歷史資料庫 |
| IV Weekly Monitor | 每週一 09:00 | 週 IV 變化分析 |
| 00637L 每日分析 | 09:35 Mon-Fri | 十大因子追蹤 |

### IV 歷史資料庫
- **腳本：** `iv_history_logger.py` + `iv_weekly_monitor.py`
- **位置：** `memory/iv_database.json`
- **進度：** 建设中（需 252 天才可計算 IV Rank/Percentile）

---

## 📁 重要文件位置

| 檔案 | 位置 |
|------|------|
| Sell Put v5 模型 | `~/.qclaw/workspace/skills/sellput-v5-skill/` |
| 00637L 分析 | `~/.openclaw/workspace-option/skills/00637l-analysis/` |
| stock-market-pro | `~/.openclaw/workspace-option/skills/stock-market-pro/` |
| IV 資料庫 | `memory/iv_database.json` |

---

## ⚠️ 待修復

- Gemini API Key 問題（影響 image 分析功能）

---

## 📌 歷史存檔索引

以下詳細記錄已移至 `memory/archive/2026-03/`：
- 2026-03-15 ~ 2026-03-31 每日互動記錄
- Sell Put 模型版本演化（v1.0 → v2.1）完整過程
- A50 指數分析框架建立
- 初期 cron job 建置記錄

以下詳細記錄已移至 `memory/archive/2026-04-early/`：
- 2026-04-01 ~ 2026-04-07 每日互動記錄
- v3.x / v4.0 模型開發過程
- AMD 實戰驗證案例

---

> 最後更新：2026-04-15 17:30 (Asia/Taipei)
