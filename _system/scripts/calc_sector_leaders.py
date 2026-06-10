#!/usr/bin/env python3
"""
🏆 细分行业龙头计算
按 f100（细分行业）分组，按流通市值降序排名
输出: data/sector_leaders.json
"""
import json, os, sys
from datetime import date
from collections import defaultdict

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORKSPACE)

RAW_DIR = os.path.join(WORKSPACE, "data", "raw")
OUT_PATH = os.path.join(WORKSPACE, "data", "sector_leaders.json")

def main():
    # 找最新原始数据文件
    files = sorted([f for f in os.listdir(RAW_DIR) if f.endswith('.json')], reverse=True)
    if not files:
        print("❌ 无原始数据文件")
        sys.exit(1)

    raw_file = files[0]
    date_str = raw_file.replace('.json', '')
    print(f"📡 数据文件: {raw_file}")

    with open(os.path.join(RAW_DIR, raw_file)) as f:
        data = json.load(f)

    meta = data.pop("_meta", {})
    fetched_at = meta.get("fetched_at", "")[:19] if isinstance(meta.get("fetched_at"), str) else date_str

    # 按 f100 (细分行业) 分组
    sectors = defaultdict(list)
    for code, s in data.items():
        sector = s.get("f100") or "其他"
        circ_mv = s.get("f21")  # 流通市值(亿)
        if circ_mv is None or circ_mv == '' or circ_mv == 0:
            continue
        try:
            circ_mv = float(circ_mv)
        except (ValueError, TypeError):
            continue
        if circ_mv <= 0:  # 排除无市值数据
            continue
        sectors[sector].append({
            "code": code,
            "name": s.get("f14", ""),
            "circ_mv": circ_mv,
            "change_pct": s.get("f3")
        })

    # 各行业排序+取TOP9
    leaders_map = {}
    sector_list = {}

    for sector, stocks in sorted(sectors.items()):
        if len(stocks) < 3:
            continue  # 不足3只的行业跳过
        ranked = sorted(stocks, key=lambda x: x["circ_mv"], reverse=True)[:9]
        top9 = []
        for i, s in enumerate(ranked):
            rank = i + 1
            if rank <= 3:
                label, tier = "🏆龙头", 1
            elif rank <= 6:
                label, tier = "💎核心", 2
            else:
                label, tier = "📌关注", 3
            leaders_map[s["code"]] = {
                "rank": rank,
                "label": label,
                "tier": tier,
                "sector": sector,
                "name": s["name"],
                "circ_mv": round(s["circ_mv"], 1)
            }
            top9.append({
                "code": s["code"],
                "name": s["name"],
                "rank": rank,
                "label": label,
                "tier": tier,
                "circ_mv": round(s["circ_mv"], 1),
                "change_pct": round(s["change_pct"], 2) if s["change_pct"] is not None else None
            })
        sector_list[sector] = top9

    result = {
        "date": date_str,
        "fetched_at": fetched_at,
        "total_sectors": len(sector_list),
        "total_stocks": len(leaders_map),
        "leaders": leaders_map,
        "sector_list": sector_list
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    tiers = {"🏆龙头": 0, "💎核心": 0, "📌关注": 0}
    for v in leaders_map.values():
        tiers[v["label"]] += 1

    print(f"✅ {OUT_PATH}")
    print(f"   行业: {result['total_sectors']}个")
    print(f"   股票: {result['total_stocks']}只")
    print(f"   🏆龙头 {tiers['🏆龙头']} · 💎核心 {tiers['💎核心']} · 📌关注 {tiers['📌关注']}")

if __name__ == "__main__":
    main()
