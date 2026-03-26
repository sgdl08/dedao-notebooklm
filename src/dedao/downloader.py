"""得到内容下载器

支持并发下载课程章节内容和音频文件。
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .client import DedaoClient
from .models import Course, Chapter, CourseDetail
from utils import get_config

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """下载进度"""
    chapter_id: str
    chapter_title: str
    status: str  # pending, downloading, completed, failed
    message: str = ""
    total: int = 0
    current: int = 0


@dataclass
class DownloadResult:
    """下载结果"""
    success: bool
    chapter: Optional[Chapter] = None
    error: Optional[str] = None
    local_path: Optional[Path] = None
    audio_path: Optional[Path] = None


class CourseDownloader:
    """课程下载器

    支持并发下载课程的所有章节内容和音频。
    """

    def __init__(
        self,
        client: DedaoClient,
        max_workers: int = 5,
        output_dir: Optional[Path] = None
    ):
        """初始化下载器

        Args:
            client: DedaoClient 实例
            max_workers: 最大并发数
            output_dir: 输出目录，默认为 ./downloads
        """
        self.client = client
        self.max_workers = max_workers
        self.output_dir = output_dir or Path(get_config().download_dir)

        # 进度回调
        self._progress_callback: Optional[Callable[[DownloadProgress], None]] = None

    def set_progress_callback(self, callback: Callable[[DownloadProgress], None]):
        """设置进度回调函数"""
        self._progress_callback = callback

    def _notify_progress(self, progress: DownloadProgress):
        """通知进度更新"""
        if self._progress_callback:
            self._progress_callback(progress)
        else:
            # 默认输出日志
            if progress.status == "completed":
                logger.info(f"✓ {progress.chapter_title}")
            elif progress.status == "failed":
                logger.error(f"✗ {progress.chapter_title}: {progress.message}")
            else:
                logger.debug(f"{progress.status}: {progress.chapter_title}")

    def download_course(
        self,
        course_id: str,
        include_audio: bool = True,
        output_format: str = "md",
        concurrent: bool = True,
    ) -> List[DownloadResult]:
        """下载整个课程

        Args:
            course_id: 课程 ID
            include_audio: 是否下载音频
            output_format: 输出格式 ("md" 或 "pdf")

        Returns:
            下载结果列表
        """
        # 获取课程详情
        logger.info(f"准备下载课程：{course_id}")
        course_detail = self.client.get_course_detail(course_id)

        logger.info(f"课程：{course_detail.course.title}, 共 {course_detail.total_chapters} 章")

        # 下载所有章节
        results = self.download_chapters(
            course_detail.chapters,
            include_audio=include_audio,
            course_title=course_detail.course.title,
            output_format=output_format,
            concurrent=concurrent,
        )

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        logger.info(f"下载完成：{success_count}/{len(results)} 成功")

        return results

    def download_chapters(
        self,
        chapters: List[Chapter],
        include_audio: bool = True,
        course_title: str = "unknown",
        output_format: str = "md",
        concurrent: bool = True,
    ) -> List[DownloadResult]:
        """下载章节列表（兼容老接口名）。

        Args:
            chapters: 章节列表
            include_audio: 是否下载音频
            course_title: 课程标题
            output_format: 输出格式 ("md" 或 "pdf")
            concurrent: 是否并发下载

        Returns:
            下载结果列表
        """
        if not chapters:
            return []

        if concurrent:
            return self.download_chapters_concurrent(
                chapters=chapters,
                include_audio=include_audio,
                course_title=course_title,
                output_format=output_format,
            )

        results: List[DownloadResult] = []
        for chapter in chapters:
            results.append(
                self.download_chapter(
                    chapter=chapter,
                    include_audio=include_audio,
                    course_title=course_title,
                    output_format=output_format,
                )
            )
        return results

    def download_audios(
        self,
        chapters: List[Chapter],
        course_title: str = "unknown",
        concurrent: bool = True,
    ) -> List[DownloadResult]:
        """仅下载音频（兼容老接口名）。"""
        return self.download_chapters(
            chapters=chapters,
            include_audio=True,
            course_title=course_title,
            output_format="md",
            concurrent=concurrent,
        )

    def download_chapter(
        self,
        chapter: Chapter,
        include_audio: bool = True,
        course_title: str = "unknown",
        output_format: str = "md",
    ) -> DownloadResult:
        """下载单个章节

        Args:
            chapter: 章节对象
            include_audio: 是否下载音频
            course_title: 课程标题（用于创建目录）
            output_format: 输出格式 ("md" 或 "pdf")

        Returns:
            下载结果
        """
        # 通知开始下载
        self._notify_progress(DownloadProgress(
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            status="downloading"
        ))

        try:
            # 获取章节详细内容
            chapter_detail = self.client.get_chapter_content(chapter.id)

            # 创建课程目录
            course_dir = self._sanitize_filename(course_title)
            base_path = self.output_dir / course_dir
            base_path.mkdir(parents=True, exist_ok=True)

            # 保存文字内容
            md_path = None
            pdf_path = None
            if chapter_detail.content:
                # 使用原始章节的 sort_order，因为 chapter_detail.sort_order 可能不准确
                filename = self._sanitize_filename(f"{chapter.sort_order:03d}_{chapter_detail.title}")

                # 尝试将 JSON 内容转换为 Markdown
                content_to_save = chapter_detail.content
                markdown_content = None
                try:
                    content_data = json.loads(chapter_detail.content)
                    if isinstance(content_data, list):
                        # 使用延迟导入避免循环依赖
                        from converter import contents_to_markdown
                        content_to_save = contents_to_markdown(content_data)
                        markdown_content = content_to_save
                        logger.debug(f"JSON 内容已转换为 Markdown")
                except (json.JSONDecodeError, ImportError) as e:
                    # 如果不是 JSON 或转换失败，保持原内容
                    logger.debug(f"保持原始内容格式: {e}")

                # 根据输出格式保存
                if output_format == "pdf" and markdown_content:
                    # 保存为 PDF
                    pdf_path = base_path / f"{filename}.pdf"
                    try:
                        from converter import convert_markdown_to_pdf
                        result = convert_markdown_to_pdf(markdown_content, pdf_path, title=chapter_detail.title)
                        if result and result.suffix == '.pdf':
                            logger.debug(f"保存 PDF 内容：{pdf_path}")
                        else:
                            # PDF 生成失败，保存为 Markdown
                            md_path = base_path / f"{filename}.md"
                            md_path.write_text(content_to_save, encoding="utf-8")
                            logger.warning(f"PDF 生成失败，保存为 Markdown：{md_path}")
                    except Exception as e:
                        # PDF 生成失败，保存为 Markdown
                        md_path = base_path / f"{filename}.md"
                        md_path.write_text(content_to_save, encoding="utf-8")
                        logger.warning(f"PDF 生成失败 ({e})，保存为 Markdown：{md_path}")
                else:
                    # 保存为 Markdown
                    md_path = base_path / f"{filename}.md"
                    md_path.write_text(content_to_save, encoding="utf-8")
                    logger.debug(f"保存文字内容：{md_path}")

            # 下载音频
            audio_path = None
            if include_audio and chapter_detail.audio_url:
                try:
                    audio_filename = self._sanitize_filename(f"{chapter.sort_order:03d}_{chapter_detail.title}.mp3")
                    audio_path = base_path / audio_filename
                    self.client.download_file(chapter_detail.audio_url, audio_path)
                except Exception as e:
                    logger.warning(f"下载音频失败：{chapter_detail.audio_url}, 错误：{e}")

            # 更新章节信息
            chapter.content = chapter_detail.content
            chapter.audio_url = chapter_detail.audio_url
            chapter.downloaded = True
            chapter.local_path = str(pdf_path or md_path) if (pdf_path or md_path) else None

            # 通知完成
            self._notify_progress(DownloadProgress(
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                status="completed"
            ))

            return DownloadResult(
                success=True,
                chapter=chapter,
                local_path=pdf_path or md_path,
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

            return DownloadResult(
                success=False,
                chapter=chapter,
                error=str(e)
            )

    def download_chapters_concurrent(
        self,
        chapters: List[Chapter],
        include_audio: bool = True,
        course_title: str = "unknown",
        output_format: str = "md",
    ) -> List[DownloadResult]:
        """并发下载多个章节

        Args:
            chapters: 章节列表
            include_audio: 是否下载音频
            course_title: 课程标题

        Returns:
            下载结果列表
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self.download_chapter,
                    chapter,
                    include_audio,
                    course_title,
                    output_format,
                ): chapter for chapter in chapters
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    chapter = futures[future]
                    logger.error(f"下载章节异常：{chapter.title}, 错误：{e}")
                    results.append(DownloadResult(
                        success=False,
                        chapter=chapter,
                        error=str(e)
                    ))

        return results

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        # Windows 和 macOS 不允许的字符
        invalid_chars = '<>:"/\\|？*'

        result = filename
        for char in invalid_chars:
            result = result.replace(char, "_")

        # 移除前后空格
        return result.strip()
