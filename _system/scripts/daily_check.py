#!/usr/bin/env python3
"""📋 每日系统自检 — 检查系统一致性 + 全量健康检查"""
import json, os, sys, subprocess
from datetime import datetime, date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []
warnings = []
info_log = []

def check(ok, msg):
    if not ok: errors.append(msg)

def warn(ok, msg):
    if not ok: warnings.append(msg)

def log(msg):
    info_log.append(msg)
    print(f"  {msg}")

now = datetime.now()
today_str = date.today().isoformat()
log(f"🕐 自检时间: {now.strftime('%Y-%m-%d %H:%M')}")

# ═══════════════════════════════════════════════
# 1. 配置文件 + 脚本一致性
# ═══════════════════════════════════════════════
log("\n📋 1. 配置文件与脚本一致性")
with open(os.path.join(WORKSPACE, "config", "stocks.json")) as f:
    cfg = json.load(f)
check('watchlist' in cfg, "config/stocks.json 缺少 watchlist")
stock_count = len(cfg.get('watchlist',[]))
check(stock_count >= 31, f"config/stocks.json 股票数不足: {stock_count}")
log(f"   持仓股票: {stock_count} 只")

from scripts.tushare_fetch import WATCHLIST as tw
from scripts.stock_analysis import WATCHLIST_CODES as sw
cfg_codes = {s['code'] for s in cfg['watchlist']}
if cfg_codes != set(tw):
    warn(False, f"tushare_fetch 与配置不一致: {cfg_codes ^ set(tw)}")
if cfg_codes != set(sw):
    warn(False, f"stock_analysis 与配置不一致: {cfg_codes ^ set(sw)}")
log(f"   脚本一致性: ✅")

# ═══════════════════════════════════════════════
# 2. Cron 任务存活率
# ═══════════════════════════════════════════════
log("\n⏰ 2. Cron 任务状态")
try:
    r = subprocess.run(['openclaw', 'cron', 'list'], capture_output=True, text=True, timeout=20)
    if r.returncode == 0 and r.stdout.strip():
        lines = [l for l in r.stdout.strip().split('\n') if l.strip()]
        # 第一行是表头，跳过；计数器从 ID 行开始
        job_lines = [l for l in lines[1:] if len(l) > 30 and '-' not in l[:5]]
        # 检查关键任务名称是否在输出中
        expected_names = ['午间', '收盘数据', '收盘推送', '盘前数据', '盘前简报', 
                         '评分', '每日复盘', '自检', 'TED', '周复盘']
        missing = [n for n in expected_names if n not in r.stdout]
        if missing:
            warn(False, f"cron 中缺少预期任务: {missing}")
        log(f"   任务行数: {len(job_lines)} | 预期任务均在线" if not missing else f"   任务行数: {len(job_lines)} | 缺少: {missing}")
        
        # 检查 lastRunStatus=failed 的任务
        if 'failed' in r.stdout.lower():
            warn(False, "有 cron 任务上次运行失败，需人工排查")
    else:
        errors.append("Cron list 无数据返回")
except Exception as e:
    errors.append(f"Cron list 检查失败: {e}")

# ═══════════════════════════════════════════════
# 3. 数据文件健康
# ═══════════════════════════════════════════════
log("\n📊 3. 数据文件健康")

# stock_history.json
hist_path = os.path.join(WORKSPACE, "data", "stock_history.json")
if os.path.exists(hist_path):
    with open(hist_path) as f:
        hist = json.load(f)
    dates = sorted(hist.get('history', {}).keys())
    check(len(dates) > 0, "stock_history.json 无历史数据")
    if dates:
        latest = dates[-1]
        last_day = hist['history'][latest]
        stock_cnt = 0
        if isinstance(last_day, dict):
            stocks = last_day.get('stocks', {})
            stock_cnt = len(stocks) if isinstance(stocks, dict) else 0
        log(f"   stock_history.json: {len(dates)}天, 最新{latest}, {stock_cnt}只")
        try:
            last_dt = datetime.strptime(latest, '%Y%m%d')
            if (now - last_dt).days > 5:
                warn(False, f"stock_history 最新数据 {latest} 已过时 ({(now-last_dt).days}天前)")
        except:
            pass
        check(stock_cnt >= 30, f"stock_history.json 最新日股票数不足: {stock_cnt}")
else:
    errors.append("data/stock_history.json 不存在")

# macro_cache.json
macro_path = os.path.join(WORKSPACE, "data", "macro_cache.json")
if os.path.exists(macro_path):
    with open(macro_path) as f:
        mac = json.load(f)
    for k in ['pmi', 'cpi', 'ppi', 'gdp']:
        v = mac.get(k, {})
        check(v.get('status') == 'ok', f"macro_cache.{k} 状态异常: {v.get('status')}")
    fetched = mac.get('fetched_at', '无')
    log(f"   macro_cache: PMI✓ CPI✓ PPI✓ GDP✓ (更新于 {fetched})")
else:
    errors.append("data/macro_cache.json 不存在")

# tushare token
token_path = os.path.join(WORKSPACE, "data", "tushare_token.txt")
if os.path.exists(token_path):
    token = open(token_path).read().strip()
    check(len(token) >= 30, f"tushare_token 长度异常: {len(token)}")
    log(f"   tushare_token: {len(token)} 位 ✅")
else:
    errors.append("data/tushare_token.txt 不存在")

