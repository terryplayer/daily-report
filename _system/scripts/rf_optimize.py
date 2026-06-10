#!/usr/bin/env python3
"""
🌲 随机森林迭代优化（2026-06-08）
精简实用版：比较多种配置 + 特征重要性 + 存储最佳
"""
import json, os, sys, pickle, warnings
from datetime import datetime
import numpy as np
warnings.filterwarnings('ignore')

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)
sys.path.insert(0, WORKSPACE)

print('📂 加载数据...')
with open('data/stock_history.json') as f: hist = json.load(f)
with open('/tmp/stock_analysis_cache.json') as f: cache = json.load(f)

# ─── 现有模型 ────────────────────────────────────────────
print('\n📋 现有模型参数:')
for name in ['random_forest_v2', 'rf_cross_section', 'rf_stock_model']:
    p = f'models/{name}.pkl'
    if os.path.exists(p):
        m = pickle.load(open(p, 'rb'))
        print(f'  {name:20s}  n={m.n_estimators}  d={m.max_depth}  '
              f'split={m.min_samples_split}  leaf={m.min_samples_leaf}  f={m.n_features_in_}')

# ─── 截面特征构建 ────────────────────────────────────────
print('\n🔧 构建截面特征...')
rs_all = cache.get('rs_ranking', [])
rs_lookup = {s['code']: s for s in rs_all}
mf_all = cache.get('multi_factor_scores', {}).get('stocks', [])
mom_all = cache.get('stock_momentum', {})
ts_all = cache.get('tech_signals', {})
sec_rank = {s['sector']: s for s in cache.get('sector_ranking', [])}
sec_mom = cache.get('sector_momentum', {})
top_sec = set(sec_mom.get('top_sectors', [])); bot_sec = set(sec_mom.get('bottom_sectors', []))
mf_lookup = {s['code']: s for s in mf_all}

def rv(r): return {'A+':1.0,'A':0.8,'B':0.5,'C':0.3,'D':0.1}.get(r,0.5)
def tv(t): return {'强势上攻':1.0,'震荡偏强':0.7,'横盘震荡':0.5,'震荡偏弱':0.3,'弱势下行':0.0}.get(t,0.5)

X_all, y_all, meta_all = [], [], []
for mf in mf_all:  # ★ 全量77只
    code = mf['code']
    s = rs_lookup.get(code, {})  # RS数据（可能为空）
    mom = mom_all.get(code, {})
    ts = ts_all.get(code, {}); boll = ts.get('signals',{}).get('bollinger',[])
    f10 = 0.5
    if len(boll)==3 and boll[0]!=boll[2]:
        c = ts.get('signals',{}).get('close',0)
        if c: f10 = (c - boll[2])/(boll[0]-boll[2])
    sec = mf.get('sector', s.get('sector', ''))
    fx = [
        s.get('rs_value',50)/50,        # 0: RS标准化（无RS数据则默认1.0）
        s.get('rs_score',50),            # 1: RS评分（无RS数据则默认50）
        mf.get('total_score',5),         # 2: 多因子
        0,                               # 3: 保留
        1 if sec in top_sec else (0 if sec in bot_sec else 0.5),  # 4: 板块偏向
        sec_rank.get(sec,{}).get('avg_score',5),  # 5: 板块均分
        s.get('stock_change_pct',0)/10,  # 6: 涨跌幅/10
        rv(s.get('rank','B')),           # 7: 等级
        tv(mom.get('trend_label','')),   # 8: 趋势标签
        f10,                             # 9: 布林位置
        mom.get('position_pct',50)/100,  # 10: 价格位置
    ]
    X_all.append(fx)
    y_all.append(s.get('stock_change_pct',0)/10)
    meta_all.append({'code':code,'name':mf.get('name',s.get('name','?')),'sector':sec})

X = np.array(X_all); y = np.array(y_all)
print(f'样本: {len(X)} 条, 特征: {X.shape[1]} 维')

# ─── 时间序列分割 ────────────────────────────────────────
n_train = int(len(X) * 0.8)
X_tr, X_te = X[:n_train], X[n_train:]
y_tr, y_te = y[:n_train], y[n_train:]
print(f'训练: {len(X_tr)} | 测试: {len(X_te)}')

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score, mean_squared_error

# ─── 待测试的配置 ────────────────────────────────────────
configs = {
    '基线(原)': {'n_estimators':200, 'max_depth':8,  'min_samples_split':2, 'min_samples_leaf':5},
    '更多树':   {'n_estimators':500, 'max_depth':8,  'min_samples_split':2, 'min_samples_leaf':5},
    '更深':     {'n_estimators':200, 'max_depth':12, 'min_samples_split':2, 'min_samples_leaf':5},
    '更深更多': {'n_estimators':300, 'max_depth':12, 'min_samples_split':2, 'min_samples_leaf':8},
    '防过拟合': {'n_estimators':200, 'max_depth':6,  'min_samples_split':5, 'min_samples_leaf':10},
    '精调A':    {'n_estimators':300, 'max_depth':10, 'min_samples_split':2, 'min_samples_leaf':4},
    '精调B':    {'n_estimators':400, 'max_depth':10, 'min_samples_split':2, 'min_samples_leaf':3},
    '激进':     {'n_estimators':500, 'max_depth':None,'min_samples_split':2, 'min_samples_leaf':2},
}

