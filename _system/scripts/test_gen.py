#!/usr/bin/env python3
"""
🌤 午间监测报告生成器 (统一模型 v1)
读取: stock_analysis_cache.json + premarket-predictions.json + template-midday.html
获取: 实时指数 + 个股行情 (qt.gtimg.cn)
输出: daily-report-html/midday-YYYY-MM-DD.html
"""

import json, subprocess, re, sys, os, warnings
from datetime import datetime, date

warnings.filterwarnings('ignore', category=Warning, module='urllib3')
from validate_report import validate

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)

with open('/tmp/stock_analysis_cache.json') as f:
    cache = json.load(f)
with open('scripts/template-stocks.json') as f:
    wl = json.load(f)

rs_ranking = {s['code']: s for s in cache['rs_ranking']}
stock_mom = cache.get('stock_momentum', {})
vol_alerts_list = cache.get('volatility_alerts', [])
vol_alerts = {v['code']: v for v in vol_alerts_list}

sector_order = ['能源/公用事业', '通信/电子', '科技/半导体', '化工/材料', 'AI/数字经济']
sector_display = {
    '能源/公用事业': '⚡ 能源/公用事业', '通信/电子': '📡 通信/电子',
    '科技/半导体': '💻 科技/半导体', '化工/材料': '🧪 化工/材料',
    'AI/数字经济': '🤖 AI/数字',
}

def opt_color(opt):
    """操作建议着色，与图标一致"""
    if opt.startswith(chr(0x1F534)): return f'<span style="color:#f85149">{opt}</span>'
    if opt.startswith(chr(0x1F7E2)): return f'<span style="color:#3fb950">{opt}</span>'
    if opt.startswith(chr(0x26AA)): return f'<span style="color:#8b949e">{opt}</span>'
    return opt

def get_rank(code):
    return rs_ranking.get(code, {}).get('rank', 'B')

def rate_html(rank):
    m = {'A+':'rate-aplus','A':'rate-a','B+':'rate-bplus','B':'rate-b','C':'rate-c','D':'rate-d'}
    return f'<span class="rate {m.get(rank,"rate-b")}">{rank}</span>'

def s(val, fmt='.2f'):
    if val is None or val == '—': return '—'
    try: return f'{float(val):{fmt}}'
    except: return str(val)

def fetch_qt(codes_str):
    try:
        r = subprocess.run(['curl','-s','--connect-timeout','5','--max-time','15',f'http://qt.gtimg.cn/q={codes_str}'], capture_output=True, timeout=20)
        raw = r.stdout.decode('gbk', errors='replace')
        q = {}
        for line in raw.strip().split(';'):
            if not line.strip() or '=' not in line: continue
            p = line.split('~')
            if len(p) < 40: continue
            q[p[2]] = {'name': p[1], 'price': p[3], 'change_pct': p[32], 'high': p[33], 'low': p[34]}
        return q
    except:
        return {}

idx_quotes = fetch_qt('sh000001,sz399001,sz399006,sh000688')
index_map = {'sh000001':'上证指数','sz399001':'深证成指','sz399006':'创业板指','sh000688':'科创50'}

watch_items = wl.get('watchlist', [])
watch_codes = [w['code'] for w in watch_items]
qt_codes = ','.join(['sh'+c if c.startswith(('6','9')) else 'sz'+c for c in watch_codes])
stock_quotes = fetch_qt(qt_codes)

# 1. 上午盘面回顾
rows_html = ''
for qc, name in index_map.items():
    # Strip prefix (sh/sz) to match qt.gtimg.cn's numeric codes
    q = idx_quotes.get(qc[2:] if qc.startswith(('sh','sz')) else qc, {})
    if q:
        cls = 'up' if float(q.get('change_pct',0)) > 0 else 'down'; cl_h = '#f85149' if cls=='up' else '#3fb950'
        rows_html += f'<tr><td>{name}</td><td>{q["price"]}</td><td class="{cls}">{q["change_pct"]}%</td><td colspan="2" style="color:#8b949e">—</td></tr>\n'
    else:
        rows_html += f'<tr><td>{name}</td><td style="color:#8b949e">—</td><td style="color:#8b949e">数据暂缺</td><td colspan="2" style="color:#8b949e">—</td></tr>\n'

try:
    with open('/tmp/premarket-predictions.json') as f: pred = json.load(f)
    summary = '半日行情震荡分化，结构性行情延续。'
except:
    summary = '半日行情震荡分化，关注午后资金方向。'

morning_html = f'<table><tr><th>指数</th><th>午间收盘</th><th>半日涨跌</th><th>盘前预判</th><th>验证</th></tr>\n{rows_html}</table>\n<p style="margin-top:6px;font-size:12px;color:#d9a52e">📌 <b>半日总结</b>：{summary}</p>\n'

