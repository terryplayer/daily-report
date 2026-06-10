#!/usr/bin/env python3
"""
🌲 Ridge回归 — 定时重训脚本（每周五15:35自动执行）
基于累积的 stock_history.json 数据，随时间推移自然提升
"""
import json, os, sys, pickle, warnings
import numpy as np
from datetime import datetime
warnings.filterwarnings('ignore')

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)
MODEL_PATH = os.path.join(WORKSPACE, 'models', 'ridge_direction.pkl')

def build_dataset():
    """从多日历史数据构建训练集"""
    with open('data/stock_history.json') as f:
        hist = json.load(f)

    dates = sorted(hist['history'].keys())
    if len(dates) < 3:
        print(f"❌ 交易日不足: {len(dates)}")
        return None, None

    X, y = [], []
    for i in range(len(dates) - 1):
        today = dates[i]
        tomorrow = dates[i + 1]
        day_data = hist['history'][today]
        next_day = hist['history'][tomorrow]

        stocks = day_data.get('stocks', {})
        next_stocks = next_day.get('stocks', {})
        bench_chg = day_data.get('benchmark', {}).get('change_pct', 0)

        for code, s in stocks.items():
            close = s.get('close', 0)
            chg = s.get('change_pct', 0)
            next_s = next_stocks.get(code, {})
            next_chg = next_s.get('change_pct', 0)

            if not close or next_chg is None: continue

            fx = [
                chg / 15,                    # 当日涨跌
                close / 100,                  # 价格归一化
                bench_chg / 5,                # 大盘涨跌
                1 if chg > 0 else 0,          # 当日是否上涨
            ]
            target = 1 if next_chg > 0 else 0
            X.append(fx)
            y.append(target)

    return np.array(X), np.array(y)


def main():
    X, y = build_dataset()
    if X is None or len(X) < 50:
        print("❌ 数据不足，跳过训练")
        sys.exit(1)

    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0, 100.0], cv=3)
    model.fit(X_scaled, y)

    scores = cross_val_score(model, X_scaled, y, cv=3, scoring='accuracy')
    up_pct = sum(y) / len(y) * 100

    print(f"📊 训练样本: {len(X)}, 上涨率: {up_pct:.0f}%")
    print(f"✅ 准确率: {scores.mean():.1%} ± {scores.std():.1%}")
    print(f"✅ 模型保存: {MODEL_PATH}")

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'model': model, 'scaler': scaler}, f)

    # 本日预测准确率（使用最新数据）
    latest = sorted([d for d in os.listdir('data/raw') if d.endswith('.json')], reverse=True)[0]
    print(f"   数据截至: {latest.replace('.json','')}")


if __name__ == '__main__':
    main()
