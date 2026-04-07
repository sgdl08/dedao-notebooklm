"""课程下载器

支持并发下载课程章节内容和音频文件。
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .client import CourseClient
from ..models import Course, Chapter, CourseDetail

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """下载进度"""
    chapter_id: str
    chapter_title: str
    status: str  # pending, downloading, completed, failed
    message: str = ""


@dataclass
class DownloadResult:
    """下载结果"""
    success: bool
    chapter: Optional[Chapter] = None
    error: Optional[str] = None
    local_path: Optional[Path] = None
    audio_path: Optional[Path] = None


class CourseDownloader:
    """课程下载器"""

    def __init__(
        self,
        client: Optional[CourseClient] = None,
        output_dir: Optional[Path] = None,
        max_workers: int = 5
    ):
        self.client = client or CourseClient()
        self.output_dir = output_dir or Path("./downloads")
        self.max_workers = max_workers
        self._progress_callback: Optional[Callable[[DownloadProgress], None]] = None

    def set_progress_callback(self, callback: Callable[[DownloadProgress], None]):
        """设置进度回调"""
        self._progress_callback = callback

    def _notify_progress(self, progress: DownloadProgress):
        """通知进度"""
        if self._progress_callback:
            self._progress_callback(progress)
        elif progress.status == "completed":
            logger.info(f"✓ {progress.chapter_title}")
        elif progress.status == "failed":
            logger.error(f"✗ {progress.chapter_title}: {progress.message}")

    def download_course(
        self,
        course_id: str,
        include_audio: bool = True,
        output_format: str = "md"
    ) -> List[DownloadResult]:
        """下载整个课程"""
        logger.info(f"准备下载课程：{course_id}")
        course_detail = self.client.get_course_detail(course_id)

        logger.info(f"课程：{course_detail.course.title}, 共 {course_detail.total_chapters} 章")

        results = []
        for chapter in course_detail.chapters:
            result = self.download_chapter(
                chapter,
                include_audio=include_audio,
                course_title=course_detail.course.title,
                output_format=output_format
            )
            results.append(result)

        success_count = sum(1 for r in results if r.success)
        logger.info(f"下载完成：{success_count}/{len(results)} 成功")

        return results

    def download_chapter(
        self,
        chapter: Chapter,
        include_audio: bool = True,
        course_title: str = "unknown",
        output_format: str = "md"
    ) -> DownloadResult:
        """下载单个章节"""
        self._notify_progress(DownloadProgress(
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            status="downloading"
        ))

        try:
            chapter_detail = self.client.get_chapter_content(chapter.id)

            course_dir = self._sanitize_filename(course_title)
            base_path = self.output_dir / course_dir
            base_path.mkdir(parents=True, exist_ok=True)

            # 保存内容
            local_path = None
            if chapter_detail.content:
                filename = self._sanitize_filename(f"{chapter.sort_order:03d}_{chapter_detail.title}")
                content_to_save = chapter_detail.content

                # 尝试转换 JSON 为 Markdown
                try:
                    content_data = json.loads(chapter_detail.content)
                    if isinstance(content_data, list):
                        content_to_save = self._contents_to_markdown(content_data)
                except (json.JSONDecodeError, TypeError):
                    pass

                local_path = base_path / f"{filename}.md"
                local_path.write_text(content_to_save, encoding="utf-8")

            # 下载音频
            audio_path = None
            if include_audio and chapter_detail.audio_url:
                audio_filename = self._sanitize_filename(f"{chapter.sort_order:03d}_{chapter_detail.title}.mp3")
                audio_path = base_path / audio_filename
                try:
                    self.client.download_file(chapter_detail.audio_url, audio_path)
                except Exception as e:
                    logger.warning(f"下载音频失败：{e}")

            self._notify_progress(DownloadProgress(
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                status="completed"
            ))

            return DownloadResult(
                success=True,
                chapter=chapter,
                local_path=local_path,
                audio_path=audio_path
            )

        except Exception as e:
            logger.error(f"下载章节失败：{chapter.title}, 错误：{e}")
            self._notify_progress(DownloadProgress(
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                status="failed",
                message=str(e)
            ))
            return DownloadResult(success=False, chapter=chapter, error=str(e))

    def download_chapters_concurrent(
        self,
        chapters: List[Chapter],
        include_audio: bool = True,
        course_title: str = "unknown"
    ) -> List[DownloadResult]:
        """并发下载多个章节"""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.download_chapter, ch, include_audio, course_title): ch
                for ch in chapters
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    chapter = futures[future]
                    results.append(DownloadResult(success=False, chapter=chapter, error=str(e)))

        return results

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名"""
        result = re.sub(r'[<>:"/\\|?*]', '', name)
        return result[:100].strip()

    def _contents_to_markdown(self, contents: list) -> str:
        """将内容列表转换为 Markdown"""
        lines = []
        for item in contents:
            if isinstance(item, dict):
                text = item.get("text", "") or item.get("content", "")
                if text:
                    lines.append(text)
            elif isinstance(item, str):
                lines.append(item)
        return "\n\n".join(lines)


# 便捷函数
def download_course(course_id: str, output_dir: Optional[Path] = None) -> List[DownloadResult]:
    """下载课程（便捷函数）"""
    downloader = CourseDownloader(output_dir=output_dir)
    return downloader.download_course(course_id)
