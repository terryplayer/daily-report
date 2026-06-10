#!/usr/bin/env python3
"""
🌲 随机森林完整管线 v2
Step 1: 拉60天历史 → Step 2: 构建特征 → Step 3: 训练+调参 → Step 4: 保存模型
"""

import json, os, sys, warnings, pickle, math
from datetime import datetime, date, timedelta
import numpy as np
import tushare as ts

warnings.filterwarnings('ignore')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── 1. 批量拉取历史数据 ──────────────────────────────────
ts.set_token(open('data/tushare_token.txt').read().strip())
pro = ts.pro_api()

with open('scripts/template-stocks.json') as f:
    wl = json.load(f)

print('📡 拉取60天历史数据...')
all_data = {}  # code -> [{date, close, change_pct}, ...]

for w in wl['watchlist']:
    code = w['code']
    suffix = '.SH' if code.startswith(('6', '9')) else '.SZ'
    df = pro.daily(ts_code=code+suffix, start_date='20260301', end_date='20260603')
    if df is None or len(df) == 0:
        continue
    records = []
    for _, row in df.iterrows():
        records.append({
            'date': str(row['trade_date']),
            'close': float(row['close']),
            'change_pct': float(row['pct_chg']),
            'high': float(row['high']),
            'low': float(row['low']),
        })
    records.reverse()  # 按日期升序
    all_data[code] = {'name': w['name'], 'sector': w['sector'], 'records': records}

print(f'  成功: {len(all_data)}/{len(wl["watchlist"])} 只股票')
print(f'  单只最多: {max(len(v["records"]) for v in all_data.values())} 天')

# ─── 2. 构建特征矩阵 ──────────────────────────────────────
# 同时从 cache 读取已有特征
with open('/tmp/stock_analysis_cache.json') as f:
    cache = json.load(f)

rs_lookup = {s['code']: s for s in cache['rs_ranking']}
mf_lookup = {s['code']: s for s in cache['multi_factor_scores']['stocks']}
mom_lookup = cache.get('stock_momentum', {})

print('\n🔨 构建特征矩阵...')
X, y, meta = [], [], []

for code, info in all_data.items():
    recs = info['records']
    if len(recs) < 10:
        continue
    
    rs = rs_lookup.get(code, {})
    mf = mf_lookup.get(code, {})
    mom = mom_lookup.get(code, {})
    
    for i in range(10, len(recs) - 1):
        day = recs[i]
        next_day = recs[i + 1]
        
        close = day['close']
        if not close or close == 0:
            continue
        
        # 回溯价格序列
        closes_20 = [r['close'] for r in recs[max(0,i-19):i+1] if r['close']]
        closes_10 = closes_20[-10:] if len(closes_20) >= 10 else closes_20
        closes_5 = closes_10[-5:] if len(closes_10) >= 5 else closes_10
        
        if len(closes_10) < 5:
            continue
        
        # Features (15维)
        f1 = day['change_pct']  # 当日涨跌
        
        ma5 = sum(closes_5) / len(closes_5)
        ma10 = sum(closes_10) / len(closes_10)
        ma20 = sum(closes_20) / len(closes_20) if len(closes_20) >= 20 else ma10
        
        f2 = (close / ma5 - 1) * 100      # MA5偏离
        f3 = (close / ma10 - 1) * 100     # MA10偏离
        f4 = (close / ma20 - 1) * 100     # MA20偏离
        
        # 近期高低点位置
        high_10 = max(r['high'] for r in recs[max(0,i-9):i+1])
        low_10 = min(r['low'] for r in recs[max(0,i-9):i+1])
        f5 = (close - low_10) / (high_10 - low_10) if high_10 != low_10 else 0.5  # 布林/位置
        
        # 波动率
        chgs = [r['change_pct'] for r in recs[max(0,i-9):i+1]]
        f6 = float(np.std(chgs))          # 10日波动率
        
        # 动量
        chg_3d = close / recs[i-2]['close'] - 1 if i >= 2 else 0
        chg_5d = close / recs[i-4]['close'] - 1 if i >= 4 else 0
        chg_10d = close / recs[i-9]['close'] - 1 if i >= 9 else 0
        f7 = chg_3d * 100                  # 3日动量
        f8 = chg_5d * 100                  # 5日动量
        f9 = chg_10d * 100                 # 10日动量
        
        # RS值 (来自现有系统)
        f10 = rs.get('rs_value', 0)
        
        # 多因子评分
        f11 = mf.get('total_score', 5)
        
        # 趋势动量 (来自stock_momentum)
        f12 = mom.get('trend_slope_3d', 0)
        
        # 价格位置
        f13 = mom.get('position_pct', 50) / 100
        
        # 昨日涨跌
        prev_change = recs[i-1]['change_pct'] if i >= 1 else 0
        f14 = prev_change
        
        # 是否靠近支撑/压力
        pos_label = mom.get('position_label', '')
        f15 = 1.0 if '靠近压力' in pos_label else (0.0 if '靠近支撑' in pos_label else 0.5)
        
        features = [f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13, f14, f15]
        target = next_day['change_pct']
        
        X.append(features)
        y.append(target)
        meta.append({
            'code': code, 'name': info['name'],
            'date': day['date'], 'close': close,
            'sector': info['sector'],
            'next_change': target
        })

