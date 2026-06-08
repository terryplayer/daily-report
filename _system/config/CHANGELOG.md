# 🔄 修改检查清单

每次修改持仓或系统配置后，按此清单逐项确认。

## 修改类型

### A. 增删股票
- [ ] 更新 `config/stocks.json`（唯一数据源）
- [ ] 运行 `python3 scripts/daily_check.py`（自动验证一致性）
- [ ] 更新 `memory/stock-watchlist.md`
- [ ] 更新 `_moc/持仓分析.md`（Obsidian）
- [ ] 更新 `工作流说明书.md`
- [ ] 运行 `obsidian-sync.sh` 或 `python3 scripts/parse_html.py`

### B. 修改流程/配置
- [ ] 更新 `工作流说明书.md`
- [ ] 更新相关 cron 提示词（9:00/12:00/15:45/周复盘）
- [ ] 运行 `python3 scripts/daily_check.py`
- [ ] 通知用户变更

### C. 部署相关
- [ ] `git push github main` → 触发 Cloudflare Pages 部署
- [ ] 验证线上链接 `https://daily-report-3ai.pages.dev/`
- [ ] 验证今日报告可访问

## 自动检查

每天早上 9:00 自检任务会执行：
```bash
python3 scripts/daily_check.py
```
检查项：
1. config/stocks.json 完整性
2. tushare_fetch.py 与配置一致
3. stock_analysis.py 与配置一致
4. Cloudflare API token 有效
5. GitHub remote 配置正确
6. 今日盘前简报是否已生成（提醒）
