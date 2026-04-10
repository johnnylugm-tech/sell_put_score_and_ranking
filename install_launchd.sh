#!/bin/bash
# Sell Put v5.0 launchd 安裝腳本
# 完全脫離 OpenClaw Cron，使用 macOS 原生定時器

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.qclaw.sellput-v50.plist"

echo "=============================================="
echo "Sell Put v5.0 launchd 安裝腳本"
echo "=============================================="

# 創建 LaunchAgents 目錄
mkdir -p "$LAUNCH_AGENTS_DIR"

# 生成 plist
cat > "$LAUNCH_AGENTS_DIR/$PLIST_NAME" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.qclaw.sellput-v50</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>__SCRIPT_DIR__/cron_run.py</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>0</integer>
            <key>Weekday</key>
            <integer>1</integer>
        </dict>
    </array>
    
    <key>RunAtLoad</key>
    <false/>
    
    <key>StandardOutPath</key>
    <string>__HOME__/Library/Logs/sellput-v50.log</string>
    
    <key>StandardErrorPath</key>
    <string>__HOME__/Library/Logs/sellput-v50.error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    
    <key>ProcessType</key>
    <string>Background</string>
    
    <key>ThrottleInterval</key>
    <integer>60</integer>
</dict>
</plist>
EOF

# 替換路徑佔位符
sed -i '' "s|__SCRIPT_DIR__|$SCRIPT_DIR|g" "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
sed -i '' "s|__HOME__|$HOME|g" "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo "✅ plist 已生成: $LAUNCH_AGENTS_DIR/$PLIST_NAME"

# 卸載舊任務（如果存在）
echo "檢查舊任務..."
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null

# 載入新任務
echo "載入定時任務..."
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

# 驗證
echo ""
echo "=============================================="
echo "驗證安裝"
echo "=============================================="
launchctl list | grep sellput

echo ""
echo "✅ 安裝完成！"
echo ""
echo "執行記錄: ~/Library/Logs/sellput-v50.log"
echo "錯誤記錄: ~/Library/Logs/sellput-v50.error.log"
echo ""
echo "手動觸發測試:"
echo "  launchctl start com.qclaw.sellput-v50"
echo ""
echo "卸載:"
echo "  launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
echo "  rm ~/Library/LaunchAgents/$PLIST_NAME"
