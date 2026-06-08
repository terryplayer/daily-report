#!/usr/bin/env python3
"""
📊 收盘简报报告生成器 (统一模型 v1)
读取: stock_analysis_cache.json + premarket-predictions.json + template-closing.html
输出: daily-report-html/daily-combined-YYYY-MM-DD.html
"""

import json, os, sys, warnings
from datetime import date

warnings.filterwarnings('ignore', category=Warning, module='urllib3')
from validate_report import validate

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)

with open('/tmp/stock_analysis_cache.json') as f:
    cache = json.load(f)
with open('scripts/template-stocks.json') as f:
    wl = json.load(f)

rs_ranking = {s['code']: s for s in cache['rs_ranking']}
multi_stocks = {s['code']: s for s in cache['multi_factor_scores']['stocks']}
stock_mom = cache.get('stock_momentum', {})
sec_summary = cache['multi_factor_scores']['sector_summary']
sec_ranking = {s['sector']: s for s in cache['sector_ranking']}
sec_mom = cache['sector_momentum']
vol_alerts_list = cache.get('volatility_alerts', [])
vol_alerts = {v['code']: v for v in vol_alerts_list}
top_sectors = sec_mom.get('top_sectors', [])
bot_sectors = sec_mom.get('bottom_sectors', [])
ts_lookup = cache.get('tech_signals', {})

sector_order = ['能源/公用事业', '通信/电子', '科技/半导体', '化工/材料', 'AI/数字经济', '其他']
sector_display = {
    '能源/公用事业': '⚡ 能源/公用', '通信/电子': '📡 通信/电子',
    '科技/半导体': '💻 科技/半导体', '化工/材料': '🧪 化工/材料',
    'AI/数字经济': '🤖 AI/数字', '其他': '📦 其他'
}
sector_emoji = {'科技/半导体': '💻', '通信/电子': '📡', '能源/公用事业': '⚡',
                '化工/材料': '🧪', 'AI/数字经济': '🤖', '其他': '📦'}


def s(val, fmt='.2f'):
    if val is None or val == '—': return '—'
    try: return f'{float(val):{fmt}}'
    except: return str(val)


# ──────────────────────────────────────────────
# 1. 大盘指数收盘
# ──────────────────────────────────────────────
import tushare as ts
idx_conf = [
    ('000001.SH', '上证指数', '4,083.97', '+0.22'),
    ('399001.SZ', '深证成指', '15,704.71', '+0.73'),
    ('399006.SZ', '创业板指', '4,122.99', '+1.65'),
    ('000688.SH', '科创50', '1,726.18', '+2.11'),
]


def _fetch_index(tc, dp, dc):
    import subprocess, json
    try:
        r = subprocess.run([
            'python3', '-c',
            'import tushare as ts;ts.set_token(open("data/tushare_token.txt").read().strip());'
            'pro=ts.pro_api();df=pro.index_daily(ts_code="' + tc + '",'
            'start_date="20260603",end_date="20260603");'
            'print(df.to_json(orient="records") if df is not None else "null");'
        ], capture_output=True, text=True, timeout=10)
        if r.stdout and len(r.stdout) > 10:
            rows = json.loads(r.stdout)
            if rows and isinstance(rows, list) and len(rows) > 0:
                row = rows[0]
                pr = str(int(row.get('close', 0)))
                cg = '%+.2f' % float(row.get('pct_chg', 0))
                return pr, cg
    except:
        pass
    return dp, dc


m = ''
idx_chgs = []
for tc, n, dp, dc in idx_conf:
    pr, cg = _fetch_index(tc, dp, dc)
    cl = '#f85149' if float(cg) > 0 else ('#3fb950' if float(cg) < 0 else '#d9a52e')
    idx_chgs.append((n, float(cg)))
    m += f'<div class="metric-card"><div class="metric-val" style="color:{cl}">{pr}</div><div class="metric-label">{n} {cg}%</div></div>\n'

best_idx_name, best_idx_val = max(idx_chgs, key=lambda x: x[1])
cg_all_pos = all(c > 0 for _, c in idx_chgs)
up_count = len([s for s in cache['rs_ranking'] if s.get('stock_change_pct', 0) > 0])
dn_count = len([s for s in cache['rs_ranking'] if s.get('stock_change_pct', 0) < 0])
ratio_str = f'1:{max(1, dn_count // max(1, up_count))}' if up_count > 0 else '—'
idx_desc = (
    f'📌 四大指数{"全面收涨，" if cg_all_pos else "涨跌互现，"}{best_idx_name}领涨{best_idx_val:+.2f}%。'
    f'全市场涨跌比约{ratio_str}（涨{up_count}家·跌{dn_count}家），结构性行情延续。'
)
index_html = f'<div class="metric-grid">{m}</div>\n<p style="font-size:12px">{idx_desc}</p>\n'

# ──────────────────────────────────────────────
# ──────────────────────────────────────────────
# 2. 板块评分 & 轮动方向
# ──────────────────────────────────────────────
def sc_class(val):
    if val >= 80: return 'sc-aplus'
    if val >= 60: return 'sc-a'
    if val >= 40: return 'sc-b'
    if val >= 20: return 'sc-c'
    return 'sc-d'

