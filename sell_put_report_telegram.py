#!/usr/bin/env python3
"""
Sell Put Report - 直接發送完整報告到 Telegram（不使用 AI Agent）
繞過 cron announce 機制，直接用 Telegram Bot API 發送
"""
import subprocess
import os
import sys
import urllib.request
import urllib.parse
import json

SKILL_DIR = os.path.expanduser("~/.qclaw/workspace/skills/sellput-v5-skill")
TELEGRAM_CHAT_ID = "7550668951"

def get_default_bot_token():
    """從 openclaw.json 取得預設 Telegram Bot Token"""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(config_path) as f:
        config = json.load(f)
    accounts = config["channels"]["telegram"]["accounts"]
    default = accounts.get("default", {})
    return default.get("botToken", "")

MAX_MSG_SIZE = 4000  # Telegram 訊息上限 4096，留 96 字元 buffer

def send_telegram(text, token):
    """使用 Telegram Bot API 發送訊息"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def send_telegram_splits(text, token):
    """分段發送，確保每段不超過 MAX_MSG_SIZE"""
    import time
    if len(text) <= MAX_MSG_SIZE:
        r = send_telegram(text, token)
        return [r]
    # 在換行處分割
    parts = []
    while len(text) > MAX_MSG_SIZE:
        split_pt = text.rfind('\n', 0, MAX_MSG_SIZE)
        if split_pt == -1:
            split_pt = MAX_MSG_SIZE
        parts.append(text[:split_pt])
        text = text[split_pt:]
    if text:
        parts.append(text)
    results = []
    for i, part in enumerate(parts):
        r = send_telegram(part, token)
        print(f"  {'✅' if r.get('ok') else '❌'} 第{i+1}段 ({len(part)} 字)")
        if not r.get("ok"):
            print(f"     錯誤: {r}")
        results.append(r)
        time.sleep(1)
    return results

def main():
    print("📊 執行 Sell Put 報告...")
    
    # Step 1: 生成報告
    result = subprocess.run(
        ["python3", "report_formatter.py"],
        cwd=SKILL_DIR,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "PYTHONPATH": SKILL_DIR}
    )
    
    if result.returncode != 0:
        err_msg = f"❌ 執行失敗\n{result.stderr}"
        print(err_msg)
        # 嘗試發送錯誤訊息
        token = get_default_bot_token()
        if token:
            send_telegram(err_msg, token)
        sys.exit(1)
    
    report = result.stdout
    print(f"✅ 報告生成成功，長度: {len(report)} 字元")
    
    # Step 2: 直接發送到 Telegram
    token = get_default_bot_token()
    if not token:
        print("❌ 無法取得 Telegram Bot Token")
        sys.exit(1)
    
    print(f"📤 發送到 Telegram...")
    try:
        results = send_telegram_splits(report, token)
        ok_count = sum(1 for r in results if r.get("ok"))
        print(f"📤 發送完成：{ok_count}/{len(results)} 段成功")
    except Exception as e:
        print(f"❌ 發送例外: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
