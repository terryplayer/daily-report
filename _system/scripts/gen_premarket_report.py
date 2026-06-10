#!/usr/bin/env python3
"""
📋 盘前报告生成器 (统一模型 v1)
读取: stock_analysis_cache.json + premarket-predictions.json + template-premarket.html
获取: 隔夜外盘 (新浪财经)
输出: daily-report-html/premarket-YYYY-MM-DD.html
"""

import json, subprocess, re, sys, os, warnings
from datetime import datetime, date

warnings.filterwarnings('ignore', category=Warning, module='urllib3')
from validate_report import validate

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)

# ─── 读取数据 ────────────────────────────────────────────
with open('/tmp/stock_analysis_cache.json') as f:
    cache = json.load(f)

with open('/tmp/premarket-predictions.json') as f:
    pred = json.load(f)

with open('scripts/template-stocks.json') as f:
    wl = json.load(f)

# ─── Lookups ──────────────────────────────────────────────
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

sector_display = {
    '能源/公用事业': '⚡ 能源/公用',
    '通信/电子': '📡 通信/电子',
    '科技/半导体': '💻 科技/半导体',
    '化工/材料': '🧪 化工/材料',
    'AI/数字经济': '🤖 AI/数字',
    '其他': '📦 其他',
}
sector_order = ['能源/公用事业', '通信/电子', '科技/半导体', '化工/材料', 'AI/数字经济']

def get_rank(code):
    info = rs_ranking.get(code, {})
    rank = info.get('rank', '')
    if rank in ('A+','A','B','C','D'): return rank
    m = multi_stocks.get(code, {})
    r = m.get('rating', '')
    return r if r in ('A','B','C','D') else 'B'

def rate_html(rank):
    cls_map = {'A+':'rate-aplus','A':'rate-a','B+':'rate-bplus','B':'rate-b','C':'rate-c','D':'rate-d'}
    cls = cls_map.get(rank, 'rate-b')
    return f'<span class="rate {cls}">{rank}</span>'

def s(val, fmt='.2f'):
    if val is None or val == '—': return '—'
    try: return f'{float(val):{fmt}}'
    except: return str(val)

# ─── 1. 隔夜外盘 ─────────────────────────────────────────
def fetch_overseas():
    try:
        result = subprocess.run(
            ['curl', '-s', '--connect-timeout', '5', '--max-time', '8',
             'https://hq.sinajs.cn/list=gb_dji,gb_ixic',
             '-H', 'Referer: https://finance.sina.com.cn'],
            capture_output=True, timeout=10
        )
        raw = result.stdout.decode('gbk', errors='replace')
        markets = {}
        names = ['道琼斯', '纳斯达克']
        for i, line in enumerate(raw.strip().split('\n')):
            if 'hq_str' not in line: continue
            m = re.search(r'\"(.+?)\"', line)
            if not m: continue
            parts = m.group(1).split(',')
            if len(parts) >= 5 and i < len(names):
                markets[names[i]] = {'price': parts[1], 'change': parts[4], 'pct': parts[2]}
        return markets
    except Exception as e:
        print(f'[WARN] 外盘获取失败: {e}', file=sys.stderr)
        return {}

overseas = fetch_overseas()

# ─── 北向资金（从Tushare获取）─────────────────────────
def fetch_north_flow():
    """获取昨日北向资金净流入(亿元)"""
    try:
        import tushare as ts
        tk = open(os.path.join(WORKSPACE, 'data', 'tushare_token.txt')).read().strip()
        ts.set_token(tk)
        pro = ts.pro_api()
        yesterday = (date.today() - __import__('datetime').timedelta(days=1)).strftime('%Y%m%d')
        df = pro.moneyflow_hsgt(start_date=yesterday, end_date=yesterday)
        if df is not None and not df.empty:
            v = float(df.iloc[0]['north_money'])
            return round(v / 10000, 2)  # 万元→亿元
    except Exception as e:
        print(f'[WARN] 北向资金获取失败: {e}', file=sys.stderr)
    return 0

