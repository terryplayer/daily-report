# A股周复盘流程模板 (周日12:00)

## 前置约束
- 样式参考：`https://daily-report-3ai.pages.dev/weekly-review-2026-05-31`
- 持仓清单：`scripts/template-stocks.json`
- 不可修改：`dashboard.html`

## 执行步骤

### 1. 读取持仓配置
```bash
cat /Users/shisan/.openclaw/workspace/scripts/template-stocks.json
```

### 2. 采集分析数据
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/stock_analysis.py --update
python3 scripts/stock_analysis.py --days 5 --json
python3 scripts/macro_fetch.py --rotation --json
```

### 3. 读取本周日报
- 本周的 daily-combined-YYYY-MM-DD.html 文件
- memory/stock-watchlist.md

### 4. 搜索周末信息
- web_search 搜索国内外重大新闻

### 5. 生成HTML
- 保存到 `weekly-review-YYYY-MM-DD.html`
- 样式参考 weekly-review-2026-05-31

### 6. 7大板块
1. 本周大盘回顾 — 四大指数周变化
2. 本周板块轮动回顾 — 领涨/领跌TOP
3. 预测验证 & 准确率评估
4. 周末重大信息汇总
5. 下周趋势判断 — 支撑压力+板块预判
6. 下周板块及个股建议
7. 综合评级与操作建议（短期持有/长期持有/卖出）

### 7. 发送文字摘要到飞书

### 8. 同步部署
```bash
bash /Users/shisan/.openclaw/workspace/scripts/gh-pages-sync.sh
```

### 9. 末尾加链接
```
📎 https://daily-report-3ai.pages.dev/weekly-review-YYYY-MM-DD
```
