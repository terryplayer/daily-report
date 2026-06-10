#!/usr/bin/env python3
"""
🌲 随机森林预测框架 — 统一模型集成
特征: RS·动量·技术面·多因子 · 目标: 次日涨跌幅
接入: get_model_summary() 统一输出

用法: python3 scripts/random_forest_model.py
"""

import json, os, sys, warnings, math
from datetime import datetime, date, timedelta
import numpy as np

# 预加载持仓列表（避免在每个循环中重复导入）
_STOCK_CODES = []
_WATCHLIST_FULL = []
try:
    from scripts.stock_analysis import WATCHLIST_FULL as _WF
    _WATCHLIST_FULL = _WF
    _STOCK_CODES = [(s['code'], s['sector']) for s in _WF]
except Exception:
    pass

_CODE_TO_SECTOR = {code: sec for code, sec in _STOCK_CODES}

warnings.filterwarnings('ignore')

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)
sys.path.insert(0, WORKSPACE)

# ─── 加载数据 ──────────────────────────────────────────
with open('data/stock_history.json') as f:
    hist = json.load(f)

with open('/tmp/stock_analysis_cache.json') as f:
    cache = json.load(f)

def _compute_date_similarity_for_rf(history, target_date, stock_code, stock_sector):
    """
    为RF训练计算历史相似度特征。
    
    对 target_date 之前的所有交易日，找与 target_date 市场特征最相似的N天，
    看那些相似日里该板块的表现如何。
    
    这是一个简化的替代方案（不依赖FAISS），用股价数据直接计算。
    """
    dates = sorted(history.get('history', {}).keys())
    # target_date 之前的交易日
    prev_dates = [d for d in dates if d < target_date]
    
    if len(prev_dates) < 3:
        return 50.0  # 数据不足，返回中性
    
    # 获取 target_date 的市场特征
    target_data = history['history'].get(target_date, {})
    target_bench = target_data.get('benchmark', {})
    target_stocks = target_data.get('stocks', {})
    
    # 收集 sector 变化
    def _get_sector_changes(stocks_dict):
        sec_changes = {}
        for code, s in stocks_dict.items():
            if not isinstance(s, dict):
                continue
            sec = _CODE_TO_SECTOR.get(code, '其他')
            chg = s.get('change_pct', 0) or 0
            sec_changes.setdefault(sec, []).append(chg)
        return {sec: sum(v)/len(v) for sec, v in sec_changes.items()}
    
    target_sec_changes = _get_sector_changes(target_stocks)
    target_bench_pct = target_bench.get('change_pct', 0)
    if isinstance(target_bench_pct, str):
        try:
            target_bench_pct = float(target_bench_pct.rstrip('%'))
        except:
            target_bench_pct = 0
    
    # 对每个历史日前一天，计算与 target_date 的相似度
    similarities = []
    for d in prev_dates:
        d_data = history['history'][d]
        d_bench = d_data.get('benchmark', {})
        d_stocks = d_data.get('stocks', {})
        
        if not isinstance(d_stocks, dict):
            continue
        
        d_bench_pct = d_bench.get('change_pct', 0)
        if isinstance(d_bench_pct, str):
            try:
                d_bench_pct = float(d_bench_pct.rstrip('%'))
            except:
                d_bench_pct = 0
        
        d_sec_changes = _get_sector_changes(d_stocks)
        
        # 简单相似度：基准涨跌差 + 板块涨跌差 的负指数
        bench_diff = abs(target_bench_pct - d_bench_pct)
        sec_diff = 0
        all_secs = set(list(target_sec_changes.keys()) + list(d_sec_changes.keys()))
        count = 0
        for sec in all_secs:
            tc = target_sec_changes.get(sec, 0)
            dc = d_sec_changes.get(sec, 0)
            sec_diff += abs(tc - dc)
            count += 1
        avg_sec_diff = sec_diff / max(count, 1)
        
        # 相似度 = exp(-(bench_diff + avg_sec_diff * 0.5))
        sim = math.exp(-(bench_diff + avg_sec_diff * 0.3))
        
        # 该历史日的下一个交易日该板块的涨跌
        next_date_idx = dates.index(d) + 1
        if next_date_idx >= len(dates):
            continue
        next_date = dates[next_date_idx]
        next_data = history['history'].get(next_date, {})
        next_stocks = next_data.get('stocks', {})
        next_sec_changes = _get_sector_changes(next_stocks)
        next_sec_change = next_sec_changes.get(stock_sector, 0)
        
        similarities.append({'sim': sim, 'next_change': next_sec_change})
    
    if not similarities:
        return 50.0
    
    # 加权平均
    total_sim = sum(s['sim'] for s in similarities)
    if total_sim <= 0:
        return 50.0
    
    weighted_change = sum(s['sim'] * s['next_change'] for s in similarities) / total_sim
    
    # 转成 0~100 分
    score = 50 + weighted_change * 3
    return max(0, min(100, score))


