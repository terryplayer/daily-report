#!/usr/bin/env python3
"""Generate index.html: shell + dynamic report links + footer.
Shell and footer are locked copies of the confirmed template."""
import os, re
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(WORKSPACE, "daily-report-html")
SHELL = os.path.join(WORKSPACE, "scripts", "index-shell.html")
FOOTER = os.path.join(WORKSPACE, "scripts", "index-footer.html")

DOW_CN = {"Monday":"周一","Tuesday":"周二","Wednesday":"周三","Thursday":"周四","Friday":"周五","Saturday":"周六","Sunday":"周日"}
DOW_CLS = {0:"day-mon",1:"day-tue",2:"day-wed",3:"day-thu",4:"day-fri"}

def get_week_number(d):
    return d.isocalendar()[1]

def gen_cards(reports):
    """Generate the two card divs (weekly review + daily reports)."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    sorted_dates = sorted(reports.keys(), reverse=True)
    L = []
    ap = L.append

    # ═══ 每周简报卡片 ═══
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

    # ═══ 每日简报卡片 ═══
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
                    ap(f'    <a href="{r["premarket"]}.html" class="pm">📋 盘前简报</a>')
                if 'midday' in r:
                    ap(f'    <a href="{r["midday"]}.html" class="mid">🌤 午间监测</a>')
                if 'daily-combined' in r:
                    ap(f'    <a href="{r["daily-combined"]}.html" class="dc">📊 收盘汇总</a>')
                if 'weekend' in r:
                    ap(f'    <a href="{r["weekend"]}.html" class="we">🌙 周末简报</a>')
                if 'market_overview' in r:
                    ap(f'    <a href="{r["market_overview"]}" class="mo">🌐 市场全景</a>')

                ap(f'  </div></div>')

        ap('</div>')

    return "\n".join(L)

def main():
    for f in [SHELL, FOOTER]:
        if not os.path.exists(f):
            print(f"❌ 缺少模板文件: {f}")
            return 1

    # Read all report files
    reports = {}
    for f in os.listdir(HTML_DIR):
        m = re.match(r'(premarket|midday|daily-combined|weekend|weekly-review)-(\d{4}-\d{2}-\d{2})\.html', f)
        if m:
            reports.setdefault(m.group(2), {})[m.group(1)] = f.replace('.html', '')
    # 市场全景（selestock 子目录）
    sel_dir = os.path.join(HTML_DIR, 'selestock')
    if os.path.exists(sel_dir):
        for f in os.listdir(sel_dir):
            m = re.match(r'(\d{4}-\d{2}-\d{2})\.html', f)
            if m:
                reports.setdefault(m.group(1), {})['market_overview'] = f'selestock/{m.group(1)}.html'

    if not reports:
        print("❌ 没有找到任何报告文件")
        return 1

    with open(SHELL) as f:
        shell = f.read()
    with open(FOOTER) as f:
        footer = f.read()

    cards = gen_cards(reports)
    idx_path = os.path.join(HTML_DIR, "index.html")

    with open(idx_path, "w") as f:
        f.write(shell + cards + footer)

    print(f"✅ index.html 已生成（{len(reports)} 天, 外壳固定）")
    return 0

if __name__ == "__main__":
    exit(main())