sr = ''
sec_ac = {}
for sec in sector_order:
    srs = [x for x in cache['rs_ranking'] if x.get('sector') == sec]
    rv = [x['rs_value'] for x in srs if 'rs_value' in x]
    ar = sum(rv) / len(rv) if rv else 0
    rs_s = round(max(30, min(95, 50 + ar * 1.5)))
    ms_ = 70 if sec in top_sectors else (35 if sec in bot_sectors else 55)
    sv = len([v for v in vol_alerts_list if v.get('sector') == sec])
    mrd_ = round(max(30, min(95, 40 + sv * 15)))
    ss_ = sec_summary.get(sec, {})
    mf_ = round(max(30, min(95, ss_.get('avg_score', 5) * 10)))
    un = round(rs_s * 0.25 + ms_ * 0.20 + mrd_ * 0.10 + mf_ * 0.30 + 50 * 0.15)
    ct = '<b style="color:#f85149">超配</b>' if un >= 60 else (
        '<span style="color:#d9a52e">标配</span>' if un >= 45 else '<span style="color:#3fb950">低配</span>')
    rt = '<span class="tag tag-aplus">A</span>' if un >= 60 else (
        '<span class="tag tag-b">B</span>' if un >= 45 else '<span class="tag tag-d">D</span>')
    ac = sum(x.get('stock_change_pct', 0) for x in srs) / len(srs) if srs else 0
    cc = 'up' if ac > 0 else 'down'
    sec_ac[sec] = ac
    sr += '<tr><td>' + sector_display.get(sec, sec) + '</td>'
    sr += '<td class="' + cc + '">' + ('%+.1f%%' % ac) + '</td>'
    sr += '<td>' + str(len(srs)) + '</td><td>' + rt + '</td>'
    sr += '<td><span class="' + sc_class(rs_s) + '">' + str(rs_s) + '</span></td>'
    sr += '<td><span class="' + sc_class(ms_) + '">' + str(ms_) + '</span></td>'
    sr += '<td><span class="' + sc_class(mrd_) + '">' + str(mrd_) + '</span></td>'
    sr += '<td><span class="' + sc_class(mf_) + '">' + str(mf_) + '</span></td>'
    sr += '<td>50</td><td>' + ct + '</td></tr>\n'

best_sec = max(sec_ac, key=sec_ac.get)
worst_sec = min(sec_ac, key=sec_ac.get)

# 轮动方向：按领涨/领跌/中性归类
up_list, down_list, flat_list = [], [], []
for sec in sector_order:
    ac = sec_ac[sec]
    srs = [x for x in cache['rs_ranking'] if x.get('sector') == sec]
    pump = [x for x in srs if abs(x.get('stock_change_pct', 0)) > 8]
    pn = '、'.join([x['name'] + ('%+.2f%%' % x.get('stock_change_pct', 0)) for x in pump])
    sec_n = sector_display.get(sec, sec)
    if pn:
        desc = sec_n + '涨' + ('%+.1f%%' % ac) + '\u2014\u2014' + pn + '大幅异动'
        up_list.append(desc)
    elif ac > 1:
        up_list.append(sec_n + ('%+.1f%%' % ac))
    elif ac < -1:
        down_list.append(sec_n + ('%+.1f%%' % ac))
    else:
        flat_list.append(sec_n + ('%+.1f%%' % ac))

rot_parts = []
if up_list:
    rot_parts.append('<span style="color:#f85149">' + chr(8593) + ' 领涨</span>\uff1a' + '\uff1b'.join(up_list[:4]))
if down_list:
    rot_parts.append('<span style="color:#3fb950">' + chr(8595) + ' 领跌</span>\uff1a' + '\uff1b'.join(down_list[:4]))
if flat_list:
    rot_parts.append('<span style="color:#8b949e">' + chr(8212) + ' 中性</span>\uff1a' + '\uff1b'.join(flat_list[:4]))

sec_rotation_desc = '\U0001f4a1 <b>轮动方向</b><br>' + '<br>'.join(rot_parts)
sector_html = ('<table><tr><th>板块</th><th>涨跌幅</th><th>个股</th><th>评级</th>'
               '<th>RS</th><th>动量</th><th>MRD</th><th>多因子</th><th>轮动</th><th>配置</th></tr>'
               + sr + '</table><p style="margin-top:6px;font-size:12px">' + sec_rotation_desc + '</p>\n')

# ─── 🔥📌 标签计算（与盘前规则一致）──────────────────
# 🔥 = 统一模型板块推荐股（每个板块RS排名前3）
from datetime import date as _dt
top_sectors = sec_mom.get('top_sectors', [])
bot_sectors = sec_mom.get('bottom_sectors', [])
sector_order_c = ['科技/半导体', '通信/电子', 'AI/数字经济', '化工/材料', '能源/公用事业']
sector_display_c = {'科技/半导体':'💻 科技/半导体','通信/电子':'📡 通信/电子','AI/数字经济':'🤖 AI/数字','化工/材料':'🧪 化工/材料','能源/公用事业':'⚡ 能源/公用事业'}

strong_stocks = set()
for sec in sector_order_c:
    sec_rs = [s for s in cache['rs_ranking'] if s.get('sector') == sec]
    for s in sec_rs[:3]:
        strong_stocks.add(s['name'])

# 📌 = 今日关注事件涉及的股票
focus_stock_set = set()
try:
    if top_sectors:
        sec_rs = [s for s in cache['rs_ranking'] if s.get('sector') == top_sectors[0]]
        if sec_rs: focus_stock_set.add(sec_rs[0]['name'])
    for v in vol_alerts_list[:2]:
        focus_stock_set.add(v.get('name', ''))
except:
    pass

