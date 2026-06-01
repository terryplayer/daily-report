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

## 简报模板修改流程
- 要修改简报样式时，先改本地的 `scripts/template-xxx.html` 文件
- 改完后同步到 Obsidian
- 修改后第二天18:00的每日选股评分任务会自动应用到新生成的报告
- 不得在生成简报时临时修改样式

## 模板文件一览
| 文件 | 说明 |
|------|------|
| `scripts/template-premarket.html` | 盘前简报CSS+结构模板 |
| `scripts/template-midday.html` | 午间报告CSS+结构模板 |
| `scripts/template-daily-combined.html` | 收盘简报CSS+结构模板 |
| `scripts/template-stocks.json` | 持仓股票清单（简报使用这个，不是config） |

## 模板优先级（2026-06-01 补充）
所有定时任务遵循以下模板优先级：

### 1️⃣ 执行流程模板（最高优先级）
- `scripts/taskflows/*.md` — 每次任务先读取对应的流程模板文件
- 流程修改必须先改对应的 `.md` 文件
- 不得在 cron prompt 中直接写长流程

### 2️⃣ 样式模板
- `scripts/template-premarket.html` — 盘前简报
- `scripts/template-midday.html` — 午间报告
- `scripts/template-daily-combined.html` — 收盘简报

### 3️⃣ 数据模板
- `scripts/template-stocks.json` — 持仓股票清单

### 修改流程
修改样式/流程 → 先改对应的 template/taskflow 文件 → 同步 Obsidian → 自动生效
