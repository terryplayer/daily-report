#!/usr/bin/env python3
"""
🌲 RF Predictor — 加载模型，为盘前报告注入 ML 预测
被 gen_premarket_report.py 调用，不碰模板。
"""

import pickle, json, os, re, sys
import numpy as np

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC_DISPLAY = {'能源/公用事业':'⚡ 能源/公用','通信/电子':'📡 通信/电子','科技/半导体':'💻 科技/半导体','化工/材料':'🧪 化工/材料','AI/数字经济':'🤖 AI/数字'}

def sector_predictions(cache):
    model_path = os.path.join(WORKSPACE, 'models', 'rf_cross_section.pkl')
    if not os.path.exists(model_path): return []
    
    with open(model_path, 'rb') as f: model = pickle.load(f)
    
    rs_all = cache['rs_ranking']
    mf_all = cache['multi_factor_scores']['stocks']
    mom_all = cache.get('stock_momentum', {})
    ts_all = cache.get('tech_signals', {})
    sec_rank = {s['sector']: s for s in cache['sector_ranking']}
    sec_mom = cache['sector_momentum']
    top_sec = sec_mom.get('top_sectors', []); bot_sec = sec_mom.get('bottom_sectors', [])
    mf_lookup = {s['code']: s for s in mf_all}
    
    def rv(r): return {'A+':1.0,'A':0.8,'B':0.5,'C':0.3,'D':0.1}.get(r,0.5)
    def tv(t): return {'强势上攻':1.0,'震荡偏强':0.7,'横盘震荡':0.5,'震荡偏弱':0.3,'弱势下行':0.0}.get(t,0.5)
    
    sectors = {}
    for s in rs_all:
        sec = s.get('sector', '其他')
        if sec not in sectors: sectors[sec] = {'preds': [], 'up': 0, 'total': 0}
        code = s['code']; mf = mf_lookup.get(code, {}); mom = mom_all.get(code, {})
        ts = ts_all.get(code, {}); boll = ts.get('signals',{}).get('bollinger',[])
        f10 = 0.5
        if len(boll)==3 and boll[0]!=boll[2]:
            c = ts.get('signals',{}).get('close',0)
            if c: f10 = (c - boll[2]) / (boll[0] - boll[2])
        fx = [s.get('rs_value',0)/50, s.get('rs_score',5), mf.get('total_score',5), 0,
              1 if sec in top_sec else (0 if sec in bot_sec else 0.5),
              sec_rank.get(sec,{}).get('avg_score',5),
              s.get('stock_change_pct',0)/10, rv(s.get('rank','B')),
              tv(mom.get('trend_label','')), f10, mom.get('position_pct',50)/100]
        pred = model.predict([fx])[0]
        sectors[sec]['preds'].append(pred); sectors[sec]['total'] += 1
        if pred > 0: sectors[sec]['up'] += 1
    
    return [(sec, sum(d['preds'])/len(d['preds']), d['up'], d['total']) for sec, d in sectors.items()]

def inject_into_html(html_path, cache):
    results = sector_predictions(cache)
    if not results: return
    
    with open(html_path) as f: html = f.read()
    
    # Build RF rows
    rf_rows = ''
    up_arrow = chr(8593); down_arrow = chr(8595)
    for sec, avg, up, total in results:
        arrow = up_arrow if avg > 0 else down_arrow
        tag_cls = 'tag-up' if avg > 0 else 'tag-down'
        tag = '<span class="%s">%s</span>' % (tag_cls, arrow)
        display_name = SEC_DISPLAY.get(sec, sec)
        row = '<tr><td>' + chr(127794) + ' ' + display_name + '</td><td style="color:#8b949e">-</td><td style="color:#8b949e">-</td>'
        row += '<td style="color:#8b949e">-</td><td style="color:#8b949e">-</td><td style="color:#8b949e">-</td>'
        row += '<td style="color:#8b949e">-</td><td>%s</td>' % tag
        row += '<td style="color:#8b949e">%s %.1f%%</td></tr>' % (arrow, avg)
        rf_rows += row + chr(10)
    
    # 在统一模型表后面追加RF预测小表格（独立表格，不注入到表内部）
    rf_table = (
        '<div style="margin-top:12px">\n'
        '<h3 style="color:#8b949e;margin:8px 0;font-size:13px">🌲 随机森林预测</h3>\n'
        '<table style="width:100%;border-collapse:collapse;font-size:12px">\n'
        '<colgroup><col style="width:35%"><col style="width:20%"><col style="width:45%"></colgroup>\n'
        '<tr><th style="text-align:left">板块</th><th style="text-align:center">方向</th><th style="text-align:center">概率</th></tr>\n'
    )
    up_arrow = chr(8593); down_arrow = chr(8595)
    up_color = '#f85149'; down_color = '#3fb950'
    for sec, avg, up, total in results:
        arrow = up_arrow if avg > 0 else down_arrow
        tag_cls = 'tag-up' if avg > 0 else 'tag-down'
        tag = '<span class="%s">%s</span>' % (tag_cls, arrow)
        prob_color = up_color if avg > 0 else down_color
        display_name = SEC_DISPLAY.get(sec, sec)
        rf_table += (
            '<tr>'
            '<td style="padding:4px 8px">%s</td>'
            '<td style="padding:4px 8px;text-align:center">%s</td>'
            '<td style="padding:4px 8px;text-align:center;color:%s">%s %.1f%%</td>'
            '</tr>\n' % (display_name, tag, prob_color, arrow, avg)
        )
    rf_table += '</table></div>\n'
    
    # 在统一模型table之后、颜色图例之前插入
    # 找颜色图例：唯一特征是 '▓ ≥80 强势' 这个字符串
    legend_mark = chr(0x2593) + ' ' + chr(8805) + '80'  # ▓ ≥80
    legend_pos = html.find(legend_mark)
    if legend_pos > 0:
        # 找到<p>标签结束（</p>），插在后面
        p_end = html.find('</p>', legend_pos)
        if p_end > 0:
            pos = p_end + 4  # 跳过</p>
        else:
            pos = legend_pos
        html = html[:pos] + rf_table + html[pos:]
    else:
        # 兜底：在统一模型表之后插入
        tables = list(re.finditer(r'<table>.*?</table>', html, re.DOTALL))
        for t in reversed(tables):
            if '板块' in t.group() and ('综合' in t.group() or 'RS' in t.group()):
                pos = t.end()
                html = html[:pos] + rf_table + html[pos:]
                break
    
    with open(html_path, 'w') as f: f.write(html)

if __name__ == '__main__':
    import json
    cp = sys.argv[1] if len(sys.argv) > 1 else '/tmp/stock_analysis_cache.json'
    with open(cp) as f: cache = json.load(f)
    results = sector_predictions(cache)
    for sec, avg, up, total in results:
        arrow = chr(8593) if avg > 0 else chr(8595)
        print('%s  %s %.2f%% (%d/%d)' % (sec, arrow, avg, up, total))
