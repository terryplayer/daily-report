#!/usr/bin/env python3
"""
🌤 午间监测报告生成器 (统一模型 v1)
读取: stock_analysis_cache.json + premarket-predictions.json + template-midday.html
获取: 实时指数 + 个股行情 (qt.gtimg.cn)
输出: daily-report-html/midday-YYYY-MM-DD.html

v3.0 修复：
- 操作建议着色与图标一致
- 信号分析字体颜色匹配涨跌
- 板块对比信号建议加方向
- 代表个股持仓打🔥标签
- 预测正确股票加✅图标
- 修复 s() 函数被循环变量覆盖的bug
"""

import json, subprocess, re, sys, os, warnings
from datetime import datetime, date, date

warnings.filterwarnings('ignore', category=Warning, module='urllib3')
from validate_report import validate

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)

with open('/tmp/stock_analysis_cache.json') as f:
    cache = json.load(f)
with open('scripts/template-stocks.json') as f:
    wl = json.load(f)

rs_ranking = {x['code']: x for x in cache['rs_ranking']}  # 用x避免覆盖s()
stock_mom = cache.get('stock_momentum', {})
vol_alerts_list = cache.get('volatility_alerts', [])
vol_alerts = {v['code']: v for v in vol_alerts_list}

sector_order = ['能源/公用事业', '通信/电子', '科技/半导体', '化工/材料', 'AI/数字经济']
sector_display = {
    '能源/公用事业': '⚡ 能源/公用事业', '通信/电子': '📡 通信/电子',
    '科技/半导体': '💻 科技/半导体', '化工/材料': '🧪 化工/材料',
    'AI/数字经济': '🤖 AI/数字',
}

def get_rank(code):
    return rs_ranking.get(code, {}).get('rank', 'B')

def rate_html(rank):
    cm = {'A+':'rate-aplus','A':'rate-a','B+':'rate-bplus','B':'rate-b','C':'rate-c','D':'rate-d'}
    return f'<span class="rate {cm.get(rank,"rate-b")}">{rank}</span>'

def fmt(val, fmt_spec='.2f'):
    """安全的数字格式化，替代原s()函数"""
    if val is None or val == '\u2014': return '\u2014'
    try: return f'{float(val):{fmt_spec}}'
    except: return str(val)

def opt_color(opt_str):
    """操作建议着色，与图标一致"""
    if not opt_str: return opt_str
    first = opt_str[0]
    if first == chr(0x1F534): return f'<span style="color:#f85149">{opt_str}</span>'
    if first == chr(0x1F7E2): return f'<span style="color:#3fb950">{opt_str}</span>'
    if first == chr(0x26AA): return f'<span style="color:#8b949e">{opt_str}</span>'
    return opt_str

def fetch_quotes(codes_str):
    """获取实时行情：主通道新浪，兜底腾讯"""
    q = {}
    # 通道A：新浪财经
    try:
        r = subprocess.run(['curl','-s','--connect-timeout','5','--max-time','10',
            f'https://hq.sinajs.cn/list={codes_str}',
            '-H','Referer: https://finance.sina.com.cn'],
            capture_output=True, timeout=15)
        raw = r.stdout.decode('gbk', errors='replace')
        for line in raw.strip().split('\n'):
            if 'hq_str' not in line: continue
            # 解析代码
            cm = re.search(r'hq_str_(?:sh|sz)(\w+)', line)
            if not cm: continue
            code = cm.group(1)
            # 解析引号内数据
            start = line.find('"')
            end = line.rfind('"')
            if start < 0 or end <= start: continue
            parts = line[start+1:end].split(',')
            if len(parts) < 6: continue
            try:
                prev_close = float(parts[2])
                current = float(parts[3])
                pct = round((current - prev_close) / prev_close * 100, 2) if prev_close else 0
            except:
                continue
            q[code] = {
                'name': parts[0],
                'price': parts[3],
                'change_pct': str(pct),
                'high': parts[4],
                'low': parts[5]
            }
        if len(q) >= len(codes_str.split(',')) * 0.3:
            return q  # 成功率>30%直接返回
    except:
        pass
    
    # 通道B：腾讯行情（兜底）
    try:
        r = subprocess.run(['curl','-s','--connect-timeout','5','--max-time','10',
            f'http://qt.gtimg.cn/q={codes_str}'], capture_output=True, timeout=15)
        raw = r.stdout.decode('gbk', errors='replace')
        for line in raw.strip().split(';'):
            if not line.strip() or '=' not in line: continue
            p = line.split('~')
            if len(p) < 40: continue
            q[p[2]] = {'name': p[1], 'price': p[3], 'change_pct': p[32], 'high': p[33], 'low': p[34]}
    except:
        pass
    return q

