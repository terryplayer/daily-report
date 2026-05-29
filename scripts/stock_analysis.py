#!/usr/bin/env python3
"""
股票分析模块 — RS相对强度 + 波动率异常预警

用法:
  python3 stock_analysis.py           # 输出完整分析报告 (JSON)
  python3 stock_analysis.py --rs      # 仅RS排名
  python3 stock_analysis.py --vol     # 仅波动率预警
  python3 stock_analysis.py --update  # 更新历史数据（收盘后执行）

数据存储: data/stock_history.json
"""

import sys, os, json, math
from datetime import datetime, timedelta

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(WORKSPACE, "data", "stock_history.json")
sys.path.insert(0, WORKSPACE)

# 持仓股完整列表（含代码和名称）
WATCHLIST_FULL = [
    # 科技/半导体
    {"code": "688549", "name": "中巨芯-U", "sector": "科技/半导体"},
    {"code": "603019", "name": "电科蓝天(中科曙光)", "sector": "科技/半导体"},
    {"code": "688381", "name": "帝奥微", "sector": "科技/半导体"},
    {"code": "688323", "name": "瑞华泰", "sector": "科技/半导体"},
    {"code": "688530", "name": "欧莱新材", "sector": "科技/半导体"},
    {"code": "688268", "name": "华特气体", "sector": "科技/半导体"},
    {"code": "301389", "name": "隆扬电子", "sector": "科技/半导体"},
    {"code": "002600", "name": "领益智造", "sector": "科技/半导体"},
    {"code": "603629", "name": "利通电子", "sector": "科技/半导体"},
    {"code": "301396", "name": "宏景科技", "sector": "科技/半导体"},
    {"code": "600584", "name": "长电科技", "sector": "科技/半导体"},
    {"code": "300604", "name": "长川科技", "sector": "科技/半导体"},
    # 通信/电子
    {"code": "000586", "name": "汇源通信", "sector": "通信/电子"},
    {"code": "002384", "name": "东山精密", "sector": "通信/电子"},
    {"code": "300433", "name": "蓝思科技", "sector": "通信/电子"},
    {"code": "301611", "name": "珂玛科技", "sector": "通信/电子"},
    {"code": "603516", "name": "淳中科技", "sector": "通信/电子"},
    {"code": "300975", "name": "商络电子", "sector": "通信/电子"},
    {"code": "002484", "name": "江海股份", "sector": "通信/电子"},
    # AI/数字经济
    {"code": "300496", "name": "中科创达", "sector": "AI/数字经济"},
    {"code": "301171", "name": "易点天下", "sector": "AI/数字经济"},
    {"code": "300058", "name": "蓝色光标", "sector": "AI/数字经济"},
    {"code": "300290", "name": "荣科科技", "sector": "AI/数字经济"},
    # 化工/材料
    {"code": "600330", "name": "天通股份", "sector": "化工/材料"},
    {"code": "002407", "name": "多氟多", "sector": "化工/材料"},
    {"code": "300196", "name": "长海股份", "sector": "化工/材料"},
    {"code": "605006", "name": "山东玻纤", "sector": "化工/材料"},
    # 能源/公用事业
    {"code": "603318", "name": "水发燃气", "sector": "能源/公用事业"},
    {"code": "600396", "name": "华电辽能", "sector": "能源/公用事业"},
    {"code": "002418", "name": "康盛股份", "sector": "能源/公用事业"},
    # 其他
    {"code": "000981", "name": "山子高科", "sector": "其他"},
    {"code": "600860", "name": "京城股份", "sector": "其他"},
]

# 基准指数
BENCHMARK = "sh000001"  # 上证指数

# 用于引用TS代码的纯数字代码
WATCHLIST_CODES = [s["code"] for s in WATCHLIST_FULL]


def load_history():
    """读取历史数据"""
    if not os.path.exists(HISTORY_FILE):
        return {"history": {}, "metadata": {"last_updated": None}}
    with open(HISTORY_FILE) as f:
        return json.load(f)


