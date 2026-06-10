# 盘前推送流程模板 (9:15)

## 前置约束
- 不可修改：`dashboard.html`
- 周六日/节假日：直接结束，不推送

## 执行步骤

### 1. 判断日期
- 判断今天是否周六日或节假日
- 如果是周末/节假日 → 直接完成，不推送

### 2. 读取简报内容
```bash
cat /tmp/premarket-content.txt
```
- 盘前简报已经在9:00任务中生成完毕
- 这里是纯推送任务，直接读取已有内容

### 3. 发送到飞书
- 将读取到的内容直接发送

### 4. 末尾添加链接
```
📎 在线查看：https://daily-report-3ai.pages.dev/premarket-YYYY-MM-DD
```

### 5. 同步到 Obsidian
```bash
bash /Users/shisan/.openclaw/workspace/scripts/obsidian-sync.sh
```

### 6. 同步到 Cloudflare Pages
```bash
bash /Users/shisan/.openclaw/workspace/scripts/gh-pages-sync.sh
```

### 7. 更新持仓看板
- 更新 `/Users/shisan/.openclaw/workspace/memory/stock-watchlist.md`
