"""电子书下载器。

直接使用项目内 API 下载电子书正文，不依赖 dedao-dl 的登录态。
"""

import base64
from collections import defaultdict
from html import escape, unescape
import mimetypes
import logging
import re
import xml.etree.ElementTree as ET
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests

from converter.ebook_html_to_md import EbookHtmlToMarkdownConverter
from converter.svg_to_md import SvgToMarkdownRenderer

from .client import EbookClient
from ..models import EbookChapter, EbookDetail

logger = logging.getLogger(__name__)


@dataclass
class EbookDownloadProgress:
    """下载进度"""
    stage: str  # "checking", "syncing", "downloading", "converting", "completed", "failed"
    message: str = ""
    progress: float = 0.0  # 0-100


@dataclass
class EbookDownloadResult:
    """下载结果"""
    success: bool
    ebook: Optional[EbookDetail] = None
    output_files: List[Path] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.output_files is None:
            self.output_files = []


@dataclass
class SvgTextFragment:
    text: str
    x: float
    y: float
    top: float
    width: float
    height: float
    font_size: float
    bold: bool = False


@dataclass
class SvgTextLine:
    text: str
    x: float
    y: float
    right: float
    font_size: float
    max_font_size: float
    bold: bool
    centered: bool


@dataclass
class SemanticBlock:
    kind: str
    y: float
    text: str = ""
    level: int = 0
    src: str = ""
    alt: str = ""
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class SvgImageItem:
    href: str
    x: float
    y: float
    width: float
    height: float


