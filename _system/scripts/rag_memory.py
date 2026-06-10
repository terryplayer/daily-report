#!/usr/bin/env python3
"""
🧠 RAG 向量检索 - 混动系统记忆层

基于 FAISS (本地向量索引) + DashScope text-embedding-v3 实现语义搜索。

工作流程:
  1. 记忆文件 (MEMORY.md + memory/*.md) → 分块 → 向量化 → FAISS 索引
  2. 搜索时: query → 向量 → FAISS 相似度检索 → 返回 top-k 结果
  3. 支持增量索引: 只索引新文件或修改过的文件

集成方式:
  from rag_memory import search_memories, index_all_memories, ensure_indexed

  # 首次使用：索引所有记忆
  index_all_memories()

  # 搜索
  results = search_memories("板块评分方法", top_k=5)

  # Hermes 集成
  history = search_memories(f"关于 {stock_name} 的分析")
  prompt = f"历史参考：{history}\n当前数据：..."
"""

from __future__ import annotations
import json
import os
import re
import hashlib
import pickle
from datetime import datetime
from typing import Optional, Union, List, Dict, Any

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(WORKSPACE, "scripts")
MEMORY_DIR = os.path.join(WORKSPACE, "memory")
MEMORY_FILE = os.path.join(WORKSPACE, "MEMORY.md")

# FAISS 索引和元数据存储路径
INDEX_DIR = os.path.join(WORKSPACE, "memory", ".rag_index")
os.makedirs(INDEX_DIR, exist_ok=True)
FAISS_INDEX_FILE = os.path.join(INDEX_DIR, "index.faiss")
METADATA_FILE = os.path.join(INDEX_DIR, "metadata.json")
HASH_CACHE_FILE = os.path.join(INDEX_DIR, "file_hashes.json")

EMBEDDING_DIM = 1024
CHUNK_SIZE = 512  # 每段截断字符数