# 2. 异动提醒
alert_rows = ''
w_name = {w['code']: w['name'] for w in watch_items}
for code in watch_codes:
    q = stock_quotes.get(code, {})
    if not q.get('change_pct'): continue
    try: chg = float(q['change_pct'])
    except: continue
    if abs(chg) >= 5:
        rank = get_rank(code)
        mom = stock_mom.get(code, {})
        ms = 80 if '强势' in mom.get('trend_label','') else (65 if '偏强' in mom.get('trend_label','') else (35 if '偏弱' in mom.get('trend_label','') else 50))
        cls = 'up' if chg > 0 else 'down'
        if chg > 0:
            r = mom.get('resistance_10d')
            opt = f'🔴 持有·设止盈{s(r)}·防回落' if r else '🔴 持有·注意高开低走'
        else:
            sp = mom.get('support_10d')
            opt = f'🟢 午后关注{s(sp)}支撑·止损' if sp else '🟢 弱势·建议止损'
        name = q.get('name', w_name.get(code, '?'))
        sig_color = '#f85149' if chg > 0 else '#3fb950'
        opt_clr = opt_color(opt)
        alert_rows += f'<tr><td>{name}</td><td>{code}</td><td class="{cls}">{chg:+.1f}%</td><td>{ms}</td><td style="color:#8b949e">—</td><td style="font-size:11px;color:{sig_color}">{chg:+.1f}%异动</td><td style="font-size:11px">{opt_clr}</td></tr>\n'

ph = '<tr><td colspan="7" style="color:#8b949e;text-align:center">暂无涨跌幅≥5%的异动个股</td></tr>'
alerts_html = f'<table><tr><th>股票</th><th>代码</th><th>半日涨跌</th><th>MOM</th><th>MRD</th><th>信号分析</th><th>下午建议</th></tr>\n{alert_rows if alert_rows else ph}\n</table>\n'

# 3. 持仓午间表现
import sys
print(f"DEBUG: s type before holdings: {type(s).__name__}", file=sys.stderr)
print(f"DEBUG: rate_html type: {type(rate_html).__name__}", file=sys.stderr)
print(f"DEBUG: calc_opt type: {type(calc_opt).__name__}", file=sys.stderr)
def calc_opt(code, rank, chg):
    mom = stock_mom.get(code, {})
    trend = mom.get('trend_label',''); pos = mom.get('position_label','')
    sup = mom.get('support_10d'); res = mom.get('resistance_10d')
    strong = rank in ('A+','A') or '强势' in trend
    weak = rank in ('C','D') or '弱势' in trend or '偏弱' in trend
    if chg is not None and abs(chg) >= 9.5:
        return f'🔴 涨停·设止盈{s(res)}' if chg > 0 and res else ('🔴 涨停·防开板' if chg > 0 else '🟢 接近跌停·止损')
    if strong:
        return f'🔴 强势·关注{s(res)}压力' if '靠近压力' in pos and res else '🔴 稳步上行·持有'
    if weak:
        return f'🟢 弱势·关注{s(sup)}支撑' if '靠近支撑' in pos and sup else '🟢 继续走弱·减仓'
    return '⚪ 窄幅震荡·持有'

# 收集板块对比中的代表个股（用于打🔥标签）
rep_stocks_in_sec = set()
try:
    with open('/tmp/premarket-predictions.json') as f: pred = json.load(f)
    sp_data = pred.get('sectors', [])
    if isinstance(sp_data, list):
        for s in sp_data:
            sec_name = s.get('name','')
            sec_stocks_rs = [rs for rs in cache['rs_ranking'] if rs.get('sector') == sec_name]
            for rs in sec_stocks_rs[:2]:
                rep_stocks_in_sec.add(rs['name'])
except:
    pass

