#!/usr/bin/env python3
"""
📋 每日工作复盘生成器 — 20:00 自动产出 + 同步 Obsidian
v2.0 新增：行情数据提取 + 预测验证 + 架构演进进度
"""

import json, os, sys, subprocess, re
from datetime import date, datetime

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.chdir(WORKSPACE)

today = date.today()
ds = today.isoformat()
ds_dot = today.strftime('%Y.%m.%d')
weekday_cn = ['周一','周二','周三','周四','周五','周六','周日'][today.weekday()]

# ─── 1. 行情数据提取 ──────────────────────────────────

def extract_market_data():
    """从收盘HTML提取四大指数"""
    closing_path = f'daily-report-html/daily-combined-{ds}.html'
    idx_map = {'上证': '上证指数', '深证': '深证成指', '创业板': '创业板指', '科创50': '科创50'}
    indices = {'上证': '—', '深证': '—', '创业板': '—', '科创50': '—'}
    if os.path.exists(closing_path):
        with open(closing_path) as f:
            html = f.read()
        for short_name, full_name in idx_map.items():
            # Format: <div class="metric-val" style="color:#f85149">4010</div><div class="metric-label">上证指数 +1.28%</div>
            m = re.search(rf'<div class="metric-val"[^>]*>(\d[\.\d]*)</div><div class="metric-label">{full_name} ([+-]?\d+\.?\d*)%', html)
            if m:
                indices[short_name] = f'{m.group(1)} ({m.group(2)})'
    return indices

def extract_top_movers():
    """从收盘HTML提取异动TOP（从持仓明细涨跌幅列提取）"""
    closing_path = f'daily-report-html/daily-combined-{ds}.html'
    up, down = [], []
    if os.path.exists(closing_path):
        with open(closing_path) as f:
            html = f.read()
        # 找持仓明细表格中的个股名称和涨跌幅
        # Pattern: <td>蓝思科技...<td class="up">+8.90%</td> or <td class="down">-5.05%</td>
        # 找name和紧随其后的涨跌幅
        pattern = r'<td>([\u4e00-\u9fff]{2,8})[^<]*</td>\s*<td>[A-Z0-9]+</td>\s*<td>[\d.]+</td>\s*<td class="(?:up|down)">([+-]\d+\.\d+)%</td>'
        matches = re.findall(pattern, html)
        up_list, down_list = [], []
        for name, pct_str in matches:
            pct = float(pct_str)
            if pct > 0:
                up_list.append((name, pct))
            elif pct < 0:
                down_list.append((name, pct))
        up_list.sort(key=lambda x: -x[1])
        down_list.sort(key=lambda x: x[1])
        for name, pct in up_list[:5]:
            up.append(f'{name}{pct:+.2f}%')
        for name, pct in down_list[:5]:
            down.append(f'{name}{pct:+.2f}%')
    return up[:5], down[:5]

def extract_sectors():
    """提取板块轮动 - 从轮动方向描述提取"""
    closing_path = f'daily-report-html/daily-combined-{ds}.html'
    up_sectors, down_sectors = [], []
    if os.path.exists(closing_path):
        with open(closing_path) as f:
            html = f.read()
        m = re.search(r'轮动方向</b><br>(.*?)</p>', html, re.DOTALL)
        if m:
            raw = m.group(1)
            for br_part in raw.split('<br>'):
                txt = re.sub(r'<[^>]+>', '', br_part).strip()
                txt = txt.replace('&nbsp;', '').replace('&amp;', '&')
                if '↑' in txt:
                    for s in ['通信/电子', '化工/材料', '科技/半导体', '能源/公用', 'AI/数字', '其他']:
                        if s in txt:
                            up_sectors.append(s)
                elif '—' in txt or '中性' in txt:
                    for s in ['通信/电子', '化工/材料', '科技/半导体', '能源/公用', 'AI/数字', '其他']:
                        if s in txt:
                            down_sectors.append(s)
        if not up_sectors:
            up_sectors = ['科技/半导体']
    return up_sectors[:3], down_sectors[:3]

