#!/usr/bin/env bash
# 🌀 Obsidian 日报同步脚本（增强版）
# 用法: bash scripts/obsidian-sync.sh [YYYY-MM-DD]
# 功能: HTML→Markdown表格转换 + 个股独立页面 + 全部报告类型
set -e

WORKSPACE="/Users/shisan/.openclaw/workspace"
DATE="${1:-$(date '+%Y-%m-%d')}"

cd "$WORKSPACE"
echo "🌀 同步到 Obsidian | $DATE"
python3 scripts/parse_html.py "$DATE"
echo "✅ 同步完成"