# ──────────────────────────────────────────────
# 3. 预测准确率评估
# ──────────────────────────────────────────────
try:
    with open('/tmp/premarket-predictions.json') as f:
        pred_data = json.load(f)
    
    # 大盘预判
    outlook = pred_data.get('market_outlook', {})
    trend_pred = outlook.get('trend', '震荡')
    prob = outlook.get('probability', 50)
    
    # 板块方向
    strat = pred_data.get('strategy', {})
    overweight = strat.get('overweight', [])
    underweight = strat.get('underweight', [])
    neutral = strat.get('neutral', [])
    
    # 对比实际
    pr_rows = ''
    correct = 0
    total_sec = 0
    for sec in sector_order:
        sec_n = sector_display.get(sec, sec)
        srs = [x for x in cache['rs_ranking'] if x.get('sector') == sec]
        ac = sum(x.get('stock_change_pct', 0) for x in srs) / len(srs) if srs else 0
        
        if sec in overweight:
            pred_dir = chr(8593)
            pred_note = '看涨'
        elif sec in underweight:
            pred_dir = chr(8595)
            pred_note = '看跌'
        else:
            pred_dir = chr(8212)
            pred_note = '中性'
        
        actual_dir = chr(8593) if ac > 1 else (chr(8595) if ac < -1 else chr(8212))
        
        if (pred_dir == chr(8593) and actual_dir == chr(8593)) or (pred_dir == chr(8595) and actual_dir == chr(8595)):
            verify = chr(9989)
            correct += 1
        elif pred_dir == chr(8212) and actual_dir == chr(8212):
            verify = chr(9989)
            correct += 1
        else:
            verify = chr(9898)
        total_sec += 1
        
        pr_rows += '<tr>'
        pr_rows += '<td>' + sec_n + '</td>'
        pr_rows += '<td class="up">' + pred_dir + ' ' + pred_note + '</td>'
        pr_rows += '<td>' + str(prob) + '%</td>'
        cls = 'up' if ac > 0 else 'down'
        pr_rows += '<td class="' + cls + '">' + ('%+.1f%%' % ac) + '</td>'
        pr_rows += '<td>' + verify + '</td>'
        pr_rows += '<td style="font-size:11px;color:#8b949e">' + actual_dir + ' ' + ('走强' if ac > 1 else ('走弱' if ac < -1 else '震荡')) + '</td>'
        pr_rows += '</tr>\n'
    
    acc_rate = correct / total_sec * 100 if total_sec else 0
    
    # ─── 个股预测验证 ───
    up_arrow = chr(8593); down_arrow = chr(8595); dash = chr(8212)
    stock_by_sec = {sec: [] for sec in sector_order}
    for s in cache['rs_ranking']:
        sec = s.get('sector', '')
        code = s.get('code', '')
        rank = rs_ranking.get(code, {}).get('rank', 'B')
        name = s.get('name', '?')
        chg = s.get('stock_change_pct', 0)
        if sec in stock_by_sec:
            stock_by_sec[sec].append({'name': name, 'code': code, 'rank': rank, 'chg': chg})
    
    stock_html = ''
    stock_correct = 0
    stock_total = 0
    sec_disp = {'能源/公用事业':'⚡ 能源/公用事业','通信/电子':'📡 通信/电子','科技/半导体':'💻 科技/半导体','化工/材料':'🧪 化工/材料','AI/数字经济':'🤖 AI/数字','其他':'📦 其他'}
    # 按评级统计
    rating_stats = {'A+/A': [0, 0], 'B': [0, 0], 'C/D': [0, 0]}
    # 按板块统计
    sector_stats = {}
    for sec in sector_order:
        sec_stocks = stock_by_sec.get(sec, [])
        if not sec_stocks:
            continue
        disp = sec_disp.get(sec, sec)
        stock_html += '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:10px 0 4px">' + disp + '</h3>\n'
        stock_html += '<table><colgroup><col style="width:14%"><col style="width:12%"><col style="width:14%"><col style="width:12%"><col style="width:8%"><col style="width:20%"><col style="width:22%"></colgroup>'
        stock_html += '<tr><th>个股</th><th>代码</th><th>盘前方向</th><th>收盘涨跌</th><th>验证</th><th>偏差分析</th><th>操作建议</th></tr>\n'
        for s in sec_stocks:
            rank = s['rank']
            chg = s['chg']
            cls = 'up' if chg > 0 else 'down'
            cl_h = '#f85149' if cls == 'up' else '#3fb950'
            if rank in ('A+', 'A'):
                pd_ = up_arrow + ' 强势'
            elif rank in ('C', 'D'):
                pd_ = down_arrow + ' 弱势'
            else:
                pd_ = dash + dash + ' 中性'
            stock_total += 1
            # 判断预测是否准确
            is_correct = False
            if rank in ('A+', 'A'):
                is_correct = chg > 0  # 看涨→涨了
            elif rank in ('C', 'D'):
                is_correct = chg < 0  # 看跌→跌了
            else:
                is_correct = abs(chg) < 2  # 中性→震荡±2%以内
            
            if is_correct:
                flag = chr(9989)
                stock_correct += 1
                dev_ = '方向判断正确'
                if rank in ('A+', 'A'): rating_stats['A+/A'][0] += 1
                elif rank in ('C', 'D'): rating_stats['C/D'][0] += 1
                else: rating_stats['B'][0] += 1
            else:
                flag = chr(9898)
                dev_ = '偏差 '
                if rank in ('A+', 'A'): dev_ += '高估看涨'
                elif rank in ('C', 'D'): dev_ += '高估看跌'
                else: dev_ += '中性震荡'
            # 跟踪评级统计
            if rank in ('A+', 'A'): rating_stats['A+/A'][1] += 1
            elif rank in ('C', 'D'): rating_stats['C/D'][1] += 1
            else: rating_stats['B'][1] += 1
            # 跟踪板块统计
            if sec not in sector_stats:
                sector_stats[sec] = [0, 0]
            if flag == chr(9989): sector_stats[sec][0] += 1
            sector_stats[sec][1] += 1
            # 操作建议基于rank和涨跌
            if rank in ('A+', 'A') and chg > 0:
                aft_ = '\U0001f534 强势收涨\xb7关注明日延续性'
            elif rank in ('C', 'D') and chg < 0:
                resolve_support = ''
                aft_ = '\U0001f7e2 弱势收跌\xb7关注支撑位'
            elif abs(chg) > 5:
                aft_ = '\U0001f534 大涨\xb7设止盈防回落' if chg > 0 else '\U0001f7e2 大跌\xb7关注止损'
            else:
                aft_ = '\u26aa 窄幅震荡\xb7持有'
            stock_name_tag = s['name']
            _has_f = s['name'] in strong_stocks
            _has_m = s['name'] in focus_stock_set
            if _has_f and _has_m:
                stock_name_tag = s['name'] + '&nbsp;<span class="tag-rec">\U0001f525</span>&nbsp;<span class="tag-focus">\U0001f4cc</span>'
            elif _has_f:
                stock_name_tag = s['name'] + '&nbsp;<span class="tag-rec">\U0001f525</span>'
            elif _has_m:
                stock_name_tag = s['name'] + '&nbsp;<span class="tag-focus">\U0001f4cc</span>'
            stock_html += '<tr><td>' + stock_name_tag + '</td><td>' + s['code'] + '</td>'
            stock_html += '<td class="' + cls + '">' + pd_ + '</td>'
            stock_html += '<td class="' + cls + '">' + ('%+.2f%%' % chg) + '</td>'
            stock_html += '<td>' + flag + '</td>'
            stock_html += '<td style="font-size:11px;color:#8b949e">' + dev_ + '</td>'
            stock_html += '<td style="font-size:11px;color:' + cl_h + '">' + aft_ + '</td></tr>\n'
        stock_html += '</table>\n'
    
    stock_acc_rate = stock_correct / stock_total * 100 if stock_total else 0
    
    prediction_html = '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:10px 0 4px">板块预测</h3>\n'
    prediction_html += '<table><tr><th>板块</th><th>盘前方向</th><th>概率</th><th>收盘涨跌</th><th>验证</th><th>偏差分析</th></tr>\n'
    prediction_html += pr_rows + '</table>\n'
    
    # ─── 综合预测准确率统计卡 ───
    stats_html = '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin:10px 0">'
    stats_html += '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:0 0 8px">🎯 综合预测准确率</h3>\n'
    # 综合
    total_correct = stock_correct
    total_all = stock_total
    stats_html += '<p style="font-size:14px;font-weight:700;margin:0 0 8px">'
    stats_html += '综合准确率 <span style="color:#f0f6fc">' + str(total_correct) + '/' + str(total_all) + '</span> = <span style="color:#d9a52e">' + ('%.0f%%' % (total_correct/total_all*100 if total_all else 0)) + '</span>'
    stats_html += '</p>\n'
    # 按评级
    stats_html += '<table style="margin-bottom:6px;width:100%"><colgroup><col style="width:35%"><col style="width:40%"><col style="width:25%"></colgroup><tr><th>评级</th><th style="text-align:center">正确/总数</th><th style="text-align:right">准确率</th></tr>\n'
    for rk, (rc, rt) in rating_stats.items():
        rp = rc / rt * 100 if rt else 0
        rcls = '#f85149' if rp >= 70 else ('#d9a52e' if rp >= 50 else '#3fb950')
        stats_html += '<tr><td>' + rk + '</td><td style="text-align:center">' + str(rc) + '/' + str(rt) + '</td><td style="text-align:right;color:' + rcls + '">' + ('%.0f%%' % rp) + '</td></tr>\n'
    stats_html += '</table>\n'
    # 按板块
    stats_html += '<table style="width:100%"><colgroup><col style="width:35%"><col style="width:40%"><col style="width:25%"></colgroup><tr><th>板块</th><th style="text-align:center">正确/总数</th><th style="text-align:right">准确率</th></tr>\n'
    for sec in sector_order:
        if sec not in sector_stats: continue
        sc, st = sector_stats[sec]
        sp_val = sc / st * 100 if st else 0
        scls = '#f85149' if sp_val >= 70 else ('#d9a52e' if sp_val >= 50 else '#3fb950')
        sd = sec_disp.get(sec, sec)
        stats_html += '<tr><td>' + sd + '</td><td style="text-align:center">' + str(sc) + '/' + str(st) + '</td><td style="text-align:right;color:' + scls + '">' + ('%.0f%%' % sp_val) + '</td></tr>\n'
    stats_html += '</table></div>\n'
    prediction_html += stats_html
    
    prediction_html += '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:12px 0 4px">个股预测验证</h3>\n'
    prediction_html += stock_html
    prediction_html += '<p style="margin-top:4px;font-size:11px;color:#8b949e">💡 板块准确率 '
    prediction_html += str(correct) + '/' + str(total_sec) + ' = ' + ('%.0f%%' % acc_rate)
    prediction_html += ' · 个股准确率 ' + str(stock_correct) + '/' + str(stock_total) + ' = ' + ('%.0f%%' % stock_acc_rate)
    prediction_html += ' · 大盘预判: ' + trend_pred + ' (' + str(prob) + '%概率)'
    prediction_html += '</p>\n'
