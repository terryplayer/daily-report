#!/usr/bin/env python3
"""
Tushare 数据获取脚本 — 用于日报数据源
"""

import sys
import os
import json
from datetime import datetime, timedelta

TOKEN_FILE = os.path.expanduser("~/.openclaw/workspace/data/tushare_token.txt")

# 持仓股代码（六位数格式）
WATCHLIST = [
    "603019","688381","688323","688530","688268",
    "301389","002600","603629","301396","000586","002384",
    "300433","301611","603516","300496","301171","300058","300290",
    "600330","002407","301217","002379","603318","600396","002418","000981",
    "600860","688549","600584","300604","300975","002484",
    "300196","605006",
    "000062",
    "000678",
    "000890",
    "002195",
    "002261",
    "002340",
    "002364",
    "002389",
    "002429",
    "002498",
    "002501",
    "002580",
    "002624",
    "002716",
    "300027",
    "300059",
    "300244",
    "300255",
    "300322",
    "300390",
    "300394",
    "300395",
    "300398",
    "300502",
    "300540",
    "300613",
    "300857",
    "300911",
    "301236",
    "301237",
    "301511",
    "600110",
    "600170",
    "600519",
    "600711",
    "601179",
    "603799",
    "603985",
    "688008",
    "688020",
    "688055",
    "688166",
    "688818"
]


def get_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE) as f:
        token = f.read().strip()
    return token if token else None


def init_pro():
    token = get_token()
    if not token:
        return None, "TOKEN_NOT_FOUND"
    import tushare as ts
    ts.set_token(token)
    return ts.pro_api(), None


def code_to_tscode(code):
    """把 600519 转成 600519.SH"""
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    elif code.startswith(("0", "3", "2")):
        return f"{code}.SZ"
    elif code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def safe_int(v):
    try:
        return int(v)
    except:
        return None


def safe_float(v):
    try:
        return round(float(v), 2)
    except:
        return None


def fetch_via_eastmoney(trade_date=None):
    """通过东方财富接口获取行情数据（Tushare失效时的备选#1）"""
    import urllib.request
    from datetime import datetime

    result = {"stock_data": [], "market_overview": None, "north_flow": None}
    if not trade_date:
        now = datetime.now()
        trade_date = now.strftime("%Y%m%d")
    result["trade_date"] = trade_date

    # 构建请求参数 - 上证+深证+科创50+31只持仓
    secids = ["1.000001", "0.399001", "0.399006", "1.000688"]
    seen = set()
    for code in WATCHLIST:
        prefix = "1." if code.startswith(("6", "9")) else "0."
        if code not in seen:
            secids.append(f"{prefix}{code}")
            seen.add(code)

    secid_str = ",".join(secids)
    url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={secid_str}&fields=f2,f3,f12,f14,f15,f16,f17,f18"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        items = data.get("data", {}).get("diff", [])
        stocks = []
        for item in items:
            code = item.get("f12", "")
            name = item.get("f14", "")
            price = safe_float(item.get("f2"))
            change_pct = safe_float(item.get("f3"))
            high = safe_float(item.get("f15"))
            low = safe_float(item.get("f16"))
            open_p = safe_float(item.get("f17"))
            vol = safe_float(item.get("f18"))
            if code and price:
                stocks.append({
                    "ts_code": code,
                    "name": name,
                    "close": price,
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "change_pct": change_pct,
                    "vol": vol,
                    "source": "eastmoney"
                })
        result["stock_data"] = stocks
        result["_note"] = f"东方财富接口获取 {len(stocks)} 条数据"
    except Exception as e:
        result["stock_data"] = []
        result["_error"] = str(e)

    return result


