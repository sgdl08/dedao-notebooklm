"""得到 (Dedao) 模块

提供得到 App 内容的下载功能。

主要组件：
- BaseClient: 基础客户端
- course: 课程模块
- ebook: 电子书模块
- audiobook: 有声书模块
- dedao_dl: dedao-dl 工具封装
"""

# 基础类
from .base import BaseClient, DedaoAPIError, DedaoNetworkError, DedaoAuthError
from .auth import DedaoAuth, get_cookie_from_chrome
from .constants import ContentType, APIEndpoint

# 数据模型
from .models import (
    Course,
    Chapter,
    CourseDetail,
    Audiobook,
    AudiobookChapter,
    AudiobookDetail,
    EbookCatalog,
    EbookDetail,
    EbookChapter,
    EbookPage,
    EbookInfo,
    ChannelPerson,
    ChannelStatistics,
    ChannelInfo,
    ChannelCategory,
    ChannelNote,
    ChannelHomepage,
    Topic,
    TopicNote,
    TopicDetail,
    ContentCategory,
    FreeContent,
)

# 缓存
from .cache import (
    Cache,
    get_cache,
    cache_get,
    cache_set,
    cache_delete,
    CachePrefix,
    CacheTTL,
)

# 账户管理
from .account import (
    Account,
    AccountManager,
    get_account_manager,
    get_current_account,
    get_current_cookie,
    get_current_token,
)

# dedao-dl 工具封装
from .dedao_dl import (
    DedaoDLTool,
    DedaoDLResult,
    get_dedao_dl_tool,
    check_dl_tool,
    sync_cookies,
)

# 子模块导入
from . import course
from . import ebook
from . import audiobook

# 常用类（便捷导入）
from .course import CourseClient, DedaoClient, CourseDownloader, download_course
from .ebook import EbookClient, EbookDownloader, download_ebook

# 向后兼容：保留旧的导入路径
Category = ContentType


__all__ = [
    # 基础类
    "BaseClient",
    "DedaoAPIError",
    "DedaoNetworkError",
    "DedaoAuthError",
    "DedaoAuth",
    "get_cookie_from_chrome",
    "ContentType",
    "Category",  # 向后兼容
    "APIEndpoint",

    # 数据模型
    "Course",
    "Chapter",
    "CourseDetail",
    "Audiobook",
    "AudiobookChapter",
    "AudiobookDetail",
    "EbookCatalog",
    "EbookDetail",
    "EbookChapter",
    "EbookPage",
    "EbookInfo",
    "ChannelPerson",
    "ChannelStatistics",
    "ChannelInfo",
    "ChannelCategory",
    "ChannelNote",
    "ChannelHomepage",
    "Topic",
    "TopicNote",
    "TopicDetail",
    "ContentCategory",
    "FreeContent",

    # 缓存
    "Cache",
    "get_cache",
    "cache_get",
    "cache_set",
    "cache_delete",
    "CachePrefix",
    "CacheTTL",

    # 账户管理
    "Account",
    "AccountManager",
    "get_account_manager",
    "get_current_account",
    "get_current_cookie",
    "get_current_token",

    # dedao-dl 工具
    "DedaoDLTool",
    "DedaoDLResult",
    "get_dedao_dl_tool",
    "check_dl_tool",
    "sync_cookies",

    # 子模块
    "course",
    "ebook",
    "audiobook",

    # 常用类
    "CourseClient",
    "DedaoClient",
    "CourseDownloader",
    "download_course",
    "EbookClient",
    "EbookDownloader",
    "download_ebook",
]