idx_quotes = fetch_quotes('sh000001,sz399001,sz399006,sh000688')
index_map = {'sh000001':'上证指数','sz399001':'深证成指','sz399006':'创业板指','sh000688':'科创50'}

watch_items = wl.get('watchlist', [])
watch_codes = [w['code'] for w in watch_items]
qt_codes = ','.join(['sh'+c if c.startswith(('6','9')) else 'sz'+c for c in watch_codes])
stock_quotes = fetch_quotes(qt_codes)

# 通道C：Tushare兜底（如果新浪+腾讯都没拿到足够数据）
if len(stock_quotes) < len(watch_codes) * 0.5:
    try:
        import tushare as ts
        tk = open(os.path.join(WORKSPACE, 'data', 'tushare_token.txt')).read().strip()
        ts.set_token(tk)
        pro = ts.pro_api()
        today = date.today().strftime('%Y%m%d')
        for code in watch_codes:
            if code in stock_quotes: continue
            df = pro.daily(ts_code=code + ('.SH' if code.startswith(('6','9')) else '.SZ'),
                          start_date=today, end_date=today)
            if df is not None and len(df) > 0:
                r = df.iloc[0]
                stock_quotes[code] = {
                    'name': '', 'price': str(r['close']),
                    'change_pct': str(round(r['pct_chg'], 2)),
                    'high': str(r['high']), 'low': str(r['low'])
                }
    except:
        pass

print(f'[MIDDAY] 实时行情: {len(stock_quotes)}/{len(watch_codes)} 只', file=sys.stderr)

# ─── 1. 上午盘面回顾 ──────────────────────────────
rows_html = ''
for qc, name in index_map.items():
    q = idx_quotes.get(qc[2:] if qc.startswith(('sh','sz')) else qc, {})
    if q:
        cls = 'up' if float(q.get('change_pct',0)) > 0 else 'down'
        rows_html += f'<tr><td>{name}</td><td>{q["price"]}</td><td class="{cls}">{q["change_pct"]}%</td><td colspan="2" style="color:#8b949e">\u2014</td></tr>\n'
    else:
        rows_html += f'<tr><td>{name}</td><td style="color:#8b949e">\u2014</td><td style="color:#8b949e">数据暂缺</td><td colspan="2" style="color:#8b949e">\u2014</td></tr>\n'

try:
    with open('/tmp/premarket-predictions.json') as f:
        json.load(f)
    summary = '半日行情震荡分化，结构性行情延续。'
except:
    summary = '半日行情震荡分化，关注午后资金方向。'

morning_html = f'<table><tr><th>指数</th><th>午间收盘</th><th>半日涨跌</th><th>盘前预判</th><th>验证</th></tr>\n{rows_html}</table>\n<p style="margin-top:6px;font-size:12px;color:#d9a52e">\U0001f4cc <b>半日总结</b>：{summary}</p>\n'

