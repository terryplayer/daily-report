#!/usr/bin/env python3
"""Generate index.html matching confirmed template structure (fb9685e)."""
import os, re
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(WORKSPACE, "daily-report-html")
TEMPLATE = os.path.join(WORKSPACE, "scripts", "index-template.html")

DOW_CN = {"Monday":"周一","Tuesday":"周二","Wednesday":"周三","Thursday":"周四","Friday":"周五","Saturday":"周六","Sunday":"周日"}
DOW_CLS = {0:"day-mon",1:"day-tue",2:"day-wed",3:"day-thu",4:"day-fri"}

def get_week_number(d):
    return d.isocalendar()[1]

def main():
    # Read all report files
    reports = {}
    for f in os.listdir(HTML_DIR):
        m = re.match(r'(premarket|midday|daily-combined|weekend|weekly-review)-(\d{4}-\d{2}-\d{2})\.html', f)
        if m:
            reports.setdefault(m.group(2), {})[m.group(1)] = f.replace('.html', '')

    if not reports:
        print("❌ 没有找到任何报告文件")
        return 1

    # Read template CSS
    with open(TEMPLATE) as f:
        tmpl = f.read()
    css_m = re.search(r'<style>(.*?)</style>', tmpl, re.DOTALL)
    css = css_m.group(1).strip() if css_m else ""

    today_str = datetime.now().strftime("%Y-%m-%d")
    sorted_dates = sorted(reports.keys(), reverse=True)

    L = []
    ap = L.append

    ap('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">')
    ap(f'<title>🌀 小十三 · 股市简报</title><style>{css}</style></head><body><div class="container">')
    ap('<h1>🌀 小十三 · 股市简报</h1>')
    ap('<p class="subtitle">A股 · 盘前 | 午间 | 收盘日报 · 每周复盘</p>')

    # ═══ 每周简报 ═══
    wk_reviews = {d:r for d,r in reports.items() if 'weekly-review' in r}
    if wk_reviews:
        ap('<div class="card"><h2 class="card-hdr-weekly">🐱 每周简报</h2>')
        for i, d in enumerate(sorted(wk_reviews, reverse=True)):
            wc = f" weekly-w{i+1}" if i < 2 else ""
            dt = datetime.strptime(d, "%Y-%m-%d")
            dw = DOW_CN.get(dt.strftime("%A"), "")
            ap(f'<div class="weekly-row{wc}">')
            ap(f'  <a href="{wk_reviews[d]["weekly-review"]}">')
            ap(f'    <span><span class="date-text">{d}</span> <span class="day-tag-sm">{dw}</span> 完整版</span>')
            ap(f'    <span class="version">完整版 →</span>')
            ap(f'  </a></div>')
        ap('</div>')

    # ═══ 每日简报 ═══
    daily_dates = [d for d in sorted_dates if any(t in reports[d] for t in ('premarket','midday','daily-combined','weekend'))]
    if daily_dates:
        ap('<div class="card"><h2 class="card-hdr-daily">🐶 每日简报 <span class="badge" style="background:#bf77f6;">按自然周</span></h2>')

        # Group by ISO week
        week_groups = {}
        for d_str in daily_dates:
            dt = datetime.strptime(d_str, "%Y-%m-%d")
            week_groups.setdefault(get_week_number(dt), []).append(d_str)

        wk_idx = 0
        for wk in sorted(week_groups, reverse=True):
            wk_idx += 1
            dates = week_groups[wk]
            # Week header
            first = datetime.strptime(dates[-1], "%Y-%m-%d")
            last = datetime.strptime(dates[0], "%Y-%m-%d")
            fs = f'{first.month:02d}.{first.day:02d}'
            ls = f'{last.month:02d}.{last.day:02d}'
            fd = DOW_CN.get(first.strftime("%A"), "")
            ld = DOW_CN.get(last.strftime("%A"), "")
            tag_html = '<span class="week-tag">本周</span>' if wk_idx == 1 else ""
            wc = f"week-hdr-w{min(wk_idx, 2)}"

            ap(f'<div class="week-header {wc}">Week {wk} · {fs} {fd} — {ls} {ld} {tag_html}</div>')

            for d_str in dates:
                dt = datetime.strptime(d_str, "%Y-%m-%d")
                dw_cn = DOW_CN.get(dt.strftime("%A"), "")
                cls = DOW_CLS.get(dt.weekday(), "")
                is_today = (d_str == today_str)
                today_tag = ' <span class="tag-tag" style="font-size:11px;background:#1f6feb22;color:#58a6ff;border:1px solid #1f6feb44;padding:1px 6px;border-radius:4px;">今日</span>' if is_today else ""

                ap(f'<div class="date-group {cls}">')
                ap(f'  <div class="date-label">{d_str} <span class="day-tag">{dw_cn}</span>{today_tag}</div>')
                ap(f'  <div class="report-links">')

                r = reports[d_str]
                if 'premarket' in r:
                    ap(f'    <a href="{r["premarket"]}" class="pm">📋 盘前简报</a>')
                if 'midday' in r:
                    ap(f'    <a href="{r["midday"]}" class="mid">🌤 午间监测</a>')
                if 'daily-combined' in r:
                    ap(f'    <a href="{r["daily-combined"]}" class="dc">📊 收盘汇总</a>')
                if 'weekend' in r:
                    ap(f'    <a href="{r["weekend"]}" class="we">🌙 周末简报</a>')

                ap(f'  </div></div>')

        ap('</div>')

    # ═══ 底部 ═══
    ap('<div class="card" style="background:#0d1117;border-color:#21262d;">')
    ap('<p style="font-size:13px;color:#8b949e;line-height:1.8;">')
    ap('简报交易日自动生成 · 盘前 9:15 · 午间 12:00 · 收盘 16:00<br>')
    ap('周日 12:00 周复盘 · 周末休市无报告<br>')
    ap('数据仅供参考，不构成投资建议')
    ap('</p></div>')
    ap('<p class="footer">🌀 小十三 · 每日自动更新 · <a href="https://daily-report-3ai.pages.dev" style="color:#8b949e;">访问主页</a> · <a href="https://github.com/terryplayer/daily-report" style="color:#8b949e;">GitHub</a></p>')
    ap('</div></body></html>')

    with open(os.path.join(HTML_DIR, "index.html"), "w") as f:
        f.write("\n".join(L))
    print(f"✅ index.html 已生成（{len(reports)} 天）")
    return 0

if __name__ == "__main__":
    exit(main())
