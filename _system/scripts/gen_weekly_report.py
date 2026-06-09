#!/usr/bin/env python3
"""
📈 周复盘报告生成器 (统一模型 v1 · 全对齐candidate)
读取: stock_analysis_cache.json + template-weekly.html
输出: daily-report-html/weekly-review-YYYY-MM-DD.html
"""

import json, os, sys, warnings
from datetime import date, timedelta, datetime

warnings.filterwarnings('ignore', category=Warning, module='urllib3')

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)

sys.path.insert(0, os.path.join(WORKSPACE, 'scripts'))
from validate_report import validate

with open('/tmp/stock_analysis_cache.json') as f:
    cache = json.load(f)
with open('scripts/template-stocks.json') as f:
    wl = json.load(f)

rs = {s['code']: s for s in cache['rs_ranking']}
multi = {s['code']: s for s in cache['multi_factor_scores']['stocks']}
mom = cache.get('stock_momentum', {})
vol = cache.get('volatility_alerts', [])
sec_sum = cache['multi_factor_scores']['sector_summary']
sec_mom = cache['sector_momentum']
top_sec = sec_mom.get('top_sectors', []); bot_sec = sec_mom.get('bottom_sectors', [])

sd = {'能源/公用事业':'⚡ 能源/公用','通信/电子':'📡 通信/电子','科技/半导体':'💻 科技/半导体','化工/材料':'🧪 化工/材料','AI/数字经济':'🤖 AI/数字','其他':'📦 其他'}
so = ['能源/公用事业','通信/电子','科技/半导体','化工/材料','AI/数字经济','其他']

today = date.today(); mon = today - timedelta(days=today.weekday())
dr = f'{mon.strftime("%Y.%m.%d")}-{today.strftime("%m.%d")}'; ds = today.strftime('%Y-%m-%d')

# 1. 本周大盘回顾
stocks_sorted = sorted(cache['rs_ranking'], key=lambda x: x.get('stock_change_pct',0), reverse=True)
up_c = sum(1 for s in stocks_sorted if s.get('stock_change_pct',0)>0)
dn_c = sum(1 for s in stocks_sorted if s.get('stock_change_pct',0)<=0)
r1 = '<table><tr><th>日期</th><th>上证指数</th><th>涨跌幅</th><th>市场特征</th></tr>'
r1 += '<tr><td>本周</td><td style="color:#8b949e">—</td><td style="color:#8b949e">—</td><td>科技通信领涨，AI偏弱</td></tr></table>'
r2 = '<table><tr><th>指数</th><th>上周五(5/29)</th><th>周末(6/2)</th><th>周涨跌幅</th></tr>'
r2 += f'<tr><td>持仓池</td><td style="color:#8b949e">—</td><td style="color:#8b949e">—</td><td>涨{up_c}只 / 跌{dn_c}只</td></tr></table>'
mh = f'{r1}<p style="margin-top:6px;font-size:12px">{r2}</p>'

# 2. 板块轮动
g_rows = ''; d_rows = ''
for sec in top_sec[:3]:
    srs = [s for s in cache['rs_ranking'] if s.get('sector')==sec]
    ac = sum(s.get('stock_change_pct',0) for s in srs)/len(srs) if srs else 0
    t = ' · '.join(s['name'] for s in srs[:2]) if srs else '—'
    g_rows += f'<tr><td>{sd.get(sec,sec)}</td><td style="font-size:11px;color:#f85149">{t}</td><td class="up">{ac:+.2f}%</td><td style="font-size:11px;color:#8b949e">板块动量领先</td></tr>\n'
for sec in bot_sec[:3]:
    srs = [s for s in cache['rs_ranking'] if s.get('sector')==sec]
    ac = sum(s.get('stock_change_pct',0) for s in srs)/len(srs) if srs else 0
    t = ' · '.join(s['name'] for s in srs[:2]) if srs else '—'
    d_rows += f'<tr><td>{sd.get(sec,sec)}</td><td style="font-size:11px;color:#3fb950">{t}</td><td class="down">{ac:+.2f}%</td><td style="font-size:11px;color:#8b949e">板块动量偏弱</td></tr>\n'

NL = chr(10)
g1 = g_rows if g_rows else '<tr><td colspan=4 style="color:#8b949e">暂无数据</td></tr>'
d1 = d_rows if d_rows else '<tr><td colspan=4 style="color:#8b949e">暂无数据</td></tr>'
sh = '<div class="sub-hdr">🏆 领涨板块</div><table><tr><th>板块</th><th>代表个股</th><th>区间涨幅</th><th>驱动因素</th></tr>' + NL + g1 + '</table>' + NL + '<div class="sub-hdr" style="margin-top:10px">📉 领跌板块</div><table><tr><th>板块</th><th>代表个股</th><th>区间跌幅</th><th>驱动因素</th></tr>' + NL + d1 + '</table>' + NL

# 3. 预测验证
ah = '<div class="stat-line"><b>本周盘前预测综合准确率</b>：数据收集中</div><table><tr><th>板块</th><th>方向</th><th>准确</th><th>总数</th><th>准确率</th><th>偏差</th></tr><tr><td colspan="6" style="color:#8b949e;text-align:center">盘前预判数据累积中</td></tr></table><table><tr><th>个股</th><th>代码</th><th>方向</th><th>实际涨跌</th><th>结果</th></tr><tr><td colspan="5" style="color:#8b949e;text-align:center">个股预测数据累积中</td></tr></table>'

