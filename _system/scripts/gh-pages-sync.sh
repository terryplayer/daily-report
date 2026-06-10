#!/usr/bin/env bash
# 🚀 Cloudflare Pages 同步脚本（自动维护首页索引）
# 用法: bash scripts/gh-pages-sync.sh
# 作用: 将 daily-report-html/ 同步到 GitHub main，Cloudflare Pages 自动部署

set -e
cd "$(dirname "$0")/.."
WORKSPACE=$(pwd)

echo "🌀 同步到 Cloudflare Pages（GitHub → 自动部署）..."

cd daily-report-html

# ---- 计算行业龙头 ----
python3 "$WORKSPACE/scripts/calc_sector_leaders.py" 2>&1 | tail -3

# ---- 生成完整 Dashboard（标准+进阶版报告，唯一入口）----
python3 "$WORKSPACE/scripts/gen_dashboard.py" 2>&1 | tail -3

# ---- index.html 为静态主页，不在此更新 ----
# 如需重新生成，手动运行 python3 scripts/gen_index.py

# ---- 提交并推送到 GitHub（触发 Cloudflare Pages 自动部署） ----
# 只提交简报HTML文件，不自动覆盖其他修改
git add *.html
if git diff --cached --quiet; then
    echo "✅ 没有新文件需要推送"
else
    git commit -m "📊 同步报告 $(date '+%Y-%m-%d %H:%M')"
git commit -m "📊 同步报告 $(date '+%Y-%m-%d %H:%M')"
    
    # 重试机制：推送失败后重试3次
    RETRY=0
    MAX_RETRY=3
    until [ $RETRY -ge $MAX_RETRY ]; do
      if git push origin main 2>&1; then
        echo "✅ 推送 GitHub 完成 → Cloudflare Pages 自动部署中"
        break
      else
        RETRY=$((RETRY+1))
        if [ $RETRY -lt $MAX_RETRY ]; then
          echo "⚠️ 推送失败，${MAX_RETRY}秒后第${RETRY}次重试..."
          sleep $MAX_RETRY
        else
          echo "❌ 推送失败，已达到最大重试次数"
          # 尝试 GIT_ASKPASS=echo 方式
          echo "🔁 尝试备用认证方式..."
          GIT_ASKPASS=echo git push origin main 2>&1 || echo "❌ 备用方式也失败"
        fi
      fi
    done
fi

# ---- 保底：用 wrangler 直接部署（确保 Cloudflare 更新） ----
CLOUDFLARE_API_TOKEN=$(python3 -c "import json; print(json.load(open('/Users/shisan/.wrangler/config.json'))[0]['api_token'])" 2>/dev/null) || true
export CLOUDFLARE_API_TOKEN
if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
  npx --yes wrangler pages deploy . --project-name=daily-report --branch=main 2>&1 | tail -3
fi

echo "🌐 https://daily-report-3ai.pages.dev"
