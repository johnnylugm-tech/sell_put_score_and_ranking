#!/usr/bin/env python3
"""
Sell Put Report - 只生成報告並輸出到 stdout
發送由 OpenClaw cron delivery 機制處理
"""
import subprocess
import os
import sys

SKILL_DIR = os.path.expanduser("~/.qclaw/workspace/skills/sellput-v5-skill")

def main():
    print("📊 執行 Sell Put 報告...")
    
    # 生成報告
    result = subprocess.run(
        ["python3", "report_formatter.py"],
        cwd=SKILL_DIR,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "PYTHONPATH": SKILL_DIR}
    )
    
    if result.returncode != 0:
        print(f"❌ 執行失敗\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    report = result.stdout
    print(f"✅ 報告生成成功，長度: {len(report)} 字元")
    
    # 只輸出報告內容，由 OpenClaw delivery 處理發送
    print(report)

if __name__ == "__main__":
    main()
