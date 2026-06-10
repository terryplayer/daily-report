# 收盘数据采集流程模板 (15:45)

## 前置约束
- 样式模板：`scripts/template-daily-combined.html`
- 持仓清单：`scripts/template-stocks.json`
- 不可修改：`dashboard.html`
- 周末/节假日：直接结束
- 颜色规则：🔴红色=正向(涨/利好/强势) 🟢绿色=负向(跌/利空/弱势)
- 静默执行：不推送飞书

## 执行步骤

### 1. 判断日期
- 判断今天是否周六日或节假日
- 如果是周末/节假日 → 直接完成

### 2. 读取模板样式
```bash
head -100 /Users/shisan/.openclaw/workspace/scripts/template-daily-combined.html
```
- 仔细阅读模板CSS样式（背景色、字体颜色、卡片布局、红绿颜色值等）
- 生成收盘简报时**严格复制这些样式，不得改动**

### 3. 采集数据
```bash
cd /Users/shisan/.openclaw/workspace && python3 scripts/stock_analysis.py --update 2>&1 | tail -5
python3 scripts/tushare_fetch.py report 2>/dev/null
python3 scripts/stock_analysis.py --json > /tmp/stock_analysis_cache.json 2>&1
```
- 同时通过腾讯API获取实时收盘价（从config动态读取代码）

### 4. 读取盘前预判
```bash
cat /tmp/premarket-content.txt 2>/dev/null
```

### 5. 读取持仓配置
```bash
cat /Users/shisan/.openclaw/workspace/scripts/template-stocks.json
```

### 6. 按10板块模板生成收盘简报
- HTML的`<style>`部分必须完全复制自 template-daily-combined.html
- 保存HTML到 `daily-report-html/daily-combined-YYYY-MM-DD.html`
- 保存文字版到 `/tmp/closing-content.txt`

#### 10大板块结构
1. 📊 大盘指数收盘 — 四大指数格栅卡
2. 🔄 板块评分&宏观 — 6板块评分+配置建议+宏观周期
3. 📋 持仓收盘明细 — stock-row布局+分析标签
4. 📰 今日要闻 — 宏观/行业/全球/公司分类
5. 📐 技术面信号 — MA5/布林/KDJ分析
6. ⚡ 波动预警
7. 🎯 预测准确率 — 综合统计+个股明细
8. ⭐ 多因子评分 — TOP5+BOTTOM5
9. ⚠️ 风险提示
10. 🔮 今日总结&明日展望

### 7. 验证输出
- 确认HTML文件存在

### 8. 同步部署
```bash
bash scripts/gh-pages-sync.sh
```
