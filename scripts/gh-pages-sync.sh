#!/usr/bin/env bash
# 🚀 Cloudflare Pages 同步脚本（自动维护首页索引）
# 用法: bash scripts/gh-pages-sync.sh
# 作用: 将 daily-report-html/ 同步到 GitHub main，Cloudflare Pages 自动部署

set -e
cd "$(dirname "$0")/.."
WORKSPACE=$(pwd)

echo "🌀 同步到 Cloudflare Pages（GitHub → 自动部署）..."

cd daily-report-html

# ---- 自动生成 index.html ----
TODAY=$(date '+%Y-%m-%d')

cat > index.html << 'INDEXHEAD'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌀 小十三 · 每日简报</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; background:#0d1117; color:#e6edf3; padding:40px 20px; }
.container { max-width:600px; margin:0 auto; }
h1 { color:#58a6ff; font-size:26px; margin-bottom:4px; display:flex; align-items:center; gap:8px; }
.subtitle { color:#8b949e; font-size:13px; margin-bottom:28px; }
.card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px 20px; margin-bottom:12px; }
.card h2 { font-size:15px; color:#f0f6fc; margin-bottom:10px; display:flex; align-items:center; gap:8px; }
.card h2 .badge { font-size:11px; background:#1f6feb; color:#fff; padding:1px 8px; border-radius:8px; font-weight:400; }
.date-group { border-bottom:1px solid #21262d; padding:10px 0; }
.date-group:last-child { border-bottom:none; }
.date-label { font-size:14px; color:#f0f6fc; font-weight:600; margin-bottom:6px; display:flex; align-items:center; gap:8px; }
.date-label .tag { font-size:11px; font-weight:400; padding:1px 6px; border-radius:4px; }
.tag-today { background:#1f6feb22; color:#58a6ff; border:1px solid #1f6feb44; }
.tag-weekend { background:#bf77f622; color:#bf77f6; border:1px solid #bf77f644; }
.report-links { display:flex; gap:8px; flex-wrap:wrap; }
.report-links a { display:inline-flex; align-items:center; gap:4px; font-size:13px; color:#8b949e; text-decoration:none; padding:4px 10px; border-radius:6px; transition:all .2s; border:1px solid #21262d; }
.report-links a:hover { color:#f0f6fc; background:#21262d; border-color:#30363d; }
.report-links a.pm { color:#d29922; }
.report-links a.pm:hover { background:#d2992211; border-color:#d2992244; }
.report-links a.dc { color:#3fb950; }
.report-links a.dc:hover { background:#3fb95011; border-color:#3fb95044; }
.report-links a.wr { color:#bc8cff; }
.report-links a.wr:hover { background:#bc8cff11; border-color:#bc8cff44; }
.report-links a.mid { color:#58a6ff; }
.report-links a.mid:hover { background:#58a6ff11; border-color:#58a6ff44; }
.report-links a.we { color:#bf77f6; }
.report-links a.we:hover { background:#bf77f611; border-color:#bf77f644; }
.weekly-row { padding:8px 0; border-bottom:1px solid #21262d; }
.weekly-row:last-child { border-bottom:none; }
.weekly-row a { display:flex; justify-content:space-between; align-items:center; padding:6px 8px; color:#e6edf3; text-decoration:none; border-radius:6px; transition:background .2s; }
.weekly-row a:hover { background:#21262d; }
.weekly-row .version { font-size:12px; color:#8b949e; }
.footer { text-align:center; color:#8b949e; font-size:12px; margin-top:32px; padding-top:16px; border-top:1px solid #21262d; line-height:1.8; }
</style>
</head>
<body>
<div class="container">

<h1>🌀 小十三 · 每日简报</h1>
<p class="subtitle">A股持仓分析 · 盘前 & 收盘 · 周复盘 · 周末资讯</p>
INDEXHEAD

# ---- 周复盘卡片 ----
echo '<div class="card">' >> index.html
echo '<h2>📋 周复盘</h2>' >> index.html

for wr in $(ls weekly-review-*.html 2>/dev/null | sort -r); do
  if [[ $wr =~ weekly-review-([0-9]{4}-[0-9]{2}-[0-9]{2})\.html ]]; then
    WR_DATE="${BASH_REMATCH[1]}"
    WR_LABEL="${WR_DATE}  $(date -j -f '%Y-%m-%d' "$WR_DATE" '+%A' 2>/dev/null | sed 's/Monday/周一/;s/Tuesday/周二/;s/Wednesday/周三/;s/Thursday/周四/;s/Friday/周五/;s/Saturday/周六/;s/Sunday/周日/')"
    wr_link="${wr%.html}"
    cat >> index.html << WEEKROW
<div class="weekly-row">
  <a href="$wr_link">
    <span>$WR_LABEL <span style="font-size:12px;color:#8b949e;font-weight:400;">完整版</span></span>
    <span class="version">完整版 →</span>
  </a>
</div>
WEEKROW
  fi
done

echo '</div>' >> index.html

# ---- 按日期卡片 ----
echo '<div class="card">' >> index.html
echo '<h2>📅 按日期 <span class="badge">最新在前</span></h2>' >> index.html

DAYS=""
for f in premarket-*.html daily-combined-*.html midday-*.html weekend-*.html; do
  [ -f "$f" ] || continue
  if [[ $f =~ (premarket|daily-combined|midday|weekend)-([0-9]{4}-[0-9]{2}-[0-9]{2})\.html ]]; then
    DAYS="$DAYS ${BASH_REMATCH[2]}"
  fi
done
SORTED_DAYS=$(echo "$DAYS" | tr ' ' '\n' | sort -ru | grep -v '^$')

for d in $SORTED_DAYS; do
  DW=$(date -j -f '%Y-%m-%d' "$d" '+%A' 2>/dev/null | sed 's/Monday/周一/;s/Tuesday/周二/;s/Wednesday/周三/;s/Thursday/周四/;s/Friday/周五/;s/Saturday/周六/;s/Sunday/周日/')
  DATE_LABEL="${d//-/.}  $DW"
  TODAY_TAG=""
  if [ "$d" = "$TODAY" ]; then
    # 判断是否周末
    DOW=$(date -j -f '%Y-%m-%d' "$d" '+%u' 2>/dev/null)
    if [ "$DOW" -gt 5 ]; then
      TODAY_TAG=' <span class="tag tag-weekend">周末</span>'
    else
      TODAY_TAG=' <span class="tag tag-today">今日</span>'
    fi
  fi

  echo '<div class="date-group">' >> index.html
  echo "  <div class=\"date-label\">${DATE_LABEL}${TODAY_TAG}</div>" >> index.html
  echo '  <div class="report-links">' >> index.html

  if [ -f "premarket-${d}.html" ]; then
    echo "    <a href=\"premarket-${d}\" class=\"pm\">📋 盘前简报</a>" >> index.html
  fi
  if [ -f "midday-${d}.html" ]; then
    echo "    <a href=\"midday-${d}\" class=\"mid\">🌤 午间监测</a>" >> index.html
  fi
  if [ -f "daily-combined-${d}.html" ]; then
    echo "    <a href=\"daily-combined-${d}\" class=\"dc\">📊 收盘汇总</a>" >> index.html
  fi
  if [ -f "weekend-${d}.html" ]; then
    echo "    <a href=\"weekend-${d}\" class=\"we\">🌙 周末简报</a>" >> index.html
  fi
  if [ -f "weekly-review-${d}.html" ]; then
    echo "    <a href=\"weekly-review-${d}\" class=\"wr\">📑 周复盘</a>" >> index.html
  fi

  echo '  </div>' >> index.html
  echo '</div>' >> index.html
done

echo '</div>' >> index.html

# 底部说明
cat >> index.html << 'INDEXFOOT'
<div class="card" style="background:#0d1117;border-color:#21262d;">
<p style="font-size:13px;color:#8b949e;line-height:1.8;">
简报每日自动生成 · 盘前 9:15 · 收盘 16:00<br>
周末提供市场资讯简报 · 周日 12:00 周复盘<br>
数据仅供参考，不构成投资建议
</p>
</div>

<p class="footer">🌀 小十三 · 每日自动更新 · <a href="https://daily-report-3ai.pages.dev" style="color:#8b949e;">访问主页</a> · <a href="https://github.com/terryplayer/daily-report" style="color:#8b949e;">GitHub</a></p>
</div>
</body>
</html>
INDEXFOOT

DAY_COUNT=$(echo "$SORTED_DAYS" | wc -l | tr -d " ")
echo "✅ 首页索引已生成（${DAY_COUNT} 天）"

# ---- 提交并推送到 GitHub（触发 Cloudflare Pages 自动部署） ----
git add -A
if git diff --cached --quiet; then
    echo "✅ 没有新文件需要推送"
else
    git commit -m "📊 同步报告 $(date '+%Y-%m-%d %H:%M')"
    git push github main
    echo "✅ 推送 GitHub 完成 → Cloudflare Pages 自动部署中"
fi

# ---- 保底：用 wrangler 直接部署（确保 Cloudflare 更新） ----
export CLOUDFLARE_API_TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.wrangler/config.json'))[0]['api_token'])" 2>/dev/null)
if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
  npx --yes wrangler pages deploy . --project-name=daily-report --branch=main 2>&1 | tail -3
fi

echo "🌐 https://daily-report-3ai.pages.dev"