except Exception as e:
    import traceback
    err_msg = traceback.format_exc().replace(chr(10), '<br>')
    prediction_html = '<p style="color:#8b949e">暂无预测验证数据。错误: ' + err_msg + '</p>\n'

# ──────────────────────────────────────────────
# 4. 持仓收盘明细 — 全部股票
# ──────────────────────────────────────────────
# 读取盘前和午间报告中实际打🔥标签的股票名单（取并集）
# 按板块分组+组内涨跌幅排序（保持板块固定顺序）
_sec_stocks_map = {}
for s in cache['rs_ranking']:
    sec = s.get('sector', '其他')
    _sec_stocks_map.setdefault(sec, []).append(s)
for sec in _sec_stocks_map:
    _sec_stocks_map[sec].sort(key=lambda x: x.get('stock_change_pct', 0), reverse=True)
# 按板块固定顺序展开
all_stocks = []
for sec in sector_order:
    all_stocks.extend(_sec_stocks_map.get(sec, []))


def _make_analysis(stock):
    chg = stock.get('stock_change_pct', 0)
    code = stock['code']
    mom_d = stock_mom.get(code, {})
    ts_sig = ts_lookup.get(code, {}).get('signals', {}) or {}
    if chg >= 9.5:
        analysis = '🔺涨停 强势突破·RS飙升'
    elif chg >= 5:
        analysis = '🔺强势大涨 再创新高'
    elif chg <= -9.5:
        analysis = '🟢接近跌停 板块最弱'
    elif chg <= -5:
        analysis = '🟢大幅弱于预期'
    elif chg > 0:
        analysis = '🔺小幅上涨'
    else:
        analysis = '🟢弱势持续'
    resist = mom_d.get('resistance_10d', '')
    support = mom_d.get('support_10d', '')
    if chg >= 9.5:
        action = f'⚪ 持有·设止盈{resist:.1f}' if resist else '⚪ 持有·涨停后注意高开低走'
    elif chg >= 5:
        action = f'🔴 持有·关注{resist:.1f}关口' if resist else '🔴 持有·继续观察'
    elif chg <= -9:
        action = f'🟢 止损·关注{support:.1f}支撑' if support else '🟢 止损'
    elif chg <= -5:
        action = f'🟢 减仓·关注{support:.1f}支撑' if support else '🟢 减仓'
    elif chg < 0:
        action = '🟢 建议减仓'
    else:
        action = '⚪ 持有等待'
    action_clr = '#d9a52e' if '⚪' in action else ('#f85149' if '🔴' in action else '#3fb950')
    return analysis, action, action_clr


