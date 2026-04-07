"""JSON 内容转 Markdown 转换器

将得到课程的 JSON 结构化内容转换为 Markdown 格式。
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


def contents_to_markdown(contents: List[Dict[str, Any]]) -> str:
    """将 JSON 结构化内容转换为 Markdown

    Args:
        contents: JSON 内容列表，每个元素包含 type 和对应字段

    Returns:
        Markdown 格式的文本
    """
    if not contents:
        return ""

    result = []

    for content in contents:
        content_type = content.get("type", "")

        if content_type == "audio":
            # 音频标题
            title = content.get("title", "").rstrip(".mp3")
            result.append(f"# {title}\n")

        elif content_type == "header":
            # 标题
            text = content.get("text", "").strip()
            level = content.get("level", 2)
            if text:
                result.append(f"{_get_md_header(level)}{text}\n")

        elif content_type == "blockquote":
            # 引用块
            text = content.get("text", "")
            lines = text.split("\n")
            for line in lines:
                result.append(f"> {line}")
            result.append("")

        elif content_type == "paragraph":
            # 段落
            para_md = _paragraph_to_markdown(content.get("contents", []))
            result.append(para_md)

        elif content_type == "list":
            # 列表
            list_md = _list_to_markdown(content.get("contents", []))
            result.append(list_md)

        elif content_type == "elite":
            # 划重点
            text = content.get("text", "")
            # 处理可能的多行内容
            if text:
                result.append(f"{_get_md_header(2)}划重点\n\n{text}\n")

        elif content_type == "image":
            # 图片
            url = content.get("url", "")
            legend = content.get("legend", "")
            if url:
                if legend:
                    result.append(f'![{legend}]({url} "{legend}")\n')
                else:
                    result.append(f"![]({url})\n")

        elif content_type == "label-group":
            # 标签组
            text = content.get("text", "")
            if text:
                result.append(f"{_get_md_header(2)}`{text}`\n")

        elif content_type == "text":
            # 纯文本
            text = content.get("text", content.get("content", ""))
            if text:
                result.append(f"{text}\n")

    return "\n".join(result)


def _paragraph_to_markdown(contents: Union[List, Any]) -> str:
    """将段落内容转换为 Markdown

    Args:
        contents: 段落内容列表

    Returns:
        Markdown 文本
    """
    if not contents:
        return ""

    # 如果 contents 不是列表，尝试转换
    if not isinstance(contents, list):
        if isinstance(contents, str):
            return contents + "\n"
        return str(contents) + "\n"

    result = []

    for item in contents:
        if not isinstance(item, dict):
            result.append(str(item))
            continue

        item_type = item.get("type", "text")

        if item_type == "text":
            text_info = item.get("text", {})
            if isinstance(text_info, str):
                text_content = text_info
                is_bold = False
                is_highlight = False
            else:
                text_content = text_info.get("content", "")
                is_bold = text_info.get("bold", False)
                is_highlight = text_info.get("highlight", False)

            text_content = text_content.strip()

            if is_bold:
                result.append(f" **{text_content}** ")
            elif is_highlight:
                result.append(f" *{text_content}* ")
            else:
                result.append(text_content)

    # 清理并格式化
    res = "".join(result).strip()
    res = res.rstrip("\r\n")
    return f"{res}\n\n"


def _list_to_markdown(contents: Union[List, Any]) -> str:
    """将列表内容转换为 Markdown

    Args:
        contents: 列表内容

    Returns:
        Markdown 文本
    """
    if not contents:
        return ""

    if not isinstance(contents, list):
        return str(contents) + "\n"

    result = []

    for item in contents:
        if not isinstance(item, list):
            item = [item]

        for sub_item in item:
            if not isinstance(sub_item, dict):
                result.append(f"* {sub_item}\n")
                continue

            sub_type = sub_item.get("type", "text")

            if sub_type == "text":
                text_info = sub_item.get("text", {})
                if isinstance(text_info, str):
                    text_content = text_info
                    is_bold = False
                    is_highlight = False
                else:
                    text_content = text_info.get("content", "")
                    is_bold = text_info.get("bold", False)
                    is_highlight = text_info.get("highlight", False)

                text_content = text_content.strip()

                if is_bold:
                    result.append(f"* **{text_content}** ")
                elif is_highlight:
                    result.append(f"* *{text_content}* ")
                else:
                    result.append(f"* {text_content}")

        result.append("\n")

    return "".join(result)


def _get_md_header(level: int) -> str:
    """获取 Markdown 标题前缀

    Args:
        level: 标题级别 1-6

    Returns:
        标题前缀，如 "# "
    """
    headers = {
        1: "# ",
        2: "## ",
        3: "### ",
        4: "#### ",
        5: "##### ",
        6: "###### ",
    }
    return headers.get(level, "## ")


def parse_content_string(content_str: str) -> List[Dict[str, Any]]:
    """解析内容字符串为 JSON 对象列表

    Args:
        content_str: JSON 格式的内容字符串

    Returns:
        解析后的内容列表
    """
    if not content_str:
        return []

    try:
        # 尝试解析为 JSON
        content = json.loads(content_str)
        if isinstance(content, list):
            return content
        elif isinstance(content, dict):
            return [content]
        else:
            return []
    except json.JSONDecodeError:
        # 如果不是 JSON，返回纯文本
        return [{"type": "text", "text": content_str}]


def convert_article_content(content: str) -> str:
    """转换文章内容为 Markdown

    这是主要的入口函数，处理各种格式的文章内容。

    Args:
        content: 文章内容（可能是 JSON 字符串或纯文本）

    Returns:
        Markdown 格式的文本
    """
    if not content:
        return ""

    # 检查是否为 JSON 格式
    content = content.strip()
    if content.startswith("["):
        # JSON 数组格式
        try:
            contents = json.loads(content)
            return contents_to_markdown(contents)
        except json.JSONDecodeError:
            pass

    if content.startswith("{"):
        # JSON 对象格式
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                # 检查是否有 content 字段
                if "content" in data:
                    return convert_article_content(data["content"])
                # 检查是否有 contents 字段
                if "contents" in data:
                    return contents_to_markdown(data["contents"])
                # 单个内容对象
                return contents_to_markdown([data])
        except json.JSONDecodeError:
            pass

    # 纯文本或 HTML，直接返回
    return content


class JsonToMarkdownConverter:
    """JSON 内容转 Markdown 转换器"""

    def __init__(self):
        """初始化转换器"""
        pass

    def convert(self, content: str) -> str:
        """转换内容为 Markdown

        Args:
            content: JSON 格式或纯文本内容

        Returns:
            Markdown 文本
        """
        return convert_article_content(content)

    def convert_file(self, input_path, output_path=None):
        """转换文件

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）

        Returns:
            输出文件路径
        """
        from pathlib import Path

        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在：{input_path}")

        content = input_path.read_text(encoding="utf-8")
        markdown = self.convert(content)

        if output_path is None:
            output_path = input_path.with_suffix(".md")
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")

        logger.info(f"已转换：{input_path} -> {output_path}")
        return output_path
