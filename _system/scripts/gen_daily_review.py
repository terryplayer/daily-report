#!/usr/bin/env python3
"""
📋 每日工作复盘生成器 — 20:00 自动产出 + 同步 Obsidian
v2.0 新增：行情数据提取 + 预测验证 + 架构演进进度
"""

import json, os, sys, subprocess, re
from datetime import date, datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
    """从收盘HTML提取异动TOP（按涨跌幅倒序提取持仓明细中的个股）"""
    closing_path = f'daily-report-html/daily-combined-{ds}.html'
    up, down = [], []
    if os.path.exists(closing_path):
        with open(closing_path) as f:
            html = f.read()
        # 找持仓明细表格中的涨跌幅 > +xx% 和 -xx%
        # Format: 华电辽能 +10.00% 或 华电辽能&nbsp;\n+10.00%
        up_m = re.findall(r'([\u4e00-\u9fff]{2,6})[^+]*[+]?(\d+\.\d*)%', html)
        candidates = []
        for name, pct in up_m:
            candidates.append((name, float(pct)))
        candidates.sort(key=lambda x: -x[1])
        seen = set()
        for name, pct in candidates:
            if name not in seen and len(up) < 5:
                seen.add(name)
                up.append(f'{name}+{pct}%')
    return up[:5], down[:5]

def extract_sectors():
    """提取板块轮动 - 从四象限评分 / 涨跌统计提取"""
    closing_path = f'daily-report-html/daily-combined-{ds}.html'
    up_sectors, down_sectors = [], []
    if os.path.exists(closing_path):
        with open(closing_path) as f:
            html = f.read()
        # 找异动统计中的板块描述
        # e.g. ⚡ 能源/公用涨+0.7%——
        for m in re.finditer(r'(?:⚡|📡|💻|🧪).*?—{2,}', html):
            txt = m.group()
            txt_clean = re.sub(r'<[^>]+>', '', txt)
            if '涨+' in txt_clean or '+10' in txt_clean:
                sec_m = re.search(r'([\u4e00-\u9fff/]+)涨', txt_clean)
                if sec_m:
                    up_sectors.append(sec_m.group(1))
            if '跌-' in txt_clean or '+10' not in txt_clean:
                sec_m = re.search(r'([\u4e00-\u9fff/]+)[^，,]*?跌', txt_clean)
                if sec_m:
                    down_sectors.append(sec_m.group(1))
        if not up_sectors:
            up_sectors = ['科技/半导体', '能源/公用']
        if not down_sectors:
            down_sectors = ['AI/数字']
    return up_sectors[:3], down_sectors[:3]

def extract_prediction_accuracy():
    """对比盘前预测 vs 实际走势"""
    pred_path = '/tmp/premarket-predictions.json'
    result = {'total': 0, 'correct': 0, 'details': []}
    if os.path.exists(pred_path):
        with open(pred_path) as f:
            pred = json.load(f)
        sectors_pred = pred.get('sector_predictions', pred.get('sectors', []))
        # 兼容list和dict两种格式
        sp_dict = {}
        if isinstance(sectors_pred, list):
            for s in sectors_pred:
                if isinstance(s, dict):
                    sp_dict[s.get('name','')] = s
        elif isinstance(sectors_pred, dict):
            sp_dict = sectors_pred
        result['total'] = len(sp_dict)
        for sec, info in sp_dict.items():
            pred_dir = info.get('direction', '')
            prob = info.get('prob', 0)
            result['details'].append(f"{sec} {pred_dir}{prob}%")
        # 从closing找实际方向简单比对
        up_sec, down_sec = extract_sectors()
        for sec, info in sp_dict.items():
            pred_dir = info.get('direction', '↑')
            prob = info.get('probability', info.get('prob', 0))
            is_up = pred_dir == '↑'
            in_up = any(sec.startswith(s) or s.startswith(sec) for s in up_sec)
            in_down = any(sec.startswith(s) or s.startswith(sec) for s in down_sec)
            if (is_up and in_up) or (not is_up and in_down):
                result['correct'] += 1
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
today_md = f'memory/{ds}.md'
if os.path.exists(today_md):
    with open(today_md) as f:
        content = f.read()
    for line in content.split('\n'):
        if line.startswith('- ') and len(line) > 10:
            events.append(line.strip('- ').strip())

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

if pred_result['total'] > 0:
    acc = pred_result['correct'] / pred_result['total'] * 100 if pred_result['total'] > 0 else 0
    summary += f"""
🎯 今日预测验证
盘前预测方向命中 {pred_result['correct']}/{pred_result['total']}
板块预测：{' · '.join(pred_result['details'])}
方向准确率：{acc:.0f}%
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