results = {}
train_results = {}
print(f'\n{"="*80}')
print(f'📊 模型对比')
print(f'{"="*80}')
print(f'{"配置":<12} {"n_est":>5} {"深度":>5} {"split":>5} {"leaf":>5}  '
      f'{"MAE":>8} {"RMSE":>8} {"R²":>8} {"方向准确率":>10} {"训练R²":>8}')
print(f'{"-"*80}')

for name, params in configs.items():
    m = RandomForestRegressor(random_state=42, n_jobs=-1, **params)
    m.fit(X_tr, y_tr)
    yp = m.predict(X_te)
    yp_tr = m.predict(X_tr)

    mae = mean_absolute_error(y_te, yp)
    rmse = np.sqrt(mean_squared_error(y_te, yp))
    r2 = r2_score(y_te, yp)
    r2_tr = r2_score(y_tr, yp_tr)
    dir_acc = accuracy_score((y_te>0).astype(int), (yp>0).astype(int))

    results[name] = {'mae':mae, 'rmse':rmse, 'r2':r2, 'dir_acc':dir_acc, 'model':m}
    train_results[name] = {'r2': r2_tr}

    print(f'{name:<12} {params["n_estimators"]:>5} {str(params["max_depth"]):>5} '
          f'{params["min_samples_split"]:>5} {params["min_samples_leaf"]:>5}  '
          f'{mae:>8.4f} {rmse:>8.4f} {r2:>8.4f} {dir_acc:>10.2%} {r2_tr:>8.4f}')

# ─── 最佳模型（按R²） ────────────────────────────────────
best_name = max(results, key=lambda k: results[k]['r2'])
best_model = results[best_name]['model']
print(f'\n🏆 最佳: {best_name} (R²={results[best_name]["r2"]:.4f})')
print(f'   配置: n_estimators={best_model.n_estimators}, max_depth={best_model.max_depth}, '
      f'min_samples_split={best_model.min_samples_split}, min_samples_leaf={best_model.min_samples_leaf}')

# ─── 特征重要性 ──────────────────────────────────────────
fn = ['RS标准化','RS评分','多因子','保留','板块偏向','板块均分','涨跌幅/10','等级评分','趋势标签','布林位置','价格位置']
imp = best_model.feature_importances_; si = np.argsort(imp)[::-1]
print(f'\n🔑 特征重要性 (best={best_name}):')
for i, idx in enumerate(si):
    print(f'  {i+1:2d}. {fn[idx]:>10}  {imp[idx]:.3f}  {"█"*int(imp[idx]*50)}')

# ─── 与基线对比 ──────────────────────────────────────────
print(f'\n{"="*80}')
print(f'📊 基线 vs 最优')
print(f'{"="*80}')
base_r = results['基线(原)']; opt_r = results[best_name]
for nm, bk, ok in [('MAE',base_r['mae'],opt_r['mae']),('RMSE',base_r['rmse'],opt_r['rmse']),
                    ('R²',base_r['r2'],opt_r['r2']),('方向准确率',base_r['dir_acc'],opt_r['dir_acc'])]:
    if nm in ('MAE','RMSE'):
        chg = (bk - ok)/abs(bk)*100 if bk != 0 else 0
    else:
        chg = (ok - bk)/abs(bk)*100 if bk != 0 else 0
    a = '↑' if chg > 0 else '↓'
    print(f'  {nm:<12}  {bk:.4f} → {ok:.4f}  {a} {abs(chg):.1f}%')

# ─── 保存 ────────────────────────────────────────────────
os.makedirs('models', exist_ok=True)
for path in ['models/random_forest_optimized.pkl', 'models/random_forest_v2.pkl',
             'models/rf_cross_section.pkl', 'models/rf_stock_model.pkl']:
    pickle.dump(best_model, open(path, 'wb'))
    print(f'💾 {path}')

# ─── 结果写入文件 ───────────────────────────────────────
result = f"""🌲 随机森林迭代优化结果
====================================
时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
数据: {len(X)} 只股票截面样本 (训练{len(X_tr)} | 测试{len(X_te)})
特征: {X.shape[1]} 维

基线参数: {configs['基线(原)']}
基线性能: MAE={base_r['mae']:.4f} | R²={base_r['r2']:.4f} | 方向准确率={base_r['dir_acc']:.2%}

最优参数: {best_name}
     {best_model}
最优性能: MAE={opt_r['mae']:.4f} | R²={opt_r['r2']:.4f} | 方向准确率={opt_r['dir_acc']:.2%}

全配置对比:
"""
for name, params in configs.items():
    r = results[name]
    flag = ' ← 最优' if name == best_name else ''
    rank_info = f' (R²={r["r2"]:.4f}, 方向准确率={r["dir_acc"]:.2%})'
    result += f"  {name:<12} {params}  {rank_info}{flag}\n"

result += f"""
特征重要性 (TOP5):
"""
for i, idx in enumerate(si[:5]):
    result += f"  {i+1}. {fn[idx]} = {imp[idx]:.3f}\n"

with open('/tmp/rf_optimization_result.txt', 'w') as f:
    f.write(result)

print(f'\n💾 /tmp/rf_optimization_result.txt')
print('\n✅ 优化完成!')