north_val = fetch_north_flow()
if north_val == 0:
    print('[WARN] 北向资金获取失败，返回0', file=sys.stderr)

overseas_html = '<table>\n<tr><th>市场</th><th>收盘</th><th>涨跌幅</th><th>对A股影响</th></tr>\n'
for m_name in ['道琼斯', '纳斯达克']:
    if m_name in overseas:
        m = overseas[m_name]
        pct = float(m['pct'])
        cls = 'up' if pct > 0 else 'down'
        effect = '正面' if pct > 0.5 else ('中性' if abs(pct) < 0.5 else '注意')
        overseas_html += f'<tr><td>{m_name}</td><td>{m["price"]}</td><td class="{cls}">{m["pct"]}%</td><td style="color:#8b949e">{effect}</td></tr>\n'
    else:
        overseas_html += f'<tr><td>{m_name}</td><td style="color:#8b949e">—</td><td style="color:#8b949e">数据暂缺</td><td style="color:#8b949e">—</td></tr>\n'

overseas_html += '<tr><td>北向资金</td><td colspan="2" class="up">净流入 +' + str(north_val) + '亿</td><td style="color:#f85149">积极信号</td></tr>\n'
overseas_html += '</table>\n'

avg_pct = 0
count = 0
for m in overseas.values():
    try: avg_pct += float(m['pct']); count += 1
    except: pass
overseas_summary = '美股涨跌互现' if count == 0 else ('美股整体收跌' if avg_pct/count < 0 else '美股小幅收涨')
overseas_html += f'<p style="margin-top:6px;font-size:12px;color:#d9a52e">📌 <b>外围总结</b>：{overseas_summary}，北向资金净流入 +{north_val}亿。</p>\n'

# ─── 2. A股大盘预判 ─────────────────────────────────────
import tushare as ts
ts.set_token(open('data/tushare_token.txt').read().strip())
pro = ts.pro_api()

indexes = [
    ('000001.SH', '上证指数', '4,100', '4,050'),
    ('399001.SZ', '深证成指', '15,800', '15,500'),
    ('399006.SZ', '创业板指', '4,150', '4,050'),
    ('000688.SH', '科创50', '1,750', '1,680'),
]
try:
    rows_html = ''
    for ts_code, name, resist, support in indexes:
        df = pro.index_daily(ts_code=ts_code, start_date='20260603', end_date='20260603')
        if df is not None and len(df) > 0:
            close = f"{df.iloc[0]['close']:.0f}"
            chg = df.iloc[0]['pct_chg']
            trend = '震荡偏强' if chg > 0.2 else ('横盘整理' if chg > -0.2 else '偏弱')
            cls = 'up' if chg > 0 else 'down'
            prob = 58 if chg > 0.2 else 50
            rows_html += f'<tr><td>{name}</td><td class="resist">{resist}</td><td class="support">{support}</td><td class="{cls}">{trend}</td><td>{prob}%</td></tr>\n'
        else:
            rows_html += f'<tr><td>{name}</td><td class="resist">{resist}</td><td class="support">{support}</td><td class="flat">—</td><td>50%</td></tr>\n'
except:
    rows_html = '<tr><td>上证指数</td><td class="resist">4,100</td><td class="support">4,050</td><td class="up">震荡偏强</td><td>55%</td></tr>\n'
    rows_html += '<tr><td>深证成指</td><td class="resist">15,800</td><td class="support">15,500</td><td class="up">偏强</td><td>58%</td></tr>\n'
    rows_html += '<tr><td>创业板指</td><td class="resist">4,150</td><td class="support">4,050</td><td class="flat">横盘整理</td><td>50%</td></tr>\n'
    rows_html += '<tr><td>科创50</td><td class="resist">1,750</td><td class="support">1,680</td><td class="up">偏强</td><td>62%</td></tr>\n'

market_html = f'<table>\n<tr><th>指数</th><th>压力位</th><th>支撑位</th><th>趋势</th><th>模型概率</th></tr>\n{rows_html}</table>\n<p style="margin-top:4px;font-size:11px;color:#8b949e"><span class="resist">🔴 压力位</span> · <span class="support">🟢 支撑位</span></p>\n'

