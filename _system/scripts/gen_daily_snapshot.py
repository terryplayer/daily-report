#!/usr/bin/env python3
"""
📸 每日行情快照生成器 — 收盘后自动运行

功能:
  1. 从 stock_history.json 提取当日行情
  2. 从 cache 提取板块分析数据
  3. 读取盘前预测 + 收盘对比
  4. 生成结构化快照 → 索引到 FAISS（供RAG检索）
  5. 回填历史交易日快照（首次运行）

运行位置: workspace 根目录
   python3 scripts/gen_daily_snapshot.py
   python3 scripts/gen_daily_snapshot.py --backfill  # 回填历史
"""

import json, os, sys
from datetime import date, datetime
from typing import Optional, List, Dict, Any

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

HISTORY_FILE = os.path.join(WORKSPACE, "data", "stock_history.json")
SECTOR_ORDER = ['科技/半导体', '通信/电子', 'AI/数字经济', '化工/材料', '能源/公用事业']


def _load_json(path, default=None):
    """安全加载 JSON 文件"""
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            pass
    return default if default is not None else {}


def build_snapshot_from_history(day_data: dict) -> Optional[dict]:
    """
    从 stock_history 中的单日数据构建快照。
    day_data = history['20260604'] 格式。
    """
    if not day_data or not isinstance(day_data, dict):
        return None

    date_str = day_data.get('date', '')
    if not date_str:
        return None

    bench = day_data.get('benchmark', {})
    stocks = day_data.get('stocks', {})

    if isinstance(stocks, dict):
        stocks_dict = stocks
    else:
        stocks_dict = {}

    # --- 基准指数 ---
    benchmark = {}
    if isinstance(bench, dict):
        if 'change_pct' in bench:
            benchmark['change_pct'] = float(bench['change_pct'])
        else:
            benchmark = {k: float(v) for k, v in bench.items() if isinstance(v, (int, float))}
        if 'close' in bench:
            benchmark['close'] = bench['close']

    # --- 按板块汇总 ---
    # 先加载持仓配置获取板块归属
    stocks_config = _load_json(os.path.join(WORKSPACE, "config", "stocks.json"), {}).get('watchlist', [])

    # code -> sector 映射
    code_to_sector = {}
    for s in stocks_config:
        code_to_sector[s['code']] = s.get('sector', '其他')

    # 按板块汇总
    sector_data = {}
    for code, stock in stocks_dict.items():
        if not isinstance(stock, dict):
            continue
        sec = code_to_sector.get(code, '其他')
        if sec not in sector_data:
            sector_data[sec] = {
                'stocks_count': 0,
                'changes': [],
                'codes': [],
            }
        sector_data[sec]['stocks_count'] += 1
        chg = stock.get('change_pct', 0) or stock.get('pct_chg', 0)
        if isinstance(chg, (int, float)):
            sector_data[sec]['changes'].append(chg)
        sector_data[sec]['codes'].append(code)

    # 计算板块平均涨跌
    actual_sector_changes = {}
    for sec, data in sector_data.items():
        if data['changes']:
            actual_sector_changes[sec] = round(sum(data['changes']) / len(data['changes']), 2)
        else:
            actual_sector_changes[sec] = 0.0

    # --- 市场宽度 ---
    all_changes = []
    for stock in stocks_dict.values():
        if isinstance(stock, dict):
            chg = stock.get('change_pct', 0) or stock.get('pct_chg', 0)
            if isinstance(chg, (int, float)):
                all_changes.append(chg)
    market_breadth = sum(1 for c in all_changes if c > 0) / max(len(all_changes), 1) if all_changes else 0.5

    # --- 从 cache 读取RS/动量均分（如果有）---
    cache = _load_json('/tmp/stock_analysis_cache.json')
    sectors_from_cache = {}
    if cache:
        rs_list = cache.get('rs_ranking', [])
        mom_data = cache.get('stock_momentum', {})

        for sec in SECTOR_ORDER + ['其他']:
            sec_stocks = [s for s in rs_list if s.get('sector') == sec]
            rs_vals = [s.get('rs_score', 50) for s in sec_stocks if s.get('rs_score') is not None]
            mom_vals = []
            for s in sec_stocks:
                code = s.get('code', '')
                mom = mom_data.get(code, {})
                if isinstance(mom, dict):
                    mom_vals.append(mom.get('mom_score', 50))
                elif isinstance(mom, (int, float)):
                    mom_vals.append(mom)

            sectors_from_cache[sec] = {
                'rs_mean': round(sum(rs_vals) / len(rs_vals), 1) if rs_vals else 50,
                'mom_mean': round(sum(mom_vals) / len(mom_vals), 1) if mom_vals else 50,
                'stocks_count': len(sec_stocks),
            }

    # --- 读取盘前预测 ---
    predictions = _load_json('/tmp/premarket-predictions.json')
    pred_data = predictions if predictions else {}
    raw_sectors = pred_data.get('sectors', [])
    # sectors 可能是 dict {板块名: 预测数据} 或 list [{name, direction, ...}]
    if isinstance(raw_sectors, dict):
        pred_sectors = raw_sectors
    elif isinstance(raw_sectors, list):
        pred_sectors = {}
        for item in raw_sectors:
            if isinstance(item, dict):
                name = item.get('name', item.get('sector', ''))
                if name:
                    pred_sectors[name] = item
    else:
        pred_sectors = {}

    # 计算预测准确率
    prediction_accuracy = None
    if pred_sectors and actual_sector_changes:
        correct = 0
        total = 0
        for sec_name, sec_pred in pred_sectors.items():
            direction = ''
            if isinstance(sec_pred, dict):
                direction = sec_pred.get('direction', '—')
            elif isinstance(sec_pred, str):
                direction = sec_pred
            else:
                direction = str(sec_pred) if sec_pred else '—'
            actual = actual_sector_changes.get(sec_name, 0)
            if direction in ('↑', 'up', '看涨') and actual > 0:
                correct += 1
            elif direction in ('↓', 'down', '看跌') and actual < 0:
                correct += 1
            elif direction in ('—', 'neutral', '中性'):
                correct += 1  # 中性不算错
            total += 1
        prediction_accuracy = (correct / total) > 0.5 if total > 0 else None

    # --- 读取随机森林预测 ---
    rf_pred = {}
    if cache:
        rf_data = cache.get('random_forest', cache.get('rf_prediction', {}))
        if isinstance(rf_data, dict):
            rf_pred = rf_data

    # --- 组装快照 ---
    snapshot = {
        'date': date_str,
        'benchmark': benchmark,
        'sectors': sectors_from_cache or {sec: {'rs_mean': 50, 'mom_mean': 50, 'stocks_count': 0} for sec in SECTOR_ORDER},
        'actual_sector_changes': actual_sector_changes,
        'rf_prediction': {
            'direction': rf_pred.get('direction', 'unknown'),
            'probability': rf_pred.get('probability', rf_pred.get('prob', 0.5)),
        },
        'prediction_accuracy': prediction_accuracy,
        'market_breadth': round(market_breadth, 4),
        'north_flow': 0,  # 北向资金暂缺
    }

    return snapshot


