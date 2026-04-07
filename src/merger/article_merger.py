"""文章合并器

将专栏文章按分类合并成 Markdown 文件。
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedao.models import Chapter, CourseDetail
from converter.html_to_md import HTMLToMarkdownConverter

logger = logging.getLogger(__name__)


@dataclass
class MergedSection:
    """合并后的章节"""
    title: str
    articles: List[Chapter]
    order: int = 0


class ArticleMerger:
    """文章合并器

    将课程章节按分类合并成 Markdown 文件。
    """

    def __init__(self, max_sources_per_notebook: int = 45):
        """初始化合并器

        Args:
            max_sources_per_notebook: 每个 Notebook 最大源文件数（默认 45，预留余量）
        """
        self.max_sources = max_sources_per_notebook
        self._converter = HTMLToMarkdownConverter()

    def merge_by_category(
        self,
        course_detail: CourseDetail,
        output_dir: Path
    ) -> List[Path]:
        """按分类合并文章

        Args:
            course_detail: 课程详情
            output_dir: 输出目录

        Returns:
            合并后的文件路径列表
        """
        # 创建课程目录
        course_dir = output_dir / self._sanitize_name(course_detail.course.title)
        course_dir.mkdir(parents=True, exist_ok=True)

        # 尝试从章节中提取分类信息
        categories = self._extract_categories(course_detail.chapters)

        if not categories:
            # 如果没有分类，按章节数量决定是否合并
            logger.info("未检测到分类信息，按章节合并")
            return self._merge_by_chunks(course_detail, course_dir)

        logger.info(f"检测到 {len(categories)} 个分类")
        merged_files = []

        for idx, (category_name, chapters) in enumerate(categories.items()):
            category_file = course_dir / f"{idx + 1:02d}_{self._sanitize_name(category_name)}.md"

            # 合并该分类下的所有文章
            content = self._merge_chapters(chapters, category_name)
            category_file.write_text(content, encoding='utf-8')

            logger.info(f"已合并分类 '{category_name}': {len(chapters)} 篇文章 -> {category_file}")
            merged_files.append(category_file)

        return merged_files

    def _extract_categories(self, chapters: List[Chapter]) -> Dict[str, List[Chapter]]:
        """从章节中提取分类

        得到的课程通常有以下结构：
        - 分类/模块名称（如"发刊词"、"第一部分"、"模块一"等）
        - 同一分类下的多个章节

        Args:
            chapters: 章节列表

        Returns:
            分类 -> 章节列表 的字典
        """
        categories: Dict[str, List[Chapter]] = {}

        for chapter in chapters:
            # 尝试从标题中提取分类
            category = self._guess_category(chapter.title)

            if category not in categories:
                categories[category] = []
            categories[category].append(chapter)

        return categories

    def _guess_category(self, title: str) -> str:
        """从章节标题猜测分类

        得到的课程标题通常有以下模式：
        - "001 | 发刊词" -> 发刊词
        - "01 | 第一章：XXX" -> 第一章
        - "模块一 01 | XXX" -> 模块一
        - "001. 标题" -> 默认分类

        Args:
            title: 章节标题

        Returns:
            分类名称
        """
        import re

        # 移除章节序号前缀
        title_clean = re.sub(r'^[\d]+[\.|：:]\s*', '', title.strip())

        # 检查是否包含模块/部分标识
        module_match = re.match(r'^(模块 [一二三四五六七八九十\d]+|第 [一二三四五六七八九十\d]+ 部分 | 第 [一二三四五六七八九十\d]+ 篇)', title_clean)
        if module_match:
            return module_match.group(1)

        # 检查是否是发刊词/序言等
        special_match = re.match(r'^(发刊词 | 序言 | 前言 | 导读 | 导论)', title_clean)
        if special_match:
            return special_match.group(1)

        # 默认使用第一个有意义的词组作为分类
        # 尝试提取 "第一章" 这种格式
        chapter_match = re.match(r'^(第 [\d]+ 章)', title_clean)
        if chapter_match:
            return chapter_match.group(1)

        # 如果没有明确的分类，返回"默认分类"
        return "正文"

    def _merge_chapters(
        self,
        chapters: List[Chapter],
        category_name: str,
        convert_html: bool = True
    ) -> str:
        """合并多个章节成一个 Markdown 文件

        Args:
            chapters: 章节列表
            category_name: 分类名称
            convert_html: 是否转换 HTML 为 Markdown

        Returns:
            合并后的 Markdown 内容
        """
        sections = []

        # 添加分类标题
        sections.append(f"# {category_name}\n\n")
        sections.append(f"*共 {len(chapters)} 篇文章*\n\n")
        sections.append("---\n\n")

        # 添加目录
        sections.append("## 目录\n\n")
        for idx, chapter in enumerate(chapters, 1):
            sections.append(f"{idx}. [{chapter.title}](#{self._make_anchor(chapter.title)})\n")
        sections.append("\n---\n\n")

        # 添加每篇文章内容
        for idx, chapter in enumerate(chapters, 1):
            sections.append(f"## {chapter.title}\n\n")

            if chapter.content:
                content = chapter.content
                if convert_html and self._is_html(content):
                    content = self._converter.convert(content)
                sections.append(content)
            else:
                sections.append("*（本章暂无文字内容）*\n")

            sections.append("\n\n---\n\n")

        return "".join(sections)

    def _merge_by_chunks(
        self,
        course_detail: CourseDetail,
        course_dir: Path,
        chunk_size: int = 10
    ) -> List[Path]:
        """按块合并文章（当没有分类信息时）

        Args:
            course_detail: 课程详情
            course_dir: 课程目录
            chunk_size: 每块的文章数量

        Returns:
            合并后的文件路径列表
        """
        chapters = course_detail.chapters
        merged_files = []

        # 计算需要分成多少块
        total = len(chapters)
        num_chunks = (total + chunk_size - 1) // chunk_size

        logger.info(f"课程共 {total} 章，分成 {num_chunks} 个文件")

        for i in range(num_chunks):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, total)
            chunk_chapters = chapters[start:end]

            # 文件名
            if num_chunks == 1:
                filename = f"000_{self._sanitize_name(course_detail.course.title)}.md"
                category_name = course_detail.course.title
            else:
                filename = f"{i + 1:02d}_{self._sanitize_name(course_detail.course.title)}_{start + 1}-{end}.md"
                category_name = f"第{i + 1}部分 ({start + 1}-{end}章)"

            file_path = course_dir / filename

            # 合并章节
            content = self._merge_chapters(chunk_chapters, category_name)
            file_path.write_text(content, encoding='utf-8')

            logger.info(f"已合并：{filename}")
            merged_files.append(file_path)

        return merged_files

    def _is_html(self, content: str) -> bool:
        """检查内容是否是 HTML"""
        return '<' in content and '>' in content

    def _make_anchor(self, title: str) -> str:
        """从标题生成 Markdown 锚点"""
        # 移除特殊字符，保留中文、英文、数字
        import re
        anchor = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '-', title)
        anchor = re.sub(r'-+', '-', anchor)  # 多个连字符变成一个
        return anchor.strip('-').lower()

    def _sanitize_name(self, name: str) -> str:
        """清理文件名中的非法字符"""
        import re
        # 移除不允许的字符
        result = re.sub(r'[<>:"/\\|？*]', '_', name)
        # 移除前后空格
        return result.strip()


class CourseDownloaderWithMerge:
    """带合并功能的课程下载器"""

    def __init__(self, client, output_dir: Path, max_workers: int = 5):
        """初始化下载器

        Args:
            client: DedaoClient 实例
            output_dir: 输出目录
            max_workers: 最大并发数
        """
        from .dedao.downloader import CourseDownloader
        self._downloader = CourseDownloader(client, max_workers, output_dir)
        self._merger = ArticleMerger()
        self._output_dir = output_dir

    def download_and_merge(
        self,
        course_id: str,
        include_audio: bool = False,
        merge: bool = True
    ) -> Tuple[List[Path], List[Path]]:
        """下载课程并合并文章

        Args:
            course_id: 课程 ID
            include_audio: 是否下载音频
            merge: 是否合并文章

        Returns:
            (合并后的 Markdown 文件列表，音频文件列表)
        """
        # 先下载所有章节
        logger.info(f"开始下载课程：{course_id}")
        results = self._downloader.download_course(course_id, include_audio=include_audio)

        # 收集下载成功的章节
        successful_chapters = []
        audio_files = []

        for result in results:
            if result.success:
                if result.chapter:
                    successful_chapters.append(result.chapter)
                if result.audio_path:
                    audio_files.append(result.audio_path)

        if not successful_chapters:
            logger.warning("没有成功下载任何章节")
            return [], []

        logger.info(f"成功下载 {len(successful_chapters)} 个章节")

        if not merge:
            # 不合并，返回单个文件
            md_files = [Path(r.local_path) for r in results if r.success and r.local_path]
            return md_files, audio_files

        # 合并文章 - 简化处理，直接使用输出目录
        merged_files = self._merger.merge_by_category(
            CourseDetail(
                course=type('obj', (object,), {'title': '未命名课程'})(),
                chapters=successful_chapters
            ),
            self._output_dir
        )

        return merged_files, audio_files