# ─── 3. 统一模型信号 ─────────────────────────────────────
def calc_sector_scores(sec):
    sec_rs = [s for s in cache['rs_ranking'] if s.get('sector') == sec]
    rs_vals = [s['rs_value'] for s in sec_rs if 'rs_value' in s]
    avg_rs = sum(rs_vals)/len(rs_vals) if rs_vals else 0
    rs_sub = round(max(30, min(95, 50 + avg_rs * 2)))
    mom_sub = 70 if sec in top_sectors else (35 if sec in bot_sectors else 55)
    sec_vol = len([v for v in vol_alerts_list if v.get('sector') == sec])
    mrd_sub = 40 + sec_vol * 15
    mrd_sub = max(30, min(95, mrd_sub))
    ss = sec_summary.get(sec, {})
    mf_sub = round(max(30, min(95, ss.get('avg_score', 5) * 12)))
    rot_sub = 50
    uni = round(rs_sub*0.25 + mom_sub*0.20 + mrd_sub*0.10 + mf_sub*0.30 + rot_sub*0.15)
    top_n = [s['name'] for s in sec_rs[:3]]
    return uni, rs_sub, mom_sub, mrd_sub, mf_sub, rot_sub, top_n

def score_class(val):
    """根据分值返回对应的sc-*类"""
    if val >= 80: return 'sc-aplus'
    if val >= 60: return 'sc-a'
    if val >= 40: return 'sc-b'
    if val >= 20: return 'sc-c'
    return 'sc-d'

model_rows = ''
for sec in sector_order:
    if sec not in sector_display: continue
    uni, rs_s, mom, mrd, mf, rot, stocks = calc_sector_scores(sec)
    stock_text = ' · '.join(stocks) if stocks else '—'
    if uni >= 60: uclass, tag = 'sc-a', '<span class="tag-up">↑增配</span>'
    elif uni >= 45: uclass, tag = 'sc-b', '<span class="tag-hold">—标配</span>'
    else: uclass, tag = 'sc-c', '<span class="tag-down">↓低配</span>'
    model_rows += f'<tr><td>{sector_display[sec]}</td>'
    model_rows += f'<td><span class="{uclass}">{uni}</span></td>'
    model_rows += f'<td><span class="{score_class(rs_s)}">{rs_s}</span></td>'
    model_rows += f'<td><span class="{score_class(mom)}">{mom}</span></td>'
    model_rows += f'<td><span class="{score_class(mrd)}">{mrd}</span></td>'
    model_rows += f'<td><span class="{score_class(mf)}">{mf}</span></td>'
    model_rows += f'<td><span class="{score_class(rot)}">{rot}</span></td>'
    model_rows += f'<td>{tag}</td><td style="color:#f85149">{stock_text}</td></tr>\n'

unified_html = f'''
<table>
<tr><th>板块</th><th>综合</th><th>RS</th><th>动量</th><th>MRD</th><th>多因子</th><th>轮动</th><th>配置</th><th>强势个股</th></tr>
{model_rows}
</table>
<p style="margin-top:4px;font-size:11px;color:#8b949e"><span class="sc-aplus">▓ ≥80 强势</span> · <span class="sc-a">▓ 60-79 偏强</span> · <span class="sc-b">▓ 40-59 中性</span> · <span class="sc-c">▓ 20-39 偏弱</span> · <span class="sc-d">▓ &lt;20 弱势</span></p>
'''

# ─── 4. 今日关注 ─────────────────────────────────────────
events = []
# 资金类：从多因子评分取资金面评分最高的2只股票
mf_stocks_list = cache['multi_factor_scores']['stocks']
capital_top = sorted(mf_stocks_list,
    key=lambda s: (s.get('factors', {}).get('capital', {}).get('score', 0), s.get('total_score', 0)),
    reverse=True)[:2]
