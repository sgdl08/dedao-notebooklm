"""课程同步主流程。

sync_course = 拉取课程 -> 增量下载 -> 合并 -> 导出 AI pack -> （可选）上传 NotebookLM。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SRC_DIR = Path(__file__).resolve().parent
SRC_DIR_STR = str(SRC_DIR)
if sys.path[:1] != [SRC_DIR_STR]:
    try:
        sys.path.remove(SRC_DIR_STR)
    except ValueError:
        pass
    sys.path.insert(0, SRC_DIR_STR)

from ai_pack import ChapterSource, export_ai_pack
from dedao.client import DedaoClient
from dedao.downloader import CourseDownloader, DownloadResult
from dedao.models import Chapter
from notebooklm.browser import NotebookLMBrowser


def _sanitize_filename(name: str) -> str:
    for char in '<>:"/\\|？*':
        name = name.replace(char, "_")
    return name.strip()


@dataclass
class SyncResult:
    """同步结果。"""

    course_id: str
    course_title: str
    course_dir: Path
    manifest_path: Path
    chapter_state_path: Path
    downloaded: int
    skipped: int
    failed: int
    ai_pack: Dict[str, str]
    uploaded_files: int = 0
    notebook_id: str = ""
    notebook_url: str = ""


class CourseSyncService:
    """课程同步服务。"""

    def __init__(
        self,
        *,
        client: DedaoClient,
        output_root: Path,
        workers: int = 5,
    ):
        self.client = client
        self.output_root = output_root
        self.workers = workers

    def sync_course(
        self,
        *,
        course_id: str,
        include_audio: bool = False,
        output_format: str = "md",
        upload_to_notebooklm: bool = False,
        notebook_id: Optional[str] = None,
        headless: bool = True,
    ) -> SyncResult:
        """执行课程同步。"""
        detail = self.client.get_course_detail(course_id)
        course_title = detail.course.title
        safe_course_title = _sanitize_filename(course_title)
        course_dir = self.output_root / safe_course_title
        course_dir.mkdir(parents=True, exist_ok=True)

        chapter_state_path = course_dir / "chapter_state.json"
        manifest_path = course_dir / "manifest.json"
        ai_dir = course_dir / "ai_pack"

        state = self._load_state(chapter_state_path)
        chapters = sorted(detail.chapters, key=lambda c: c.sort_order)

        to_download: List[Chapter] = []
        skipped = 0
        for chapter in chapters:
            entry = state.get(chapter.id, {})
            local_path = entry.get("local_path")
            status = entry.get("status")
            if status == "completed" and local_path and Path(local_path).exists():
                skipped += 1
                continue
            to_download.append(chapter)

        downloader = CourseDownloader(
            client=self.client,
            max_workers=self.workers,
            output_dir=self.output_root,
        )

        download_results: List[DownloadResult] = downloader.download_chapters(
            chapters=to_download,
            include_audio=include_audio,
            course_title=course_title,
            output_format=output_format,
            concurrent=True,
        )

        downloaded = 0
        failed = 0
        for result in download_results:
            chapter = result.chapter
            if not chapter:
                continue
            if result.success:
                downloaded += 1
                state[chapter.id] = {
                    "chapter_id": chapter.id,
                    "title": chapter.title,
                    "order": chapter.sort_order,
                    "status": "completed",
                    "local_path": str(result.local_path) if result.local_path else "",
                    "audio_path": str(result.audio_path) if result.audio_path else "",
                    "updated_at": datetime.now().isoformat(),
                    "error": "",
                }
            else:
                failed += 1
                current = state.get(chapter.id, {})
                current.update(
                    {
                        "chapter_id": chapter.id,
                        "title": chapter.title,
                        "order": chapter.sort_order,
                        "status": "failed",
                        "updated_at": datetime.now().isoformat(),
                        "error": result.error or "unknown error",
                    }
                )
                state[chapter.id] = current

        chapter_sources = self._build_chapter_sources(chapters, state)
        merged_path = self._build_merged_markdown(course_title, chapter_sources, course_dir)

        ai_pack_files = export_ai_pack(
            course_id=course_id,
            course_title=course_title,
            chapter_sources=chapter_sources,
            output_dir=ai_dir,
        )
        ai_pack_files["merged_md"] = str(merged_path)

        upload_count = 0
        upload_notebook_id = ""
        upload_notebook_url = ""

        if upload_to_notebooklm:
            browser = NotebookLMBrowser(headless=headless)
            try:
                if notebook_id:
                    browser.set_active_notebook(notebook_id)
                    upload_notebook_id = notebook_id
                    upload_notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
                else:
                    nb = browser.create_notebook(course_title)
                    if nb:
                        upload_notebook_id = nb.id
                        upload_notebook_url = nb.url

                files_to_upload = [Path(ai_pack_files["full_md"]), Path(ai_pack_files["brief_md"])]
                if upload_notebook_id:
                    browser.set_active_notebook(upload_notebook_id)
                    stats = browser.upload_files(files_to_upload)
                    upload_count = stats["success"]
            finally:
                browser.close()

        self._save_state(chapter_state_path, state)

        manifest = {
            "schema_version": "v1",
            "updated_at": datetime.now().isoformat(),
            "course_id": course_id,
            "course_title": course_title,
            "course_dir": str(course_dir),
            "workers": self.workers,
            "total_chapters": len(chapters),
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
            "uploaded_files": upload_count,
            "notebook_id": upload_notebook_id,
            "notebook_url": upload_notebook_url,
            "files": ai_pack_files,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return SyncResult(
            course_id=course_id,
            course_title=course_title,
            course_dir=course_dir,
            manifest_path=manifest_path,
            chapter_state_path=chapter_state_path,
            downloaded=downloaded,
            skipped=skipped,
            failed=failed,
            ai_pack=ai_pack_files,
            uploaded_files=upload_count,
            notebook_id=upload_notebook_id,
            notebook_url=upload_notebook_url,
        )

    @staticmethod
    def _load_state(path: Path) -> Dict[str, dict]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _save_state(path: Path, state: Dict[str, dict]) -> None:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _build_chapter_sources(chapters: List[Chapter], state: Dict[str, dict]) -> List[ChapterSource]:
        sources: List[ChapterSource] = []
        for chapter in chapters:
            entry = state.get(chapter.id, {})
            local_path = entry.get("local_path")
            if not local_path:
                continue
            path = Path(local_path)
            if not path.exists():
                continue
            sources.append(
                ChapterSource(
                    chapter_id=chapter.id,
                    title=chapter.title,
                    order=chapter.sort_order,
                    path=path,
                )
            )
        return sources

    @staticmethod
    def _build_merged_markdown(course_title: str, chapter_sources: List[ChapterSource], course_dir: Path) -> Path:
        output = course_dir / "merged.md"
        lines: List[str] = [f"# {course_title}", ""]
        for source in sorted(chapter_sources, key=lambda s: s.order):
            text = source.path.read_text(encoding="utf-8", errors="ignore").strip()
            lines.extend(
                [
                    f"## {source.order:03d} {source.title}",
                    "",
                    text,
                    "",
                    "---",
                    "",
                ]
            )
        output.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output
