#!/usr/bin/env python3
"""📋 每日早间自检 — 检查系统一致性"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []
warnings = []

def check(ok, msg):
    if not ok: errors.append(msg)

def warn(ok, msg):
    if not ok: warnings.append(msg)

# 1. 检查配置文件
with open(os.path.join(WORKSPACE, "config", "stocks.json")) as f:
    cfg = json.load(f)
check('watchlist' in cfg, "config/stocks.json 缺少 watchlist")
check(len(cfg.get('watchlist',[])) >= 31, f"config/stocks.json 股票数不足: {len(cfg.get('watchlist',[]))}")

# 2. 检查脚本与配置一致
from scripts.tushare_fetch import WATCHLIST as tw
from scripts.stock_analysis import WATCHLIST_CODES as sw
from scripts.parse_html import update_stock_pages as _

cfg_codes = {s['code'] for s in cfg['watchlist']}
check(cfg_codes == set(tw), f"tushare_fetch WATCHLIST 与配置不一致: 差异={cfg_codes ^ set(tw)}")
check(cfg_codes == set(sw), f"stock_analysis WATCHLIST 与配置不一致: 差异={cfg_codes ^ set(sw)}")

# 3. 检查HTML输出目录
html_dir = os.path.join(WORKSPACE, "daily-report-html")
check(os.path.isdir(html_dir), "daily-report-html/ 目录不存在")

# 4. 检查今日已有文件
today = __import__('datetime').date.today().isoformat()
pre_file = os.path.join(html_dir, f"premarket-{today}.html")
# 不强制要求存在，只是提示
warn(os.path.exists(pre_file), f"今日盘前简报尚未生成")

# 5. 检查Cloudflare token
cf_config = os.path.expanduser("~/.wrangler/config.json")
if os.path.exists(cf_config):
    with open(cf_config) as f:
        cf = json.load(f)
    if cf and 'api_token' in cf[0]:
        print("  ✅ Cloudflare API token 存在")
    else:
        errors.append("Cloudflare token 无效")
else:
    errors.append("Cloudflare token 未配置")

# 6. 检查Gitee/GitHub远程
import subprocess
try:
    r = subprocess.run(['git', '-C', html_dir, 'remote', '-v'], capture_output=True, text=True, timeout=5)
    if 'github.com/terryplayer/daily-report' in r.stdout:
        print("  ✅ GitHub remote 配置正确")
    else:
        errors.append("GitHub remote 未配置")
except:
    errors.append("Git remote 检查失败")

print(f"\n{'='*40}")
if errors:
    print(f"❌ 错误 ({len(errors)}):")
    for e in errors: print(f"  - {e}")
else:
    print("✅ 无错误")

if warnings:
    print(f"\n⚠️ 提示 ({len(warnings)}):")
    for w in warnings: print(f"  - {w}")

sys.exit(1 if errors else 0)