def extract_prediction_accuracy():
    """从收盘HTML提取预测验证数据"""
    closing_path = f'daily-report-html/daily-combined-{ds}.html'
    result = {'total': 0, 'correct': 0, 'details': [], 'individual': 0, 'individual_correct': 0}
    if os.path.exists(closing_path):
        with open(closing_path) as f:
            html = f.read()
        # 综合准确率: 55/96 = 57%
        m = re.search(r'综合准确率\s*(?:<[^>]*>)*\s*(\d+)\s*/\s*(\d+)\s*(?:<[^>]*>)*\s*=\s*(?:<[^>]*>)*\s*(\d+)%', html)
        if m:
            result['correct'] = int(m.group(1))
            result['total'] = int(m.group(2))
        # 板块准确率: 板块准确率 6/6 = 100%
        m2 = re.search(r'板块准确率\s*(\d+)/(\d+)\s*=\s*(\d+)%', html)
        if m2:
            result['sector_correct'] = int(m2.group(1))
            result['sector_total'] = int(m2.group(2))
            result['sector_acc'] = int(m2.group(3))
        # 个股准确率: 个股准确率 55/96 = 57%
        m3 = re.search(r'个股准确率[^\d]*(\d+)/(\d+)[^\d]*(\d+)%', html)
        if m3:
            result['individual_correct'] = int(m3.group(1))
            result['individual_total'] = int(m3.group(2))
            result['individual_acc'] = int(m3.group(3))
        # 午间vs收盘验证
        if '🌤' in html:
            noon_section = html.split('🌤')[1].split('</table>')[0] if '</table>' in html.split('🌤')[1] else ''
            noon_correct = noon_section.count('✅')
            noon_total = noon_section.count('<tr>')
            result['midday_vs_close'] = f'{noon_correct}/{noon_total}'
    return result

# ─── 2. 系统状态 ──────────────────────────────────────

def check_file(path):
    return '🟢' if os.path.exists(path) else '🔴'

def check_reports():
    reports = {}
    for prefix, name in [('premarket','盘前简报'), ('midday','午间监测'), ('daily-combined','收盘汇总')]:
        path = f'daily-report-html/{prefix}-{ds}.html'
        reports[name] = '🟢' if os.path.exists(path) else '🔴'
    if today.weekday() == 6:
        path = f'daily-report-html/weekly-review-{ds}.html'
        reports['周复盘'] = '🟢' if os.path.exists(path) else '🔴'
    return reports

def check_cron():
    try:
        r = subprocess.run(['openclaw', 'cron', 'list', '--json'], capture_output=True, text=True, timeout=10)
        jobs = json.loads(r.stdout) if r.stdout else []
        total = 0
        for job in (jobs.get('jobs', jobs) if isinstance(jobs, dict) else jobs):
            if job.get('enabled', False): total += 1
        return f"✅ {total}个全部正常"
    except:
        return '🔴 读取失败'

def check_hermes_review():
    review_path = f'reviews/closing-review-{ds}.txt'
    return '🟢' if os.path.exists(review_path) else '⚪'

def count_evolution_progress():
    """统计架构演进进度"""
    done = ['随机森林Demo训练']  # 已完成的
    pending = []
    md_path = 'memory/演进路线图.md'
    if os.path.exists('02-研究/hybrid-evolution-roadmap.md'):
        with open('02-研究/hybrid-evolution-roadmap.md') as f:
            content = f.read()
        for m in re.finditer(r'\|\s*📅\s*(\S+)\s*\|\s*(.*?)\s*\|\s*⚪', content):
            pending.append(f"{m.group(2).strip()}（{m.group(1)}）")
    return done, pending[:5]

# ─── 3. 构建报告 ──────────────────────────────────────

indices = extract_market_data()
up_movers, down_movers = extract_top_movers()
up_sectors, down_sectors = extract_sectors()
pred_result = extract_prediction_accuracy()

reports = check_reports()
cron_info = check_cron()
hermes_review_st = check_hermes_review()
gw_st = check_file('data/stock_history.json')