# ─── 构建特征矩阵 ──────────────────────────────────────
def build_feature_matrix(history, cache):
    """
    为每只股票每天构建特征向量。
    
    特征:
    - f1: 当日涨跌幅 (change_pct)
    - f2: 5日均线偏离度 (close/ma5 - 1)
    - f3: 10日均线偏离度 (close/ma10 - 1)
    - f4: 布林位置 (close - lower) / (upper - lower)
    - f5: 波动率 (过去5天change_pct的std)
    - f6: RS值 (来自RS ranking)
    - f7: 多因子评分
    - f8: 趋势动量 (trend_slope_3d)
    - f9: 价格位置 (position_pct/100)
    - f10: 昨日涨跌幅 (滞后1期)
    - f11: 历史相似度 (RAG增强) — 相似市场环境下该板块的表现预期
    
    目标:
    - 次日涨跌幅 (next_day_change)
    """
    dates = sorted(history.get('history', {}).keys())
    stock_codes = set()
    for d in dates:
        stock_codes.update(history['history'][d].get('stocks', {}).keys())
    
    rs_lookup = {s['code']: s for s in cache['rs_ranking']}
    mf_lookup = {s['code']: s for s in cache['multi_factor_scores']['stocks']}
    mom_lookup = cache.get('stock_momentum', {})
    ts_lookup = cache.get('tech_signals', {})
    
    X, y, meta = [], [], []
    
    for code in sorted(stock_codes):
        # 提取该股票所有交易日数据
        price_series = []
        for d in dates:
            stocks = history['history'][d].get('stocks', {})
            if code in stocks:
                price_series.append({'date': d, **stocks[code]})
        
        if len(price_series) < 6:
            continue  # 数据太少
        
        rs_info = rs_lookup.get(code, {})
        mf_info = mf_lookup.get(code, {})
        mom_info = mom_lookup.get(code, {})
        ts_info = ts_lookup.get(code, {})
        
        for i in range(5, len(price_series) - 1):
            day = price_series[i]
            next_day = price_series[i + 1]
            
            # 获取收盘价序列用于技术指标计算
            closes_10 = [p.get('close') for p in price_series[max(0,i-9):i+1]]
            closes_10 = [c for c in closes_10 if c is not None]
            closes_5 = closes_10[-5:] if len(closes_10) >= 5 else closes_10
            
            if not closes_10 or not closes_5:
                continue
            
            close = day.get('close')
            if close is None:
                continue
            
            # f1: 当日涨跌幅
            f1 = day.get('change_pct', 0) or 0
            
            # f2-f3: 均线偏离度
            ma5 = sum(closes_5) / len(closes_5) if closes_5 else close
            ma10 = sum(closes_10) / len(closes_10) if closes_10 else close
            f2 = (close / ma5 - 1) * 100 if ma5 > 0 else 0
            f3 = (close / ma10 - 1) * 100 if ma10 > 0 else 0
            
            # f4: 布林位置
            boll = ts_info.get('signals', {}).get('bollinger', [])
            if boll and len(boll) == 3:
                upper, mid, lower = boll[0], boll[1], boll[2]
                f4 = (close - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
            else:
                f4 = 0.5
            
            # f5: 波动率
            changes_5 = [p.get('change_pct', 0) or 0 for p in price_series[max(0,i-4):i+1]]
            f5 = np.std(changes_5) if len(changes_5) > 1 else 0
            
            # f6: RS值
            f6 = rs_info.get('rs_value', 0)
            
            # f7: 多因子评分
            f7 = mf_info.get('total_score', 5)
            
            # f8: 趋势动量
            f8 = mom_info.get('trend_slope_3d', 0)
            
            # f9: 价格位置
            f9 = mom_info.get('position_pct', 50) / 100
            
            # f10: 昨日涨跌幅
            prev_change = price_series[i-1].get('change_pct', 0) or 0
            f10 = prev_change
            
            # f11: 历史相似度 (RAG增强)
            # 在训练时动态计算，避免数据泄露
            f11 = _compute_date_similarity_for_rf(
                history, day['date'], code,
                rs_info.get('sector', '?')
            )
            
            # 标签: 次日涨跌幅
            target = next_day.get('change_pct', 0) or 0
            
            # 特征向量
            features = [f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11]
            
            X.append(features)
            y.append(target)
            meta.append({
                'code': code, 'name': day.get('name') or rs_info.get('name', '?'),
                'date': day['date'], 'close': close,
                'sector': rs_info.get('sector', '?'),
                'next_change': target
            })
    
    return np.array(X), np.array(y), meta


# ─── 训练模型 ──────────────────────────────────────────
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score
import pandas as pd

print('🌲 随机森林预测框架')
print('=' * 50)

X, y, meta = build_feature_matrix(hist, cache)

print(f'\n样本总数: {len(X)}')
print(f'特征维度: {X.shape[1]}')

# 按时间切分：前80%训练，后20%测试
n_train = int(len(X) * 0.8)
X_train, X_test = X[:n_train], X[n_train:]
y_train, y_test = y[:n_train], y[n_train:]
meta_train, meta_test = meta[:n_train], meta[n_train:]

print(f'训练集: {len(X_train)} | 测试集: {len(X_test)}')

# ─── 训练 ────────────────────────────────────────────
model = RandomForestRegressor(
    n_estimators=200,
    max_depth=8,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

# ─── 评估 ────────────────────────────────────────────
y_pred = model.predict(X_test)
y_pred_train = model.predict(X_train)

mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

# 方向准确率（涨/跌判断）
y_dir_true = (y_test > 0).astype(int)
y_dir_pred = (y_pred > 0).astype(int)
dir_acc = accuracy_score(y_dir_true, y_dir_pred)

print(f'\n📊 模型评估')
print(f'  MAE (平均绝对误差): {mae:.2f}%')
print(f'  R²: {r2:.3f}')
print(f'  方向准确率: {dir_acc:.1%}')
print(f'  训练R²: {r2_score(y_train, y_pred_train):.3f}')

# ─── 特征重要性 ─────────────────────────────────────
feature_names = ['当日涨跌', 'MA5偏离', 'MA10偏离', '布林位置', '波动率',
                 'RS值', '多因子', '趋势动量', '价格位置', '昨日涨跌',
                 '历史相似度']
importances = model.feature_importances_
sorted_idx = np.argsort(importances)[::-1]

print(f'\n🔑 特征重要性排序:')
for i, idx in enumerate(sorted_idx):
    bar = '█' * int(importances[idx] * 50)
    print(f'  {i+1}. {feature_names[idx]:>8}  {importances[idx]:.3f}  {bar}')

# ─── 最新预测（明天） ───────────────────────────────
print(f'\n🔮 最新交易日 ({meta[-1]["date"]}) 持仓股票次日预测:')
print(f'  {"股票":<10} {"代码":<8} {"今日涨跌":>8} {"预测明日":>8} {"方向":>4} {"置信度":>6}')
print(f'  {"-"*48}')

# 取最后一天的样本作为最新预测
latest_date = meta[-1]['date']
latest_samples = [(m, X[i]) for i, m in enumerate(meta) if m['date'] == latest_date]

for m, fx in latest_samples[:15]:
    pred = model.predict([fx])[0]
    conf = min(abs(pred) / 2, 1.0)
    arrow = '↑' if pred > 0 else '↓'
    print(f'  {m["name"]:<10} {m["code"]:<8} {m.get("next_change",0):>+7.2f}%  {pred:>+7.2f}%  {arrow:>3}  {conf:.0%}')

# ─── 板块汇总预测 ──────────────────────────────────
sector_preds = {}
for m, fx in latest_samples:
    sec = m.get('sector', '其他')
    pred = model.predict([fx])[0]
    if sec not in sector_preds:
        sector_preds[sec] = {'count': 0, 'up': 0, 'down': 0, 'total_pred': 0}
    sector_preds[sec]['count'] += 1
    sector_preds[sec]['total_pred'] += pred
    if pred > 0:
        sector_preds[sec]['up'] += 1
    else:
        sector_preds[sec]['down'] += 1

print(f'\n📋 板块方向预测:')
for sec, info in sorted(sector_preds.items()):
    avg_pct = info['total_pred'] / info['count']
    arrow = '↑' if avg_pct > 0 else '↓'
    print(f'  {sec:<8}  {arrow} {avg_pct:+.2f}%  ({info["up"]}/{info["count"]}只看涨)')

# ─── 统一模型摘要 ──────────────────────────────────
print(f'\n{"="*50}')
print('📈 get_model_summary() — 统一模型摘要')
print(f'{"="*50}')
print(f'模型: RandomForest (n_estimators=200, max_depth=8)')
print(f'特征: {X.shape[1]} 维 ({", ".join(feature_names[sorted_idx[i]] for i in range(5))}...)')
print(f'样本: {len(X)} 条 ({meta[0]["date"]}~{meta[-1]["date"]})')
print(f'MAE: {mae:.2f}% | 方向准确率: {dir_acc:.1%} | R²: {r2:.3f}')
print(f'最强特征: {feature_names[sorted_idx[0]]} ({importances[sorted_idx[0]]:.3f})')
print(f'最新预测: {len(latest_samples)} 只持仓')
print(f'{"="*50}')