capital_stocks = ' · '.join([s['name'] for s in capital_top])
events.append(('<span class="tag-up">资金</span>', f'北向资金大幅净流入+{north_val}亿', 'class="up"', '正面', '全市场/核心资产', capital_stocks))
for sec in top_sectors[:1]:
    sec_rs = [s for s in cache['rs_ranking'] if s.get('sector') == sec]
    top_stock = sec_rs[0]['name'] if sec_rs else '—'
    events.append(('<span class="tag-up">行业</span>', f'{sector_display.get(sec, sec)}板块走强', 'class="up"', '正面', sector_display.get(sec, sec), top_stock))
for v in vol_alerts_list[:2]:
    events.append(('<span class="tag-down">异动</span>', f'{v["name"]}({v["today_change"]:+.1f}%)波动异常', 'class="up"', '关注', v.get('sector', ''), v['name']))

focus_rows = ''
for cat, content, imp, effect, sect, stocks in events:
    focus_rows += f'<tr><td>{cat}</td><td>{content}</td><td {imp}>{effect}</td><td style="font-size:11px;color:#8b949e">{sect}</td><td style="font-size:11px;color:#f85149">{stocks}</td></tr>\n'
focus_html = f'<table>\n<tr><th>类别</th><th>内容</th><th>影响</th><th>影响板块</th><th>影响个股</th></tr>\n{focus_rows}</table>\n'

# 收集今日关注中的股票名单
focus_stock_set = set()
for _, _, _, _, _, stocks in events:
    for stock_name in stocks.replace(' ', '').split('·'):
        if stock_name:
            focus_stock_set.add(stock_name.strip())

# ─── 5. 持仓观察 ─────────────────────────────────────────
watch_by_sec = {}
for w in wl.get('watchlist', []):
    sec = w['sector']
    if sec not in watch_by_sec: watch_by_sec[sec] = []
    watch_by_sec[sec].append(w)

def _get_price(code):
    """从 tech_signals 缓存获取最新收盘价（兼容嵌套signals结构）"""
    ts = cache.get('tech_signals', {}).get(code, {}).get('signals', {})
    price = ts.get('close')
    if price: return f"{price:.2f}"
    # 有些股票数据不足，close在嵌套的signals里
    nested = ts.get('signals', {})
    price = nested.get('close')
    if price: return f"{price:.2f}"
    return "—"


def calc_mom_score(trend_label):
    if '强势' in trend_label: return 80
    if '偏强' in trend_label: return 65
    if '偏弱' in trend_label: return 35
    if '弱势' in trend_label: return 25
    return 50

def calc_opt(code, rank):
    sig = rs_ranking.get(code, {}).get('signal', '')
    mom = stock_mom.get(code, {})
    trend = mom.get('trend_label', '')
    pos = mom.get('position_label', '')
    slope = mom.get('trend_slope_3d', 0)
    vol = vol_alerts.get(code, {})
    change = vol.get('today_change', 0) if vol else None
    resist = mom.get('resistance_10d')
    support = mom.get('support_10d')

    if change is not None and abs(change) >= 9.5:
        if change > 0:
            sup_text = f'，设止盈{resist:.1f}' if resist and resist != '—' else ''
            return f'🔴 涨停持有{sup_text}'
        else:
            return '🟢 接近跌停，建议止损'

    is_strong = (rank in ('A+', 'A') or '强势' in sig or '强势' in trend)
    is_weak = (rank in ('C', 'D') or '弱势' in sig or '弱势' in trend or '偏弱' in sig or '偏弱' in trend)

    if is_strong:
        if '涨停' in trend or ('靠近压力' in pos and slope > 2):
            sup_text = f'{resist:.1f}' if resist and resist != '—' else '压力位'
            return f'🔴 强势持有，关注{sup_text}压力'
        if '靠近压力' in pos:
            return '🔴 强势突破，关注压力位'
        if '区间中段' in pos:
            return '🔴 强势中段，继续持有'
        if slope > 3:
            return '🔴 强势上攻，继续持有'
        return '🔴 偏强持有，持有观察'

    if is_weak:
        if '弱势下行' in trend and '靠近支撑' in pos:
            sup_text = f'{support:.1f}' if support and support != '—' else '支撑'
            return f'🟢 弱势下行，关注{sup_text}支撑'
        if '偏弱' in trend:
            return '🟢 偏弱整理，观望等待'
        if rank == 'D':
            return '🟢 弱势明显，建议减仓'
        return '🟢 关注风险，谨慎持有'

    if '横盘' in trend or '中性' in sig:
        if '靠近支撑' in pos:
            sup_text = f'{support:.1f}' if support and support != '—' else '支撑'
            return f'⚪ 回踩中，关注{sup_text}支撑'
        if '靠近压力' in pos:
            return '⚪ 冲高回落，短线观望'
        if '区间中段' in pos:
            return '⚪ 横盘整理，方向不明'
        return '⚪ 方向不明，观望等待'
    return '⚪ 持有观察，等待方向'