def fetch_via_tencent(trade_date=None):
    """通过腾讯财经接口获取行情数据（备选#2）"""
    import urllib.request
    from datetime import datetime

    result = {"stock_data": [], "market_overview": None, "north_flow": None}
    if not trade_date:
        now = datetime.now()
        trade_date = now.strftime("%Y%m%d")
    result["trade_date"] = trade_date

    codes = ["sh000001", "sz399001", "sz399006", "sh000688"] + \
            [f"sh{c}" if c.startswith(("6","9")) else f"sz{c}" for c in WATCHLIST]

    stocks = []
    for code in codes:
        try:
            url = f"https://qt.gtimg.cn/q={code}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=8)
            text = resp.read().decode("gbk")
            # 格式: v_sh600584="1~名称~代码~现价~昨收~开盘~...~涨跌额~涨跌幅~..."
            parts = text.split("~")
            if len(parts) > 10:
                name = parts[1] if len(parts) > 1 else ""
                price = safe_float(parts[3])
                change_pct = safe_float(parts[32]) if len(parts) > 32 else None
                high = safe_float(parts[33]) if len(parts) > 33 else None
                low = safe_float(parts[34]) if len(parts) > 34 else None
                open_p = safe_float(parts[5])
                vol = safe_float(parts[6])
                if price is not None:
                    stocks.append({
                        "ts_code": code[2:],
                        "name": name,
                        "close": price,
                        "open": open_p,
                        "high": high,
                        "low": low,
                        "change_pct": change_pct,
                        "vol": vol,
                        "source": "tencent"
                    })
        except:
            pass

    result["stock_data"] = stocks
    result["_note"] = f"腾讯接口获取 {len(stocks)} 条数据"
    return result


def get_report_data(trade_date=None):
    """
    获取日报需要的所有数据
    返回 {"stock_data": [...], "north_flow": ..., "trade_cal": {...}}
    """
    if not trade_date:
        # 默认取最近交易日（下午3点前用前一日，3点后用当日）
        now = datetime.now()
        if now.hour < 15:
            trade_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        else:
            trade_date = now.strftime("%Y%m%d")

    pro, err = init_pro()
    if err:
        return {"error": err}

    result = {"trade_date": trade_date}

    # 1. 获取持仓股行情 (daily — Tushare主力接口，含pct_chg)
    try:
        df_daily = pro.daily(trade_date=trade_date)
        if df_daily is not None and not df_daily.empty:
            ts_codes = {code_to_tscode(c) for c in WATCHLIST}
            matched = df_daily[df_daily["ts_code"].isin(ts_codes)]
            stock_list = []
            for _, row in matched.iterrows():
                stock_list.append({
                    "ts_code": row.get("ts_code"),
                    "name": None,
                    "open": safe_float(row.get("open")),
                    "high": safe_float(row.get("high")),
                    "low": safe_float(row.get("low")),
                    "close": safe_float(row.get("close")),
                    "pre_close": safe_float(row.get("pre_close")),
                    "change_pct": safe_float(row.get("pct_chg")),
                    "vol": safe_float(row.get("vol")),
                    "amount": safe_float(row.get("amount")),
                })
            result["stock_data"] = stock_list
        else:
            result["stock_data"] = []
            result["_note"] = f"交易日 {trade_date} 无数据（可能休市）"
    except Exception as e:
        result["stock_data"] = []
        result["stock_error"] = str(e)

    # 2. 北向资金流向
    try:
        df_north = pro.moneyflow_hsgt(start_date=trade_date, end_date=trade_date)
        if df_north is not None and not df_north.empty:
            row = df_north.iloc[0]
            result["north_flow"] = {
                "south_money": safe_float(row.get("south_money")),
                "north_money": safe_float(row.get("north_money")),
                "sgt": safe_float(row.get("sgt")),
                "sgt_amount": safe_float(row.get("sgt_amount")),
                "sgt_balance": safe_float(row.get("sgt_balance")),
                "hgt": safe_float(row.get("hgt")),
                "hgt_amount": safe_float(row.get("hgt_amount")),
                "hgt_balance": safe_float(row.get("hgt_balance")),
            }
        else:
            result["north_flow"] = None
    except Exception as e:
        result["north_flow"] = None
        result["north_error"] = str(e)

    # 3. 全市场概览（daily行情统计）
    try:
        df_all = pro.daily(trade_date=trade_date)
        if df_all is not None and not df_all.empty:
            total = len(df_all)
            up_count = len(df_all[df_all["pct_chg"] > 0])
            down_count = len(df_all[df_all["pct_chg"] < 0])
            flat_count = total - up_count - down_count
            total_amount = safe_float(df_all["amount"].sum())
            result["market_overview"] = {
                "total_stocks": total,
                "up_count": int(up_count),
                "down_count": int(down_count),
                "flat_count": int(flat_count),
                "total_amount_yi": round(total_amount / 1e8, 2) if total_amount else None
            }
        else:
            result["market_overview"] = None
    except Exception as e:
        result["market_overview"] = None

    # 4. 返回结果
    return result


