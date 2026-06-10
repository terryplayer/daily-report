# 午间动态监测流程模板 (12:00)

## 前置约束
- 样式模板：`scripts/template-midday.html`
- 持仓清单：`scripts/template-stocks.json`
- 不可修改：`dashboard.html`
- 周末/节假日：直接结束

## 执行步骤

### 1. 判断日期
- 判断今天是否周六日或节假日
- 如果是周末/节假日 → 直接完成

### 2. 读取模板样式
```bash
head -120 /Users/shisan/.openclaw/workspace/scripts/template-midday.html
```
- 严格复制模板CSS样式

### 3. 获取实时行情数据

#### 3a. 指数数据
```bash
python3 -c "
import urllib.request
url = 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399005,sz399006'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=10).read().decode('gbk')
for line in resp.strip().split(';'):
    if not line.strip(): continue
    parts = line.split('~')
    print(f'{parts[1]}: {parts[3]} ({parts[31]}) [{parts[32]}%] 高:{parts[33]} 低:{parts[34]}')
"
```

#### 3b. 个股实时行情（从config动态读取）
```bash
python3 -c "
import urllib.request, json
cfg = json.load(open('/Users/shisan/.openclaw/workspace/config/stocks.json'))
codes = [s['code'] for s in cfg['watchlist']]
qt_codes = ','.join([f'sh{c}' if c.startswith(('6','9')) else f'sz{c}' for c in codes])
url = f'https://qt.gtimg.cn/q={qt_codes}'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=10).read().decode('gbk')
for line in resp.strip().split(';'):
    if not line.strip(): continue
    parts = line.split('~')
    code = parts[2]; price = parts[3]; change_pct = parts[32]; name = parts[1]
    print(f'{name}({code}) {price} {change_pct}%')
" 2>&1
```
- 如果实时API失败：用 web_search 抓取上午行情概览

### 4. 读取持仓配置
```bash
cat /Users/shisan/.openclaw/workspace/scripts/template-stocks.json
```

### 5. 读取盘前预判（用于偏差对比）
```bash
cat /tmp/premarket-content.txt 2>/dev/null || echo '无盘前简报缓存'
```

### 6. 调用 Hermes V4 Pro 做午间分析
```
exec("hermes chat -q '基于上午行情数据，给出午间分析...' -Q -m deepseek/deepseek-v4-pro")
```
- 把上午实时数据和盘前预判差值喂给 Hermes
- Hermes 生成：半日总结、板块异动、午后策略

### 8. 生成午间报告
- 使用模板 `midday-2026-05-29` 的内容结构和样式
- 保存到 `daily-report-html/midday-YYYY-MM-DD.html`
- 涨用🔴红标，跌用🟢绿标

### 8b. 生成临时预览文件（待确认）
- 复制生成的HTML到 `temp_reports/午间监测_预览_YYYY-MM-DD.html`
- 推送时末尾加上：📁 预览版路径

#### 📐 排版规范
先读取模板规范文件：
```bash
cat /Users/shisan/.openclaw/workspace/memory/daily-report-template.md
```
- 午间文字版排版 → 遵循文件中

### 7. 推送飞书
- 发送文字内容
- 末尾加链接：`📎 https://daily-report-3ai.pages.dev/midday-YYYY-MM-DD`

### 8. 同步部署
```bash
bash /Users/shisan/.openclaw/workspace/scripts/gh-pages-sync.sh
```

### 9. 更新持仓看板
- 更新 `/Users/shisan/.openclaw/workspace/memory/stock-watchlist.md`
