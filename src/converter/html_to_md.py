"""内容转换模块

提供 HTML 转 Markdown、Markdown 转 PDF 等功能。
"""

import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HTMLToMarkdownConverter:
    """HTML 转 Markdown 转换器

    将得到课程的 HTML 内容转换为干净的 Markdown 格式。
    """

    # HTML 标签到 Markdown 的映射
    BLOCK_PATTERNS = {
        r'<h1[^>]*>(.*?)</h1>': r'# \1\n\n',
        r'<h2[^>]*>(.*?)</h2>': r'## \1\n\n',
        r'<h3[^>]*>(.*?)</h3>': r'### \1\n\n',
        r'<h4[^>]*>(.*?)</h4>': r'#### \1\n\n',
        r'<p[^>]*>(.*?)</p>': r'\1\n\n',
        r'<br\s*/?>': '\n',
        r'<hr\s*/?>': '\n---\n',
        r'<blockquote[^>]*>(.*?)</blockquote>': r'> \1\n\n',
        r'<pre[^>]*>(.*?)</pre>': r'```\n\1\n```\n\n',
        r'<code[^>]*>(.*?)</code>': r'`\1`',
        r'<ul[^>]*>(.*?)</ul>': r'\1\n',
        r'<ol[^>]*>(.*?)</ol>': r'\1\n',
        r'<li[^>]*>(.*?)</li>': r'- \1\n',
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>': r'[\2](\1)',
        r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>': r'![\2](\1)\n',
        r'<img[^>]*src="([^"]*)"[^>]*>': r'![](\1)\n',
        r'<strong[^>]*>(.*?)</strong>': r'**\1**',
        r'<b[^>]*>(.*?)</b>': r'**\1**',
        r'<em[^>]*>(.*?)</em>': r'*\1*',
        r'<i[^>]*>(.*?)</i>': r'*\1*',
        r'<del[^>]*>(.*?)</del>': r'~~\1~~',
        r'<s[^>]*>(.*?)</s>': r'~~\1~~',
    }

    # 需要移除的标签
    REMOVE_PATTERNS = {
        r'<script[^>]*>.*?</script>': '',
        r'<style[^>]*>.*?</style>': '',
        r'<!--.*?-->': '',
        r'<div[^>]*>': '',
        r'</div>': '',
        r'<span[^>]*>': '',
        r'</span>': '',
        r'<section[^>]*>': '',
        r'</section>': '',
        r'<article[^>]*>': '',
        r'</article>': '',
        r'<header[^>]*>': '',
        r'</header>': '',
        r'<footer[^>]*>': '',
        r'</footer>': '',
        r'<nav[^>]*>': '',
        r'</nav>': '',
    }

    def __init__(self, keep_images: bool = True):
        """初始化转换器

        Args:
            keep_images: 是否保留图片
        """
        self.keep_images = keep_images

    def convert(self, html: str) -> str:
        """将 HTML 转换为 Markdown

        Args:
            html: HTML 内容

        Returns:
            Markdown 内容
        """
        if not html:
            return ""

        text = html

        # 1. 移除不需要的标签
        for pattern, replacement in self.REMOVE_PATTERNS.items():
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)

        # 2. 转换块级元素
        for pattern, replacement in self.BLOCK_PATTERNS.items():
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)

        # 3. 处理实体
        text = self._decode_entities(text)

        # 4. 清理多余空白
        text = self._clean_whitespace(text)

        return text

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

    def _clean_whitespace(self, text: str) -> str:
        """清理多余空白"""
        # 移除每行末尾的空格
        lines = text.split('\n')
        lines = [line.rstrip() for line in lines]
        text = '\n'.join(lines)

        # 将多个空行缩减为最多 2 个
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 移除首尾空白
        text = text.strip()

        return text

    def convert_file(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """转换文件

        Args:
            input_path: 输入 HTML 文件路径
            output_path: 输出 Markdown 文件路径，默认为 input_path 同名但扩展名为 .md

        Returns:
            输出文件路径
        """
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在：{input_path}")

        html = input_path.read_text(encoding='utf-8')
        markdown = self.convert(html)

        if output_path is None:
            output_path = input_path.with_suffix('.md')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding='utf-8')

        logger.info(f"已转换：{input_path} -> {output_path}")
        return output_path


