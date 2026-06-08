# 收盘简报推送流程模板 (16:00)

## 前置约束
- 样式模板：`scripts/template-daily-combined.html`
- 不可修改：`index.html`
- 周六日/节假日：直接结束，不推送

## 执行步骤

### 1. 判断日期
- 判断今天是否周六日或节假日
- 如果是周末/节假日 → 直接完成，不推送

### 2. 读取简报内容
```bash
cat /tmp/closing-content.txt
```
- 收盘简报已经在15:45任务中生成完毕
- 不存在则用 web_search 抓取行情数据生成简要报告

### 3. 发送到飞书
- 发送内容包含：大盘指数、板块评分、持仓明细、准确率统计、风险提示、展望等

### 4. 末尾添加链接
```
📎 在线查看：https://daily-report-3ai.pages.dev/daily-combined-YYYY-MM-DD
```

### 5. 同步到 Obsidian
```bash
bash /Users/shisan/.openclaw/workspace/scripts/obsidian-sync.sh
```

### 6. 同步 Cloudflare
- 先用 wrangler 直推，失败则 git push 兜底

### 7. 更新持仓看板
- 更新 `/Users/shisan/.openclaw/workspace/memory/stock-watchlist.md`
