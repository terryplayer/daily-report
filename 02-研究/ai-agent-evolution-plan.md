# 🛠️ 混动系统演进方案 — 详细实施说明

> 参考架构：AI智能体标准架构（Allen）
> 更新日期：2026-06-03

---

## 演进项总览

| # | 演进项 | 层级 | 优先级 | 预估工时 |
|:-:|:-------|:----|:------:|:--------:|
| 1 | RAG向量检索 | 记忆层 | 🥇 | 2-3天 |
| 2 | 多智能体专业化分工 | 架构层 | 🥇 | 3-5天 |
| 3 | 自动任务拆解（AI规划器） | 规划层 | 🥈 | 5-7天 |
| 4 | 语音输入 | 输入层 | 🥉 | 1天 |
| 5 | 复盘后自动调整 | 控制循环 | 🥉 | 3-5天 |
| 6 | MCP工具扩展 | 工具层 | 🥈 | 2-3天 |

---

## 1️⃣ RAG向量检索 — 记忆层升级

### 作用
让 Hermes 在做深度分析时，能**自动检索历史经验**。比如：
- 今天分析某只股票 → Hermes 自动查到上周对同一只股票的分析结论
- 做板块判断 → 自动查到历史类似行情下的预测准确率
- 复盘学习后 → 经验自动存入向量库，下次直接可用

### 当前状态
```text
Tablestore → 存了记忆但只能按key查，不能语义搜索
Hermes分析时 → 只能靠当前对话上下文，无法主动查历史
```

### 需要材料
| 材料 | 说明 | 已有？ |
|:----|:-----|:------:|
| 向量数据库 | 存Embedding向量 | ✅ Tablestore已配（text-embedding-v3）|
| Embedding模型 | 文本→向量 | ✅ 通义 text-embedding-v3（已配）|
| 语义搜索接口 | 向量相似度查询 | ❌ 需要构建 |
| 历史数据 | 需要向量化的内容 | ✅ MEMORY.md + 每日日志 |

### 构建方案

#### 第一步：建立记忆向量化管线
```
每日日志 + MEMORY.md + Hermes复盘记录
               ↓
       通义 text-embedding-v3（已配）
               ↓
       Tablestore 向量存储（已有表）
               ↓
       语义搜索接口
```

#### 第二步：在Tablestore中建向量索引
Tablestore 支持向量数据类型，需要：
```sql
-- 在 memories 表中添加向量字段
ALTER TABLE memories ADD COLUMN embedding vector(1024);
ALTER TABLE memories ADD COLUMN memory_type VARCHAR(32);  -- 'analysis'/'reflection'/'daily'
CREATE VECTOR INDEX idx_embedding ON memories(embedding);
```

#### 第三步：封装搜索接口
```python
def search_memories(query, top_k=5):
    # 1. query → text-embedding-v3 → 向量
    # 2. Tablestore 向量相似度搜索
    # 3. 返回最相似的 top_k 条历史记录
    pass
```

#### 第四步：集成到Hermes调用流程
```python
# 在调 Hermes 分析前，先检索相关历史
history = search_memories(f"类似行情：{当前板块} {当前信号}")
prompt = f"历史参考：{history}\n当前数据：{current_data}"
result = exec(f"hermes chat -q '{prompt}' -Q -m deepseek/deepseek-v4-pro")
```

### 依赖
- Tablestore 向量索引功能（阿里云OTS已支持）
- 需要确认当前 Tablestore 实例版本是否支持向量（大概率支持，因为已有embedding配置）
- 不需要额外费用

---

## 2️⃣ 多智能体专业化分工 — 架构演进

### 作用
把现在"我（OpenClaw）包揽所有"的模式，拆成**专业角色各司其职**：

```
                你（十三哥）
                     │
             🌀 主控（小十三）
              /    |    \     \
         研究员  分析师  撰写员  评审员
```

| 角色 | 谁干 | 职责 |
|:----|:-----|:-----|
| 🌀 **主控** | 小十三（OpenClaw） | 接收你的指令、调度任务、展示结果、推送飞书 |
| 🔍 **研究员** | Hermes Agent | 采集行情数据、搜新闻、查信号 |
| 📊 **分析师** | Hermes + V4 Pro | 跑模型评分、趋势判断、概率预测 |
| ✍️ **撰写员** | Hermes | 写报告内容、生成HTML |
| 🔎 **评审员** | Hermes（复盘模式） | 对比预测vs实际、分析偏差、写入记忆 |

