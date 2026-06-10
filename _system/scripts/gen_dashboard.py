#!/usr/bin/env python3
"""生成报告中心 Dashboard — 四网格最终模板风格"""
import os, json, re
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(WORKSPACE, "daily-report-html")
os.chdir(WORKSPACE)

# ─── 扫描报告文件 ─────────────────────────────
files = [f for f in os.listdir(REPORT_DIR) if f.endswith('.html') and f not in ('index.html', 'dashboard.html')]

reports = []
for fn in files:
    path = os.path.join(REPORT_DIR, fn)
    mtime = os.path.getmtime(path)
    size = os.path.getsize(path)
    
    # 识别报告类型
    fn_lower = fn.lower()
    rtype = 'other'
    label = '其他'
    icon = '📄'
    
    if 'premarket' in fn_lower:
        rtype = 'premarket'
        label = '盘前简报'
        icon = '📋'
    elif 'midday' in fn_lower:
        rtype = 'midday'
        label = '午间监测'
        icon = '🌤'
    elif 'daily-combined' in fn_lower or 'closing' in fn_lower or 'report-close' in fn_lower:
        rtype = 'closing'
        label = '收盘简报'
        icon = '📊'
    elif 'weekly' in fn_lower:
        rtype = 'weekly'
        label = '周复盘'
        icon = '📈'
    
    # 识别是否进阶版
    is_advanced = 'advanced' in fn_lower
    version = 'advanced' if is_advanced else 'standard'
    
    # 提取日期
    date_match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', fn)
    date_str = ''
    date_sort = ''
    if date_match:
        y, m, d = date_match.group(1), date_match.group(2), date_match.group(3)
        date_str = f'{y}-{m}-{d}'
        date_sort = f'{y}{m}{d}'
    
    reports.append({
        'file': fn,
        'type': rtype,
        'label': label,
        'icon': icon,
        'version': version,
        'date': date_str,
        'date_sort': date_sort,
        'size': size,
        'mtime': mtime,
    })

# 按日期降序、类型排序
reports.sort(key=lambda r: (r['date_sort'], r['type'], r['version']), reverse=True)

# 按日期分组
dates_group = {}
for r in reports:
    if not r['date']:
        continue
    dates_group.setdefault(r['date'], []).append(r)

# 按日期降序排列
sorted_dates = sorted(dates_group.keys(), reverse=True)

# 统计
total = len(reports)
type_count = {}
for r in reports:
    type_count[r['label']] = type_count.get(r['label'], 0) + 1

# 获取最近日期
latest_date = sorted_dates[0] if sorted_dates else ''

# ─── 工具函数 ─────────────────────────────────
def fmt_size(sz):
    if sz < 1024: return f'{sz}B'
    if sz < 1024*1024: return f'{sz/1024:.0f}KB'
    return f'{sz/1024/1024:.1f}MB'

def type_color(t):
    return {
        'premarket': '#58a6ff',
        'midday': '#56d4dd',
        'closing': '#f85149',
        'weekly': '#f778ba',
    }.get(t, '#8b949e')

# 日期头渐变背景（按类型占比生成主题色）
def date_header_gradient(dt, type_summary_str):
    # 赛博霓虹 · 按星期分配渐变色
    from datetime import datetime
    try:
        wd = datetime.strptime(dt, '%Y-%m-%d').weekday()
    except:
        wd = 0
    gradients = [
        'linear-gradient(135deg,#2a0a2a,#0a0a14)',  # 周一 霓虹品红
        'linear-gradient(135deg,#0a1a3a,#0a0a14)',  # 周二 霓虹蓝
        'linear-gradient(135deg,#1a0a3a,#0a0a14)',  # 周三 霓虹紫
        'linear-gradient(135deg,#0a2a2a,#0a0a14)',  # 周四 霓虹青
        'linear-gradient(135deg,#0a2a1a,#0a0a14)',  # 周五 霓虹绿
        'linear-gradient(135deg,#2a1a0a,#0a0a14)',  # 周六 霓虹橙
        'linear-gradient(135deg,#1a1a2a,#0a0a14)',  # 周日 暗夜灰
    ]
    return gradients[wd]