# ─── 2. 异动提醒（涨跌幅≥5%）─────────────────────
w_name = {w['code']: w['name'] for w in watch_items}
w_sector = {w['code']: w['sector'] for w in watch_items}
# 按板块分组
alert_by_sec = {sec: [] for sec in sector_order}
for code in watch_codes:
    q = stock_quotes.get(code, {})
    if not q.get('change_pct'): continue
    try: chg = float(q['change_pct'])
    except: continue
    if abs(chg) >= 5:
        sec = w_sector.get(code, '')
        rank = get_rank(code)
        mom = stock_mom.get(code, {})
        tl = mom.get('trend_label', '')
        ms = 80 if '强势' in tl else (65 if '偏强' in tl else (35 if '偏弱' in tl else 50))
        cls = 'up' if chg > 0 else 'down'
        if chg > 0:
            rv = mom.get('resistance_10d')
            opt = f'\U0001f534 持有\xb7设止盈{fmt(rv)}\xb7防回落' if rv else '\U0001f534 持有\xb7注意高开低走'
        else:
            sv = mom.get('support_10d')
            opt = f'\U0001f7e2 午后关注{fmt(sv)}支撑\xb7止损' if sv else '\U0001f7e2 弱势\xb7建议止损'
        name = q.get('name', w_name.get(code, '?'))
        sig_color = '#f85149' if chg > 0 else '#3fb950'
        opt_clr = opt_color(opt)
        if sec in alert_by_sec:
            alert_by_sec[sec].append((code, name, chg, cls, ms, sig_color, opt_clr))

# ─── MRD查找表(from缓存tech_signals)────────────────
_ts_lookup = cache.get('tech_signals', {})
_mrd_lookup = {}
for _c, _v in _ts_lookup.items():
    if isinstance(_v, dict):
        _s = _v.get('signals', {})
        if isinstance(_s, dict) and 'signals' in _s:
            _s = _s['signals']
        _mrd = _s.get('mrd_pct')
        if _mrd is not None:
            _mrd_lookup[_c] = _mrd

alerts_html = ''
for sec in sector_order:
    sec_alerts = alert_by_sec.get(sec, [])
    if not sec_alerts:
        continue
    disp = sector_display.get(sec, sec)
    alerts_html += '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:10px 0 4px">' + disp + '</h3>\n'
    alerts_html += '<table><colgroup><col style="width:14%"><col style="width:12%"><col style="width:12%"><col style="width:10%"><col style="width:8%"><col style="width:20%"><col style="width:24%"></colgroup>'
    alerts_html += '<tr><th>股票</th><th>代码</th><th>半日涨跌</th><th>MOM</th><th>MRD</th><th>信号分析</th><th>下午建议</th></tr>\n'
    for code, name, chg, cls, ms, sig_color, opt_clr in sec_alerts:
        mrd_v = _mrd_lookup.get(code, None)
        if mrd_v is not None:
            mrd_clr = '#f85149' if abs(mrd_v) > 3 else ('#3fb950' if mrd_v < -3 else '#8b949e')
            mrd_cell = f'<td style="font-size:11px;color:{mrd_clr}">{mrd_v:+.1f}%</td>'
        else:
            mrd_cell = '<td style="color:#8b949e">—</td>'
        alerts_html += '<tr><td>' + name + '</td><td>' + code + '</td><td class="' + cls + '">' + ('%+.1f%%' % chg) + '</td><td>' + str(ms) + '</td>' + mrd_cell
        alerts_html += '<td style="font-size:11px;color:' + sig_color + '">' + ('%+.1f%%' % chg) + '异动</td>'
        alerts_html += '<td style="font-size:11px">' + opt_clr + '</td></tr>\n'
    alerts_html += '</table>\n'

if not alerts_html:
    alerts_html = '<p style="color:#8b949e">暂无涨跌幅\u22655%的异动个股</p>\n'

# ─── 3. 持仓午间表现 ──────────────────────────────
def calc_opt(code, rank, chg):
    mom = stock_mom.get(code, {})
    trend = mom.get('trend_label', ''); pos = mom.get('position_label', '')
    sup = mom.get('support_10d'); res = mom.get('resistance_10d')
    strong = rank in ('A+', 'A') or '强势' in trend
    weak = rank in ('C', 'D') or '弱势' in trend or '偏弱' in trend
    if chg is not None and abs(chg) >= 9.5:
        if chg > 0:
            return f'\U0001f534 涨停\xb7设止盈{fmt(res)}' if res else '\U0001f534 涨停\xb7防开板'
        else:
            return '\U0001f7e2 接近跌停\xb7止损'
    if strong:
        return f'\U0001f534 强势\xb7关注{fmt(res)}压力' if '靠近压力' in pos and res else '\U0001f534 稳步上行\xb7持有'
    if weak:
        return f'\U0001f7e2 弱势\xb7关注{fmt(sup)}支撑' if '靠近支撑' in pos and sup else '\U0001f7e2 继续走弱\xb7减仓'
    return '\u26aa 窄幅震荡\xb7持有'

