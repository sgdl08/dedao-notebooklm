"""AI pack 导出测试。"""

import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_pack import ChapterSource, build_query_context, export_ai_pack


def test_export_ai_pack_creates_outputs(tmp_path: Path):
    chapter1 = tmp_path / "001_intro.md"
    chapter2 = tmp_path / "002_dup.md"
    chapter3 = tmp_path / "003_unique.md"

    chapter1.write_text("# 介绍\n\n这是一个测试章节。", encoding="utf-8")
    chapter2.write_text("# 重复\n\n这是一个测试章节。", encoding="utf-8")
    chapter3.write_text("# 唯一\n\n这是另一个章节，包含更多内容。", encoding="utf-8")

    output_dir = tmp_path / "ai_pack"
    files = export_ai_pack(
        course_id="c1",
        course_title="测试课程",
        chapter_sources=[
            ChapterSource(chapter_id="1", title="介绍", order=1, path=chapter1),
            ChapterSource(chapter_id="2", title="重复", order=2, path=chapter2),
            ChapterSource(chapter_id="3", title="唯一", order=3, path=chapter3),
        ],
        output_dir=output_dir,
        target_tokens=50,
        overlap_tokens=10,
    )

    for key in ("full_md", "brief_md", "chunks_jsonl", "toc_json", "metadata_json"):
        assert key in files
        assert Path(files[key]).exists()

    metadata = json.loads(Path(files["metadata_json"]).read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "v1"
    assert metadata["course_id"] == "c1"
    assert metadata["chunk_count"] >= 1
    # chapter2 与 chapter1 内容一致，应被去重
    assert metadata["chapter_count"] == 2


def test_build_query_context_fallback_and_budget(tmp_path: Path):
    chapter = tmp_path / "001.md"
    chapter.write_text("# 测试\n\n学习效率和阅读方法。", encoding="utf-8")
    pack_dir = tmp_path / "ai_pack"
    export_ai_pack(
        course_id="c1",
        course_title="测试课程",
        chapter_sources=[ChapterSource(chapter_id="1", title="测试", order=1, path=chapter)],
        output_dir=pack_dir,
        target_tokens=30,
        overlap_tokens=5,
    )

    hit = build_query_context(query="阅读 方法", pack_dir=pack_dir, top_k=2, hard_budget_tokens=100)
    assert hit["mode"] == "chunks"
    assert hit["text"]

    miss = build_query_context(query="完全不相关关键词", pack_dir=pack_dir, top_k=2, hard_budget_tokens=100)
    assert miss["mode"] == "brief"
    assert "摘要" in miss["text"]
