#!/usr/bin/env python3
"""
宏观数据获取模块 — PMI / CPI / PPI / GDP / 社融

用法:
  python3 macro_fetch.py              # 获取所有宏观数据
  python3 macro_fetch.py --pmi        # 仅PMI
  python3 macro_fetch.py --cpi        # 仅CPI
  python3 macro_fetch.py --json       # JSON输出
  python3 macro_fetch.py --rotation   # 输出行业轮动建议
  python3 macro_fetch.py --cache      # 使用缓存

数据缓存: data/macro_cache.json
"""

import sys, os, json
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(WORKSPACE, "data", "macro_cache.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/"
}


def _fetch_json(url):
    from urllib.request import Request, urlopen
    req = Request(url, headers=HEADERS)
    resp = urlopen(req, timeout=15)
    return json.loads(resp.read())


def _safe_float(v, default=None):
    try:
        return round(float(v), 1)
    except:
        return default


def fetch_pmi():
    """制造业PMI + 非制造业PMI"""
    try:
        url = 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_PMI&columns=ALL&pageSize=6&pageNumber=1&sortColumns=REPORT_DATE&sortTypes=-1'
        data = _fetch_json(url)
        if data.get("success") and data.get("result", {}).get("data"):
            rows = data["result"]["data"]
            result = []
            for r in rows[:3]:
                result.append({
                    "date": r.get("TIME", ""),
                    "制造业PMI": _safe_float(r.get("MAKE_INDEX")),
                    "非制造业PMI": _safe_float(r.get("NMAKE_INDEX")),
                })
            return {"status": "ok", "data": result}
        return {"status": "error", "message": "无数据"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def fetch_cpi():
    """CPI居民消费价格指数"""
    try:
        url = 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_CPI&columns=ALL&pageSize=6&pageNumber=1&sortColumns=REPORT_DATE&sortTypes=-1'
        data = _fetch_json(url)
        if data.get("success") and data.get("result", {}).get("data"):
            rows = data["result"]["data"]
            result = []
            for r in rows[:3]:
                result.append({
                    "date": r.get("TIME", ""),
                    "CPI同比%": _safe_float(r.get("NATIONAL_SAME")),
                    "CPI环比%": _safe_float(r.get("NATIONAL_SEQUENTIAL")),
                })
            return {"status": "ok", "data": result}
        return {"status": "error", "message": "无数据"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def fetch_ppi():
    """PPI工业生产者出厂价格指数"""
    try:
        url = 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_PPI&columns=ALL&pageSize=6&pageNumber=1&sortColumns=REPORT_DATE&sortTypes=-1'
        data = _fetch_json(url)
        if data.get("success") and data.get("result", {}).get("data"):
            rows = data["result"]["data"]
            result = []
            for r in rows[:3]:
                result.append({
                    "date": r.get("TIME", ""),
                    "PPI同比%": _safe_float(r.get("BASE_SAME")),
                })
            return {"status": "ok", "data": result}
        return {"status": "error", "message": "无数据"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def fetch_gdp():
    """GDP同比增速"""
    try:
        url = 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_GDP&columns=ALL&pageSize=4&pageNumber=1&sortColumns=REPORT_DATE&sortTypes=-1'
        data = _fetch_json(url)
        if data.get("success") and data.get("result", {}).get("data"):
            rows = data["result"]["data"]
            result = []
            for r in rows[:2]:
                result.append({
                    "date": r.get("TIME", ""),
                    "GDP同比%": _safe_float(r.get("SUM_SAME")),
                    "GDP绝对值(亿)": _safe_float(r.get("DOMESTICL_PRODUCT_BASE")),
                })
            return {"status": "ok", "data": result}
        return {"status": "error", "message": "无数据"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def fetch_all():
    """获取所有宏观数据"""
    result = {
        "pmi": fetch_pmi(),
        "cpi": fetch_cpi(),
        "ppi": fetch_ppi(),
        "gdp": fetch_gdp(),
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ============================================================
# 行业轮动模型（自动使用宏观数据）
# ============================================================

CYCLE_PHASES = {
    "recovery": {
        "label": "📈 复苏期",
        "desc": "经济扩张 + 通胀温和 → 成长风格占优",
        "sector_advice": {
            "超配": ["科技/半导体", "AI/数字经济"],
            "标配": ["通信/电子", "化工/材料", "其他"],
            "低配": ["能源/公用事业"]
        },
        "tactical": "科技板块中期看好，重点关注半导体设备和AI应用"
    },
    "overheat": {
        "label": "🔥 过热期",
        "desc": "经济扩张 + 通胀偏高 → 周期风格占优",
        "sector_advice": {
            "超配": ["化工/材料", "能源/公用事业"],
            "标配": ["科技/半导体(精选)", "通信/电子", "其他"],
            "低配": []
        },
        "tactical": "关注资源板块，成长股需精选"
    },
    "stagflation": {
        "label": "⛽ 滞胀期",
        "desc": "经济收缩 + 通胀偏高 → 防御为上",
        "sector_advice": {
            "超配": ["能源/公用事业"],
            "标配": ["化工/材料", "其他"],
            "低配": ["科技/半导体", "AI/数字经济", "通信/电子"]
        },
        "tactical": "防御为上，超配公用事业和高股息"
    },
    "recession": {
        "label": "❄️ 衰退期",
        "desc": "经济收缩 + 通胀回落 → 等待政策宽松",
        "sector_advice": {
            "超配": ["能源/公用事业"],
            "标配": ["科技/半导体(等待右侧)", "AI/数字经济", "通信/电子", "其他"],
            "低配": ["化工/材料"]
        },
        "tactical": "防御为主，逐步布局利率敏感型板块"
    }
}


def calc_rotation(macro_data):
    """根据宏观数据判断周期 → 输出行业轮动建议"""
    pmi = macro_data.get("pmi", {})
    cpi = macro_data.get("cpi", {})
    ppi = macro_data.get("ppi", {})

    # 提取最新值
    pmi_val = pmi.get("data", [{}])[0].get("制造业PMI") if pmi.get("data") else None
    cpi_val = cpi.get("data", [{}])[0].get("CPI同比%") if cpi.get("data") else None

    # 判断周期
    is_expanding = pmi_val and pmi_val >= 50
    is_high_cpi = cpi_val and cpi_val >= 3

    if is_expanding and not is_high_cpi:
        phase = "recovery"
    elif is_expanding and is_high_cpi:
        phase = "overheat"
    elif not is_expanding and is_high_cpi:
        phase = "stagflation"
    else:
        phase = "recession"

    phase_info = CYCLE_PHASES[phase]

    # 格式化输出
    lines = ["━━━ 行业轮动模型（自动）━━━"]
    lines.append(f"\n{phase_info['label']}")
    lines.append(f"{phase_info['desc']}")
    lines.append(f"\n判断依据: PMI={pmi_val}, CPI={cpi_val}%")
    lines.append(f"\n【配置建议】")
    for alloc, sectors in phase_info["sector_advice"].items():
        for s in sectors:
            icon = "🔴" if alloc == "超配" else ("🟢" if alloc == "低配" else "⚪")
            lines.append(f"  {icon} {s}: {alloc}")
    lines.append(f"\n💡 {phase_info['tactical']}")

    return {
        "phase": phase,
        "phase_label": phase_info["label"],
        "sector_advice": phase_info["sector_advice"],
        "tactical": phase_info["tactical"],
        "determined_by": {"PMI": pmi_val, "CPI": cpi_val},
        "text": "\n".join(lines)
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pmi", action="store_true")
    parser.add_argument("--cpi", action="store_true")
    parser.add_argument("--rotation", action="store_true", help="输出行业轮动建议")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--cache", action="store_true")
    args = parser.parse_args()

    if args.cache and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            macro = json.load(f)
    else:
        if args.pmi:
            macro = {"pmi": fetch_pmi()}
        elif args.cpi:
            macro = {"cpi": fetch_cpi()}
        else:
            macro = fetch_all()

    if args.rotation:
        rotation = calc_rotation(macro)
        if args.json:
            print(json.dumps(rotation, ensure_ascii=False, indent=2))
        else:
            print(rotation["text"])
    elif args.json:
        print(json.dumps(macro, ensure_ascii=False, indent=2))
    else:
        # 文本摘要
        lines = ["━━━ 宏观经济数据（东方财富）━━━"]
        for key, label in [("pmi", "PMI"), ("cpi", "CPI"), ("ppi", "PPI"), ("gdp", "GDP")]:
            item = macro.get(key, {})
            if item.get("status") == "ok" and item.get("data"):
                row = item["data"][0]
                vals = " | ".join(f"{k}={v}" for k, v in row.items() if v is not None and k != "date")
                lines.append(f"\n📊 {label} ({row['date']}):")
                lines.append(f"  {vals}")
            else:
                lines.append(f"\n{label}: (暂不可用)")

        # 自动行业轮动
        lines.append("\n" + "-" * 30)
        rotation = calc_rotation(macro)
        lines.append(rotation["text"])

        print("\n".join(lines))
