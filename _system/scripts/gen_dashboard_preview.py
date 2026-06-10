#!/usr/bin/env python3
"""生成8种配色方案的dashboard预览"""
import os, json, re
from datetime import datetime, timedelta

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(WORKSPACE, "daily-report-html")

# ─── 扫描报告文件 ─────────────────────────────
files = [f for f in os.listdir(REPORT_DIR) if f.endswith('.html') and f not in ('index.html', 'dashboard.html')]
reports = []
for fn in files:
    path = os.path.join(REPORT_DIR, fn)
    mtime = os.path.getmtime(path)
    size = os.path.getsize(path)
    fn_lower = fn.lower()
    rtype = 'other'; label = '其他'; icon = '📄'
    if 'premarket' in fn_lower: rtype = 'premarket'; label = '盘前简报'; icon = '📋'
    elif 'midday' in fn_lower: rtype = 'midday'; label = '午间监测'; icon = '🌤'
    elif 'daily-combined' in fn_lower or 'closing' in fn_lower or 'report-close' in fn_lower:
        rtype = 'closing'; label = '收盘简报'; icon = '📊'
    elif 'weekly' in fn_lower: rtype = 'weekly'; label = '周复盘'; icon = '📈'
    is_advanced = 'advanced' in fn_lower
    version = 'advanced' if is_advanced else 'standard'
    date_match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', fn)
    date_str = ''; date_sort = ''
    if date_match:
        y, m, d = date_match.group(1), date_match.group(2), date_match.group(3)
        date_str = f'{y}-{m}-{d}'; date_sort = f'{y}{m}{d}'
    reports.append({'file': fn, 'type': rtype, 'label': label, 'icon': icon,
                    'version': version, 'date': date_str, 'date_sort': date_sort,
                    'size': size, 'mtime': mtime})
reports.sort(key=lambda r: (r['date_sort'], r['type'], r['version']), reverse=True)
dates_group = {}
for r in reports:
    if not r['date']: continue
    dates_group.setdefault(r['date'], []).append(r)
sorted_dates = sorted(dates_group.keys(), reverse=True)
total = len(reports)
type_count = {}
for r in reports: type_count[r['label']] = type_count.get(r['label'], 0) + 1
latest_date = sorted_dates[0] if sorted_dates else ''
if sorted_dates:
    dt_min = datetime.strptime(sorted_dates[-1], '%Y-%m-%d').date()
    dt_max = datetime.strptime(sorted_dates[0], '%Y-%m-%d').date()
    d = dt_max; date_range = []
    while d >= dt_min:
        date_range.append(d.strftime('%Y-%m-%d')); d -= timedelta(days=1)
else: date_range = sorted_dates