### 当前状态
```text
小十三：采集+分析+撰写+推送+复盘 = 全包
Hermes：偶尔被调用做深度分析
```

### 需要材料
| 材料 | 说明 | 已有？ |
|:----|:-----|:------:|
| Hermes Agent | 执行角色任务 | ✅ 已安装 v0.15.1 |
| Hermes的子代理 | 并行执行多任务 | ✅ 内置 `subagent` 功能 |
| Taskflows调度 | 编排各角色工作流 | ✅ 已有流程模板 |

### 构建方案

#### 第一阶段：研究员角色（最简单）
```python
# 研究员：数据采集专用
result = exec("""
    hermes chat -q '你是一个A股研究员。请采集以下数据：1. 昨日北向资金 2. 隔夜美股 3. A50期指 4. 板块热点新闻' \
    -Q -m deepseek/deepseek-v4-pro
""")
```

#### 第二阶段：分析师角色
```python
# 分析师：模型评分+趋势判断
result = exec("""
    hermes chat -q '你是一个A股量化分析师。基于RS排名、MOM动量、MRD偏离度数据，给出板块评分和趋势判断。输出格式：板块 | 综合评分 | 方向 | 概率 | 逻辑' \
    -Q -m deepseek/deepseek-v4-pro
""")
```

#### 第三阶段：撰写员角色
```python
# 撰写员：写报告
result = exec("""
    hermes chat -q '你是一个财经报告撰写员。基于分析师的研究结果，生成收盘简报HTML' \
    -Q -m deepseek/deepseek-v4-pro
""")
```

#### 第四阶段：评审员角色
```python
# 评审员：复盘
result = exec("""
    hermes chat -q '你是一个策略评审员。对比今日盘前预测与实际走势，分析偏差原因，提出改进建议' \
    -Q -m deepseek/deepseek-v4-pro
""")
```

### 跟Hermes内置subagent的结合
Hermes v0.15.1 支持 `subagent` 功能，可以让它自己并行派生子任务：
```python
# 让 Hermes 自己当主控，派生子任务给各角色
exec("hermes chat -q '请作为主控智能体，同时派发3个子任务：研究员采集数据、分析师评分、撰写员报告'")
```
但这个还在评估阶段，先用手动调度更可控。

### 依赖
- ✅ 不需要额外安装任何东西
- 只需要修改 taskflows 中的调用方式

---

## 3️⃣ 自动任务拆解（AI规划器）

### 作用
现在 taskflows 是**人工写死的步骤**：
```text
9:00 → 采集数据 → 跑模型 → 生成HTML → 同步
```

目标是让 AI **自己拆解任务**：
```text
目标：「生成今日收盘简报」
AI自动拆解：
  1. 分析需要哪些数据 → 行情/持仓/信号
  2. 调用研究员采集 → Hermes
  3. 调用分析师评分 → 模型计算
  4. 调用撰写员写报告 → Hermes + 模板
  5. 自我检查 → 格式验证
  6. 输出
```

### 当前状态
```text
Taskflows = 人工编排的步骤说明书
AI执行时严格按照说明书走，不会自己想办法
```

### 需要材料
| 材料 | 说明 | 已有？ |
|:----|:-----|:------:|
| 推理模型 | 能做规划推理 | ✅ DeepSeek V4 Pro |
| 工具列表 | AI知道自己能用什么 | ⚠️ 需要给Hermes一份工具清单 |
| 执行环境 | 能执行Python/Shell | ✅ |

### 构建方案

#### 第一步：给AI定义"能力边界"
创建一个能力清单文件，让AI知道自己能做什么：
```json
{
  "tools": [
    {"name": "web_search", "desc": "搜索网络信息"},
    {"name": "stock_history", "desc": "读取股票历史数据"},
    {"name": "calc_rs", "desc": "计算RS相对强度排名"},
    {"name": "calc_momentum", "desc": "计算动量因子"},
    {"name": "gen_html", "desc": "生成HTML报告"},
    {"name": "push_feishu", "desc": "推送到飞书"},
    {"name": "sync_obsidian", "desc": "同步到Obsidian"},
    ...
  ]
}
```