class EbookDownloader:
    """电子书下载器

    使用项目内电子书 API 下载内容，支持 Markdown、HTML 和 EPUB。
    """

    def __init__(
        self,
        client: Optional[EbookClient] = None,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[EbookDownloadProgress], None]] = None
    ):
        """初始化下载器

        Args:
            client: EbookClient 实例
            output_dir: 输出目录，默认为 ./downloads/ebooks
            progress_callback: 进度回调函数
        """
        self.client = client or EbookClient()
        self.output_dir = output_dir or Path("./downloads/ebooks")
        self.progress_callback = progress_callback
        self._svg_block_cache: Dict[str, List[SemanticBlock]] = {}
        self._asset_cache: Dict[str, str] = {}
        self._inline_assets: Dict[str, Dict[str, str]] = {}
        self._converter = EbookHtmlToMarkdownConverter(keep_images=True, image_dir="images")
        self._md_renderer = SvgToMarkdownRenderer()
        self._http = requests.Session()

    def _notify_progress(self, stage: str, message: str = "", progress: float = 0.0):
        """通知进度更新"""
        if self.progress_callback:
            progress_obj = EbookDownloadProgress(
                stage=stage,
                message=message,
                progress=progress
            )
            self.progress_callback(progress_obj)
        else:
            # 默认日志输出
            logger.info(f"[{stage}] {message} ({int(progress)}%)")

    def check_prerequisites(self) -> tuple[bool, str]:
        """检查下载前提条件

        Returns:
            (是否满足条件, 错误消息)
        """
        if not self.client.cookie:
            return False, "未检测到得到 Cookie，请先登录: dedao-nb login --cookie <cookie>"

        try:
            self.client.check_auth()
        except Exception as exc:
            return False, f"登录信息无效，请重新登录: {exc}"

        return True, ""

    def download(
        self,
        ebook_id: str,
        output_format: str = "html",
        filename: Optional[str] = None
    ) -> EbookDownloadResult:
        """下载电子书。

        Args:
            ebook_id: 电子书 ID、enid 或标题
            output_format: 输出格式 ("html", "md", "epub")
            filename: 自定义文件名（不含扩展名）

        Returns:
            下载结果
        """
        self._notify_progress("checking", "检查下载环境...", 0)

        # 检查前提条件
        ok, error = self.check_prerequisites()
        if not ok:
            return EbookDownloadResult(success=False, error=error)

        # 获取电子书信息
        self._notify_progress("checking", "获取电子书信息...", 10)
        try:
            ebook = self.client.resolve_ebook(ebook_id)
            if not ebook.catalog:
                ebook = self.client.get_ebook_detail(ebook.enid)
            elif not ebook.extra.get("id"):
                ebook = self.client.get_ebook_detail(ebook.enid)
        except Exception as e:
            return EbookDownloadResult(success=False, error=f"获取电子书信息失败: {e}")

        # 创建输出目录
        safe_title = self._sanitize_filename(ebook.title)
        book_dir = self.output_dir / safe_title
        book_dir.mkdir(parents=True, exist_ok=True)
        self._svg_block_cache.clear()
        self._asset_cache.clear()
        self._inline_assets.clear()

        # 直接使用 API 下载
        self._notify_progress("downloading", f"正在下载《{ebook.title}》...", 30)
        try:
            token = self.client.get_ebook_read_token(ebook.enid)
            ebook_info = self.client.get_ebook_info(token)
            chapters = self._download_chapters(ebook, ebook_info.orders, token)
        except Exception as e:
            return EbookDownloadResult(
                success=False,
                ebook=ebook,
                error=f"下载失败: {e}"
            )

        output_files: List[Path] = []
        self._notify_progress("converting", "生成输出文件...", 80)

        if output_format == "html":
            output_files.extend(self._write_html(book_dir, filename or safe_title, ebook, chapters))
        elif output_format == "epub":
            epub_file = self._write_epub(book_dir, filename or safe_title, ebook, chapters)
            if epub_file:
                output_files.append(epub_file)
        else:
            output_files.extend(self._write_markdown(book_dir, filename or safe_title, ebook, chapters))

        self._notify_progress("completed", f"下载完成: {book_dir}", 100)

        return EbookDownloadResult(
            success=True,
            ebook=ebook,
            output_files=output_files
        )

    def download_by_title(
        self,
        title: str,
        output_format: str = "html"
    ) -> EbookDownloadResult:
        """按标题下载电子书。"""
        return self.download(title, output_format)

    def _download_chapters(
        self,
        ebook: EbookDetail,
        orders: List[dict],
        token: str,
    ) -> List[EbookChapter]:
        chapters: List[EbookChapter] = []
        current_chapter: Optional[EbookChapter] = None

        total = max(len(orders), 1)
        for index, order in enumerate(orders, 1):
            chapter_id = str(order.get("chapterId") or order.get("chapter_id") or "")
            if not chapter_id:
                continue

            title = self._get_catalog_title(chapter_id, ebook)
            if current_chapter is None or current_chapter.title != title:
                current_chapter = EbookChapter(
                    chapter_id=chapter_id,
                    title=title,
                    order=len(chapters) + 1,
                )
                chapters.append(current_chapter)

            progress = 30 + (index / total) * 45
            self._notify_progress(
                "downloading",
                f"下载章节 {index}/{total}: {title}",
                progress,
            )
            current_chapter.svg_contents.extend(
                self.client.get_all_chapter_pages(ebook.enid, chapter_id, token)
            )

        return chapters

    def _get_catalog_title(self, chapter_id: str, ebook: EbookDetail) -> str:
        for catalog in ebook.catalog:
            href = catalog.extra.get("href") or catalog.chapter_id
            href_base = str(href).split("#", 1)[0]
            if href_base.startswith(chapter_id) or chapter_id.startswith(href_base):
                return catalog.title or chapter_id

        fallback_titles = {
            "cover.xhtml": "封面",
            "preface1.xhtml": "卷首语",
            "author.xhtml": "作者介绍",
        }
        if chapter_id in fallback_titles:
            return fallback_titles[chapter_id]

        return chapter_id

    @staticmethod
    def _local_name(tag: str) -> str:
        return str(tag).rsplit("}", 1)[-1]

    @staticmethod
    def _parse_float(value: Optional[str], default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(re.sub(r"[^0-9.+-]", "", str(value)))
        except ValueError:
            return default

    @staticmethod
    def _parse_style(style: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for item in style.split(";"):
            if ":" not in item:
                continue
            key, value = item.split(":", 1)
            result[key.strip()] = value.strip()
        return result

    @staticmethod
    def _sha1(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def _extract_text_fragments(self, root: ET.Element) -> List[SvgTextFragment]:
        fragments: List[SvgTextFragment] = []
        for elem in root.iter():
            if self._local_name(elem.tag) != "text":
                continue
            text = unescape("".join(elem.itertext())).replace("\xa0", " ").strip()
            if not text:
                continue

            style = self._parse_style(elem.attrib.get("style", ""))
            font_size = self._parse_float(style.get("font-size"), 0.0)
            height = self._parse_float(elem.attrib.get("height"), 0.0)
            if font_size <= 0:
                font_size = height or 16.0

            weight = (style.get("font-weight") or elem.attrib.get("font-weight") or "").lower()
            bold = "bold" in weight
            if not bold and weight.isdigit():
                bold = int(weight) >= 600

            fragments.append(
                SvgTextFragment(
                    text=text,
                    x=self._parse_float(elem.attrib.get("x")),
                    y=self._parse_float(elem.attrib.get("y"), self._parse_float(elem.attrib.get("top"))),
                    top=self._parse_float(elem.attrib.get("top"), self._parse_float(elem.attrib.get("y"))),
                    width=self._parse_float(elem.attrib.get("width")),
                    height=height,
                    font_size=font_size,
                    bold=bold,
                )
            )
        return fragments

    def _needs_space(self, previous: SvgTextFragment, current: SvgTextFragment) -> bool:
        gap = current.x - (previous.x + previous.width)
        threshold = max(previous.font_size, current.font_size) * 1.6
        if gap < threshold:
            return False

        prev_char = previous.text[-1:]
        curr_char = current.text[:1]
        if prev_char and curr_char and prev_char.isascii() and curr_char.isascii():
            return True

        return gap >= threshold * 1.8

    def _group_text_fragments(self, fragments: List[SvgTextFragment], page_width: float) -> List[SvgTextLine]:
        rows: Dict[float, List[SvgTextFragment]] = defaultdict(list)
        for fragment in fragments:
            rows[round(fragment.top or fragment.y, 1)].append(fragment)

        lines: List[SvgTextLine] = []
        for row_y in sorted(rows):
            row = sorted(rows[row_y], key=lambda item: item.x)
            parts: List[str] = []
            previous: Optional[SvgTextFragment] = None
            for fragment in row:
                if previous and self._needs_space(previous, fragment):
                    parts.append(" ")
                parts.append(fragment.text)
                previous = fragment

            text = "".join(parts).strip()
            if not text:
                continue

            x = min(fragment.x for fragment in row)
            right = max(fragment.x + max(fragment.width, fragment.font_size) for fragment in row)
            total_chars = sum(max(len(fragment.text), 1) for fragment in row)
            weighted_font = sum(fragment.font_size * max(len(fragment.text), 1) for fragment in row) / max(total_chars, 1)
            max_font = max(fragment.font_size for fragment in row)
            bold_count = sum(1 for fragment in row if fragment.bold)
            centered = abs(((x + right) / 2) - (page_width / 2)) <= max(page_width * 0.16, 5000)

            lines.append(
                SvgTextLine(
                    text=text,
                    x=x,
                    y=row_y,
                    right=right,
                    font_size=weighted_font,
                    max_font_size=max_font,
                    bold=bold_count >= max(1, len(row) // 2),
                    centered=centered,
                )
            )

        return lines

    def _extract_images(self, root: ET.Element) -> List[SvgImageItem]:
        images: List[SvgImageItem] = []
        for elem in root.iter():
            if self._local_name(elem.tag) != "image":
                continue
            href = (
                elem.attrib.get("href")
                or elem.attrib.get("{http://www.w3.org/1999/xlink}href")
                or elem.attrib.get("src")
            )
            if not href:
                continue
            images.append(
                SvgImageItem(
                    href=href,
                    x=self._parse_float(elem.attrib.get("x")),
                    y=self._parse_float(elem.attrib.get("y")),
                    width=self._parse_float(elem.attrib.get("width")),
                    height=self._parse_float(elem.attrib.get("height")),
                )
            )
        return images

    def _extract_shape_stats(self, root: ET.Element, page_width: float) -> Dict[str, int]:
        stats = {"horizontal": 0, "vertical": 0, "paths": 0, "total": 0}

        for elem in root.iter():
            tag = self._local_name(elem.tag)
            if tag not in {"line", "rect", "path"}:
                continue

            if tag == "path":
                stats["paths"] += 1
                stats["total"] += 1
                continue

            if tag == "line":
                x1 = self._parse_float(elem.attrib.get("x1"))
                y1 = self._parse_float(elem.attrib.get("y1"))
                x2 = self._parse_float(elem.attrib.get("x2"))
                y2 = self._parse_float(elem.attrib.get("y2"))
                width = abs(x2 - x1)
                height = abs(y2 - y1)
            else:
                width = abs(self._parse_float(elem.attrib.get("width")))
                height = abs(self._parse_float(elem.attrib.get("height")))

            if width >= page_width * 0.25 and height <= 3:
                stats["horizontal"] += 1
                stats["total"] += 1
            elif height >= 60 and width <= 3:
                stats["vertical"] += 1
                stats["total"] += 1

        return stats

    def _is_probable_table_page(self, shape_stats: Dict[str, int], lines: List[SvgTextLine]) -> bool:
        if self._is_prose_heavy_page(lines):
            return False
        return (
            (shape_stats["horizontal"] >= 4 and shape_stats["vertical"] >= 2)
            or (shape_stats["horizontal"] >= 6 and shape_stats["vertical"] >= 1 and len(lines) >= 4)
            or (shape_stats["horizontal"] >= 3 and shape_stats["vertical"] >= 3 and len(lines) >= 4)
        )

    def _is_probable_page_number(self, line: SvgTextLine, page_height: float) -> bool:
        text = line.text.strip()
        if line.y < page_height * 0.84:
            return False
        return bool(re.fullmatch(r"[—\-–]?\s*\d+\s*[—\-–]?", text))

    def _heading_level(self, line: SvgTextLine) -> int:
        text = line.text.strip()
        if not text:
            return 0

        # 严格的中文章节模式 → h2
        if re.match(r"^第[〇零一二三四五六七八九十百千万\d]+[章节部篇卷]", text):
            return 2

        # 严格的 "Part X" 模式 → h2
        if re.match(r"^(?:Part|PART)\s+[IVXLC\d]+", text):
            return 2

        # 字号 + 中心 + 短文本 → h2（书名级/大标题）
        if line.max_font_size >= 26 and line.centered and len(text) <= 36:
            return 2

        # 字号 ≥ 20, 居中或加粗, 短文本 → h3（章节标题）
        if line.max_font_size >= 20 and (line.centered or line.bold) and len(text) <= 42:
            return 3

        # 字号 ≥ 17, 加粗, 短文本 → h4（小节标题）
        if line.max_font_size >= 17 and line.bold and len(text) <= 48:
            return 4

        # 中文数字小节模式: "一、xxx" "（一）xxx"
        if re.match(r"^[（(]?[一二三四五六七八九十]+[）)]?[、.．]\s*\S", text) and len(text) <= 40:
            return 4

        return 0

    @staticmethod
    def _parse_list_item(text: str) -> Optional[Dict[str, str]]:
        ordered_patterns = [
            r"^\s*(\d+)[\.\)、]\s*(.+)$",
            r"^\s*[(（](\d+)[)）]\s*(.+)$",
            r"^\s*([一二三四五六七八九十]+)、\s*(.+)$",
            r"^\s*([A-Za-z])[\.\)]\s*(.+)$",
        ]
        for pattern in ordered_patterns:
            match = re.match(pattern, text)
            if match:
                return {"ordered": "true", "text": match.group(2).strip()}

        bullet_match = re.match(r"^\s*([\-*•●▪◦])\s*(.+)$", text)
        if bullet_match:
            return {"ordered": "false", "text": bullet_match.group(2).strip()}
        return None

    @staticmethod
    def _merge_paragraph_lines(lines: List[SvgTextLine]) -> str:
        merged = ""
        for line in lines:
            text = line.text.strip()
            if not text:
                continue
            if not merged:
                merged = text
                continue
            if text.startswith("@@INLINE_IMG_"):
                merged += text
                continue
            if merged[-1:].isascii() and text[:1].isascii():
                merged += " " + text
            else:
                merged += text
        return merged.strip()

    def _lines_to_blocks(self, lines: List[SvgTextLine], page_height: float) -> List[SemanticBlock]:
        blocks: List[SemanticBlock] = []
        paragraph_lines: List[SvgTextLine] = []
        previous_y: Optional[float] = None

        def flush_paragraph():
            nonlocal paragraph_lines
            if not paragraph_lines:
                return
            text = self._merge_paragraph_lines(paragraph_lines)
            if text:
                blocks.append(
                    SemanticBlock(
                        kind="paragraph",
                        y=paragraph_lines[0].y,
                        text=text,
                    )
                )
            paragraph_lines = []

        for line in lines:
            text = re.sub(r"\s+", " ", line.text).strip()
            if not text or self._is_probable_page_number(line, page_height):
                continue

            gap = line.y - previous_y if previous_y is not None else 0.0
            if gap > max(line.max_font_size * 1.9, 42):
                flush_paragraph()

            level = self._heading_level(line)
            list_meta = self._parse_list_item(text)
            if level:
                flush_paragraph()
                blocks.append(SemanticBlock(kind="heading", y=line.y, text=text, level=level))
            elif list_meta:
                flush_paragraph()
                blocks.append(
                    SemanticBlock(
                        kind="list_item",
                        y=line.y,
                        text=list_meta["text"],
                        extra={"ordered": list_meta["ordered"]},
                    )
                )
            else:
                paragraph_lines.append(
                    SvgTextLine(
                        text=text,
                        x=line.x,
                        y=line.y,
                        right=line.right,
                        font_size=line.font_size,
                        max_font_size=line.max_font_size,
                        bold=line.bold,
                        centered=line.centered,
                    )
                )
            previous_y = line.y

        flush_paragraph()
        return blocks

    @staticmethod
    def _is_small_inline_image(image: SvgImageItem, page_width: float, page_height: float) -> bool:
        return (
            image.width > 0
            and image.height > 0
            and image.width <= page_width * 0.18
            and image.height <= page_height * 0.08
        )

    @staticmethod
    def _is_decorative_repeated_icon(image: SvgImageItem, repeated_count: int) -> bool:
        if repeated_count < 2 or image.width <= 0 or image.height <= 0:
            return False
        ratio = image.width / max(image.height, 1.0)
        return 0.75 <= ratio <= 1.35

    @staticmethod
    def _is_tiny_square_raster_icon(image: SvgImageItem) -> bool:
        suffix = Path(str(image.href).split("?", 1)[0]).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            return False
        if image.width <= 0 or image.height <= 0 or max(image.width, image.height) > 4000:
            return False
        ratio = image.width / max(image.height, 1.0)
        return 0.75 <= ratio <= 1.35

    @staticmethod
    def _is_formula_like_inline_image(image: SvgImageItem) -> bool:
        suffix = Path(str(image.href).split("?", 1)[0]).suffix.lower()
        if suffix == ".svg":
            return True

        ratio = image.width / max(image.height, 1.0)
        return ratio >= 1.6 or ratio <= 0.6

    def _find_inline_image_row(self, image: SvgImageItem, rows: List[float]) -> Optional[float]:
        if not rows:
            return None
        nearest = min(rows, key=lambda row: abs(row - image.y))
        tolerance = min(max(image.height * 0.35, 3.0), 16.0)
        if abs(nearest - image.y) <= tolerance:
            return nearest
        return None

    def _register_inline_asset(self, src: str, alt: str) -> str:
        token = f"@@INLINE_IMG_{len(self._inline_assets) + 1}@@"
        self._inline_assets[token] = {"src": src, "alt": alt}
        return token

    def _render_text_with_inline_assets(self, book_dir: Path, text: str, embed_assets: bool = False) -> str:
        rendered = escape(text)
        for token, info in self._inline_assets.items():
            if token not in rendered:
                continue
            src = info["src"]
            if embed_assets:
                src = self._asset_to_data_uri(book_dir, src)
            alt_attr = f' alt="{escape(info["alt"])}"' if info["alt"] else ' alt=""'
            img_html = f'<img class="inline-image" src="{escape(src)}"{alt_attr} />'
            rendered = rendered.replace(token, img_html)
        return rendered

    @staticmethod
    def _normalize_semantic_text(text: str) -> str:
        text = re.sub(r"@@INLINE_IMG_\d+@@", "", text)
        text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
        return text.strip()

    @staticmethod
    def _looks_like_raw_chapter_id(text: str) -> bool:
        stripped = str(text).strip()
        return bool(re.fullmatch(r"[A-Za-z0-9_\-]+\.xhtml", stripped))

    def _chapter_asset_prefix(self, chapter_title: str) -> str:
        title = str(chapter_title).strip()
        if not title or self._looks_like_raw_chapter_id(title):
            return ""
        return title

    def _build_asset_alt(
        self,
        chapter_title: str,
        kind: str,
        page_index: int,
        item_index: Optional[int] = None,
    ) -> str:
        prefix = self._chapter_asset_prefix(chapter_title)
        if kind == "inline":
            suffix = f"inline-{page_index}-{item_index}"
        elif kind == "table":
            suffix = f"table-{page_index}"
        else:
            suffix = f"image-{page_index}-{item_index}"
        return f"{prefix}-{suffix}" if prefix else ""

    @staticmethod
    def _is_prose_like_line(text: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        if not compact:
            return False
        if len(compact) >= 24:
            return True
        return len(compact) >= 16 and bool(re.search(r"[，。；：！？,.!?;:]", compact))

    def _is_prose_heavy_page(self, lines: List[SvgTextLine]) -> bool:
        if len(lines) < 6:
            return False
        return sum(1 for line in lines if self._is_prose_like_line(line.text)) >= 6

    def _looks_like_chapter_opener(self, chapter_title: str, lines: List[SvgTextLine]) -> bool:
        if not lines or len(lines) > 4:
            return False

        normalized_title = self._normalize_semantic_text(chapter_title)
        if not normalized_title:
            return False

        combined = self._normalize_semantic_text(" ".join(line.text for line in lines))
        if combined != normalized_title:
            return False

        return any(self._heading_level(line) for line in lines)

    def _is_decorative_chapter_opener_image(
        self,
        chapter_title: str,
        image: SvgImageItem,
        lines: List[SvgTextLine],
        page_width: float,
        page_height: float,
        kept_image_count: int,
    ) -> bool:
        if kept_image_count != 1 or not self._looks_like_chapter_opener(chapter_title, lines):
            return False
        if image.width < page_width * 0.55 or image.height < page_height * 0.28:
            return False
        if image.y < page_height * 0.12:
            return False
        return True

    def _trim_leading_title_blocks(self, chapter_title: str, blocks: List[SemanticBlock]) -> List[SemanticBlock]:
        normalized_title = self._normalize_semantic_text(chapter_title)
        if not normalized_title:
            return blocks

        leading: List[SemanticBlock] = []
        for block in blocks[:4]:
            if block.kind not in {"heading", "paragraph"}:
                break
            if not block.text.strip():
                break
            leading.append(block)
            combined = self._normalize_semantic_text(" ".join(item.text for item in leading))
            if combined == normalized_title:
                return blocks[len(leading):]
            if len(combined) > len(normalized_title) + 8:
                break

        return blocks

    def _drop_duplicate_heading_blocks(self, chapter_title: str, blocks: List[SemanticBlock]) -> List[SemanticBlock]:
        normalized_title = self._normalize_semantic_text(chapter_title)
        if not normalized_title:
            return blocks

        filtered: List[SemanticBlock] = []
        for block in blocks:
            if block.kind == "heading" and self._normalize_semantic_text(block.text) == normalized_title:
                continue
            filtered.append(block)
        return filtered

    def _inline_nested_svg_images(self, svg_text: str) -> str:
        try:
            root = ET.fromstring(svg_text)
        except ET.ParseError:
            return svg_text

        changed = False
        for elem in root.iter():
            if self._local_name(elem.tag) != "image":
                continue
            href = (
                elem.attrib.get("href")
                or elem.attrib.get("{http://www.w3.org/1999/xlink}href")
                or elem.attrib.get("src")
            )
            if not href or href.startswith("data:"):
                continue

            try:
                response = self._http.get(href, timeout=30)
                response.raise_for_status()
            except Exception:
                continue

            mime_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(href.split("?", 1)[0])
            mime_type = mime_type or "application/octet-stream"
            data_uri = f"data:{mime_type};base64,{base64.b64encode(response.content).decode('ascii')}"
            elem.set("href", data_uri)
            elem.set("{http://www.w3.org/1999/xlink}href", data_uri)
            changed = True

        if not changed:
            return svg_text

        return ET.tostring(root, encoding="unicode")

    def _download_image_asset(self, url: str, images_dir: Path) -> str:
        if url in self._asset_cache:
            return self._asset_cache[url]

        suffix = Path(url.split("?", 1)[0]).suffix.lower() or ".jpg"
        if len(suffix) > 6:
            suffix = ".jpg"
        filename = f"img-{self._sha1(url)[:16]}{suffix}"
        target = images_dir / filename
        relative = f"images/{filename}"

        response = self._http.get(url, timeout=30)
        response.raise_for_status()
        if suffix == ".svg":
            processed = self._inline_nested_svg_images(response.text)
            if not target.exists() or target.read_text(encoding="utf-8") != processed:
                target.write_text(processed, encoding="utf-8")
        else:
            if not target.exists() or target.read_bytes() != response.content:
                target.write_bytes(response.content)

        self._asset_cache[url] = relative
        return relative

    def _write_svg_asset(self, svg: str, images_dir: Path, prefix: str) -> str:
        filename = f"{prefix}-{self._sha1(svg)[:16]}.svg"
        target = images_dir / filename
        processed = self._inline_nested_svg_images(svg)
        if not target.exists() or target.read_text(encoding="utf-8") != processed:
            target.write_text(processed, encoding="utf-8")
        return f"images/{filename}"

    def _asset_to_data_uri(self, book_dir: Path, src: str) -> str:
        if src.startswith("http"):
            return src

        asset_path = book_dir / src
        if not asset_path.exists():
            return src

        mime_type, _ = mimetypes.guess_type(asset_path.name)
        if asset_path.suffix.lower() == ".svg":
            mime_type = "image/svg+xml"
        mime_type = mime_type or "application/octet-stream"
        data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{data}"

    def _render_page_blocks(
        self,
        svg: str,
        images_dir: Path,
        chapter_title: str,
        page_index: int,
    ) -> List[SemanticBlock]:
        cache_key = self._sha1(svg)
        if cache_key in self._svg_block_cache:
            return self._svg_block_cache[cache_key]

        try:
            root = ET.fromstring(svg)
        except ET.ParseError:
            fallback = [SemanticBlock(kind="paragraph", y=0.0, text=re.sub(r"<[^>]+>", "", svg).strip())]
            self._svg_block_cache[cache_key] = fallback
            return fallback

        page_width = self._parse_float(root.attrib.get("width"), 60000.0)
        page_height = self._parse_float(root.attrib.get("height"), 200000.0)
        images = self._extract_images(root)
        fragments = self._extract_text_fragments(root)
        shape_stats = self._extract_shape_stats(root, page_width)
        repeated_images: Dict[str, int] = defaultdict(int)
        for image in images:
            repeated_images[image.href] += 1

        row_keys = sorted({round(fragment.top or fragment.y, 1) for fragment in fragments})
        kept_images: List[tuple[int, SvgImageItem, str]] = []
        for image_index, image in enumerate(sorted(images, key=lambda item: item.y), 1):
            if self._is_tiny_square_raster_icon(image):
                continue
            if self._is_decorative_repeated_icon(image, repeated_images[image.href]):
                continue

            src = self._download_image_asset(str(image.href), images_dir)
            if self._is_small_inline_image(image, page_width, page_height) and self._is_formula_like_inline_image(image):
                target_row = self._find_inline_image_row(image, row_keys)
                if target_row is not None:
                    token = self._register_inline_asset(
                        src,
                        self._build_asset_alt(chapter_title, "inline", page_index, image_index),
                    )
                    fragments.append(
                        SvgTextFragment(
                            text=token,
                            x=image.x,
                            y=image.y,
                            top=target_row,
                            width=max(image.width, 1.0),
                            height=max(image.height, 1.0),
                            font_size=max(image.height, 16.0),
                        )
                    )
                    continue

            kept_images.append((image_index, image, src))

        lines = self._group_text_fragments(fragments, page_width)
        block_images = [
            (image_index, image, src)
            for image_index, image, src in kept_images
            if not self._is_decorative_chapter_opener_image(
                chapter_title,
                image,
                lines,
                page_width,
                page_height,
                len(kept_images),
            )
        ]

        if self._is_probable_table_page(shape_stats, lines):
            blocks = []
            for line in lines[:3]:
                level = self._heading_level(line)
                if level:
                    blocks.append(SemanticBlock(kind="heading", y=line.y, text=line.text.strip(), level=level))
            blocks.append(
                SemanticBlock(
                    kind="table_image",
                    y=lines[0].y if lines else 0.0,
                    src=self._write_svg_asset(svg, images_dir, "table"),
                    alt=self._build_asset_alt(chapter_title, "table", page_index),
                )
            )
            self._svg_block_cache[cache_key] = blocks
            return blocks

        blocks = self._lines_to_blocks(lines, page_height)
        for image_index, image, src in block_images:
            blocks.append(
                SemanticBlock(
                    kind="image",
                    y=float(image.y),
                    src=src,
                    alt=self._build_asset_alt(chapter_title, "image", page_index, image_index),
                )
            )

        blocks = sorted(blocks, key=lambda item: (item.y, 0 if item.kind == "heading" else 1))
        self._svg_block_cache[cache_key] = blocks
        return blocks

    def _render_chapter_html(self, book_dir: Path, chapter: EbookChapter, embed_assets: bool = False) -> str:
        images_dir = book_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        blocks: List[SemanticBlock] = []
        for page_index, svg in enumerate(chapter.svg_contents, 1):
            blocks.extend(self._render_page_blocks(svg, images_dir, chapter.title, page_index))
        blocks = self._trim_leading_title_blocks(chapter.title, blocks)
        blocks = self._drop_duplicate_heading_blocks(chapter.title, blocks)

        parts = ["<section>"]
        if not self._looks_like_raw_chapter_id(chapter.title):
            parts.append(f"<h2>{escape(chapter.title)}</h2>")
        list_items: List[SemanticBlock] = []
        list_kind = "ul"

        def flush_list():
            nonlocal list_items
            if not list_items:
                return
            parts.append(f"<{list_kind}>")
            for item in list_items:
                parts.append(
                    f"<li>{self._render_text_with_inline_assets(book_dir, item.text, embed_assets=embed_assets)}</li>"
                )
            parts.append(f"</{list_kind}>")
            list_items = []

        for block in blocks:
            if block.kind == "list_item":
                current_kind = "ol" if block.extra.get("ordered") == "true" else "ul"
                if list_items and current_kind != list_kind:
                    flush_list()
                list_kind = current_kind
                list_items.append(block)
                continue

            flush_list()
            if block.kind == "heading":
                level = min(max(block.level, 3), 4)
                parts.append(
                    f"<h{level}>{self._render_text_with_inline_assets(book_dir, block.text, embed_assets=embed_assets)}</h{level}>"
                )
            elif block.kind == "paragraph":
                parts.append(f"<p>{self._render_text_with_inline_assets(book_dir, block.text, embed_assets=embed_assets)}</p>")
            elif block.kind in {"image", "table_image"}:
                src = block.src
                if embed_assets:
                    src = self._asset_to_data_uri(book_dir, src)
                alt_attr = escape(block.alt) if block.alt else ""
                figure = [f'<figure class="{block.kind}"><img src="{escape(src)}" alt="{alt_attr}" />']
                caption = "表格图片" if block.kind == "table_image" else block.alt
                if caption:
                    figure.append(f"<figcaption>{escape(caption)}</figcaption>")
                figure.append("</figure>")
                parts.append("".join(figure))

        flush_list()
        parts.append("</section>")
        chapter.html_content = "\n".join(parts)
        chapter.markdown_content = self._converter.convert(chapter.html_content)
        return chapter.html_content

    def _build_html_document(self, book_dir: Path, ebook: EbookDetail, chapters: List[EbookChapter], embed_assets: bool = False) -> str:
        parts = [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '  <meta charset="UTF-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f"  <title>{ebook.title}</title>",
            "  <style>",
            "    body { font-family: serif; max-width: 960px; margin: 0 auto; padding: 24px; }",
            "    .meta { color: #666; margin-bottom: 24px; }",
            "    .intro { background: #f5f5f5; padding: 16px; border-radius: 8px; }",
            "    section { margin-top: 32px; }",
            "    figure { margin: 20px 0; }",
            "    img { max-width: 100%; height: auto; display: block; }",
            "    p img.inline-image { display: inline-block; vertical-align: middle; max-height: 1.7em; width: auto; margin: 0 0.22em; }",
            "    figcaption { color: #666; font-size: 0.92rem; margin-top: 6px; }",
            "  </style>",
            "</head>",
            "<body>",
            f"  <h1>{escape(ebook.title)}</h1>",
            f'  <p class="meta">作者：{escape(ebook.author)}</p>',
        ]

        if ebook.book_intro:
            parts.extend(
                [
                    '  <div class="intro">',
                    f"    <p>{escape(ebook.book_intro)}</p>",
                    "  </div>",
                ]
            )

        for chapter in chapters:
            parts.append(self._render_chapter_html(book_dir, chapter, embed_assets=embed_assets))

        parts.extend(["</body>", "</html>"])
        return "\n".join(parts)

    def _render_chapter_markdown(self, book_dir: Path, chapter: EbookChapter) -> str:
        """直接将章节 SVG 渲染为 Markdown（跳过 HTML 中间层）。"""
        images_dir = book_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        blocks: List[SemanticBlock] = []
        for page_index, svg in enumerate(chapter.svg_contents, 1):
            blocks.extend(self._render_page_blocks(svg, images_dir, chapter.title, page_index))
        blocks = self._trim_leading_title_blocks(chapter.title, blocks)
        blocks = self._drop_duplicate_heading_blocks(chapter.title, blocks)

        # 使用 SvgToMarkdownRenderer 直接渲染
        self._md_renderer._inline_assets = self._inline_assets
        chapter_title = None if self._looks_like_raw_chapter_id(chapter.title) else chapter.title

        # 为章节添加一个 h2 标题块
        chapter_blocks = []
        if chapter_title:
            chapter_blocks.append(SemanticBlock(kind="heading", y=0, text=chapter_title, level=2))
        chapter_blocks.extend(blocks)

        md = self._md_renderer.render(chapter_blocks)
        chapter.markdown_content = md
        return md

    def _write_markdown(
        self,
        book_dir: Path,
        filename: str,
        ebook: EbookDetail,
        chapters: List[EbookChapter],
    ) -> List[Path]:
        # 直接 SVG→MD：每章独立渲染，最后合并
        all_blocks: List[SemanticBlock] = []
        images_dir = book_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        for chapter in chapters:
            # 添加章节标题
            if not self._looks_like_raw_chapter_id(chapter.title):
                all_blocks.append(SemanticBlock(kind="heading", y=0, text=chapter.title, level=2))
            for page_index, svg in enumerate(chapter.svg_contents, 1):
                page_blocks = self._render_page_blocks(svg, images_dir, chapter.title, page_index)
                page_blocks = self._trim_leading_title_blocks(chapter.title, page_blocks)
                page_blocks = self._drop_duplicate_heading_blocks(chapter.title, page_blocks)
                all_blocks.extend(page_blocks)

        self._md_renderer._inline_assets = self._inline_assets
        md = self._md_renderer.render(
            all_blocks,
            title=ebook.title,
            author=ebook.author,
            intro=ebook.book_intro,
        )

        output_path = book_dir / f"{filename}.md"
        output_path.write_text(md, encoding="utf-8")

        # 同时生成 HTML 版本用于 NotebookLM（保持原逻辑）
        notebooklm_html = book_dir / f"{filename}.notebooklm.html"
        notebooklm_html.write_text(
            self._build_html_document(book_dir, ebook, chapters, embed_assets=True),
            encoding="utf-8",
        )
        return [output_path, notebooklm_html]

    def _write_html(
        self,
        book_dir: Path,
        filename: str,
        ebook: EbookDetail,
        chapters: List[EbookChapter],
    ) -> List[Path]:
        output_path = book_dir / f"{filename}.html"
        output_path.write_text(
            self._build_html_document(book_dir, ebook, chapters, embed_assets=False),
            encoding="utf-8",
        )
        return [output_path]

    def _write_epub(
        self,
        book_dir: Path,
        filename: str,
        ebook: EbookDetail,
        chapters: List[EbookChapter],
    ) -> Optional[Path]:
        try:
            from converter.epub_generator import EPUBGenerator
        except ImportError:
            logger.warning("未安装 ebooklib，跳过 EPUB 生成")
            return None

        output_path = book_dir / f"{filename}.epub"
        generator = EPUBGenerator(
            title=ebook.title,
            author=ebook.author,
            cover_path=ebook.cover if ebook.cover else None,
        )
        for chapter in chapters:
            generator.add_chapter(
                chapter.title,
                "\n".join(chapter.svg_contents),
                chapter.order,
            )
        generator.generate(output_path)
        return output_path

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理文件名中的非法字符"""
        result = re.sub(r'[<>:"/\\|?*]', '', name)
        return result[:100].strip()


# 便捷函数
def download_ebook(
    ebook_id: str,
    output_dir: Optional[Path] = None,
    output_format: str = "md"
) -> EbookDownloadResult:
    """下载电子书（便捷函数）

    Args:
        ebook_id: 电子书 ID
        output_dir: 输出目录
        output_format: 输出格式

    Returns:
        下载结果
    """
    downloader = EbookDownloader(output_dir=output_dir)
    return downloader.download(ebook_id, output_format)