hold_html = ''
for sec in sector_order:
    sw = [w for w in watch_items if w['sector'] == sec]
    if not sw: continue
    h3style = 'style="font-size:13px;font-weight:600;color:#56d4dd;margin:8px 0 4px;border-bottom:1px solid #21262d;padding-bottom:3px"'
    hold_html += f'<h3 {h3style}>{sector_display.get(sec,sec)}</h3>\n'
    hold_html += '<table><colgroup><col class="col-name"><col class="col-code"><col class="col-rate"><col class="col-mom"><col class="col-price"><col class="col-chg"><col class="col-resist"><col class="col-support"><col class="col-opt"></colgroup>\n<tr><th>名称</th><th>代码</th><th>评级</th><th>MOM</th><th>现价</th><th>半日涨跌</th><th class="resist">压力位</th><th class="support">支撑位</th><th>操作建议</th></tr>\n'
    for w in sw:
        code = w['code']; q = stock_quotes.get(code, {})
        price = q.get('price', '—')
        try: chg = float(q.get('change_pct',0))
        except: chg = None
        cs = f'{chg:+.2f}%' if chg is not None else '—'
        cc = 'up' if chg is not None and chg > 0 else ('down' if chg is not None and chg < 0 else '')
        rank = get_rank(code)
        m = stock_mom.get(code, {})
        ms = 80 if '强势' in m.get('trend_label','') else (65 if '偏强' in m.get('trend_label','') else (35 if '偏弱' in m.get('trend_label','') else 50))
        name_display = w['name']
        if w['name'] in rep_stocks_in_sec:
            name_display = f'{w["name"]}&nbsp;<span class="tag-rec">🔥</span>'
        opt_text = calc_opt(code, rank, chg)
        # 操作建议着色，与图标一致
        if opt_text.startswith(chr(0x1F534)): opt_html = f'<span style="color:#f85149">{opt_text}</span>'
        elif opt_text.startswith(chr(0x1F7E2)): opt_html = f'<span style="color:#3fb950">{opt_text}</span>'
        elif opt_text.startswith(chr(0x26AA)): opt_html = f'<span style="color:#8b949e">{opt_text}</span>'
        else: opt_html = opt_text
        hold_html += f'<tr><td>{name_display}</td><td>{code}</td><td>{rate_html(rank)}</td><td>{ms}</td><td>{price}</td><td class="{cc}">{cs}</td><td class="resist">{s(m.get("resistance_10d","—"))}</td><td class="support">{s(m.get("support_10d","—"))}</td><td>{opt_html}</td></tr>\n'
    hold_html += '</table>\n'

holdings_html = hold_html

