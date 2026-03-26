"""AI 友好导出工具。

导出课程的多层产物：
- full.md: 全量合并文本
- brief.md: 章节摘要
- chunks.jsonl: 检索切块
- toc.json / metadata.json: 元数据
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _strip_markdown_noise(text: str) -> str:
    """清理重复噪声和常见冗余文本。"""
    if not text:
        return ""

    patterns = [
        r"本工具仅供学习交流使用.*?$",
        r"请支持正版内容.*?$",
        r"下载的内容仅供个人学习使用.*?$",
        r"^\s*---\s*$",
    ]

    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _normalize_for_dedupe(text: str) -> str:
    """构建去重键。"""
    normalized = re.sub(r"(?m)^\s*#{1,6}\s+.*?$", "", text or "")
    return re.sub(r"\s+", "", normalized)


def _token_estimate(text: str) -> int:
    """粗略 token 估算，适配中英混合文本。"""
    if not text:
        return 0
    # 中文内容通常 1 token ~= 1~2 字符，这里取保守估算。
    return max(1, len(text) // 2)


def _split_with_budget(text: str, target_tokens: int, overlap_tokens: int) -> List[str]:
    """按预算切块，优先按段落边界。"""
    if not text:
        return []

    target_chars = max(400, target_tokens * 2)
    overlap_chars = max(0, overlap_tokens * 2)

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= target_chars:
            current = candidate
            continue

        if current:
            chunks.append(current.strip())
            if overlap_chars > 0 and len(current) > overlap_chars:
                current = f"{current[-overlap_chars:]}\n\n{para}".strip()
            else:
                current = para
            continue

        # 超长段落：硬切分
        start = 0
        step = target_chars - overlap_chars if target_chars > overlap_chars else target_chars
        while start < len(para):
            end = min(len(para), start + target_chars)
            piece = para[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(para):
                break
            start += max(1, step)
        current = ""

    if current:
        chunks.append(current.strip())

    return chunks


@dataclass
class ChapterSource:
    """AI 导出的章节输入。"""

    chapter_id: str
    title: str
    order: int
    path: Path


def export_ai_pack(
    *,
    course_id: str,
    course_title: str,
    chapter_sources: Iterable[ChapterSource],
    output_dir: Path,
    target_tokens: int = 900,
    overlap_tokens: int = 100,
    top_k: int = 6,
    hard_budget_tokens: int = 6000,
) -> Dict[str, str]:
    """导出 AI pack 产物。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    ordered_sources = sorted(chapter_sources, key=lambda s: s.order)
    now = datetime.now().isoformat()

    full_sections: List[str] = [f"# {course_title}\n"]
    brief_sections: List[str] = [f"# {course_title} 摘要\n"]
    toc: List[dict] = []
    chunk_lines: List[str] = []
    seen_content: set[str] = set()

    chunk_index = 1
    chapter_count = 0
    chunk_count = 0

    for source in ordered_sources:
        if not source.path.exists():
            continue

        raw = source.path.read_text(encoding="utf-8", errors="ignore")
        cleaned = _strip_markdown_noise(raw)
        if not cleaned:
            continue

        key = _normalize_for_dedupe(cleaned)
        if key in seen_content:
            continue
        seen_content.add(key)
        chapter_count += 1

        toc.append(
            {
                "chapter_id": source.chapter_id,
                "title": source.title,
                "order": source.order,
                "path": str(source.path),
            }
        )

        full_sections.append(f"\n## {source.order:03d} {source.title}\n\n{cleaned}\n")

        summary = cleaned[:360].replace("\n", " ").strip()
        brief_sections.append(f"\n## {source.order:03d} {source.title}\n\n{summary}\n")

        for chunk in _split_with_budget(cleaned, target_tokens=target_tokens, overlap_tokens=overlap_tokens):
            payload = {
                "id": f"chunk-{chunk_index:06d}",
                "course_id": course_id,
                "course_title": course_title,
                "chapter_id": source.chapter_id,
                "chapter_title": source.title,
                "chapter_order": source.order,
                "text": chunk,
                "token_estimate": _token_estimate(chunk),
            }
            chunk_lines.append(json.dumps(payload, ensure_ascii=False))
            chunk_index += 1
            chunk_count += 1

    full_path = output_dir / "full.md"
    brief_path = output_dir / "brief.md"
    chunks_path = output_dir / "chunks.jsonl"
    toc_path = output_dir / "toc.json"
    metadata_path = output_dir / "metadata.json"

    full_path.write_text("\n".join(full_sections).strip() + "\n", encoding="utf-8")
    brief_path.write_text("\n".join(brief_sections).strip() + "\n", encoding="utf-8")
    chunks_path.write_text("\n".join(chunk_lines) + ("\n" if chunk_lines else ""), encoding="utf-8")
    toc_path.write_text(json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "generated_at": now,
                "course_id": course_id,
                "course_title": course_title,
                "chapter_count": chapter_count,
                "chunk_count": chunk_count,
                "defaults": {
                    "retrieval_top_k": top_k,
                    "hard_budget_tokens": hard_budget_tokens,
                    "target_chunk_tokens": target_tokens,
                    "overlap_tokens": overlap_tokens,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "full_md": str(full_path),
        "brief_md": str(brief_path),
        "chunks_jsonl": str(chunks_path),
        "toc_json": str(toc_path),
        "metadata_json": str(metadata_path),
    }


def load_chunks(chunks_path: Path) -> List[dict]:
    """加载 chunks.jsonl。"""
    if not chunks_path.exists():
        return []
    rows: List[dict] = []
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def select_chunks_for_query(
    query: str,
    chunks: List[dict],
    *,
    top_k: int = 6,
    hard_budget_tokens: int = 6000,
) -> List[dict]:
    """基于关键词重叠做轻量检索并施加 token 预算。"""
    if not query or not chunks:
        return []

    terms = [t for t in re.split(r"\W+", query.lower()) if t]
    if not terms:
        return []

    scored = []
    for chunk in chunks:
        text = (chunk.get("text") or "").lower()
        score = sum(text.count(term) for term in terms)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected: List[dict] = []
    budget = 0
    for _, chunk in scored[: max(top_k * 3, top_k)]:
        token_est = int(chunk.get("token_estimate", _token_estimate(chunk.get("text", ""))))
        if budget + token_est > hard_budget_tokens:
            continue
        selected.append(chunk)
        budget += token_est
        if len(selected) >= top_k:
            break
    return selected


def build_query_context(
    *,
    query: str,
    pack_dir: Path,
    top_k: int = 6,
    hard_budget_tokens: int = 6000,
) -> Dict[str, object]:
    """根据预算构建问答上下文，超预算或命中不足时回退 brief。"""
    chunks = load_chunks(pack_dir / "chunks.jsonl")
    selected = select_chunks_for_query(
        query,
        chunks,
        top_k=top_k,
        hard_budget_tokens=hard_budget_tokens,
    )
    if selected:
        return {
            "mode": "chunks",
            "selected": selected,
            "text": "\n\n".join(item.get("text", "") for item in selected),
        }

    brief_path = pack_dir / "brief.md"
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    return {
        "mode": "brief",
        "selected": [],
        "text": brief_text,
    }