# ─── 8种配色方案 ─────────────────────────
SCHEMES = {
    'A-光谱七色': [
        'linear-gradient(135deg,#4a1a1a,#0d1b2a)',  # 周一 暗红
        'linear-gradient(135deg,#4a3a1a,#0d1b2a)',  # 周二 暗橙
        'linear-gradient(135deg,#3d3d1a,#0d1b2a)',  # 周三 暗黄
        'linear-gradient(135deg,#1a3d2e,#0d1b2a)',  # 周四 暗绿
        'linear-gradient(135deg,#1a3d3d,#0d1b2a)',  # 周五 暗青
        'linear-gradient(135deg,#1a2a4a,#0d1b2a)',  # 周六 暗蓝
        'linear-gradient(135deg,#2d1a3d,#0d1b2a)',  # 周日 暗紫
    ],
    'B-极光科技': [
        'linear-gradient(135deg,#1a2a5c,#0d1b2a)',  # 周一 极光蓝
        'linear-gradient(135deg,#1a4a3a,#0d1b2a)',  # 周二 极光绿
        'linear-gradient(135deg,#3a1a4a,#0d1b2a)',  # 周三 极光紫
        'linear-gradient(135deg,#4a1a3a,#0d1b2a)',  # 周四 极光粉
        'linear-gradient(135deg,#4a3a1a,#0d1b2a)',  # 周五 极光橙
        'linear-gradient(135deg,#1a4a4a,#0d1b2a)',  # 周六 极光青
        'linear-gradient(135deg,#2a2a3a,#0d1b2a)',  # 周日 极光灰
    ],
    'C-柔和治愈': [
        'linear-gradient(135deg,#2a3a5a,#0d1b2a)',  # 周一 雾霾蓝
        'linear-gradient(135deg,#2a4a3a,#0d1b2a)',  # 周二 薄荷绿
        'linear-gradient(135deg,#4a4a2a,#0d1b2a)',  # 周三 奶油黄
        'linear-gradient(135deg,#3a2a4a,#0d1b2a)',  # 周四 薰衣紫
        'linear-gradient(135deg,#4a2a3a,#0d1b2a)',  # 周五 珊瑚粉
        'linear-gradient(135deg,#1a3a5a,#0d1b2a)',  # 周六 天空蓝
        'linear-gradient(135deg,#3a3a4a,#0d1b2a)',  # 周日 浅灰紫
    ],
    'D-五色周末灰': [
        'linear-gradient(135deg,#1a3a5c,#0d1b2a)',  # 周一 蓝
        'linear-gradient(135deg,#1a4a3a,#0d1b2a)',  # 周二 绿
        'linear-gradient(135deg,#3a3a1a,#0d1b2a)',  # 周三 黄
        'linear-gradient(135deg,#3a1a3a,#0d1b2a)',  # 周四 紫
        'linear-gradient(135deg,#4a1a1a,#0d1b2a)',  # 周五 红
        'linear-gradient(135deg,#2a2a2a,#0d1b2a)',  # 周六 灰
        'linear-gradient(135deg,#2a2a3a,#0d1b2a)',  # 周日 灰紫
    ],
    'E-赛博霓虹': [
        'linear-gradient(135deg,#2a0a2a,#0a0a14)',  # 周一 霓虹品红
        'linear-gradient(135deg,#0a1a3a,#0a0a14)',  # 周二 霓虹蓝
        'linear-gradient(135deg,#1a0a3a,#0a0a14)',  # 周三 霓虹紫
        'linear-gradient(135deg,#0a2a2a,#0a0a14)',  # 周四 霓虹青
        'linear-gradient(135deg,#0a2a1a,#0a0a14)',  # 周五 霓虹绿
        'linear-gradient(135deg,#2a1a0a,#0a0a14)',  # 周六 霓虹橙
        'linear-gradient(135deg,#1a1a2a,#0a0a14)',  # 周日 暗夜灰
    ],
    'F-森林大地': [
        'linear-gradient(135deg,#1a3a2a,#0d1b14)',  # 周一 森林绿
        'linear-gradient(135deg,#3a2a1a,#0d1b14)',  # 周二 大地褐
        'linear-gradient(135deg,#2a3a1a,#0d1b14)',  # 周三 苔藓绿
        'linear-gradient(135deg,#3a2a0a,#0d1b14)',  # 周四 秋叶橙
        'linear-gradient(135deg,#3a1a1a,#0d1b14)',  # 周五 浆果红
        'linear-gradient(135deg,#1a2a3a,#0d1b14)',  # 周六 溪水蓝
        'linear-gradient(135deg,#2a2a2a,#0d1b14)',  # 周日 岩石灰
    ],
    'G-莫兰迪灰': [
        'linear-gradient(135deg,#1a1a2e,#151515)',  # 周一 雾灰蓝
        'linear-gradient(135deg,#1a2a1a,#151515)',  # 周二 豆沙绿
        'linear-gradient(135deg,#2e1a1a,#151515)',  # 周三 干枯粉
        'linear-gradient(135deg,#2a1a2e,#151515)',  # 周四 薰衣灰紫
        'linear-gradient(135deg,#2e2a1a,#151515)',  # 周五 燕麦黄
        'linear-gradient(135deg,#1a2e2e,#151515)',  # 周六 鼠尾草青
        'linear-gradient(135deg,#2e2e2e,#151515)',  # 周日 暖灰
    ],
    'H-极简黑白': [
        'linear-gradient(135deg,#2a2a2a,#111111)',  # 周一 浅灰
        'linear-gradient(135deg,#333333,#111111)',  # 周二 中灰
        'linear-gradient(135deg,#3a3a3a,#111111)',  # 周三 深灰
        'linear-gradient(135deg,#303030,#111111)',  # 周四 中深灰
        'linear-gradient(135deg,#282828,#111111)',  # 周五 中浅灰
        'linear-gradient(135deg,#1e1e1e,#111111)',  # 周六 深炭灰
        'linear-gradient(135deg,#222233,#111111)',  # 周日 灰黑
    ],
}

