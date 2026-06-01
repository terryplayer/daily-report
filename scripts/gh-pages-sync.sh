#!/usr/bin/env bash
# 🚀 Cloudflare Pages 同步脚本（自动维护首页索引）
# 用法: bash scripts/gh-pages-sync.sh
# 作用: 将 daily-report-html/ 同步到 GitHub main，Cloudflare Pages 自动部署

set -e
cd "$(dirname "$0")/.."
WORKSPACE=$(pwd)

echo "🌀 同步到 Cloudflare Pages（GitHub → 自动部署）..."

cd daily-report-html

# ---- 用Python脚本生成 index.html（匹配模板结构）----
python3 "$WORKSPACE/scripts/gen_index.py"

# ---- 提交并推送到 GitHub（触发 Cloudflare Pages 自动部署） ----
# 只提交简报HTML文件，不自动覆盖其他修改
git add *.html
if git diff --cached --quiet; then
    echo "✅ 没有新文件需要推送"
else
    git commit -m "📊 同步报告 $(date '+%Y-%m-%d %H:%M')"
    git push github main
    echo "✅ 推送 GitHub 完成 → Cloudflare Pages 自动部署中"
fi

# ---- 保底：用 wrangler 直接部署（确保 Cloudflare 更新） ----
CLOUDFLARE_API_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/shisan/.wrangler/config.json'))[0]['api_token'])" 2>/dev/null) || true
export CLOUDFLARE_API_TOKEN
if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
  npx --yes wrangler pages deploy . --project-name=daily-report --branch=main 2>&1 | tail -3
fi

echo "🌐 https://daily-report-3ai.pages.dev"