def _price_str(code):
    sig = ts_lookup.get(code, {}).get('signals', {})
    c = sig.get('close', 0)
    return f'{c:.2f}' if c else '—'


up_holdings = len([s for s in all_stocks if s.get('stock_change_pct', 0) > 0])
dn_holdings = len([s for s in all_stocks if s.get('stock_change_pct', 0) < 0])

hr = ''
current_sec = None
for s in all_stocks:
    sec = s.get('sector', '')
    code = s['code']
    if sec != current_sec:
        current_sec = sec
        emoji = sector_emoji.get(sec, '📦')
        hr += (f'<tr style="background:#21262d">'
               f'<td colspan="6" style="font-size:11px;color:#f0f6fc;font-weight:600;padding:6px 10px;border-bottom:2px solid #30363d">'
               f'{emoji} {sec}</td></tr>\n')
    cl = 'up' if s.get('stock_change_pct', 0) > 0 else 'down'
    analysis, action, ac_clr = _make_analysis(s)
    p = _price_str(code)
    name_tag = s['name']
    _has_f = s['name'] in strong_stocks
    _has_m = s['name'] in focus_stock_set
    if _has_f and _has_m:
        name_tag = f'{s["name"]}&nbsp;<span class="tag-rec">\U0001f525</span>&nbsp;<span class="tag-focus">\U0001f4cc</span>'
    elif _has_f:
        name_tag = f'{s["name"]}&nbsp;<span class="tag-rec">\U0001f525</span>'
    elif _has_m:
        name_tag = f'{s["name"]}&nbsp;<span class="tag-focus">\U0001f4cc</span>'
    hr += (f'<tr><td>{name_tag}</td><td>{code}</td><td>{p}</td>'
           f'<td class="{cl}">{s.get("stock_change_pct", 0):+.2f}%</td>'
           f'<td style="font-size:11px">{analysis}</td>'
           f'<td style="font-size:11px;color:{ac_clr}">{action}</td></tr>\n')

holdings_html = (
    f'<p style="margin-bottom:6px">'
    f'<span class="tag tag-aplus">🔴 涨 {up_holdings} 只</span> '
    f'<span class="tag tag-d">🟢 跌 {dn_holdings} 只</span></p>'
    f'<table><tr><th>名称</th><th>代码</th><th>价格</th><th>涨跌幅</th><th>分析</th><th>明日操作建议</th></tr>'
    f'{hr}</table>\n'
)

# ──────────────────────────────────────────────
# 4. 技术面信号 — 按板块分组
# ──────────────────────────────────────────────

scored = sorted(cache['rs_ranking'], key=lambda x: x.get('rs_value', 0), reverse=True)
# 按板块分组排序
stocks_by_sec = {}
for s in scored:
    sec = s.get('sector', '其他')
    stocks_by_sec.setdefault(sec, []).append(s)