# ─── 公用工具 ─────────────────────────
def fmt_size(sz):
    if sz < 1024: return f'{sz}B'
    if sz < 1024*1024: return f'{sz/1024:.0f}KB'
    return f'{sz/1024/1024:.1f}MB'

def type_color(t):
    return {'premarket': '#58a6ff', 'midday': '#56d4dd', 'closing': '#f85149', 'weekly': '#f778ba'}.get(t, '#8b949e')

CSS = '''
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0d1117;color:#e6edf3;padding:24px;line-height:1.6}
.container{max-width:960px;margin:0 auto}
h1{font-size:20px;color:#e6edf3;border-bottom:2px solid #30363d;padding-bottom:12px;margin-bottom:8px;display:flex;align-items:center;gap:8px}
h1 span{font-size:12px;color:#8b949e;font-weight:400}
.stats{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.stat-card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 16px;flex:1;min-width:100px;text-align:center}
.stat-val{font-size:18px;font-weight:700;color:#e6edf3}
.stat-label{font-size:11px;color:#8b949e;margin-top:2px}
.stat-val.p{color:#58a6ff}.stat-val.m{color:#56d4dd}.stat-val.c{color:#f85149}.stat-val.w{color:#f778ba}
.date-group{margin-bottom:20px}
.date-header{font-size:13px;color:#e6edf3;font-weight:700;padding:8px 12px;background:#1c2333;border-radius:6px 6px 0 0;border:1px solid #30363d;border-bottom:none;display:flex;justify-content:space-between;align-items:center}
.date-header .day{font-size:12px;color:#8b949e;font-weight:400}
.report-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;border:1px solid #30363d;border-top:none;border-radius:0 0 8px 8px;padding:8px;background:#161b22}
.report-card{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:10px 12px;display:flex;align-items:center;gap:10px;text-decoration:none;color:#e6edf3;transition:all 0.15s}
.report-card:hover{border-color:#58a6ff;transform:translateY(-1px);box-shadow:0 2px 8px rgba(0,0,0,0.3)}
.report-icon{font-size:20px;width:28px;text-align:center}
.report-info{flex:1;min-width:0}
.report-name{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.report-meta{font-size:11px;color:#8b949e;margin-top:1px}
.report-badge{font-size:10px;padding:1px 6px;border-radius:3px;font-weight:600}
.badge-advanced{background:rgba(247,120,186,0.2);color:#f778ba}
.badge-standard{background:rgba(63,185,80,0.2);color:#3fb950}
.filter-bar{margin-bottom:12px;display:flex;gap:6px;flex-wrap:wrap}
.filter-btn{padding:4px 12px;border-radius:12px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid #30363d;background:#0d1117;color:#8b949e}
.filter-btn:hover{border-color:#58a6ff;color:#e6edf3}
.filter-btn.active{background:#58a6ff;color:#fff;border-color:#58a6ff}
.footer{text-align:center;color:#8b949e;font-size:11px;margin-top:24px;padding-top:12px;border-top:1px solid #21262d}
'''