def get_stock_names(pro):
    """获取股票名称映射 — 用 stock_basic 可能需要权限"""
    try:
        df = pro.stock_basic(list_status='L')
        return dict(zip(df["ts_code"], df["name"]))
    except:
        return {}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["report", "daily_basic", "moneyflow_hsgt", "test", "eastmoney", "tencent"])
    parser.add_argument("--trade_date", help="交易日 YYYYMMDD")
    parser.add_argument("--codes", nargs="*", help="股票代码")
    args = parser.parse_args()

    if args.action == "test":
        pro, err = init_pro()
        if err:
            print(json.dumps({"status": "error", "msg": f"Token问题: {err}"}))
        else:
            try:
                df = pro.daily_basic(trade_date=args.trade_date or "20260101", limit=1)
                print(json.dumps({"status": "ok", "msg": "连接成功"}))
            except Exception as e:
                print(json.dumps({"status": "error", "msg": str(e)}))

    elif args.action == "eastmoney":
        data = fetch_via_eastmoney(args.trade_date)
        print(json.dumps(data, ensure_ascii=False, default=str))

    elif args.action == "tencent":
        data = fetch_via_tencent(args.trade_date)
        print(json.dumps(data, ensure_ascii=False, default=str))

    elif args.action == "report":
        # Tushare优先（daily API），数据无效时降级
        data = get_report_data(args.trade_date)
        stock_data = data.get("stock_data", [])
        # Tushare daily API有pct_chg，只要有数据就算有效
        valid_tushare = len(stock_data) >= 20
        if not valid_tushare:
            # Tushare无数据，依次尝试东方财富→腾讯
            fallback = fetch_via_eastmoney(args.trade_date)
            if fallback.get("stock_data"):
                fallback["_source"] = "eastmoney"
                data = fallback
            else:
                fallback = fetch_via_tencent(args.trade_date)
                if fallback.get("stock_data"):
                    fallback["_source"] = "tencent"
                    data = fallback
                else:
                    data["_note"] = "Tushare/东方财富/腾讯均无数据"
        print(json.dumps(data, ensure_ascii=False, default=str))

    elif args.action == "daily_basic":
        pro, err = init_pro()
        if err:
            print(json.dumps({"error": err}))
            sys.exit(1)
        codes = [code_to_tscode(c) for c in (args.codes or [])]
        df = pro.daily_basic(trade_date=args.trade_date or datetime.now().strftime("%Y%m%d"))
        if codes:
            df = df[df["ts_code"].isin(codes)]
        print(df.to_json(orient="records", force_ascii=False))

    elif args.action == "moneyflow_hsgt":
        pro, err = init_pro()
        if err:
            print(json.dumps({"error": err}))
            sys.exit(1)
        td = args.trade_date or datetime.now().strftime("%Y%m%d")
        df = pro.moneyflow_hsgt(start_date=td, end_date=td)
        print(df.to_json(orient="records", force_ascii=False))