#### 第二步：AI规划→执行→验证
```python
prompt = f"""
你是一个AI规划器。目标是：{目标}
你能用的工具：{工具清单}
请按以下格式输出：
  1. 思考：当前任务需要哪些步骤
  2. 规划：每一步用什么工具
  3. 执行：按顺序执行
  4. 验证：检查结果是否正确
"""
```

### 依赖
- ✅ 模型已有（V4 Pro做规划足够）
- ✅ 工具已有
- ❌ 需要搭建"规划→执行→验证"的循环框架

---

## 4️⃣ 语音输入

### 作用
飞书语音消息 → 自动转文字 → 我处理

### 当前状态
飞书语音消息来了，我目前看不到内容

### 需要材料
| 材料 | 说明 | 已有？ |
|:----|:-----|:------:|
| 飞书语音消息API | 获取语音文件 | ⚠️ 需要确认飞书API |
| 语音转文字模型 | STT | ✅ 可调OpenAI Whisper或本地 |
| OpenClaw的stt配置 | 已有local whisper配置 | ✅ OpenClaw配置中有stt.local |

### 构建方案
OpenClaw 已经支持语音转文字（stt配置中有local/whisper），只需要在飞书频道中启用语音消息处理即可。可能需要确认飞书WebSocket网关是否支持语音消息格式。

### 依赖
- 飞书语音消息格式确认
- 无需额外费用（Whisper本地运行）

---

## 5️⃣ 复盘后自动调整

### 作用
现在复盘后只记录了经验，但**没有自动调整策略**。比如：
- 复盘发现MRD权重太高导致误判 → 系统自动降低MRD权重
- 复盘发现北向资金信号准确率高 → 系统自动提高该信号权重

### 当前状态
```text
收盘 → 对比预测vs实际 → Hermes分析偏差 → 写入Tablestore
                                                   ↓
                                             结束了！没有下一步
```

### 构建方案

#### 第一步：记录偏差数据
```python
# 每次复盘后，记录结构化偏差信息
{
  "date": "2026-06-03",
  "predictions": [
    {"sector": "通信/电子", "direction": "↑", "probability": 68, "actual": 3.2, "correct": true},
    {"sector": "科技/半导体", "direction": "↑", "probability": 62, "actual": 1.9, "correct": true},
    {"sector": "化工/材料", "direction": "—", "probability": 50, "actual": -0.2, "correct": null},
  ],
  "analysis": "北向资金信号准确...MRD权重偏高导致..."
}
```

#### 第二步：定期调整模型权重
```python
# 每周自动计算各信号的准确率，动态调整权重
current_weights = {"RS": 0.25, "MOM": 0.20, "MRD": 0.10, "MF": 0.30, "ROT": 0.15}
recent_accuracy = calc_signal_accuracy(last_30_days)
# 准确率高的信号提高权重，准确率低的降低权重
new_weights = adjust_weights(current_weights, recent_accuracy)
```

### 依赖
- 需要积累足够多的复盘数据（至少20-30个交易日）
- 预估启动时间：**7月初**（数据够时）

---

## 6️⃣ MCP工具扩展

### 作用
MCP（Model Context Protocol）是AI模型的"USB接口"——通过MCP服务器，可以给Hermes接上任意外部工具：
- 数据库查询
- 外部API调用
- 自定义业务逻辑

### 当前状态
```text
Hermes 支持 MCP（配置中已有 mcp 章节）
但：MCP服务器未配置，未启用
```

### 构建方案
Hermes 文档中提到支持 MCP 集成，可以通过配置 `mcp.servers` 来接入外部服务。

潜在可用的MCP服务器：
- 数据库查询MCP → 直接查Tablestore
- 财经数据MCP → 封装Tushare/东方财富API
- 计算引擎MCP → Python代码执行

### 依赖
- Hermes v0.15.1 支持MCP ✅
- 需要搭建或接入现成的MCP服务器
- 工作量：2-3天

---

## 实施路线图

```text
6月第1周（当前）   ✅ 基础架构 + 复盘循环
                   🔄 临时报告确认

6月第2周           🔷 RAG向量检索（记忆层升级）
                   🔷 研究员角色上线（多智能体第一步）

6月第3周           🔷 分析师+撰写员角色上线
                   🔷 MCP工具扩展

6月第4周           🔷 自动任务拆解（AI规划器实验）
                   🔷 语音输入

7月                🔷 复盘后自动调整（需数据积累）
                   🔷 评审员角色+全角色协奏
```

---

> 📎 同步位置：`memory/ai-agent-evolution-plan.md`
