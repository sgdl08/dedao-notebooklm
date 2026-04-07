"""得到下载工具

下载得到专栏课程、电子书、有声书。
"""

__version__ = "0.4.0"
__author__ = "Your Name"

from .dedao import (
    # 基础
    BaseClient,
    DedaoAPIError,
    ContentType,

    # 课程
    CourseClient,
    CourseDownloader,

    # 电子书
    EbookClient,
    EbookDownloader,

    # 认证
    DedaoAuth,
    get_cookie_from_chrome,

    # dedao-dl 工具
    DedaoDLTool,
    check_dl_tool,
    sync_cookies,
)

from .converter import HTMLToMarkdownConverter

__all__ = [
    "__version__",

    # 基础
    "BaseClient",
    "DedaoAPIError",
    "ContentType",

    # 课程
    "CourseClient",
    "CourseDownloader",

    # 电子书
    "EbookClient",
    "EbookDownloader",

    # 认证
    "DedaoAuth",
    "get_cookie_from_chrome",

    # dedao-dl 工具
    "DedaoDLTool",
    "check_dl_tool",
    "sync_cookies",

    # 转换器
    "HTMLToMarkdownConverter",
]