# ─── CSS 块（模板风格）─────────────────────────
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
.nav-bar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center}
.nav-btn{display:inline-block;padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;text-decoration:none;border:1px solid #30363d;color:#e6edf3;background:#161b22;transition:all 0.15s}
.nav-btn:hover{background:#1c2333;border-color:#58a6ff}
.nav-btn.active{background:#58a6ff;color:#fff;border-color:#58a6ff}
.footer{text-align:center;color:#8b949e;font-size:11px;margin-top:24px;padding-top:12px;border-top:1px solid #21262d}
.filter-bar{margin-bottom:12px;display:flex;gap:6px;flex-wrap:wrap}
.filter-btn{padding:4px 12px;border-radius:12px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid #30363d;background:#0d1117;color:#8b949e}
.filter-btn:hover{border-color:#58a6ff;color:#e6edf3}
.filter-btn.active{background:#58a6ff;color:#fff;border-color:#58a6ff}
'''

# ─── 生成HTML ─────────────────────────────────
html = '<!DOCTYPE html><html lang="zh-CN"><head>\n'
html += '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
html += '<title>📋 股票报告中心 · 混动系统</title>\n'
html += f'<style>{CSS}</style>\n'
html += '</head>\n<body><div class="container">\n'

html += '<h1>📋 股票报告中心 <span>混动系统 · 四象限</span></h1>\n'

# 统计卡片（渐变背景）
stat_gradients = {
    'total': 'linear-gradient(135deg,#1a1f2e,#161b22)',
    'premarket': 'linear-gradient(135deg,#1a2333,#161b22)',
    'midday': 'linear-gradient(135deg,#1a2d2d,#161b22)',
    'closing': 'linear-gradient(135deg,#2d1c1c,#161b22)',
    'weekly': 'linear-gradient(135deg,#2d1c2d,#161b22)',
}
html += '<div class="stats">\n'
html += f'<div class="stat-card" style="background:{stat_gradients["total"]}"><div class="stat-val">{total}</div><div class="stat-label">报告总数</div></div>\n'
html += f'<div class="stat-card" style="background:{stat_gradients["premarket"]}"><div class="stat-val p">{type_count.get("盘前简报", 0)}</div><div class="stat-label">盘前简报</div></div>\n'
html += f'<div class="stat-card" style="background:{stat_gradients["midday"]}"><div class="stat-val m">{type_count.get("午间监测", 0)}</div><div class="stat-label">午间监测</div></div>\n'
html += f'<div class="stat-card" style="background:{stat_gradients["closing"]}"><div class="stat-val c">{type_count.get("收盘简报", 0)}</div><div class="stat-label">收盘简报</div></div>\n'
html += f'<div class="stat-card" style="background:{stat_gradients["weekly"]}"><div class="stat-val w">{type_count.get("周复盘", 0)}</div><div class="stat-label">周复盘</div></div>\n'
html += '</div>\n'

# 过滤器
html += '<div class="filter-bar" id="filterBar">\n'
html += '<button class="filter-btn active" data-filter="all">全部</button>\n'
for t, label in [('premarket','盘前'),('midday','午间'),('closing','收盘'),('weekly','周复盘')]:
    html += f'<button class="filter-btn" data-filter="{t}">{label}</button>\n'
html += '<button class="filter-btn" data-filter="advanced">进阶版</button>\n'
html += '<button class="filter-btn" data-filter="standard">标准版</button>\n'
html += '</div>\n'

# 卡片生成函数
def _card_html(r):
    bc = type_color(r['type'])
    badge_cls = 'badge-advanced' if r['version'] == 'advanced' else 'badge-standard'
    badge_text = '进阶' if r['version'] == 'advanced' else '标准'
    # 最新日期的进阶版标记NEW
    is_t = (r['date'] == latest_date and r['version'] == 'advanced')
    tg = ' <span style="font-size:10px;color:#f85149;font-weight:700">●NEW</span>' if is_t else ''
    return (f'<a href="{r["file"]}" class="report-card" data-type="{r["type"]}" data-version="{r["version"]}" style="border-left:3px solid {bc}">\n'
            f'<div class="report-icon">{r["icon"]}</div>\n'
            f'<div class="report-info">\n'
            f'<div class="report-name">{r["label"]}{tg}</div>\n'
            f'<div class="report-meta"><span class="report-badge {badge_cls}">{badge_text}</span> · {fmt_size(r["size"])}</div>\n'
            f'</div>\n'
            f'</a>\n')

def _empty_card(slot_is_advanced_row=False):
    if slot_is_advanced_row:
        return ('<div class="report-card report-card-empty" style="cursor:default;background:#0d1117">\n'
                '<div class="report-icon" style="color:#ffcc00">⏳</div>\n'
                '<div class="report-info">\n'
                '<div class="report-name" style="color:#ffcc00;font-size:11px">待更新</div>\n'
                '</div>\n'
                '</div>\n')
    else:
        return ('<div class="report-card report-card-empty" style="cursor:default;background:#0d1117">\n'
                '<div class="report-icon" style="color:#8b949e">—</div>\n'
                '<div class="report-info">\n'
                '<div class="report-name" style="color:#8b949e;font-size:11px">无报告</div>\n'
                '</div>\n'
                '</div>\n')

# ─── 补全日期连续区间（无报告日期也显示全空位组）──
from datetime import timedelta
date_range = []
if sorted_dates:
    dt_min = datetime.strptime(sorted_dates[-1], '%Y-%m-%d').date()
    dt_max = datetime.strptime(sorted_dates[0], '%Y-%m-%d').date()
    d = dt_max
    while d >= dt_min:
        date_range.append(d.strftime('%Y-%m-%d'))
        d -= timedelta(days=1)
else:
    date_range = sorted_dates

# 按日期输出
for dt in date_range:
    day_reports = dates_group.get(dt, [])
    
    # 日期标题 + 星期
    try:
        dt_obj = datetime.strptime(dt, '%Y-%m-%d')
        weekday_cn = ['周一','周二','周三','周四','周五','周六','周日'][dt_obj.weekday()]
        day_label = weekday_cn
    except:
        day_label = ''
    
    # 类型汇总
    count_by_type = {}
    for r in day_reports:
        count_by_type[r['type']] = count_by_type.get(r['type'], 0) + 1
    type_summary = ' · '.join([f'{icon}{label}:{count_by_type.get(t,0)}' for t,label,icon in [('premarket','盘前','📋'),('midday','午间','🌤'),('closing','收盘','📊'),('weekly','周复','📈')]])
    
    # 日期头渐变
    grad = date_header_gradient(dt, type_summary)
    
    html += f'<div class="date-group">\n'
    html += f'<div class="date-header" style="background:{grad}">{dt} <span class="day">{day_label}</span><span style="font-size:11px;color:#8b949e">{type_summary}</span></div>\n'
    
    # 判断该日期是交易日还是非交易日
    is_trading_day = dt_obj.weekday() < 5  # 周一到周五=交易日, 周六日=非交易日
    is_sunday = dt_obj.weekday() == 6
    
    # 构建查询表
    report_lookup = {}
    for r in day_reports:
        report_lookup[(r['type'], r['version'])] = r
    
    type_list = ['premarket', 'midday', 'closing', 'weekly']
    
    def _should_show_placeholder(typ, version):
        """
        根据规则判断占位卡类型:
        - 'none'    → 无报告
        - 'pending' → 待更新
        """
        key = (typ, version)
        if key in report_lookup:
            return None  # 报告存在，不显示占位卡
        
        if is_trading_day:
            if typ == 'weekly':
                return 'none'  # 交易日周复盘固定无报告
            return 'pending'   # 交易日盘前/午间/收盘未生成→待更新
        else:
            # 非交易日
            if typ == 'weekly':
                if is_sunday:
                    return 'pending'  # 周日周复盘未生成→待更新
                else:
                    return 'none'    # 非周日→无报告
            else:
                return 'none'  # 盘前/午间/收盘非交易日→无报告
    
    html += '<div class="report-grid">\n'
    
    # 第一行：标准版
    for typ in type_list:
        key = (typ, 'standard')
        if key in report_lookup:
            html += _card_html(report_lookup[key])
        else:
            status = _should_show_placeholder(typ, 'standard')
            html += _empty_card(slot_is_advanced_row=(status == 'pending'))
    
    # 第二行：进阶版
    for typ in type_list:
        key = (typ, 'advanced')
        if key in report_lookup:
            html += _card_html(report_lookup[key])
        else:
            status = _should_show_placeholder(typ, 'advanced')
            html += _empty_card(slot_is_advanced_row=(status == 'pending'))
    
    html += '</div>\n'  # report-grid
    html += '</div>\n'  # date-group

# Footer + JS
html += '''
<div class="footer">
🌀 混动系统 · 报告中心 · 自动生成
</div>

<script>
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', function() {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');
    const filter = this.dataset.filter;
    document.querySelectorAll('.report-card').forEach(card => {
      if (filter === 'all') {
        card.style.display = 'flex';
      } else if (filter === 'advanced') {
        card.style.display = card.dataset.version === 'advanced' ? 'flex' : 'none';
      } else if (filter === 'standard') {
        card.style.display = card.dataset.version === 'standard' ? 'flex' : 'none';
      } else {
        card.style.display = card.dataset.type === filter ? 'flex' : 'none';
      }
    });
    document.querySelectorAll('.date-group').forEach(g => {
      const visible = g.querySelectorAll('.report-card[style*="display: flex"], .report-card:not([style])');
      g.style.display = visible.length > 0 ? 'block' : 'none';
    });
  });
});
</script>

</div></body></html>
'''

# ─── 保存 ─────────────────────────────────────
out_path = os.path.join(REPORT_DIR, 'dashboard.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'✅ Dashboard 已生成: {out_path}')
print(f'   报告总数: {total}')
print(f'   盘前: {type_count.get("盘前简报",0)} · 午间: {type_count.get("午间监测",0)} · 收盘: {type_count.get("收盘简报",0)} · 周复盘: {type_count.get("周复盘",0)} · 其他: {type_count.get("其他",0)}')