def generate_and_index(date_str: str = None) -> bool:
    """
    生成快照并索引到FAISS。
    如果 date_str 为空，用最新交易日。
    """
    from scripts.rag_memory import index_daily_snapshot

    hist = _load_json(HISTORY_FILE, {}).get('history', {})

    if not hist:
        print('❌ 无历史数据')
        return False

    # 确定日期
    dates = sorted(hist.keys())
    target_date = date_str or dates[-1]

    if target_date not in hist:
        print(f'❌ 未找到 {target_date} 的数据')
        return False

    day_data = hist[target_date]
    snapshot = build_snapshot_from_history(day_data)

    if not snapshot:
        print(f'❌ {target_date} 数据格式不支持')
        return False

    # 索引到FAISS
    ok = index_daily_snapshot(snapshot)
    if ok:
        print(f'✅ {target_date}: 快照已索引')
        print(f'   上证 {snapshot["benchmark"].get("sz_sh", 0):+.2f}%')
        secs = list(snapshot['actual_sector_changes'].items())[:3]
        for sec, ch in secs:
            print(f'   {sec}: {ch:+.2f}%')
    else:
        print(f'⏭️  {target_date}: 已存在，跳过')

    return ok


def backfill_all() -> int:
    """回填所有历史交易日"""
    from scripts.rag_memory import index_daily_snapshot

    hist = _load_json(HISTORY_FILE, {}).get('history', {})
    dates = sorted(hist.keys())

    count = 0
    for d in dates:
        day_data = hist[d]
        snapshot = build_snapshot_from_history(day_data)
        if snapshot:
            ok = index_daily_snapshot(snapshot)
            if ok:
                count += 1
                print(f'✅ {d}: 已索引')

    print(f'\n📊 回填完成: {count}/{len(dates)} 个交易日')
    return count


# ─── CLI ──────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description='📸 每日行情快照生成器')
    parser.add_argument('--backfill', action='store_true', help='回填所有历史交易日')
    parser.add_argument('--date', help='指定日期 (YYYYMMDD)')
    parser.add_argument('--show', action='store_true', help='显示快照内容（不索引）')

    args = parser.parse_args()

    if args.backfill:
        backfill_all()
        return

    if args.date:
        hist = _load_json(HISTORY_FILE, {}).get('history', {})
        day_data = hist.get(args.date)
        if not day_data:
            print(f'❌ 未找到 {args.date}')
            return
        snapshot = build_snapshot_from_history(day_data)
        if args.show:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        else:
            generate_and_index(args.date)
        return

    # 默认：最新交易日
    if args.show:
        hist = _load_json(HISTORY_FILE, {}).get('history', {})
        dates = sorted(hist.keys())
        if dates:
            snapshot = build_snapshot_from_history(hist[dates[-1]])
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        generate_and_index()


if __name__ == '__main__':
    main()