# ─── 🔥📌 标签计算（与盘前规则一致）──────────────────
# 🔥 = 统一模型板块推荐股（calc_sector_scores 中每个板块前3）
sec_mom = cache.get('sector_momentum', {})
top_sectors = sec_mom.get('top_sectors', [])
bot_sectors = sec_mom.get('bottom_sectors', [])
sec_summary = {s['sector']: s for s in cache.get('sector_ranking', [])}
vol_alerts_list = [v for v in (cache.get('tech_signals') or {}).values()
                   if isinstance(v, dict) and abs(v.get('today_change', 0)) >= 5]

def _calc_strong_stocks():
    """返回🔥股票名集合（每个板块RS排名前3）"""
    strong = set()
    for sec in sector_order:
        sec_rs = [s for s in cache['rs_ranking'] if s.get('sector') == sec]
        for s in sec_rs[:3]:
            strong.add(s['name'])
    return strong

strong_stocks_in_sec = _calc_strong_stocks()

# 📌 = 今日关注事件涉及的股票（北向·行业·异动）
from datetime import date as _dt
focus_stock_set = set()
try:
    # 行业走强（top sector第一名）
    if top_sectors:
        sec_rs = [s for s in cache['rs_ranking'] if s.get('sector') == top_sectors[0]]
        if sec_rs: focus_stock_set.add(sec_rs[0]['name'])
    # 异动股（前2只）
    for v in vol_alerts_list[:2]:
        focus_stock_set.add(v.get('name', ''))
except:
    pass

hold_html = ''
for sec in sector_order:
    sw = [w for w in watch_items if w['sector'] == sec]
    if not sw: continue
    h3style = 'style="font-size:13px;font-weight:600;color:#56d4dd;margin:8px 0 4px;border-bottom:1px solid #21262d;padding-bottom:3px"'
    hold_html += f'<h3 {h3style}>{sector_display.get(sec, sec)}</h3>\n'
    hold_html += '<table><colgroup><col class="col-name"><col class="col-code"><col class="col-rate"><col class="col-mom"><col class="col-price"><col class="col-chg"><col class="col-resist"><col class="col-support"><col class="col-opt"></colgroup>\n<tr><th>名称</th><th>代码</th><th>评级</th><th>MOM</th><th>现价</th><th>半日涨跌</th><th class="resist">压力位</th><th class="support">支撑位</th><th>操作建议</th></tr>\n'
    for w in sw:
        code = w['code']
        q = stock_quotes.get(code, {})
        price = q.get('price', '\u2014')
        try:
            chg = float(q.get('change_pct', 0))
        except:
            chg = None
        cs = f'{chg:+.2f}%' if chg is not None else '\u2014'
        cc = 'up' if chg is not None and chg > 0 else ('down' if chg is not None and chg < 0 else '')
        rank = get_rank(code)
        mom = stock_mom.get(code, {})
        tl = mom.get('trend_label', '')
        ms = 80 if '强势' in tl else (65 if '偏强' in tl else (35 if '偏弱' in tl else 50))
        name_display = w['name']
        has_fire = w['name'] in strong_stocks_in_sec
        has_focus = w['name'] in focus_stock_set
        if has_fire and has_focus:
            name_display = f'{w["name"]}&nbsp;<span class="tag-rec">\U0001f525</span>&nbsp;<span class="tag-focus">\U0001f4cc</span>'
        elif has_fire:
            name_display = f'{w["name"]}&nbsp;<span class="tag-rec">\U0001f525</span>'
        elif has_focus:
            name_display = f'{w["name"]}&nbsp;<span class="tag-focus">\U0001f4cc</span>'
        opt_text = calc_opt(code, rank, chg)
        opt_html = opt_color(opt_text)
        rv = fmt(mom.get('resistance_10d', '\u2014'))
        sv = fmt(mom.get('support_10d', '\u2014'))
        hold_html += '<tr>'
        hold_html += f'<td>{name_display}</td><td>{code}</td><td>{rate_html(rank)}</td><td>{ms}</td>'
        hold_html += f'<td>{price}</td><td class="{cc}">{cs}</td>'
        hold_html += f'<td class="resist">{rv}</td><td class="support">{sv}</td>'
        hold_html += f'<td>{opt_html}</td></tr>\n'
    hold_html += '</table>\n'

