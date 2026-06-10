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

> **角色**：研究员（Researcher Agent）v1.0 已上线
> **Prompt模板**：`scripts/researcher_prompt.md`
> **Python模块**：`scripts/researcher.py`

### 8. 研究员数据采集
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/researcher.py --mode premarket 2>&1
```
- 输出保存到 `data/research_cache.json` 和 `/tmp/research-report.txt`
- 如果失败则跳过，不影响后续流程

### 9. 三重修正因子评级
- 基于RS排名+多因子评分+技术面综合
- 参考研究员采集的北向/外盘/A50等辅助信号
- 参考板块动量修正、隔夜情绪修正、量价验证修正

### 10. 调用 Hermes 分析（含研究员数据）
- 读取研究员报告：`cat /tmp/research-report.txt 2>/dev/null`
- 将研究员报告+持仓配置+RS数据打包喂给 Hermes
```
exec("hermes chat -q '基于研究员数据和信号，给出盘前预判...' -Q -m deepseek/deepseek-v4-pro")
```

### 11. 生成HTML文件
- 保存到 `daily-report-html/premarket-YYYY-MM-DD.html`
- **严格使用模板样式**

### 12. 保存文字内容
- 保存到 `/tmp/premarket-content.txt`（覆盖旧内容）

### 13. 同步部署
```bash
bash scripts/gh-pages-sync.sh
```