class MarkdownToPDFConverter:
    """Markdown 转 PDF 转换器

    使用 markdown 库将 Markdown 转换为 HTML，再使用 weasyprint 或 wkhtmltopdf 转为 PDF。
    """

    def __init__(self):
        """初始化转换器"""
        self._md = None
        self._check_dependencies()

    def _check_dependencies(self):
        """检查依赖"""
        try:
            import markdown
            self._md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
        except ImportError:
            logger.warning("markdown 库未安装，PDF 转换功能不可用")
            logger.warning("请运行：pip install markdown")

    def convert(
        self,
        markdown_text: str,
        output_path: Path,
        title: Optional[str] = None
    ) -> Optional[Path]:
        """将 Markdown 转换为 PDF

        Args:
            markdown_text: Markdown 内容
            output_path: 输出 PDF 文件路径
            title: PDF 标题

        Returns:
            输出文件路径，如果依赖缺失则返回 None
        """
        if not self._md:
            logger.error("markdown 库未安装，无法转换 PDF")
            return None

        try:
            import markdown
            from markdown.extensions.toc import TocExtension
        except ImportError:
            logger.error("markdown 库未安装")
            return None

        # 转换 Markdown 到 HTML
        md = markdown.Markdown(extensions=[
            'tables',
            'fenced_code',
            'toc',
            'nl2br',
        ])
        html_body = md.convert(markdown_text)
        toc = md.toc  # 目录

        # 构建完整 HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title or 'Document'}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
        }}
        code {{
            background-color: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        pre {{
            background-color: #f5f5f5;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            padding-left: 16px;
            color: #666;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px 12px;
        }}
        th {{
            background-color: #f5f5f5;
            font-weight: 600;
        }}
        img {{
            max-width: 100%;
        }}
        a {{
            color: #0366d6;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""

        # 优先尝试 fpdf2 (纯 Python，无需系统依赖)
        try:
            return self._convert_with_fpdf(markdown_text, output_path, title)
        except Exception as e:
            logger.debug(f"fpdf2 转换失败: {e}")

        # 尝试使用 weasyprint 转换
        try:
            from weasyprint import HTML
            HTML(string=html).write_pdf(str(output_path))
            logger.info(f"已转换 PDF: {output_path}")
            return output_path
        except (ImportError, OSError) as e:
            logger.debug(f"weasyprint 不可用: {e}")

        # 尝试使用 pdfkit (需要 wkhtmltopdf)
        try:
            import pdfkit
            pdfkit.from_string(html, str(output_path), options={'quiet': ''})
            logger.info(f"已转换 PDF: {output_path}")
            return output_path
        except (ImportError, OSError) as e:
            logger.debug(f"pdfkit 不可用: {e}")

        # 如果都无法使用，保存为 HTML
        logger.warning("无法生成 PDF，保存为 HTML 文件")
        html_path = output_path.with_suffix('.html')
        html_path.write_text(html, encoding='utf-8')
        return html_path

    def _convert_with_fpdf(
        self,
        markdown_text: str,
        output_path: Path,
        title: Optional[str] = None
    ) -> Optional[Path]:
        """使用 fpdf2 转换 Markdown 到 PDF (纯 Python，无需系统依赖)

        Args:
            markdown_text: Markdown 内容
            output_path: 输出 PDF 文件路径
            title: PDF 标题

        Returns:
            输出文件路径
        """
        from fpdf import FPDF
        import re

        class PDF(FPDF):
            def header(self):
                pass

            def footer(self):
                self.set_y(-15)
                self.set_font('Helvetica', '', 8)
                self.cell(0, 10, f'{self.page_no()}', align='C')

        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # 添加中文字体支持
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',  # macOS
            '/System/Library/Fonts/STHeiti Light.ttc',  # macOS 备选
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',  # Linux
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',  # Linux
            'C:\\Windows\\Fonts\\msyh.ttc',  # Windows 微软雅黑
        ]

        font_name = 'Chinese'
        font_added = False
        for font_path in font_paths:
            try:
                pdf.add_font(font_name, '', font_path, uni=True)
                font_added = True
                break
            except Exception:
                continue

        if not font_added:
            font_name = 'Helvetica'
            logger.warning("未找到中文字体，PDF 可能无法正确显示中文")

        base_size = 12
        pdf.set_font(font_name, '', base_size)

        # 处理标题
        if title:
            pdf.set_font(font_name, '', 18)
            pdf.write(10, title + "\n")
            pdf.ln(5)
            pdf.set_font(font_name, '', base_size)

        # 简单的 Markdown 解析
        lines = markdown_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                pdf.ln(3)
                continue

            # 处理标题 (用字号区分，不用粗体)
            if line.startswith('# '):
                pdf.set_font(font_name, '', 16)
                pdf.write(8, line[2:] + "\n")
                pdf.ln(2)
                pdf.set_font(font_name, '', base_size)
            elif line.startswith('## '):
                pdf.set_font(font_name, '', 14)
                pdf.write(7, line[3:] + "\n")
                pdf.ln(2)
                pdf.set_font(font_name, '', base_size)
            elif line.startswith('### '):
                pdf.set_font(font_name, '', 13)
                pdf.write(6, line[4:] + "\n")
                pdf.ln(1)
                pdf.set_font(font_name, '', base_size)
            elif line.startswith('- ') or line.startswith('* '):
                # 列表项 - 使用 write 方法避免宽度计算问题
                text = line[2:]
                # 移除 Markdown 标记
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                text = re.sub(r'\*(.+?)\*', r'\1', text)
                # 使用缩进和 write 方法
                pdf.set_x(20)
                pdf.write(6, "- ")
                pdf.write(6, text + "\n")
            elif line.startswith('> '):
                # 引用 - 使用 write 方法
                pdf.set_x(20)
                pdf.write(6, "> " + line[2:] + "\n")
            else:
                # 普通文本，移除 Markdown 标记
                text = line
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                text = re.sub(r'\*(.+?)\*', r'\1', text)
                # 使用 write 方法避免宽度计算问题
                pdf.write(6, text + "\n")

        pdf.output(str(output_path))
        logger.info(f"已转换 PDF (fpdf2): {output_path}")
        return output_path

    def convert_file(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        title: Optional[str] = None
    ) -> Optional[Path]:
        """转换文件

        Args:
            input_path: 输入 Markdown 文件路径
            output_path: 输出 PDF 文件路径
            title: PDF 标题

        Returns:
            输出文件路径
        """
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在：{input_path}")

        markdown_text = input_path.read_text(encoding='utf-8')

        if output_path is None:
            output_path = input_path.with_suffix('.pdf')

        return self.convert(markdown_text, output_path, title)


def convert_html_to_markdown(html: str) -> str:
    """便捷函数：HTML 转 Markdown"""
    converter = HTMLToMarkdownConverter()
    return converter.convert(html)


def convert_markdown_to_pdf(
    markdown_text: str,
    output_path: Path,
    title: Optional[str] = None
) -> Optional[Path]:
    """便捷函数：Markdown 转 PDF"""
    converter = MarkdownToPDFConverter()
    return converter.convert(markdown_text, output_path, title)