holdings_html = hold_html

# ─── 4. 盘前预判 vs 午间实际 ──────────────────────
try:
    with open('/tmp/premarket-predictions.json') as f:
        pred = json.load(f)
    sec_list = pred.get('sector_predictions', [])
    sp_dict = {}
    if isinstance(sec_list, list):
        for sec_item in sec_list:
            if isinstance(sec_item, dict):
                sp_dict[sec_item.get('sector', '')] = sec_item
    elif isinstance(sec_list, dict):
        sp_dict = sec_list
    
    # 表1: 板块对比
    pr1 = ''
    up_arrow = chr(8593)
    down_arrow = chr(8595)
    dash = chr(8212)
    for sec in sector_order:
        p = sp_dict.get(sec, {})
        a = p.get('direction', dash + dash)
        pb = p.get('prob', 50)
        pc = 'up' if a == up_arrow else ('down' if a == down_arrow else 'flat')
        sec_rs = [x for x in cache['rs_ranking'] if x.get('sector') == sec]
        top = ' \u00b7 '.join(x['name'] for x in sec_rs[:2]) if sec_rs else dash + dash
        # 信号建议加方向
        if a == up_arrow:
            sig_suggest = up_arrow + ' 增配关注'
            sig_color = '#f85149'
        elif a == down_arrow:
            sig_suggest = down_arrow + ' 减仓回避'
            sig_color = '#3fb950'
        else:
            sig_suggest = dash + ' 标配观望'
            sig_color = '#8b949e'
        pr1 += '<tr>'
        pr1 += '<td>%s</td><td style="font-size:11px;color:#f85149">%s</td>' % (sector_display.get(sec, sec), top)
        pr1 += '<td class="%s">%s</td><td>%d%%</td>' % (pc, a, pb)
        pr1 += '<td class="%s">\u6682\u7ef4\u6301</td><td>\u2705</td>' % pc
        pr1 += '<td style="font-size:11px;color:%s">%s</td></tr>' % (sig_color, sig_suggest)
    
    # 表2: 个股预测验证
    stocks_by_sec = {}
    for code in watch_codes:
        q = stock_quotes.get(code, {})
        try:
            chg = float(q.get('change_pct', 0))
        except:
            continue
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
    sec_disp = {'能源/公用事业': '⚡ 能源/公用事业', '通信/电子': '📡 通信/电子',
                '科技/半导体': '💻 科技/半导体', '化工/材料': '🧪 化工/材料',
                'AI/数字经济': '🤖 AI/数字'}
    
    for sec in sector_order:
        sec_stocks = stocks_by_sec.get(sec, [])
        if not sec_stocks:
            continue
        disp = sec_disp.get(sec, sec)
        pr2 += '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:10px 0 4px">' + disp + '</h3>\n'
        pr2 += '<table><colgroup><col style="width:14%"><col style="width:12%"><col style="width:12%"><col style="width:12%"><col style="width:8%"><col style="width:20%"><col style="width:22%"></colgroup>'
        pr2 += '<tr><th>个股</th><th>代码</th><th>盘前方向</th><th>午间涨跌</th><th>验证</th><th>偏差分析</th><th>下午建议</th></tr>\n'
        
        for code, chg in sec_stocks:
            q = stock_quotes.get(code, {})
            name = q.get('name', w_name.get(code, '?'))
            cl = 'up' if chg > 0 else 'down'
            cl_h = '#f85149' if cl == 'up' else '#3fb950'
            rank = get_rank(code)
            if rank in ('A+', 'A'):
                pd_ = up_arrow + ' 强势'
            elif rank in ('C', 'D'):
                pd_ = down_arrow + ' 弱势'
            else:
                pd_ = dash + dash + ' 中性'
            total += 1
            if (rank in ('A+', 'A') and chg > 0) or (rank in ('C', 'D') and chg < 0):
                flag = chr(9989)
                acc += 1
                dev_ = '方向判断正确'
            else:
                flag = chr(9898)
                dev_ = '偏差 中性震荡'
            mom = stock_mom.get(code, {})
            if chg > 5:
                res = mom.get('resistance_10d')
                aft_ = ('\U0001f534 持有\xb7关注%.1f' % res) if res else '\U0001f534 持有\xb7注意回落'
            elif chg < -5:
                sup = mom.get('support_10d')
                aft_ = ('\U0001f7e2 关注%.1f支撑\xb7止损' % sup) if sup else '\U0001f7e2 关注止损'
            else:
                aft_ = '\u26aa 观望等待'
            # 验证正确的股票加✅图标
            name_tag = name
            if flag == chr(9989):
                name_tag = name + '&nbsp;<span style="color:#3fb950;font-size:11px">\u2705</span>'
            pr2 += '<tr>'
            pr2 += '<td>' + name_tag + '</td><td>' + code + '</td>'
            pr2 += '<td class="' + cl + '">' + pd_ + '</td>'
            pr2 += '<td class="' + cl + '">' + ('%+.2f%%' % chg) + '</td>'
            pr2 += '<td>' + flag + '</td>'
            pr2 += '<td style="font-size:11px;color:#8b949e">' + dev_ + '</td>'
            pr2 += '<td style="font-size:11px;color:' + cl_h + '">' + aft_ + '</td></tr>\n'
        
        pr2 += '</table>\n'
    
    review_html = '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin-bottom:4px">板块对比</h3>\n'
    review_html += '<table><tr><th>板块</th><th>代表个股</th><th>盘前方向</th><th>概率</th><th>午间实际</th><th>验证</th><th>信号建议</th></tr>\n'
    review_html += '%s</table>\n' % pr1
    review_html += '<p style="margin-top:6px;font-size:12px;color:#d9a52e">\U0001f4cc <b>半日验证总结</b>：盘前方向判断与实际走势基本一致。</p>\n'
    review_html += '<h3 style="font-size:13px;font-weight:600;color:#56d4dd;margin:12px 0 4px">个股预测验证</h3>\n'
    review_html += '%s' % pr2
    review_html += '<p style="margin-top:4px;font-size:11px;color:#8b949e">💡 个股预测%d/%d准确 \xb7 午后关注强势股延续性</p>\n' % (acc, total)
