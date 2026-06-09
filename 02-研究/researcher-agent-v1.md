# 🔍 Researcher Agent v1.0 — 研究员角色规范

| 文档编号 | AGENT-RESEARCHER-001 | 版本 | v1.0 | 更新 | 2026-06-09 |
|:---------|:-------------------|:----|:-----|:-----|:----------|
| 状态 | ✅ 正式发布 | 密级 | 内部 | 维护 | 小十三 🌀 |

---

## 📑 目录

1. [概述](#1)
2. [角色定位](#2)
3. [框架设计](#3)
4. [数据资源](#4)
5. [使用方式](#5)
6. [配置说明](#6)
7. [输出规范](#7)
8. [与各角色的协作关系](#8)
9. [演进路线图](#9)

---

<a id="1"></a>

## 1. 概述

### 1.1 什么是 Researcher Agent

Researcher Agent（研究员角色）是混动系统多智能体专业化分工的**第一步**。它将原来"小十三全包"的模式拆出来，形成一个**专攻数据采集与信息检索**的独立智能体。

### 1.2 为什么需要它

| 问题 | 当前状态 | Researcher 解决 |
|:-----|:---------|:--------------|
| 数据采集碎片化 | gen_*.py 各自独立采集，重复工作 | 统一由 Researcher 采集并结构化缓存 |
| 外部信息覆盖不足 | 仅依赖 Tushare + 新浪，缺乏新闻/情绪/外盘 | Researcher 可扩展多源（新闻/社交/研报） |
| 采集与决策耦合 | 采集→分析→撰写混在同一个 cron 任务里 | 采集独立，后续分析/撰写可异步 |
| 异常处理不透明 | 采集失败只抛错，缺乏结构化错误报告 | Researcher 输出结构化状态报告 |
| 数据不可复用 | 每个 cron 任务各自读一次数据 | Researcher 集中缓存，下游按需读取 |

### 1.3 设计原则

```
1️⃣ 专注采集，不分析        Researcher 只负责数据检索和结构化整理
2️⃣ 结构化输出，标准化格式    所有输出必须有 schema，下游消费方按 schema 读取
3️⃣ 容错设计，下限有保底      数据源不可用时，输出状态标记而非崩溃
4️⃣ 异步解耦，不阻塞流程      采集→缓存→通知，不阻塞下游 gen_*.py
```

---

<a id="2"></a>

## 2. 角色定位

### 2.1 一句话定位

> **Researcher Agent 是混动系统的大规模数据采集员和信息检索器。**

它负责在每天的关键时间窗口内，从多个数据源采集行情、新闻、情绪、宏观等数据，**结构化整理后写入缓存**，供下游的 Analyst（分析师）和 Writer（撰写员）使用。

### 2.2 能力清单

| 能力 | 说明 | 状态 |
|:-----|:------|:----:|
| ✅ A股行情采集 | 通过 Tushare API 获取个股日线行情 | v1.0 |
| ✅ 四指数行情 | 通过新浪财经获取四大指数实时数据 | v1.0 |
| ✅ 隔夜外盘 | 通过新浪财经获取道琼斯/纳斯达克/标普 | v1.0 |
| ✅ 北向资金 | 通过 Tushare API 获取北向资金流向 | v1.0 |
| ✅ 行业轮动数据 | 通过 macro_fetch.py 获取板块动量 | v1.0 |
| ✅ 技术指标计算 | RS排名/MOM动量/MRD偏离/BBW布林 | v1.0 |
| ✅ 多因子评分 | 基于 6 个维度计算综合评分 | v1.0 |
| ✅ 支撑/压力位 | 基于 10 日均线计算动态支撑压力 | v1.0 |
| ✅ 波动率预警 | 日内涨跌幅异常检测（±5%阈值） | v1.0 |
| ✅ 数据缓存管理 | 写入 `/tmp/` 缓存供下游读取 | v1.0 |
| ⏳ 新闻情绪采集 | 从东方财富/同花顺/微博获取热点新闻 | v1.1 |
| ⏳ 外围期货/汇率 | 原油/黄金/人民币汇率 | v1.1 |
| ⏳ 财报数据 | 从 Tushare 获取财报/业绩预告 | v1.2 |
| ⏳ 研报观点摘要 | 从公开渠道获取券商研报观点 | v1.2 |
| ⏳ 社交情绪指标 | 股吧/雪球热度分析 | v2.0 |
| ⏳ 定时主动推送异动 | 盘中异动主动警报 | v2.0 |

### 2.3 能力边界（不作的事）

| 不作 | 原因 |
|:-----|:------|
| ❌ 不作趋势判断/预测 | 那是 Analyst 的职责 |
| ❌ 不生成报告内容 | 那是 Writer 的职责 |
| ❌ 不评估预测准确率 | 那是 Reviewer 的职责 |
| ❌ 不写 MEMORY.md | 那是主控的职责 |
| ❌ 不调模型参数 | 那是 Model Engineer 的职责 |
| ❌ 不修改脚本逻辑 | 代码变更由主控统一管理 |

---

<a id="3"></a>

## 3. 框架设计

### 3.1 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                   Researcher Agent v1.0                       │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 行情采集模块  │  │ 信号计算模块  │  │ 信息检索模块  │          │
│  │ StockFetcher │  │ SignalCalc   │  │ InfoSearcher │          │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤          │
│  │· Tushare API │  │· RS排名      │  │· web_search  │          │
│  │· 新浪财经    │  │· MOM动量     │  │· 新闻热点    │          │
│  │· 北向资金    │  │· MRD偏离     │  │· 板块异动    │          │
│  │· 外盘数据    │  │· 多因子评分   │  │· 关键事件    │          │
│  └──────┬──────┘  │· 支撑/压力    │  └──────┬──────┘          │
│         │         └──────┬──────┘         │                  │
│         └────────────────┼────────────────┘                  │
│                          ▼                                   │
│              ┌─────────────────────┐                         │
│              │  数据聚合与缓存管理器  │                         │
│              │  Cache Manager      │                         │
│              ├─────────────────────┤                         │
│              │· dedup / merge      │                         │
│              │· schema validate    │                         │
│              │· timeout handling   │                         │
│              │· fallback / default │                         │
│              └──────────┬──────────┘                         │
│                         ▼                                    │
│              ┌─────────────────────┐                         │
│              │   /tmp/ 缓存输出     │                         │
│              │  stock_analysis_    │                         │
│              │  cache.json         │                         │
│              └─────────────────────┘                         │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────┐
              │     下游消费者       │
              ├─────────────────────┤
              │· gen_premarket.py   │
              │· gen_midday.py      │
              │· gen_closing.py     │
              │· gen_weekly.py      │
              │· Analyst Agent      │
              └─────────────────────┘
```

### 3.2 调用时序（盘前场景为例）

```
时间线    主控(小十三)        Researcher         Analyst          Writer
─────    ──────────        ──────────         ────────          ──────
09:00    ① 触发采集 ──→    ② Tushare抓行情
                           ③ 新浪抓外盘
                           ④ 计算RS/MOM等
                           ⑤ 写入缓存 ──→    ⑥ 读取缓存
                                             ⑦ 趋势判断
                                             ⑧ 概率预测
                                             ⑨ 写入预测 ──→   ⑩ 生成HTML
                                                                ⑪ 部署
09:15                      ⑫ 推送简报
```

### 3.3 缓存数据结构

Researcher 写入 `/tmp/stock_analysis_cache.json` 的标准结构：

```json
{
  "rs_ranking": [
    {
      "code": "688549",
      "name": "中巨芯-U",
      "sector": "科技/半导体",
      "rs_value": 15.2,
      "rs_score": 85,
      "rank": 1,
      "signal": "强势",
      "stock_change_pct": 20.01,
      "bench_change_pct": -3.73
    }
  ],
  "volatility_alerts": [
    { "code": "300322", "name": "硕贝德", "today_change": -15.23, "alert": "暴跌" }
  ],
  "multi_factor_scores": {
    "stocks": [
      {
        "code": "688549",
        "name": "中巨芯-U",
        "sector": "科技/半导体",
        "total_score": 6.4,
        "rs_score": 8.5,
        "mom_score": 7.0,
        "mrd_score": 3.0,
        "bbw_score": 5.0,
        "mf_score": 6.0,
        "rot_score": 5.0
      }
    ],
    "sector_summary": { "科技/半导体": 5.2, "通信/电子": 4.7 },
    "generated_at": "2026-06-09T09:00:00"
  },
  "sector_momentum": {
    "top_sectors": ["能源/公用事业", "通信/电子"],
    "bottom_sectors": ["化工/材料", "AI/数字经济"],
    "spread": 8.5
  },
  "stock_momentum": {
    "688549": {
      "trend_slope_3d": 6.67,
      "trend_label": "强势上攻",
      "support_10d": 14.62,
      "resistance_10d": 19.19,
      "position_pct": 100.0,
      "position_label": "靠近压力"
    }
  },
  "tech_signals": {
    "688549": {
      "name": "中巨芯-U",
      "sector": "科技/半导体",
      "signals": {
        "close": 19.19,
        "data_days": 7,
        "ma5": 15.036,
        "mrd_pct": 27.63,
        "signal": "信号中性"
      }
    }
  }
}
```

---

<a id="4"></a>

## 4. 数据资源

### 4.1 内部资源

| 资源 | 路径 | 用途 | 访问方式 |
|:-----|:-----|:-----|:---------|
| 持仓清单 | `_system/scripts/template-stocks.json` | 确定采集范围 | `json.load(open(...))` |
| 历史行情 | `_system/data/stock_history.json` | 计算技术指标 | `load_history()` |
| 宏观缓存 | `_system/data/macro_cache.json` | 行业轮动数据 | `json.load(open(...))` |
| 模型文件 | `_system/models/rf_*.pkl` | 随机森林预测 | `joblib.load(...)` |
| 持仓看板 | `memory/stock-watchlist.md` | 持仓状态记录 | 主控写入 |
| 今日复盘 | `memory/YYYY-MM-DD.md` | 当日事件日志 | 主控写入 |

### 4.2 外部数据源

| 数据源 | 协议 | 用途 | 频率限制 | 费用 |
|:------|:-----|:-----|:---------|:----|
| Tushare API | HTTP/REST | A股日线行情、北向资金 | 200次/分钟 | 积分制（已有） |
| 新浪财经 | HTTP | 四指数、外盘、实时行情 | 无明确限制 | 免费 |
| web_search (Brave) | API | 新闻热点、关键事件 | 按配额 | 免费配额 |
| 通义 text-embedding-v3 | API | RAG向量化 | 按量 | 月固定¥3 |

### 4.3 依赖的外部工具链

| 工具 | 用途 | 检查方式 |
|:-----|:------|:---------|
| Python 3.9+ | 脚本执行环境 | `python3 --version` |
| Tushare SDK | A股数据接口 | `python3 -c "import tushare; print(tushare.__version__)"` |
| numpy | 数值计算 | `import numpy` |
| joblib | 模型加载 | `import joblib` |
| curl | 新浪财经 HTTP | `curl -s --connect-timeout 5` |
| scikit-learn | 随机森林 | `import sklearn` |

### 4.4 输出文件

| 文件 | 路径 | 格式 | 更新时机 |
|:-----|:-----|:-----|:---------|
| 分析缓存 | `/tmp/stock_analysis_cache.json` | JSON | 每 cycle 覆盖 |
| 盘前内容 | `/tmp/premarket-content.txt` | 纯文本 | 09:00 写入，09:15 读取 |
| 盘前预测 | `/tmp/premarket-predictions.json` | JSON | 09:00 写入 |
| 选股评分 | `_system/daily-report-html/selestock/` | HTML | 20:00 每日 |
| RAG快照 | `memory/.rag_index/` | FAISS索引 | 收盘后更新 |

---

<a id="5"></a>

## 5. 使用方式

### 5.1 触发方式

Researcher Agent 通过以下方式触发：

| 方式 | 时间 | 说明 |
|:-----|:-----|:------|
| ⏰ Cron 调度 | 09:00 盘前数据采集 | 主力采集 cycle，覆盖全量数据 |
| ⏰ Cron 调度 | 12:00 午间动态监测 | 盘中行情快照，增量更新 |
| ⏰ Cron 调度 | 15:30 收盘数据采集 | 收盘数据，含 Hermes 复盘触发 |
| ⌨️ 手动调用 | 任意时间 | 十三哥指令触发 |

### 5.2 调用命令

```bash
# 全量数据采集（盘前/收盘场景）
cd /Users/shisan/.openclaw/workspace/_system
python3 scripts/stock_analysis.py --update
python3 scripts/tushare_fetch.py report
python3 scripts/stock_analysis.py --json > /tmp/stock_analysis_cache.json
python3 scripts/macro_fetch.py --rotation --json

# 增量更新（午间场景）
cd /Users/shisan/.openclaw/workspace/_system
python3 scripts/stock_analysis.py --json > /tmp/stock_analysis_cache.json

# 新闻信息检索（盘前分析辅助）
web_search 查询："A股 今日重大新闻 2026-06-09"
web_search 查询："隔夜美股 收盘 道琼斯 纳斯达克"
```

### 5.3 集成到 Taskflows

在 `taskflows/premarket-data.md` 中，Researcher 环节已自然存在：

```markdown
### 第 4-6 步（Researcher 模块）

4. 更新历史数据 → `stock_analysis.py --update`
5. 获取 Tushare 数据 → `tushare_fetch.py report`
6. 获取分析缓存 → `stock_analysis.py --json > /tmp/stock_analysis_cache.json`
```

### 5.4 调用 Hermes 深度研究

当需要更深度的数据解读时，Researcher 可调用 Hermes：

```python
# Researcher 调用 Hermes 做行情解读
hermes_research = exec(f"""
hermes chat -q '
你是一个A股研究员。请分析以下信息：
1. 昨日北向资金净流入{flow}亿，连续{n}日净流入
2. 隔夜纳指{nasdaq_change}%，道指{dow_change}%
3. 板块强度排序: {top_sectors}
输出格式：简明结构化，含方向判断和置信度。
' -Q -m deepseek/deepseek-v4-flash
""")
```

### 5.5 异常处理流程

```python
# Researcher 异常处理模板
try:
    # 采集数据
    data = collect_all_data()
    # 缓存写
    write_cache(data)
    status = "✅"
except TushareTimeout:
    status = "⚠️ Tushare超时，使用新浪保底"
    data = fallback_from_sina()
    write_cache(data)
except NetworkError:
    status = "❌ 网络不可用，使用本地缓存"
    # 读取上次缓存
    data = read_last_cache()
    write_cache(data, stale=True)
finally:
    # 写入操作报告
    write_status_report(status)
```

---

<a id="6"></a>

## 6. 配置说明

### 6.1 核心配置文件

| 文件 | 路径 | 说明 |
|:-----|:-----|:------|
| 持仓配置 | `_system/scripts/template-stocks.json` | 81只持仓股票清单，按板块分组 |
| 持仓配置（源码） | `_system/scripts/stock_analysis.py` → `WATCHLIST_FULL` | 与 template-stocks.json 同步维护 |
| Tushare Token | `_system/data/tushare_token.txt` | Tushare API 认证凭证 |

### 6.2 关键参数

```python
# stock_analysis.py 中的采集参数
RS_DAYS = 5              # RS排名周期（交易日）
MOM_SHORT = 5            # 短期动量窗口
MOM_LONG = 10            # 长期动量窗口
BBW_PERIOD = 10          # 布林带周期
MRD_PERIOD = 20          # 均值回归偏离周期
VOL_WINDOW = 20          # 波动率窗口
VOL_THRESHOLD = 1.5      # 波动率预警阈值
HISTORY_MAX_DAYS = 60    # 本地缓存最大保留天数
CACHE_TTL_SECONDS = 600  # 缓存有效时间（10分钟）

# Researcher Agent 调度参数
RESEARCH_TIMEOUT = 300   # 采集超时（秒）
RETRY_MAX = 3            # 失败重试次数
RETRY_DELAY = 10         # 重试间隔（秒）
STALE_CACHE_TOLERANCE = 3600  # 允许使用最多1小时前的缓存
```

### 6.3 多环境配置

| 环境 | 说明 | 差异 |
|:-----|:------|:-----|
| 生产环境 | 十三哥的 MacBook Pro | 全量数据源，Tushare 正式 token |
| 回测环境 | 本地 stock_history.json | 使用历史缓存，不调外部 API |
| 故障降级 | 网络不可用 | 使用本地已有缓存 + stale 标记 |

---

<a id="7"></a>

## 7. 输出规范

### 7.1 缓存文件规范

所有 Researcher 输出的缓存文件必须：

```
✅ JSON 格式，UTF-8 编码
✅ 包含 generated_at 时间戳（ISO 8601）
✅ 包含 status 字段（ok/warning/error）
✅ 数据缺失时使用 null 而非空字符串
✅ 数组为空的字段保留字段名，不省略
```

### 7.2 状态码

| 状态 | 含义 | 下游处理 |
|:-----|:------|:---------|
| `ok` | 全部正常 | 正常消费 |
| `warning` | 部分数据源不可用，有保底 | 使用保底数据，报告标记⚠️ |
| `error` | 核心数据不可用 | 使用上次缓存，报告标记❌ |
| `stale` | 使用过期缓存（>1小时） | 使用但有延迟标记 |

### 7.3 错误报告格式

当采集失败或异常时，写入 `/tmp/researcher_status.json`：

```json
{
  "cycle_id": "20260609-0900",
  "started_at": "2026-06-09T09:00:00+08:00",
  "finished_at": "2026-06-09T09:01:23+08:00",
  "status": "warning",
  "modules": {
    "tushare_fetch": { "status": "ok", "stocks_count": 77 },
    "sina_overseas": { "status": "ok", "sources": 2 },
    "stock_analysis": { "status": "ok", "rs_count": 81 },
    "north_flow": { "status": "error", "message": "Tushare API 超时, 使用上次缓存" },
    "news_search": { "status": "ok" }
  },
  "errors": [
    { "module": "north_flow", "error": "Tushare API timeout after 10s", "fallback": "last_cache" }
  ],
  "cache_age_seconds": 45,
  "data_completeness_pct": 92
}
```

---

<a id="8"></a>

## 8. 与各角色的协作关系

### 8.1 多智能体协作全景

```
                     ┌─────────────┐
                     │  十三哥（用户） │
                     └──────┬──────┘
                            │ 飞书
                     ┌──────▼──────┐
                     │ 🌀 主控(小十三) │
                     └──────┬──────┘
            ┌───────────────┼───────────────┐
            │               │               │
     ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
     │ 🔍 Researcher│  │ 📊 Analyst  │  │ ✍️ Writer   │
     │  数据采集    │──│  模型评分    │──│  报告撰写    │
     └──────────────┘  └─────────────┘  └─────────────┘
                                        ┌──────────────┐
                                        │ 🔎 Reviewer  │
                                        │  复盘验证    │
                                        └──────────────┘
```

### 8.2 角色接口契约

| 输入/输出 | 格式 | 生产者→消费者 |
|:----------|:-----|:--------------|
| `stock_analysis_cache.json` | JSON | Researcher → Analyst / Writer |
| `premarket-predictions.json` | JSON | Analyst → Writer |
| `premarket-content.txt` | 纯文本 | Writer → 主控(推送) |
| 持仓评分 HTML | HTML | Writer → 部署管线 |
| Hermes 复盘记录 | Tablestore | Reviewer → 主控 |

### 8.3 协作原则

```
1️⃣ 数据单向流动：Researcher → Analyst → Writer (不反向)
2️⃣ 缓存解耦：Producer写完即完，Consumer读的时候才校验
3️⃣ 各角色独立容错：数据不够时各自降级，不互相等待
4️⃣ 主控统一推送：只有主控有飞书推送权限
```

---

<a id="9"></a>

## 9. 演进路线图

### v1.x 时间线

```
v1.0 (当前) ─── 基础行情采集 + 技术指标 + 缓存管理
               包含：Tushare日线 / 新浪指数 / RS/MOM/MRD/BBW / 多因子 / 支撑压力
               
v1.1 (6月中) ── 扩展数据源：新闻情绪 / 外围期货汇率 / 财报数据
               新增：新闻NLP模块 / 汇率期货采集 / 财报分位
               
v1.2 (7月初) ── 研报观点摘要 / 数据质量监控
               新增：券商研报摘要 / 数据完整性仪表盘 / 采集成功率统计
               
v2.0 (7月底) ── 主动异动推送 / 社交情绪分析
               新增：盘中异动主动警报 / 股吧雪球热度 / 定时器+Webhook
```

### 各版本能力对比

| 能力 | v1.0 | v1.1 | v1.2 | v2.0 |
|:-----|:----:|:----:|:----:|:----:|
| A股日线行情 | ✅ | ✅ | ✅ | ✅ |
| 四指数/外盘 | ✅ | ✅ | ✅ | ✅ |
| 北向资金 | ✅ | ✅ | ✅ | ✅ |
| RS/MOM/MRD/BBW | ✅ | ✅ | ✅ | ✅ |
| 多因子评分 | ✅ | ✅ | ✅ | ✅ |
| 支撑/压力位 | ✅ | ✅ | ✅ | ✅ |
| 波动率预警 | ✅ | ✅ | ✅ | ✅ |
| 缓存管理 | ✅ | ✅ | ✅ | ✅ |
| 结构化状态报告 | ⏳ 待完善 | ✅ | ✅ | ✅ |
| 新闻情绪采集 | ❌ | ✅ | ✅ | ✅ |
| 外围期货/汇率 | ❌ | ✅ | ✅ | ✅ |
| 财报数据 | ❌ | ✅ | ✅ | ✅ |
| 数据质量监控 | ❌ | ❌ | ✅ | ✅ |
| 研报观点摘要 | ❌ | ❌ | ✅ | ✅ |
| 社交情绪分析 | ❌ | ❌ | ❌ | ✅ |
| 主动异动推送 | ❌ | ❌ | ❌ | ✅ |

### 已知限制与待优化

| 问题 | 影响 | 解决方向 | 目标版本 |
|:-----|:-----|:---------|:--------|
| 55/81 只股票支撑压力位缺失 | 持仓报告数据不完整 | 降低最小数据天数 3→2 | v1.1 |
| 外盘数据依赖新浪静态页 | 可能被反爬，格式不稳定 | 接入 Tushare 美股接口 | v1.1 |
| `latest_price` 与 `stock_momentum` 数据源不一致 | 价格来自 tech_signals，趋势来自 stock_momentum | 统一数据入口 | v1.1 |
| 无采集成功率统计 | 不知道数据质量趋势 | 添加采集状态计数器 | v1.2 |
| `/tmp/` 缓存重启后丢失 | 机器重启后需全量重采 | 考虑持久化到 data/ 目录 | v1.2 |
| 盘中增量采集无去重 | 午间重跑全量不经济 | 增量更新模式 | v1.2 |

---

> **相关文档：**
> - `02-研究/混动系统架构说明书.md` — 系统整体架构
> - `02-研究/ai-agent-evolution-plan.md` — 多智能体演进方案
> - `02-研究/股票模型全景.md` — 模型评分体系
> - `02-研究/报告数据类型清单.md` — 报告数据项清单
> - `02-研究/工作流说明书.md` — 日报工作流
> - `02-研究/股票分析四象限模型全景.md` — 四象限评分框架
>
> **维护：** 小十三 🌀 · 2026-06-09