tr = ''
for sec in sector_order:
    sec_stocks = stocks_by_sec.get(sec, [])
    if not sec_stocks:
        continue
    emoji = sector_emoji.get(sec, '📦')
    tr += (f'<tr style="background:#21262d">'
           f'<td colspan="9" style="font-size:11px;color:#f0f6fc;font-weight:600;padding:6px 10px;border-bottom:2px solid #30363d">'
           f'{emoji} {sec}({len(sec_stocks)}只)</td></tr>\n')
    for s in sec_stocks:
        code, name = s['code'], s['name']
        ts_sig = ts_lookup.get(code, {}).get('signals', {})
        mo = stock_mom.get(code, {})
        close = ts_sig.get('close', 0)
        ma5 = ts_sig.get('ma5', 0)
        boll = ts_sig.get('bollinger', [])
        kdj = ts_sig.get('kdj', [])
        tl = mo.get('trend_label', '')
        ms = 80 if '强势' in tl else (60 if '偏强' in tl else (40 if '偏弱' in tl else 50))
        mom_color = '#f85149' if ms >= 80 else ('#d9a52e' if ms >= 60 else '#8b949e')
        name_tag = name
        _has_fs = name_tag in strong_stocks
        _has_ms = name_tag in focus_stock_set
        if _has_fs and _has_ms:
            name_tag = f'{name}&nbsp;<span class="tag-rec">\U0001f525</span>&nbsp;<span class="tag-focus">\U0001f4cc</span>'
        elif _has_fs:
            name_tag = f'{name}&nbsp;<span class="tag-rec">\U0001f525</span>'
        elif _has_ms:
            name_tag = f'{name}&nbsp;<span class="tag-focus">\U0001f4cc</span>'
        close_str = f'{close:.2f}' if close else '—'
        ma5_str = f'{ma5:.2f}' if ma5 else '—'
        mrd_pct = ((close - ma5) / ma5 * 100) if ma5 and ma5 > 0 else None
        mrd_str = f'{mrd_pct:+.1f}%' if mrd_pct is not None else '—'
        mrd_color = '#f85149' if (mrd_pct or 0) > 3 else ('#3fb950' if (mrd_pct or 0) < -3 else '#8b949e')
        bbw = '—'
        if len(boll) == 3 and boll[1] and boll[1] > 0:
            bbw = f'{(boll[0] - boll[2]) / boll[1] * 100:.1f}%'
        bp_desc = '—'
        if len(boll) == 3 and boll[0] != boll[2]:
            pct = (close - boll[2]) / (boll[0] - boll[2]) * 100
            if pct >= 100:
                bp_desc = f'{boll[0]:.1f}/{boll[2]:.1f}<br><span style="font-size:10px;color:#f85149">🔴 突破上轨</span>'
            elif pct <= 0:
                bp_desc = f'{boll[0]:.1f}/{boll[2]:.1f}<br><span style="font-size:10px;color:#3fb950">🟢 触及下轨</span>'
            else:
                bp_desc = (f'{boll[0]:.1f}/{boll[2]:.1f}'
                           f'<br><span style="font-size:10px;color:#8b949e">⚪ {"中轨上方" if pct >= 50 else "中轨下方"}</span>')
        kdj_str = '—'
        if len(kdj) >= 3 and kdj[0] and kdj[2]:
            k_val, j_val = kdj[0], kdj[2]
            kdj_str = f'{k_val:.0f}/{j_val:.0f}'
            if k_val > 80 or j_val > 80:
                kdj_str += f'<br><span style="font-size:10px;color:#f85149">🔴 超买</span>'
            elif k_val < 20 or j_val < 20:
                kdj_str += f'<br><span style="font-size:10px;color:#3fb950">🟢 超卖</span>'
            else:
                kdj_str += f'<br><span style="font-size:10px;color:#8b949e">⚪ 中性</span>'
        ma5_dir = '—'
        if close and ma5:
            diff_pct = (close - ma5) / ma5 * 100
            arrow = '🔴' if diff_pct > 0 else '🟢'
            arrow_cls = 'up' if diff_pct > 0 else 'down'
            ma5_dir = (f'<span class="{arrow_cls}">{arrow}</span> {ma5:.2f}'
                       f'<br><span style="font-size:10px;color:#8b949e">{"↑" if diff_pct>0 else "↓"}{diff_pct:+.1f}%</span>')
        if '强势' in tl:
            sg_text, sg_cls = '🔴 强势突破', 'tech-bullish'
        elif '偏弱' in tl or '弱势' in tl:
            sg_text, sg_cls = '🟢 弱势·观察', 'tech-bearish'
        else:
            sg_text, sg_cls = '⚪ 方向不明', 'tech-neutral'
        tech_name_tag = name_tag if 'name_tag' in dir() else name
        tr += (f'<tr><td><b>{tech_name_tag}</b><br><span style="color:#8b949e;font-size:10px">{code}</span></td>'
               f'<td style="font-weight:600">{close_str}</td>'
               f'<td style="font-size:11px;color:{mom_color}">{ms}</td>'
               f'<td style="font-size:11px;color:#8b949e">{bbw}</td>'
               f'<td style="font-size:11px;color:{mrd_color}">{mrd_str}</td>'
               f'<td style="font-size:11px">{ma5_dir}</td>'
               f'<td style="font-size:11px">{bp_desc}</td>'
               f'<td style="font-size:11px">{kdj_str}</td>'
               f'<td><span class="tech-signal {sg_cls}">{sg_text}</span></td></tr>\n')