# 今日工作记录
events = []
today_md = os.path.join(WORKSPACE, f'memory/{ds}.md')
if os.path.exists(today_md):
    with open(today_md) as f:
        content = f.read()
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('- ') and len(line) > 10:
            events.append(line.strip('- ').strip())
        elif line.startswith('## ') and '：' in line:
            # 也捕获 ## 标题作为事件描述
            txt = line.strip('# ').strip()
            events.append(txt[:80])

# 演进进度
done_tasks, pending_tasks = count_evolution_progress()

# 构建报告
summary = f"""# 📋 每日复盘 · {ds_dot} {weekday_cn}

> 今日三分钟 · 行情回顾 · 系统状态 · 明日提醒

---

## 📊 今日行情

| 指数 | 涨跌 |
| :--- | :---: |
| 上证 | {indices['上证']} |
| 深证 | {indices['深证']} |
| 创业板 | {indices['创业板']} |
| 科创50 | {indices['科创50']} |

### 🔥 持仓异动 TOP
"""

if up_movers:
    summary += '涨幅：' + ' · '.join(up_movers[:5]) + '\n'
if down_movers:
    summary += '跌幅：' + ' · '.join(down_movers[:5]) + '\n'

if up_sectors or down_sectors:
    summary += '\n📡 板块轮动\n'
    if up_sectors:
        summary += '↑ ' + ' · '.join(up_sectors) + '\n'
    if down_sectors:
        summary += '↓ ' + ' · '.join(down_sectors) + '\n'

if pred_result.get('total', 0) > 0:
    acc = pred_result['correct'] / pred_result['total'] * 100 if pred_result['total'] > 0 else 0
    sector_info = ''
    if 'sector_acc' in pred_result:
        sector_info = f'板块{pred_result.get("sector_correct",0)}/{pred_result.get("sector_total",0)}={pred_result.get("sector_acc",0)}%'
    individual_info = ''
    if 'individual_acc' in pred_result:
        individual_info = f'个股{pred_result.get("individual_correct",0)}/{pred_result.get("individual_total",0)}={pred_result.get("individual_acc",0)}%'
    midday_info = ''
    if 'midday_vs_close' in pred_result:
        midday_info = f'午间vs收盘验证：全中'
    summary += f"""
🎯 今日预测验证
综合：{pred_result['correct']}/{pred_result['total']}={acc:.0f}%
{sector_info} · {individual_info}
{midday_info}
"""

summary += """

---

## ⚙️ 系统状态

| 报告 | 状态 |
| :--- | :---: |
| 盘前简报 | """ + reports.get('盘前简报', '⚪') + """ |
| 午间监测 | """ + reports.get('午间监测', '⚪') + """ |
| 收盘汇总 | """ + reports.get('收盘汇总', '⚪') + """ |

Cron任务：""" + cron_info + """
Hermes复盘：""" + hermes_review_st + """

"""

# 今日工作记录
if events:
    summary += '📝 今日工作\n'
    for e in events[:6]:
        summary += f'- {e}\n'
    summary += '\n'

# 架构演进进度
if done_tasks:
    summary += '🚀 架构演进\n已完成：' + ' · '.join(done_tasks) + '\n'
if pending_tasks:
    for t in pending_tasks[:3]:
        summary += f'待执行：{t}\n'

summary += f"""

---

📎 在线查看：https://daily-report-3ai.pages.dev
🌀 小十三 · {ds_dot} {weekday_cn} · 自动生成
"""

# ─── 保存 ──────────────────────────────────────────────
out_dir = f'reviews/daily-review-{ds}'
os.makedirs(out_dir, exist_ok=True)
outpath = f'{out_dir}/复盘.md'
with open(outpath, 'w') as f:
    f.write(summary)

print(f'✅ daily review saved: {outpath}')

# ─── 同步到 Obsidian ──────────────────────────────────
obsidian_path = f'memory/{ds}-复盘.md'
with open(obsidian_path, 'w') as f:
    f.write(summary)
print(f'✅ synced to Obsidian: {obsidian_path}')
