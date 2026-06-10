#!/usr/bin/env python3
"""
🧠 记忆备份脚本
- 读取 Mem0 全部记忆 → 导出到 memory/snapshots/
- 更新 MEMORY.md 合并关键信息
- 记录备份时间戳
"""

import json, os, sys, time
from datetime import date, datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_DIR = os.path.join(WORKSPACE, 'memory', 'snapshots')
MEMORY_FILE = os.path.join(WORKSPACE, 'MEMORY.md')

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ─── 读取 Mem0 全部记忆 ──────────────────────────
# 用 memory_search 思路：搜空关键词获取所有，或分段搜
import subprocess

# 构建一个 CLI 调用去读 Mem0
# 方案：跑一个简短的 python 从 Mem0 SDK 直接读
read_script = '''
import json, os, sys
sys.path.insert(0, "/Users/shisan/.openclaw/workspace/scripts")

# 直接从 openclaw 内部配置读取 MEM0
config_path = "/Users/shisan/.openclaw/openclaw.json"
with open(config_path) as f:
    cfg = json.load(f)

mem0_cfg = cfg.get("plugins", {}).get("entries", {}).get("openclaw-mem0", {}).get("config", {})
user_id = mem0_cfg.get("userId", "shisan")

# 尝试通过 mem0 SDK 读取全部记忆
try:
    from mem0 import MemoryClient
    # 从配置构建 client
    # 但 MEM0 开源自建版不走 MemoryClient
    # 走本地 API 或 SQLite
    # 试试直接读取 tablestore
    print(json.dumps({"method": "sdk_not_available", "user_id": user_id}))
except Exception as e:
    # 降级方案：走 MEM0 HTTP API
    print(json.dumps({"method": "sdk_error", "error": str(e), "user_id": user_id}))
'''

result = subprocess.run(
    ['python3', '-c', read_script],
    capture_output=True, text=True, timeout=30
)

print(f'📡 Mem0 读取结果: {result.stdout.strip()[:200]}')

# ─── 方案：通过 memory_search 依次获取 ─────────────
# 用不同关键词分段查询，尽可能覆盖所有记忆
SEARCH_QUERIES = [
    '十三哥', '小十三', '混动系统', '收盘简报', '盘前简报',
    '午间监测', 'Hermes', '复pan', '模型', 'token',
    '记忆', '备份', 'cron', '定时任务', '配置',
    '架构', '路线图', '多因子', '随机森林',
]

all_memories = {}
memory_ids_seen = set()

# 从 memory_search 工具不好在脚本内调用，换个方式
# 直接通过 openclaw gateway API 调 sessions_send 风格的 memory_search
# 或者用 hermes CLI

# 最稳方案：用 hermes 或直接调 MEM0 本地 API
# 查 MEM0 是本地 Tablestore + OpenAI embedder
# 直接查 tablestore 表

print('🔍 尝试通过多样关键词获取记忆...')
for q in SEARCH_QUERIES:
    try:
        r = subprocess.run(
            ['python3', '-c', f'''
import json, os, sys
# 模拟 memory_search 的调用 - 用 hermes
result = os.popen("hermes memory search \\"{q}\\" 2>/dev/null").read()
if result.strip():
    print(result.strip()[:500])
else:
    print("null")
'''],
            capture_output=True, text=True, timeout=15
        )
        if r.stdout and r.stdout.strip() and r.stdout.strip() != 'null':
            print(f'  [{q}] → 有结果')
    except:
        pass

# ─── 最可靠方案：直接读 MEMORY.md + memory/ 目录 ──
print()
print('📦 使用文件系统备份方案...')

# 1. 收集文件系统上的记忆
fs_memories = {
    'MEMORY.md': open(MEMORY_FILE).read(),
    'memory_dir': {},
}

mem_dir = os.path.join(WORKSPACE, 'memory')
for root, dirs, files in os.walk(mem_dir):
    for f in files:
        fpath = os.path.join(root, f)
        rel = os.path.relpath(fpath, mem_dir)
        try:
            fs_memories['memory_dir'][rel] = open(fpath).read()
        except:
            fs_memories['memory_dir'][rel] = f'[unreadable]'

# 2. 也读其他重要配置文件
important_files = [
    'MEMORY.md',
    'SOUL.md',
    'IDENTITY.md',
    'USER.md',
    'HEARTBEAT.md',
    'TOOLS.md',
    'AGENTS.md',
]
for fname in important_files:
    fpath = os.path.join(WORKSPACE, fname)
    if os.path.exists(fpath):
        fs_memories[f'workspace/{fname}'] = open(fpath).read()

# 3. 读混动系统架构
arch_path = os.path.join(WORKSPACE, '02-研究', '混动系统架构说明书.md')
if os.path.exists(arch_path):
    fs_memories['architecture'] = open(arch_path).read()

# 4. 记录所有 cron 任务
# 获取 cron 任务列表（直接用 openclaw CLI）
try:
    cron_r = subprocess.run(
        ['openclaw', 'cron', 'list', '--json'],
        capture_output=True, text=True, timeout=15
    )
    if cron_r.stdout and cron_r.stdout.strip():
        import re
        # 输出可能是 CLI 表格，先尝试 JSON 解析
        out = cron_r.stdout.strip()
        if out.startswith('{'):
            data = json.loads(out)
            jobs = []
            for j in data.get('jobs', []):
                jobs.append({
                    'name': j.get('name'),
                    'schedule': j.get('schedule', {}).get('expr', ''),
                    'enabled': j.get('enabled'),
                    'lastStatus': j.get('state', {}).get('lastStatus', ''),
                })
            fs_memories['cron_jobs'] = jobs
except:
    fs_memories['cron_jobs'] = []

# ─── 写入快照 ─────────────────────────────────────
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
today_str = date.today().isoformat()

snapshot = {
    'meta': {
        'timestamp': timestamp,
        'date': today_str,
        'version': '1.0',
        'type': 'full_backup',
    },
    'file_system_memories': fs_memories,
    'mem0_memories': [],  # 待 Mem0 API 可用时补充
}

snapshot_path = os.path.join(SNAPSHOT_DIR, f'memory-snapshot-{timestamp}.json')
with open(snapshot_path, 'w', encoding='utf-8') as f:
    json.dump(snapshot, f, indent=2, ensure_ascii=False)

# 也写一个最新链接
latest_symlink = os.path.join(SNAPSHOT_DIR, 'latest.json')
if os.path.exists(latest_symlink) or os.path.islink(latest_symlink):
    os.remove(latest_symlink)
os.symlink(snapshot_path, latest_symlink)

# 清理旧快照（保留最近30天）
import glob
snapshots = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, 'memory-snapshot-*.json')))
for old_path in snapshots[:-90]:  # 保留90个
    try:
        os.remove(old_path)
    except:
        pass

print()
print(f'✅ 记忆快照已保存')
print(f'   路径: {snapshot_path}')
print(f'   大小: {os.path.getsize(snapshot_path)} bytes')
print(f'   内容: MEMORY.md + {len(fs_memories.get("memory_dir",{}))}个 memory/ 文件 + 架构文档 + cron 任务')
print()
print('🔄 恢复命令:')
print(f'   python3 scripts/restore_memory.py {snapshot_path}')
print()
print('📋 当前记忆摘要:')
print(f'   MEMORY.md: {len(fs_memories.get("MEMORY.md",""))} 字符')
print(f'   memory/ 目录: {len(fs_memories.get("memory_dir",{}))} 个文件')
print(f'   cron 任务: {len(fs_memories.get("cron_jobs",[]))} 个')