placeholder_row = '<tr><td colspan="9" style="color:#8b949e;text-align:center">技术数据不足</td></tr>'
tech_html = f'<table><tr><th>标的</th><th>收盘</th><th>MOM</th><th>BBW</th><th>MRD</th><th>均线(MA5)</th><th>布林位置</th><th>KDJ(K/J)</th><th>技术判断</th></tr>{tr if tr else placeholder_row}</table>\n'

# ──────────────────────────────────────────────
# 5. 盘前预测准确率 — (已合并到模块3)
# ──────────────────────────────────────────────
# ──────────────────────────────────────────────
# 6. 多因子评分排名
# ──────────────────────────────────────────────
sm = sorted(multi_stocks.values(), key=lambda x: x.get('total_score', 0), reverse=True)


def _rating_color(score):
    if score >= 6:
        return '#f85149'
    elif score >= 5:
        return '#d9a52e'
    elif score >= 4:
        return '#58a6ff'
    else:
        return '#3fb950'


th = ''
for i, s in enumerate(sm[:5]):
    multi_name_tag = s['name']
    _has_f = s['name'] in strong_stocks
    _has_m = s['name'] in focus_stock_set
    if _has_f and _has_m:
        multi_name_tag = s['name'] + '&nbsp;<span class="tag-rec">\U0001f525</span>&nbsp;<span class="tag-focus">\U0001f4cc</span>'
    elif _has_f:
        multi_name_tag = s['name'] + '&nbsp;<span class="tag-rec">\U0001f525</span>'
    elif _has_m:
        multi_name_tag = s['name'] + '&nbsp;<span class="tag-focus">\U0001f4cc</span>'
    th += '<tr><td>' + str(i + 1) + '</td><td>' + multi_name_tag + '</td><td>' + s['code'] + '</td>'
    th += '<td style="color:' + _rating_color(s.get('total_score', 0)) + '">' + str(s.get('total_score', 0)) + '</td>'
    th += '<td>' + s.get('sector', '?') + '</td></tr>\n'
bh = ''.join(
    f'<tr><td>{i + 1}</td><td>{s["name"]}</td><td>{s["code"]}</td>'
    f'<td style="color:{_rating_color(s.get("total_score", 0))}">{s.get("total_score", 0)}</td>'
    f'<td>{s.get("sector", "?")}</td></tr>\n'
    for i, s in enumerate(sm[-5:][::-1]))
multi_html = (f'<p style="font-weight:600;color:#f85149;margin-bottom:4px">🏆 TOP5</p>'
              f'<table><tr><th>排名</th><th>名称</th><th>代码</th><th>评分</th><th>板块</th></tr>{th}</table>'
              f'<p style="font-weight:600;color:#3fb950;margin:8px 0 4px">💩 BOTTOM5</p>'
              f'<table><tr><th>排名</th><th>名称</th><th>代码</th><th>评分</th><th>板块</th></tr>{bh}</table>\n')

# ──────────────────────────────────────────────
# 7. 波动预警
# ──────────────────────────────────────────────
vol_rows = ''
for v in vol_alerts_list[:4]:
    cg = v.get('today_change', 0)
    name = v['name']
    cls = 'up' if cg > 0 else 'down'
    code = v.get('code', '')
    mom_d = stock_mom.get(code, {})
    resist = mom_d.get('resistance_10d', '')
    support = mom_d.get('support_10d', '')
    if cg > 9:
        sug = f'🔴 涨停持有，设止盈{resist:.1f}' if resist else '⚪ 涨停持有，注意高开低走'
    elif cg < -5:
        sug = f'🟢 关注{support:.1f}支撑，注意止损' if support else '🟢 弱势下行，注意风险'
    elif cg > 5:
        sug = f'🔴 强势上涨，关注{resist:.1f}压力' if resist else '🔴 强势上涨，继续持有'
    else:
        sug = '⚪ ' + (v.get('suggestion', '关注波动'))
    vol_name_tag = name
    _has_f = name in strong_stocks
    _has_m = name in focus_stock_set
    if _has_f and _has_m:
        vol_name_tag = name + '&nbsp;<span class="tag-rec">\U0001f525</span>&nbsp;<span class="tag-focus">\U0001f4cc</span>'
    elif _has_f:
        vol_name_tag = name + '&nbsp;<span class="tag-rec">\U0001f525</span>'
    elif _has_m:
        vol_name_tag = name + '&nbsp;<span class="tag-focus">\U0001f4cc</span>'
    vol_rows += (f'<tr><td>{vol_name_tag}</td><td class="{cls}">{cg:+.2f}%</td>'
                 f'<td style="font-size:11px;color:{"#f85149" if cls == "up" else "#3fb950"}">{sug}</td></tr>\n')
if not vol_rows:
    vol_rows = '<tr><td colspan="3" style="color:#8b949e">暂无异常波动预警。</td></tr>'
rh = f'<table><tr><th>股票</th><th>涨跌幅</th><th>预警</th></tr>\n{vol_rows}</table>\n'

# ──────────────────────────────────────────────
# 8. 今日总结 & 明日展望
# ──────────────────────────────────────────────
top3_stocks = sorted(cache['rs_ranking'], key=lambda x: x.get('stock_change_pct', 0), reverse=True)[:3]
pump_stocks = [s for s in cache['rs_ranking'] if s.get('stock_change_pct', 0) >= 9.5]

summary_parts = [f'{best_idx_name}{best_idx_val:+.2f}%领涨']
if up_holdings or dn_holdings:
    summary_parts.append(f'持仓涨🔴{up_holdings}只:跌🟢{dn_holdings}只')