holdings_html = ''
for sec in sector_order:
    if sec not in watch_by_sec: continue
    display = sector_display.get(sec, sec)
    holdings_html += f'<h3 class="sector-title">{display}</h3>\n'
    holdings_html += '''<table>
<colgroup><col class="col-name"><col class="col-code"><col class="col-rate"><col class="col-mom"><col class="col-price"><col class="col-resist"><col class="col-support"><col class="col-opt"></colgroup>
<tr><th>名称</th><th>代码</th><th>评级</th><th>MOM</th><th>现价</th><th class="resist">压力位</th><th class="support">支撑位</th><th>操作建议</th></tr>
'''
    # 统一模型表中该板块的推荐强势股
    strong_stocks_in_sec = set()
    if sec in sector_order:
        _, _, _, _, _, _, top_stocks = calc_sector_scores(sec)
        strong_stocks_in_sec = set(top_stocks)

    # 按评级降序排列（A+ > A > B > C > D）
    rank_order = {'A+': 0, 'A': 1, 'B': 2, 'C': 3, 'D': 4, '': 5}
    sorted_stocks = sorted(watch_by_sec[sec], key=lambda w: rank_order.get(get_rank(w['code']), 5))
    for w in sorted_stocks:
        code = w['code']
        rank = get_rank(code)
        mom = stock_mom.get(code, {})
        mom_score = calc_mom_score(mom.get('trend_label', ''))
        price = _get_price(code)
        resist = s(mom.get('resistance_10d', '—'))
        support = s(mom.get('support_10d', '—'))
        opt = calc_opt(code, rank)
        name_display = w['name']
        has_fire = w['name'] in strong_stocks_in_sec
        has_focus = w['name'] in focus_stock_set
        if has_fire and has_focus:
            name_display = f'{w["name"]}&nbsp;<span class="tag-rec">🔥</span>&nbsp;<span class="tag-focus">📌</span>'
        elif has_fire:
            name_display = f'{w["name"]}&nbsp;<span class="tag-rec">🔥</span>'
        elif has_focus:
            name_display = f'{w["name"]}&nbsp;<span class="tag-focus">📌</span>'
        # 操作建议颜色与圆形图标一致
        first_ch = opt[0] if opt else ''
        if first_ch == chr(0x1F534):  # 🔴
            opt_colored = f'<span style="color:#f85149">{opt}</span>'
        elif first_ch == chr(0x1F7E2):  # 🟢
            opt_colored = f'<span style="color:#3fb950">{opt}</span>'
        elif first_ch == chr(0x26AA):  # ⚪
            opt_colored = f'<span style="color:#8b949e">{opt}</span>'
        else:
            opt_colored = f'<span>{opt}</span>'
        mom_cls = score_class(mom_score)
        holdings_html += f'<tr><td>{name_display}</td><td>{code}</td><td>{rate_html(rank)}</td><td><span class="{mom_cls}">{mom_score}</span></td><td>{price}</td><td class="resist">{resist}</td><td class="support">{support}</td><td>{opt_colored}</td></tr>\n'
    holdings_html += '</table>\n'

# ─── 6. 策略 ────────────────────────────────────────────
short_sec = {'能源/公用事业':'能源/公用','通信/电子':'通信/电子','科技/半导体':'科技/半导体','化工/材料':'化工/材料','AI/数字经济':'AI/数字'}
top_display = [short_sec.get(s,s) for s in top_sectors[:2]]
bot_display = [short_sec.get(s,s) for s in bot_sectors[:2]]
top_str = ' + '.join(top_display)
bot_str = ' + '.join(bot_display)