X = np.array(X); y = np.array(y)
print(f'  特征矩阵: {X.shape[0]} 样本 × {X.shape[1]} 特征')
print(f'  日期范围: {meta[0]["date"]} ~ {meta[-1]["date"]}')

# ─── 3. 训练 + 调参 ──────────────────────────────────────
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score

n_train = int(len(X) * 0.8)
X_train, X_test = X[:n_train], X[n_train:]
y_train, y_test = y[:n_train], y[n_train:]
meta_train, meta_test = meta[:n_train], meta[n_train:]

print(f'\n🎯 训练集: {len(X_train)} | 测试集: {len(X_test)}')

# 调参
print('\n🔧 网格调参...')
param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [6, 8, 10, 12],
    'min_samples_leaf': [3, 5, 8],
}

grid = GridSearchCV(
    RandomForestRegressor(random_state=42, n_jobs=-1),
    param_grid, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=0
)
grid.fit(X_train, y_train)

best = grid.best_estimator_
print(f'  最佳参数: {grid.best_params_}')
print(f'  最佳CV MAE: {-grid.best_score_:.2f}%')

# 评估
y_pred = best.predict(X_test)
y_pred_train = best.predict(X_train)

mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
r2_train = r2_score(y_train, y_pred_train)

y_dir_true = (y_test > 0).astype(int)
y_dir_pred = (y_pred > 0).astype(int)
dir_acc = accuracy_score(y_dir_true, y_dir_pred)

print(f'\n📊 最终评估:')
print(f'  MAE: {mae:.2f}%')
print(f'  R²:  {r2:.3f}')
print(f'  训练R²: {r2_train:.3f}')
print(f'  方向准确率: {dir_acc:.1%}')

# 特征重要性
fnames = ['当日涨跌','MA5偏离','MA10偏离','MA20偏离','位置',
          '波动率','3日动量','5日动量','10日动量',
          'RS值','多因子','趋势动量','价格位置','昨日涨跌','支撑压力']
imp = best.feature_importances_
si = np.argsort(imp)[::-1]

print(f'\n🔑 特征重要性:')
for i, idx in enumerate(si[:8]):
    bar = '█' * int(imp[idx] * 50)
    print(f'  {i+1}. {fnames[idx]:>6}  {imp[idx]:.3f}  {bar}')

# ─── 4. 保存模型 + 元数据 ──────────────────────────────
model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(model_dir, exist_ok=True)

model_path = os.path.join(model_dir, 'random_forest_v2.pkl')
with open(model_path, 'wb') as f:
    pickle.dump(best, f)

summary = {
    'version': 'v2',
    'trained_at': datetime.now().isoformat(),
    'samples': len(X),
    'features': len(fnames),
    'feature_names': fnames,
    'feature_importance': {fnames[i]: float(imp[i]) for i in si},
    'mae': round(mae, 2),
    'r2': round(r2, 3),
    'dir_acc': round(dir_acc, 3),
    'best_params': grid.best_params_,
    'date_range': f'{meta[0]["date"]}~{meta[-1]["date"]}',
}

summary_path = os.path.join(model_dir, 'model_summary.json')
with open(summary_path, 'w') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f'\n💾 模型已保存: {model_path}')
print(f'📋 摘要: {summary_path}')

# ─── 5. 最新预测 ──────────────────────────────────────────
latest_date = meta[-1]['date']
latest_samples = [(m, X[i]) for i, m in enumerate(meta) if m['date'] == latest_date]

print(f'\n🔮 最新交易日 ({latest_date}) 预测:')
print(f'  {"股票":<10} {"代码":<8} {"收盘":>6} {"预测明日":>8} {"方向":>4}')
print(f'  {"-"*40}')
for m, fx in latest_samples[:15]:
    pred = best.predict([fx])[0]
    arrow = '↑' if pred > 0 else '↓'
    print(f'  {m["name"]:<10} {m["code"]:<8} {m["close"]:>6.2f} {pred:>+7.2f}%  {arrow:>3}')

# 板块汇总
sector_preds = {}
for m, fx in latest_samples:
    sec = m.get('sector', '其他')
    pred = best.predict([fx])[0]
    if sec not in sector_preds:
        sector_preds[sec] = {'count': 0, 'up': 0, 'total_pred': 0}
    sector_preds[sec]['count'] += 1
    sector_preds[sec]['total_pred'] += pred
    if pred > 0:
        sector_preds[sec]['up'] += 1

print(f'\n📋 板块方向:')
for sec, info in sorted(sector_preds.items()):
    avg = info['total_pred'] / info['count']
    arrow = '↑' if avg > 0 else '↓'
    print(f'  {sec:<8}  {arrow} {avg:+.2f}%  ({info["up"]}/{info["count"]})')

print(f'\n✅ 完成!')
