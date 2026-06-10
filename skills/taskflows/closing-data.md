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

### 6. 调用 Hermes V4 Pro 做深度分析
将采集到的行情数据、持仓配置、盘前预判打包传给 Hermes V4 Pro 做深度解读：
```
结果 = exec("hermes chat -q '基于以下数据生成收盘简报分析内容...' -Q -m deepseek/deepseek-v4-pro")
```
- 把 `stock_analysis_cache.json` 的数据喂给 Hermes
- 让 Hermes 生成板块轮动点评、异动分析、明日展望等深度内容
- Hermes 返回的结果作为简报的核心分析素材

### 7. 按10板块模板生成收盘简报
- HTML的`<style>`部分必须完全复制自 template-daily-combined.html
- 使用6/2的HTML结构（table/stock-row/sector-title等CSS类），**不要用<p>标签堆文字**
- 保存HTML到 `daily-report-html/daily-combined-YYYY-MM-DD.html`
- 保存文字版到 `/tmp/closing-content.txt`

### 7b. 生成临时预览文件（待确认）
- 复制生成的HTML到 `temp_reports/收盘简报_预览_YYYY-MM-DD.html`
- 推送飞书时末尾加上：
  ```
  📁 预览版：daily-report-html/temp_reports/收盘简报_预览_YYYY-MM-DD.html
  ```
- 如果十三哥确认有问题，可以用临时文件回滚重新部署

#### 📐 排版规范 — 严格遵循
先读取模板规范文件：
```bash
cat /Users/shisan/.openclaw/workspace/memory/daily-report-template.md
```

**关键规则：**
1. **以昨天的版本为基准** —— 生成前先看 `daily-report-html/daily-combined-前一日.html` 的文字结构，**严格对标**前一日格式
2. 文字版必须完全复制前一天的布局/对齐/分隔线/空行风格
3. 生成后逐条检查排版规则（见模板文件第4.4节检查清单）
4. 特别注意：板块表格必须用空格对齐、不能有 `&amp;` 等HTML转义、不能内容重复、持仓只列TOP5涨+TOP5跌
5. 总长度控制在2000字符以内

- **HTML 版** → 遵循 `memory/daily-report-template.md`
- **文字版** → 严格对标前一日格式 + 遵循 `memory/daily-report-template.md`

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

### 7. 预测复盘 & Hermes 学习循环（关键！）

#### 7a. 读取盘前预测
```bash
cat /tmp/premarket-predictions.txt 2>/dev/null || cat /tmp/premarket-predictions.json 2>/dev/null || echo '无盘前预测缓存'
```

#### 7b. 对比预测 vs 实际
逐项对比盘前预测方向与实际走势：
- 预测上涨的板块 → 实际涨了吗？
- 预测下跌的板块 → 实际跌了吗？
- 预测概率 vs 实际涨跌幅偏差多少？
- 记录到 `/tmp/prediction-review.txt`

#### 7c. 调用 Hermes V4 Pro 复盘学习
```
学习结果 = exec("hermes chat -q '你是A股分析学习引擎。分析以下盘前预测与收盘实际的对比，找出预测偏差的原因，输出结构化复盘...' -Q -m deepseek/deepseek-v4-pro")
```
- 把盘前预测、实际走势、偏差数据喂给 Hermes
- Hermes 分析要点：
  1. 哪些信号（RS/北向/外盘/PCR）预测准确，哪些失效
  2. 本次预测偏差的主要原因是什么
  3. 下次应该如何调整判断逻辑
  4. 输出结构化的复盘报告

#### 7d. 将复盘经验写入 Hermes 记忆
```
# 让 Hermes 把这次复盘经验写入长期记忆
exec("hermes chat -q '请记住以下预测复盘经验，作为以后类似行情的参考依据：...' -Q -m deepseek/deepseek-v4-pro")
```
- 把复盘要点写入 Hermes 的 Tablestore 记忆
- 这样下次遇到类似行情时，Hermes 会参考历史经验

### 8. 验证输出
- 确认HTML文件存在
- 确认复盘日志已写入

### 9. 同步部署
```bash
bash scripts/gh-pages-sync.sh
```