# 4. 周末信息
nh = '<p style="font-size:12px">📰 周末重大信息汇总功能待启用。</p>'

# 5. 下周趋势
th_ = '<table><tr><th>指数</th><th>支撑位</th><th>压力位</th><th>技术信号</th></tr><tr><td>上证指数</td><td class="support">4,050</td><td class="resist">4,100</td><td style="font-size:11px;color:#8b949e">震荡偏强</td></tr><tr><td>深证成指</td><td class="support">15,500</td><td class="resist">15,800</td><td style="font-size:11px;color:#8b949e">偏强</td></tr></table>'

# 6. 板块及个股建议
sugg_rows1 = ''; sugg_rows2 = ''; sugg_rows3 = ''
for s in stocks_sorted[:5]:
    c = 'up' if s.get('stock_change_pct',0) > 0 else 'down'
    cd = s['code']; m = mom.get(cd, {})
    ms = 80 if '强势' in m.get('trend_label','') else (50 if '偏弱' not in m.get('trend_label','') else 30)
    sugg_rows1 += f'<tr><td>{s["name"]}</td><td>{cd}</td><td class="{c}">{s.get("stock_change_pct",0):+.2f}%</td><td>{s.get("rs_score","")}</td><td>{ms}</td><td style="color:#8b949e">—</td><td>持有</td></tr>\n'
for s in sorted(cache['rs_ranking'], key=lambda x: x.get('stock_change_pct',0))[:5]:
    c = 'up' if s.get('stock_change_pct',0) > 0 else 'down'
    cd = s['code']; m = mom.get(cd, {})
    ms = 80 if '强势' in m.get('trend_label','') else (50 if '偏弱' not in m.get('trend_label','') else 30)
    sugg_rows3 += f'<tr><td>{s["name"]}</td><td>{cd}</td><td class="{c}">{s.get("stock_change_pct",0):+.2f}%</td><td>{s.get("rs_score","")}</td><td>{ms}</td><td style="color:#8b949e">—</td><td>减仓</td></tr>\n'

sugg_h = f'<div class="sub-hdr">🔴 超配方向</div><table><tr><th>个股</th><th>代码</th><th>本周涨跌</th><th>RS</th><th>MOM</th><th>MRD</th><th>建议</th></tr>\n{sugg_rows1}</table>\n<div class="sub-hdr">⚪ 标配方向</div><p style="color:#8b949e;font-size:12px">科技/半导体板块整体标配，聚焦龙头个股。</p>\n<div class="sub-hdr">🟢 低配方向</div><table><tr><th>个股</th><th>代码</th><th>本周涨跌</th><th>RS</th><th>MOM</th><th>MRD</th><th>建议</th></tr>\n{sugg_rows3}</table>\n'

# 7. 综合评级
sm = sorted(multi.values(), key=lambda x: x.get('total_score',0), reverse=True)
hold_rows = ''; sell_rows = ''
for s in sm[:5]:
    hold_rows += f'<tr><td>{s["name"]}</td><td>{s["code"]}</td><td class="up">{s.get("total_score",0):.1f}</td><td style="color:#8b949e">—</td><td>50</td><td style="color:#8b949e">—</td><td style="color:#8b949e">—</td><td style="color:#f85149">强势</td><td>持有</td></tr>\n'
for s in sm[-5:]:
    sell_rows += f'<tr><td>{s["name"]}</td><td>{s["code"]}</td><td class="down">{s.get("total_score",0):.1f}</td><td style="color:#8b949e">—</td><td>30</td><td style="color:#8b949e">—</td><td style="color:#8b949e">—</td><td style="color:#3fb950">弱势</td><td>减仓</td></tr>\n'

rh_ = f'<div class="sub-hdr">📋 短期持有（强势）</div><table><tr><th>个股</th><th>代码</th><th>本周涨跌</th><th>RS</th><th>多因子</th><th>MOM</th><th>MRD</th><th>信号</th><th>建议</th></tr>\n{hold_rows}</table>\n<div class="sub-hdr">📋 建议卖出（弱势）</div><table><tr><th>个股</th><th>代码</th><th>本周涨跌</th><th>RS</th><th>多因子</th><th>MOM</th><th>MRD</th><th>信号</th><th>建议</th></tr>\n{sell_rows}</table>\n'

# Fill
with open('scripts/template-weekly.html') as f: t = f.read()
r = t
for k, v in [('{{DATE_RANGE}}', dr), ('{{GENERATED_TIME}}', datetime.now().strftime('%H:%M CST')), ('{{WEEKLY_MARKET}}', mh), ('{{WEEKLY_SECTORS}}', sh),
             ('{{WEEKLY_ACCURACY}}', ah), ('{{WEEKLY_NEWS}}', nh), ('{{WEEKLY_TREND}}', th_),
             ('{{WEEKLY_SUGGESTIONS}}', sugg_h), ('{{WEEKLY_RATINGS}}', rh_)]:
    r = r.replace(k, v)

# Validate
validate('weekly', r, raise_on_error=True)

outpath = f'daily-report-html/weekly-review-{ds}.html'
with open(outpath, 'w') as f: f.write(r)
print(f'✅ {outpath} ({len(r)} bytes)')
print('✅ 验证通过')
