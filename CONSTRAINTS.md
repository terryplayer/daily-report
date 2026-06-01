# 🔒 固定约束（2026-06-01 与十三哥确认）

## 主页
- **不修改 index.html** — 除非十三哥明确要求
- 主页样式以当前 [daily-report-3ai.pages.dev](https://daily-report-3ai.pages.dev) 为准

## 简报模板（固定不可修改样式/结构）
| 类型 | 固定模板 |
|------|---------|
| 📋 盘前简报 | `premarket-2026-05-29` |
| 🌤 午间监测 | `midday-2026-05-29` |
| 📊 收盘汇总 | `daily-combined-2026-05-29` |
| 📑 周复盘 | `weekly-review-2026-05-31` |

## 发送时间（仅工作日）
- 盘前简报 — 9:15
- 午间监测 — 12:00
- 收盘简报 — 16:00
- 周复盘 — 周日 12:00（仅周日）

## 周末规则
- 周六日不发送盘前/午间/收盘报告
- 周日 12:00 仅发送周复盘

## 主页保护机制
index.html 由三部分组成：
- `scripts/index-shell.html` — 锁定外壳（CSS + header，不可修改）
- 动态生成 — 报告链接卡片（gen_index.py 自动生成）
- `scripts/index-footer.html` — 锁定页脚（不可修改）

每次同步时 gen_index.py 读取外壳和页脚文件，只替换中间卡片部分。
**要修改主页样式，必须修改 index-shell.html 和 index-footer.html 这两个模板文件。**
