#!/usr/bin/env python3
"""
♻️ 记忆恢复脚本
用法: python3 scripts/restore_memory.py [快照文件路径]
不传参则自动恢复最新的快照 (memory/snapshots/latest.json)

作用：
1. 把快照中的记忆写回 MEMORY.md
2. 恢复 memory/ 目录下的文件
3. 输出摘要供 AI 读取
"""

import json, os, sys, shutil
from datetime import date

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_DIR = os.path.join(WORKSPACE, 'memory', 'snapshots')
MEMORY_FILE = os.path.join(WORKSPACE, 'MEMORY.md')
MEMORY_DIR = os.path.join(WORKSPACE, 'memory')


def find_latest_snapshot():
    latest_link = os.path.join(SNAPSHOT_DIR, 'latest.json')
    if os.path.exists(latest_link):
        real = os.readlink(latest_link)
        if os.path.isabs(real):
            return real
        return os.path.join(SNAPSHOT_DIR, real)
    # fallback: 按文件名排序
    import glob
    snaps = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, 'memory-snapshot-*.json')))
    return snaps[-1] if snaps else None


def restore(snapshot_path):
    if not snapshot_path or not os.path.exists(snapshot_path):
        print(f'❌ 快照文件不存在: {snapshot_path}')
        return False

    with open(snapshot_path, encoding='utf-8') as f:
        snap = json.load(f)

    meta = snap.get('meta', {})
    fs = snap.get('file_system_memories', {})
    mem0 = snap.get('mem0_memories', [])

    print(f'📋 快照信息:')
    print(f'   日期: {meta.get("date", "?")}')
    print(f'   时间: {meta.get("timestamp", "?")}')
    print(f'   类型: {meta.get("type", "?")}')
    print()

    # 1. 恢复 MEMORY.md
    old_memory = fs.get('MEMORY.md', '')
    if old_memory:
        # 备份当前 MEMORY.md
        if os.path.exists(MEMORY_FILE):
            bak = MEMORY_FILE + '.bak'
            shutil.copy2(MEMORY_FILE, bak)
            print(f'📦 当前 MEMORY.md 已备份到: {bak}')

        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            f.write(old_memory)
        print(f'✅ MEMORY.md 已恢复 ({len(old_memory)} 字符)')

    # 2. 恢复 memory/ 目录文件
    mem_files = fs.get('memory_dir', {})
    restored_count = 0
    for rel_path, content in mem_files.items():
        full_path = os.path.join(MEMORY_DIR, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        restored_count += 1
    print(f'✅ memory/ 目录已恢复 {restored_count} 个文件')

    # 3. 恢复 workspace 根文件
    ws_files = {k: v for k, v in fs.items() if k.startswith('workspace/')}
    for rel_path, content in ws_files.items():
        fname = rel_path.replace('workspace/', '')
        fpath = os.path.join(WORKSPACE, fname)
        if os.path.exists(fpath):
            # 备份当前
            bak = fpath + '.bak'
            shutil.copy2(fpath, bak)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'✅ {fname} 已恢复')

    # 4. 输出摘要（供 AI 读取上下文）
    print()
    print('━' * 40)
    print('🧠 恢复摘要（AI 读取用）')
    print('━' * 40)
    print()
    print(f'📅 快照日期: {meta.get("date", "?")}')
    print()

    # 输出 MEMORY.md 内容
    if old_memory:
        print('--- MEMORY.md ---')
        print(old_memory)
        print()

    # 输出 cron 任务
    cron_jobs = fs.get('cron_jobs', [])
    if cron_jobs:
        print(f'--- Cron 任务 ({len(cron_jobs)}个) ---')
        for j in cron_jobs:
            enabled = '🟢' if j.get('enabled') else '⚪'
            print(f'  {enabled} {j.get("name","?")} [{j.get("schedule","")}]')
        print()

    # 输出架构文档摘要
    arch = fs.get('architecture', '')
    if arch:
        lines = arch.split('\n')
        print(f'--- 混动系统架构 ({len(arch)}字符) ---')
        # 只打印前20行和关键标签
        for line in lines[:30]:
            if line.strip():
                print(f'  {line[:100]}')
        if len(lines) > 30:
            print(f'  ... (共 {len(lines)} 行)')
        print()

    if mem0:
        print(f'--- Mem0 记忆 ({len(mem0)}条) ---')
        for m in mem0:
            print(f'  - {m.get("text","")[:100]}')

    return True


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        path = sys.argv[1]
    else:
        path = find_latest_snapshot()

    print('♻️  记忆恢复工具')
    print()

    if restore(path):
        print()
        print('✅ 恢复完成')
    else:
        print()
        print('❌ 恢复失败')
        sys.exit(1)