def save_history(data):
    """保存历史数据"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_via_sina():
    """通过新浪财经接口获取实时行情（Tushare限速时用）"""
    import urllib.request
    from datetime import datetime

    now = datetime.now()
    if now.hour < 15:
        trade_date = (now - timedelta(days=1)).strftime("%Y%m%d")
    else:
        trade_date = now.strftime("%Y%m%d")

    # 构建所有指数+个股的sina代码列表
    sina_codes = [
        ("sh000001", "上证指数"), ("sz399001", "深证成指"),
        ("sz399006", "创业板指"), ("sh000688", "科创50"),
    ]
    code_to_stock = {}
    for s in WATCHLIST_FULL:
        c = s["code"]
        prefix = "sh" if c.startswith(("6", "9")) else "sz"
        sina_codes.append((f"{prefix}{c}", s["name"]))
        code_to_stock[c] = s

    list_str = ",".join([c for c, _ in sina_codes])
    url = f"https://hq.sinajs.cn/list={list_str}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn"
    })
    resp = urllib.request.urlopen(req, timeout=15)
    text = resp.read().decode("gbk")

    day_data = {
        "date": trade_date,
        "benchmark": {"close": None, "change_pct": None},
        "stocks": {}
    }

    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("=\\”")
        if len(parts) < 2:
            continue
        var_name = parts[0].replace("var hq_str_", "")
        values = parts[1].rstrip("\";").split(",")
        try:
            current = float(values[3]) if values[3] else 0
            prev_close = float(values[2]) if values[2] else 0
            change_pct = round((current - prev_close) / prev_close * 100, 2) if prev_close else 0
        except:
            continue

        if var_name in ["sh000001", "sz399001", "sz399006", "sh000688"]:
            day_data["benchmark"] = {
                "close": round(current, 2),
                "change_pct": change_pct
            }
        else:
            for code, info in code_to_stock.items():
                prefix = "sh" if code.startswith(("6", "9")) else "sz"
                if var_name == f"{prefix}{code}":
                    day_data["stocks"][code] = {
                        "close": round(current, 2),
                        "change_pct": change_pct
                    }
                    break

    return day_data


def fetch_today_data():
    """获取今日收盘数据（优先Tushare，失败则用新浪web）"""
    from scripts.tushare_fetch import init_pro, code_to_tscode, safe_float
    from datetime import datetime

    now = datetime.now()
    if now.hour < 15:
        trade_date = (now - timedelta(days=1)).strftime("%Y%m%d")
    else:
        trade_date = now.strftime("%Y%m%d")

    # 检查今天是否已更新
    hist = load_history()
    if hist["metadata"].get("last_updated") == trade_date:
        print(f"今日({trade_date})数据已存在，跳过")
        return None

    # 尝试Tushare
    pro, err = init_pro()
    if err:
        print(f"Tushare不可用({err})，回退到新浪接口...")
        return _save_web_data(trade_date, hist)

    try:
        df = pro.daily(trade_date=trade_date)
        if df is None or df.empty:
            print(f"Tushare无数据，回退到新浪接口...")
            return _save_web_data(trade_date, hist)

        day_data = {"date": trade_date, "benchmark": {}, "stocks": {}}

        # 基准指数
        try:
            df_idx = pro.index_daily(ts_code="000001.SH", trade_date=trade_date)
            if df_idx is not None and not df_idx.empty:
                row = df_idx.iloc[0]
                day_data["benchmark"] = {
                    "close": safe_float(row.get("close")),
                    "change_pct": safe_float(row.get("pct_chg")),
                }
            else:
                # 无ts_code参数时尝试全量
                df_idx_all = pro.index_daily(trade_date=trade_date)
                if df_idx_all is not None and not df_idx_all.empty:
                    sh_row = df_idx_all[df_idx_all["ts_code"] == "000001.SH"]
                    if not sh_row.empty:
                        row = sh_row.iloc[0]
                        day_data["benchmark"] = {
                            "close": safe_float(row.get("close")),
                            "change_pct": safe_float(row.get("pct_chg")),
                        }
        except Exception as idx_err:
            print(f"基准指数获取失败: {idx_err}")

        ts_codes = {code_to_tscode(c): c for c in WATCHLIST_CODES}
        for ts_code, orig_code in ts_codes.items():
            match = df[df["ts_code"] == ts_code]
            if not match.empty:
                row = match.iloc[0]
                day_data["stocks"][orig_code] = {
                    "close": safe_float(row.get("close")),
                    "change_pct": safe_float(row.get("pct_chg")),
                }

        return _save_day_data(trade_date, day_data, hist)

    except Exception as e:
        print(f"Tushare报错({e})，回退到新浪接口...")
        return _save_web_data(trade_date, hist)


def _save_web_data(trade_date, hist):
    """通过新浪接口获取并保存"""
    from datetime import datetime
    if now.hour < 15 if False else True:
        pass
    print(f"通过新浪获取 {trade_date} 数据...")
    day_data = fetch_via_sina()
    if not day_data or not day_data.get("benchmark", {}).get("close"):
        print("新浪获取失败，可能休市")
        return None
    return _save_day_data(trade_date, day_data, hist)


def _save_day_data(trade_date, day_data, hist):
    """保存当日数据到历史"""
    if hist["history"].get(trade_date):
        print(f"覆盖已有数据: {trade_date}")
    hist["history"][trade_date] = day_data

    # 保留最近60日
    sorted_dates = sorted(hist["history"].keys(), reverse=True)
    for old_date in sorted_dates[60:]:
        del hist["history"][old_date]

    hist["metadata"]["last_updated"] = trade_date
    save_history(hist)
    print(f"✅ 已更新 {trade_date} 数据，共 {len(hist['history'])} 个交易日")
    return day_data


def calc_rs(history, days=5):
    """
    RS相对强度计算

    RS值 = 个股期间涨幅 - 基准指数期间涨幅
    归一化: 将所有RS值映射到 -10 ~ +10 区间
    排名: 从强到弱排序
    """
    if not history or len(history) < 2:
        return []

    sorted_dates = sorted(history.keys(), reverse=True)

    # 取最近 days 个交易日
    recent_dates = sorted_dates[:min(days, len(sorted_dates))]
    if len(recent_dates) < 2:
        return []

    start_date = recent_dates[-1]
    end_date = recent_dates[0]

    # 计算基准指数期间涨幅
    bench_start = history[start_date]["benchmark"]["close"]
    bench_end = history[end_date]["benchmark"]["close"]
    if not bench_start or not bench_end or bench_start == 0:
        return []

    bench_change = (bench_end - bench_start) / bench_start * 100

    results = []
    for stock in WATCHLIST_FULL:
        code = stock["code"]
        s_start = history[start_date]["stocks"].get(code, {}).get("close")
        s_end = history[end_date]["stocks"].get(code, {}).get("close")
        if s_start and s_end and s_start > 0:
            stock_change = (s_end - s_start) / s_start * 100
            rs_value = round(stock_change - bench_change, 2)
            results.append({
                "code": code,
                "name": stock["name"],
                "sector": stock["sector"],
                "rs_value": rs_value,
                "stock_change_pct": round(stock_change, 2),
                "bench_change_pct": round(bench_change, 2),
            })

    # 按RS值从高到低排序
    results.sort(key=lambda x: x["rs_value"], reverse=True)

    # 归一化(映射到 -10~10) 并分档
    if results:
        max_abs = max(abs(r["rs_value"]) for r in results) or 1
        for r in results:
            normalized = round(r["rs_value"] / max_abs * 10, 1)
            r["rs_score"] = normalized
            if normalized >= 3:
                r["rank"] = "A+"
                r["signal"] = "强势 持有/加仓"
            elif normalized >= 1:
                r["rank"] = "A"
                r["signal"] = "偏强 持有"
            elif normalized >= -1:
                r["rank"] = "B"
                r["signal"] = "中性 观察"
            elif normalized >= -3:
                r["rank"] = "C"
                r["signal"] = "偏弱 关注风险"
            else:
                r["rank"] = "D"
                r["signal"] = "弱势 建议减仓/止损"

    return results


def calc_volatility_alerts(history, window=20, threshold=1.5):
    """
    波动率异常预警

    原理:
    1. 对每只股票，取最近 window 个交易日的涨跌幅序列
    2. 计算均值和标准差
    3. 如果今日涨跌幅超出 (均值 ± threshold × 标准差)，触发预警

    threshold=1.5 表示偏离正常波动1.5倍标准差以上即预警
    threshold=2.0 表示重度预警
    """
    if not history or len(history) < 3:
        return []

    sorted_dates = sorted(history.keys(), reverse=True)
    recent_dates = sorted_dates[:min(window + 1, len(sorted_dates))]

    if len(recent_dates) < 3:
        return []

    alerts = []
    today = recent_dates[0]

    for stock in WATCHLIST_FULL:
        code = stock["code"]

        # 收集该股票在窗口内的涨跌幅序列
        change_history = []
        for dt in recent_dates:
            cp = history[dt]["stocks"].get(code, {}).get("change_pct")
            if cp is not None:
                change_history.append(cp)

        if len(change_history) < 3:
            continue

        # 今日涨跌幅
        today_change = change_history[0]
        if today_change is None:
            continue

        # 计算均值 + 标准差
        n = len(change_history)
        mean = sum(change_history) / n
        variance = sum((x - mean) ** 2 for x in change_history) / n
        stddev = math.sqrt(variance)

        if stddev == 0:
            continue

        # 偏离倍数
        if mean >= 0:
            deviation = (today_change - mean) / stddev
        else:
            deviation = abs(today_change - mean) / stddev

        if deviation >= threshold:
            level = "🔴 高危" if deviation >= 2.0 else "🟡 关注"
            alerts.append({
                "code": code,
                "name": stock["name"],
                "sector": stock["sector"],
                "today_change": round(today_change, 2),
                "mean_change": round(mean, 2),
                "stddev": round(stddev, 2),
                "deviation_ratio": round(deviation, 1),
                "level": level,
                "suggestion": "触发减仓/止损建议" if deviation >= 2.0 else "需重点关注"
            })

    # 按偏离倍数从高到低排序
    alerts.sort(key=lambda x: x["deviation_ratio"], reverse=True)
    return alerts


def get_rs_text_section(rs_results, top_n=5, bottom_n=5):
    """生成RS排名的文字摘要"""
    if not rs_results:
        return "（暂无足够历史数据计算RS排名）"

    lines = ["━━━ RS相对强度排名 ━━━"]

    lines.append("\n🏆 RS榜 TOP{}（最强势，趋势仍在）".format(top_n))
    for i, r in enumerate(rs_results[:top_n], 1):
        lines.append(f"  {i}. {r['name']}({r['code']})  RS:{r['rs_value']:+.1f}  [{r['rank']} {r['signal']}]")

    lines.append("\n🚫 RS榜 BOTTOM{}（最弱势，考虑减仓）".format(bottom_n))
    for i, r in enumerate(rs_results[-bottom_n:], 1):
        idx = len(rs_results) - bottom_n + i
        lines.append(f"  {i}. {r['name']}({r['code']})  RS:{r['rs_value']:+.1f}  [{r['rank']} {r['signal']}]")

    lines.append(f"\n📊 基准: 上证指数 期间涨幅: {rs_results[0]['bench_change_pct']:+.2f}%")
    return "\n".join(lines)


def get_vol_text_section(vol_alerts, top_n=10):
    """生成波动率预警的文字摘要"""
    if not vol_alerts:
        return "✅ 今日无波动异常（所有持仓均在正常波动范围内）"

    lines = ["━━━ 波动率异常预警 ━━━"]
    for v in vol_alerts[:top_n]:
        lines.append(
            f"  {v['level']} {v['name']}({v['code']}) "
            f"今日{v['today_change']:+.2f}% "
            f"(正常波动{v['mean_change']:+.2f}%±{v['stddev']:.2f}%, "
            f"偏离{v['deviation_ratio']}倍标准差) → {v['suggestion']}"
        )
    return "\n".join(lines)


# ============================================================
# 新增模型二：多因子评分模型
# ============================================================

# ============================================================
# 技术面量化指标
# ============================================================

def calc_ma(data_list, period):
    """简单移动平均"""
    if len(data_list) < period:
        return None
    return sum(data_list[-period:]) / period


def calc_rsi(data_list, period=14):
    """RSI相对强弱指标"""
    if len(data_list) < period + 1:
        return None
    gains, losses = [], []
    for i in range(len(data_list) - period, len(data_list)):
        if i == 0:
            continue
        diff = data_list[i] - data_list[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    if not gains or not losses:
        return None
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def calc_macd(data_list, fast=12, slow=26, signal=9):
    """MACD指标"""
    if len(data_list) < slow + signal:
        return None, None, None
    def ema(data, n):
        if len(data) < n:
            return None
        k = 2 / (n + 1)
        r = data[0]
        for v in data[1:]:
            r = v * k + r * (1 - k)
        return r
    dif = ema(data_list, fast) - ema(data_list, slow)
    if dif is None:
        return None, None, None
    dif_values = []
    for i in range(signal, len(data_list) + 1):
        segment = data_list[:i]
        if len(segment) >= slow:
            d = ema(segment, fast) - ema(segment, slow)
            if d is not None:
                dif_values.append(d)
    if len(dif_values) < signal:
        return None, None, None
    dea = ema(dif_values, signal)
    macd_val = (dif_values[-1] - dea) * 2 if dea else None
    return round(dif_values[-1] if dif_values else 0, 2), round(dea or 0, 2), round(macd_val or 0, 2)


def calc_bollinger(data_list, period=20, std_mult=2):
    """布林带"""
    if len(data_list) < period:
        return None, None, None
    import math
    recent = data_list[-period:]
    ma = sum(recent) / period
    variance = sum((x - ma) ** 2 for x in recent) / period
    std = math.sqrt(variance)
    upper = round(ma + std_mult * std, 2)
    lower = round(ma - std_mult * std, 2)
    return upper, round(ma, 2), lower


def calc_kdj(data_list, period=9):
    """KDJ随机指标"""
    if len(data_list) < period:
        return None, None, None
    recent = data_list[-period:]
    low = min(recent)
    high = max(recent)
    if high == low:
        return 50, 50, 50
    rsv = (data_list[-1] - low) / (high - low) * 100
    k = round(2/3 * 50 + 1/3 * rsv, 1)
    d = round(2/3 * 50 + 1/3 * k, 1)
    j = round(3 * k - 2 * d, 1)
    return k, d, j


def get_tech_signals(code, history):
    """获取某只股票的技术面信号汇总"""
    sorted_dates = sorted(history.keys(), reverse=True)
    closes = []
    for dt in sorted_dates:
        c = history[dt]["stocks"].get(code, {}).get("close")
        if c is not None:
            closes.append(c)
    closes.reverse()
    if len(closes) < 5:
        return {"status": f"数据不足({len(closes)}天)", "data_days": len(closes)}
    signals = {
        "close": closes[-1], "data_days": len(closes),
        "ma5": calc_ma(closes, min(5, len(closes))),
        "ma10": calc_ma(closes, min(10, len(closes))) if len(closes) >= 10 else None,
        "ma20": calc_ma(closes, min(20, len(closes))) if len(closes) >= 20 else None,
        "rsi14": calc_rsi(closes, min(14, len(closes)-1)) if len(closes) >= 15 else None,
        "macd": calc_macd(closes),
        "bollinger": calc_bollinger(closes, min(20, len(closes))),
        "kdj": calc_kdj(closes, min(9, len(closes))),
    }
    notes = []
    if signals["rsi14"] is not None:
        if signals["rsi14"] >= 70: notes.append(f"RSI({signals['rsi14']})超买⚠️")
        elif signals["rsi14"] <= 30: notes.append(f"RSI({signals['rsi14']})超卖💡")
        else: notes.append(f"RSI({signals['rsi14']})中性")
    if signals["macd"] and signals["macd"][0] is not None:
        d, dea, _ = signals["macd"]
        notes.append(f"MACD{'金叉' if d > dea else '死叉'}({d}/{dea})")
    if signals["bollinger"] and signals["bollinger"][0] is not None:
        u, m, l = signals["bollinger"]
        if closes[-1] >= u: notes.append(f"突破布林上轨")
        elif closes[-1] <= l: notes.append(f"触及布林下轨")
    if signals["kdj"][0] is not None:
        k, d, j = signals["kdj"]
        if k > 80: notes.append(f"KDJ超买({k}/{d})")
        elif k < 20: notes.append(f"KDJ超卖({k}/{d})")
    signals["signal"] = " | ".join(notes) if notes else "信号中性"
    return signals


def calc_all_tech_signals(history):
    """计算所有持仓股票的技术面信号"""
    result = {}
    for stock in WATCHLIST_FULL:
        code = stock["code"]
        signals = get_tech_signals(code, history)
        result[code] = {"name": stock["name"], "sector": stock["sector"], "signals": signals}
    return result


# ============================================================
# 多因子评分模型
# ============================================================

def calc_multi_factor_score(history, rs_results=None):
    """
    多因子评分模型

    对每只持仓股，从5个维度打分，加权求和:
    1. 动量因子 (25%) — RS相对强度 (来自现有计算)
    2. 趋势因子 (20%) — 短期趋势方向 (最近3日涨跌方向一致性)
    3. 波动因子 (15%) — 波动稳定性 (波动小=高分, 波动大=低分)
    4. 资金因子 (20%) — 量能配合 (放量上涨/缩量下跌=高分)
    5. 估值因子 (20%) — PE估值水平 (粗略, 无历史数据时用change_pct替代)

    总分 = 加权后归一化到 0-100
    评级: A(≥75) B(60-74) C(40-59) D(<40)
    """
    if not history or len(history) < 2:
        return {"stocks": [], "summary": "数据不足"}

    sorted_dates = sorted(history.keys(), reverse=True)
    top_n_dates = sorted_dates[:min(5, len(sorted_dates))]

    # 如果没有传入RS结果，就先算一下
    if rs_results is None:
        rs_results = calc_rs(history, days=5)
    rs_map = {r["code"]: r for r in (rs_results or [])}

    scores = []
    for stock in WATCHLIST_FULL:
        code = stock["code"]

        # --- 1. 动量分 (weight 25%) ---
        rs_info = rs_map.get(code)
        if rs_info:
            momentum_score = max(0, min(10, (rs_info["rs_score"] + 10) / 2))  # -10~10 → 0~10
            momentum_note = f"RS:{rs_info['rs_value']:+.1f} [{rs_info['rank']}]"
        else:
            momentum_score = 5
            momentum_note = "RS数据不足"

        # --- 2. 趋势分 (weight 20%) ---
        # 看最近3个交易日涨跌方向一致性
        recent_changes = []
        for d in top_n_dates:
            cp = history[d]["stocks"].get(code, {}).get("change_pct")
            if cp is not None:
                recent_changes.append(cp)

        if len(recent_changes) >= 2:
            # 连续上涨或涨多跌少 → 高分
            up_count = sum(1 for c in recent_changes if c > 0)
            trend_score = up_count / len(recent_changes) * 10
            if trend_score >= 7:
                trend_note = f"近{len(recent_changes)}日中{up_count}天上涨"
            elif trend_score >= 4:
                trend_note = f"近{len(recent_changes)}日涨跌各半"
            else:
                trend_note = f"近{len(recent_changes)}日仅{up_count}天上涨"
        else:
            trend_score = 5
            trend_note = "趋势数据不足"

        # --- 3. 波动分 (weight 15%) ---
        if len(recent_changes) >= 3:
            avg_abs = sum(abs(c) for c in recent_changes) / len(recent_changes)
            # 日均波动 < 3% → 稳定高分; > 7% → 过山车低分
            if avg_abs < 2:
                vol_score = 9
                vol_note = f"低波动(均{avg_abs:.1f}%)"
            elif avg_abs < 4:
                vol_score = 7
                vol_note = f"正常波动(均{avg_abs:.1f}%)"
            elif avg_abs < 6:
                vol_score = 5
                vol_note = f"波动较大(均{avg_abs:.1f}%)"
            else:
                vol_score = 3
                vol_note = f"高波动⚠️(均{avg_abs:.1f}%)"
        else:
            vol_score = 5
            vol_note = "波动数据不足"

        # --- 4. 资金分 (weight 20%) ---
        # 用换手率变化 + 量能判断
        vol_signals = []
        for d in top_n_dates[:3]:  # 最近3日
            s = history[d]["stocks"].get(code, {})
            cp = s.get("change_pct")
            tr = s.get("turnover_rate")
            if cp is not None and tr is not None:
                if cp > 0 and tr > 3:
                    vol_signals.append(1)   # 放量上涨↗
                elif cp > 0 and tr <= 3:
                    vol_signals.append(0.5)  # 缩量上涨
                elif cp < 0 and tr > 3:
                    vol_signals.append(0)    # 放量下跌↘
                elif cp < 0 and tr <= 3:
                    vol_signals.append(0.3)  # 缩量下跌

        if vol_signals:
            fund_score = sum(vol_signals) / len(vol_signals) * 10
            fund_note = f"量能得分{fund_score:.0f}/10"
        else:
            # 没有换手率数据，用涨跌幅方向粗略判断
            if recent_changes:
                last_chg = recent_changes[0]
                if last_chg > 0:
                    fund_score = 6
                    fund_note = "今日上涨资金偏多"
                elif last_chg < -3:
                    fund_score = 3
                    fund_note = "今日大跌资金流出"
                else:
                    fund_score = 5
                    fund_note = "资金信号中性"
            else:
                fund_score = 5
                fund_note = "资金数据不足"

        # --- 5. 估值分 (weight 20%) ---
        # 简单用最新change_pct的负值反向: 跌越多说明估值回归越多
        # 更精确的需要PE/PB数据
        if recent_changes:
            last_chg = recent_changes[0]
        else:
            last_chg = 0
        # 粗略: 近期累计跌幅大 → 估值回归 → 高分
        cumul_chg = sum(recent_changes) if recent_changes else 0
        if cumul_chg < -15:
            val_score = 8
            val_note = f"深度回调(近{cumul_chg:.0f}%)估值压力释放"
        elif cumul_chg < -8:
            val_score = 6
            val_note = f"较大回调(近{cumul_chg:.0f}%)"
        elif cumul_chg < 0:
            val_score = 5
            val_note = f"小幅回调(近{cumul_chg:.0f}%)"
        elif cumul_chg < 10:
            val_score = 4
            val_note = f"累计上涨(近{cumul_chg:.0f}%)关注高估风险"
        else:
            val_score = 3
            val_note = f"大幅上涨(近{cumul_chg:.0f}%)警惕估值偏高"

        # --- 总分 ---
        total = (
            momentum_score * 0.25 +
            trend_score * 0.20 +
            vol_score * 0.15 +
            fund_score * 0.20 +
            val_score * 0.20
        )
        total = round(total, 1)

        if total >= 7.5:
            rating = "A"
            rating_label = "推荐"
        elif total >= 6.0:
            rating = "B"
            rating_label = "关注"
        elif total >= 4.0:
            rating = "C"
            rating_label = "观望"
        else:
            rating = "D"
            rating_label = "回避"

        scores.append({
            "code": code,
            "name": stock["name"],
            "sector": stock["sector"],
            "total_score": total,
            "rating": rating,
            "rating_label": rating_label,
            "factors": {
                "momentum": {"score": round(momentum_score, 1), "note": momentum_note, "weight": "25%"},
                "trend": {"score": round(trend_score, 1), "note": trend_note, "weight": "20%"},
                "volatility": {"score": round(vol_score, 1), "note": vol_note, "weight": "15%"},
                "capital": {"score": round(fund_score, 1), "note": fund_note, "weight": "20%"},
                "valuation": {"score": round(val_score, 1), "note": val_note, "weight": "20%"},
            }
        })

    # 按总分排序
    scores.sort(key=lambda x: x["total_score"], reverse=True)

    # 板块汇总
    sector_summary = {}
    for s in scores:
        sec = s["sector"]
        if sec not in sector_summary:
            sector_summary[sec] = {"count": 0, "avg_score": 0, "top_rating": "C"}
        sector_summary[sec]["count"] += 1

    for sec, info in sector_summary.items():
        sec_scores = [s["total_score"] for s in scores if s["sector"] == sec]
        info["avg_score"] = round(sum(sec_scores) / len(sec_scores), 1)
        best = max(s["rating"] for s in scores if s["sector"] == sec)
        info["top_rating"] = best

    return {
        "stocks": scores,
        "sector_summary": sector_summary,
        "num_scored": len(scores),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }


def get_multi_score_text(scores_data):
    """生成多因子评分的文字摘要"""
    stocks = scores_data.get("stocks", [])
    if not stocks:
        return "（暂无足够数据计算多因子评分）"

    lines = ["━━━ 多因子评分排名（动量25%+趋势20%+波动15%+资金20%+估值20%）━━━"]

    lines.append("\n【行业评分汇总】")
    sec_summary = scores_data.get("sector_summary", {})
    for sec, info in sorted(sec_summary.items(), key=lambda x: x[1]["avg_score"], reverse=True):
        lines.append(f"  {sec}: 均分{info['avg_score']} | {info['count']}只 | 最优评级{info['top_rating']}")

    lines.append("\n【个股评分 TOP5】")
    for s in stocks[:5]:
        f = s["factors"]
        lines.append(
            f"  {s['name']}({s['code']})  ⭐{s['total_score']} [{s['rating']} {s['rating_label']}]"
        )

    lines.append("\n【个股评分 BOTTOM5】")
    for s in stocks[-5:]:
        f = s["factors"]
        lines.append(
            f"  {s['name']}({s['code']})  ⭐{s['total_score']} [{s['rating']} {s['rating_label']}]"
        )

    return "\n".join(lines)


# ============================================================
# 新增模型一：行业轮动模型（美林时钟改良版）
# ============================================================

# 经济周期阶段定义
CYCLE_PHASES = {
    "recovery": {  # 复苏: 经济扩张 + 通胀温和
        "label": "📈 复苏期",
        "desc": "经济增长上行，通胀温和，流动性宽松",
        "allocation": {
            "科技/半导体": "超配(成长弹性)",
            "AI/数字经济": "超配(高成长赛道)",
            "通信/电子": "标配",
            "化工/材料": "标配",
            "能源/公用事业": "低配",
            "其他": "标配"
        },
        "top_sectors": ["科技/半导体", "AI/数字经济"],
        "avoid": ["能源/公用事业"],
        "tactical": "成长风格优于价值，科技板块中期看好"
    },
    "overheat": {  # 过热: 经济扩张 + 通胀高企
        "label": "🔥 过热期",
        "desc": "经济增长强劲，通胀上升，政策可能收紧",
        "allocation": {
            "科技/半导体": "标配(精选)",
            "AI/数字经济": "标配",
            "通信/电子": "标配",
            "化工/材料": "超配(大宗商品受益)",
            "能源/公用事业": "超配(通胀受益)",
            "其他": "标配"
        },
        "top_sectors": ["化工/材料", "能源/公用事业"],
        "avoid": [],
        "tactical": "价值/周期风格优于成长，关注资源板块"
    },
    "stagflation": {  # 滞胀: 经济收缩 + 通胀高企
        "label": "⛽ 滞胀期",
        "desc": "经济下行，通胀高企，政策两难",
        "allocation": {
            "科技/半导体": "低配(估值承压)",
            "AI/数字经济": "低配",
            "通信/电子": "低配",
            "化工/材料": "标配(必需)",
            "能源/公用事业": "超配(防御+通胀受益)",
            "其他": "标配"
        },
        "top_sectors": ["能源/公用事业"],
        "avoid": ["科技/半导体", "AI/数字经济"],
        "tactical": "防御为上，超配公用事业和高股息"
    },
    "recession": {  # 衰退: 经济收缩 + 通胀下行
        "label": "❄️ 衰退期",
        "desc": "经济下行，通胀回落，政策宽松预期",
        "allocation": {
            "科技/半导体": "标配(等待右侧)",
            "AI/数字经济": "标配(政策受益)",
            "通信/电子": "标配",
            "化工/材料": "低配",
            "能源/公用事业": "超配(防御)",
            "其他": "超配(金融/高股息)"
        },
        "top_sectors": ["能源/公用事业"],
        "avoid": ["化工/材料"],
        "tactical": "防御为主，逐步布局利率敏感型板块"
    }
}


def calc_sector_rotation(macro_input=None):
    """
    行业轮动模型 — 基于宏观数据判断当前经济周期

    参数 macro_input (dict):
      - pmi_trend: "扩张" | "收缩" (或 PMI数值)
      - cpi_level: "高" | "中" | "低" (或 CPI数值)
      - policy: "宽松" | "中性" | "收紧"
      - confidence: "高" | "中" | "低" (数据置信度)

    如果 macro_input 为 None，返回模型框架说明
    """
    if macro_input is None:
        return {
            "status": "need_input",
            "message": "请提供宏观数据以判断周期阶段",
            "required_fields": ["pmi_trend (扩张/收缩或数值)", "cpi_level (高/中/低)", "policy (宽松/中性/收紧)"],
            "phases": {k: {"label": v["label"], "desc": v["desc"], "top_sectors": v["top_sectors"], "avoid": v["avoid"]}
                       for k, v in CYCLE_PHASES.items()}
        }

    # 判断经济周期阶段
    pmi = macro_input.get("pmi_trend", "扩张")
    cpi = macro_input.get("cpi_level", "中")
    policy = macro_input.get("policy", "中性")

    # Simple logic for phase determination
    is_expanding = pmi in ["扩张", "expanding"] or (isinstance(pmi, (int, float)) and pmi >= 50)
    is_high_inflation = cpi in ["高", "high"] or (isinstance(cpi, (int, float)) and cpi >= 3)
    is_tightening = policy in ["收紧", "tightening"]
    is_easing = policy in ["宽松", "easing"]

    if is_expanding and not is_high_inflation:
        phase = "recovery"
    elif is_expanding and is_high_inflation:
        phase = "overheat"
    elif not is_expanding and is_high_inflation:
        phase = "stagflation"
    else:  # not expanding and not high inflation
        phase = "recession"

    phase_info = CYCLE_PHASES[phase]

    # 生成输出
    result = {
        "status": "ok",
        "phase": phase,
        "phase_label": phase_info["label"],
        "phase_desc": phase_info["desc"],
        "tactical_advice": phase_info["tactical"],
        "allocation": phase_info["allocation"],
        "top_sectors": phase_info["top_sectors"],
        "avoid_sectors": phase_info.get("avoid", []),
        "determined_by": {
            "pmi_trend": pmi,
            "cpi_level": cpi,
            "policy": policy
        },
        "confidence": macro_input.get("confidence", "中"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    # 如果有模型评分数据，可以交叉验证
    return result


def get_rotation_text(rotation_data):
    """生成行业轮动建议的文字摘要"""
    if rotation_data.get("status") == "need_input":
        return (
            "📊 行业轮动模型待激活\n"
            "请提供以下宏观数据：\n"
            f"- PMI趋势（扩张/收缩）\n"
            f"- CPI水平（高/中/低）\n"
            f"- 货币政策（宽松/中性/收紧）\n"
            f"\n可参考的周期阶段：\n" +
            "\n".join(f"  {v['label']}: {v['desc']}" for v in CYCLE_PHASES.values())
        )

    lines = ["━━━ 行业轮动模型（美林时钟改良版）━━━"]
    lines.append(f"\n【当前判断: {rotation_data['phase_label']}】")
    lines.append(f"{rotation_data['phase_desc']}")
    lines.append(f"\n判断依据: PMI={rotation_data['determined_by']['pmi_trend']}, "
                 f"CPI={rotation_data['determined_by']['cpi_level']}, "
                 f"政策={rotation_data['determined_by']['policy']}")
    lines.append(f"\n【配置建议】")
    for sector, alloc in rotation_data["allocation"].items():
        if "超配" in alloc:
            lines.append(f"  🔴 {sector}: {alloc}")
        elif "低配" in alloc:
            lines.append(f"  🟢 {sector}: {alloc}")
        else:
            lines.append(f"  ⚪ {sector}: {alloc}")

    lines.append(f"\n【战术要点】{rotation_data['tactical_advice']}")

    if rotation_data.get("top_sectors"):
        lines.append(f"\n✅ 关注板块: {', '.join(rotation_data['top_sectors'])}")
    if rotation_data.get("avoid_sectors"):
        lines.append(f"❌ 回避板块: {', '.join(rotation_data['avoid_sectors'])}")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rs", action="store_true", help="仅输出RS排名")
    parser.add_argument("--vol", action="store_true", help="仅输出波动预警")
    parser.add_argument("--score", action="store_true", help="仅输出多因子评分")
    parser.add_argument("--rotation", action="store_true", help="输出行业轮动模型框架")
    parser.add_argument("--macro", type=str, help="行业轮动: JSON宏观经济数据")
    parser.add_argument("--update", action="store_true", help="更新历史数据")
    parser.add_argument("--days", type=int, default=5, help="RS计算周期(天)")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()

    if args.update:
        fetch_today_data()
        sys.exit(0)

    # 行业轮动模型
    if args.rotation or args.macro:
        macro_data = json.loads(args.macro) if args.macro else None
        rotation = calc_sector_rotation(macro_data)
        if args.json:
            print(json.dumps(rotation, ensure_ascii=False, indent=2))
        else:
            print(get_rotation_text(rotation))
        sys.exit(0)

    hist = load_history()
    history = hist.get("history", {})

    if not history or len(history) < 2:
        print(json.dumps({
            "status": "error",
            "message": f"历史数据不足 (当前 {len(history)} 个交易日)，请先执行 python3 stock_analysis.py --update"
        }, ensure_ascii=False))
        sys.exit(1)

    output = {}
    if args.vol:
        vol_alerts = calc_volatility_alerts(history)
        output["volatility_alerts"] = vol_alerts
    elif args.rs:
        rs_results = calc_rs(history, days=args.days)
        output["rs_ranking"] = rs_results
    elif args.score:
        multi_scores = calc_multi_factor_score(history)
        output["multi_factor_scores"] = multi_scores
        output["text_multi"] = get_multi_score_text(multi_scores)
    else:
        # 完整分析
        rs_results = calc_rs(history, days=args.days)
        vol_alerts = calc_volatility_alerts(history)
        output["rs_ranking"] = rs_results
        output["volatility_alerts"] = vol_alerts
        output["text_rs"] = get_rs_text_section(rs_results)
        output["text_vol"] = get_vol_text_section(vol_alerts)

        # 多因子评分
        try:
            multi_scores = calc_multi_factor_score(history)
            output["multi_factor_scores"] = multi_scores
            output["text_multi"] = get_multi_score_text(multi_scores)
            
            # 板块动量排名（从强到弱）
            sec_sum = multi_scores.get("sector_summary", {})
            sec_rank = sorted(sec_sum.items(), key=lambda x: x[1].get("avg_score", 0), reverse=True)
            output["sector_ranking"] = [
                {"sector": s[0], "avg_score": s[1]["avg_score"], "count": s[1]["count"], "top_rating": s[1]["top_rating"]}
                for s in sec_rank
            ]
            # 板块动量标签
            if len(sec_rank) >= 2:
                output["sector_momentum"] = {
                    "top_sectors": [s[0] for s in sec_rank[:2]],
                    "bottom_sectors": [s[0] for s in sec_rank[-2:]],
                    "spread": round(sec_rank[0][1]["avg_score"] - sec_rank[-1][1]["avg_score"], 1) if sec_rank else 0
                }
        except Exception as e:
            output["multi_factor_scores"] = []
            output["text_multi"] = f"（多因子评分暂不可用: {e}）"

        # 技术面量化指标
        try:
            tech_signals = calc_all_tech_signals(history)
            output["tech_signals"] = tech_signals
        except Exception as e:
            output["tech_signals"] = {}

        # 个股动量维度（趋势斜率/量价比/支撑压力）
        try:
            stock_signals = {}
            # history已经是hist["history"]，直接使用
            dates = sorted(history.keys())
            for stock in WATCHLIST_FULL:
                code = stock["code"]
                # 收集该股票所有交易日数据
                prices = []
                vols = []
                for d in dates[-10:]:  # 最近10个交易日
                    s = history[d].get("stocks", {}).get(code)
                    if s and s.get("close"):
                        prices.append({"date": d, "close": s["close"], "vol": s.get("vol", 0)})
                        if s.get("vol"):
                            vols.append(s["vol"])
                
                signal = {}
                
                if len(prices) >= 3:
                    # ① 趋势斜率：最近3天收盘价的平均变化率
                    recent = prices[-3:]
                    changes = []
                    for i in range(1, len(recent)):
                        prev = recent[i-1]["close"]
                        curr = recent[i]["close"]
                        if prev and prev > 0:
                            changes.append((curr - prev) / prev * 100)
                    if changes:
                        slope = round(sum(changes) / len(changes), 2)
                        signal["trend_slope_3d"] = slope
                        if slope > 2:
                            signal["trend_label"] = "强势上攻"
                        elif slope > 0.8:
                            signal["trend_label"] = "震荡偏强"
                        elif slope > -0.8:
                            signal["trend_label"] = "横盘震荡"
                        elif slope > -2:
                            signal["trend_label"] = "震荡偏弱"
                        else:
                            signal["trend_label"] = "弱势下行"
                    
                    # ② 量价配合（如有成交量数据）
                    vols_present = [v["vol"] for v in prices if v.get("vol")]
                    if vols_present:
                        last5_vols = [v["vol"] for v in prices[-5:] if v.get("vol")]
                        avg_vol = sum(last5_vols) / len(last5_vols) if last5_vols else 0
                        latest_vol = prices[-1].get("vol", 0)
                        latest_close = prices[-1]["close"]
                        prev_close = prices[-2]["close"] if len(prices) >= 2 else latest_close
                        price_change = (latest_close - prev_close) / prev_close * 100 if prev_close else 0
                        vol_ratio = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 0
                        signal["vol_ratio_5d"] = vol_ratio
                        if price_change > 0.5 and vol_ratio > 1.2:
                            signal["volume_price"] = "放量上攻"
                        elif price_change > 0.5 and 0 < vol_ratio < 0.8:
                            signal["volume_price"] = "缩量反弹"
                        elif price_change < -0.5 and vol_ratio > 1.2:
                            signal["volume_price"] = "放量下跌"
                        elif price_change < -0.5 and 0 < vol_ratio < 0.8:
                            signal["volume_price"] = "缩量回调"
                        else:
                            signal["volume_price"] = "量价常态"
                    
                    # ③ 支撑/压力
                    prices_10d = [p["close"] for p in prices]
                    if prices_10d:
                        high_10d = max(prices_10d)
                        low_10d = min(prices_10d)
                        current = prices_10d[-1]
                        signal["support_10d"] = round(low_10d, 2)
                        signal["resistance_10d"] = round(high_10d, 2)
                        if high_10d > low_10d:
                            pos = round((current - low_10d) / (high_10d - low_10d) * 100, 1)
                            signal["position_pct"] = pos
                            if pos <= 20:
                                signal["position_label"] = "靠近支撑"
                            elif pos >= 80:
                                signal["position_label"] = "靠近压力"
                            else:
                                signal["position_label"] = "区间中段"
                
                stock_signals[code] = signal
            
            output["stock_momentum"] = stock_signals
        except Exception as e:
            output["stock_momentum"] = {}
            output["_stock_momentum_error"] = str(e)

    if args.json or not args.rs and not args.vol:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if args.rs:
            print(get_rs_text_section(rs_results))
        if args.vol:
            print(get_vol_text_section(vol_alerts))
        if args.score:
            print(get_multi_score_text(multi_scores))