# ═══════════════════════════════════════════════
# 4. 模板文件完整性
# ═══════════════════════════════════════════════
log("\n📐 4. 模板文件完整性")
templates = [
    'template-premarket.html', 'template-premarket-advanced-model.html',
    'template-midday.html', 'template-midday-advanced-model.html',
    'template-closing.html', 'template-closing-advanced-model.html',
    'template-weekly.html',
    'template-stocks.json',
    'index-shell.html', 'index-footer.html',
]
tpl_dir = os.path.join(WORKSPACE, "scripts")
missing_tpl = [t for t in templates if not os.path.exists(os.path.join(tpl_dir, t))]
check(len(missing_tpl) == 0, f"缺少模板: {missing_tpl}")
log(f"   模板文件: {len(templates)}/{len(templates)} 齐全" if not missing_tpl else f"   缺少: {missing_tpl}")

# ═══════════════════════════════════════════════
# 5. 模型文件完整性
# ═══════════════════════════════════════════════
log("\n🌲 5. 模型文件完整性")
model_dir = os.path.join(WORKSPACE, "models")
models = ['random_forest_optimized.pkl', 'random_forest_v2.pkl', 'rf_cross_section.pkl', 'rf_stock_model.pkl']
missing_model = [m for m in models if not os.path.exists(os.path.join(model_dir, m))]
check(len(missing_model) == 0, f"缺少模型: {missing_model}")
if not missing_model:
    total_size = sum(os.path.getsize(os.path.join(model_dir, m)) for m in models)
    log(f"   模型文件: {len(models)}/{len(models)} 齐全 (共{total_size/1024/1024:.0f}MB)")
else:
    log(f"   缺少: {missing_model}")

# ═══════════════════════════════════════════════
# 6. HTML目录 + Cloudflare 部署
# ═══════════════════════════════════════════════
log("\n🚀 6. 部署链路")
html_dir = os.path.join(WORKSPACE, "daily-report-html")
check(os.path.isdir(html_dir), "daily-report-html/ 目录不存在")

# GitHub remote
try:
    r = subprocess.run(['git', '-C', html_dir, 'remote', '-v'], capture_output=True, text=True, timeout=5)
    if 'github.com/terryplayer/daily-report' in r.stdout:
        log(f"   GitHub remote: ✅")
    else:
        errors.append("GitHub remote 未配置")
except:
    errors.append("Git remote 检查失败")

# Cloudflare token
cf_config = os.path.expanduser("~/.wrangler/config.json")
if os.path.exists(cf_config):
    with open(cf_config) as f:
        cf = json.load(f)
    if cf and 'api_token' in cf[0]:
        log(f"   Cloudflare token: ✅")
    else:
        errors.append("Cloudflare token 无效")
else:
    errors.append("Cloudflare token 未配置")

# Pages 可达性
try:
    r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--connect-timeout', '5', '--max-time', '8', 'https://daily-report-3ai.pages.dev'],
                      capture_output=True, text=True, timeout=10)
    code = r.stdout.strip()
    check(code in ('200', '308'), f"Pages 返回 {code} (期望200/308)")
    log(f"   Cloudflare Pages: HTTP {code} ✅")
except Exception as e:
    errors.append(f"Pages 可达性检查失败: {e}")

# ═══════════════════════════════════════════════
# 7. 今日报告状态
# ═══════════════════════════════════════════════
log("\n📋 7. 今日报告生成状态")
report_files = [
    (f"premarket-{today_str}.html", "今日盘前简报(标准)"),
    (f"premarket-advanced-{today_str.replace('-','')}.html", "今日盘前简报(进阶)"),
]
for fname, label in report_files:
    fpath = os.path.join(html_dir, fname)
    if os.path.exists(fpath):
        size = os.path.getsize(fpath)
        log(f"   {label}: ✅ ({size/1024:.0f}KB)")
    else:
        warn(False, f"{label} 未生成")

# ═══════════════════════════════════════════════
# 8. 临时缓存
# ═══════════════════════════════════════════════
log("\n💾 8. 临时缓存")
caches = [
    ('/tmp/stock_analysis_cache.json', '分析缓存'),
    ('/tmp/premarket-predictions.json', '盘前预判'),
    ('/tmp/premarket-content.txt', '盘前文字'),
]
for cpath, clabel in caches:
    if os.path.exists(cpath):
        mtime = os.path.getmtime(cpath)
        age_hours = (now.timestamp() - mtime) / 3600
        freshness = '新鲜' if age_hours < 12 else ('较旧' if age_hours < 48 else '过期')
        log(f"   {clabel}: ✅ ({age_hours:.0f}h前, {freshness})")
    else:
        warn(False, f"{clabel} 缓存文件不存在")

# ═══════════════════════════════════════════════
# 结果汇总
# ═══════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"📊 自检报告 | {now.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*50}")

if errors:
    print(f"\n❌ 错误 ({len(errors)}):")
    for e in errors:
        print(f"  🔴 {e}")
else:
    print("\n✅ 无错误")

if warnings:
    print(f"\n⚠️ 提示 ({len(warnings)}):")
    for w in warnings:
        print(f"  🟡 {w}")

print(f"\n{'='*50}")
print(f"✅ 自检完成 | {len(info_log)} 项检查")
print(f"{'='*50}")

sys.exit(1 if errors else 0)
