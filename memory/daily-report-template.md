# 📊 收盘简报 HTML 模板规范

**参考文件：** `daily-report-html/daily-combined-2026-05-22.html`
**线上参考：** https://terryplayer.github.io/daily-report/daily-combined-2026-05-22.html

## 固定结构（10大板块）

| 板块 | 内容 | 样式 |
|------|------|------|
| 🌤 市场概览 | 四大指数表 + 一句话点评 | `table` 红涨绿跌 |
| 🔄 板块轮动 | 领涨/弱势双栏 grid | `grid-2` 左右分栏 |
| 📈 持仓股票 | 按板块分类，每板块一个 `stock-table` | 含RS等级标签 |
| 📰 今日要闻 | 事件列表 | `event-item` |
| 📐 技术面信号 | 技术指标表 | 数据不足时显示"数据积累中" |
| ⚡ 波动预警 | 预警框 | `alert-box` |
| ⭐ 多因子评分 | TOP5 + BOTTOM5 + 行业汇总 | `multi-top5` / `multi-bot5` |
| 🌍 宏观与行业轮动 | 周期判断 + 配置建议 | `macro-box` |
| 🚨 风险提示 | 风险列表 | `warning-box` |
| 🔮 明日展望 | 前瞻判断列表 | `event-item` |

## 关键样式规则
- **颜色：** 红涨 (`#f85149`) / 绿跌 (`#3fb950`)
- **RS等级标签：** `tag-rs-aplus` (深红) / `tag-rs-a` (浅红) / `tag-rs-b` (黄) / `tag-rs-c` (蓝) / `tag-rs-d` (绿)
- **板块标题：** `sector-title` 紫色 `#bf77f6`
- **表格表头：** `stock-table th` 深蓝背景 `#1c2333`
- **头部：** 红色下划线 `#f85149`
- **每个板块用 `section` 卡片包裹**

---

# 📋 盘前简报 HTML 模板规范

**参考文件：** `daily-report-html/premarket-2026-05-25.html`
**线上参考：** https://terryplayer.github.io/daily-report/premarket-2026-05-25.html

## 固定结构（8大板块）

| 板块 | 内容 |
|------|------|
| 🌍 隔夜外围市场 | 美股三大指数涨跌表 |
| 📊 A股大盘预判 | 支撑/压力位 + 趋势判断 |
| 📅 今日关注 | 经济数据/政策/资金面 |
| 🧭 板块提示与行业轮动 | 板块方向 + 行业轮动模型 |
| 📋 持仓股票盘前观察 | 按板块分类，每板块一个 `stock-table` |
| 🏆 多因子评分 TOP5 | TOP5 评分表 |
| ⚠️ 多因子评分 BOTTOM5 | BOTTOM5 评分表 |
| 🎯 综合策略 | 当日操作策略建议 |

## 关键样式规则
- **头部：** 蓝色下划线 `#58a6ff`（与收盘报告的红色区分）
- **板块标题：** `h2` 蓝色 `#58a6ff`
- **子板块标题：** `sector-title` 也是蓝色 `#58a6ff`（非紫色）
- **RS等级标签：** `tag-aplus` / `tag-a` / `tag-b` / `tag-c` / `tag-d`
- **颜色：** 红涨 (`#f85149`) / 绿跌 (`#3fb950`)
- **每个板块用 `section` 卡片包裹**