def generate_html(gradients, name):
    html = '<!DOCTYPE html><html lang="zh-CN"><head>\n'
    html += '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
    html += f'<title>📋 {name} · 配色预览</title>\n'
    html += f'<style>{CSS}</style>\n</head>\n<body><div class="container">\n'
    html += f'<h1>📋 股票报告中心 <span>{name} · 配色预览</span></h1>\n'
    
    # 色标卡
    day_names = ['周一','周二','周三','周四','周五','周六','周日']
    html += '<div style="display:flex;gap:4px;margin-bottom:16px">\n'
    for dn, grad in zip(day_names, gradients):
        html += f'<div style="flex:1;background:{grad};border-radius:6px;padding:8px 4px;text-align:center;font-size:11px;font-weight:600">{dn}</div>\n'
    html += '</div>\n'
    
    # 统计卡片
    sg = {'total':'linear-gradient(135deg,#1a1f2e,#161b22)','premarket':'linear-gradient(135deg,#1a2333,#161b22)',
          'midday':'linear-gradient(135deg,#1a2d2d,#161b22)','closing':'linear-gradient(135deg,#2d1c1c,#161b22)',
          'weekly':'linear-gradient(135deg,#2d1c2d,#161b22)'}
    html += '<div class="stats">\n'
    html += f'<div class="stat-card" style="background:{sg["total"]}"><div class="stat-val">{total}</div><div class="stat-label">报告总数</div></div>\n'
    for t, k in [('premarket','盘前简报'),('midday','午间监测'),('closing','收盘简报'),('weekly','周复盘')]:
        html += f'<div class="stat-card" style="background:{sg[t]}"><div class="stat-val {t[0]}">{type_count.get(k,0)}</div><div class="stat-label">{k}</div></div>\n'
    html += '</div>\n'
    
    # 过滤器
    html += '<div class="filter-bar">\n<button class="filter-btn active" data-filter="all">全部</button>\n'
    for t, l in [('premarket','盘前'),('midday','午间'),('closing','收盘'),('weekly','周复盘')]:
        html += f'<button class="filter-btn" data-filter="{t}">{l}</button>\n'
    html += '<button class="filter-btn" data-filter="advanced">进阶版</button>\n<button class="filter-btn" data-filter="standard">标准版</button>\n</div>\n'
    
    def ch(r):
        bc = type_color(r['type'])
        bcls = 'badge-advanced' if r['version']=='advanced' else 'badge-standard'
        bt = '进阶' if r['version']=='advanced' else '标准'
        nt = ' <span style="font-size:10px;color:#f85149;font-weight:700">●NEW</span>' if r['date']==latest_date and r['version']=='advanced' else ''
        return (f'<a href="{r["file"]}" class="report-card" data-type="{r["type"]}" data-version="{r["version"]}" style="border-left:3px solid {bc}">\n'
                f'<div class="report-icon">{r["icon"]}</div>\n<div class="report-info">\n'
                f'<div class="report-name">{r["label"]}{nt}</div>\n'
                f'<div class="report-meta"><span class="report-badge {bcls}">{bt}</span> · {fmt_size(r["size"])}</div>\n</div></a>\n')
    def ec(adv=False):
        if adv:
            return '<div class="report-card report-card-empty" style="cursor:default;background:#0d1117">\n<div class="report-icon" style="color:#ffcc00">⏳</div>\n<div class="report-info"><div class="report-name" style="color:#ffcc00;font-size:11px">待更新</div></div></div>\n'
        else:
            return '<div class="report-card report-card-empty" style="cursor:default;background:#0d1117">\n<div class="report-icon" style="color:#8b949e">—</div>\n<div class="report-info"><div class="report-name" style="color:#8b949e;font-size:11px">无报告</div></div></div>\n'
    
    tl = ['premarket','midday','closing','weekly']
    for dt in date_range:
        dr = dates_group.get(dt, [])
        try:
            wd = datetime.strptime(dt,'%Y-%m-%d').weekday()
            wcn = ['周一','周二','周三','周四','周五','周六','周日'][wd]
        except: wd=0; wcn=''
        cbt = {}
        for r in dr: cbt[r['type']] = cbt.get(r['type'],0)+1
        ts = ' · '.join([f'{i}{l}:{cbt.get(t,0)}' for t,l,i in [('premarket','盘前','📋'),('midday','午间','🌤'),('closing','收盘','📊'),('weekly','周复','📈')]])
        html += f'<div class="date-group">\n<div class="date-header" style="background:{gradients[wd]}">{dt} <span class="day">{wcn}</span><span style="font-size:11px;color:#8b949e">{ts}</span></div>\n<div class="report-grid">\n'
        rl = {}
        for r in dr: rl[(r['type'],r['version'])] = r
        for typ in tl:
            k = (typ,'standard')
            html += ch(rl[k]) if k in rl else ec(False)
        for typ in tl:
            k = (typ,'advanced'); sk = (typ,'standard')
            html += ch(rl[k]) if k in rl else ec(sk in rl)
        html += '</div>\n</div>\n'
    html += '<div class="footer">🌀 混动系统 · 配色预览</div>\n</div></body></html>'
    return html

TEMP_DIR = os.path.join(REPORT_DIR, 'temp_reports')
for name, grads in SCHEMES.items():
    path = os.path.join(TEMP_DIR, f'dashboard_{name[0]}.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(generate_html(grads, name))
    print(f'✅ {name} → {path}')
