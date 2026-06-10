#!/usr/bin/env bash
# Watchlist API 保活脚本（每5分钟由cron调用）
# 检测进程是否存活，挂了自动重启

if ! curl -sf http://127.0.0.1:18790/watchlist > /dev/null 2>&1; then
    cd /Users/shisan/.openclaw/workspace
    nohup python3 scripts/watchlist_api.py > /tmp/watchlist_api.log 2>&1 &
    echo "[$(date '+%Y-%m-%d %H:%M')] Watchlist API 已重启" >> /tmp/watchlist_keepalive.log
fi
