#!/usr/bin/env python3
"""
🔍 Gen 脚本硬编码审计 — 检测候选模板样本数据是否混入代码
用法: python3 scripts/audit_gen_scripts.py
"""

import re, os, json, sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_FILES = ['gen_premarket_report.py', 'gen_midday_report.py', 'gen_closing_report.py', 'gen_weekly_report.py']

# 候选模板样本关键字（股票名）
with open(os.path.join(WORKSPACE, 'scripts', 'candidate_sample_keywords.json')) as f:
    keywords = json.load(f)

SKIP_NAMES = {'上证指数','深证成指','创业板指','科创50','中小板指','正面','中性','负面',
              '道琼斯','纳斯达克','标普500','A50','北向资金','沪股通','深股通','全市场',
              '核心资产','今日','最新','压力位','支撑位','成交额','涨停','跌停','板块','方向','震荡偏强','震荡偏弱','横盘整理','横盘震荡','强势上攻','弱势下行'}

class Found:
    """标记找到的问题"""
    def __init__(self):
        self.issues = []

found = Found()

for fname in GEN_FILES:
    path = os.path.join(WORKSPACE, 'scripts', fname)
    if not os.path.exists(path):
        continue
    
    with open(path) as f:
        code = f.read()
    
    report_type = fname.replace('gen_', '').replace('_report.py', '')
    kw_list = keywords.get(report_type, [])
    
    # 只检查股票名
    stock_names = [k for k in kw_list if re.match(r'^[\u4e00-\u9fff]{2,4}$', k) and k not in SKIP_NAMES]
    
    found_names = []
    for name in stock_names:
        # 在字符串引号内搜索股票名
        if re.search(r"['\"]" + name + r"['\"]", code):
            found_names.append(name)
    
    # 检查硬编码价格（不是从数据源读取的）
    hardcoded_prices = re.findall(r"(?<!['\"])['\"](\d{2,3}\.\d{2})['\"](?!['\"])", code)
    # 过滤：10-500之间的价格可能是硬编码的
    suspect_prices = [p for p in hardcoded_prices if 10 < float(p) < 500]
    
    issues = []
    if found_names:
        issues.append('硬编码股票名(%d): %s' % (len(found_names), found_names[:8]))
    if suspect_prices:
        issues.append('可疑硬编码价格(%d): %s' % (len(suspect_prices), suspect_prices[:5]))
    
    if issues:
        found.issues.append((fname, issues))

if found.issues:
    print('❌ 硬编码数据检测到:')
    for fname, issues in found.issues:
        print('  %s:' % fname)
        for i in issues:
            print('    - %s' % i)
    sys.exit(1)
else:
    print('✅ 所有 gen 脚本无硬编码候选样本数据')
    sys.exit(0)
