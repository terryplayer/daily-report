# 盘前数据采集流程模板 (9:00)

## 前置约束
- 样式模板：`scripts/template-premarket.html`
- 持仓清单：`scripts/template-stocks.json`
- 不可修改：`dashboard.html`
- 周末/节假日：直接结束，不生成任何内容

## 执行步骤

### 1. 每日自检
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/daily_check.py 2>&1
```
- 如果报错（非0退出码）：记录错误但不中止，继续执行

### 2. 判断日期
- 判断今天是否周六日或节假日
- 如果是周末/节假日 → 直接完成，不生成任何简报，不推送

### 3. 读取模板样式
```bash
head -120 /Users/shisan/.openclaw/workspace/scripts/template-premarket.html
```
- 仔细阅读模板CSS样式（背景色、字体颜色、卡片布局、表格样式、红绿颜色值）
- 生成盘前简报时**严格复制这些样式**

### 4. 更新历史数据
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/stock_analysis.py --update 2>&1 | tail -20
```

### 5. 获取Tushare数据
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/tushare_fetch.py report 2>/dev/null
```

### 6. 获取分析数据
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/stock_analysis.py --json > /tmp/stock_analysis_cache.json 2>&1
```
- 如果以上脚本报错：用 web_search 抓取美股行情，跳过RS/评分细节

### 7. 读取持仓配置（使用模板文件）
```bash
cat /Users/shisan/.openclaw/workspace/scripts/template-stocks.json
```

---

## 🔍 研究员角色 — 数据采集

> **角色**：研究员（Researcher Agent）
> **职责**：采集行情数据、搜索新闻、核查信号
> **状态**：✅ v1.0 已上线（2026-06-09）
> **Prompt模板**：`scripts/researcher_prompt.md`
> **Python模块**：`scripts/researcher.py`

### 8. 研究员数据采集（研究员角色）

#### 方式A：通过研究员脚本自动采集（推荐）
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/researcher.py --mode premarket 2>&1 | tail -5
```
- 输出保存到 `data/research_cache.json` 和 `/tmp/research-report.txt`
- 如果报错（脚本不存在或依赖缺失），回退到方式B

#### 方式B：手动脚本逐一采集（回退）

##### 8a. 北向资金（昨日）
```bash
python3 -c "
import tushare as ts, json
ts.set_token(open('data/tushare_token.txt').read().strip())
pro = ts.pro_api()
north = pro.moneyflow_hsgt(trade_date='昨日YYYYMMDD')
if north is not None and len(north) > 0:
    last = north.iloc[-1]
    print(f'北向: {last.get(\"north_money\",0)/1e8:.1f}亿')
" 2>/dev/null || echo '北向获取失败'
```

#### 8b. 隔夜外盘
```bash
python3 -c "
import urllib.request
urls = {\"道指\":'sh_dji',\"纳指\":'sh_ixic',\"标普\":'sh_spx',\"A50\":'sh_zh0901'}
for name, symbol in urls.items():
    try:
        resp = urllib.request.urlopen(f'http://qt.gtimg.cn/q={symbol}', timeout=5).read().decode('gbk')
        parts = resp.split('~')
        if len(parts) > 32:
            print(f'{name}: {parts[3]} ({parts[32]}%)')
    except: pass
" 2>/dev/null
```

#### 8c. 期权PCR（50ETF）
```bash
python3 -c "
import urllib.request, json
try:
    resp = urllib.request.urlopen('https://hq.sinajs.cn/list=OP_UP_510050,OP_DOWN_510050', timeout=5)
    # 简化为输出PCR指标
    print('PCR: 数据获取中')
except: print('PCR: 获取失败')
" 2>/dev/null || echo 'PCR跳过'
```

#### 8d. 早盘舆情
```bash
web_search 'A股 今日热点 盘前 2026-06-03' 2>/dev/null || echo '舆情跳过'
```

### 9. 三重修正因子 + 概率化评级
- 基于RS排名+多因子评分+技术面综合
- 参考研究员采集的**北向资金方向、隔夜外盘走势、A50期指**
- **每板块输出概率**，格式：
  ```
  板块A  ↑ 65%  看涨理由：……
  板块B  ↓ 55%  看跌理由：……
  板块C  — 50%  方向不明：……
  ```
- 不再使用二元涨/跌判断，改用概率+逻辑

### 10. 调用研究员(Prompt模板) → Hermes V4 Pro 做盘前分析

#### 10a. 读取研究员Prompt模板
```bash
cat /Users/shisan/.openclaw/workspace/scripts/researcher_prompt.md
```

#### 10b. 读取研究员采集的数据
```bash
cat /tmp/research-report.txt 2>/dev/null || echo '研究员报告未生成，使用原始数据'
```

#### 10c. 调用 Hermes 分析
```
exec("hermes chat -q '基于以下研究员采集的数据和信号，给出今日概率化盘前预判...' -Q -m deepseek/deepseek-v4-pro")
```
- 把 **研究员报告 + 持仓配置 + RS数据 + 辅助信号（北向/外盘/PCR）+ 概率评级** 打包喂给 Hermes
- Hermes 生成：大盘预判（含概率）、板块方向（含概率）、关注个股、操作策略
- Hermes 的回答中每个预测必须附带概率百分比和推理逻辑
- 如果研究员数据不可用，使用原始脚本采集的数据作为替代

### 11. 保存盘前预判到缓存（用于收盘复盘对比）
```bash
cp /tmp/premarket-content.txt /tmp/premarket-predictions.txt
```
- 同时保存一份结构化预测到 `/tmp/premarket-predictions.json`，包含：预测板块/方向/概率/关键逻辑
- 这个文件收盘时用于对比实际走势和复盘学习

### 12. 生成HTML文件
- 保存到 `daily-report-html/premarket-YYYY-MM-DD.html`
- **严格使用模板样式，用CSS类布局，不要用<p>标签堆文字**

### 12b. 生成临时预览文件（待确认）
- 复制生成的HTML到 `temp_reports/盘前简报_预览_YYYY-MM-DD.html`
- 推送时末尾加上：📁 预览版路径

### 10. 保存文字内容
- 保存到 `/tmp/premarket-content.txt`（覆盖旧内容）

#### 📐 排版规范
先读取模板规范文件：
```bash
cat /Users/shisan/.openclaw/workspace/memory/daily-report-template.md
```
- 文字版排版 → 遵循文件中

### 11. 同步部署
```bash
bash scripts/gh-pages-sync.sh
```
