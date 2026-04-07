"""EPUB 生成器模块

将内容转换为 EPUB 电子书格式。
"""

import logging
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EpubChapter:
    """EPUB 章节内容"""
    title: str
    content: str  # HTML 内容
    order: int = 0
    file_name: str = ""


class EPUBGenerator:
    """EPUB 电子书生成器

    功能：
    - 创建 EPUB 文件
    - 支持封面图片
    - 支持目录生成
    - 支持章节组织
    """

    def __init__(
        self,
        title: str,
        author: str = "",
        description: str = "",
        cover_path: Optional[str] = None,
        language: str = "zh-CN",
    ):
        """初始化 EPUB 生成器

        Args:
            title: 书名
            author: 作者
            description: 描述
            cover_path: 封面图片路径
            language: 语言
        """
        self.title = title
        self.author = author
        self.description = description
        self.cover_path = cover_path
        self.language = language

        self.chapters: List[EpubChapter] = []
        self._chapter_counter = 0

    def add_chapter(
        self,
        title: str,
        content: str,
        order: Optional[int] = None,
    ) -> None:
        """添加章节

        Args:
            title: 章节标题
            content: 章节内容（HTML）
            order: 顺序（可选）
        """
        if order is None:
            order = self._chapter_counter

        self._chapter_counter += 1

        chapter = EpubChapter(
            title=title,
            content=content,
            order=order,
            file_name=f"chapter_{order:04d}.xhtml",
        )
        self.chapters.append(chapter)

    def generate(self, output_path: Path) -> Path:
        """生成 EPUB 文件

        Args:
            output_path: 输出路径

        Returns:
            生成的文件路径
        """
        try:
            from ebooklib import epub

            book = epub.EpubBook()

            # 设置元数据
            book.set_identifier(str(uuid.uuid4()))
            book.set_title(self.title)
            book.set_language(self.language)

            if self.author:
                book.add_author(self.author)

            if self.description:
                book.add_metadata("DC", "description", self.description)

            # 添加封面
            if self.cover_path:
                try:
                    cover_path = Path(self.cover_path)
                    if cover_path.exists():
                        with open(cover_path, "rb") as f:
                            book.set_cover("cover.jpg", f.read())
                        logger.debug(f"已添加封面：{self.cover_path}")
                    else:
                        # 尝试作为 URL 下载
                        import requests
                        response = requests.get(self.cover_path, timeout=30)
                        if response.status_code == 200:
                            book.set_cover("cover.jpg", response.content)
                            logger.debug("已下载并添加封面")
                except Exception as e:
                    logger.warning(f"添加封面失败：{e}")

            # 按顺序排序章节
            sorted_chapters = sorted(self.chapters, key=lambda x: x.order)

            # 创建章节
            epub_chapters = []
            toc = []
            for chapter in sorted_chapters:
                epub_chapter = epub.EpubHtml(
                    title=chapter.title,
                    file_name=chapter.file_name,
                    lang=self.language,
                )

                # 设置内容
                epub_chapter.content = f"""
                <html>
                <head><title>{chapter.title}</title></head>
                <body>
                    <h1>{chapter.title}</h1>
                    <div class="content">
                        {chapter.content}
                    </div>
                </body>
                </html>
                """

                book.add_item(epub_chapter)
                epub_chapters.append(epub_chapter)
                toc.append(epub_chapter)

            # 设置目录
            book.toc = tuple(toc)

            # 添加导航
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # 设置样式
            style = """
            body { font-family: serif; line-height: 1.6; }
            h1 { text-align: center; margin-top: 1em; }
            .content { margin: 1em; }
            """
            nav_css = epub.EpubItem(
                uid="style_nav",
                file_name="style/nav.css",
                media_type="text/css",
                content=style,
            )
            book.add_item(nav_css)

            # 设置文件顺序
            book.spine = ["nav"] + epub_chapters

            # 写入文件
            epub.write_epub(str(output_path), book, {})

            logger.info(f"EPUB 已生成：{output_path}")
            return output_path

        except ImportError:
            logger.error(
                "未安装 ebooklib，请运行: pip install ebooklib"
            )
            raise ImportError("需要安装 ebooklib 库")

        except Exception as e:
            logger.error(f"生成 EPUB 失败：{e}")
            raise

    def generate_from_markdown(
        self,
        markdown_content: str,
        output_path: Path,
    ) -> Path:
        """从 Markdown 内容生成 EPUB

        Args:
            markdown_content: Markdown 内容
            output_path: 输出路径

        Returns:
            生成的文件路径
        """
        try:
            import markdown

            # 转换为 HTML
            html_content = markdown.markdown(markdown_content)

            # 分割章节（基于 h1/h2 标题）
            self._split_html_to_chapters(html_content)

            return self.generate(output_path)

        except ImportError:
            logger.error(
                "未安装 markdown，请运行: pip install markdown"
            )
            raise ImportError("需要安装 markdown 库")

    def _split_html_to_chapters(self, html_content: str) -> None:
        """将 HTML 内容按标题分割为章节

        Args:
            html_content: HTML 内容
        """
        import re

        # 按 h2 标题分割
        pattern = r"<h2>(.*?)</h2>"
        parts = re.split(pattern, html_content)

        # 第一个部分作为简介
        if parts and parts[0].strip():
            self.add_chapter("简介", parts[0].strip(), order=0)

        # 其余部分作为章节
        order = 1
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                title = parts[i]
                content = parts[i + 1]
                if title.strip() and content.strip():
                    self.add_chapter(title.strip(), content.strip(), order=order)
                    order += 1
