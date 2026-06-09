#!/usr/bin/env python3
"""
📡 Layer 1: 数据采集器 v1.1
主方案：Tushare API（日线 + daily_basic）
兜底：东方财富 API（网络不通时自动切）
输出：data/raw/YYYY-MM-DD.json（原始数据，不覆盖已有）
独立运行，不依赖任何评分逻辑
"""

import json, os, sys, time, urllib.request
from datetime import date, datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(WORKSPACE, "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# 方案A: Tushare
def fetch_tushare(date_str):
    """通过 Tushare 获取全量数据"""
    import warnings
    warnings.filterwarnings('ignore')
    import tushare as ts
    
    tk_path = os.path.join(WORKSPACE, "data", "tushare_token.txt")
    if not os.path.exists(tk_path):
        log("  ❌ Tushare token 不存在")
        return None
    
    tk = open(tk_path).read().strip()
    ts.set_token(tk)
    pro = ts.pro_api()
    
    # 日线行情
    df = pro.daily(trade_date=date_str.replace("-", ""))
    if df is None or len(df) < 1000:
        log(f"  ⚠️ Tushare 日线数据不足: {len(df) if df is not None else 0}只")
        return None
    
    log(f"  ✅ Tushare 日线: {len(df)}只")
    
    # daily_basic（PE/PB/换手率/量比）
    dfb = pro.daily_basic(
        trade_date=date_str.replace("-", ""),
        fields="ts_code,pe,pb,turnover_rate,volume_ratio,circ_mv"
    )
    has_basic = dfb is not None and len(dfb) > 1000
    basic_map = {}
    if has_basic:
        for _, r in dfb.iterrows():
            basic_map[r["ts_code"][:6]] = r
        log(f"  ✅ Tushare daily_basic: {len(basic_map)}只")
    
    # 股票名称映射
    try:
        df_name = pro.stock_basic()
        name_map = {}
        for _, r in df_name.iterrows():
            name_map[r["ts_code"][:6]] = r.get("name", "")
    except:
        name_map = {}
        log("  ⚠️ 名称映射获取失败")
    
    all_data = {}
    for _, row in df.iterrows():
        code = row["ts_code"][:6]
        b = basic_map.get(code, {})
        chg = float(row.get("pct_chg", 0))
        vol = float(row.get("vol", 0) or 0)
        
        all_data[code] = {
            "f2": float(row.get("close", 0)),        # 最新价
            "f3": chg,                                 # 涨跌幅%
            "f12": code,                               # 代码
            "f14": name_map.get(code, ""),             # 名称
            "f15": float(row.get("high", 0)),          # 最高价
            "f16": float(row.get("low", 0)),           # 最低价
            "f17": float(row.get("open", 0)),          # 今开
            "f18": float(row.get("pre_close", 0)),     # 昨收
            "f20": round(float(row.get("amount", 0) or 0) / 1e5, 4),  # 成交额(亿元) — Tushare amount 单位千元
            "f21": round(float(b.get("circ_mv", 0) or 0) / 1e8, 4) if b.get("circ_mv") else None,  # 流通市值(亿元)
            "f23": float(b.get("pb", 0)) if b.get("pb") else None,  # 市净率
            "f62": round(float(b.get("turnover_rate", 0)), 4) if b.get("turnover_rate") else round(vol / 1e8, 4),  # 换手率% 或 估算值
            "f115": None,     # 市盈率(动) — Tushare 无此字段
            "f168": round(float(b.get("volume_ratio", 0)), 4) if b.get("volume_ratio") else None,  # 量比
            "f175": float(b.get("pe", 0)) if b.get("pe") else None,  # 市盈率(静)
            "f184": None,     # ROE% — 需要额外接口
            "f100": None,     # 细分行业 — 需要额外接口
        }
    
    return all_data

# 方案B: 东方财富兜底
def fetch_eastmoney():
    """东财 API 兜底（不传日期，实时数据）"""
    all_data = {}
    url_template = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=%d&pz=100&po=1&np=1&fltt=2&invt=2"
        "&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        "&fields=f2,f3,f12,f14,f15,f16,f17,f18,f20,f21,"
        "f23,f62,f115,f168,f175,f184,f100"
    )
    
    for page in range(1, 57):
        url = url_template % page
        for retry in range(3):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                })
                resp = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
                items = json.loads(resp).get("data", {}).get("diff", [])
                if not items:
                    break
                for item in items:
                    code = item.get("f12", "")
                    if code:
                        all_data[code] = item
                if len(items) < 100:
                    break
                time.sleep(0.3)
                break
            except:
                time.sleep(1)
    
    return all_data

def normalize(raw_data):
    """包装为统一输出格式"""
    result = {
        "_meta": {
            "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "tushare" if len(raw_data) > 1000 else "eastmoney",
            "total": len(raw_data)
        }
    }
    for code, item in raw_data.items():
        stock = {"code": code}
        for field in ["f2","f3","f12","f14","f15","f16","f17","f18",
                       "f20","f21","f23","f62","f115","f168","f175","f184","f100"]:
            v = item.get(field)
            if v is None:
                stock[field] = None
            elif isinstance(v, (int, float)):
                stock[field] = round(float(v), 4)
            else:
                try:
                    stock[field] = round(float(v), 4)
                except:
                    stock[field] = str(v) if v else None
        result[code] = stock
    
    return result

def save(date_str, data):
    path = os.path.join(RAW_DIR, f"{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    kb = os.path.getsize(path) / 1024
    log(f"  ✅ 已保存: {path} ({kb:.0f}KB)")
    return path

def main():
    date_str = date.today().strftime("%Y-%m-%d")
    log(f"📡 数据采集开始: {date_str}")
    
    # 检查是否已存在
    existing = os.path.join(RAW_DIR, f"{date_str}.json")
    if os.path.exists(existing) and "--force" not in sys.argv:
        log(f"  ⏭️ 今日数据已存在 ({os.path.getsize(existing)/1024:.0f}KB)")
        log(f"  💡 加 --force 强制刷新")
        return
    
    # 方案A: Tushare
    log(f"  📡 Tushare 方案...")
    raw = fetch_tushare(date_str)
    
    # 方案B: 东财兜底
    if not raw or len(raw) < 1000:
        log(f"  📡 Tushare 不可用，切东财兜底...")
        raw = fetch_eastmoney()
    
    if not raw or len(raw) < 100:
        log(f"  ❌ 所有数据源均失败")
        return
    
    data = normalize(raw)
    stock_count = len([k for k in data if k != "_meta"])
    log(f"  ✅ 采集完成: {stock_count}只 (来源: {data['_meta']['source']})")
    
    path = save(date_str, data)
    print(f"\n[RESULT] ✅ 采集完成: {date_str} | {stock_count}只 | {data['_meta']['source']} | {path}")

if __name__ == "__main__":
    main()
