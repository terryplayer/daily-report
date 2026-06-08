#!/usr/bin/env python3
"""
生成 A股周复盘 HTML → 发送飞书
"""

import json, os, sys, subprocess
from datetime import datetime, timedelta

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(WORKSPACE, "daily-report-html", "weekly-review-template.html")
OUTPUT = os.path.join(WORKSPACE, "daily-report-html", "weekly-review-latest.html")

# 读取分析结果
with open("/tmp/stock_analysis_full.json") as f:
    data = json.load(f)

rs_ranking = data.get("rs_ranking", [])
vol_alerts = data.get("volatility_alerts", [])
multi_scores = data.get("multi_factor_scores", {})
tech_signals = data.get("tech_signals", {})
stocks_scored = multi_scores.get("stocks", [])
sector_summary = multi_scores.get("sector_summary", {})

# 上周交易区间 (简化计算)
now = datetime.now()
# 找到最近一个周一的日期
days_since_monday = now.weekday()
monday = now - timedelta(days=days_since_monday)
# 调整到上上周日作为上周区间起始 - 实际上我们直接用5月18-22日
week_start = "2026.05.18 周一"
week_end = "2026.05.22 周五"
week_num = 21

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def tag_cls(val):
    if val > 0: return "up"
    if val < 0: return "down"
    return "flat"

def tag_arrow(val):
    if val > 0: return "🔴"
    if val < 0: return "🟢"
    return "⚪"

def rs_tag(rank):
    m = {"A+": "tag tag-aplus", "A": "tag tag-a", "B": "tag tag-b", "C": "tag tag-c", "D": "tag tag-d"}
    return m.get(rank, "tag tag-b")

def rating_tag(rating):
    m = {"A": "tag tag-red", "B": "tag tag-blue", "C": "tag tag-yellow", "D": "tag tag-green"}
    return m.get(rating, "tag tag-blue")

def sector_color(sector):
    colors = {
        "科技/半导体": "#bf77f6",
        "通信/电子": "#58a6ff",
        "AI/数字经济": "#f08776",
        "化工/材料": "#d9a52e",
        "能源/公用事业": "#3fb950",
        "其他": "#8b949e"
    }
    return colors.get(sector, "#8b949e")

# ============ 构建HTML ============

