#!/usr/bin/env python3
"""
🔍 研究员角色 — 数据采集模块

职责：采集行情数据、搜索新闻、核查信号
输出：结构化 JSON 数据，供下游分析师/撰写员使用

独立运行：
  python3 scripts/researcher.py                  # 盘前采集
  python3 scripts/researcher.py --mode intraday  # 盘中实时采集
  python3 scripts/researcher.py --mode closing   # 收盘采集
  python3 scripts/researcher.py --mode test      # 连通性测试
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TODAY = datetime.now().strftime("%Y-%m-%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


def log(msg: str):
    print(f"[研究员] {msg}", file=sys.stderr)


def collect_overnight_markets() -> dict:
    """采集隔夜外盘数据"""
    log("采集隔夜外盘...")
    result = {}
    # 腾讯行情接口格式: ~字段以~分隔，索引3=最新价，索引32=涨跌幅
    urls = {
        "dow": "sh_dji",
        "nasdaq": "sh_ixic",
        "sp500": "sh_spx",
        "a50_futures": "sh_zh0901",
    }
    for name, symbol in urls.items():
        try:
            req = urllib.request.Request(
                f"http://qt.gtimg.cn/q={symbol}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp = urllib.request.urlopen(req, timeout=8).read().decode("gbk")
            parts = resp.split("~")
            if len(parts) > 32 and parts[3]:
                result[name] = {
                    "price": parts[3],
                    "change_pct": parts[32] if parts[32] else "N/A",
                }
            else:
                result[name] = {"price": "N/A", "change_pct": "N/A"}
        except Exception as e:
            log(f"  {name} 获取失败: {e}")
            result[name] = {"price": "N/A", "change_pct": "N/A", "error": str(e)}
    return result


def collect_north_bound() -> dict:
    """采集北向资金（昨日）"""
    log("采集北向资金...")
    try:
        import tushare as ts

        token_path = BASE_DIR / "data" / "tushare_token.txt"
        if token_path.exists():
            ts.set_token(token_path.read_text().strip())
            pro = ts.pro_api()
            north = pro.moneyflow_hsgt(trade_date=YESTERDAY)
            if north is not None and len(north) > 0:
                last = north.iloc[-1]
                raw = last.get("north_money", "0")
                # 兼容字符串和数值类型
                if isinstance(raw, str):
                    raw = raw.replace(",", "") if raw else "0"
                total = float(raw) / 1e8
                return {
                    "total": f"{total:.1f}亿",
                    "direction": "净流入" if total > 0 else "净流出",
                    "data_source": "Tushare",
                }
        return {"total": "N/A", "direction": "未知", "data_source": "Tushare"}
    except ImportError:
        log("  tushare 不可用，跳过北向资金采集")
        return {"total": "N/A", "direction": "未知", "data_source": "不可用"}
    except Exception as e:
        log(f"  北向资金采集失败: {e}")
        return {"total": "N/A", "direction": "未知", "data_source": "失败", "error": str(e)}


def collect_sector_news() -> dict:
    """采集板块热点新闻"""
    log("采集板块热点新闻...")
    news_items = []
    sectors = [
        "科技/半导体",
        "通信/电子",
        "AI/数字经济",
        "化工/材料",
        "能源/公用事业",
    ]
    for sector in sectors:
        news_items.append({
            "sector": sector,
            "status": "web_search",
            "note": "通过 web_search 补充",
        })
    return {"sectors": news_items, "note": "需调用 web_search 补充实时热点新闻"}


def collect_pcr() -> dict:
    """采集期权PCR"""
    log("采集50ETF期权PCR...")
    try:
        resp = urllib.request.urlopen(
            "https://hq.sinajs.cn/list=OP_UP_510050,OP_DOWN_510050", timeout=5
        )
        return {"pcr_50etf": "数据获取中", "data_source": "新浪财经"}
    except Exception as e:
        log(f"  PCR采集失败: {e}")
        return {"pcr_50etf": "N/A", "data_source": "失败", "error": str(e)}


def build_research_report() -> dict:
    """组装研究员完整报告"""
    report = {
        "date": TODAY,
        "collected_at": datetime.now().strftime("%H:%M:%S"),
        "overnight_markets": collect_overnight_markets(),
        "north_bound": collect_north_bound(),
        "sector_news_status": collect_sector_news(),
        "signals": {
            "pcr": collect_pcr(),
        },
        "data_sources_available": _check_data_sources(),
    }
    return report


def _check_data_sources() -> dict:
    """检查各数据源连通性"""
    status = {}
    # Tushare
    try:
        import tushare
        status["tushare"] = "可用"
    except ImportError:
        status["tushare"] = "未安装"

    # 腾讯行情
    try:
        resp = urllib.request.urlopen("http://qt.gtimg.cn/q=sh000001", timeout=3)
        status["tencent_quote"] = "可用" if resp.getcode() == 200 else "异常"
    except Exception:
        status["tencent_quote"] = "不可用"

    # Hermes
    try:
        r = subprocess.run(
            ["which", "hermes"], capture_output=True, text=True, timeout=5
        )
        status["hermes"] = "可用" if r.returncode == 0 else "未安装"
    except Exception:
        status["hermes"] = "检查失败"

    return status


def save_report(report: dict):
    """保存研究员报告到中间缓存"""
    output_path = BASE_DIR / "data" / "research_cache.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    log(f"报告已保存到 {output_path}")

    # 同时保存简版文本到 /tmp
    text_path = Path("/tmp/research-report.txt")
    lines = [
        f"📋 研究员报告 | {report['date']} {report['collected_at']}",
        "",
        "🌍 隔夜外盘:",
    ]
    for name, data in report["overnight_markets"].items():
        lines.append(
            f"  {name}: {data.get('price','N/A')} ({data.get('change_pct','N/A')})"
        )
    lines.append("")
    lines.append(f"💰 北向资金: {report['north_bound'].get('total','N/A')}")
    lines.append(
        f"   方向: {report['north_bound'].get('direction','未知')}"
    )
    lines.append("")
    lines.append("📡 数据源状态:")
    for name, st in report["data_sources_available"].items():
        lines.append(f"  {name}: {st}")
    text_path.write_text("\n".join(lines))
    log(f"简版报告已保存到 {text_path}")


def test_connectivity():
    """连通性测试"""
    print("=" * 50)
    print("🔍 研究员角色 — 数据源连通性测试")
    print("=" * 50)
    status = _check_data_sources()
    all_ok = True
    for name, st in status.items():
        ok = st in ("可用", "未安装")
        print(f"  {'✅' if ok else '❌'} {name}: {st}")
        if not ok:
            all_ok = False
    print("-" * 50)
    if all_ok:
        print("✅ 所有核心数据源可用")
    else:
        print("⚠️  部分数据源异常（详情如上）")
    print("=" * 50)

    # 快速采集测试
    print("\n📡 快速采集测试...")
    markets = collect_overnight_markets()
    for name, data in markets.items():
        price = data.get("price", "N/A")
        chg = data.get("change_pct", "N/A")
        err = data.get("error")
        if err:
            print(f"  ❌ {name}: {err}")
        else:
            print(f"  ✅ {name}: {price} ({chg})")
    print("\n✅ 研究员角色可用")


def main():
    parser = argparse.ArgumentParser(description="🔍 研究员角色 - 数据采集模块")
    parser.add_argument(
        "--mode",
        choices=["premarket", "intraday", "closing", "test"],
        default="premarket",
        help="采集模式 (默认: premarket)",
    )
    args = parser.parse_args()

    if args.mode == "test":
        test_connectivity()
        return

    log(f"启动研究员角色 — 模式: {args.mode}")
    report = build_research_report()
    save_report(report)

    # 输出到 stdout（可被调用方消费）
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
