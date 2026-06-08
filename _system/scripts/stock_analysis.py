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

# 基准指数
BENCHMARK = "sh000001"  # 上证指数

# ─── 从统一配置源加载持仓清单 ───
def load_watchlist():
    """从 config/stocks.json 加载持仓股票清单"""
    path = os.path.join(WORKSPACE, "config", "stocks.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 配置文件不存在: {path}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ 配置文件格式错误: {e}")
        return []
    watchlist = data.get("watchlist", [])
    if not watchlist:
        print(f"⚠️ 配置文件中 watchlist 为空")
    # 自动同步到 template-stocks.json（标准版报告用）
    tpl_path = os.path.join(WORKSPACE, "scripts", "template-stocks.json")
    try:
        with open(tpl_path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 同步到 template-stocks.json 失败: {e}")
    return watchlist

WATCHLIST_FULL = load_watchlist()
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
# 新增统计模型：MOM / BBW / MRD / 随机森林
# ============================================================

def calc_momentum(code, history, short_days=5, long_days=10):
    """
    动量因子 MOM
    短期动量+长期动量加权，反映趋势延续性
    返回: {'mom_short':float, 'mom_long':float, 'mom_score':float(0-100)}
    """
    dates = sorted(history.keys())
    closes = []
    for d in dates:
        if code in history[d].get('stocks', {}):
            c = history[d]['stocks'][code].get('close')
            if c: closes.append(c)
    if len(closes) < long_days + 1:
        return {'mom_short': 0, 'mom_long': 0, 'mom_score': 50}
    
    mom_short = (closes[-1] / closes[-short_days-1] - 1) * 100
    mom_long = (closes[-1] / closes[-long_days-1] - 1) * 100
    # 综合评分 (0-100): 正动量为高分
    raw = mom_short * 0.6 + mom_long * 0.4
    score = max(0, min(100, 50 + raw * 2))
    return {'mom_short': round(mom_short, 2), 'mom_long': round(mom_long, 2), 'mom_score': round(score, 1)}


def calc_bbw(code, history, period=None):
    """
    布林带宽度 BBW (Bollinger Band Width)
    BBW = (上轨 - 下轨) / 中轨
    收窄→变盘信号，拓宽→趋势延续
    自动适配数据量: period = min(10, len(closes)-1)
    """
    import math
    dates = sorted(history.keys())
    closes = []
    for d in dates:
        if code in history[d].get('stocks', {}):
            c = history[d]['stocks'][code].get('close')
            if c: closes.append(c)
    if period is None:
        period = min(10, max(5, len(closes) - 1))
    if len(closes) < period:
        return {'bbw': 0, 'bbw_percentile': 50, 'signal': '数据不足', 'period': period}
    
    recent = closes[-period:]
    ma = sum(recent) / period
    variance = sum((x - ma) ** 2 for x in recent) / period
    std = math.sqrt(variance)
    upper = ma + 2 * std
    lower = ma - 2 * std
    bbw = (upper - lower) / ma * 100 if ma > 0 else 0
    
    # 历史百分位估算（用最近period/2个窗口的历史数据）
    bbws = []
    for i in range(period, len(closes) - period // 2):
        seg = closes[i-period:i]
        m = sum(seg) / period
        s = math.sqrt(sum((x-m)**2 for x in seg) / period)
        bw = ((m+2*s) - (m-2*s)) / m * 100 if m > 0 else 0
        bbws.append(bw)
    
    percentile = 50
    if bbws:
        count_below = sum(1 for b in bbws if b <= bbw)
        percentile = count_below / len(bbws) * 100
    
    if percentile < 20:
        signal = '⚠️ 布林带极致收窄·可能变盘'
    elif percentile < 40:
        signal = '🔍 布林带收窄·关注方向'
    elif percentile > 80:
        signal = '📊 布林带拓宽·趋势延续'
    else:
        signal = '⚪ 正常'
    
    return {'bbw': round(bbw, 2), 'bbw_percentile': round(percentile, 1), 'signal': signal}


def calc_mrd(code, history, period=None):
    """
    均值回归偏离度 MRD (Mean Reversion Deviation)
    MRD = (close - MA) / MA * 100
    >+8% 超买，<-8% 超卖
    自动适配数据量: period = min(20, len(closes)-1, 10)
    """
    dates = sorted(history.keys())
    closes = []
    for d in dates:
        if code in history[d].get('stocks', {}):
            c = history[d]['stocks'][code].get('close')
            if c: closes.append(c)
    # 自动适配窗口: 最多10天（当前数据有限）
    if period is None:
        period = min(10, max(5, len(closes) - 1))
    if len(closes) < period + 1:
        return {'mrd_20': 0, 'signal': '数据不足', 'period': period}
    
    ma = sum(closes[-period:]) / period
    cur = closes[-1]
    mrd = (cur - ma) / ma * 100
    
    if mrd > 8:
        signal = '🔴 超买 · 回归概率高'
    elif mrd > 4:
        signal = '🟡 偏高 · 关注压力'
    elif mrd < -8:
        signal = '🟢 超卖 · 反弹概率高'
    elif mrd < -4:
        signal = '🔵 偏低 · 关注支撑'
    else:
        signal = '⚪ 正常区间'
    
    return {'mrd_20': round(mrd, 2), 'signal': signal}


def calc_combined_signals(code, history):
    """
    计算单只股票的四个新模型信号
    返回 dict
    """
    mom = calc_momentum(code, history)
    bbw = calc_bbw(code, history)
    mrd = calc_mrd(code, history)
    return {
        'momentum': mom,
        'bbw': bbw,
        'mrd': mrd
    }


def calc_all_new_signals(history):
    """计算所有持仓的新模型信号"""
    result = {}
    for stock in WATCHLIST_FULL:
        code = stock["code"]
        signals = calc_combined_signals(code, history)
        result[code] = {"name": stock["name"], "sector": stock["sector"], "signals": signals}
    return result


def calc_random_forest_prediction(history, target_date=None):
    """
    随机森林多因子分类器（进阶模型-第四阶段）
    
    使用全部因子: RS排名 | MOM_5 | MOM_10 | BBW | MRD | RSI | 成交量比 |
                  北向资金方向 | 隔夜外盘 | PCR
    预测: 次日涨/跌/平 三分类
    
    需要 sklearn，如不可用则返回 None
    需要积累至少 60 个交易日的训练数据（目前约10天，数据积累中）
    
    当前状态：数据积累中，暂不生效
    """
    return {
        'status': 'data_accumulating',
        'message': f'需要至少60个交易日数据，当前{len(history)}天',
        'accuracy_estimate': None
    }


# ============================================================
# 统一模型评估框架（所有报告共用）
# ============================================================
# 提供标准化评分(0-100)和信号，保证盘前/午间/收盘/周复盘一致

SIGNAL_STRONG_BUY = {'icon': '🔴🔴', 'label': '强势', 'color': '#f85149', 'action': '超配/持有'}
SIGNAL_BUY = {'icon': '🔴', 'label': '偏强', 'color': '#d9a52e', 'action': '增配/关注'}
SIGNAL_NEUTRAL = {'icon': '⚪', 'label': '中性', 'color': '#8b949e', 'action': '标配/观望'}
SIGNAL_SELL = {'icon': '🟢', 'label': '偏弱', 'color': '#58a6ff', 'action': '减配/减仓'}
SIGNAL_STRONG_SELL = {'icon': '🟢🟢', 'label': '弱势', 'color': '#3fb950', 'action': '低配/止损'}

def normalize_score(raw, min_v=-100, max_v=100):
    """将任意范围的值映射到0-100"""
    if max_v == min_v:
        return 50
    clipped = max(min_v, min(max_v, raw))
    return round((clipped - min_v) / (max_v - min_v) * 100, 1)

def score_to_signal(score):
    """将0-100评分转为标准信号"""
    if score >= 80: return SIGNAL_STRONG_BUY
    if score >= 60: return SIGNAL_BUY
    if score >= 40: return SIGNAL_NEUTRAL
    if score >= 20: return SIGNAL_SELL
    return SIGNAL_STRONG_SELL

def score_to_action(score):
    """评分转操作建议"""
    if score >= 80: return '⭐超配'
    if score >= 60: return '↑增配'
    if score >= 40: return '—标配'
    if score >= 20: return '↓减配'
    return '末低配'

def calc_historical_similarity_score(history, model_cache=None):
    """
    计算历史相似度得分（RAG增强维度）。
    
    从当前行情特征检索历史相似交易日，
    按各板块在相似日的涨跌情况输出得分 0~100。
    
    这是统一模型的新增维度："历史记忆"。
    """
    try:
        from scripts.rag_memory import search_similar_trading_days
    except ImportError:
        return {'score': 50.0, 'sector_scores': {}, 'note': 'rag_not_available'}
    
    if not history:
        return {'score': 50.0, 'sector_scores': {}, 'note': 'no_history'}
    
    # 构建当前日特征
    dates = sorted(history.keys())
    latest = dates[-1] if dates else None
    if not latest:
        return {'score': 50.0, 'sector_scores': {}, 'note': 'no_dates'}
    
    last_day = history[latest]
    stocks_data = last_day.get('stocks', {})
    bench = last_day.get('benchmark', {})
    
    if not isinstance(stocks_data, dict):
        return {'score': 50.0, 'sector_scores': {}, 'note': 'bad_stocks_format'}
    
    # 计算 sector 变化
    sector_changes = {}
    sec_stock_count = {}
    for code, s in stocks_data.items():
        if not isinstance(s, dict):
            continue
        sec = '其他'
        for stock in WATCHLIST_FULL:
            if stock['code'] == code:
                sec = stock['sector']
                break
        chg = s.get('change_pct', 0) or s.get('pct_chg', 0)
        if isinstance(chg, (int, float)):
            sector_changes.setdefault(sec, []).append(chg)
    
    sector_avg_changes = {}
    for sec, changes in sector_changes.items():
        sector_avg_changes[sec] = round(sum(changes) / len(changes), 2) if changes else 0
    
    # 市场宽度
    all_changes = []
    for s in stocks_data.values():
        if isinstance(s, dict):
            chg = s.get('change_pct', 0) or s.get('pct_chg', 0)
            if isinstance(chg, (int, float)):
                all_changes.append(chg)
    market_breadth = sum(1 for c in all_changes if c > 0) / max(len(all_changes), 1) if all_changes else 0.5
    
    # 从 cache 读 RS 均分
    rs_scores = {}
    if model_cache:
        rs_list = model_cache.get('rs_ranking', [])
        rs_by_sector = {}
        for r in rs_list:
            sec = r.get('sector', '其他')
            rs_by_sector.setdefault(sec, []).append(r.get('rs_score', 50))
        for sec, vals in rs_by_sector.items():
            rs_scores[sec] = sum(vals) / len(vals)
    
    # 构建 day_data
    bench_pct = bench.get('change_pct', 0)
    if isinstance(bench_pct, str):
        try:
            bench_pct = float(bench_pct.rstrip('%'))
        except:
            bench_pct = 0
    
    day_data = {
        'date': latest,
        'benchmark': {'change_pct': bench_pct},
        'actual_sector_changes': sector_avg_changes,
        'market_breadth': market_breadth,
        'sectors': {},
    }
    
    # 用平均涨跌作为 RS 模拟
    for sec, avg_ch in sector_avg_changes.items():
        rs = rs_scores.get(sec)
        day_data['sectors'][sec] = {
            'rs_mean': rs if rs else (50 + avg_ch * 3),
        }
    
    # 搜索相似日
    SECTOR_ORDER = ['科技/半导体', '通信/电子', 'AI/数字经济', '化工/材料', '能源/公用事业']
    all_sectors = set(list(sector_avg_changes.keys()) + SECTOR_ORDER)
    
    similar = search_similar_trading_days(day_data, top_k=5, exclude_date=latest)
    
    if not similar:
        return {'score': 50.0, 'sector_scores': {}, 'note': 'no_similar_days'}
    
    total_sim = sum(d['score'] for d in similar)
    if total_sim <= 0:
        return {'score': 50.0, 'sector_scores': {}, 'note': 'zero_similarity'}
    
    # 计算各板块加权得分
    sector_scores = {}
    for sec in all_sectors:
        weighted_change = 0.0
        wsum = 0.0
        for d in similar:
            w = d['score'] / total_sim
            change = d.get('actual_sector_changes', {}).get(sec, 0)
            weighted_change += change * w
            wsum += w
        
        # 转成 0~100 分
        sec_score = 50 + weighted_change * 3
        sec_score = max(0, min(100, sec_score))
        sector_scores[sec] = round(sec_score, 1)
    
    global_score = sum(sector_scores.values()) / max(len(sector_scores), 1)
    
    return {
        'score': round(global_score, 1),
        'sector_scores': sector_scores,
        'similar_days': [d['date'] for d in similar[:3]],
        'note': 'ok',
    }


def get_model_summary(history, rs_results=None, sector_rotation=None):
    """
    统一模型摘要：计算所有模型的最新信号
    返回结构：
    {
        'composite': {板块: {score, signal, action, confidence}},
        'models': {
            'rs': {板块: score},
            'momentum': {板块: score},
            'mrd': {板块: score},
            'multi_factor': {板块: score},
            'rotation': {板块: score},
        },
        'all_stocks': [每只股票的综合评分]
    }
    """
    result = {'models': {}, 'composite': {}, 'all_stocks': []}
    
    # 1. RS相对强度
    rs_list = calc_rs(history, days=5) if rs_results is None else rs_results
    rs_by_sector = {}
    for r in rs_list or []:
        sec = r.get('sector', '其他')
        if sec not in rs_by_sector:
            rs_by_sector[sec] = []
        rs_by_sector[sec].append(r.get('rs_score', 50))
    
    # RS归一化：原始值范围约-10~+5，映射到0-100
    all_rs_vals = [v for vals in rs_by_sector.values() for v in vals]
    rs_min, rs_max = min(all_rs_vals), max(all_rs_vals) if all_rs_vals else (-10, 10)
    rs_range = max(rs_max - rs_min, 1)
    
    rs_scores = {}
    for sec, scores in rs_by_sector.items():
        avg_raw = sum(scores) / len(scores) if scores else rs_min
        # 归一化到0-100
        normalized = (avg_raw - rs_min) / rs_range * 100
        rs_scores[sec] = round(normalized, 1)
    result['models']['rs'] = rs_scores
    
    # 2. MOM动量
    mom_by_sector = {}
    for stock in WATCHLIST_FULL:
        code, sec = stock['code'], stock['sector']
        mom = calc_momentum(code, history)
        if sec not in mom_by_sector:
            mom_by_sector[sec] = []
        mom_by_sector[sec].append(mom['mom_score'])
    
    mom_scores = {}
    for sec, scores in mom_by_sector.items():
        mom_scores[sec] = round(sum(scores) / len(scores), 1) if scores else 50
    result['models']['momentum'] = mom_scores
    
    # 3. MRD均值回归
    mrd_by_sector = {}
    for stock in WATCHLIST_FULL:
        code, sec = stock['code'], stock['sector']
        mrd = calc_mrd(code, history)
        # MRD得分：偏离越大得分越低（超买/超卖都是风险）
        dev = abs(mrd.get('mrd_20', 0))
        mrd_score = max(0, 100 - dev * 3)  # 偏离1%扣3分
        if sec not in mrd_by_sector:
            mrd_by_sector[sec] = []
        mrd_by_sector[sec].append(mrd_score)
    
    mrd_scores = {}
    for sec, scores in mrd_by_sector.items():
        mrd_scores[sec] = round(sum(scores) / len(scores), 1) if scores else 50
    result['models']['mrd'] = mrd_scores
    
    # 4. 多因子评分
    mf = calc_multi_factor_score(history, rs_results)
    mf_by_sector = {}
    for s in mf.get('stocks', []):
        sec = s.get('sector', '其他')
        if sec not in mf_by_sector:
            mf_by_sector[sec] = []
        mf_by_sector[sec].append(s.get('total_score', 50))
    
    # 多因子归一化：原始值范围约2-7，映射到0-100
    all_mf_vals = [v for vals in mf_by_sector.values() for v in vals]
    mf_min, mf_max = min(all_mf_vals), max(all_mf_vals) if all_mf_vals else (0, 10)
    mf_range = max(mf_max - mf_min, 1)
    
    mf_scores = {}
    for sec, scores in mf_by_sector.items():
        avg_raw = sum(scores) / len(scores) if scores else mf_min
        normalized = (avg_raw - mf_min) / mf_range * 100
        mf_scores[sec] = round(normalized, 1)
    result['models']['multi_factor'] = mf_scores
    
    # 5. 行业轮动
    if sector_rotation is None:
        sr = calc_sector_rotation()
    else:
        sr = sector_rotation
    rot_scores = {}
    for item in sr.get('rotation', []):
        sec = item.get('sector', '')
        conf = item.get('confidence', 50)
        if sec:
            rot_scores[sec] = conf
    result['models']['rotation'] = rot_scores
    
    # 6. 历史相似度 (RAG增强)
    try:
        hist_scores = calc_historical_similarity_score(history, model_cache=result)
        result['models']['historical'] = hist_scores.get('sector_scores', {})
    except Exception:
        result['models']['historical'] = {}
    
    # 7. 综合评分（所有模型加权平均）
    all_sectors = set()
    for m in result['models'].values():
        all_sectors.update(m.keys())
    
    # 权重：历史相似度占10%，其余等比缩减
    weights = {
        'rs': 0.23, 'momentum': 0.18, 'mrd': 0.09,
        'multi_factor': 0.27, 'rotation': 0.13, 'historical': 0.10
    }
    
    for sec in all_sectors:
        total_w = 0
        weighted = 0
        for model_name, w in weights.items():
            if sec in result['models'].get(model_name, {}):
                weighted += result['models'][model_name][sec] * w
                total_w += w
        composite = round(weighted / total_w, 1) if total_w > 0 else 50
        signal = score_to_signal(composite)
        action = score_to_action(composite)
        result['composite'][sec] = {
            'score': composite,
            'signal': signal['icon'],
            'label': signal['label'],
            'action': action,
            'models': {m: result['models'].get(m, {}).get(sec, None) for m in weights}
        }
    
    return result


def format_model_summary_text(model_summary):
    """将模型摘要格式化为文本（用于飞书推送）"""
    lines = []
    lines.append('板块评分 & 模型信号')
    lines.append(f'{"板块":<10}{"综合":>5}{"RS":>5}{"动量":>5}{"MRD":>5}{"多因子":>5}{"轮动":>5}{"历史":>5}{"配置":>6}')
    
    for sec, info in sorted(model_summary['composite'].items()):
        ms = info['models']
        score = info['score']
        sig = info['signal']
        action = info['action']
        def _fmt(v):
            if v is None:
                return '  -'
            try:
                return f'{v:>4.0f}'
            except:
                return '  -'
        rs_v = _fmt(ms.get('rs'))
        mom_v = _fmt(ms.get('momentum'))
        mrd_v = _fmt(ms.get('mrd'))
        mf_v = _fmt(ms.get('multi_factor'))
        rot_v = _fmt(ms.get('rotation'))
        hist_v = _fmt(ms.get('historical'))
        lines.append(f'{sec:<10}{score:>5.0f}{rs_v:>5}{mom_v:>5}{mrd_v:>5}{mf_v:>5}{rot_v:>5}{hist_v:>5}{action:>6}')
    
    return '\n'.join(lines)


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
