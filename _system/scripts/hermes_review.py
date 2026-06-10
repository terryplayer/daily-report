#!/usr/bin/env python3
"""
🧠 Hermes 预测复盘 — 收盘后自动分析预测 vs 实际
被 cron 调用，把复盘结果存入 Hermes 长期记忆

用法: python3 scripts/hermes_review.py
"""

import json, os, sys, subprocess
from datetime import date

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)

# ─── 读取数据 ────────────────────────────────────────────
try:
    with open('/tmp/premarket-predictions.json') as f:
        pred = json.load(f)
except:
    print('❌ 无盘前预测数据')
    sys.exit(0)

try:
    with open('/tmp/stock_analysis_cache.json') as f:
        cache = json.load(f)
except:
    print('❌ 无分析数据')
    sys.exit(0)

# ─── 对比预测 vs 实际 ──────────────────────────────────
sectors_pred = pred.get('sectors', {})
rs_ranking = cache['rs_ranking']

review_data = []
total_correct = 0
total_count = 0

for sec_name, sec_pred in sectors_pred.items():
    direction = sec_pred.get('direction', '—')
    prob = sec_pred.get('prob', 50)
    
    # 取该板块的实际涨跌
    sec_stocks = [s for s in rs_ranking if s.get('sector') == sec_name]
    if not sec_stocks:
        continue
    
    avg_change = sum(s.get('stock_change_pct', 0) for s in sec_stocks) / len(sec_stocks)
    
    # 判断预测是否正确
    if direction == '↑' and avg_change > 0:
        correct = True
    elif direction == '↓' and avg_change < 0:
        correct = True
    elif direction == '—':
        correct = None  # 中性不判断
    else:
        correct = False
    
    if correct is not None:
        total_count += 1
        if correct:
            total_correct += 1
    
    review_data.append({
        'sector': sec_name,
        'prediction': direction,
        'prob': prob,
        'actual': f'{avg_change:+.2f}%',
        'correct': correct
    })

accuracy = f'{total_correct}/{total_count}' if total_count > 0 else '无数据'

# ─── 调用 Hermes 做深度复盘分析 ───────────────────────────
review_text = f"""
## 今日复盘 ({date.today().isoformat()})

### 板块预测验证
{'| 板块 | 预测方向 | 概率 | 实际涨跌 | 验证 |'}
{'|------|---------|------|---------|------|'}
"""
for r in review_data:
    check = '✅' if r['correct'] else ('❌' if r['correct'] is False else '⚪')
    review_text += f"| {r['sector']} | {r['prediction']} | {r['prob']}% | {r['actual']} | {check} |\n"

review_text += f"""
### 准确率
板块方向准确率: {accuracy}

### 本期经验
1. 今日哪些预测准确、哪些偏差？
2. 偏差的主要原因是什么？
3. 下次类似行情应如何调整判断逻辑？

请分析以上问题，并将复盘经验记入长期记忆。
"""

# 调用 Hermes CLI
prompt = f"""你是A股复盘分析引擎。分析以下盘前预测与收盘实际的对比，输出结构化复盘：

{review_text}

输出格式：
1. 准确率总结
2. 成功预测分析：为什么这些预测对了
3. 偏差预测分析：为什么错了，下次如何修正
请分析以上问题，并将复盘经验记入长期记忆。
"""

# 调用 Hermes CLI
prompt = f"""你是A股复盘分析引擎。分析以下盘前预测与收盘实际的对比，输出结构化复盘：

{review_text}

输出格式：
1. 准确率总结
2. 成功预测分析：为什么这些预测对了
3. 偏差预测分析：为什么错了，下次如何修正
4. 关键经验（最重要的一条，需要记住）

请直接输出分析结果，然后将关键经验记入你的长期记忆。"""

try:
    result = subprocess.run(
        ['hermes', 'chat', '-q', prompt, '-Q', '-m', 'deepseek/deepseek-v4-pro'],
        capture_output=True, text=True, timeout=120
    )
    print('🧠 Hermes 复盘完成')
    print(result.stdout[-500:])
    
    # 保存复盘结果
    outpath = f'reviews/closing-review-{date.today().isoformat()}.txt'
    os.makedirs('reviews', exist_ok=True)
    with open(outpath, 'w') as f:
        f.write(f'准确率: {accuracy}\n\n{result.stdout}')
    print(f'📝 复盘已保存: {outpath}')
    
except Exception as e:
    print(f'❌ Hermes 复盘失败: {e}')