h = []
h.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 A股周复盘 | 2026年第%d周</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #0d1117; color: #e6edf3; padding: 20px; line-height: 1.6; }
.container { max-width: 920px; margin: 0 auto; }
.header { border-bottom: 2px solid #bf77f6; padding-bottom: 16px; margin-bottom: 24px; }
.header h1 { font-size: 24px; color: #bf77f6; }
.header .subtitle { color: #8b949e; font-size: 13px; margin-top: 4px; }
.header .meta { color: #8b949e; font-size: 12px; margin-top: 2px; }
.section { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 18px 22px; margin-bottom: 18px; }
.section h2 { font-size: 15px; color: #58a6ff; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid #21262d; }
.section h3 { font-size: 13px; margin: 12px 0 6px; color: #e6edf3; }
.sector-title { font-size: 13px; font-weight: 600; color: #bf77f6; margin: 16px 0 8px; padding: 4px 0; border-bottom: 1px solid #21262d; }
.sector-title:first-of-type { margin-top: 0; }
table { width: 100%%; border-collapse: collapse; font-size: 13px; margin-bottom: 6px; }
th, td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #21262d; }
th { color: #8b949e; font-weight: 500; font-size: 12px; background: #1c2333; }
.up { color: #f85149; }
.down { color: #3fb950; }
.flat { color: #d9a52e; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 4px; }
.tag-red { background: rgba(248,81,73,0.15); color: #f85149; }
.tag-green { background: rgba(63,185,80,0.15); color: #3fb950; }
.tag-yellow { background: rgba(210,153,34,0.15); color: #d9a52e; }
.tag-blue { background: rgba(88,166,255,0.15); color: #58a6ff; }
.tag-purple { background: rgba(191,119,246,0.15); color: #bf77f6; }
.tag-aplus { background: rgba(191,119,246,0.2); color: #d2a8ff; }
.tag-a { background: rgba(88,166,255,0.2); color: #79c0ff; }
.tag-b { background: rgba(210,153,34,0.2); color: #d9a52e; }
.tag-c { background: rgba(248,81,73,0.15); color: #f85149; }
.tag-d { background: rgba(248,81,73,0.3); color: #ff7b72; }
.footer { text-align: center; color: #8b949e; font-size: 12px; padding: 20px 0; border-top: 1px solid #21262d; margin-top: 24px; }
.event-item { padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 13px; }
.event-item:last-child { border-bottom: none; }
.event-item .date-tag { display: inline-block; background: #1c2333; color: #8b949e; font-size: 11px; padding: 1px 6px; border-radius: 3px; margin-right: 6px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.grid-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; }
.warning-box { background: rgba(248,81,73,0.08); border: 1px solid rgba(248,81,73,0.3); border-radius: 6px; padding: 12px 14px; margin: 10px 0; }
.info-box { background: rgba(88,166,255,0.08); border: 1px solid rgba(88,166,255,0.3); border-radius: 6px; padding: 12px 14px; margin: 10px 0; }
.success-box { background: rgba(63,185,80,0.08); border: 1px solid rgba(63,185,80,0.3); border-radius: 6px; padding: 12px 14px; margin: 10px 0; }
.index-week { width: 100%%; font-size: 13px; }
.index-week th { background: #1c2333; }
.stock-table { width: 100%%; border-collapse: collapse; font-size: 13px; }
.stock-table th { background: #1c2333; }
.footer { text-align: center; color: #8b949e; font-size: 12px; padding: 20px 0; border-top: 1px solid #21262d; margin-top: 24px; }
.score-box { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px 16px; margin-top: 10px; }
.score-row { display: flex; gap: 16px; margin: 6px 0; flex-wrap: wrap; }
.score-item { flex: 1; min-width: 120px; background: #161b22; border-radius: 6px; padding: 10px; text-align: center; border: 1px solid #21262d; }
.score-item .label { font-size: 11px; color: #8b949e; }
.score-item .value { font-size: 22px; margin: 4px 0; font-weight: 700; }
.score-item .desc { font-size: 11px; color: #8b949e; }
.rating-card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 10px 12px; margin: 6px 0; }
.rating-card .stock-name { font-size: 13px; font-weight: 600; }
.rating-card .stock-code { color: #8b949e; font-size: 11px; }
.rating-card .stock-reason { font-size: 11px; color: #8b949e; margin-top: 2px; }
@media (max-width: 600px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="container">

<div class="header">
<h1>📊 A股周复盘 | 2026年第%d周</h1>
<div class="subtitle">复盘区间：%s ～ %s</div>
<div class="meta">生成时间：%s | 数据基于最近5个交易日 | 持仓：26只</div>
</div>
''' % (week_num, week_num, week_start, week_end, now.strftime("%Y.%m.%d %H:%M")))

# ===== 板块一：大盘回顾 =====
h.append('''
<div class="section">
<h2>📈 本周大盘回顾</h2>

<div class="grid-4">
  <div class="score-item" style="border-color:#30363d;">
    <div class="label">上证指数</div>
    <div class="value" style="color:#e6edf3;">4,112.90</div>
    <div class="desc down">-0.45%%</div>
  </div>
  <div class="score-item" style="border-color:#30363d;">
    <div class="label">深证成指</div>
    <div class="value" style="color:#e6edf3;">15,597.30</div>
    <div class="desc up">+0.43%%</div>
  </div>
  <div class="score-item" style="border-color:#30363d;">
    <div class="label">创业板指</div>
    <div class="value" style="color:#e6edf3;">3,938.50</div>
    <div class="desc up">+0.60%%</div>
  </div>
  <div class="score-item" style="border-color:#30363d;">
    <div class="label">科创50</div>
    <div class="value" style="color:#e6edf3;">1,790.77</div>
    <div class="desc up">+0.89%%</div>
  </div>
</div>

<div class="info-box">
<strong>📌 本周小结：</strong> A股整体震荡分化，上证-0.45%%偏弱，深证/创业板微涨，科创50+0.89%%表现最强。周中经历先跌后反弹，科技成长方向周五强势回归。<br>
<strong>📆 下周关注：</strong> 5月25日周一开盘预判——科技线延续修复，但需关注量能配合。持仓中26只标的，半导体/消费电子方向RS评级持续领先。
</div>
</div>
''')

# ===== 板块二：RS相对强度排名 =====
h.append('<div class="section"><h2>🏆 RS相对强度排名</h2>')
if rs_ranking:
    top_n = min(5, len(rs_ranking))
    bottom_n = min(5, len(rs_ranking))
    
    h.append('<div class="success-box"><strong>🏆 TOP%d（最强）</strong></div>' % top_n)
    h.append('<table class="stock-table"><tr><th>#</th><th>标的</th><th>RS值</th><th>同期涨幅</th><th>评级</th><th>信号</th></tr>')
    for i, r in enumerate(rs_ranking[:top_n], 1):
        h.append('<tr><td>%d</td><td>%s <span style="color:#8b949e;font-size:11px;">%s</span></td><td class="up">%+.1f</td><td class="up">%+.2f%%</td><td><span class="%s">%s</span></td><td>%s</td></tr>' % (
            i, esc(r["name"]), r["code"], r["rs_value"], r["stock_change_pct"],
            rs_tag(r["rank"]), r["rank"], esc(r["signal"])))
    h.append('</table>')
    
    h.append('<div class="warning-box" style="margin-top:10px;"><strong>🚫 BOTTOM%d（最弱）</strong></div>' % bottom_n)
    h.append('<table class="stock-table"><tr><th>#</th><th>标的</th><th>RS值</th><th>同期涨幅</th><th>评级</th><th>信号</th></tr>')
    for i, r in enumerate(rs_ranking[-bottom_n:], 1):
        h.append('<tr><td>%d</td><td>%s <span style="color:#8b949e;font-size:11px;">%s</span></td><td class="down">%+.1f</td><td class="down">%+.2f%%</td><td><span class="%s">%s</span></td><td>%s</td></tr>' % (
            i, esc(r["name"]), r["code"], r["rs_value"], r["stock_change_pct"],
            rs_tag(r["rank"]), r["rank"], esc(r["signal"])))
    h.append('</table>')
    
    bench = rs_ranking[0].get("bench_change_pct")
    h.append('<div style="font-size:12px;color:#8b949e;margin-top:8px;">📊 基准: 上证指数 期间涨幅: %+.2f%%</div>' % bench)
h.append('</div>')

# ===== 板块三：多因子评分 =====
h.append('<div class="section"><h2>⭐ 多因子评分（动量25%%+趋势20%%+波动15%%+资金20%%+估值20%%）</h2>')

# 行业评分汇总
h.append('<h3>📋 行业评分汇总</h3>')
h.append('<div class="grid-4" style="margin-bottom:12px;">')
for sec, info in sorted(sector_summary.items(), key=lambda x: x[1].get("avg_score", 0), reverse=True):
    sc = info.get("avg_score", 0)
    clr = sector_color(sec)
    h.append('<div class="score-item" style="border-color:%s;"><div class="label">%s</div><div class="value" style="color:%s;">%.1f</div><div class="desc">%d只 | 最优%s</div></div>' % (
        clr, esc(sec), clr, sc, info.get("count", 0), info.get("top_rating", "-")))
h.append('</div>')

# TOP5个股
top5 = [s for s in stocks_scored[:5] if s.get("total_score")]
h.append('<h3>✅ TOP5 推荐关注</h3>')
for s in top5:
    rating = s.get("rating", "C")
    clr = {"A": "#f85149", "B": "#58a6ff", "C": "#d9a52e", "D": "#3fb950"}.get(rating, "#8b949e")
    h.append('''<div class="rating-card">
      <div><span class="stock-name">%s</span> <span class="stock-code">%s</span> <span class="%s">%s %s</span></div>
      <div class="stock-reason">⭐总分%.1f | 动量%s | 趋势%s | 波动%s | 资金%s | 估值%s</div>
    </div>''' % (
        esc(s["name"]), s["code"], rating_tag(rating), s["rating"], s.get("rating_label", ""),
        s["total_score"],
        s.get("factors", {}).get("momentum", {}).get("note", "-"),
        s.get("factors", {}).get("trend", {}).get("note", "-"),
        s.get("factors", {}).get("volatility", {}).get("note", "-"),
        s.get("factors", {}).get("capital", {}).get("note", "-"),
        s.get("factors", {}).get("valuation", {}).get("note", "-"),
    ))

# BOTTOM5
bot5 = [s for s in stocks_scored[-5:] if s.get("total_score")]
h.append('<h3>⚠️ BOTTOM5 需关注风险</h3>')
for s in bot5:
    rating = s.get("rating", "C")
    h.append('''<div class="rating-card">
      <div><span class="stock-name">%s</span> <span class="stock-code">%s</span> <span class="%s">%s %s</span></div>
      <div class="stock-reason">⭐总分%.1f | 动量%s | 趋势%s | 波动%s</div>
    </div>''' % (
        esc(s["name"]), s["code"], rating_tag(rating), s["rating"], s.get("rating_label", ""),
        s["total_score"],
        s.get("factors", {}).get("momentum", {}).get("note", "-"),
        s.get("factors", {}).get("trend", {}).get("note", "-"),
        s.get("factors", {}).get("volatility", {}).get("note", "-"),
    ))

h.append('</div>')

# ===== 板块四：波动率预警 =====
h.append('<div class="section"><h2>📊 波动率异常预警</h2>')
if vol_alerts:
    h.append('<table class="stock-table"><tr><th>标的</th><th>今日涨跌</th><th>正常波动</th><th>偏离倍数</th><th>等级</th><th>建议</th></tr>')
    for v in vol_alerts[:8]:
        lvl_cls = "tag-red" if "高危" in v.get("level", "") else "tag-yellow"
        h.append('<tr><td>%s <span style="color:#8b949e;font-size:11px;">%s</span></td><td class="%s">%+.2f%%</td><td>%+.2f%%±%.2f</td><td>%.1fσ</td><td><span class="%s">%s</span></td><td>%s</td></tr>' % (
            esc(v["name"]), v["code"], tag_cls(v["today_change"]), v["today_change"],
            v["mean_change"], v["stddev"], v["deviation_ratio"],
            lvl_cls, v["level"].split(" ")[-1] if " " in v["level"] else v["level"],
            esc(v.get("suggestion", ""))))
    h.append('</table>')
else:
    h.append('<div class="success-box">✅ 今日无波动异常，所有持仓均在正常波动范围内</div>')
h.append('</div>')

# ===== 板块五：行业轮动 =====
h.append('''
<div class="section">
<h2>🔄 行业轮动建议（美林时钟改良版）</h2>
<div class="info-box">
<strong>📈 当前判断：复苏期</strong><br>
经济增长上行，通胀温和，流动性宽松。<br>
<strong>配置建议：</strong> 科技/半导体(AI+)超配 | 通信/电子标配 | 化工/材料标配 | 能源/公用事业低配<br>
<strong>战术要点：</strong> 成长风格优于价值，科技板块中期看好
</div>
</div>
''')

# ===== 板块六：全持仓股票列表 =====
h.append('''<div class="section">
<h2>📋 全持仓概览（26只）</h2>
<table class="stock-table">
<tr><th>标的</th><th>代码</th><th>RS评级</th><th>多因子评分</th><th>状态</th></tr>
''')

sectors_order = ["科技/半导体", "通信/电子", "AI/数字经济", "化工/材料", "能源/公用事业", "其他"]
# Build a map of code->rs_info
rs_map = {r["code"]: r for r in rs_ranking}
score_map = {s["code"]: s for s in stocks_scored}

for sec in sectors_order:
    sec_stocks = [s for s in stocks_scored if s.get("sector") == sec] if stocks_scored else []
    if not sec_stocks:
        continue
    clr = sector_color(sec)
    h.append('<tr style="background:#1c2333;"><td colspan="5" style="color:%s;font-weight:600;font-size:12px;">%s</td></tr>' % (clr, sec))
    for s in sec_stocks:
        code = s["code"]
        rs_info = rs_map.get(code, {})
        rs_rank = rs_info.get("rank", "-")
        total = s.get("total_score", 0)
        rating = s.get("rating", "C")
        h.append('<tr><td>%s</td><td style="color:#8b949e;">%s</td><td><span class="%s">%s</span></td><td><span class="%s">%.1f [%s]</span></td><td>%s</td></tr>' % (
            esc(s["name"]), code,
            rs_tag(rs_rank), rs_rank,
            rating_tag(rating), total, rating,
            esc(s.get("rating_label", ""))))

h.append('</table></div>')

# 底部
h.append('''
<div class="footer">
📊 A股周复盘 · 自动生成 · 数据来源：东方财富/新浪财经<br>
⚙️ 投资有风险，操作需谨慎 · 仅供个人持仓参考
</div>
</div>
</body>
</html>
''')

html = "\n".join(h)
with open(OUTPUT, "w") as f:
    f.write(html)

print(f"✅ 周报已生成: {OUTPUT}")
print(f"   大小: {len(html)} bytes")
