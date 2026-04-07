"""电子书 HTML 转 Markdown 转换器

使用 BeautifulSoup 解析得到电子书的 HTML，生成干净的 Markdown。
"""

import re
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup, Tag, NavigableString

logger = logging.getLogger(__name__)


class EbookHtmlToMarkdownConverter:
    """电子书 HTML 转 Markdown 转换器"""

    # 块级元素 - 这些元素会在前后产生换行
    BLOCK_ELEMENTS = {
        'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'pre', 'table', 'tr',
        'section', 'article', 'header', 'footer', 'nav', 'main',
        'hr', 'br'
    }

    def __init__(self, keep_images: bool = True, image_dir: Optional[str] = None):
        self.keep_images = keep_images
        self.image_dir = image_dir or "images"

    def convert(self, html: str, title: Optional[str] = None) -> str:
        """将 HTML 转换为 Markdown"""
        if not html:
            return ""

        # 优先使用 lxml 解析器，它对畸形 HTML 处理更好
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            soup = BeautifulSoup(html, 'html.parser')

        # 移除 script 和 style
        for tag in soup.find_all(['script', 'style']):
            tag.decompose()

        body = soup.find('body') or soup

        # 收集内容块
        blocks = self._collect_blocks(body)

        # 构建 Markdown
        lines: List[str] = []

        if title:
            lines.append(f"# {title}")
            lines.append("")

        for block_type, content in blocks:
            if block_type == 'h1':
                lines.append(f"\n# {self._clean_title(content)}\n")
            elif block_type == 'h2':
                lines.append(f"\n## {self._clean_title(content)}\n")
            elif block_type == 'h3':
                lines.append(f"\n### {self._clean_title(content)}\n")
            elif block_type == 'para':
                lines.append(content)
                lines.append("")
            elif block_type == 'image':
                lines.append(f"\n{content}\n")
            elif block_type == 'hr':
                lines.append("\n---\n")
            elif block_type == 'quote':
                for line in content.split('\n'):
                    lines.append(f"> {line}")
                lines.append("")
            elif block_type == 'code':
                lines.append(f"\n```\n{content}\n```\n")
            elif block_type == 'list':
                lines.extend(content)
                lines.append("")
            elif block_type == 'table':
                lines.extend(content)
                lines.append("")

        md = '\n'.join(lines)
        md = self._clean_markdown(md)

        return md

    def _collect_blocks(self, element: Tag) -> List[Tuple[str, str]]:
        """收集内容块

        返回列表，每个元素是 (类型, 内容) 的元组
        """
        blocks: List[Tuple[str, str]] = []

        for child in element.children:
            if isinstance(child, NavigableString):
                continue  # 跳过顶级文本节点

            if not isinstance(child, Tag):
                continue

            tag_name = child.name.lower()

            # 跳过某些标签
            if tag_name in ['script', 'style', 'nav', 'footer']:
                continue

            # 标题标签
            if tag_name == 'h1':
                text = self._extract_inline_text(child)
                if text:
                    blocks.append(('h1', text))
                continue

            if tag_name == 'h2':
                text = self._extract_inline_text(child)
                if text:
                    blocks.append(('h2', text))
                continue

            if tag_name in ['h3', 'h4', 'h5', 'h6']:
                text = self._extract_inline_text(child)
                if text:
                    blocks.append(('h3', text))
                continue

            # 段落
            if tag_name == 'p':
                # 检查是否是标题样式
                heading_level = self._get_heading_level(child)
                if heading_level:
                    text = self._extract_inline_text(child)
                    if text:
                        blocks.append((f'h{heading_level}', text))
                else:
                    text = self._extract_inline_text(child)
                    if text.strip():
                        blocks.append(('para', text))
                continue

            # Div - 检查是否是标题区域
            if tag_name == 'div':
                div_class = child.get('class', [])
                if isinstance(div_class, list):
                    div_class = ' '.join(div_class)

                # 标题区域 - 根据字体大小和内容判断级别
                if 'header0' in div_class or 'header1' in div_class:
                    text = self._extract_inline_text(child)
                    if text:
                        # 检查是否包含章节编号（第X章）- 优先级最高
                        if re.search(r'第\s*\d+\s*章', text):
                            blocks.append(('h2', text))
                            continue

                        # 检查字体大小来确定级别
                        h_tag = child.find(['h1', 'h2', 'h3'])
                        if h_tag:
                            span = h_tag.find('span')
                            if span:
                                style = span.get('style', '')
                                font_match = re.search(r'font-size:\s*(\d+)px', style)
                                if font_match:
                                    size = int(font_match.group(1))
                                    if 'header0' in div_class:
                                        if size >= 22:
                                            blocks.append(('h1', text))
                                        elif size >= 17:
                                            blocks.append(('h2', text))
                                        else:
                                            blocks.append(('h3', text))
                                    else:  # header1
                                        blocks.append(('h3', text))
                                    continue
                        # 默认：header0 -> h2, header1 -> h3
                        level = 'h2' if 'header0' in div_class else 'h3'
                        blocks.append((level, text))
                    continue

                # 普通 div，递归处理
                sub_blocks = self._collect_blocks(child)
                blocks.extend(sub_blocks)
                continue

            # 图片
            if tag_name == 'img':
                if self.keep_images:
                    src = child.get('src', '')
                    alt = child.get('alt', '') or child.get('title', '')
                    if src:
                        # 如果是远程 URL，保留原始 URL；否则使用本地路径
                        if not src.startswith('http'):
                            # 本地图片，修正路径
                            if self.image_dir:
                                src = f"{self.image_dir}/{src.split('/')[-1]}"
                        blocks.append(('image', f"![{alt}]({src})"))
                continue

            # 换行
            if tag_name == 'br':
                continue  # 在段落内处理

            # 分隔线
            if tag_name == 'hr':
                blocks.append(('hr', ''))
                continue

            # 无序列表
            if tag_name == 'ul':
                items = []
                for li in child.find_all('li', recursive=False):
                    text = self._extract_inline_text(li)
                    if text:
                        items.append(f"- {text}")
                if items:
                    blocks.append(('list', items))
                continue

            # 有序列表
            if tag_name == 'ol':
                items = []
                for i, li in enumerate(child.find_all('li', recursive=False), 1):
                    text = self._extract_inline_text(li)
                    if text:
                        items.append(f"{i}. {text}")
                if items:
                    blocks.append(('list', items))
                continue

            # 引用
            if tag_name == 'blockquote':
                text = self._extract_text(child)
                if text:
                    blocks.append(('quote', text))
                continue

            # 代码块
            if tag_name == 'pre':
                code = child.get_text()
                if code.strip():
                    blocks.append(('code', code.strip()))
                continue

            # 表格
            if tag_name == 'table':
                table_lines = self._process_table(child)
                if table_lines:
                    blocks.append(('table', table_lines))
                continue

            # 其他标签 - 递归处理
            sub_blocks = self._collect_blocks(child)
            blocks.extend(sub_blocks)

        return blocks

    def _get_heading_level(self, tag: Tag) -> Optional[int]:
        """判断段落是否为标题样式，        迃回标题级别

        改进逻辑：
        1. 包含章节编号（第X章）的段落 -> h2
        2. 大号标题（>=22px）或红色 -> h1
        3. 中号标题（17-21px）-> h3
        """
        span = tag.find('span')
        if not span:
            return None

        text = tag.get_text(strip=True)
        style = span.get('style', '')
        if not style:
            return None

        # 检查是否包含章节编号（第X章）
        if re.search(r'第\s*\d+\s*章', text):
            return 2

        # 检查字号
        font_match = re.search(r'font-size:\s*(\d+)px', style)
        if font_match:
            size = int(font_match.group(1))
            # 大标题 -> h1
            if size >= 22:
                return 1
            # 中标题 -> h3（而不是 h2）
            if size >= 17:
                return 3

        # 检查红色（某些标题使用红色）
        if 'rgb(178, 34, 34)' in style:
            return 1

        return None

    def _extract_text(self, element: Tag) -> str:
        """提取元素的纯文本"""
        text = element.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _clean_title(self, title: str) -> str:
        """清理标题，去除特殊符号

        - 移除中文引号 ""''
        - 替换破折号为普通连字符
        - 压缩多余空格
        """
        # 移除中文引号和各种引号（使用字符类避免转义问题）
        quotes_to_remove = '"' + "'" + "'" + '"' + "'" + "'"
        for q in quotes_to_remove:
            title = title.replace(q, '')
        # 替换破折号为普通连字符
        title = re.sub(r'[–—]', '-', title)
        # 压缩多余空格
        title = re.sub(r'\s+', ' ', title)
        return title.strip()

    def _extract_inline_text(self, element: Tag) -> str:
        """提取内联内容，保留格式标记"""
        parts: List[str] = []

        def process_node(node):
            if isinstance(node, NavigableString):
                parts.append(str(node))
                return

            if not isinstance(node, Tag):
                return

            name = node.name.lower()

            if name == 'br':
                parts.append('\n')
                return

            if name in ['script', 'style']:
                return

            if name == 'img':
                src = node.get('src', '')
                alt = node.get('alt', '') or node.get('title', '')
                if src:
                    if not src.startswith('http') and self.image_dir:
                        src = f"{self.image_dir}/{src.split('/')[-1]}"
                    parts.append(f" ![{alt}]({src}) ")
                return

            # 获取子节点文本
            inner_text = node.get_text()
            if not inner_text.strip():
                return

            if name in ['strong', 'b']:
                # 检查前一个部分是否已经是加粗结束标记
                # 如果是，合并而不是添加新的标记
                parts.append('**')
                for child in node.children:
                    process_node(child)
                parts.append('**')
            elif name in ['em', 'i']:
                parts.append('*')
                for child in node.children:
                    process_node(child)
                parts.append('*')
            elif name == 'code':
                parts.append('`')
                for child in node.children:
                    process_node(child)
                parts.append('`')
            elif name == 'a':
                href = node.get('href', '')
                text = node.get_text()
                if href and not href.startswith('#'):
                    parts.append(f'[{text}]({href})')
                else:
                    for child in node.children:
                        process_node(child)
            else:
                # 其他标签，递归处理子节点
                for child in node.children:
                    process_node(child)

        for child in element.children:
            process_node(child)

        text = ''.join(parts)
        # 合并连续的加粗标记：**** -> 空
        text = re.sub(r'\*\*\*\*', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _process_table(self, table: Tag) -> List[str]:
        """处理表格"""
        lines = []
        rows = table.find_all('tr')
        if not rows:
            return lines

        for i, row in enumerate(rows):
            cells = row.find_all(['th', 'td'])
            cell_texts = [c.get_text(strip=True) for c in cells]
            lines.append('| ' + ' | '.join(cell_texts) + ' |')

            if i == 0:
                lines.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')

        return lines

    def _clean_markdown(self, md: str) -> str:
        """清理 Markdown"""
        md = self._decode_entities(md)
        md = re.sub(r'\n{3,}', '\n\n', md)

        lines = md.split('\n')
        lines = [line.rstrip() for line in lines]
        md = '\n'.join(lines)

        return md.strip()

    def _decode_entities(self, text: str) -> str:
        """解码 HTML 实体"""
        entities = {
            '&nbsp;': ' ',
            '&lt;': '<',
            '&gt;': '>',
            '&amp;': '&',
            '&quot;': '"',
            '&#39;': "'",
            '&mdash;': '—',
            '&ndash;': '–',
            '&hellip;': '…',
            '&ldquo;': '"',
            '&rdquo;': '"',
            '&lsquo;': ''',
            '&rsquo;': ''',
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        return text

    def convert_file(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        title: Optional[str] = None
    ) -> Path:
        """转换文件"""
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在：{input_path}")

        html = input_path.read_text(encoding='utf-8')

        if self.image_dir is None:
            images_dir = input_path.parent / "images"
            if images_dir.exists():
                self.image_dir = "images"

        markdown = self.convert(html, title)

        if output_path is None:
            output_path = input_path.with_suffix('.md')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding='utf-8')

        logger.info(f"已转换：{input_path} -> {output_path}")
        return output_path


def convert_ebook_html_to_markdown(
    html: str,
    title: Optional[str] = None,
    keep_images: bool = True,
    image_dir: Optional[str] = None
) -> str:
    """便捷函数"""
    converter = EbookHtmlToMarkdownConverter(
        keep_images=keep_images,
        image_dir=image_dir
    )
    return converter.convert(html, title)


def convert_ebook_html_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    title: Optional[str] = None
) -> Path:
    """便捷函数"""
    converter = EbookHtmlToMarkdownConverter()
    return converter.convert_file(input_path, output_path, title)