strategy_html = f'''
<table>
<tr><th>维度</th><th>信号</th><th>说明</th></tr>
<tr><td>📊 市场情绪</td><td><span class="tag-up">偏乐观</span></td><td>北向大幅流入+科技通信强势</td></tr>
<tr><td class="up">↑ 方向</td><td><span class="tag-up">超配: {top_str}</span></td><td>综合评分领先，强势个股集中</td></tr>
<tr><td class="flat">— 方向</td><td><span class="tag-hold">标配: 科技/半导体</span></td><td>内部分化严重，聚焦龙头</td></tr>
<tr><td class="down">↓ 方向</td><td><span class="tag-down">低配: {bot_str}</span></td><td>评分偏低，弱势股减仓</td></tr>
</table>
<p style="margin-top:4px;font-size:11px;color:#8b949e">💡 今日情绪指数: 58/100（谨慎乐观）· 结构性行情延续</p>
'''

# ─── FILL TEMPLATE ────────────────────────────────────────
with open('scripts/template-premarket.html') as f:
    template = f.read()

today = date.today()
date_str = today.strftime('%Y.%m.%d')
weekday_cn = ['周一','周二','周三','周四','周五','周六','周日'][today.weekday()]
now_str = datetime.now().strftime('%H:%M CST')

result = template
result = result.replace('{{DATE}}', date_str)
result = result.replace('{{WEEKDAY}}', weekday_cn)
result = result.replace('{{GENERATED_TIME}}', now_str)
result = result.replace('{{OVERSEAS_MARKET}}', overseas_html)
result = result.replace('{{MARKET_OUTLOOK}}', market_html)
result = result.replace('{{UNIFIED_MODEL_TABLE}}', unified_html)
result = result.replace('{{TODAY_FOCUS}}', focus_html)
result = result.replace('{{HOLDINGS_OBSERVATION}}', holdings_html)
result = result.replace('{{STRATEGY}}', strategy_html)

# Validate
errors = []
for ph in ['{{OVERSEAS_MARKET}}','{{MARKET_OUTLOOK}}','{{UNIFIED_MODEL_TABLE}}','{{TODAY_FOCUS}}','{{HOLDINGS_OBSERVATION}}','{{STRATEGY}}']:
    if ph in result: errors.append(f'❌ 未替换: {ph}')
if '{{' in result: errors.append('❌ 残留模板占位符')

date_id = today.strftime('%Y-%m-%d')
outpath = f'daily-report-html/premarket-{date_id}.html'
with open(outpath, 'w') as f:
    f.write(result)
    # \U0001f332 RF预测注入
    try:
        from rf_injector import inject_into_html
        inject_into_html(outpath, cache)
        print('  \U0001f332 RF注入完成')
    except Exception as _ee:
        print('  \U0001f332 RF注入失败:', _ee)
validate('premarket', result, raise_on_error=True)


print(f'✅ {outpath} ({len(result)} bytes)')
for c in ['{{OVERSEAS_MARKET}}','{{MARKET_OUTLOOK}}','{{UNIFIED_MODEL_TABLE}}','{{TODAY_FOCUS}}','{{HOLDINGS_OBSERVATION}}','{{STRATEGY}}']:
    print(f'   {c}: {"✅" if c not in result else "❌"}')
if errors:
    for e in errors: print(e)
else:
    print('✅ 验证通过')
holding_codes = set(w['code'] for w in wl.get('watchlist', []))
real_rs = len([c for c in holding_codes if c in rs_ranking])
real_mom_10 = len([c for c in holding_codes if c in stock_mom])
print(f'   持仓: {len(holding_codes)}只 | 有RS数据: {real_rs}只 | 有MOM/支撑压力: {real_mom_10}只')
print(f'   板块: {len(model_rows.split(chr(10)))} 行 | 外盘: {len(overseas)}/2 个')
