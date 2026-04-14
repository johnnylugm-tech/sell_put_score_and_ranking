# Sell Put v5.0 Skill

## 概述

Sell Put 評分模型 v5.0 的 Python 自動化實現。

**核心特點：**
- 完全脫離 LLM，純 Python 執行（避免幻覺）
- macOS 原生 launchd 定時器（穩定可靠）
- 微信通知自動化

---

## 架構

```
┌─────────────────────────────────────────────────────────────┐
│                    自動化架構                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  macOS launchd (每週一 09:00)                              │
│         │                                                   │
│         ▼                                                   │
│  cron_run.py (純 Python)                                   │
│    │                                                        │
│    ├── fetch_stock_data()  ──→ yfinance                    │
│    ├── fetch_option_data() ──→ yfinance option_chain       │
│    ├── calculate_scores()   ──→ 本地計算                    │
│    └── generate_excel()     ──→ openpyxl                    │
│                                                             │
│    │                                                        │
│    ▼                                                        │
│  微信通知 (openclaw exec 後台執行)                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 執行方式

### 手動執行

```bash
# 完整執行
python3 ~/.qclaw/workspace/skills/sellput-v5-skill/run.py

# 或 cron 模式（含日誌）
python3 ~/.qclaw/workspace/skills/sellput-v5-skill/cron_run.py
```

### 自動執行（launchd）

```bash
# 安裝/重裝
bash ~/.qclaw/workspace/skills/sellput-v5-skill/install_launchd.sh

# 手動觸發測試
launchctl start com.qclaw.sellput-v50

# 查看日誌
tail -f ~/Library/Logs/sellput-v50.log

# 卸載
launchctl unload ~/Library/LaunchAgents/com.qclaw.sellput-v50.plist
rm ~/Library/LaunchAgents/com.qclaw.sellput-v50.plist
```

---

## 文件結構

```
~/.qclaw/workspace/skills/sellput-v5-skill/
├── SKILL.md         (本文件)
├── run.py           (CLI 入口)
├── cron_run.py      (Cron 專用腳本)
├── core.py          (核心評分邏輯)
├── excel_gen.py     (Excel 報告生成)
├── install_launchd.sh (launchd 安裝腳本)
└── __pycache__/     (編譯緩存)
```

---

## 維度評分

| # | 維度 | 滿分 | 數據源 | 說明 |
|---|------|------|--------|------|
| ① | 距52W低點 | 23 | yfinance | 距52週低點% |
| ② | IV/HV | 18 | yfinance option_chain + HV | IV/HV 比率 |
| ③ | 基本面 | 28 | yfinance info | PE + FCF + 營收成長 |
| ④ | RSI | 9 | yfinance 歷史 | 60日 RSI |
| ⑤ | 流動性+相關性 | 8 | 市值 + Beta | 首次建倉默認5分 |
| ⑥ | 期權流動性 | 9 | option_chain | Spread + OI |
| ⑦ | 事件風險 | 5 | yfinance calendar | 距財報天數 |
| ⑧ | PoP×ROCC | 9 | Black-Scholes + 計算 | 效率指標 |
| ⑨ | 52W位置 | 4 | yfinance | 52週高低% |
| ⑩ | Skew | 4 | IV - HV | 波動率偏斜 |

**理論滿分：117分**

---

## 等級分界

| 等級 | 分數範圍 | 說明 |
|------|----------|------|
| A | ≥ 80 | 優質標的 |
| B | 65-79 | 良好標的 |
| C | 50-64 | 一般標的 |
| D | < 50 | 觀望 |

---

## P0 修正記錄

| 日期 | 修正內容 | 狀態 |
|------|----------|------|
| 2026-04-10 | IVR → IV/HV（52W IV 無法取得） | ✅ |
| 2026-04-10 | DTE 多到期日（30-45天窗口） | ✅ |
| 2026-04-10 | 財報日抓取修復（dict/DataFrame 兼容） | ✅ |
| 2026-04-10 | ③ 期權到期日 × 財報日交叉過濾（動態DTE窗口） | ✅ |
| 2026-04-10 | ④ FCF<0 → s3 上限 5 分 | ✅ |
| 2026-04-10 | ⑤ QQQ s3=0 直接跳過計算 | ✅ |
| 2026-04-10 | ⑥ MSFT 近52W低點警告 + Excel 警告欄 | ✅ |
| 2026-04-10 | 期權重試保護（yfinance 偶發返回空） | ✅ |

### P0-1 邏輯詳解

```
輸入：today, earnings_date, yfinance options 列表
計算：days_to_earnings = earnings_date - today

days > 30 → DTE窗口 = [30, 45]（正常）
7 < days ≤ 30 → DTE窗口 = [14, 60]（擴展 + 強制不涵蓋財報）
days ≤ 7 → DTE窗口 = [5, 60]（短期 Put 豁免）

若 earnings 落在 [today+窗口下界, today+45] 區間（NVDA 5/21 落在 5/15臨界）：
  → 強制只選 DTE ≤ days_to_earnings - 7 的到期日
  → NVDA: earnings=5/21 → hard_deadline=14天 → 選 DTE=13（4/24）
     ⚠️ 但 4/24 DTE=13 <20 不在 valid_exps → fallback 到 5/8（DTE=27）

最終邏輯：safe_and_valid = {e,d | d in window AND NOT covers_earnings(e)}
         fallback = {e,d | d in window AND covers_earnings(e)}  # 數據約束時

---

## 數據正確性承諾

1. **所有數據即時從 yfinance 獲取**
2. **IVR 因數據不可得，改用 IV/HV 並明確標示**
3. **禁止幻覺：不編造任何價格、漲跌幅、財務數據**
4. **期權 Delta 使用 Black-Scholes 公式計算**

---

## 常見問題

### Q: 為什麼不用 OpenClaw Cron？
A: OpenClaw Cron 使用 agentTurn + Prompt，會調用 LLM 有幻覺風險且執行慢。

### Q: launchd 和 cron 有什麼區別？
A: launchd 是 macOS 原生服務管理器，比 cron 更穩定，支持日誌和重啟恢復。

### Q: 執行失敗怎麼辦？
A: 檢查 `~/Library/Logs/sellput-v50.error.log` 查看錯誤詳情。

---

## 版本

- v5.0: 初始版本
- v5.0-P0: IVR 修正、DTE 修正、財報日修復
