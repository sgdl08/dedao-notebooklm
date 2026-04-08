"""SVG 语义块直接转 Markdown 转换器

跳过 HTML 中间层，直接将 SVG 解析后的 SemanticBlock 列表转为干净的 Markdown。
比 SVG→HTML→MD 两层转换保留更多语义信息、格式更准确。
"""

import re
import logging
from html import unescape
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from dedao.ebook.downloader import SemanticBlock

logger = logging.getLogger(__name__)


class SvgToMarkdownRenderer:
    """将 SemanticBlock 列表直接渲染为 Markdown。

    设计目标：
    1. 标题层级准确（基于 SemanticBlock.level）
    2. 段落间距自然
    3. 图片以标准 Markdown 语法嵌入
    4. 表格图采用图片形式保留
    5. 列表项正确缩进
    6. 行内图片（公式等）以 HTML img 保留
    """

    def __init__(self, inline_assets: Optional[Dict[str, Dict[str, str]]] = None):
        self._inline_assets = inline_assets or {}

    def render(
        self,
        blocks: List["SemanticBlock"],
        title: Optional[str] = None,
        author: Optional[str] = None,
        intro: Optional[str] = None,
    ) -> str:
        """将语义块列表渲染为 Markdown 文本。"""
        parts: List[str] = []

        if title:
            parts.append(f"# {self._clean(title)}")
            parts.append("")
        if author:
            parts.append(f"> 作者：{self._clean(author)}")
            parts.append("")
        if intro:
            parts.append(f"> {self._clean(intro)}")
            parts.append("")

        # 跟踪上一个块类型，控制空行
        prev_kind: Optional[str] = None
        list_buffer: List[str] = []
        list_ordered = False

        def flush_list():
            nonlocal list_buffer
            if not list_buffer:
                return
            parts.extend(list_buffer)
            parts.append("")
            list_buffer = []

        for block in blocks:
            kind = block.kind

            if kind == "list_item":
                # 收集列表项
                ordered = block.extra.get("ordered") == "true"
                if list_buffer and ordered != list_ordered:
                    flush_list()
                list_ordered = ordered
                text = self._render_inline(block.text)
                if ordered:
                    list_buffer.append(f"{len(list_buffer) + 1}. {text}")
                else:
                    list_buffer.append(f"- {text}")
                prev_kind = kind
                continue

            # 非列表项时先 flush 列表
            flush_list()

            if kind == "heading":
                level = max(1, min(block.level, 6))
                prefix = "#" * level
                text = self._clean(block.text)
                # 标题前空一行（除非是第一个块）
                if parts and parts[-1] != "":
                    parts.append("")
                parts.append(f"{prefix} {text}")
                parts.append("")

            elif kind == "paragraph":
                text = self._render_inline(block.text)
                if not text:
                    continue
                parts.append(text)
                parts.append("")

            elif kind == "image":
                alt = self._clean(block.alt) if block.alt else ""
                src = block.src
                if parts and parts[-1] != "":
                    parts.append("")
                parts.append(f"![{alt}]({src})")
                parts.append("")

            elif kind == "table_image":
                alt = self._clean(block.alt) if block.alt else "表格"
                src = block.src
                if parts and parts[-1] != "":
                    parts.append("")
                parts.append(f"![{alt}]({src})")
                parts.append("")

            elif kind == "blockquote":
                text = self._render_inline(block.text)
                for line in text.split("\n"):
                    parts.append(f"> {line}")
                parts.append("")

            elif kind == "code":
                parts.append("```")
                parts.append(block.text)
                parts.append("```")
                parts.append("")

            elif kind == "hr":
                parts.append("---")
                parts.append("")

            else:
                # 未知类型当段落处理
                text = self._render_inline(block.text)
                if text:
                    parts.append(text)
                    parts.append("")

            prev_kind = kind

        flush_list()

        md = "\n".join(parts)
        md = self._clean_whitespace(md)
        return md

    def _render_inline(self, text: str) -> str:
        """渲染行内内容，处理内联图片 token。"""
        if not text:
            return ""
        # 先清理非 token 部分的 HTML
        rendered = self._clean(text)
        # 然后替换 inline token → <img> 标签（在 clean 之后，避免 <img> 被 clean 移除）
        for token, info in self._inline_assets.items():
            if token not in rendered:
                continue
            src = info.get("src", "")
            alt = info.get("alt", "")
            rendered = rendered.replace(
                token,
                f'<img src="{src}" alt="{alt}" style="display:inline;height:1.5em;vertical-align:middle" />'
            )
        return rendered

    @staticmethod
    def _clean(text: str) -> str:
        """清理文本：去除 HTML 残留、规范空白。"""
        text = unescape(text)
        text = re.sub(r"<[^>]+>", "", text)  # 移除残留 HTML 标签
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _clean_whitespace(md: str) -> str:
        """规范化空行：最多连续两个换行。"""
        md = re.sub(r"\n{3,}", "\n\n", md)
        return md.strip() + "\n"