# ─── 嵌入 ───────────────────────────────────────
def _get_openai_client():
    """初始化 OpenAI 兼容客户端（指向 DashScope）"""
    from openai import OpenAI

    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path) as f:
        cfg = json.load(f)

    embed_cfg = (
        cfg.get("plugins", {})
        .get("entries", {})
        .get("openclaw-mem0", {})
        .get("config", {})
        .get("oss", {})
        .get("embedder", {})
        .get("config", {})
    )

    return OpenAI(
        api_key=embed_cfg.get("apiKey", ""),
        base_url=embed_cfg.get("baseURL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )


def get_embedding(text: str) -> list[float]:
    """调用 DashScope text-embedding-v3 获取向量"""
    client = _get_openai_client()
    resp = client.embeddings.create(
        model="text-embedding-v3",
        input=text,
        dimensions=EMBEDDING_DIM,
    )
    return resp.data[0].embedding


def get_embeddings_batch(texts: list[str], batch_size: int = 10) -> list[list[float]]:
    """批量获取向量（自动分小批避免 API 限制）"""
    client = _get_openai_client()
    all_embeddings = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        resp = client.embeddings.create(
            model="text-embedding-v3",
            input=batch,
            dimensions=EMBEDDING_DIM,
        )
        indexed = {e.index: e.embedding for e in resp.data}
        all_embeddings.extend(indexed[i] for i in range(len(batch)))
    return all_embeddings


# ─── 文件哈希缓存 ───────────────────────────────
def _load_hash_cache() -> dict:
    """读取文件哈希缓存"""
    if os.path.exists(HASH_CACHE_FILE):
        with open(HASH_CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_hash_cache(cache: dict):
    """保存文件哈希缓存"""
    with open(HASH_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def _file_hash(filepath: str) -> str:
    """计算文件的 MD5 哈希（用于检测变更）"""
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# ─── 记忆文件分块 ──────────────────────────────
def _parse_markdown_chunks(filepath: str) -> list[dict]:
    """
    将 markdown 记忆文件分块。
    按 ## 章节 + 长度阈值切分。

    返回:
      [{"text": "内容", "source": "相对路径", "section": "章节名"}, ...]
    """
    if not os.path.exists(filepath):
        return []

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    rel_path = os.path.relpath(filepath, WORKSPACE)
    lines = content.split("\n")

    chunks = []
    current_section = "前言"
    current_lines = []
    current_len = 0

    for line in lines:
        header = re.match(r"^(#{2,4})\s+(.+)$", line)
        if header:
            # 保存当前块
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text and len(text) > 20:
                    chunks.append({
                        "text": text,
                        "source": rel_path,
                        "section": current_section,
                    })
            current_section = header.group(2).strip()
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len += len(line) + 1
            if current_len > CHUNK_SIZE and len(current_lines) >= 8:
                text = "\n".join(current_lines).strip()
                if text and len(text) > 20:
                    chunks.append({
                        "text": text,
                        "source": rel_path,
                        "section": current_section,
                    })
                current_lines = []
                current_len = 0

    # 收尾
    if current_lines:
        text = "\n".join(current_lines).strip()
        if text and len(text) > 20:
            chunks.append({
                "text": text,
                "source": rel_path,
                "section": current_section,
            })

    return chunks


# ─── FAISS 索引管理 ────────────────────────────
def _load_index():
    """加载 FAISS 索引和元数据"""
    import numpy as np

    if os.path.exists(FAISS_INDEX_FILE):
        try:
            import faiss
            index = faiss.read_index(FAISS_INDEX_FILE)
        except ImportError:
            # 降级：使用暴力搜索
            index = None
    else:
        index = None

    metadata = []
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE) as f:
            metadata = json.load(f)

    return index, metadata


def _save_index(index, metadata: list[dict]):
    """保存 FAISS 索引和元数据"""
    import faiss
    faiss.write_index(index, FAISS_INDEX_FILE)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def _build_index(chunks: list[dict]) -> tuple:
    """
    从 chunks 构建 FAISS 索引

    返回: (faiss.Index, metadata_list)
    """
    import numpy as np
    import faiss

    if not chunks:
        # 空索引
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        return index, []

    texts = [c["text"] for c in chunks]

    # 批量嵌入
    print(f"  🔮 向量化 {len(chunks)} 个 chunks...")
    embeddings = get_embeddings_batch(texts)
    emb_array = np.array(embeddings, dtype=np.float32)

    # 构建 Inner Product (余弦相似度) 索引
    index = faiss.IndexFlatIP(EMBEDDING_DIM)

    # 归一化以便 IP = 余弦相似度
    faiss.normalize_L2(emb_array)
    index.add(emb_array)

    # 元数据
    metadata = [
        {
            "text": c["text"],
            "source": c["source"],
            "section": c["section"],
            "memory_type": _classify_memory(c["source"]),
        }
        for c in chunks
    ]

    return index, metadata


def _classify_memory(source: str) -> str:
    """根据文件名判断记忆类型"""
    s = source.lower()
    if "复盘" in s or "review" in s:
        return "review"
    if source == "MEMORY.md":
        return "root"
    if "模板" in s or "template" in s:
        return "template"
    if re.search(r"\d{4}-\d{2}-\d{2}", s):
        return "daily"
    return "system"


# ─── 公开接口 ───────────────────────────────────
def ensure_indexed(force: bool = False) -> bool:
    """
    确保索引已建立（懒加载）。
    如果索引文件存在且无需重索引，跳过。

    返回: True 表示已就绪
    """
    if os.path.exists(FAISS_INDEX_FILE) and not force:
        return True

    print("📦 首次使用，建立记忆索引...")
    index_all_memories(verbose=True)
    return True


def index_all_memories(verbose: bool = True) -> dict:
    """
    扫描所有记忆文件，检测变更，重建 FAISS 索引。

    扫描:
      - MEMORY.md
      - memory/*.md (每日记录、复盘、模版等)

    返回: {文件名: chunk数}
    """
    hash_cache = _load_hash_cache()
    changed = False
    all_chunks = []

    # 文件列表
    files_to_index = []
    if os.path.exists(MEMORY_FILE):
        files_to_index.append(MEMORY_FILE)

    if os.path.isdir(MEMORY_DIR):
        for fname in sorted(os.listdir(MEMORY_DIR)):
            if fname.startswith(".") or fname.startswith("snapshot") or fname.startswith(".rag"):
                continue
            fpath = os.path.join(MEMORY_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith(".md"):
                files_to_index.append(fpath)

    # 检查变更
    for fpath in files_to_index:
        rel = os.path.relpath(fpath, WORKSPACE)
        current_hash = _file_hash(fpath)
        last_hash = hash_cache.get(rel)

        if current_hash != last_hash:
            hash_cache[rel] = current_hash
            changed = True

    # 无变更且索引已存在 -> 跳过
    if not changed and os.path.exists(FAISS_INDEX_FILE):
        if verbose:
            print("✅ 所有记忆文件无变更，索引已最新")
        return {}

    # 解析所有文件
    for fpath in files_to_index:
        rel = os.path.relpath(fpath, WORKSPACE)
        chunks = _parse_markdown_chunks(fpath)
        if verbose:
            print(f"📄 {rel}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    if not all_chunks:
        if verbose:
            print("⚠️  无记忆内容可索引")
        return {}

    # 构建索引
    index, metadata = _build_index(all_chunks)
    _save_index(index, metadata)
    _save_hash_cache(hash_cache)

    if verbose:
        total = len(metadata)
        print(f"  ✅ 索引完成: {total} chunks, {index.ntotal} 向量")

    # 统计
    report = {}
    for m in metadata:
        src = m["source"]
        report[src] = report.get(src, 0) + 1
    return report


def search_memories(
    query: str,
    top_k: int = 5,
    memory_type: Optional[str] = None,
) -> list[dict]:
    """
    语义搜索历史记忆。

    参数:
        query: 自然语言搜索文本
        top_k: 返回 top-k 条
        memory_type: 过滤类型 (daily/review/system/template/root)，None=不限制

    返回:
        [{
            "text": "记忆原文",
            "source": "来源文件",
            "section": "章节标题",
            "memory_type": "记忆类型",
            "score": 相似度 (0~1),
        }, ...]
    """
    import numpy as np
    import faiss

    if not os.path.exists(FAISS_INDEX_FILE):
        # 自动建立索引
        index_all_memories(verbose=False)

    index, metadata = _load_index()
    if index is None or index.ntotal == 0:
        return []

    # 向量化查询
    query_emb = np.array([get_embedding(query)], dtype=np.float32)
    faiss.normalize_L2(query_emb)

    # 搜索
    n_candidates = min(top_k * 2, index.ntotal)
    scores, indices = index.search(query_emb, n_candidates)

    # 组装结果
    results = []
    for i, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        meta = metadata[idx]
        score = float(scores[0][i])

        # 过滤 memory_type
        if memory_type and meta.get("memory_type") != memory_type:
            continue

        results.append({
            "text": meta["text"][:2000],
            "source": meta["source"],
            "section": meta["section"],
            "memory_type": meta.get("memory_type", ""),
            "score": round(score, 4),
        })

        if len(results) >= top_k:
            break

    return results


def add_to_index(text: str, source: str, section: str = ""):
    """
    向索引中动态添加一条记忆（用于复盘后自动保存经验）。

    参数:
      text:   记忆文本
      source: 来源标识（如 "复盘/2026-06-06"）
      section: 章节
    """
    import numpy as np
    import faiss

    index, metadata = _load_index()

    if index is None:
        # 建新索引
        index = faiss.IndexFlatIP(EMBEDDING_DIM)

    # 向量化
    emb = np.array([get_embedding(text)], dtype=np.float32)
    faiss.normalize_L2(emb)

    # 添加到索引
    index.add(emb)
    metadata.append({
        "text": text,
        "source": source,
        "section": section,
        "memory_type": _classify_memory(source),
    })

    _save_index(index, metadata)
    return len(metadata)


# ─── 集成辅助 ───────────────────────────────────
def format_for_prompt(results: list[dict], max_chars: int = 3000) -> str:
    """
    将搜索结果格式化为提示词上下文。

    示例:
      >>> history = search_memories("板块评分")
      >>> context = format_for_prompt(history)
      >>> prompt = f"历史参考：{context}"
    """
    parts = []
    total = 0

    for r in results:
        entry = (
            f"📄 [{r['source']} > {r['section']}] "
            f"(相似度: {r['score']:.2f})\n"
            f"{r['text'][:500]}"
        )
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        total += len(entry)

    return "\n\n---\n\n".join(parts)


# ─── CLI ─────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="🧠 RAG 记忆检索")
    sub = parser.add_subparsers(dest="command")

    # search
    sp = sub.add_parser("search", help="语义搜索")
    sp.add_argument("query", help="搜索文本")
    sp.add_argument("-k", "--top-k", type=int, default=5)
    sp.add_argument("-t", "--type", help="过滤类型")

    # index
    ip = sub.add_parser("index", help="索引记忆文件")
    ip.add_argument("--force", action="store_true", help="强制重建")

    # add (动态添加)
    ap = sub.add_parser("add", help="添加一条记忆")
    ap.add_argument("text", help="记忆内容")
    ap.add_argument("-s", "--source", default="manual", help="来源")
    ap.add_argument("--section", default="", help="章节")

    args = parser.parse_args()

    if args.command == "search":
        results = search_memories(args.query, top_k=args.top_k, memory_type=args.type)
        print(f"\n🔍 搜索: 「{args.query}」")
        print(f"   找到 {len(results)} 条结果\n")
        for i, r in enumerate(results, 1):
            print(f"── [{i}] score={r['score']:.4f} | {r['source']} > {r['section']} ({r['memory_type']})")
            text = r['text'][:200].replace('\n', ' ')
            print(f"    {text}{'...' if len(r['text']) > 200 else ''}")
            print()

    elif args.command == "index":
        report = index_all_memories(verbose=True)
        if report:
            print(f"\n📊 索引报告:")
            for k, v in report.items():
                print(f"   {k}: {v} chunks")
        else:
            print("  无需更新")

    elif args.command == "add":
        n = add_to_index(args.text, args.source, args.section)
        print(f"✅ 已添加, 索引总计 {n} 条")

    else:
        parser.print_help()


# ─── 交易快照索引（单独FAISS索引，不和文本混合）───────

SNAPSHOT_INDEX_DIR = os.path.join(WORKSPACE, "memory", ".rag_index", "snapshots")
os.makedirs(SNAPSHOT_INDEX_DIR, exist_ok=True)
SNAPSHOT_FAISS_FILE = os.path.join(SNAPSHOT_INDEX_DIR, "snapshots.faiss")
SNAPSHOT_METADATA_FILE = os.path.join(SNAPSHOT_INDEX_DIR, "snapshots_meta.json")

# 交易快照的特征维度定义
# [基准涨跌, 半导体涨跌, 通信涨跌, AI涨跌, 化工涨跌, 能源涨跌,
#  市场宽度, 半导体RS(或涨跌替代), 通信RS(或涨跌替代), AI RS, 化工RS, 能源RS,
#  数据质量指标]
# 注：各板块涨跌用 soft-sign 压缩，避免极端值主导
SNAPSHOT_FEATURE_DIM = 13


def build_snapshot_feature_vector(day_data: dict) -> list[float]:
    """
    从单日行情数据构建特征向量（用于相似度检索）。
    13维：基准涨跌 + 各板块涨跌(soft-sign压缩) + 市场宽度 + RS模拟 + 数据质量
    
    day_data 格式:
    {
        'date': '20260604',
        'benchmark': {'change_pct': 0.35} 或 {'sz_sh': 0.35},
        'actual_sector_changes': {'科技/半导体': 2.1, ...},
        'market_breadth': 0.55,
        'sectors': {'科技/半导体': {'rs_mean': 65, ...}, ...},
    }
    """
    bench = day_data.get('benchmark', {})
    sector_changes = day_data.get('actual_sector_changes', {})
    sectors = day_data.get('sectors', {})
    breadcrumb = day_data.get('market_breadth', 0.5)
    
    # 定义板块顺序
    SECTOR_ORDER = ['科技/半导体', '通信/电子', 'AI/数字经济', '化工/材料', '能源/公用事业']
    
    def _soft_sign(val):
        """soft-sign 压缩，避免极端值主导"""
        return val / (1 + abs(val) / 3)
    
    feat = []
    
    # 1: 基准指数涨跌
    bench_pct = bench.get('change_pct', bench.get('sz_sh', 0))
    if isinstance(bench_pct, (int, float)):
        feat.append(bench_pct)
    else:
        feat.append(0)
    
    # 2-6: 各板块实际涨跌 (soft-sign压缩)
    for sec in SECTOR_ORDER:
        ch = sector_changes.get(sec, 0)
        feat.append(_soft_sign(ch))
    
    # 7: 市场宽度 (上涨股票占比 0~1)
    feat.append(breadcrumb)
    
    # 8-12: RS均分(如果有) 或 用涨跌模拟的RS
    for sec in SECTOR_ORDER:
        s = sectors.get(sec, {})
        rs = s.get('rs_mean')
        if rs is not None:
            feat.append(rs)
        else:
            # 用涨跌模拟RS
            ch = sector_changes.get(sec, 0)
            feat.append(50 + ch * 3)
    
    # 13: 数据质量指标 (非零涨跌幅板块占比)
    non_zero = sum(1 for v in sector_changes.values() if abs(v) > 0.01)
    quality = non_zero / max(len(sector_changes), 1) if sector_changes else 0
    feat.append(min(1.0, quality))
    
    # 保证维度正确
    while len(feat) < SNAPSHOT_FEATURE_DIM:
        feat.append(0)
    
    return feat[:SNAPSHOT_FEATURE_DIM]


def _load_snapshot_index():
    """加载快照FAISS索引和元数据"""
    import numpy as np
    import faiss
    
    if os.path.exists(SNAPSHOT_FAISS_FILE):
        index = faiss.read_index(SNAPSHOT_FAISS_FILE)
    else:
        index = faiss.IndexFlatIP(SNAPSHOT_FEATURE_DIM)
    
    metadata = []
    if os.path.exists(SNAPSHOT_METADATA_FILE):
        with open(SNAPSHOT_METADATA_FILE) as f:
            metadata = json.load(f)
    
    return index, metadata


def _save_snapshot_index(index, metadata):
    """保存快照FAISS索引和元数据"""
    import faiss
    faiss.write_index(index, SNAPSHOT_FAISS_FILE)
    with open(SNAPSHOT_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def index_daily_snapshot(day_data: dict) -> bool:
    """
    将一个交易日的结构化快照添加到索引。
    
    返回: True=成功, False=重复/失败
    """
    import numpy as np
    import faiss
    
    date_str = day_data.get('date', '')
    if not date_str:
        return False
    
    index, metadata = _load_snapshot_index()
    
    # 检查是否已存在（避免重复索引）
    for m in metadata:
        if m.get('date') == date_str:
            return False  # 已存在
    
    # 构建特征向量
    feat = build_snapshot_feature_vector(day_data)
    feat_array = np.array([feat], dtype=np.float32)
    faiss.normalize_L2(feat_array)
    
    # 添加到索引
    index.add(feat_array)
    
    # 保存元数据：包含原始数据和实际涨跌
    metadata.append({
        'date': date_str,
        'benchmark': day_data.get('benchmark', {}),
        'sectors': day_data.get('sectors', {}),
        'actual_sector_changes': day_data.get('actual_sector_changes', {}),
        'rf_prediction': day_data.get('rf_prediction', {}),
        'prediction_accuracy': day_data.get('prediction_accuracy', None),
        'market_breadth': day_data.get('market_breadth', 0.5),
        'north_flow': day_data.get('north_flow', 0),
        'feature_vector': feat,
    })
    
    _save_snapshot_index(index, metadata)
    return True


def search_similar_trading_days(
    day_data_or_features: Union[dict, list],
    top_k: int = 5,
    exclude_date: str = None,
) -> list[dict]:
    """
    搜索历史相似交易日。
    
    参数:
        day_data_or_features: 可以是 day_data dict 或直接传入 feature_vector list
        top_k: 返回 top-k 个
        exclude_date: 排除的日期（如当前日期）
    
    返回:
        [{
            'date': str,  # 交易日
            'score': float,  # 相似度 0~1
            'actual_sector_changes': dict,  # 该日的板块实际涨跌
            'prediction_accuracy': bool | None,  # 该日的预测是否准确
        }, ...]
    """
    import numpy as np
    import faiss
    
    index, metadata = _load_snapshot_index()
    if index.ntotal == 0:
        return []
    
    # 获取查询向量
    if isinstance(day_data_or_features, dict):
        feat = build_snapshot_feature_vector(day_data_or_features)
    else:
        feat = list(day_data_or_features)[:SNAPSHOT_FEATURE_DIM]
        while len(feat) < SNAPSHOT_FEATURE_DIM:
            feat.append(0)
    
    query = np.array([feat], dtype=np.float32)
    faiss.normalize_L2(query)
    
    # 搜索
    n_candidates = min(top_k * 3, index.ntotal)
    scores, indices = index.search(query, n_candidates)
    
    results = []
    for i, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        meta = metadata[idx]
        date_str = meta.get('date', '')
        if exclude_date and date_str == exclude_date:
            continue
        
        results.append({
            'date': date_str,
            'score': float(scores[0][i]),
            'benchmark': meta.get('benchmark', {}),
            'sectors': meta.get('sectors', {}),
            'actual_sector_changes': meta.get('actual_sector_changes', {}),
            'prediction_accuracy': meta.get('prediction_accuracy', None),
            'market_breadth': meta.get('market_breadth', 0.5),
            'north_flow': meta.get('north_flow', 0),
        })
        
        if len(results) >= top_k:
            break
    
    return results


def calc_historical_similarity(
    day_data: dict,
    target_sectors: list[str] = None,
    top_k: int = 5,
) -> dict:
    """
    计算历史相似度得分——作为统一模型的新维度。
    
    逻辑：
      1. 用当前日特征向量检索 top_k 个相似历史日
      2. 每个相似日的得分按相似度加权
      3. 统计相似日各板块的涨跌方向和幅度
      4. 输出 0~100 的板块得分
    
    参数:
        day_data: 当前日行情数据
        target_sectors: 目标板块列表（None=全部）
        top_k: 参考的历史日数
    
    返回:
        {
            'score': float,  # 全局相似度得分 (0~100)
            'sector_scores': {  # 各板块得分
                '科技/半导体': {'score': 68.5, 'direction': '↑', 'confidence': 0.72},
                ...
            },
            'similar_days': [  # 参考的历史日
                {'date': '20260603', 'score': 0.92, ...},
            ]
        }
    """
    similar_days = search_similar_trading_days(
        day_data, top_k=top_k, exclude_date=day_data.get('date')
    )
    
    if not similar_days:
        return {
            'score': 50.0,
            'sector_scores': {},
            'similar_days': [],
            'note': 'insufficient_data',
        }
    
    # 归一化相似度权重
    total_sim = sum(d['score'] for d in similar_days)
    if total_sim <= 0:
        return {
            'score': 50.0,
            'sector_scores': {},
            'similar_days': similar_days,
            'note': 'zero_similarity',
        }
    
    # 按板块统计历史走势
    sector_scores = {}
    all_sectors_found = set()
    for d in similar_days:
        for sec, change in d.get('actual_sector_changes', {}).items():
            all_sectors_found.add(sec)
    
    if target_sectors:
        sectors_to_check = [s for s in target_sectors if s in all_sectors_found]
    else:
        sectors_to_check = list(all_sectors_found)
    
    for sec in sectors_to_check:
        weighted_change = 0.0
        weighted_accuracy = 0.0
        weight_sum = 0.0
        
        for d in similar_days:
            w = d['score'] / total_sim
            change = d.get('actual_sector_changes', {}).get(sec, 0)
            weighted_change += change * w
            
            # 如果该日有预测准确率信息
            acc = d.get('prediction_accuracy')
            if acc is not None:
                weighted_accuracy += (1.0 if acc else 0.0) * w
            weight_sum += w
        
        # 计算得分 (0~100): 涨幅>0给高分, 涨幅<0给低分
        # 参考各模型得分范围
        sec_score = 50 + weighted_change * 3  # 1%涨跌 ≈ ±3分
        sec_score = max(0, min(100, sec_score))
        
        direction = '↑' if weighted_change > 0.5 else ('↓' if weighted_change < -0.5 else '—')
        confidence = min(0.95, weight_sum) if weight_sum > 0 else 0.5
        
        sector_scores[sec] = {
            'score': round(sec_score, 1),
            'direction': direction,
            'confidence': round(confidence, 2),
            'avg_change': round(weighted_change, 2),
            'weighted_accuracy': round(weighted_accuracy, 2),
        }
    
    # 全局得分：所有板块的平均
    global_score = sum(s['score'] for s in sector_scores.values()) / max(len(sector_scores), 1)
    
    return {
        'score': round(global_score, 1),
        'sector_scores': sector_scores,
        'similar_days': [
            {'date': d['date'], 'score': round(d['score'], 4)}
            for d in similar_days
        ],
        'note': 'ok',
    }


def format_rag_context_for_report(
    query: str,
    top_k: int = 3,
    max_chars: int = 2000,
) -> str:
    """
    为报告管线生成结构化的RAG上下文。
    同时搜索文本记忆和交易快照。
    
    返回格式化的上下文字符串，可直接拼入 Hermes prompt。
    """
    parts = []
    
    # 1. 搜索文本记忆
    text_results = search_memories(query, top_k=top_k)
    if text_results:
        text_ctx = "【历史经验参考】\n"
        for r in text_results:
            text_ctx += f"📄 [{r['source']} > {r['section']}] (相似:{r['score']:.2f})\n"
            text_ctx += f"{r['text'][:300]}\n\n"
        if len(text_ctx) > max_chars:
            text_ctx = text_ctx[:max_chars] + "..."
        parts.append(text_ctx)
    
    # 2. 搜索交易快照
    try:
        index, metadata = _load_snapshot_index()
        if index.ntotal > 0:
            # 用 query 的 embedding 和快照向量混合
            query_emb = get_embedding(query)
            # 简单模拟：检查是否有快照数据
            if metadata:
                snap_ctx = "【历史行情参考】\n"
                recent = metadata[-min(3, len(metadata)):]
                for m in recent:
                    date_str = m.get('date', '')
                    bench = m.get('benchmark', {})
                    changes = m.get('actual_sector_changes', {})
                    snap_ctx += f"📊 {date_str}: 上证{bench.get('sz_sh', 0):+.1f}%\n"
                    for sec, ch in list(changes.items())[:3]:
                        snap_ctx += f"  {sec}: {ch:+.1f}%\n"
                parts.append(snap_ctx)
    except Exception:
        pass
    
    return "\n---\n".join(parts)


# ─── CLI ───────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="🧠 RAG 记忆检索")
    sub = parser.add_subparsers(dest="command")

    # search
    sp = sub.add_parser("search", help="语义搜索")
    sp.add_argument("query", help="搜索文本")
    sp.add_argument("-k", "--top-k", type=int, default=5)
    sp.add_argument("-t", "--type", help="过滤类型")

    # index
    ip = sub.add_parser("index", help="索引记忆文件")
    ip.add_argument("--force", action="store_true", help="强制重建")

    # add (动态添加)
    ap = sub.add_parser("add", help="添加一条记忆")
    ap.add_argument("text", help="记忆内容")
    ap.add_argument("-s", "--source", default="manual", help="来源")
    ap.add_argument("--section", default="", help="章节")
    
    # snapshot
    sp_snap = sub.add_parser("snapshot-index", help="查看快照索引状态")
    
    # similar
    sp_sim = sub.add_parser("similar", help="搜索相似历史日")
    sp_sim.add_argument("date", help="目标日期 (YYYYMMDD)")
    sp_sim.add_argument("-k", "--top-k", type=int, default=5)
    
    # context
    sp_ctx = sub.add_parser("context", help="生成RAG上下文")
    sp_ctx.add_argument("query", help="搜索文本")

    args = parser.parse_args()

    if args.command == "search":
        results = search_memories(args.query, top_k=args.top_k, memory_type=args.type)
        print(f"\n🔍 搜索: 「{args.query}」")
        print(f"   找到 {len(results)} 条结果\n")
        for i, r in enumerate(results, 1):
            print(f"── [{i}] score={r['score']:.4f} | {r['source']} > {r['section']} ({r['memory_type']})")
            text = r['text'][:200].replace('\n', ' ')
            print(f"    {text}{'...' if len(r['text']) > 200 else ''}")
            print()

    elif args.command == "index":
        report = index_all_memories(verbose=True)
        if report:
            print(f"\n📊 索引报告:")
            for k, v in report.items():
                print(f"   {k}: {v} chunks")
        else:
            print("  无需更新")

    elif args.command == "add":
        n = add_to_index(args.text, args.source, args.section)
        print(f"✅ 已添加, 索引总计 {n} 条")
    
    elif args.command == "snapshot-index":
        index, metadata = _load_snapshot_index()
        print(f"\n📊 快照索引状态:")
        print(f"   向量数: {index.ntotal}")
        print(f"   交易日: {[m['date'] for m in metadata]}")
    
    elif args.command == "similar":
        # 从历史数据中构建快照并搜索
        hist_file = os.path.join(WORKSPACE, "data", "stock_history.json")
        if os.path.exists(hist_file):
            with open(hist_file) as f:
                hist = json.load(f)
            day_data = hist.get('history', {}).get(args.date, {})
            if day_data:
                results = search_similar_trading_days(day_data)
                print(f"\n🔍 搜索: 与 {args.date} 相似的历史日")
                print(f"   找到 {len(results)} 个相似日\n")
                for i, r in enumerate(results, 1):
                    print(f"── [{i}] {r['date']} 相似度={r['score']:.4f}")
                    ch = r.get('actual_sector_changes', {})
                    for sec, c in list(ch.items())[:3]:
                        print(f"   {sec}: {c:+.1f}%")
                    print()
            else:
                print(f"❌ 未找到 {args.date} 的数据")
        else:
            print("❌ 无历史数据文件")
    
    elif args.command == "context":
        ctx = format_rag_context_for_report(args.query)
        print(ctx)

    else:
        parser.print_help()


# ─── 导出 ───────────────────────────────────────
__all__ = [
    "get_embedding",
    "ensure_indexed",
    "index_all_memories",
    "search_memories",
    "add_to_index",
    "format_for_prompt",
    "search_similar_trading_days",
    "calc_historical_similarity",
    "index_daily_snapshot",
    "build_snapshot_feature_vector",
    "format_rag_context_for_report",
]

if __name__ == "__main__":
    main()