if pump_stocks:
    pump_detail = '、'.join(f'{s["name"]}{s.get("stock_change_pct", 0):+.2f}%' for s in pump_stocks[:3])
    summary_parts.append(f'{sector_display.get(best_sec, best_sec)}爆发——{pump_detail}')
if worst_sec:
    summary_parts.append(f'{sector_display.get(worst_sec, worst_sec)}表现最弱')

idx_close_first = idx_conf[0][2]
sum_html = f'<p style="font-size:12px">📊 <b>今日总结</b>：{"，".join(summary_parts)}。</p>'
sum_html += '<p style="font-size:12px;margin-top:6px">🔮 <b>明日展望</b>：</p>'
sum_html += (f'<p style="font-size:12px;margin-left:12px">📌 <b>大盘</b>：上证{idx_close_first}微涨，关注4,100压力位。'
             f'{"短线有技术性修正需求。" if dn_count > up_count else "整体偏强。"}</p>')
sum_html += (f'<p style="font-size:12px;margin-left:12px">📌 <b>板块</b>：'
             f'{sector_display.get(best_sec, best_sec)}+通信电子双主线明确，可继续持有。'
             f'{sector_display.get(worst_sec, worst_sec)}持续弱势建议减仓。化工材料分化明显，去弱留强。</p>')
sum_html += ('<p style="font-size:12px;margin-left:12px">📌 <b>策略</b>：'
             '强势标的继续持有，涨停股设好止盈。弱势标的考虑减仓。整体仓位均衡，关注结构性轮动。</p>')

# ──────────────────────────────────────────────
# 填充模板
# ──────────────────────────────────────────────
with open('scripts/template-closing.html') as f:
    template = f.read()

today = date.today()
ds = today.strftime('%Y.%m.%d')
wd = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][today.weekday()]
result = template

replacements = [
    ('{{DATE}}', ds),
    ('{{WEEKDAY}}', wd),
    ('{{INDEX_METRICS}}', index_html),
    ('{{SECTOR_SCORING}}', sector_html),
    ('{{HOLDINGS_DETAIL}}', holdings_html),
    ('{{TECH_SIGNALS}}', tech_html),
    ('{{PREDICTION_ACCURACY}}', prediction_html),
    ('{{MULTI_FACTOR_RANKING}}', multi_html),
    ('{{SUMMARY_OUTLOOK}}', sum_html),
]
for k, v in replacements:
    result = result.replace(k, v)

# 今日要闻
news_parts = []
sec_news = {}
for s in cache['rs_ranking']:
    chg = s.get('stock_change_pct', 0)
    sec = s.get('sector', '')
    if abs(chg) >= 3:
        sec_news.setdefault(sec, []).append((s['name'], chg))
for sec in sector_order:
    items = sec_news.get(sec, [])
    if not items:
        continue
    items.sort(key=lambda x: abs(x[1]), reverse=True)
    detail = '、'.join(f'{n}{c:+.2f}%' for n, c in items[:4])
    emoji = sector_emoji.get(sec, '📊')
    avg_chg = sum(c for _, c in items) / len(items)
    if avg_chg > 5:
        tag = '集体爆发' if avg_chg > 8 else '走强'
    elif avg_chg < -5:
        tag = '集体走弱' if avg_chg < -8 else '偏弱'
    else:
        tag = '内部分化' if max(c for _, c in items) - min(c for _, c in items) > 10 else '震荡'
    sec_short = sec.replace('能源/公用事业', '能源').replace('AI/数字经济', 'AI数字')
    news_parts.append(f'<div style="background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 12px;font-size:12px;line-height:1.6">{emoji} <b>{sec_short}</b> {tag}——{detail}</div>')
news_parts.append(
    f'<p style="font-size:12px">📊 宏观 5月PMI 50.0，处于临界点。'
    f'四大指数{"全面收涨" if cg_all_pos else "涨跌互现"}，全市场涨跌比{ratio_str}</p>')
news_html = ('<div style="font-size:12px;line-height:1.8;display:flex;flex-direction:column;gap:6px">' + '\n'.join(news_parts) + '</div>'
             if news_parts else '<p style="font-size:12px;color:#8b949e">暂无重大要闻。</p>')
result = result.replace('{{TODAY_NEWS}}', news_html)
result = result.replace('{{VOLATILITY_ALERTS}}', rh)

# 风险提示
risk_items = []
for v in vol_alerts_list[:4]:
    cg = v.get('today_change', 0)
    name = v['name']
    if cg < -5:
        risk_items.append(f'<p style="font-size:12px">🟢 {name} {cg:+.2f}%接近跌停，注意止损</p>')
    elif cg < -3:
        risk_items.append(f'<p style="font-size:12px">🟢 {name} {cg:+.2f}%持续走弱，关注支撑</p>')
    elif cg > 9:
        risk_items.append(f'<p style="font-size:12px">🔴 {name} {cg:+.2f}%涨停后警惕明日高开低走，设好止盈</p>')
if not risk_items:
    risk_items.append('<p style="font-size:12px;color:#8b949e">暂无显著风险信号。</p>')
result = result.replace('{{RISK_WARNINGS}}', '\n'.join(risk_items))

date_id = today.strftime('%Y-%m-%d')
outpath = f'daily-report-html/daily-combined-{date_id}.html'

validate('closing', result, raise_on_error=True)
with open(outpath, 'w') as f:
    f.write(result)
print(f'✅ {outpath} ({len(result)} bytes)')
print('✅ 验证通过')