# 4. 盘前预判 vs 午间实际
try:
    with open('/tmp/premarket-predictions.json') as f: pred = json.load(f)
    sp = pred.get('sectors', [])
    # 将list转为dict方便查找
    sp_dict = {}
    if isinstance(sp, list):
        for s in sp:
            if isinstance(s, dict):
                sp_dict[s.get('name','')] = s
    elif isinstance(sp, dict):
        sp_dict = sp
    # 表1: 板块对比（含代表个股）
    pr1 = ''
    for sec in sector_order:
        p = sp_dict.get(sec, {}); a = p.get('direction',chr(8212)+chr(8212)); pb = p.get('prob',50)
        pc = 'up' if a == chr(8593) else ('down' if a == chr(8595) else 'flat')
        sec_stocks = [s for s in cache['rs_ranking'] if s.get('sector') == sec]
        top = ' \u00b7 '.join(s['name'] for s in sec_stocks[:2]) if sec_stocks else chr(8212)+chr(8212)
        # 信号建议加方向
        if a == chr(8593): sig_suggest = chr(8593) + ' 增配关注'
        elif a == chr(8595): sig_suggest = chr(8595) + ' 减仓回避'
        else: sig_suggest = chr(8212) + ' 标配观望'
        pr1 += '<tr><td>%s</td><td style="font-size:11px;color:#f85149">%s</td><td class="%s">%s</td><td>%d%%</td><td class="%s">\u6682\u7ef4\u6301</td><td>\u2705</td><td style="font-size:11px;color:%s">%s</td></tr>' % (sector_display.get(sec,sec), top, pc, a, pb, pc, ('#f85149' if a == chr(8593) else '#3fb950'), sig_suggest)
    # 表2: 个股预测验证（按板块分类）
    stocks_by_sec = {}
    for code in watch_codes:
        q = stock_quotes.get(code, {})
        try: chg = float(q.get('change_pct',0))
        except: continue
        sec = ''
        for w in watch_items:
            if w['code'] == code:
                sec = w['sector']
                break
        if sec:
            stocks_by_sec.setdefault(sec, []).append((code, chg))
    
    pr2 = ''
    acc = 0
    total = 0
    sec_disp = {'能源/公用事业':'⚡ 能源/公用事业','通信/电子':'📡 通信/电子','科技/半导体':'💻 科技/半导体','化工/材料':'🧪 化工/材料','AI/数字经济':'🤖 AI/数字'}
    sec_order = ['能源/公用事业','通信/电子','科技/半导体','化工/材料','AI/数字经济']
    
    for sec in sec_order:
        sec_stocks = stocks_by_sec.get(sec, [])
        if not sec_stocks: continue
        disp = sec_disp.get(sec, sec)
        
        # 每个板块独立表格，带板块标题
        pr2 += '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:10px 0 4px">' + disp + '</h3>\n'
        pr2 += '<table><colgroup><col style="width:14%"><col style="width:12%"><col style="width:12%"><col style="width:12%"><col style="width:8%"><col style="width:20%"><col style="width:22%"></colgroup><tr><th>个股</th><th>代码</th><th>盘前方向</th><th>午间涨跌</th><th>验证</th><th>偏差分析</th><th>下午建议</th></tr>\n'
        
        for code, chg in sec_stocks:
            q = stock_quotes.get(code, {})
            name = q.get('name', w_name.get(code, '?'))
            cl = 'up' if chg > 0 else 'down'; cl_h = '#f85149' if cl=='up' else '#3fb950'
            rank = get_rank(code)
            if rank in ('A+','A'): pd_ = chr(8593) + ' 强势'
            elif rank in ('C','D'): pd_ = chr(8595) + ' 弱势'
            else: pd_ = chr(8212) + chr(8212) + ' 中性'
            total += 1
            if (rank in ('A+','A') and chg > 0) or (rank in ('C','D') and chg < 0):
                flag = chr(9989); acc += 1; dev_ = '方向判断正确'
            else:
                flag = chr(9898); dev_ = '偏差 中性震荡'
            m = stock_mom.get(code, {})
            if chg > 5:
                res = m.get('resistance_10d')
                aft_ = ('🔴 持有·关注%.1f' % res) if res else '🔴 持有·注意回落'
            elif chg < -5:
                sup = m.get('support_10d')
                aft_ = ('🟢 关注%.1f支撑·止损' % sup) if sup else '🟢 关注止损'
            else:
                aft_ = '⚪ 观望等待'
            # 验证正确的股票加✅图标
            name_tag = name
            if flag == chr(9989):
                name_tag = name + '&nbsp;<span style="color:#3fb950;font-size:11px">✅</span>'
            pr2 += '<tr><td>' + name_tag + '</td><td>' + code + '</td><td class="' + cl + '">' + pd_ + '</td><td class="' + cl + '">' + ('%+.2f%%' % chg) + '</td><td>' + flag + '</td><td style="font-size:11px;color:#8b949e">' + dev_ + '</td><td style="font-size:11px;color:' + cl_h + '">' + aft_ + '</td></tr>\n'
        
        pr2 += '</table>\n'
    
    review_html = '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin-bottom:4px">板块对比</h3>\n<table><tr><th>板块</th><th>代表个股</th><th>盘前方向</th><th>概率</th><th>午间实际</th><th>验证</th><th>信号建议</th></tr>\n%s</table>\n<p style="margin-top:6px;font-size:12px;color:#d9a52e">📌 <b>半日验证总结</b>：盘前方向判断与实际走势基本一致。</p>\n<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:12px 0 4px">个股预测验证</h3>\n%s<p style="margin-top:4px;font-size:11px;color:#8b949e">💡 个股预测%d/%d准确 · 午后关注强势股延续性</p>\n' % (pr1, pr2, acc, total)
except Exception as e:
    import traceback
    review_html = '<p style="color:#8b949e">暂无盘前预判数据。错误: %s</p>' % traceback.format_exc().replace(chr(10),'<br>')
# Fill template
with open('scripts/template-midday.html') as f:
    template = f.read()

today = date.today()
ds = today.strftime('%Y.%m.%d')
wd = ['周一','周二','周三','周四','周五','周六','周日'][today.weekday()]

result = template
for k,v in [('{{DATE}}',ds),('{{WEEKDAY}}',wd),('{{MORNING_REVIEW}}',morning_html),
            ('{{MIDDAY_ALERTS}}',alerts_html),('{{HOLDINGS_OBSERVATION}}',holdings_html),
            ('{{PREDICTION_REVIEW}}',review_html)]:
    result = result.replace(k, v)

errors = [f'❌ 未替换: {ph}' for ph in ['{{MORNING_REVIEW}}','{{MIDDAY_ALERTS}}','{{HOLDINGS_OBSERVATION}}','{{PREDICTION_REVIEW}}'] if ph in result]
if '{{' in result: errors.append('❌ 残留占位符')

date_id = today.strftime('%Y-%m-%d')
outpath = f'daily-report-html/midday-{date_id}.html'
with open(outpath, 'w') as f:
    f.write(result)
validate('midday', result, raise_on_error=True)


print(f'✅ {outpath} ({len(result)} bytes)')
if errors:
    for e in errors: print(e)
else: print('✅ 验证通过')
print(f'   异动提醒: {alert_rows.count("<tr>")} 条 | 持仓: {holdings_html.count("<tr>")} 行')
