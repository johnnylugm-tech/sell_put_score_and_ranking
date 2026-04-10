#!/usr/bin/env python3
"""
Sell Put v5.0 獨立執行腳本
完全脫離 LLM，直接執行 + 通知
"""
import sys
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

# 設定
WORKSPACE = Path.home() / '.qclaw' / 'workspace'
SKILL_DIR = WORKSPACE / 'skills' / 'sellput-v5-skill'
OUTPUT_DIR = WORKSPACE
NOTIFY_FILE = WORKSPACE / 'last_result.json'
LOG_FILE = WORKSPACE / 'sellput_cron.log'

def log(msg):
    """日誌記錄"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def run_python():
    """執行核心評分腳本"""
    log("開始執行 Sell Put v5.0 評分...")
    
    result = subprocess.run(
        ['python3', 'run.py'],
        cwd=SKILL_DIR,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    if result.returncode != 0:
        log(f"❌ 執行失敗: {result.stderr}")
        return False, result.stderr
    
    log("✅ 評分完成")
    return True, result.stdout

def parse_results(stdout):
    """解析執行輸出"""
    results = {
        'a_grade': [],
        'forbidden': [],
        'warnings': [],
        'vix': None,
        'date': datetime.now().strftime('%Y-%m-%d')
    }
    
    lines = stdout.split('\n')
    for line in lines:
        if 'VIX=' in line:
            try:
                vix_str = line.split('VIX=')[1].split()[0]
                results['vix'] = float(vix_str)
            except:
                pass
        
        if ' A ' in line and any(t in line for t in ['MU', 'TSM', 'AVGO', 'AMD', 'NVDA']):
            parts = line.strip().split()
            if len(parts) >= 3:
                ticker = parts[1]
                grade = 'A'
                # 提取分數
                for p in parts:
                    if p.endswith('分'):
                        score = p.replace('分', '')
                        results['a_grade'].append({'ticker': ticker, 'grade': grade, 'score': score})
        
        if '🚫' in line:
            results['forbidden'].append(line.strip())
        
        if '⚠️' in line:
            results['warnings'].append(line.strip())
    
    return results

def get_latest_excel():
    """獲取最新的 Excel 檔案"""
    excel_files = list(OUTPUT_DIR.glob('sell_put_v5.0_*.xlsx'))
    if excel_files:
        latest = max(excel_files, key=lambda p: p.stat().st_mtime)
        return latest.name, latest.stat().st_size
    return None, 0

def send_wechat_notify(results, excel_name, excel_size):
    """發送微信通知"""
    if results['vix']:
        msg = f"📊 Sell Put v5.0 | {results['date']} | VIX={results['vix']:.1f}\n\n"
    else:
        msg = f"📊 Sell Put v5.0 | {results['date']}\n\n"
    
    if results['a_grade']:
        msg += f"A級 TOP {len(results['a_grade'])}:\n"
        for i, r in enumerate(results['a_grade'][:8], 1):
            msg += f"{i}. {r['ticker']} A {r['score']}\n"
    
    if results['forbidden']:
        msg += f"\n🚫 禁止新倉: {', '.join(results['forbidden'])}\n"
    
    if results['warnings']:
        for w in results['warnings']:
            msg += f"\n{w}\n"
    
    if excel_name:
        size_kb = excel_size / 1024
        msg += f"\n📁 {excel_name} ({size_kb:.0f}KB)"
    
    # 保存通知內容（供外部讀取）
    with open(NOTIFY_FILE, 'w') as f:
        json.dump({'message': msg, 'timestamp': datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    # 嘗試發送微信（使用 openclaw exec 如果可用）
    try:
        # 寫入通知腳本
        notify_script = OUTPUT_DIR / 'wechat_notify.sh'
        escaped_msg = msg.replace("'", "'\"'\"'")
        script_content = f'''#!/bin/bash
openclaw exec -- \\
  message send \\
  --channel openclaw-weixin \\
  --target "o9cq808YRb-FoS5Ek9CwSHm1q-2w@im.wechat" \\
  --message '{escaped_msg}'
'''
        with open(notify_script, 'w') as f:
            f.write(script_content)
        os.chmod(notify_script, 0o755)
        
        # 後台執行（不等待結果）
        subprocess.Popen(
            ['bash', str(notify_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log("✅ 微信通知已發送（後台）")
    except Exception as e:
        log(f"⚠️ 通知異常: {e}")
    
    return msg

def main():
    """主入口"""
    log("=" * 60)
    log("Sell Put v5.0 Cron 執行")
    log("=" * 60)
    
    # 執行評分
    success, output = run_python()
    
    if not success:
        log("❌ 執行失敗，通知管理員")
        # 發送錯誤通知
        error_msg = f"🚨 Sell Put v5.0 執行失敗\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n錯誤: {output}"
        with open(NOTIFY_FILE, 'w') as f:
            json.dump({'message': error_msg, 'error': True}, f, ensure_ascii=False)
        sys.exit(1)
    
    # 解析結果
    results = parse_results(output)
    
    # 獲取 Excel
    excel_name, excel_size = get_latest_excel()
    
    # 發送通知
    msg = send_wechat_notify(results, excel_name, excel_size)
    
    log("=" * 60)
    log("執行完成")
    log("=" * 60)
    
    print("\n" + msg)

if __name__ == '__main__':
    main()