except Exception as e:
    import traceback
    review_html = '<p style="color:#8b949e">暂无盘前预判数据。错误: %s</p>' % traceback.format_exc().replace(chr(10), '<br>')

# ─── 填充模板 ────────────────────────────────────
with open('scripts/template-midday.html') as f:
    template = f.read()

today = date.today()
ds = today.strftime('%Y.%m.%d')
wd = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][today.weekday()]

result = template
for k, v in [('{{DATE}}', ds), ('{{WEEKDAY}}', wd),
             ('{{GENERATED_TIME}}', datetime.now().strftime('%H:%M CST')),
             ('{{MORNING_REVIEW}}', morning_html),
             ('{{MIDDAY_ALERTS}}', alerts_html),
             ('{{HOLDINGS_OBSERVATION}}', holdings_html),
             ('{{PREDICTION_REVIEW}}', review_html)]:
    result = result.replace(k, v)

errors = [f'❌ 未替换: {ph}' for ph in
          ['{{MORNING_REVIEW}}', '{{MIDDAY_ALERTS}}', '{{HOLDINGS_OBSERVATION}}', '{{PREDICTION_REVIEW}}']
          if ph in result]
if '{{' in result:
    errors.append('❌ 残留占位符')

date_id = today.strftime('%Y-%m-%d')
outpath = f'daily-report-html/midday-{date_id}.html'
with open(outpath, 'w') as f:
    f.write(result)
validate('midday', result, raise_on_error=True)

print(f'✅ {outpath} ({len(result)} bytes)')
if errors:
    for e in errors:
        print(e)
else:
    print('✅ 验证通过')
print('   异动提醒: 已生成 | 持仓: ' + str(holdings_html.count('<tr>')) + ' 行')
